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
  const [browserPath,pythonPath,reportArg]=process.argv.slice(2),report=path.resolve(reportArg||'test-reports/member-selection/web');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json'])await fs.rm(path.join(report,name),{force:true});
  const fixture=spawn(pythonPath,['tests/website_choices_fixture.py',report],{windowsHide:true,stdio:['ignore','ignore','inherit']});
  const pairing=await until(async()=>JSON.parse(await fs.readFile(path.join(report,'fixture.json'),'utf8')),'desktop');
  const server=http.createServer((req,res)=>{res.setHeader('content-type','text/html; charset=utf-8');res.end('<!doctype html><title>Choice fixture</title><style>body{margin:0;font:20px sans-serif}input{display:block;margin:20px}div{height:2400px;background:linear-gradient(#e8f0eb,#a9ccc0)}</style><input id="draft" value="unsaved"><div>Local website fixture</div>');});
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-website-choices-'));let browser,connection,worker,page;
  try{
    browser=spawn(browserPath,[`--user-data-dir=${temp}`,'--headless=new','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--no-first-run','--no-default-browser-check','--disable-background-networking','--no-proxy-server','--host-resolver-rules=MAP choice.example.com 127.0.0.1','about:blank'],{windowsHide:true,stdio:'ignore'});
    const ports=await until(async()=>String(await fs.readFile(path.join(temp,'DevToolsActivePort'))).trim().split('\n'),'browser');
    connection=await cdp(`ws://127.0.0.1:${ports[0]}${ports[1]}`);const targets=()=>fetch(`http://127.0.0.1:${ports[0]}/json/list`).then(r=>r.json());
    async function open(url){const c=await connection.call('Target.createTarget',{url});const target=await until(async()=>(await targets()).find(t=>t.id===c.targetId),'target');return {id:c.targetId,client:await cdp(target.webSocketDebuggerUrl)};}
    const settings=await open('chrome://extensions/');await until(()=>settings.client.evaluate("typeof chrome.developerPrivate?.updateProfileConfiguration==='function'"),'developer mode');
    await settings.client.evaluate('(()=>{chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},()=>{});return true;})()');settings.client.close();await connection.call('Target.closeTarget',{targetId:settings.id});
    const extension=await connection.call('Extensions.loadUnpacked',{path:path.resolve('gametime/browser_extension')});
    const target=await until(async()=>(await targets()).find(t=>t.type==='service_worker'&&t.url.includes(extension.id)),'worker');worker=await cdp(target.webSocketDebuggerUrl);
    const website=await open(`http://choice.example.com:${server.address().port}/sample`);page=website.client;
    await until(()=>page.evaluate("document.querySelector('#draft')!=null"),'page');
    await page.evaluate("document.querySelector('#draft').value='kept unsaved text';window.scrollTo(0,640)");
    const before=await page.evaluate("({url:location.href,w:innerWidth,h:innerHeight,scroll:scrollY,draft:document.querySelector('#draft').value})");
    await worker.evaluate(`chrome.storage.local.set({pairing:${JSON.stringify({port:pairing.port,token:pairing.token})},browser:'brave'})`);
    await worker.evaluate('sync()');
    const visible=()=>page.evaluate("!!document.querySelector('#keep-improving-opening-choice')");
    await until(visible,'website overlay');
    async function buttons(){const {root}=await page.call('DOM.getDocument',{depth:-1,pierce:true});const found=[];function walk(n){if(n.nodeName==='BUTTON')found.push(n);for(const c of [...n.children||[],...n.shadowRoots||[]])walk(c);}walk(root);return found;}
    async function click(index){const list=await buttons(),node=list[index];assert.ok(node);const {object}=await page.call('DOM.resolveNode',{nodeId:node.nodeId});await page.call('Runtime.callFunctionOn',{objectId:object.objectId,functionDeclaration:'function(){this.click();}'});await until(async()=>!await visible(),'choice accepted');}
    const during=await page.evaluate("({w:innerWidth,h:innerHeight,scroll:scrollY})");assert.deepEqual(during,{w:before.w,h:before.h,scroll:before.scroll});
    await page.evaluate("window.savedCover=document.querySelector('#keep-improving-opening-choice')");
    const checkCovered=async()=>{
      assert.ok(await page.evaluate("window.savedCover===document.querySelector('#keep-improving-opening-choice') && window.savedCover.isConnected"));
      const {root}=await page.call('DOM.getDocument',{depth:-1,pierce:true});
      function dialog(n){return n.nodeName==='DIALOG'?n:[...n.children||[],...n.shadowRoots||[]].map(dialog).find(Boolean);}
      assert.ok(dialog(root)?.attributes.includes('open'));
    };
    // A separate extension window leaves the original page visible behind it.
    const popupId=await worker.evaluate(`(async()=>{const w=await chrome.windows.create({url:chrome.runtime.getURL('popup.html'),type:'popup',width:420,height:560});return w.id;})()`);
    await worker.evaluate('sync()');await until(()=>worker.evaluate('!busy && websiteChoices.pending===null'),'extension popup focus');
    await checkCovered();
    for(const language of ['hu','en'])for(const width of [1000,390]) {
      await page.call('Emulation.setDeviceMetricsOverride',{width,height:700,deviceScaleFactor:1,mobile:false});
      const tabId=await worker.evaluate("[...websiteChoices.showing.keys()][0]");
      await worker.evaluate(`(async()=>{const t=await chrome.tabs.get(${tabId});const r=await websiteChoices.call((await chrome.storage.local.get('pairing')).pairing,'choices.status',{browser:'brave',domain:publicHost(t),visit:'${'a'.repeat(32)}'});await websiteChoices.send(t.id,{...r.choice,visit:'${'a'.repeat(32)}',language:'${language}'});})()`);
      await checkCovered();
      await fs.writeFile(path.join(report,`parked-${language}-${width}.png`),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    }
    await page.call('Emulation.clearDeviceMetricsOverride');
    await worker.evaluate(`chrome.windows.remove(${popupId})`);
    await connection.call('Target.activateTarget',{targetId:website.id});await worker.evaluate('sync()');await until(()=>worker.evaluate('!!websiteChoices.pending'),'returned visit');
    const parked=await open('about:blank');await worker.evaluate('sync()');
    await until(()=>worker.evaluate('!busy && websiteChoices.pending===null'),'unrelated tab');await checkCovered();
    parked.client.close();await connection.call('Target.closeTarget',{targetId:parked.id});
    await connection.call('Target.activateTarget',{targetId:website.id});await worker.evaluate('sync()');await until(()=>worker.evaluate('!!websiteChoices.pending'),'returned from unrelated tab');
    await click(1);
    assert.deepEqual(await page.evaluate("({url:location.href,w:innerWidth,h:innerHeight,scroll:scrollY,draft:document.querySelector('#draft').value})"),before);
    const other=await open('about:blank');
    async function revisit(){await connection.call('Target.activateTarget',{targetId:other.id});await worker.evaluate('sync()');await until(()=>worker.evaluate('websiteChoices.visit===null'),'leave visit');await connection.call('Target.activateTarget',{targetId:website.id});await worker.evaluate('sync()');await until(visible,'next visit');}
    await revisit();await click(1);await revisit();
    const final=await buttons();assert.ok(final[1].attributes.includes('disabled'));assert.ok(!final[0].attributes.includes('disabled'));
    await fs.writeFile(path.join(report,'overlay-hu.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    await worker.evaluate("websiteChoices.send(websiteChoices.pending.tabId,{...websiteChoices.pending.value,language:'en'})");
    await fs.writeFile(path.join(report,'overlay-en.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    await click(0);
    assert.deepEqual(await page.evaluate("({url:location.href,w:innerWidth,h:innerHeight,scroll:scrollY,draft:document.querySelector('#draft').value})"),before);
    other.client.close();console.log(JSON.stringify({extension_window_retains_cover:true,unrelated_tab_retains_cover:true,same_dialog_until_release:true,in_page_overlay:true,viewport_preserved:true,scroll_preserved:true,unsaved_form_preserved:true,no_navigation:true,two_allowed_visits:true,exhausted_disabled:true,unlimited_available:true,hu_en_screenshots:true}));
  }catch(error){if(page){await fs.writeFile(path.join(report,'failure.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64')).catch(()=>{});console.log(await worker?.evaluate('({policy,pending:websiteChoices.pending,visit:websiteChoices.visit})').catch(()=>null));}throw error;}
  finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}server.close();
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-website-choices-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
