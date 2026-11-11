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
  await fs.rm(path.join(report, "timer-fixture.json"), { force: true });
  const fixture = spawn(
    pythonPath,
    ["tests/browser_panel_fixture.py", report],
    { windowsHide: true, stdio: ["ignore","ignore","inherit"] },
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
      "(()=>{chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},()=>{});return true;})()",
    );
    settingsPage.close();
    await connection.call("Target.closeTarget", {
      targetId: settings.targetId,
    });
    const loaded = await connection.call("Extensions.loadUnpacked", {
      path: path.resolve("gametime/browser_extension"),
    });
    const workerTarget = await until(
        async () => (await targets()).find((t) => t.type === "service_worker" && t.url.startsWith(`chrome-extension://${loaded.id}/`)),
        "worker",
      ),
      worker = await cdp(workerTarget.webSocketDebuggerUrl);
    const extension = await until(() => worker.evaluate("typeof chrome!=='undefined' && chrome.runtime?.id"), "extension worker initialized");
    worker.close();
    const created = await connection.call("Target.createTarget", {
      url: `chrome-extension://${extension}/popup.html`,
    });
    page = await cdp(
      (
        await until(
          async () => (await targets()).find((t) => t.id === created.targetId),
          "unpaired popup",
        )
      ).webSocketDebuggerUrl,
    );
    await until(() => page.evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent==='Böngésző csatlakoztatása')"), 'README connection entry');
    await page.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Böngésző csatlakoztatása').click()");
    const pairingTarget = await until(async () => (await targets()).find(t=>t.url===`chrome-extension://${extension}/panel.html#settings`), 'README connection page');
    page.close();
    page = await cdp(pairingTarget.webSocketDebuggerUrl);
    await until(() => page.evaluate("document.querySelector('textarea') && [...document.querySelectorAll('button')].some(b=>b.textContent==='Mentés és kapcsolódás')"), 'pairing form');
    await page.evaluate(`(()=>{const input=document.querySelector('textarea');input.value=${JSON.stringify(JSON.stringify({port:pairing.port,token:pairing.token}))};input.dispatchEvent(new Event('input',{bubbles:true}));[...document.querySelectorAll('button')].find(b=>b.textContent==='Mentés és kapcsolódás').click();})()`);
    await until(() => page.evaluate("document.querySelector('#connection')?.textContent==='Kapcsolódva a helyi alkalmazáshoz'"), 'paired through README flow');
    assert.equal(await page.evaluate(`chrome.storage.local.get('pairing').then(s=>s.pairing.token===${JSON.stringify(pairing.token)} && s.pairing.port===${pairing.port})`),true,'pairing persisted');
    await page.evaluate("[...document.querySelectorAll('#nav button')].find(b=>b.textContent.trim()==='Áttekintés').click()");
    await page.call("Emulation.setDeviceMetricsOverride", {
      width: 1280,
      height: 850,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await until(
      () =>
        page.evaluate(
          "document.querySelector('#heading')?.textContent==='Statisztikák' && document.querySelector('.metric')",
        ),
      "overview",
    );
    const click = async (text) => {
      assert.ok(
        await page.evaluate(
          `(()=>{const b=[...document.querySelectorAll('button')].find(b=>(b.textContent.trim()===${JSON.stringify(text)}||b.getAttribute("aria-label")===${JSON.stringify(text)}));if(!b)return false;b.click();return true;})()`,
        ),
        "button " + text,
      );
      await delay(180);
    };
    const fill = async (label, value, tag = "input") => {
      assert.ok(
        await page.evaluate(
          `(()=>{const label=[...document.querySelectorAll('label.field')].find(n=>n.firstChild.textContent===${JSON.stringify(label)});const input=label?.querySelector(${JSON.stringify(tag)})||[...document.querySelectorAll(${JSON.stringify(tag)})].find(n=>n.getAttribute("aria-label")===${JSON.stringify(label)});if(!input)return false;input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));return true;})()`,
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
    if (process.argv.includes("--scroll")) {
      await page.evaluate("import(chrome.runtime.getURL('scroll-position.js')).then(module=>{window.scrollTools=module;return true})");
      for(const width of [1000,600]) {
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:700,deviceScaleFactor:1,mobile:false});
        await delay(250);
        const before=await page.evaluate("(()=>{const root=scrollTools.scrollRoot(document.querySelector('#content'));root.scrollTop=250;return root.scrollTop})()");
        assert.ok(before>0,'overview scrolls at '+width);
        await page.evaluate("document.querySelector('.day-column').click()");
        await delay(250);
        assert.equal(await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop"),before,'day selection keeps page at '+width);
        await page.evaluate("document.querySelector('#nav button').click()");
        await delay(700);
        assert.equal(await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop"),before,'async page refresh keeps position at '+width);
        await shot('scroll-hu-'+width);
        await click('Tevékenységek');await click('Áttekintés');
        await delay(700);
        assert.equal(await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop"),before,'return restores page at '+width);
      }
      await page.evaluate(`window.scrollFetch=window.fetch;window.fetch=async(url,options)=>{
        if(JSON.parse(options?.body||'{}').action==='statistics')await new Promise(r=>setTimeout(r,600));
        return window.scrollFetch(url,options);};
        document.querySelector('#nav button').click();document.querySelector('#header-actions button').click();`);
      await delay(1000);
      assert.equal(await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop"),0,'late overview request cannot scroll a new subview');
      assert.equal(await page.evaluate("document.querySelector('#content').style.paddingBottom"),'','temporary scroll range is removed');
      await page.evaluate("window.fetch=window.scrollFetch;document.querySelector('#page-back').click()");
      await delay(700);
      assert.equal(await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop"),250,'back from subview restores overview');
      await page.call('Emulation.setDeviceMetricsOverride',{width:1280,height:850,deviceScaleFactor:1,mobile:false});
      await page.evaluate("scrollTools.scrollRoot(document.querySelector('#content')).scrollTop=0");
    }
    if (process.argv.includes("--language")) {
      const key = async (name, code) => {
        await page.call("Input.dispatchKeyEvent", { type: "keyDown", key: name, code: name, windowsVirtualKeyCode: code });
        await page.call("Input.dispatchKeyEvent", { type: "keyUp", key: name, code: name, windowsVirtualKeyCode: code });
      };
      await page.evaluate("document.querySelector('#language').click()");
      await until(() => page.evaluate("[...document.querySelectorAll('#language-options img')].every(i=>i.complete&&i.naturalWidth>0)"), 'dropdown decoded flags');
      assert.equal(await page.evaluate("document.querySelector('#language-options').hidden"), false);
      assert.equal(await page.evaluate("document.activeElement.dataset.language"), 'hu');
      await shot('language-menu-hu-1280');
      await key('Escape',27);
      assert.equal(await page.evaluate("document.querySelector('#language-options').hidden && document.activeElement.id==='language'"),true,'Escape returns focus');
      await page.evaluate(`window.originalFetch=window.fetch;window.languageSaves=0;window.rejectLanguage=false;
        window.fetch=async(url,options)=>{const action=JSON.parse(options?.body||'{}').action;
          if(action==='settings.save'){window.languageSaves++;if(window.rejectLanguage)throw Error('simulated offline');}
          if(['statistics','artwork'].includes(action))await new Promise(r=>setTimeout(r,450));
          return window.originalFetch(url,options);};
        window.watchPaint=(selector)=>{window.paintSamples=[];window.painting=true;const sample=()=>{if(!window.painting)return;window.paintSamples.push(document.querySelectorAll(selector).length);requestAnimationFrame(sample);};sample();};`);
      await page.evaluate("window.watchPaint('.metric');document.querySelector('#language').click()");
      await key('ArrowDown',40); await key('Enter',13);
      await until(() => page.evaluate("document.documentElement.lang==='en' && !document.querySelector('#language').disabled"), 'keyboard language selection');
      await delay(700);
      assert.equal(await page.evaluate("window.painting=false;window.paintSamples.length>2 && window.paintSamples.every(n=>n===4)"),true,'statistics stay painted during delayed language refresh');
      assert.equal(await page.evaluate("document.querySelector('#language-name').textContent"),'English');
      await page.evaluate("document.querySelector('#language').click()");
      await shot('language-menu-en-1280');
      await page.evaluate("document.querySelector('#language-options [data-language=en]').click()");
      assert.equal(await page.evaluate("window.languageSaves"),1,'selecting the current language does not save/rebuild');
      await page.evaluate("document.querySelector('#language').click();document.querySelector('#heading').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))");
      assert.equal(await page.evaluate("document.querySelector('#language-options').hidden"),true,'outside click closes list');
      await click('Activities');
      await until(() => page.evaluate("document.querySelectorAll('.game-tile img').length===3"),'initial artwork');
      await page.evaluate("window.watchPaint('.game-tile img');document.querySelector('#language').click();document.querySelector('#language-options [data-language=hu]').click()");
      await until(() => page.evaluate("document.documentElement.lang==='hu' && !document.querySelector('#language').disabled"),'Hungarian selection');
      await delay(700);
      assert.equal(await page.evaluate("window.painting=false;window.paintSamples.length>2 && window.paintSamples.every(n=>n===3)"),true,'artwork stays painted during language switch');
      await click('Áttekintés');
      assert.equal(await page.evaluate("document.querySelectorAll('.metric').length"),4,'return to statistics uses the previous snapshot immediately');
      await page.evaluate("window.watchPaint('.metric');const period=document.querySelectorAll('.statistics-filters select')[1];period.value='0';period.dispatchEvent(new Event('input',{bubbles:true}))");
      await until(() => page.evaluate("document.querySelector('.metric strong').textContent==='15 p'"),'new period');
      assert.equal(await page.evaluate("window.painting=false;window.paintSamples.length>2 && window.paintSamples.every(n=>n===4)"),true,'period switch keeps prior results until replacement');
      await click('Tevékenységek'); await delay(600);
      assert.equal(await page.evaluate("document.querySelectorAll('.game-card').length===3 && document.querySelectorAll('.metric').length===0"),true,'late statistics response cannot repaint another page');
      for(const width of [1000,760]) {
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile:false});
        await page.evaluate("document.querySelector('#language').click()");
        assert.equal(await page.evaluate("(()=>{const r=document.querySelector('#language-options').getBoundingClientRect();return r.top>=0&&r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight})()"),true,'menu fits viewport '+width);
        await shot('language-menu-hu-'+width);await key('Escape',27);
      }
      await page.evaluate("window.rejectLanguage=true;document.querySelector('#language').click();document.querySelector('#language-options [data-language=en]').click()");
      await until(() => page.evaluate("!document.querySelector('#language').disabled && document.querySelector('#status').textContent.length>0"),'failed switch is recoverable');
      assert.equal(await page.evaluate("document.documentElement.lang==='hu' && document.querySelector('#language').value==='hu' && document.querySelector('#language-name').textContent==='Magyar'"),true,'failed save keeps selected language');
      console.log(JSON.stringify({dropdown_flags:true,keyboard_selection:true,escape_and_outside_click:true,no_redundant_save:true,statistics_no_blank_frames:true,period_no_blank_frames:true,artwork_no_blank_frames:true,late_response_guard:true,narrow_layout:true,failed_save_recovery:true}));
      return;
    }
    await shot("overview-hu-1280");
    assert.equal(await page.evaluate("document.querySelector('.statistics-filters input[type=checkbox]')===null"), true, 'measurement is in Settings');
    await click('Gépek és szinkron');
    await until(() => page.evaluate("document.querySelector('input[autocomplete=off]')"), 'computer linking on overview');
    await fill('Gép neve','Unsaved fixture name');
    await delay(10500);
    assert.equal(await page.evaluate("document.querySelector('input[maxlength=\"80\"]').value"),'Unsaved fixture name','live refresh retains linking input');
    await shot('linking-hu-1280');
    await click('Vissza');
    await until(() => page.evaluate("document.querySelector('#heading').textContent==='Statisztikák' && document.querySelector('.metric')"), 'linking returns to statistics');
    assert.equal(
      await page.evaluate(
        "document.querySelector('.metric strong').textContent",
      ),
      "7 ó",
    );
    await fill("Időszak", "0", "select");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('.metric strong')?.textContent==='15 p'",
        ),
      "today period",
    );
    await fill("Időszak", "7", "select");
    await until(
      () =>
        page.evaluate(
          "document.querySelector('.metric strong')?.textContent==='7 ó'",
        ),
      "seven day period",
    );
    assert.equal(await page.evaluate("document.querySelectorAll('.computer-legend > span').length"),2,'both computers are named');
    assert.equal(await page.evaluate("document.querySelectorAll('.computer-stack.marked').length"),14,'two computer blocks per day');
    assert.equal(await page.evaluate("[...document.querySelectorAll('.computer-stack')].every(n=>getComputedStyle(n,'::before').backgroundColor!=='rgba(0, 0, 0, 0)')"),true,'computer color rails visible');
    assert.equal(await page.evaluate("document.querySelectorAll('thead th').length"),6,'computer, type and sessions columns');
    assert.equal(await page.evaluate("[...document.querySelectorAll('.chart-stack')].every(n=>n.scrollHeight<=n.clientHeight+1)"),true,'tiny activities preserve chart scale without one-pixel inflation');
    await fill('Gép','local','select');
    await until(() => page.evaluate("document.querySelector('.metric strong')?.textContent==='4 ó 40 p'"),'local statistics');
    await fill('Gép','12121212121212121212121212121212','select');
    await until(() => page.evaluate("document.querySelector('.metric strong')?.textContent==='2 ó 20 p'"),'remote statistics');
    await fill('Gép','all','select');
    await fill('Mit szeretnél látni?','websites','select');
    await until(() => page.evaluate("document.querySelector('.metric strong')?.textContent==='2 p' && document.querySelector('tbody').textContent.includes('example.com')"),'website-only statistics');
    await fill('Mit szeretnél látni?','all','select');
    await until(() => page.evaluate("document.querySelector('.metric strong')?.textContent==='7 ó'"),'all statistics restored');
    assert.equal(await page.evaluate("document.querySelectorAll('.metric strong')[2].textContent"),'35','session total follows the selected period and devices');
    assert.equal(await page.evaluate("document.querySelectorAll('.day-sessions').length"),0,'time mode has no extra count row');
    await fill('Mit szeretnél látni?','all:sessions','select');
    assert.equal(await page.evaluate("[...document.querySelectorAll('.chart-stack')].every(n=>n.dataset.value==='5')"),true,'column height follows sessions rather than usage time');
    assert.equal(await page.evaluate("[...document.querySelectorAll('.bar-total')].every(n=>n.textContent==='5')"),true);
    assert.equal(await page.evaluate("document.querySelector('.chart-axis').textContent"),'630','integer count scale');
    assert.ok(await page.evaluate("[...document.querySelectorAll('.chart-segment')].every(e=>e.title.includes('Munkamenetek:'))"),'activity blocks show session counts');
    await fill('Rendezés','sessions_desc','select');
    assert.equal(await page.evaluate("document.querySelector('tbody tr td:last-child').textContent"),'21','descending session counts');
    await fill('Rendezés','sessions_asc','select');
    assert.equal(await page.evaluate("document.querySelector('tbody tr td:last-child').textContent"),'0','ascending session counts');
    await fill('Rendezés','sessions_desc','select');
    for (const [lang,width] of [['en',1000],['hu',1280]]) {
      await page.call('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile:false});
      await page.evaluate(`(()=>{const n=document.querySelector('#language');n.value='${lang}';n.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await until(() => page.evaluate(`document.documentElement.lang==='${lang}' && document.querySelectorAll('.computer-stack').length===14`),'translated statistics');
      await shot(`statistics-sessions-${lang}-${width}`);
      await fill(lang==='hu'?'Mit szeretnél látni?':'Show activity','all','select');
      assert.equal(await page.evaluate("[...document.querySelectorAll('.chart-stack')].some(n=>Number(n.dataset.value)>5)"),true,'time geometry restored');
      await shot(`statistics-time-${lang}-${width}`);
      await fill(lang==='hu'?'Mit szeretnél látni?':'Show activity','all:sessions','select');
      await page.evaluate("document.querySelector('.table-wrap').scrollIntoView({block:'start'})");
      await shot(`statistics-details-${lang}-${width}`);
      await page.evaluate("document.querySelector('.statistics-filters').scrollIntoView({block:'start'})");
    }
    for (const [name, id] of [
      ["Tevékenységek", "activities"],
      ["Keretek", "budgets"],
      ["Értesítések", "notifications"],
      ["Fókusz mód", "focus"],
    ]) {
      await click(name);
      if (id === "activities") {
        await until(
          () =>
            page.evaluate("document.querySelectorAll('.game-card').length===3"),
          "native game cards",
        );
        await until(() => page.evaluate("[...document.querySelectorAll('.game-tile img')].filter(i=>i.complete&&i.naturalWidth>0).length===3"), 'real decoded game images');
        assert.equal(await page.evaluate("[...document.querySelectorAll('.game-card h3')].filter(n=>n.textContent==='Fixture Alpha').length"),1,'retired duplicate hidden');
        await page.evaluate("window.iconReplies=[];window.iconFetch=window.fetch;window.fetch=async(url,options)=>{const response=await window.iconFetch(url,options);if(String(url).endsWith('/control')&&JSON.parse(options.body).action==='library.icons')response.clone().json().then(value=>window.iconReplies.push(value));return response}");
        for (const [tab,key,file] of [['Alkalmazások','app:notepad.exe','applications'],['Weboldalak','site:example.com','websites']]) {
          await click(tab);
          await until(() => page.evaluate(`window.iconReplies.some(value=>value.result?.[${JSON.stringify(key)}]?.has_image===true)`),'resolved '+file+' image from desktop pipeline');
          assert.equal(await page.evaluate(`document.querySelector('[data-activity-image="${key}"] img')?.naturalWidth>0`),true,'decoded '+file+' icon');
          await shot(file+'-icons-hu-1280');
        }
        await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))");
        await delay(1200);
        const reads=await page.evaluate('window.iconReplies.length');
        await delay(1400);
        assert.equal(await page.evaluate('window.iconReplies.length'),reads,'hidden browser does not poll icons');
        await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))");
        await click('Játékok');
      }
      await shot(id + "-hu-1280");
      if (id === 'activities' && process.argv[5] === '--statistics-library-only') {
        await page.call('Emulation.setDeviceMetricsOverride',{width:1000,height:700,deviceScaleFactor:1,mobile:false});
        await page.evaluate("document.querySelector('#language').value='en';document.querySelector('#language').dispatchEvent(new Event('change'))");
        await until(() => page.evaluate("document.documentElement.lang==='en' && [...document.querySelectorAll('.game-tile img')].filter(i=>i.complete&&i.naturalWidth>0).length===3"),'English library images');
        await shot('activities-en-1000');
        console.log(JSON.stringify({multi_computer_statistics:true,website_statistics:true,proportional_segments:true,retired_game_filter:true,decoded_game_images:true,screenshots:true}));
        return;
      }
      assert.equal(await page.evaluate("[...document.querySelectorAll('#header-actions button')].some(b=>['Beállítások','Játékmappa'].includes(b.getAttribute('aria-label')))"), false, 'no duplicated settings shortcuts');
      if (id === 'notifications')
        assert.equal(await page.evaluate("document.querySelector('.notification-display')===null"),true,'global display controls are in Settings');
      if (id === 'budgets' || id === 'focus')
        await until(() => page.evaluate("document.querySelector('#content .activity-image img')?.naturalWidth>0"),'icons in '+id);
      assert.equal(
        await page.evaluate("document.querySelector('#status').textContent"),
        "",
      );
    }
    await click("Időzítő beállításai");
    await fill("Fókusz hossza (perc)", "17");
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
    await fill("Gomb az értesítésen", "pomodoro", "select");
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
    await click("Keretek");
    await click("Új hozzáadása");
    await fill("A keret neve", "Böngészős keret");
    await click("Tag hozzáadása");
    await fill("Domain vagy webcím", "https://example.com/path");
    await click("Hozzáadás");
    await click("Művelet hozzáadása");
    await fill("Mikor", "usage", "select");
    await fill("Használat után (perc)", "10");
    await fill("Mikor", "sessions", "select");
    await fill("Engedélyezett munkamenetek", "5");
    assert.equal(await page.evaluate("document.querySelector('form').textContent.includes('megújulásakor nullázódik')"),true);
    await shot("budget-editor-hu-1280");
    await page.evaluate("[...document.querySelectorAll('label.check')].find(n=>n.textContent==='Kérdezze meg a megnyitás célját').querySelector('input').click()");
    await fill('Kérdés','Miért nézed meg a statisztikát?');
    await fill('Munkamenetkeret','activity','select');
    assert.equal(await page.evaluate("[...document.querySelectorAll('label.field')].some(n=>n.firstChild.textContent==='Engedélyezett munkamenetek')"),false);
    assert.equal(await page.evaluate("[...document.querySelectorAll('label.field input')].some(n=>n.value==='Munka miatt')"),true);
    await fill('Napi alkalmak','2');
    await page.evaluate("[...document.querySelectorAll('label.field')].find(n=>n.firstChild.textContent==='Kérdés').scrollIntoView({block:'start'})");
    await shot('opening-choices-hu-1280');
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
    assert.equal(await page.evaluate("[...document.querySelectorAll('#content label')].some(n=>n.textContent.includes('Alkalmazások és weboldalak idejének mérése'))"),true,'measurement setting exists');
    await fill('Napváltás','02:00');
    await click('Emlékeztetők');
    await shot('settings-reminders-hu-1280');
    assert.equal(await page.evaluate("[...document.querySelectorAll('#content label')].some(n=>n.textContent.includes('Részletes RTSS-számláló'))"),true,'display setting exists');
    const protectedCheck = "[...document.querySelectorAll('#content label')].find(n=>n.textContent.includes('anticheates')).querySelector('input')";
    await page.evaluate(protectedCheck+'.click()');
    await until(() => page.evaluate("document.querySelector('#dialog').open"), 'permission notice');
    await click('Mégse');
    assert.equal(await page.evaluate(protectedCheck+'.checked'),false,'cancel retains disabled permission');
    await page.evaluate(protectedCheck+'.click()');
    assert.equal(await page.evaluate("document.querySelector('#dialog .primary').disabled"),true,'permission requires consent');
    await page.evaluate("document.querySelector('#dialog input[type=checkbox]').click()");
    await click('Saját felelősségre engedélyezem');
    await until(() => page.evaluate(protectedCheck+'.checked'), 'permission saved in disposable profile');
    await page.evaluate(protectedCheck+'.click()');
    await until(async () => !(await page.evaluate(protectedCheck+'.checked')), 'permission revoked');
    await click('Frissítések');
    assert.equal(await page.evaluate("[...document.querySelectorAll('#content button')].some(b=>b.textContent==='Gépek összekapcsolása')"),false,'linking not duplicated in Settings');
    await click('Általános');
    assert.equal(await page.evaluate("document.querySelector('input[type=time]').value"),'02:00','permission changes retain general draft');
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
    await page.evaluate(
      'document.querySelector("#language").value="en";document.querySelector("#language").dispatchEvent(new Event("change"))',
    );
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
    await click("Budgets");
    await shot("budgets-en-1000");
    await click("Notifications");
    await shot("notifications-en-1000");
    for (const language of ['en','hu']) {
      await page.evaluate(`document.querySelector('#language').value=${JSON.stringify(language)};document.querySelector('#language').dispatchEvent(new Event('change'))`);
      await until(() => page.evaluate(`document.documentElement.lang===${JSON.stringify(language)}`),'settings capture language');
      for (const width of [1000,1280]) {
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:width===1000?700:850,deviceScaleFactor:1,mobile:false});
        await click(language==='hu'?'Beállítások':'Settings');
        await click(language==='hu'?'Általános':'General');
        await shot(`settings-general-${language}-${width}`);
        await click(language==='hu'?'Emlékeztetők':'Reminders');
        await shot(`settings-reminders-${language}-${width}`);
        await click(language==='hu'?'Frissítések':'Updates');
        await shot(`settings-updates-${language}-${width}`);
        await click(language==='hu'?'Áttekintés':'Overview');
        await click(language==='hu'?'Gépek és szinkron':'Computers & sync');
        await until(() => page.evaluate("document.querySelector('input[autocomplete=off]')"),'linking capture');
        await shot(`linking-${language}-${width}`);
        await click(language==='hu'?'Vissza':'Back');
      }
    }
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
    const timers = () => page.evaluate("[...document.querySelectorAll('#timers .card')].map(n=>({key:n.dataset.timerKey,text:n.textContent,time:n.querySelector('strong').textContent}))");
    const scenario = async (items, language = "en") => {
      await fs.writeFile(path.join(report, "timer-fixture.json"), JSON.stringify({ language, timers: items }));
    };
    const sleep = {key:'sleep',name:'Sleep mode',event:'clock_limit',seconds:1800,wall_clock:true};
    const web = {key:'web',name:'Video',event:'break',seconds:60,total:600,active:true,scope:'site'};
    await scenario([sleep, web, {key:'focus',name:'Focus',event:'focus',seconds:1,wall_clock:true}]);
    await until(async () => (await timers()).map(t=>t.key).join(',') === 'web,sleep', 'nearest timer first and focus not duplicated');
    await page.evaluate("window.originalTimer=document.querySelector('#timers .card');window.originalButton=document.querySelector('#popup-content button');window.originalFetch=window.fetch;window.reads=[];window.fetch=(url,options)=>{if(String(url).endsWith('/control'))window.reads.push(JSON.parse(options.body).action);return window.originalFetch(url,options)}");
    const before = (await timers())[0].time;
    await until(async () => (await timers())[0].time !== before, 'visible countdown ticks');
    assert.equal(await page.evaluate("window.originalTimer===document.querySelector('#timers .card') && window.originalButton===document.querySelector('#popup-content button')"), true, 'countdown does not rebuild controls');
    assert.equal(await page.evaluate("window.reads.length>0 && window.reads.every(a=>a==='live')"), true, 'ticks use lightweight live reads');
    await shot('popup-timers-en-380');
    await scenario([{...sleep,seconds:25}, {...web,seconds:120,event:'break_active',wall_clock:true,active:false}]);
    await until(async () => {const rows=await timers();return rows[0]?.key==='sleep' && rows[1]?.text.includes('Break remaining')}, 'order and labels change while popup remains open');
    await scenario([{...web,seconds:90,event:'save',wall_clock:true}, {...web,key:'restricted',name:'Games',seconds:0,event:'limit'}, sleep], 'hu');
    await until(async () => {const rows=await timers();return rows[0]?.key==='restricted' && rows.some(r=>r.text.includes('Mentési időből hátra'))}, 'Hungarian restriction and save countdown');
    await shot('popup-timers-hu-380');
    assert.equal(await page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'), true, 'multiple timers have no horizontal overflow');
    await page.call('Emulation.setDeviceMetricsOverride', {width:340,height:600,deviceScaleFactor:1,mobile:false});
    await page.evaluate("document.body.style.width='340px'");
    await shot('popup-timers-hu-340');
    assert.equal(await page.evaluate('document.documentElement.scrollWidth<=340'), true, 'narrow popup has no horizontal overflow');
    await scenario([{...web,active:false,seconds:60,event:'quota'}]);
    await until(async () => (await timers()).length===1 && (await timers())[0].time==='01:00', 'paused use timer');
    await delay(2200);
    assert.equal((await timers())[0].time,'01:00','inactive use budget does not count down');
    await shot('popup-timers-en-340');
    await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))");
    await delay(300);
    const hiddenReads=await page.evaluate('window.reads.length');
    await delay(2200);
    assert.equal(await page.evaluate('window.reads.length'),hiddenReads,'hidden popup does not poll');
    await scenario([]);
    await page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))");
    await until(() => page.evaluate("document.querySelector('#no-timers')?.hidden===false && document.querySelector('#timers').children.length===0"), 'resume and remove completed timers');
    await page.evaluate("window.fetch=()=>Promise.reject(Error('fixture offline'))");
    await until(() => page.evaluate("!document.querySelector('#connected').classList.contains('online') && !document.querySelector('#timers')"), 'disconnect clears stale timers');
    await scenario([web]);
    await page.evaluate('window.fetch=window.originalFetch');
    await until(async () => (await timers())[0]?.key==='web', 'reconnect without reopening');
    await scenario([{...web,event:'break',seconds:60}, {...sleep,seconds:60}]);
    await until(async () => {const rows=await timers();return rows.length===2 && rows[0].key==='sleep'}, 'same-time restriction wins');
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
        multi_computer_statistics: true,
        website_statistics: true,
        retired_game_filter: true,
        decoded_game_images: true,
        readme_pairing_flow: true,
        centralized_settings: true,
        linking_return_and_drafts: true,
        popup_live_timers: true,
        popup_order_and_transitions: true,
        popup_hidden_idle: true,
        popup_reconnection: true,
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
