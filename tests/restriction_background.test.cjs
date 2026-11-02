const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const {setTimeout:delay}=require('node:timers/promises');
const policySource=fs.readFileSync('gametime/browser_extension/policy.js','utf8');
const source=fs.readFileSync('gametime/browser_extension/background.js','utf8');
const copy=value=>JSON.parse(JSON.stringify(value));
const event=()=>({listeners:[],addListener(fn){this.listeners.push(fn);}});

async function fixture(options={}) {
  const storage=copy(options.session || {}); const local=copy(options.local || {}); const tabs=new Map(options.tabs || [[1,{id:1,url:'https://example.com/watch?id=private',active:true,windowId:1,incognito:false}],
    [2,{id:2,url:'https://other.com/',active:false,windowId:1,incognito:false}]]);
  const state={policy:{active:false,tracking:true,allow:[],block:[],mode:'blocklist',remaining:0,lease_seconds:30,
    language:'hu',restriction_version:1,extension_version:'2.39.23',restrictions:[{key:'budget',name:'Fixture',domains:['example.com'],all:false,
      kind:'cover',minutes:3,grant:null}]},rules:[],removed:[],fetches:[]};
  if (options.policy) state.policy=copy(options.policy);
  const chrome={storage:{session:{async get(key){return {[key]:storage[key]};},async set(data){Object.assign(storage,copy(data));}},
    local:{async get(){return {pairing:{port:12345,token:'fixture'},browser:'brave',...local};},async set(data){Object.assign(local,copy(data));}},onChanged:event()},
    windows:{async getLastFocused(){return {id:1,focused:true};},onFocusChanged:event()},
    tabs:{async query(query){return [...tabs.values()].filter(t=>!query.active||t.active).map(copy);},
      async get(id){if(options.race && id===1 && tabs.get(id)?.url.startsWith('https://example.com')) tabs.get(id).url='https://other.com/changed';
        if(!tabs.has(id)) throw Error('No tab'); return copy(tabs.get(id));},
      async update(id,data){Object.assign(tabs.get(id),data); return copy(tabs.get(id));},
      async remove(id){tabs.delete(id);state.removed.push(id);},onActivated:event(),onUpdated:event(),onRemoved:event()},
    declarativeNetRequest:{async getSessionRules(){return state.rules;},async updateSessionRules(data){state.rules=copy(data.addRules);}},
    action:{async setBadgeText(){},onClicked:event()},alarms:{create(){},onAlarm:event()},webNavigation:{onBeforeNavigate:event()},
    runtime:{id:'fixture',getURL:path=>'chrome-extension://fixture/'+path,getManifest:()=>({version:options.loadedVersion || '2.39.23'}),
      reload(){state.reloads=(state.reloads||0)+1;state.reloadedLocal=copy(local);},onMessage:event(),onStartup:event(),onInstalled:event(),openOptionsPage(){throw Error('No options page expected');}}};
  const context=vm.createContext({chrome,URL,crypto,AbortSignal,console,setTimeout:()=>1,clearTimeout:()=>{},
    async fetch(url,request){
      if (url==='chrome-extension://fixture/manifest.json') {state.manifestReads=(state.manifestReads||0)+1; return {ok:true,async json(){return {version:'2.39.23'};}};}
      state.fetches.push({url,body:JSON.parse(request.body)});
      if(options.offline) throw Error('Monitor offline');
      if(url.endsWith('/restriction-extension')) {
        const body=JSON.parse(request.body);
        if(options.reject) return {ok:true,async json(){return {ok:false};}};
        state.policy.restrictions[0].grant={subject:`site:${body.domain}:${body.token}`,until:Date.now()/1000+180};
        state.policy.restrictions[0].minutes=0;
        return {ok:true,async json(){return {ok:true};}};
      }
      return {ok:true,async json(){return copy(state.policy);}};
    }});
  context.importScripts=(...names)=>names.forEach(name=>vm.runInContext(
    options.legacy ? fs.readFileSync('tests/fixtures/browser_2_31_1/'+name,'utf8') :
      fs.readFileSync('gametime/browser_extension/'+name,'utf8'),context));
  vm.runInContext(options.legacy ? fs.readFileSync('tests/fixtures/browser_2_31_1/background.js','utf8') : source,context);
  for(let i=0;i<100&&vm.runInContext('busy',context);i++) await delay(1);
  assert.equal(vm.runInContext('busy',context),false);
  return {context,chrome,tabs,state,storage,local,async message(action){
    return await new Promise(resolve=>chrome.runtime.onMessage.listeners[0]({action},
      {id:'fixture',url:tabs.get(1).url,tab:tabs.get(1)},resolve));}};
}

