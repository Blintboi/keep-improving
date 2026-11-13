const {test}=require('node:test'),assert=require('node:assert/strict');
const {BrowserJournal,offlinePolicy,localDay,localClock,updateBudget}=require('../gametime/browser_extension/continuity.js');
const {siteDecision}=require('../gametime/browser_extension/policy.js');
const copy=x=>JSON.parse(JSON.stringify(x));
const stamp=new Date(2026,10,4,12).getTime()/1000;
let identities=0;const uuid=()=> (++identities).toString(16).padStart(32,'0');
function snapshot(changes={}) {return {version:1,at:stamp,language:'en',browser:'brave',path:'c:\\browser\\brave.exe',tracking:true,day_start:0,sound:false,
  budgets:[{id:'web',name:'Browser and website',members:[{kind:'app',value:'brave.exe'},{kind:'site',value:'example.com'}],seconds:60,used:0,usage:true,
    days:[0,1,2,3,4,5,6],renewal:0,day:localDay(stamp,0),enforce:true,steps:[],extension_minutes:0,runtime:{},fingerprint:'f'.repeat(64)}],
  focus:{token:'a'.repeat(32),running:true,phase:'focus',remaining:25,round:0,total:0,today:0,day:localDay(stamp,0),
    settings:{work:1,short_break:1,long_break:2,rounds:0},all:false,domains:['blocked.example']},...changes};}
function model(s=snapshot()) {return new BrowserJournal({snapshot:s},uuid);}
const tab={active:true,host:'example.com',redirect:'',locked:false};

test('idle browser samples pause usage but preserve focus clocks and resume without backfill',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');let now=stamp,state='active';const queried=[];
  const context=vm.createContext({module:{exports:{}},crypto,JSON,Date:{now:()=>now*1000},
    chrome:{idle:{queryState:async seconds=>{queried.push(seconds);return state;}}},braveNewTab:()=>false});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/continuity.js','utf8'),context);
  const worker=new context.module.exports.BrowserContinuityWorker();worker.model=model(snapshot({idle_timeout_seconds:120}));
  worker.session='one';worker.browser='brave';worker.save=async()=>{};
  await worker.sample({},'example.com','');now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.snapshot.budgets[0].used,1);
  state='idle';now++;await worker.sample({},'example.com','');now+=2;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.snapshot.budgets[0].used,1);assert.equal(worker.model.value.snapshot.focus.remaining,21);
  state='active';now++;await worker.sample({},'example.com','');now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.snapshot.budgets[0].used,2);assert.ok(queried.every(s=>s===120));
  worker.model.value.snapshot.idle_timeout_seconds=0;state='idle';now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.snapshot.budgets[0].used,3);assert.equal(queried.at(-1),60);
  state='locked';now++;await worker.sample({},'example.com','');assert.equal(worker.model.value.snapshot.budgets[0].used,3);
});

test('offline opening choices use in-page gates without navigation restrictions',()=>{
  for (const kind of ['notify','cover','break']) {
    const s=snapshot();s.focus.running=false;const b=s.budgets[0];b.enforce=false;b.usage=false;b.sessions=100;
    b.steps=[{id:'why',kind,time_mode:'sessions',offset:2,break_minutes:5,break_mode:'cover',
      session_choice:{question:'Why?',options:[{id:'work',label:'For work',limit:null},{id:'other',label:'Just checking',limit:2}]}}];
    const notices=[];updateBudget(b,stamp,notices);assert.equal(notices.length,0);assert.deepEqual(b.runtime.breaks,{});
    const policy=offlinePolicy(s,stamp),decision=siteDecision('example.com',policy,'',stamp);
    assert.equal(decision.kind,'');assert.deepEqual(policy.restrictions,[]);
    assert.deepEqual(policy.choice_rules,[{domains:['example.com'],all:true,name:b.name,requires_desktop:true}]);
  }
});

test('offline choices preserve independent limits, focus, grants and active days',()=>{
  const s=snapshot();s.focus.running=false;const b=s.budgets[0];b.enforce=false;b.usage=false;
  b.steps=[{id:'choice',kind:'cover',time_mode:'sessions',offset:2,session_choice:{question:'Why?'}},
    {id:'limit',kind:'cover',time_mode:'sessions',offset:5}];
  b.sessions=6;b.runtime.grant={subject:'site:example.com:token',until:stamp+60};
  let p=offlinePolicy(s,stamp);
  assert.equal(p.choice_rules.length,1);assert.equal(p.restrictions.length,1);
  assert.equal(siteDecision('example.com',p,'',stamp).kind,'cover');
  assert.equal(siteDecision('example.com',p,'token',stamp).kind,'');
  b.steps.pop();b.usage=true;b.seconds=0;
  assert.equal(siteDecision('example.com',offlinePolicy(s,stamp),'token',stamp).kind,'cover');
  b.days=[];p=offlinePolicy(s,stamp);assert.deepEqual(p.choice_rules,[]);assert.deepEqual(p.restrictions,[]);
  s.focus.running=true;assert.equal(siteDecision('blocked.example',offlinePolicy(s,stamp),'',stamp).kind,'cover');
});

