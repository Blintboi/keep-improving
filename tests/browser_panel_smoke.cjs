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
// Real browser, real local bridge, entirely disposable profiles.
(async () => {
  const browserPath = process.argv[2],
    pythonPath = process.argv[3];
  assert.ok(
    browserPath && pythonPath,
    "Pass a Chromium/Brave executable and Python with PySide6",
  );
  const report = path.resolve(process.argv[4] || "test-reports/browser-panel");
  await fs.mkdir(report, { recursive: true });
  await fs.rm(path.join(report, "stop-fixture"), { force: true });
  await fs.rm(path.join(report, "fixture.json"), { force: true });
  const fixture = spawn(
    pythonPath,
    ["tests/browser_panel_fixture.py", report],
    { windowsHide: true, stdio: "ignore" },
  );
  const pairing = await until(
    async () =>
      JSON.parse(await fs.readFile(path.join(report, "fixture.json"), "utf8")),
    "desktop fixture",
  );
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gtm-panel-")),
    profile = path.join(root, "profile");
  let browser, connection, page;
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
        "about:blank",
      ],
      { windowsHide: true, stdio: "ignore" },
    );
    const lines = await until(
      async () =>
        String(await fs.readFile(path.join(profile, "DevToolsActivePort")))
          .trim()
          .split("\n"),
      "browser",
    );
    connection = await cdp(`ws://127.0.0.1:${lines[0]}${lines[1]}`);
    const targets = () =>
      fetch(`http://127.0.0.1:${lines[0]}/json/list`).then((r) => r.json());
    const settings = await connection.call("Target.createTarget", {
      url: "chrome://extensions/",
    });
    const settingsPage = await cdp(
      (
        await until(
          async () => (await targets()).find((t) => t.id === settings.targetId),
          "settings",
        )
      ).webSocketDebuggerUrl,
    );
    await until(
      () =>
        settingsPage.evaluate(
          "typeof chrome.developerPrivate?.updateProfileConfiguration==='function'",
        ),
      "developer mode",
    );
    await settingsPage.evaluate(
      "new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))",
    );
    settingsPage.close();
    await connection.call("Target.closeTarget", {
      targetId: settings.targetId,
    });
    const loaded = await connection.call("Extensions.loadUnpacked", {
      path: path.resolve("gametime/browser_extension"),
    });
    const workerTarget = await until(
        async () => (await targets()).find((t) => t.type === "service_worker"),
        "worker",
      ),
      worker = await cdp(workerTarget.webSocketDebuggerUrl);
    const extension = await worker.evaluate("chrome.runtime.id");
    await worker.evaluate(
      `chrome.storage.local.set({pairing:${JSON.stringify({ port: pairing.port, token: pairing.token })},browser:'brave'})`,
    );
    worker.close();
    const created = await connection.call("Target.createTarget", {
      url: `chrome-extension://${extension}/panel.html`,
    });
    page = await cdp(
      (
        await until(
          async () => (await targets()).find((t) => t.id === created.targetId),
          "dashboard",
        )
      ).webSocketDebuggerUrl,
    );
    await page.call("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 850,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#heading')?.textContent==='Áttekintés' && document.querySelector('.metric')",
        ),
      "overview",
    );
    const click = async (text) => {
      assert.ok(
        await page.evaluate(
          `(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!b)return false;b.click();return true;})()`,
        ),
        "button " + text,
      );
      await delay(180);
    };
    const fill = async (label, value, tag = "input") => {
      assert.ok(
        await page.evaluate(
          `(()=>{const label=[...document.querySelectorAll('label.field')].find(n=>n.firstChild.textContent===${JSON.stringify(label)});const input=label?.querySelector(${JSON.stringify(tag)});if(!input)return false;input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`,
        ),
        "field " + label,
      );
    };
    const shot = async (name) => {
      const value = await page.call("Page.captureScreenshot", {
        format: "png",
      });
      await fs.writeFile(
        path.join(report, name + ".png"),
        Buffer.from(value.data, "base64"),
      );
      assert.equal(
        await page.evaluate("document.documentElement.scrollWidth>innerWidth"),
        false,
        "horizontal overflow " + name,
      );
    };
    await shot("overview-hu-1280");
    assert.equal(
      await page.evaluate(
        "document.querySelector('.metric strong').textContent",
      ),
      "4 ó 40 p",
    );
    await fill("Idő", "0", "select");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('.metric strong')?.textContent==='0 ó 10 p'",
        ),
      "today period",
    );
    await fill("Idő", "7", "select");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('.metric strong')?.textContent==='4 ó 40 p'",
        ),
      "seven day period",
    );
    for (const [name, id] of [
      ["Tevékenységek", "activities"],
      ["Időkeretek", "budgets"],
      ["Értesítések", "notifications"],
      ["Fókusz mód", "focus"],
    ]) {
      await click(name);
      await shot(id + "-hu-1280");
      assert.equal(
        await page.evaluate("document.querySelector('#status').textContent"),
        "",
      );
    }
    await click("Időzítő beállításai");
    await fill("Fókusz (perc)", "17");
    await fill("Rövid szünet (perc)", "0");
    await fill("Hosszú szünet (perc)", "0");
    await fill("Körök a hosszú szünetig", "0");
    await click("Módosítások mentése");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#focus-clock')?.textContent==='17:00'",
        ),
      "saved focus",
    );
    await click("Fókusz indítása");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#content').textContent.includes('Szüneteltetés')",
        ),
      "focus started",
    );
    await click("Leállítás");
    await click("Értesítések");
    await click("Új hozzáadása");
    await fill("Cím", "Böngészős próba");
    await fill("Szöveg", "Mentés és újranyitás ellenőrzése", "textarea");
    await fill("Mikor jelenjen meg?", "startup", "select");
    await fill("Értesítés gombja", "pomodoro", "select");
    await fill("Rövid szünet (perc)", "0");
    await fill("Hosszú szünet (perc)", "0");
    await fill("Körök a hosszú szünetig", "0");
    await fill("Bezárás", "manual", "select");
    await shot("notification-hu-1280");
    await click("Módosítások mentése");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#content').textContent.includes('Böngészős próba')&&!document.querySelector('form')",
        ),
      "notification saved",
    );
    await click("Időkeretek");
    await click("Új hozzáadása");
    await fill("Időkeret neve", "Böngészős keret");
    await click("Tag hozzáadása");
    await fill("Domain vagy webcím", "https://example.com/path");
    await click("Hozzáadás");
    await click("Művelet hozzáadása");
    await fill("Mikor", "usage", "select");
    await fill("Használat után (perc)", "10");
    await shot("budget-editor-hu-1280");
    await click("Módosítások mentése");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#content').textContent.includes('Böngészős keret')&&!document.querySelector('form')",
        ),
      "budget saved",
    );
    await click("Értesítések");
    await click("Új hozzáadása");
    await fill("Cím", "Megmaradó piszkozat");
    await fill("Szöveg", "Piszkozat teszt", "textarea");
    await click("Tevékenységek");
    await click("Értesítések");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#content').textContent.includes('Megmaradó piszkozat')",
        ),
      "new draft listed",
    );
    await click("Szerkesztés folytatása");
    assert.equal(
      await page.evaluate(
        "document.querySelector('input[maxlength=\"80\"]').value",
      ),
      "Megmaradó piszkozat",
    );
    await click("Vissza");
    await click("Beállítások");
    await delay(100);
    await shot("settings-hu-1280");
    const text = await page.evaluate("document.body.innerText");
    assert.ok(!text.includes("\nnull\n"), "no null text");
    await fill("Napváltás", "02:00");
    await click("Módosítások mentése");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#status').textContent==='Mentve.'",
        ),
      "settings saved",
    );
    await click("English");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#nav').textContent.includes('Overview')",
        ),
      "English",
    );
    await click("Focus mode");
    await page.call("Emulation.setDeviceMetricsOverride", {
      width: 1000,
      height: 700,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await shot("focus-en-1000");
    await click("Time budgets");
    await shot("budgets-en-1000");
    await click("Notifications");
    await shot("notifications-en-1000");
    await page.call("Page.navigate", {
      url: `chrome-extension://${extension}/popup.html`,
    });
    await delay(900);
    await page.call("Emulation.setDeviceMetricsOverride", {
      width: 380,
      height: 600,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await shot("popup-en");
    console.log(
      JSON.stringify({
        dashboard: true,
        navigation: true,
        focus_save: true,
        focus_start_stop: true,
        notification_save: true,
        settings_save: true,
        language: true,
        screenshots: true,
      }),
    );
  } catch (error) {
    if (page) {
      console.log(
        await page.evaluate(
          "document.querySelector('#status')?.textContent+' | '+document.querySelector('.error')?.textContent",
        ),
      );
      const shot = await page.call("Page.captureScreenshot", { format: "png" });
      await fs.writeFile(
        path.join(report, "failure.png"),
        Buffer.from(shot.data, "base64"),
      );
    }
    throw error;
  } finally {
    await fs.writeFile(path.join(report, "stop-fixture"), "stop");
    await until(
      async () => fixture.exitCode !== null,
      "fixture exit",
      10000,
    ).catch(() => fixture.kill());
    page?.close();
    if (connection) {
      await connection.call("Browser.close").catch(() => {});
      connection.close();
    }
    if (browser && browser.exitCode === null) {
      await delay(1000);
      browser.kill();
    }
    if (path.resolve(root).startsWith(path.join(os.tmpdir(), "gtm-panel-")))
      await fs.rm(root, {
        recursive: true,
        force: true,
        maxRetries: 5,
        retryDelay: 500,
      });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
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
