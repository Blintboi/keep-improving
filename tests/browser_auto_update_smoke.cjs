// Run manually with a Chromium/Brave executable. Uses only a disposable profile.
const fs = require("node:fs/promises"),
  path = require("node:path"),
  os = require("node:os");
const { spawn } = require("node:child_process"),
  http = require("node:http");
const { setTimeout: delay } = require("node:timers/promises"),
  assert = require("node:assert/strict");
async function until(fn, label, timeout = 25000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    const value = await fn().catch(() => null);
    if (value) return value;
    await delay(200);
  }
  throw Error("Timed out: " + label);
}
async function cdp(url) {
  const socket = new WebSocket(url),
    requests = new Map();
  let id = 0;
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  socket.onmessage = (event) => {
    const reply = JSON.parse(event.data),
      item = requests.get(reply.id);
    if (!item) return;
    requests.delete(reply.id);
    clearTimeout(item.timer);
    reply.error
      ? item.reject(Error(JSON.stringify(reply.error)))
      : item.resolve(reply.result);
  };
  socket.onclose = () => {
    for (const item of requests.values()) {
      clearTimeout(item.timer);
      item.reject(Error("Target closed"));
    }
    requests.clear();
  };
  return {
    close: () => socket.close(),
    call(method, params = {}) {
      return new Promise((resolve, reject) => {
        const request = ++id,
          timer = setTimeout(() => {
            requests.delete(request);
            reject(Error("CDP timeout: " + method));
          }, 10000);
        requests.set(request, { resolve, reject, timer });
        socket.send(JSON.stringify({ id: request, method, params }));
      });
    },
    async evaluate(expression) {
      const value = await this.call("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (value.exceptionDetails)
        throw Error(JSON.stringify(value.exceptionDetails));
      return value.result.value;
    },
  };
}
(async () => {
  const browserPath = process.argv[2],
    legacyWorker = process.argv[3]?.startsWith("--") ? null : process.argv[3],
    dashboard = process.argv.includes("--dashboard");
  assert.ok(browserPath, "Pass a Chromium/Brave executable");
  const initialVersion = legacyWorker ? "2.39.22" : "2.39.23",
    nextVersion = legacyWorker ? "2.39.23" : "2.39.24";
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gtm-auto-extension-"));
  const extension = path.join(root, "extension"),
    profile = path.join(root, "profile");
  await fs.cp(path.resolve("gametime/browser_extension"), extension, {
    recursive: true,
  });
  if (legacyWorker)
    await fs.copyFile(legacyWorker, path.join(extension, "background.js"));
  const manifest = JSON.parse(
    await fs.readFile(path.join(extension, "manifest.json"), "utf8"),
  );
  manifest.version = initialVersion;
  await fs.writeFile(
    path.join(extension, "manifest.json"),
    JSON.stringify(manifest),
  );
  let desktopVersion = initialVersion,
    restricted = true,
    browser,
    worker,
    browserConnection;
  const server = http.createServer((req, res) => {
    if (req.method === "POST" && req.url === "/activity") {
      assert.equal(req.headers.authorization, "Bearer fixture");
      res.setHeader("Content-Type", "application/json");
      res.end(
        JSON.stringify({
          active: false,
          tracking: true,
          mode: "blocklist",
          allow: [],
          block: [],
          extension_version: desktopVersion,
          lease_seconds: 30,
          language: "en",
          restrictions: restricted
            ? [
                {
                  key: "fixture",
                  domains: ["example.com"],
                  all: false,
                  kind: "cover",
                  minutes: 0,
                  grant: null,
                },
              ]
            : [],
        }),
      );
    } else {
      res.setHeader("Content-Type", "text/html");
      res.end("<title>Local update fixture</title>Fixture");
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const bridgePort = server.address().port;
  try {
    browser = spawn(
      browserPath,
      [
        `--user-data-dir=${profile}`,
        "--headless=new",
        "--remote-debugging-port=0",
        "--enable-unsafe-extension-debugging",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--host-resolver-rules=MAP example.com 127.0.0.1",
        "about:blank",
      ],
      { windowsHide: true, stdio: "ignore" },
    );
    const port = await until(
      async () =>
        Number(
          (
            await fs.readFile(path.join(profile, "DevToolsActivePort"), "utf8")
          ).split("\n")[0],
        ),
      "debug port",
    );
    const endpoint = `http://127.0.0.1:${port}`;
    browserConnection = await cdp(
      (await fetch(endpoint + "/json/version").then((r) => r.json()))
        .webSocketDebuggerUrl,
    );
    const targets = () => fetch(endpoint + "/json/list").then((r) => r.json());
    // Match a normally loaded unpacked extension: the real installation already
    // has Developer mode enabled. Configure only this disposable test profile.
    const setupTarget = await browserConnection.call("Target.createTarget", {
      url: "chrome://extensions/",
    });
    const setupPage = await cdp(
      (
        await until(
          async () =>
            (await targets()).find((t) => t.id === setupTarget.targetId),
          "extension settings",
        )
      ).webSocketDebuggerUrl,
    );
    await until(
      () =>
        setupPage.evaluate(
          "typeof chrome.developerPrivate?.updateProfileConfiguration==='function'",
        ),
      "developer mode API",
    );
    await setupPage.evaluate(
      "new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))",
    );
    setupPage.close();
    await browserConnection.call("Target.closeTarget", {
      targetId: setupTarget.targetId,
    });
    await browserConnection.call("Extensions.loadUnpacked", {
      path: extension,
    });
    const first = await until(
      async () => (await targets()).find((t) => t.type === "service_worker"),
      "initial worker",
    );
    worker = await cdp(first.webSocketDebuggerUrl);
    assert.equal(
      await worker.evaluate("chrome.runtime.getManifest().version"),
      initialVersion,
    );
    const original = `http://example.com:${bridgePort}/original?fixture=kept`;
    await worker.evaluate(
      `(async()=>{await chrome.storage.local.set({pairing:{port:${bridgePort},token:'fixture'},browser:'brave'}); await chrome.tabs.create({url:${JSON.stringify(original)}});})()`,
    );
    await until(
      () =>
        worker.evaluate(
          "chrome.tabs.query({}).then(t=>t.some(x=>x.url?.includes('/blocked.html?key=')))",
        ),
      "covered fixture",
    );
    let dashboardTab;
    if (dashboard) {
      dashboardTab = await worker.evaluate(
        "(async()=>{await chrome.storage.local.set({'draft:upgrade-fixture':{title:'Preserved'}});return chrome.tabs.create({url:chrome.runtime.getURL('panel.html')+'#notifications'});})()",
      );
      dashboardTab = await until(
        () =>
          worker.evaluate(
            `chrome.tabs.get(${dashboardTab.id}).then(t=>t.status==='complete'&&t.url?.endsWith('/panel.html#notifications')?t:null)`,
          ),
        "dashboard committed",
      );
    }
    const before = await worker.evaluate(
      "chrome.storage.local.get('returnPages')",
    );
    assert.ok(
      Object.values(before.returnPages).some((r) => r.url === original),
    );
    const covered = await until(
      () =>
        worker.evaluate(
          "chrome.tabs.query({}).then(t=>t.find(x=>x.url?.includes('/blocked.html?key=') && x.status==='complete'))",
        ),
      "cover committed",
    );
    manifest.version = nextVersion;
    await fs.writeFile(
      path.join(extension, "manifest.json"),
      JSON.stringify(manifest),
    );
    if (legacyWorker)
      await fs.copyFile(
        path.resolve("gametime/browser_extension/background.js"),
        path.join(extension, "background.js"),
      );
    desktopVersion = nextVersion;
    if (legacyWorker) await worker.evaluate("chrome.runtime.openOptionsPage()");
    const next = await until(
      async () =>
        (await targets()).find(
          (t) => t.type === "service_worker" && t.id !== first.id,
        ),
      "automatic reload",
    ).catch(async (error) => {
      console.error(
        "Targets:",
        JSON.stringify(await targets()),
        "exit:",
        browser.exitCode,
      );
      console.error(
        "Extensions:",
        JSON.stringify(
          await browserConnection.call("Extensions.getExtensions"),
        ),
      );
      const diagnosticTarget = await browserConnection.call(
        "Target.createTarget",
        { url: "chrome://extensions/" },
      );
      const diagnostic = await cdp(
        (
          await until(
            async () =>
              (await targets()).find((t) => t.id === diagnosticTarget.targetId),
            "diagnostic page",
          )
        ).webSocketDebuggerUrl,
      );
      await delay(500);
      console.error(
        "Extension detail:",
        JSON.stringify(
          await diagnostic.evaluate(
            "new Promise(r=>chrome.developerPrivate.getExtensionsInfo({includeDisabled:true,includeTerminated:true},r))",
          ),
        ),
      );
      diagnostic.close();
      console.error(
        "Diagnostic:",
        JSON.stringify(
          await worker
            .evaluate(
              "(async()=>({loaded:chrome.runtime.getManifest().version,policy,manifest:await fetch(chrome.runtime.getURL('manifest.json'),{cache:'no-store'}).then(r=>r.json()),attempt:await chrome.storage.local.get('localUpdateAttempt')}))()",
            )
            .catch((error) => ({ closed: true, error: String(error) })),
        ),
      );
      throw error;
    });
    worker.close();
    worker = await cdp(next.webSocketDebuggerUrl);
    await until(
      () =>
        worker.evaluate(
          `typeof chrome!=='undefined' && chrome.runtime.getManifest().version===${JSON.stringify(nextVersion)}`,
        ),
      "new worker initialized",
    );
    const saved = await worker.evaluate(
      "chrome.storage.local.get(['pairing','returnPages'])",
    );
    assert.equal(saved.pairing.token, "fixture");
    assert.ok(Object.values(saved.returnPages).some((r) => r.url === original));
    if (dashboard) {
      await until(
        () =>
          worker.evaluate(
            `chrome.tabs.query({}).then(t=>t.some(x=>x.id===${dashboardTab.id}&&x.url===${JSON.stringify(dashboardTab.url)}))`,
          ),
        "dashboard restored",
      );
      assert.equal(
        (
          await worker.evaluate(
            "chrome.storage.local.get('draft:upgrade-fixture')",
          )
        )["draft:upgrade-fixture"].title,
        "Preserved",
      );
    }
    const tabs = await worker.evaluate("chrome.tabs.query({})");
    assert.equal(tabs.length, dashboard ? 3 : 2);
    assert.ok(tabs.every((t) => !t.url.includes("options.html")));
    assert.ok(
      tabs.some((tab) => tab.id === covered.id && tab.index === covered.index),
      "Original tab and position must survive",
    );
    restricted = false;
    await until(
      () =>
        worker.evaluate(
          `chrome.tabs.query({}).then(t=>t.some(x=>x.url===${JSON.stringify(original)}))`,
        ),
      "released original",
    );
    console.log(
      JSON.stringify({
        automatic_reload: !legacyWorker,
        legacy_bootstrap: !!legacyWorker,
        loaded_version: nextVersion,
        pairing_preserved: true,
        covered_url_preserved: true,
        tab_preserved: true,
        original_restored: true,
        no_update_tab: true,
      }),
    );
    worker.close();
    worker = null;
    await browserConnection.call("Browser.close").catch(() => {});
    await until(async () => browser.exitCode !== null, "browser exit", 10000);
  } finally {
    worker?.close();
    browserConnection?.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    if (browser && browser.exitCode === null) {
      browser.kill();
      await delay(1500);
    }
    const resolved = path.resolve(root),
      prefix = path.join(os.tmpdir(), "gtm-auto-extension-");
    if (resolved.startsWith(prefix))
      await fs.rm(resolved, {
        recursive: true,
        force: true,
        maxRetries: 6,
        retryDelay: 500,
      });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