test('one interval charges a browser/site group once and keeps a single timer',()=>{
  const m=model();m.observe(tab,stamp,'session');m.observe(tab,stamp+10,'session');
  assert.equal(m.value.snapshot.budgets[0].used,10);assert.equal(m.value.snapshot.focus.remaining,15);
  assert.equal(m.value.records.length,1);assert.equal(m.value.records[0].seq,1);
  assert.ok(!JSON.stringify(m.value.records).includes('://'));
});
test('durable restart retains journal identity and never replays an already sampled interval',()=>{
  let m=model();m.observe(tab,stamp,'session');m.observe(tab,stamp+10,'session');const saved=copy(m.value);
  m=new BrowserJournal(saved,uuid);m.observe(tab,stamp+10,'session');m.observe(tab,stamp+20,'session');
  assert.equal(m.value.stream,saved.stream);assert.deepEqual(m.value.records.map(r=>r.seq),[1,2]);
  assert.equal(m.value.snapshot.budgets[0].used,20);
});
test('browser closure, long sleep and clock rollback add no guessed time',()=>{
  const m=model();m.observe(tab,stamp,'one');m.observe(tab,stamp+1000,'two');m.observe(tab,stamp+2000,'two');
  m.observe(tab,stamp+1990,'two');assert.equal(m.value.records.length,0);
  m.observe(tab,stamp+2010,'two');assert.equal(m.value.snapshot.budgets[0].used,10);
  assert.equal(m.value.snapshot.focus.remaining,15);
});
test('private, background, lock and new-tab observations do not count browser activity',()=>{
  for(const empty of [{...tab,active:false},{...tab,active:false,host:''}]) {
    const m=model();m.observe(empty,stamp,'one');m.observe(empty,stamp+10,'one');
    assert.equal(m.value.snapshot.budgets[0].used,0);assert.equal(m.value.snapshot.focus.remaining,15);
  }
  const m=model();m.observe(tab,stamp,'one');m.observe({...tab,locked:true},stamp+10,'one');
  assert.equal(m.value.snapshot.budgets[0].used,0);
});
test('a natural completion and its notice survive restart without a second completion',()=>{
  let m=model();m.observe(tab,stamp,'one');m.observe(tab,stamp+30,'one');
  assert.equal(m.value.snapshot.focus.total,1);assert.equal(m.value.notices.length,1);
  m=new BrowserJournal(copy(m.value),uuid);m.observe(tab,stamp+40,'one');
  assert.equal(m.value.snapshot.focus.total,1);assert.equal(m.value.notices.length,1);
});
test('work completion carries overshoot into a break and stops at its end',()=>{
  const s=snapshot();s.focus.settings.rounds=4;const m=model(s);
  m.observe(tab,stamp,'one');m.observe(tab,stamp+30,'one');
  assert.equal(m.value.snapshot.focus.remaining,55);assert.equal(m.value.snapshot.focus.phase,'short_break');
  m.observe(tab,stamp+70,'one');m.observe(tab,stamp+90,'one');
  assert.equal(m.value.snapshot.focus.phase,'focus');assert.equal(m.value.snapshot.focus.running,false);
  assert.equal(m.value.snapshot.focus.total,1);
});
test('only a valid durable receipt removes records and the server replaces the shadow when caught up',()=>{
  const m=model();m.observe(tab,stamp,'one');m.observe(tab,stamp+10,'one');m.observe(tab,stamp+20,'one');
  assert.throws(()=>m.accept({ack:3,snapshot:snapshot()}));assert.equal(m.value.records.length,2);
  m.accept({ack:1,snapshot:snapshot()});assert.deepEqual(m.value.records.map(r=>r.seq),[2]);
  const fresh=snapshot({at:stamp+20});fresh.focus.remaining=5;
  m.accept({ack:2,snapshot:fresh});assert.equal(m.value.records.length,0);assert.equal(m.value.snapshot.focus.remaining,5);
  m.accept({ack:2,snapshot:fresh});assert.equal(m.value.snapshot.focus.total,0);
});
test('offline start pause stop are sequenced with timer generations and no implicit duplicate start',()=>{
  const m=model();m.value.snapshot.focus.running=false;m.observe(tab,stamp,'one');
  m.command('focus.start',stamp);const token=m.value.snapshot.focus.token;m.observe(tab,stamp+10,'one');
  m.command('focus.pause',stamp+10);m.observe(tab,stamp+20,'one');
  assert.equal(m.value.snapshot.focus.remaining,15);assert.notEqual(m.value.snapshot.focus.token,token);
  assert.deepEqual(m.value.records.map(r=>r.kind),['focus.start','sample','focus.pause','sample']);
  m.command('focus.stop',stamp+20);assert.equal(m.value.snapshot.focus.remaining,60);
});
test('offline budget expiry enforces cached rules without releasing them on a disconnected desktop',()=>{
  const m=model();m.value.snapshot.focus.running=false;m.observe(tab,stamp,'one');m.observe(tab,stamp+30,'one');m.observe(tab,stamp+60,'one');
  assert.equal(siteDecision('example.com',offlinePolicy(m.value.snapshot,stamp+60)).kind,'cover');
  assert.equal(siteDecision('elsewhere.example',offlinePolicy(m.value.snapshot,stamp+60)).kind,'cover');
});
test('daily renewal and disabled weekdays release budgets',()=>{
  const s=snapshot();s.focus.running=false;const b=s.budgets[0];b.used=60;
  assert.equal(siteDecision('example.com',offlinePolicy(s,stamp)).kind,'cover');
  const next=localClock(b.day,0)+86400;updateBudget(b,next,[]);
  assert.equal(b.used,0);assert.equal(siteDecision('example.com',offlinePolicy(s,next)).kind,'');
  b.used=60;b.days=[];assert.equal(siteDecision('example.com',offlinePolicy(s,next)).kind,'');
});