test('redirect keeps the return URL in session storage, not in the URL or desktop message',async()=>{
  const f=await fixture();
  assert.match(f.tabs.get(1).url,/^chrome-extension:\/\/fixture\/blocked.html\?key=[a-z0-9]+$/);
  assert.equal(f.tabs.get(2).url,'https://other.com/');
  assert.equal(f.storage.blockedTabs['1'].url,'https://example.com/watch?id=private');
  assert.ok(!JSON.stringify(f.state.fetches).includes('watch?id'));
  const result=await f.message('status');assert.equal(result.minutes,3);
});

test('a restored cover reconnects by token after restart with a different tab ID',async()=>{
  const first=await fixture(); const url=first.tabs.get(1).url;
  const next=await fixture({local:first.local,tabs:[[91,{id:91,url,active:true,windowId:1,incognito:false}]]});
  assert.equal(next.tabs.get(91).url,url); assert.deepEqual(next.state.removed,[]);
  assert.equal(next.storage.blockedTabs['91'].url,'https://example.com/watch?id=private');
  assert.ok(!JSON.stringify(next.state.fetches).includes('watch?id'));
});

test('after daily renewal the original page returns automatically including inactive restored tabs',async()=>{
  const first=await fixture(); const url=first.tabs.get(1).url;
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',restrictions:[]};
  const next=await fixture({local:first.local,policy,tabs:[[91,{id:91,url,active:false,windowId:1,incognito:false}]]});
  assert.equal(next.tabs.get(91).url,'https://example.com/watch?id=private'); assert.deepEqual(next.state.removed,[]);
});

test('monitor restart or disconnect never strands a saved cover',async()=>{
  const first=await fixture(); const url=first.tabs.get(1).url;
  const next=await fixture({local:first.local,offline:true,tabs:[[91,{id:91,url,active:true,windowId:1,incognito:false}]]});
  assert.equal(next.tabs.get(91).url,'https://example.com/watch?id=private'); assert.deepEqual(next.state.rules,[]);
});

test('expired live covers return without requiring a button click',async()=>{
  const f=await fixture(); f.state.policy.restrictions=[];
  await vm.runInContext('sync()',f.context);
  assert.equal(f.tabs.get(1).url,'https://example.com/watch?id=private');
});

test('old session records migrate to durable storage before a cover is rewritten',async()=>{
  const token='a'.repeat(32),record={host:'example.com',url:'https://example.com/original',token};
  const f=await fixture({session:{blockedTabs:{1:record}},tabs:[[1,{id:1,url:'chrome-extension://fixture/blocked.html',active:true,incognito:false,windowId:1}]]});
  assert.equal(f.local.returnPages[token].url,record.url);
  assert.equal(f.tabs.get(1).url,'chrome-extension://fixture/blocked.html?key='+token);
});

test('reused tab IDs and unrelated navigation cannot recover someone else’s saved URL',async()=>{
  const first=await fixture(); const f=await fixture({local:first.local,session:first.storage,
    tabs:[[1,{id:1,url:'https://other.com/new',active:true,incognito:false,windowId:1}]]});
  assert.equal(f.tabs.get(1).url,'https://other.com/new');
  assert.equal(f.storage.blockedTabs['1'],undefined);
});

