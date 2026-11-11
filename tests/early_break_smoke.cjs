// Real extension popup, authenticated desktop command and durable break state.
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{setTimeout:delay}=require('node:timers/promises'),assert=require('node:assert/strict');
async function until(fn,label,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){const v=await fn().catch(()=>null);if(v)return v;await delay(100);}throw Error('Timed out: '+label);}
async function cdp(url){const socket=new WebSocket(url),pending=new Map();let id=0;
  await new Promise((ok,no)=>{socket.onopen=ok;socket.onerror=no;});
  socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.no(Error(JSON.stringify(r.error))):p.ok(r.result);};
  const api={close:()=>socket.close(),call(method,params={}){return new Promise((ok,no)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);no(Error(method+' timeout'));},10000);pending.set(n,{ok,no,timer});socket.send(JSON.stringify({id:n,method,params}));});},
    async evaluate(expression){const r=await api.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}};return api;}
(async()=>{
    const [browserPath,pythonPath,reportArg]=process.argv.slice(2),report=path.resolve(reportArg||'test-reports/early-break/browser');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json','finish-break'])await fs.rm(path.join(report,name),{force:true});
  const fixture=spawn(pythonPath,['tests/early_break_fixture.py',report],{windowsHide:true,stdio:['ignore','ignore','inherit']});
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-early-break-'));let browser,connection,worker,page;
  try{
    const pairing=await until(async()=>JSON.parse(await fs.readFile(path.join(report,'fixture.json'),'utf8')),'desktop');
    browser=spawn(browserPath,[`--user-data-dir=${temp}`,'--headless=new','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--no-first-run','--no-default-browser-check','--disable-background-networking','about:blank'],{windowsHide:true,stdio:'ignore'});
    const ports=await until(async()=>String(await fs.readFile(path.join(temp,'DevToolsActivePort'))).trim().split('\n'),'browser');
    connection=await cdp(`ws://127.0.0.1:${ports[0]}${ports[1]}`);const targets=()=>fetch(`http://127.0.0.1:${ports[0]}/json/list`).then(r=>r.json());
    async function open(url){const c=await connection.call('Target.createTarget',{url});const target=await until(async()=>(await targets()).find(t=>t.id===c.targetId),'target');return {id:c.targetId,client:await cdp(target.webSocketDebuggerUrl)};}
    const settings=await open('chrome://extensions/');await until(()=>settings.client.evaluate("typeof chrome.developerPrivate?.updateProfileConfiguration==='function'"),'developer mode');
    await settings.client.evaluate('(()=>{chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},()=>{});return true;})()');settings.client.close();await connection.call('Target.closeTarget',{targetId:settings.id});
    const extension=await connection.call('Extensions.loadUnpacked',{path:path.resolve('gametime/browser_extension')});
    const target=await until(async()=>(await targets()).find(t=>t.type==='service_worker'&&t.url.includes(extension.id)),'worker');worker=await cdp(target.webSocketDebuggerUrl);
    await worker.evaluate(`chrome.storage.local.set({pairing:${JSON.stringify({port:pairing.port,token:pairing.token})},browser:'brave'})`);
    const popup=await open(`chrome-extension://${extension.id}/popup.html`);page=popup.client;
    await page.call('Emulation.setDeviceMetricsOverride',{width:380,height:720,deviceScaleFactor:1,mobile:false});
    const row="document.querySelector('[data-timer-key=youtube]')";
    await until(()=>page.evaluate(`${row}?.textContent.includes('03:00')`),'three unused minutes');
    async function shot(name){await fs.writeFile(path.join(report,name+'.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));}
    async function api(action,data={}){return page.evaluate(`(async()=>{const {api}=await import('./client.js');const live=await api('live');return api(${JSON.stringify(action)},${JSON.stringify(data)},live.revision);})()`);}
    await until(()=>page.evaluate(`${row}?.querySelector('button')?.textContent==='Szünet most'`),'Hungarian button');await shot('popup-hu');
    await api('settings.save',{language:'en'});
    await until(()=>page.evaluate(`${row}?.querySelector('button')?.textContent==='Break now'`),'English button');await shot('popup-en');
    await page.evaluate(`${row}.querySelector('button').click()`);
    await until(()=>page.evaluate(`${row}?.textContent.includes('Break remaining')`),'full break started');
    let response=await api('live'),event=response.result.timers.find(t=>t.key==='youtube');
    assert.equal(event.event,'break_active');assert.ok(event.seconds>295&&event.seconds<=300);assert.equal(event.break_step,'');assert.equal(event.total,2880);
    assert.ok(await page.evaluate(`${row}.querySelector('button').hidden`));
    await worker.evaluate('sync()');assert.ok(await worker.evaluate("policy.restrictions.some(r=>r.key==='youtube'&&r.is_break&&r.kind==='cover')"));
    await fs.writeFile(path.join(report,'finish-break'),'advance 300 seconds');
    await until(()=>page.evaluate(`${row}?.textContent.includes('15:00')`),'fresh fifteen minutes');
    response=await api('live');event=response.result.timers.find(t=>t.key==='youtube');assert.equal(event.seconds,900);assert.equal(event.total,2880);assert.equal(event.break_step,'pause');
    await page.call('Page.navigate',{url:`chrome-extension://${extension.id}/panel.html#budgets`});
    await page.call('Emulation.setDeviceMetricsOverride',{width:1000,height:780,deviceScaleFactor:1,mobile:false});
    await until(()=>page.evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent==='Edit')"),'budget editor link');
    const budgetButton="[...document.querySelectorAll('.budget-row button')].find(b=>b.textContent==='Break now'&&b.closest('.budget-row').textContent.includes('YouTube'))";
    assert.ok(await page.evaluate(`${budgetButton}&&!${budgetButton}.hidden&&!${budgetButton}.disabled`));await shot('budget-list-en');
    await page.evaluate(`${budgetButton}.click()`);
    await until(()=>page.evaluate(`${budgetButton}?.disabled`),'budget list button starts break');
    response=await api('live');assert.equal(response.result.timers.find(t=>t.key==='youtube').event,'break_active');
    await page.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==='Edit'&&b.closest('.budget-row').textContent.includes('YouTube')).click()");
    const checkbox="[...document.querySelectorAll('label.check')].find(n=>n.textContent.includes('Break now'))";
    await until(()=>page.evaluate(`${checkbox}?.querySelector('input').checked`),'saved opt-in in browser editor');
    await page.evaluate(`${checkbox}.scrollIntoView({block:'center'})`);await shot('editor-en');
    await page.evaluate(`${checkbox}.querySelector('input').click()`);
    assert.equal(await page.evaluate(`${checkbox}.querySelector('input').checked`),false);
    await page.evaluate("[...document.querySelectorAll('label.field')].find(n=>n.firstChild.textContent==='When').querySelector('select').value='clock';[...document.querySelectorAll('label.field')].find(n=>n.firstChild.textContent==='When').querySelector('select').dispatchEvent(new Event('input',{bubbles:true}))");
    assert.equal(await page.evaluate(`!!(${checkbox})`),false);
    console.log(JSON.stringify({real_popup_button:true,hu_en:true,full_five_minute_break:true,website_cover_policy:true,fresh_fifteen_minutes:true,daily_budget_preserved:true,editor_opt_in:true,clock_has_no_early_option:true,budget_list_action:true}));
  }catch(error){if(page){await fs.writeFile(path.join(report,'failure.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64')).catch(()=>{});console.error(await page.evaluate('document.body.innerText').catch(()=>''));}throw error;}
  finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-early-break-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