test('clock breaks and renewal run while browser is unfocused without adding usage',()=>{
  const s=snapshot();s.focus.running=false;const b=s.budgets[0];b.enforce=false;b.seconds=600;
  const now=new Date(stamp*1000);b.steps=[{id:'site:clock',kind:'break',time_mode:'clock',
    clock_minute:now.getHours()*60+now.getMinutes(),break_minutes:1,break_mode:'cover',offset:0}];
  const m=model(s);m.observe({...tab,active:false},stamp,'one');
  assert.equal(siteDecision('example.com',offlinePolicy(m.value.snapshot,stamp)).kind,'cover');
  m.effects(stamp);assert.equal(m.value.records[0].kind,'budget.state');assert.equal(b.used,0);
  m.observe({...tab,active:false},stamp+120,'one');
  assert.equal(siteDecision('example.com',offlinePolicy(m.value.snapshot,stamp+120)).kind,'');
  const tomorrow=localClock(b.day,0)+86400;m.observe({...tab,active:false},tomorrow,'one');
  assert.equal(m.value.snapshot.budgets[0].day,localDay(tomorrow,0));
  assert.equal(m.value.records.filter(r=>r.kind==='sample').length,0);
});
test('breaks and warning receipts are durable and exported once',()=>{
  const s=snapshot();s.focus.running=false;const b=s.budgets[0];b.enforce=false;b.seconds=600;
  b.steps=[{id:'site:warn',kind:'notify',time_mode:'usage',offset:10,sound:false,popup:true},
    {id:'site:break',kind:'break',time_mode:'usage',offset:20,break_minutes:1,break_mode:'redirect',redirect_url:''}];
  const m=model(s);m.observe(tab,stamp,'one');m.observe(tab,stamp+30,'one');m.effects(stamp+30);
  assert.equal(m.value.notices.length,1);assert.equal(m.value.records.filter(r=>r.kind==='budget.state').length,1);
  const decision=siteDecision('example.com',offlinePolicy(m.value.snapshot,stamp+30));assert.equal(decision.kind,'redirect');
  m.effects(stamp+30);assert.equal(m.value.records.filter(r=>r.kind==='budget.state').length,1);
});

