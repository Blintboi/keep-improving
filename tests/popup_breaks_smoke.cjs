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
    const [browserPath,pythonPath,reportArg]=process.argv.slice(2),report=path.resolve(reportArg||'test-reports/popup-breaks-2481/browser');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json','finish-break'])await fs.rm(path.join(report,name),{force:true});
  const fixture=spawn(pythonPath,['tests/early_break_fixture.py',report,'no-timer'],{windowsHide:true,stdio:['ignore','ignore','inherit']});
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
    const quick="document.querySelector('[data-break-key=youtube]')";
    const button=quick+".querySelector('button')";
    async function shot(name){await fs.writeFile(path.join(report,name+'.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));}
    async function api(action,data={}){return page.evaluate(`(async()=>{const {api}=await import('./client.js');const live=await api('live');return api(${JSON.stringify(action)},${JSON.stringify(data)},live.revision);})()`);}
    await until(()=>page.evaluate(`${quick}?.querySelector('button')?.textContent==='Szünet most'`),'break without active timer');
    assert.equal((await api('live')).result.timers.length,0);
    assert.equal(await page.evaluate('document.querySelector("#timers").children.length'),0);
    const checks={no_active_timer_required:true};
    for(const language of ['hu','en']) {
      if(language==='en')await api('settings.save',{language:'en'});
      await until(()=>page.evaluate(`${button}.textContent===${JSON.stringify(language==='hu'?'Szünet most':'Break now')}`),'translated action');
      for(const width of [340,380]) {
        await page.call('Emulation.setDeviceMetricsOverride',{width,height:600,deviceScaleFactor:1,mobile:false});
        await page.evaluate(`document.body.style.width='${width}px'`);
        assert.ok(await page.evaluate(`${button}.getBoundingClientRect().bottom<250 && document.documentElement.scrollWidth<=innerWidth`));
        await shot(`quick-${language}-${width}`);
      }
    }
    await page.evaluate(`window.originalFetch=window.fetch;window.attempts=0;window.failBreak=true;window.fetch=async(url,options)=>{
      if(String(url).endsWith('/control') && JSON.parse(options.body).action==='break.start') {
        window.attempts++;await new Promise(ok=>setTimeout(ok,window.failBreak?4000:900));
        if(window.failBreak)return new Response(JSON.stringify({ok:false,error:'Fixture failure'}),{headers:{'Content-Type':'application/json'}});
      }
      return window.originalFetch(url,options);
    };`);
    await page.evaluate(`${button}.click();${button}.click()`);
    await until(()=>page.evaluate(`${button}.disabled && ${button}.textContent==='Starting…' && document.querySelector('.operation-feedback').classList.contains('busy')`),'immediate progress');
    await shot('starting');
    await delay(3200);assert.ok(await page.evaluate(`${button}.disabled && ${button}.textContent==='Starting…'`));
    await until(()=>page.evaluate(`!${button}.disabled && document.querySelector('.operation-feedback').textContent==='Fixture failure'`),'failure remains retryable');
    assert.equal(await page.evaluate('window.attempts'),1);
    await page.evaluate(`window.failBreak=false;${button}.click();${button}.click()`);
    await until(()=>page.evaluate(`${quick}?.textContent.includes('Break remaining') && !document.querySelector('.operation-feedback').classList.contains('busy')`),'full break started');
    assert.equal(await page.evaluate('window.attempts'),2);assert.ok(await page.evaluate(`${button}.disabled`));
    let response=await api('live');assert.ok(response.result.break_actions.youtube.remaining>295);assert.equal(response.result.break_actions.youtube.step,'');
    const saved=await api('state');assert.equal(saved.result.budgets.find(b=>b.key==='youtube').remaining,2880);
    await page.evaluate(`window.breakNode=${quick};window.beforeText=${quick}.textContent;window.reads=[];window.fetch=(url,options)=>{if(String(url).endsWith('/control'))window.reads.push(JSON.parse(options.body).action);return window.originalFetch(url,options);}`);
    await until(()=>page.evaluate(`${quick}.textContent!==window.beforeText`),'live break countdown without timer');
    assert.ok(await page.evaluate(`window.breakNode===${quick} && window.reads.every(action=>action==='live')`));
    await shot('running');
    await page.call('Page.reload');await until(()=>page.evaluate(`${quick}?.textContent.includes('Break remaining')`),'popup reopen preserves running break');
    await fs.writeFile(path.join(report,'finish-break'),'advance 300 seconds');
    await until(()=>page.evaluate(`${quick}?.querySelector('button')?.disabled===false`),'ready for next full interval');
    await worker.evaluate('sync()');assert.ok(!(await worker.evaluate("policy.restrictions.some(r=>r.key==='youtube'&&r.is_break)")));
    Object.assign(checks,{above_fold_hu_en_340_380:true,immediate_progress:true,failure_retry:true,duplicate_clicks_blocked:true,running_countdown_without_timer:true,stable_lightweight_refresh:true,full_five_minute_break:true,daily_budget_preserved:true,reopen_preserved:true});
    await fs.writeFile(path.join(report,'checks.json'),JSON.stringify(checks,null,2));console.log(JSON.stringify(checks));
  }catch(error){if(page){await fs.writeFile(path.join(report,'failure.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64')).catch(()=>{});console.error(await page.evaluate('document.body.innerText').catch(()=>''));}throw error;}
  finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-early-break-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
