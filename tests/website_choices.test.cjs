const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
function fixture(storage={}){
  const state={tab:{id:1,url:'https://example.com/page',incognito:false},sent:[],calls:[]};
  const chrome={runtime:{id:'fixture'},storage:{session:{get:async key=>({[key]:storage[key]}),set:async value=>Object.assign(storage,value)}},
    tabs:{sendMessage:async(id,message)=>state.sent.push({id,message})},scripting:{executeScript:async()=>{throw Error('Unexpected injection');}}};
  const context=vm.createContext({chrome,crypto,URL,blockedTabs:{},activeTab:async()=>state.tab,publicHost:t=>t?.incognito?'':new URL(t.url).hostname,siteDecision:()=>({kind:''})});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/site-choices.js','utf8'),context);
  const gate=vm.runInContext('new WebsiteChoices()',context);
  gate.call=async(pairing,action,data)=>{state.calls.push({action,data});return {choice:{budget:'budget',step:'step',question:'Why?',options:[]}};};
  const policy={language:'en',choice_rules:[{domains:['example.com'],all:false}]};
  return {gate,state,storage,policy,async sync(){return gate.sync(state.tab,state.tab&&!state.tab.incognito?new URL(state.tab.url).hostname:'',policy,{},'brave');}};
}
test('same-domain tabs keep the visit; leaving and returning starts a new one',async()=>{
  const f=fixture();await f.sync();const first=f.gate.visit.token;
  f.state.tab={...f.state.tab,id:2,url:'https://example.com/other'};await f.sync();assert.equal(f.gate.visit.token,first);
  assert.ok(f.state.sent.some(m=>m.id===1&&m.message.value===null));
  f.state.tab=null;await f.sync();f.state.tab={id:2,url:'https://example.com/other'};await f.sync();assert.notEqual(f.gate.visit.token,first);
});
test('worker restart retains visit and can dismiss its restored overlay',async()=>{
  const f=fixture();await f.sync();const again=fixture(f.storage);again.gate.call=async()=>({choice:null});await again.sync();
  assert.equal(again.gate.visit.token,f.gate.visit.token);assert.ok(again.state.sent.some(m=>m.id===1&&m.message.value===null));
});
test('private tabs never request a question and clear the previous visit',async()=>{
  const f=fixture();await f.sync();f.state.tab.incognito=true;await f.sync();assert.equal(f.state.calls.length,1);assert.equal(f.gate.visit,null);
});
test('a stale tab, visit or subframe cannot consume an allowance',async()=>{
  const f=fixture();await f.sync();const p=f.gate.pending;
  const message={visit:p.data.visit,budget:'budget',step:'step',choice:'answer'},sender={id:'fixture',frameId:0,tab:f.state.tab,url:f.state.tab.url};
  assert.equal((await f.gate.choose({...message,visit:'a'.repeat(32)},sender,{})).ok,false);
  assert.equal((await f.gate.choose(message,{...sender,frameId:1},{})).ok,false);
  f.state.tab={id:2,url:'https://elsewhere.com/'};assert.equal((await f.gate.choose(message,sender,{})).ok,false);
  assert.equal(f.state.calls.length,1);
});

test('failed choice requests wait in-page and reconnect with the same accepted visit',async()=>{
  const f=fixture();f.gate.call=async()=>({choice:null});await f.sync();const token=f.gate.visit.token;
  f.gate.call=async()=>{throw Error('Control timeout');};await f.sync();
  assert.equal(f.gate.pending.value.offline,true);assert.equal(f.gate.visit.token,token);
  assert.equal(f.state.sent.at(-1).message.value.offline,true);
  f.gate.call=async()=>({choice:null});await f.sync();
  assert.equal(f.gate.pending,null);assert.equal(f.gate.visit.token,token);assert.equal(f.state.sent.at(-1).message.value,null);
});

test('offline fallback makes no choice request and survives a worker restart',async()=>{
  const f=fixture();f.policy.choice_rules[0].requires_desktop=true;await f.sync();
  assert.equal(f.state.calls.length,0);assert.equal(f.gate.pending.value.offline,true);
  const again=fixture(f.storage);again.policy.choice_rules[0].requires_desktop=true;await again.sync();
  assert.equal(again.gate.visit.token,f.gate.visit.token);assert.equal(again.gate.pending.value.offline,true);
  assert.equal((await again.gate.choose({}, {id:'fixture',frameId:0,tab:again.state.tab,url:again.state.tab.url},{})).ok,false);
  again.state.tab.incognito=true;await again.sync();assert.equal(again.gate.visit,null);assert.equal(again.gate.pending,null);
});

test('a document rejecting injection cannot turn a healthy policy into global offline mode',async()=>{
  const f=fixture();f.gate.send=async()=>{throw Error('Cannot access a protected document');};
  await assert.doesNotReject(f.sync());assert.ok(f.gate.pending);
});