test('chunk persistence, failed writes, acknowledgements and pairing changes preserve isolation',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');
  const local={},session={};let failWrite=false,failRemove=false,writes=[];
  const area=data=>({async get(keys){return Object.fromEntries((Array.isArray(keys)?keys:[keys]).filter(k=>k in data).map(k=>[k,copy(data[k])]));},
    async set(value){if(failWrite){failWrite=false;throw Error('quota fixture');}writes.push(Object.keys(value));Object.assign(data,copy(value));},
    async remove(keys){if(failRemove){failRemove=false;throw Error('delete fixture');}for(const key of keys)delete data[key];}});
  const context=vm.createContext({module:{exports:{}},crypto,chrome:{storage:{local:area(local),session:area(session)}},console,Date,JSON});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/continuity.js','utf8'),context);
  const Worker=context.module.exports.BrowserContinuityWorker,pairing={port:12345,token:'a'.repeat(64)};
  let worker=new Worker();await worker.load(pairing,'brave');
  worker.model.value.snapshot=snapshot();
  for(let i=0;i<300;i++) worker.model.append({kind:'sample',start:stamp+i,end:stamp+i+1,host:'example.com',active:true,redirect:'',timer:''});
  await worker.save();const stream=worker.model.value.stream;writes=[];
  worker.model.append({kind:'sample',start:stamp+300,end:stamp+301,host:'example.com',active:true,redirect:'',timer:''});
  failWrite=true;await assert.rejects(worker.save());
  const restored=new Worker();await restored.load(pairing,'brave');assert.equal(restored.model.value.records.length,300);
  await worker.save();assert.deepEqual(writes[0].filter(k=>k.startsWith('continuityChunk:')),['continuityChunk:2']);
  worker.model.accept({ack:270,snapshot:snapshot()});await worker.save();
  worker=new Worker();await worker.load(pairing,'brave');assert.equal(worker.model.value.stream,stream);
  assert.deepEqual(Array.from(worker.model.value.records,r=>r.seq),Array.from({length:31},(_,i)=>i+271));
  worker.model.accept({ack:301,snapshot:snapshot()});failRemove=true;await worker.save();
  worker=new Worker();await worker.load(pairing,'brave');assert.equal(worker.model.value.records.length,0);
  await worker.load({port:12345,token:'b'.repeat(64)},'brave');assert.equal(worker.model.value.records.length,0);
  assert.notEqual(worker.model.value.stream,stream);assert.equal(worker.model.value.snapshot,null);
});

test('failed durable writes roll back offline commands and one-time allowances',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');let actions=0;
  const context=vm.createContext({module:{exports:{}},crypto,Date,JSON,siteDecision,
    activeTab:async()=>null,publicHost:()=>'',setPolicy:async()=>actions++,applyPolicyTabs:async()=>actions++});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/continuity.js','utf8'),context);
  const worker=new context.module.exports.BrowserContinuityWorker();worker.model=model();worker.sample=async()=>{};
  worker.save=async()=>{throw Error('quota fixture');};
  const before=JSON.stringify(worker.model.value);
  await assert.rejects(worker.control('focus.stop'));
  assert.equal(JSON.stringify(worker.model.value),before);assert.equal(actions,0);
  worker.model.value.snapshot.focus.running=false;
  const b=worker.model.value.snapshot.budgets[0];b.used=70;
  b.steps=[{id:'site:restrict',kind:'restrict',time_mode:'usage',offset:0,extension_minutes:1}];
  const beforeGrant=JSON.stringify(worker.model.value);
  await assert.rejects(worker.extend('example.com','c'.repeat(32)));
  assert.equal(JSON.stringify(worker.model.value),beforeGrant);
  worker.save=async()=>{};assert.equal(await worker.extend('example.com','c'.repeat(32)),true);
  assert.equal(await worker.extend('example.com','d'.repeat(32)),false);
});

test('a full journal rolls back a sample and can still drain in bounded batches',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');let sent=0;
  const context=vm.createContext({module:{exports:{}},crypto,Date,JSON,AbortSignal,chrome:{},braveNewTab:()=>false,
    fetch:async(url,options)=>{const data=JSON.parse(options.body);assert.ok(data.records.length<=128);sent+=data.records.length;
      return {ok:true,status:200,json:async()=>({ok:true,result:{ack:data.records.at(-1).seq,snapshot:snapshot(),policy:{active:false}}})};}});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/continuity.js','utf8'),context);
  const worker=new context.module.exports.BrowserContinuityWorker();worker.model=model();worker.session='one';worker.browser='brave';
  worker.model.value.checkpoint={...tab,at:Date.now()/1000-1,session:'one'};
  const before=JSON.stringify(worker.model.value);
  worker.save=async()=>{throw Error('quota fixture');};
  await assert.rejects(worker.sample({},'example.com',''));
  assert.deepEqual(copy(worker.model.value),JSON.parse(before));
  worker.save=async()=>{};
  for(let i=0;i<25000;i++)worker.model.append({kind:'sample',start:stamp+i,end:stamp+i+1,host:'example.com',active:true,redirect:'',timer:''});
  await assert.rejects(worker.sample({},'example.com',''),/storage is full/);
  assert.equal(worker.model.value.seq,25000);assert.equal(worker.model.value.records.length,25000);
  await worker.exchange({port:12345,token:'fixture'});assert.equal(worker.connected,false);
  for(let i=0;worker.model.value.records.length && i<30;i++)await worker.exchange({port:12345,token:'fixture'});
  assert.equal(sent,25000);assert.equal(worker.connected,true);assert.equal(worker.model.value.ack,25000);
});


