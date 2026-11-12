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
  const [browserPath,pythonPath]=process.argv.slice(2),report=path.resolve('test-reports/usability-2470/browser');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json'])await fs.rm(path.join(report,name),{force:true});
  const fixture=spawn(pythonPath,['tests/website_choices_fixture.py',report,'choice.example.com','reconnect'],{windowsHide:true,stdio:['ignore','ignore','inherit']});
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-usability-'));let browser,connection,worker,page;
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
    const panel=await open(`chrome-extension://${extension.id}/panel.html#budgets`);page=panel.client;
    await page.call('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
    await until(()=>page.evaluate("document.querySelector('.budget-row') && !document.querySelector('.operation-feedback.busy')"),'budget list');
    const click=text=>page.evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!b)throw Error('Button unavailable: '+${JSON.stringify(text)});b.click();return true;})()`);
    await page.evaluate("(()=>{const row=[...document.querySelectorAll('.budget-row')].find(r=>r.textContent.includes('Webes próba'));const b=[...row.querySelectorAll('button')].find(b=>b.textContent==='Szerkesztés');b.click();})()");await until(()=>page.evaluate("!!document.querySelector('form.editor-form')"),'editor');
    const help=await page.evaluate("({total:document.querySelectorAll('details.help-note').length,expanded:document.querySelectorAll('details.help-note[open]').length})");assert.ok(help.total>=2);assert.equal(help.expanded,0);
    await page.evaluate("document.querySelector('details.help-note summary').click()");assert.equal(await page.evaluate("document.querySelector('details.help-note').open"),true);
    await page.evaluate("document.querySelector('details.help-note summary').click()");
    await fs.writeFile(path.join(report,'editor-hu.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    await page.evaluate("globalThis.realFetch=fetch;globalThis.saves=0;globalThis.failSave=false;globalThis.fetch=async(url,options)=>{if(String(url).endsWith('/control') && JSON.parse(options?.body || '{}').action==='budget.save'){globalThis.saves++;await new Promise(ok=>setTimeout(ok,800));if(failSave)throw Error('Injected failure');}return realFetch(url,options);}");
    await click('Módosítások mentése');
    await until(()=>page.evaluate("document.querySelector('.operation-feedback.busy')?.textContent==='Mentés…'"),'saving feedback');
    assert.equal(await page.evaluate("document.querySelector('.editor-form .footer button:last-child').disabled"),true);
    await page.evaluate("document.querySelector('form.editor-form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))");
    await fs.writeFile(path.join(report,'saving-hu.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    await until(()=>page.evaluate("document.querySelector('.operation-feedback')?.textContent==='Mentve.'"),'save result');assert.equal(await page.evaluate('saves'),1);
    await page.evaluate("(()=>{const row=[...document.querySelectorAll('.budget-row')].find(r=>r.textContent.includes('Webes próba'));const b=[...row.querySelectorAll('button')].find(b=>b.textContent==='Szerkesztés');b.click();})()");await until(()=>page.evaluate("!!document.querySelector('form.editor-form')"),'editor returns');
    await page.evaluate("globalThis.failSave=true");await click('Módosítások mentése');
    await until(()=>page.evaluate("!document.querySelector('.operation-feedback.busy') && !!document.querySelector('.editor-form .error')?.textContent"),'error visible');
    assert.equal(await page.evaluate("document.querySelector('.editor-form .footer button:last-child').disabled"),false);
    assert.ok(await page.evaluate("document.querySelector('form.editor-form')!=null"));
    await page.evaluate("globalThis.failSave=false");
    await page.evaluate("document.querySelector('form.editor-form').dispatchEvent(new KeyboardEvent('keydown',{key:'s',ctrlKey:true,bubbles:true,cancelable:true}))");
    await until(()=>page.evaluate("document.querySelector('.operation-feedback')?.textContent==='Mentve.'"),'keyboard save');assert.equal(await page.evaluate('saves'),3);
    await page.evaluate("(()=>{const picker=document.querySelector('#language');picker.value='en';picker.dispatchEvent(new Event('change',{bubbles:true}));})()");
    await until(()=>page.evaluate("document.documentElement.lang==='en' && !document.querySelector('#language').disabled && !document.querySelector('.operation-feedback.busy')"),'language save');
    await page.call('Page.reload');await until(()=>page.evaluate("document.querySelector('.budget-row') && !document.querySelector('.operation-feedback.busy') && document.documentElement.lang==='en'"),'English list');
    await page.evaluate("(()=>{const row=[...document.querySelectorAll('.budget-row')].find(r=>r.textContent.includes('Webes próba'));[...row.querySelectorAll('button')].find(b=>b.textContent==='Edit').click();})()");await until(()=>page.evaluate("!!document.querySelector('form.editor-form')"),'English editor');
    await page.call('Emulation.setDeviceMetricsOverride',{width:1000,height:700,deviceScaleFactor:1,mobile:false});
    await fs.writeFile(path.join(report,'editor-en-narrow.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.ok(await page.evaluate("[...document.querySelectorAll('button')].some(b=>b.textContent==='Break') && [...document.querySelectorAll('button')].some(b=>b.textContent==='Restriction')"));
    await page.evaluate("[...document.querySelectorAll('h2')].find(h=>h.textContent==='Actions').scrollIntoView({block:'start'})");
    await fs.writeFile(path.join(report,'actions-en-narrow.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.equal(await page.evaluate("document.documentElement.scrollWidth<=innerWidth"),true);
    await click('Break');
    assert.ok(await page.evaluate("[...document.querySelectorAll('select')].some(s=>s.value==='break')"));
    console.log(JSON.stringify({immediate_feedback:true,duplicate_save_prevented:true,success_acknowledged:true,error_retry_preserves_editor:true,ctrl_s_saves:true,help_closed_by_default:true,help_opens_in_place:true,hu_en_layouts:true,direct_break_action:true}));
  }finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-usability-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
