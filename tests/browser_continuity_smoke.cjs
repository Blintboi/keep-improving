// Real Brave, a restartable desktop, and disposable profiles. No user's data.
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {spawn}=require('node:child_process'),{setTimeout:delay}=require('node:timers/promises');
const assert=require('node:assert/strict');
async function until(fn,label,timeout=30000) {const end=Date.now()+timeout;while(Date.now()<end){const result=await fn().catch(()=>null);if(result)return result;await delay(150);}throw Error('Timed out: '+label);}
(async()=>{
  const [browserPath,pythonPath]=process.argv.slice(2),report=path.resolve(process.argv[4] || 'test-reports/browser-continuity-2400/browser');
  await fs.mkdir(report,{recursive:true});
  // A new run uses a new subfolder so failed evidence is retained.
  const run=await fs.mkdtemp(path.join(report,'run-')),root=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-continuity-'));
  let fixture,browser,connection,worker,page;
  const startFixture=()=>{fixture=spawn(pythonPath,['tests/browser_continuity_fixture.py',run],{windowsHide:true,stdio:['ignore','pipe','pipe']});
    fixture.stdout.on('data',b=>fs.appendFile(path.join(run,'desktop.log'),b));fixture.stderr.on('data',b=>fs.appendFile(path.join(run,'desktop.log'),b));};
  const stopFixture=async()=>{await fs.writeFile(path.join(run,'stop-fixture'),'stop');await until(()=>Promise.resolve(fixture.exitCode!==null),'desktop stopped',15000);await fs.rm(path.join(run,'stop-fixture'));};
  const status=async()=>JSON.parse(await fs.readFile(path.join(run,'status.json'),'utf8'));
  try {
    startFixture();const pairing=await until(async()=>JSON.parse(await fs.readFile(path.join(run,'fixture.json'),'utf8')),'desktop fixture');
    const profile=path.join(root,'profile');
    browser=spawn(browserPath,[`--user-data-dir=${profile}`,'--headless=new','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--no-first-run','--no-default-browser-check','--disable-background-networking','about:blank'],{windowsHide:true,stdio:'ignore'});
    const lines=await until(async()=>String(await fs.readFile(path.join(profile,'DevToolsActivePort'))).trim().split('\n'),'browser');
    connection=await cdp(`ws://127.0.0.1:${lines[0]}${lines[1]}`);
    const targets=()=>fetch(`http://127.0.0.1:${lines[0]}/json/list`).then(r=>r.json());
    const targetPage=async id=>cdp((await until(async()=>(await targets()).find(t=>t.id===id),'target')).webSocketDebuggerUrl);
    const settings=await connection.call('Target.createTarget',{url:'chrome://extensions/'}),settingsPage=await targetPage(settings.targetId);
    await until(()=>settingsPage.evaluate("typeof chrome.developerPrivate?.updateProfileConfiguration==='function'"),'developer settings');
    await settingsPage.evaluate('new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))');
    settingsPage.close();await connection.call('Target.closeTarget',{targetId:settings.targetId});
    const loaded=await connection.call('Extensions.loadUnpacked',{path:path.resolve('gametime/browser_extension')});
    const getWorker=async()=>cdp((await until(async()=>(await targets()).find(t=>t.type==='service_worker'&&t.url.startsWith(`chrome-extension://${loaded.id}/`)),'worker')).webSocketDebuggerUrl);
    worker=await getWorker();await until(()=>worker.evaluate("typeof continuity!=='undefined'"),'worker ready');
    await worker.evaluate(`chrome.storage.local.set({pairing:${JSON.stringify({port:pairing.port,token:pairing.token})},browser:'brave'})`);
    await until(async()=>{await worker.evaluate('sync()');return worker.evaluate('!!continuity.model?.value.snapshot?.path');},'initial snapshot');
    const web=await connection.call('Target.createTarget',{url:'about:blank'});page=await targetPage(web.targetId);
    page.on('Fetch.requestPaused',params=>page.call('Fetch.fulfillRequest',{requestId:params.requestId,responseCode:200,responseHeaders:[{name:'Content-Type',value:'text/html'}],body:Buffer.from('<!doctype html><title>Continuity fixture</title><h1>Browser activity fixture</h1>').toString('base64')}).catch(()=>{}));
    await page.call('Fetch.enable',{patterns:[{urlPattern:'https://example.com/*',requestStage:'Request'}]});
    await page.call('Page.navigate',{url:'https://example.com/continuity'});await page.call('Page.bringToFront');
    await delay(1200);await worker.evaluate('sync()');
    const online=await status();
    await fs.writeFile(path.join(run,'scenario.json'),JSON.stringify({remaining:7,budget:online.wellbeing+6}));
    await until(async()=>(await status()).focus.running,'started focus');await fs.rm(path.join(run,'scenario.json'));
    await worker.evaluate('sync()');await until(()=>worker.evaluate('continuity.model.value.snapshot.focus.running'),'timer snapshot');
    const before=await status(),started=Date.now();await stopFixture();
    for(let i=0;i<5;i++){await delay(2000);await worker.evaluate('sync()');}
    const offline=await worker.evaluate('({connected:continuity.connected,value:continuity.model.value,policy})');
    assert.equal(offline.connected,false);assert.equal(offline.value.snapshot.focus.total,1);assert.equal(offline.value.snapshot.focus.running,false);
    assert.ok(offline.value.records.length>0);assert.equal(await page.evaluate('location.protocol'),'chrome-extension:','offline budget covers the real tab');
    const stream=offline.value.stream;
    await worker.evaluate('setTimeout(()=>chrome.runtime.reload(),50)');worker.close();await delay(500);worker=await getWorker();
    await until(()=>worker.evaluate('!!continuity.model?.value.snapshot'),'worker restored');
    assert.equal(await worker.evaluate('continuity.model.value.stream'),stream);
    assert.equal(await worker.evaluate('continuity.model.value.snapshot.focus.total'),1);
    const panel=await connection.call('Target.createTarget',{url:`chrome-extension://${loaded.id}/panel.html#focus`});page.close();page=await targetPage(panel.targetId);
    await page.call('Emulation.setDeviceMetricsOverride',{width:1280,height:850,deviceScaleFactor:1,mobile:false});
    await until(()=>page.evaluate("document.querySelector('#heading')?.textContent==='Browser mode' && !!document.querySelector('#offline-clock')"),'offline panel');
    await fs.writeFile(path.join(run,'offline-en.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    const click=async name=>page.evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(name)});if(!b)return false;b.click();return true;})()`);
    assert.ok(await click('Start focus'));await until(()=>worker.evaluate('continuity.model.value.snapshot.focus.running'),'offline start');
    await delay(1800);assert.ok(await click('Pause'));await until(()=>worker.evaluate('!continuity.model.value.snapshot.focus.running'),'offline pause');
    await worker.evaluate("continuity.model.value.snapshot.language='hu';continuity.save()");
    await page.call('Emulation.setDeviceMetricsOverride',{width:1000,height:700,deviceScaleFactor:1,mobile:false});
    await page.call('Page.reload');await until(()=>page.evaluate("document.querySelector('#heading')?.textContent==='Böngészős mód'"),'Hungarian offline panel');
    await fs.writeFile(path.join(run,'offline-hu.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    const pending=await worker.evaluate('JSON.parse(JSON.stringify(continuity.model.value.records))');
    await fs.writeFile(path.join(run,'pending.json'),JSON.stringify(pending,null,2));
    startFixture();await until(async()=>{await worker.evaluate('sync()');return worker.evaluate('continuity.connected && continuity.model.value.records.length===0');},'reconnected and acknowledged');
    const after=await until(async()=>{const value=await status();return value.focus.rounds===1 && !value.focus.running && value;},'imported desktop counters');
    const gained=(after.totals.site || 0)-(before.totals.site || 0),elapsed=(Date.now()-started)/1000;
    assert.ok(gained>2 && gained<elapsed+2,`offline website time ${gained} / ${elapsed}`);
    const replay=await fetch(`http://127.0.0.1:${pairing.port}/continuity`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+pairing.token},
      body:JSON.stringify({version:1,stream,browser:'brave',records:pending.slice(0,128)})}).then(r=>r.json());
    assert.equal(replay.ok,true);await delay(600);const final=await status();
    assert.equal(final.focus.rounds,1);assert.equal(final.totals.site,after.totals.site,'replay cannot add website time');
    const result={passed:true,worker_restart_preserved_journal:true,offline_budget_enforced:true,offline_focus_completed_once:true,offline_controls_preserved:true,
      replay_preserved_totals:true,offline_website_seconds:gained,elapsed_seconds:elapsed,profile:run};
    await fs.writeFile(path.join(run,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  } catch(error) {
    if(worker) console.log(await worker.evaluate('({busy,connected:continuity.connected,snapshot:!!continuity.model?.value.snapshot,error:continuity.error,records:continuity.model?.value.records.length})').catch(()=>null));
    if(page) {console.log(await page.evaluate('document.body.innerText').catch(()=>null));const shot=await page.call('Page.captureScreenshot',{format:'png'}).catch(()=>null);if(shot)await fs.writeFile(path.join(run,'failure.png'),Buffer.from(shot.data,'base64'));}
    console.log('Evidence: '+run);throw error;
  } finally {
    if(fixture && fixture.exitCode===null) await stopFixture().catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser && browser.exitCode===null){await delay(500);browser.kill();}
    if(path.resolve(root).startsWith(path.join(os.tmpdir(),'gtm-continuity-'))) await fs.rm(root,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});

async function cdp(url) {
  const socket=new WebSocket(url),requests=new Map(),listeners=new Map();let id=0;
  await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const reply=JSON.parse(event.data);if(reply.method){listeners.get(reply.method)?.(reply.params);return;}const item=requests.get(reply.id);if(!item)return;requests.delete(reply.id);clearTimeout(item.timer);reply.error?item.reject(Error(JSON.stringify(reply.error))):item.resolve(reply.result);};
  socket.onclose=()=>{for(const item of requests.values()){clearTimeout(item.timer);item.reject(Error('Target closed'));}requests.clear();};
  return {close:()=>socket.close(),on:(name,fn)=>listeners.set(name,fn),call(method,params={}){return new Promise((resolve,reject)=>{const request=++id,timer=setTimeout(()=>{requests.delete(request);reject(Error('CDP timeout: '+method));},15000);requests.set(request,{resolve,reject,timer});socket.send(JSON.stringify({id:request,method,params}));});},
    async evaluate(expression){const value=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error(JSON.stringify(value.exceptionDetails));return value.result.value;}};
}