test('session limit allows five visits, blocks six, and ignores repeated samples and restart',()=>{
  const s=snapshot(),b=s.budgets[0];b.usage=false;b.enforce=false;b.members=[{kind:'site',value:'example.com'}];
  b.steps=[{id:'session-cap',kind:'cover',time_mode:'sessions',offset:5}];let m=model(s);
  for(let n=0;n<6;n++){
    m.observe(tab,stamp+n*10,'one');m.observe({...tab,active:false},stamp+n*10+2,'one');
    assert.equal(m.value.snapshot.budgets[0].sessions,n+1);
    assert.equal(offlinePolicy(m.value.snapshot,stamp+n*10+2).restrictions.length,n<5?0:1);
    m=new BrowserJournal(copy(m.value),uuid);m.observe({...tab,active:false},stamp+n*10+3,'one');
  }
});
test('session seed and browser/site overlap continue one visit across handoff',()=>{
  const s=snapshot(),b=s.budgets[0];b.sessions=5;b.session_visit={key:'app:'+s.path,finish:stamp};b.usage=false;b.enforce=false;
  b.steps=[{id:'pause',kind:'break',time_mode:'sessions',offset:5,break_minutes:1,break_mode:'cover'}];
  const m=model(s);m.observe(tab,stamp,'one');m.observe({...tab,host:'second.example'},stamp+10,'one');m.observe(tab,stamp+20,'one');
  assert.equal(m.value.snapshot.budgets[0].sessions,5);assert.equal(offlinePolicy(m.value.snapshot,stamp+20).restrictions.length,0);
  m.observe({...tab,active:false},stamp+21,'one');m.observe(tab,stamp+22,'one');m.observe(tab,stamp+23,'one');
  assert.equal(m.value.snapshot.budgets[0].sessions,6);assert.equal(offlinePolicy(m.value.snapshot,stamp+23).restrictions.length,1);
  updateBudget(m.value.snapshot.budgets[0],stamp+83,[]);assert.equal(offlinePolicy(m.value.snapshot,stamp+83).restrictions.length,0);
});


test('audible media optionally prevents idle and stopping starts the timeout, including worker restart',async()=>{
  const vm=require('node:vm'),fs=require('node:fs'),crypto=require('node:crypto');let now=stamp,state='idle',audible=[],queries=0;
  const context=vm.createContext({module:{exports:{}},crypto,JSON,Date:{now:()=>now*1000},
    chrome:{idle:{queryState:async()=>state},tabs:{query:async()=>{queries++;return audible;}}},braveNewTab:()=>false});
  vm.runInContext(fs.readFileSync('gametime/browser_extension/continuity.js','utf8'),context);
  const Worker=context.module.exports.BrowserContinuityWorker;let worker=new Worker();
  worker.model=model(snapshot({idle_timeout_seconds:60,media_prevents_idle:true}));worker.session='one';worker.save=async()=>{};
  await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,false);
  audible=[{audible:true,mutedInfo:{muted:false}}];now++;await worker.sample({},'example.com','');now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.snapshot.budgets[0].used,1);
  audible=[];now+=10;await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,true);
  const saved=worker.model;worker=new Worker();worker.model=saved;worker.session='one';worker.save=async()=>{};
  now+=10;await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,true);
  now+=40;await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,false);
  audible=[{audible:true,mutedInfo:{muted:true}},{audible:true,incognito:true}];now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.checkpoint.active,false);
  audible=[{audible:true}];now++;await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,true);
  state='locked';now++;await worker.sample({},'example.com','');assert.equal(worker.model.value.checkpoint.active,false);
  worker.model.value.snapshot.media_prevents_idle=false;state='idle';const before=queries;now++;await worker.sample({},'example.com','');
  assert.equal(worker.model.value.checkpoint.active,false);assert.equal(queries,before);
});