test('private tabs and invalid destinations never restore from durable records',async()=>{
  const first=await fixture(); const url=first.tabs.get(1).url;
  const f=await fixture({local:first.local,tabs:[[91,{id:91,url,active:true,incognito:true,windowId:1}]]});
  assert.equal(f.tabs.get(91).url,url); assert.equal(f.storage.blockedTabs['91'],undefined);
  const token='b'.repeat(32); const bad=await fixture({local:{returnPages:{[token]:{host:'example.com',url:'file:///C:/private',token}}},
    tabs:[[1,{id:1,url:'chrome-extension://fixture/blocked.html?key='+token,active:true,incognito:false,windowId:1}]]});
  assert.equal(bad.storage.blockedTabs['1'],undefined); assert.deepEqual(bad.state.removed,[]);
});

test('durable recovery writes do not schedule another network sync',async()=>{
  const f=await fixture(); const before=f.state.fetches.length;
  f.chrome.storage.onChanged.listeners[0]({returnPages:{newValue:f.local.returnPages}},'local');
  await delay(2); assert.equal(f.state.fetches.length,before);
});

test('the existing background connection reloads a completed desktop upgrade without opening a page',async()=>{
  const f=await fixture({loadedVersion:'2.39.22',local:{pairing:{port:12345,token:'fixture'},browser:'brave'}});
  assert.equal(f.state.reloads,1); assert.equal(f.state.reloadedLocal.pairing.token,'fixture');
  assert.ok(Object.values(f.state.reloadedLocal.returnPages).some(r=>r.url==='https://example.com/watch?id=private'));
  const restarted=await fixture({local:f.state.reloadedLocal,tabs:[...f.tabs]});
  assert.equal(restarted.state.reloads,undefined); assert.equal(restarted.state.manifestReads,undefined);
  assert.equal(restarted.storage.blockedTabs[1].url,'https://example.com/watch?id=private');
  await vm.runInContext('sync()',f.context); assert.equal(f.state.reloads,1);
});

test('normal background sync does not read the manifest or add a network request',async()=>{
  const f=await fixture(); await vm.runInContext('sync()',f.context);
  assert.equal(f.state.manifestReads,undefined); assert.equal(f.state.reloads,undefined);
  assert.ok(f.state.fetches.every(request=>request.url.endsWith('/activity')));
});

