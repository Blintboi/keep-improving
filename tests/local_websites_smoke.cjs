// Real Brave extension, two disposable local sites and a disposable desktop profile.
const fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os'),http=require('node:http');
const {spawn}=require('node:child_process'),{setTimeout:delay}=require('node:timers/promises'),assert=require('node:assert/strict');
async function until(fn,label,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){const v=await fn().catch(()=>null);if(v)return v;await delay(100);}throw Error('Timed out: '+label);}
async function cdp(url){const socket=new WebSocket(url),pending=new Map();let id=0;
  await new Promise((ok,no)=>{socket.onopen=ok;socket.onerror=no;});
  socket.onmessage=e=>{const r=JSON.parse(e.data),p=pending.get(r.id);if(!p)return;pending.delete(r.id);clearTimeout(p.timer);r.error?p.no(Error(JSON.stringify(r.error))):p.ok(r.result);};
  const api={close:()=>socket.close(),call(method,params={}){return new Promise((ok,no)=>{const n=++id,timer=setTimeout(()=>{pending.delete(n);no(Error(method+' timeout'));},10000);pending.set(n,{ok,no,timer});socket.send(JSON.stringify({id:n,method,params}));});},
    async evaluate(expression){const r=await api.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}};return api;}
(async()=>{
  const [browserPath,pythonPath]=process.argv.slice(2),report=path.resolve('test-reports/local-websites/browser');await fs.mkdir(report,{recursive:true});
  for(const name of ['stop-fixture','fixture.json'])await fs.rm(path.join(report,name),{force:true});
  async function site(){const server=http.createServer((req,res)=>{res.setHeader('content-type','text/html; charset=utf-8');res.end('<!doctype html><title>Local statistics fixture</title><input id="draft" value="unsaved"><p>Local statistics fixture</p>');});await new Promise(ok=>server.listen(0,ok));return server;}
  const server=await site(),otherServer=await site(),host='127.0.0.1:'+server.address().port;
  const fixture=spawn(pythonPath,['tests/website_choices_fixture.py',report,'http://'+host+'/'],{windowsHide:true,stdio:['ignore','ignore','inherit']});
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'gtm-local-websites-'));let browser,connection,worker,page,panel,other;
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
    const website=await open(`http://${host}/private?secret=not-recorded`);page=website.client;
    await until(()=>page.evaluate("document.querySelector('#draft')!=null"),'site');await worker.evaluate('sync()');
    const visible=()=>page.evaluate("!!document.querySelector('#keep-improving-opening-choice')");await until(visible,'local opening choice');
    await fs.writeFile(path.join(report,'choice-hu.png'),Buffer.from((await page.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.equal(await worker.evaluate('websiteChoices.pending.host'),host);
    const {root}=await page.call('DOM.getDocument',{depth:-1,pierce:true});let button;
    function walk(n){if(!button&&n.nodeName==='BUTTON')button=n;for(const c of [...n.children||[],...n.shadowRoots||[]])walk(c);}walk(root);assert.ok(button);
    const {object}=await page.call('DOM.resolveNode',{nodeId:button.nodeId});await page.call('Runtime.callFunctionOn',{objectId:object.objectId,functionDeclaration:'function(){this.click();}'});await until(async()=>!await visible(),'choice accepted');
    const before=await page.evaluate('({url:location.href,origin:performance.timeOrigin,draft:document.querySelector("#draft").value})');
    await until(()=>worker.evaluate('!busy'),'idle worker');
    await worker.evaluate("globalThis.originalFetch=fetch;globalThis.fetch=(url,...args)=>String(url).endsWith('/activity')?Promise.reject(Error('Injected outage')):originalFetch(url,...args);sync()");
    await until(visible,'local in-page reconnect gate');
    assert.deepEqual(await page.evaluate('({url:location.href,origin:performance.timeOrigin,draft:document.querySelector("#draft")?.value})'),before);
    await worker.evaluate('globalThis.fetch=originalFetch;sync()');await until(async()=>!await visible(),'local accepted visit resumes');
    assert.deepEqual(await page.evaluate('({url:location.href,origin:performance.timeOrigin,draft:document.querySelector("#draft")?.value})'),before);
    const opened=await open(`chrome-extension://${extension.id}/panel.html#budgets`);panel=opened.client;
    await until(()=>panel.evaluate("document.querySelector('.budget-row')!=null"),'budgets');
    await panel.evaluate(`(async()=>{const {api}=await import('./client.js');const state=await api('state');const b=state.result.budgets.find(b=>b.key==='web-choices');b.seconds=0;b.usage=true;b.plan=null;await api('budget.save',b,state.revision);})()`);
    await worker.evaluate('sync()');await until(()=>page.evaluate("location.protocol==='chrome-extension:'"),'local zero budget blocks');
    const rules=await worker.evaluate('chrome.declarativeNetRequest.getSessionRules()');assert.ok(rules.some(r=>r.condition.regexFilter?.includes(String(server.address().port))));
    const alias=await open(`http://localhost:${server.address().port}/alias`);await worker.evaluate('sync()');await until(()=>alias.client.evaluate("location.protocol==='chrome-extension:'"),'localhost alias blocked');alias.client.close();
    const ipv6=await open(`http://[::1]:${server.address().port}/alias`);await worker.evaluate('sync()');await until(()=>ipv6.client.evaluate("location.protocol==='chrome-extension:'"),'IPv6 alias blocked');ipv6.client.close();
    const second=await open(`http://127.0.0.1:${otherServer.address().port}/other`);other=second.client;await worker.evaluate('sync()');
    await until(()=>other.evaluate("!!document.querySelector('#draft')"),'other local service unaffected');
    assert.equal(await worker.evaluate('(async()=>trackedHost(await activeTab()))()'),'');
    await worker.evaluate("setPolicy({...policy,active:true,mode:'allowlist',block:[],allow:[]})");
    assert.equal(await worker.evaluate(`siteDecision('127.0.0.1:${pairing.port}',{...policy,active:true,mode:'allowlist',local_sites:[...policy.local_sites,'127.0.0.1:${pairing.port}']}).kind`),'');
    await panel.evaluate(`(async()=>{const {api}=await import('./client.js');const live=await api('live');return api('budget.delete',{key:'web-choices'},live.revision);})()`);
    await worker.evaluate('sync()');await until(()=>page.evaluate("document.querySelector('#draft')!=null"),'original local page restored');
    assert.equal(await page.evaluate('location.href'),`http://${host}/private?secret=not-recorded`);
    console.log(JSON.stringify({local_reconnect_without_reload:true,local_member_saved:true,in_page_choice:true,zero_budget_blocks:true,localhost_alias:true,ipv6_alias:true,real_dnr_rules:true,other_port_unaffected:true,unconfigured_port_not_tracked:true,bridge_excluded:true,original_url_restored:true}));
  }catch(error){console.error(await worker?.evaluate('({policy,pending:websiteChoices.pending})').catch(()=>null));throw error;}
  finally{
    await fs.writeFile(path.join(report,'stop-fixture'),'stop');await until(async()=>fixture.exitCode!==null,'fixture shutdown',10000).catch(()=>fixture.kill());
    page?.close();panel?.close();other?.close();worker?.close();if(connection){await connection.call('Browser.close').catch(()=>{});connection.close();}
    if(browser?.exitCode===null){await delay(500);browser.kill();}server.close();otherServer.close();
    if(path.resolve(temp).startsWith(path.join(os.tmpdir(),'gtm-local-websites-')))await fs.rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:500});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
