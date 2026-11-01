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
  const storage={}; const tabs=new Map([[1,{id:1,url:'https://example.com/watch?id=private',active:true,windowId:1,incognito:false}],
    [2,{id:2,url:'https://other.com/',active:false,windowId:1,incognito:false}]]);
  const state={policy:{active:false,tracking:true,allow:[],block:[],mode:'blocklist',remaining:0,lease_seconds:30,
    language:'hu',restriction_version:1,restrictions:[{key:'budget',name:'Fixture',domains:['example.com'],all:false,
      kind:'cover',minutes:3,grant:null}]},rules:[],removed:[],fetches:[]};
  if (options.policy) state.policy=copy(options.policy);
  const chrome={storage:{session:{async get(key){return {[key]:storage[key]};},async set(data){Object.assign(storage,copy(data));}},
    local:{async get(){return {pairing:{port:12345,token:'fixture'},browser:'brave'};}},onChanged:event()},
    windows:{async getLastFocused(){return {id:1,focused:true};},onFocusChanged:event()},
    tabs:{async query(query){return [...tabs.values()].filter(t=>!query.active||t.active).map(copy);},
      async get(id){if(options.race && id===1 && tabs.get(id)?.url.startsWith('https://example.com')) tabs.get(id).url='https://other.com/changed';
        if(!tabs.has(id)) throw Error('No tab'); return copy(tabs.get(id));},
      async update(id,data){Object.assign(tabs.get(id),data); return copy(tabs.get(id));},
      async remove(id){tabs.delete(id);state.removed.push(id);},onActivated:event(),onUpdated:event(),onRemoved:event()},
    declarativeNetRequest:{async getSessionRules(){return state.rules;},async updateSessionRules(data){state.rules=copy(data.addRules);}},
    action:{async setBadgeText(){},onClicked:event()},alarms:{create(){},onAlarm:event()},webNavigation:{onBeforeNavigate:event()},
    runtime:{id:'fixture',getURL:path=>'chrome-extension://fixture/'+path,onMessage:event(),onStartup:event(),onInstalled:event(),openOptionsPage(){}}};
  const context=vm.createContext({chrome,URL,crypto,AbortSignal,console,setTimeout:()=>1,clearTimeout:()=>{},
    async fetch(url,request){state.fetches.push({url,body:JSON.parse(request.body)});
      if(url.endsWith('/restriction-extension')) {
        const body=JSON.parse(request.body);
        if(options.reject) return {ok:true,async json(){return {ok:false};}};
        state.policy.restrictions[0].grant={subject:`site:${body.domain}:${body.token}`,until:Date.now()/1000+180};
        state.policy.restrictions[0].minutes=0;
        return {ok:true,async json(){return {ok:true};}};
      }
      return {ok:true,async json(){return copy(state.policy);}};
    }});
  context.importScripts=()=>vm.runInContext(options.legacy ? fs.readFileSync('tests/fixtures/browser_2_31_1/policy.js','utf8') : policySource,context);
  vm.runInContext(options.legacy ? fs.readFileSync('tests/fixtures/browser_2_31_1/background.js','utf8') : source,context);
  for(let i=0;i<100&&vm.runInContext('busy',context);i++) await delay(1);
  assert.equal(vm.runInContext('busy',context),false);
  return {context,chrome,tabs,state,storage,async message(action){
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
