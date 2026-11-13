// Real extension + desktop, local synthetic website and disposable browser profile.
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),http=require('node:http');
const {spawn}=require('node:child_process'),{setTimeout:delay}=require('node:timers/promises'),assert=require('node:assert/strict');
async function until(fn,label,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){const v=await fn().catch(()=>null);if(v)return v;await delay(100);}throw Error('Timed out: '+label);}
async function cdp(url){const socket=new WebSocket(url),pending=new Map();let id=0;
  await new Promise((ok,no)=>{socket.onopen=ok;socket.onerror=no;});
  socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.no(Error(JSON.stringify(r.error))):p.ok(r.result);};
  const api={close:()=>socket.close(),call(method,params={}){return new Promise((ok,no)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);no(Error(method+' timeout'));},10000);pending.set(n,{ok,no,timer});socket.send(JSON.stringify({id:n,method,params}));});},
    async evaluate(expression){const r=await api.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}};return api;}
(async()=>{
  const [browserPath,pythonPath,reportArg]=process.argv.slice(2),report=path.resolve(reportArg || 'test-reports/idle-tracking-2490/browser');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json'])await fs.rm(path.join(report,name),{force:true});
  const fixture=spawn(pythonPath,['tests/website_choices_fixture.py',report,'choice.example.com','reconnect'],{windowsHide:true,stdio:['ignore','ignore','inherit']});
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-idle-settings-'));let browser,connection,worker,page;
  try{
    const pairing=await until(async()=>JSON.parse(await fs.readFile(path.join(report,'fixture.json'),'utf8')),'desktop');
    browser=spawn(browserPath,[`--user-data-dir=${temp}`,'--headless=new','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--no-first-run','--no-default-browser-check','--disable-background-networking','--no-proxy-server','about:blank'],{windowsHide:true,stdio:'ignore'});
    const ports=await until(async()=>String(await fs.readFile(path.join(temp,'DevToolsActivePort'))).trim().split('\n'),'browser');
    connection=await cdp(`ws://127.0.0.1:${ports[0]}${ports[1]}`);const targets=()=>fetch(`http://127.0.0.1:${ports[0]}/json/list`).then(r=>r.json());
    async function open(url){const c=await connection.call('Target.createTarget',{url});const target=await until(async()=>(await targets()).find(t=>t.id===c.targetId),'target');return {id:c.targetId,client:await cdp(target.webSocketDebuggerUrl)};}
    const settings=await open('chrome://extensions/');await until(()=>settings.client.evaluate("typeof chrome.developerPrivate?.updateProfileConfiguration==='function'"),'developer mode');
    await settings.client.evaluate('(()=>{chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},()=>{});return true;})()');settings.client.close();await connection.call('Target.closeTarget',{targetId:settings.id});
    const extension=await connection.call('Extensions.loadUnpacked',{path:path.resolve('gametime/browser_extension')});
    const target=await until(async()=>(await targets()).find(t=>t.type==='service_worker'&&t.url.includes(extension.id)),'worker');worker=await cdp(target.webSocketDebuggerUrl);
    await worker.evaluate(`chrome.storage.local.set({pairing:${JSON.stringify({port:pairing.port,token:pairing.token})},browser:'brave'})`);
    const panel=await open(`chrome-extension://${extension.id}/panel.html#settings`);page=panel.client;
    const checkbox="[...document.querySelectorAll('.settings-section input[type=checkbox]')].find(i=>/Pause time tracking|Időmérés szüneteltetése/.test(i.parentElement.textContent))";
    const media="[...document.querySelectorAll('.settings-section input[type=checkbox]')].find(i=>/Count media playback|Médialejátszás számítson/.test(i.parentElement.textContent))";
    const minutes="document.querySelector('.settings-section input[type=number]')";
    await until(()=>page.evaluate(`!!(${checkbox})`),'idle settings');
    assert.equal(await page.evaluate(`${minutes}.disabled`),true);assert.equal(await page.evaluate(`${media}.disabled`),true);
    await page.evaluate(`${checkbox}.click()`);await until(()=>page.evaluate(`!${minutes}.disabled`),'enabled timeout');
    await page.evaluate(`${media}.click()`);
    await page.evaluate(`${minutes}.value='7';${minutes}.dispatchEvent(new Event('input',{bubbles:true}))`);
    await page.evaluate("document.querySelector('form.editor-form').requestSubmit()");
    await until(async()=>{const s=(await api('state')).result.settings;return s.pause_when_idle && s.idle_timeout_seconds===420 && s.media_prevents_idle;},'save completed');
    async function api(action,data={}){return page.evaluate(`(async()=>{const {api}=await import('./client.js');const live=await api('live');return api(${JSON.stringify(action)},${JSON.stringify(data)},live.revision);})()`);}
    let state=(await api('state')).result;assert.equal(state.settings.pause_when_idle,true);assert.equal(state.settings.idle_timeout_seconds,420);
    await worker.evaluate('sync()');await until(()=>worker.evaluate('continuity.model.value.snapshot?.idle_timeout_seconds===420'),'offline policy updated');assert.equal(await worker.evaluate('continuity.model.value.snapshot.media_prevents_idle'),true);
    for(const language of ['hu','en']){
      await until(()=>page.evaluate("!document.querySelector('.operation-feedback.busy')"),'idle editor');
      await api('settings.save',{language});await page.call('Page.reload');
      await until(()=>page.evaluate(`!!(${checkbox}) && document.documentElement.lang==='${language}'`),'language settings');
      assert.equal(await page.evaluate(`${minutes}.value`),'7');assert.equal(await page.evaluate(`${media}.checked`),true);
      for(const width of [1280,1000]){
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:700,deviceScaleFactor:1,mobile:false});
        await fs.writeFile(path.join(report,`settings-${language}-${width}.png`),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
        assert.ok(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'));
      }
    }
    await page.evaluate(`${checkbox}.click()`);assert.equal(await page.evaluate(`${minutes}.disabled`),true);
    await page.evaluate("document.querySelector('form.editor-form').requestSubmit()");
    await until(async()=>!(await api('state')).result.settings.pause_when_idle,'disabled save');
    state=(await api('state')).result;assert.equal(state.settings.pause_when_idle,false);assert.equal(state.settings.idle_timeout_seconds,420);
    assert.equal(state.settings.media_prevents_idle,true);
    await until(()=>page.evaluate("!document.querySelector('.operation-feedback.busy')"),'settings saved');
    await page.evaluate("location.hash='budgets'");
    const edit="[...document.querySelectorAll('.budget-row')].find(r=>r.textContent.includes('Webes próba'))?.querySelectorAll('button')";
    await until(()=>page.evaluate(`!!(${edit})`),'budget list');
    await page.evaluate(`[...${edit}].find(b=>b.textContent==='Edit').click()`);
    const repeat="[...document.querySelectorAll('label.field')].find(n=>/Do not ask again for|Ne kérdezze újra/.test(n.textContent)).querySelector('input')";
    await until(()=>page.evaluate(`!!(${repeat})`),'repeat delay editor');
    await page.evaluate(`${repeat}.value='15';${repeat}.dispatchEvent(new Event('input',{bubbles:true}))`);
    await page.evaluate("document.querySelector('form.editor-form').requestSubmit()");
    await until(async()=>((await api('state')).result.budgets.find(b=>b.key==='web-choices').plan.steps[0].session_choice.remember_minutes===15),'repeat delay saved');
    const budget=(await api('state')).result.budgets.find(b=>b.key==='web-choices'),action=budget.plan.steps[0];
    const visit=n=>({browser:'brave',domain:'choice.example.com',visit:n.toString(16).padStart(32,'0')});
    assert.ok((await api('choices.status',visit(1))).result.choice);
    assert.equal((await api('choices.choose',{...visit(1),budget:budget.key,step:action.id,choice:action.session_choice.options[0].id})).result.accepted,true);
    assert.equal((await api('choices.status',visit(2))).result.choice,null);
    assert.ok((await api('choices.status',{...visit(3),domain:'second.example.com'})).result.choice);
    for(const language of ['hu','en']){
      await until(()=>page.evaluate("!document.querySelector('.operation-feedback.busy')"),'saved budget');
      await api('settings.save',{language});await page.call('Page.reload');
      await until(()=>page.evaluate(`!!(${edit}) && document.documentElement.lang==='${language}'`),'budget language');
      await page.evaluate(`[...${edit}].find(b=>/^(Edit|Szerkesztés)$/.test(b.textContent)).click()`);
      await until(()=>page.evaluate(`!!(${repeat})`),'translated repeat setting');
      assert.equal(await page.evaluate(`${repeat}.value`),'15');
      for(const width of [1280,1000]){
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:700,deviceScaleFactor:1,mobile:false});
        await page.evaluate(`${repeat}.scrollIntoView({block:'center'})`);
        await fs.writeFile(path.join(report,`choices-${language}-${width}.png`),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
        assert.ok(await page.evaluate('document.documentElement.scrollWidth<=innerWidth'));
      }
    }
    console.log(JSON.stringify({default_continues:true,save_seven_minutes:true,reload_preserved:true,offline_policy_updated:true,disable_preserves_timeout:true,hu_en_layouts:true}));
  }catch(error){console.error(await page?.evaluate('({url:location.href,language:document.documentElement.lang,text:document.body.innerText})').catch(()=>null));throw error;}
  finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-idle-settings-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
