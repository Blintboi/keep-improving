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
  context.importScripts=()=>vm.runInContext(policySource,context);
  vm.runInContext(source,context);
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