test('zero-budget compatibility blocks an already-open tab in the still-loaded old worker',async()=>{
  const policy={active:false,tracking:true,mode:'blocklist',allow:[],block:[],remaining:0,lease_seconds:30,
    restrictions:[{key:'zero',name:'Blocked Sites',domains:['example.com'],all:false,kind:'cover',minutes:0,grant:null,is_break:false}]};
  const f=await fixture({legacy:true,policy});
  assert.equal(f.tabs.get(1).url,'https://example.com/watch?id=private');
  Object.assign(f.state.policy,{active:true,block:['example.com'],remaining:30});
  await vm.runInContext('sync()',f.context);
  assert.equal(f.tabs.get(1).url,'chrome-extension://fixture/blocked.html');
  assert.equal(f.tabs.get(2).url,'https://other.com/');
  assert.deepEqual(f.state.rules[0].condition.requestDomains,['example.com']);
  assert.ok(vm.runInContext('leaseUntil',f.context)>Date.now());
  Object.assign(f.state.policy,{active:false,block:[],remaining:0,restrictions:[]});
  await vm.runInContext('sync()',f.context);
  assert.deepEqual(f.state.rules,[]);
});
test('one allowance returns to the same original tab and installs a scoped rule',async()=>{
  const f=await fixture();const response=await f.message('extend');
  assert.equal(response.ok,true);assert.equal(f.tabs.get(1).url,'https://example.com/watch?id=private');
  assert.deepEqual(f.state.rules.find(r=>r.action.type==='allow').condition.tabIds,[1]);
  assert.equal(f.state.fetches.filter(r=>r.url.endsWith('restriction-extension')).length,1);
});
test('denied allowance leaves the block page intact',async()=>{
  const f=await fixture({reject:true});const before=f.tabs.get(1).url;
  assert.equal((await f.message('extend')).ok,false);assert.equal(f.tabs.get(1).url,before);
});
test('a later close stage also closes an already redirected tab only',async()=>{
  const f=await fixture();f.state.policy.restrictions[0].kind='close';
  await vm.runInContext('sync()',f.context);
  assert.deepEqual(f.state.removed,[1]);assert.ok(f.tabs.has(2));
});
test('navigation race never redirects the replacement website',async()=>{
  const f=await fixture({race:true});assert.equal(f.tabs.get(1).url,'https://other.com/changed');
  assert.deepEqual(f.state.removed,[]);
});
test('DNR generic block page can recover a before-navigation record',async()=>{
  const f=await fixture();
  await f.chrome.webNavigation.onBeforeNavigate.listeners[0]({frameId:0,tabId:1,url:'https://example.com/new'});
  f.tabs.get(1).url='chrome-extension://fixture/blocked.html';
  assert.equal((await f.message('status')).minutes,3);
});
test('break redirects the existing tab without leaking its original URL or looping',async()=>{
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,restrictions:[{
    key:'budget',name:'Fixture',domains:['example.com'],all:false,kind:'redirect',minutes:0,grant:null,
    redirect_url:'https://example.com/rest?q=1',break_until:Date.now()/1000+300}]};
  const f=await fixture({policy});
  assert.equal(f.tabs.get(1).url,'https://example.com/rest?q=1');
  assert.equal(f.storage.blockedTabs['1'].url,'https://example.com/watch?id=private');
  const allow=f.state.rules.find(r=>r.action.type==='allow');
  assert.deepEqual(allow.condition.tabIds,[1]);
  await f.chrome.webNavigation.onBeforeNavigate.listeners[0]({frameId:0,tabId:1,url:'https://example.com/rest?q=1'});
  await vm.runInContext('sync()',f.context);
  assert.equal(f.storage.blockedTabs['1'].url,'https://example.com/watch?id=private');
  assert.equal(f.tabs.get(1).url,'https://example.com/rest?q=1');
  assert.equal(f.state.fetches.at(-1).body.redirect_budget,'budget');
  assert.ok(!JSON.stringify(f.state.fetches).includes('watch?id'));
  f.state.policy.restrictions=[]; await vm.runInContext('sync()',f.context);
  assert.equal(f.tabs.get(1).url,'https://example.com/rest?q=1');
  assert.ok(f.state.rules.every(r=>r.action.type!=='allow'));
  await vm.runInContext('sync()',f.context);
  assert.equal(f.state.fetches.at(-1).body.redirect_budget,'');
});
test('redirect cannot override an independent restriction on the destination',async()=>{
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,restrictions:[{
    key:'budget',name:'Fixture',domains:['example.com'],all:false,kind:'redirect',minutes:0,grant:null,
    redirect_url:'https://rest.example.org/',break_until:Date.now()/1000+300},{
    key:'other',name:'Other',domains:['rest.example.org'],all:false,kind:'cover',minutes:0,grant:null}]};
  const f=await fixture({policy});
  assert.match(f.tabs.get(1).url,/^chrome-extension:\/\/fixture\/blocked.html/);
  assert.ok(f.state.rules.every(r=>r.action.type!=='allow'));
});
test('a newly opened blocked page redirects to the configured break destination',async()=>{
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,restrictions:[{
    key:'budget',name:'Fixture',domains:['example.com'],all:false,kind:'redirect',minutes:0,grant:null,
    redirect_url:'https://rest.example.org/',break_until:Date.now()/1000+300}]};
  const f=await fixture({policy});
  f.tabs.set(3,{id:3,url:'https://other.com/',active:false,windowId:1,incognito:false});
  await f.chrome.webNavigation.onBeforeNavigate.listeners[0]({frameId:0,tabId:3,url:'https://example.com/new'});
  f.tabs.get(3).url='chrome-extension://fixture/blocked.html';
  await vm.runInContext('sync()',f.context);
  assert.equal(f.tabs.get(3).url,'https://rest.example.org/');
  assert.equal(f.storage.blockedTabs['3'].url,'https://example.com/new');
});
test('an empty break destination opens the existing tab as a browser new tab',async()=>{
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,restrictions:[{
    key:'budget',name:'Fixture',domains:['example.com'],all:false,kind:'redirect',minutes:0,grant:null,
    redirect_url:'',break_until:Date.now()/1000+300}]};
  const f=await fixture({policy});
  assert.equal(f.tabs.get(1).url,'about:newtab');
  assert.equal(f.storage.blockedTabs['1'].url,'https://example.com/watch?id=private');
  assert.ok(f.state.rules.every(rule=>rule.action.type!=='allow'));
  for (const actual of ['about:newtab','chrome://newtab/','chrome://new-tab-page/', 'brave://newtab/','edge://newtab/']) {
    f.tabs.get(1).url=actual;
    await vm.runInContext('sync()',f.context);
    assert.equal(f.tabs.get(1).url,actual);
    assert.equal(f.state.fetches.at(-1).body.redirect_budget,'budget');
  }
  f.state.policy.restrictions=[]; await vm.runInContext('sync()',f.context);
  await vm.runInContext('sync()',f.context);
  assert.equal(f.state.fetches.at(-1).body.redirect_budget,'');
});
test('a regular restriction replaces a break redirect and its save grant takes priority',async()=>{
  const pause={key:'pause',name:'Break',domains:['example.com'],all:false,kind:'redirect',minutes:0,grant:null,
    redirect_url:'https://rest.example.org/',break_until:Date.now()/1000+300,is_break:true};
  const policy={active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,restrictions:[pause]};
  const f=await fixture({policy});
  assert.equal(f.tabs.get(1).url,'https://rest.example.org/');
  f.state.policy.restrictions.unshift({key:'regular',name:'Restriction',domains:['example.com'],all:false,
    kind:'cover',minutes:3,grant:null,is_break:false});
  await vm.runInContext('sync()',f.context);
  assert.match(f.tabs.get(1).url,/^chrome-extension:\/\/fixture\/blocked.html/);
  assert.equal((await f.message('status')).minutes,3);
  assert.equal((await f.message('extend')).ok,true);
  assert.equal(f.tabs.get(1).url,'https://example.com/watch?id=private');
  assert.deepEqual(f.state.rules.find(rule=>rule.action.type==='allow').condition.tabIds,[1]);
  assert.ok(f.state.policy.restrictions[1].is_break);
});
test('a save grant spanning renewal keeps the tab usable while the break continues',async()=>{
  const regular={key:'regular',name:'Restriction',domains:['example.com'],all:false,kind:'cover',minutes:3,grant:null,is_break:false};
  const pause={key:'pause',name:'Break',domains:['example.com'],all:false,kind:'close',minutes:0,grant:null,
    break_until:Date.now()/1000+300,is_break:true};
  const f=await fixture({policy:{active:false,tracking:true,allow:[],block:[],mode:'blocklist',lease_seconds:30,
    restrictions:[regular,pause]}});
  assert.equal((await f.message('extend')).ok,true);
  f.state.policy.restrictions[0].grant_only=true;
  await vm.runInContext('sync()',f.context);
  assert.equal(f.tabs.get(1).url,'https://example.com/watch?id=private');
  f.state.policy.restrictions.shift();
  await vm.runInContext('sync()',f.context);
  assert.deepEqual(f.state.removed,[1]);
});
