const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('gametime/browser_extension/local_update.js','utf8');

test('local desktop upgrade reloads the cached extension once and preserves pairing',async()=>{
  const storage={pairing:{token:'fixture',port:12345}}, token='a'.repeat(32); let reloads=0,installed='2.39.19',loaded='2.31.1';
  const context=vm.createContext({URL,chrome:{tabs:{async query(){return [];}},runtime:{getManifest:()=>({version:loaded}),getURL:p=>'chrome-extension://fixture/'+p,reload:()=>reloads++},
    storage:{session:{async get(){return {blockedTabs:{1:{host:'example.com',url:'https://example.com/original',token}}};}},
      local:{async get(){return {...storage};},async set(v){Object.assign(storage,v);}}}},
    async fetch(url,options){assert.equal(url,'chrome-extension://fixture/manifest.json');assert.equal(options.cache,'no-store');
      return {ok:true,async json(){return {version:installed};}};}});
  await vm.runInContext(source,context); assert.equal(reloads,1); assert.equal(storage.pairing.token,'fixture');
  assert.equal(storage.returnPages[token].url,'https://example.com/original');
  await vm.runInContext(source,context); assert.equal(reloads,1);
  loaded=installed; await vm.runInContext(source,context); assert.equal(reloads,1);
  installed='2.39.20'; await vm.runInContext(source,context); assert.equal(reloads,2);
  installed='invalid'; await vm.runInContext(source,context); assert.equal(reloads,2);
});

test('missing installed manifest leaves the existing extension running',async()=>{
  let reloads=0;
  const context=vm.createContext({chrome:{runtime:{getManifest:()=>({version:'2.39.19'}),getURL:p=>p,reload:()=>reloads++}},
    async fetch(){throw Error('file unavailable');}});
  await vm.runInContext(source,context); assert.equal(reloads,0);
});

function workerFixture(options={}) {
  const state={loaded:'2.39.22',installed:'2.39.23',clock:100000,reads:0,reloads:0,
    local:{pairing:{port:12345,token:'fixture'},browser:'brave'},...options};
  const context=vm.createContext({URL,importScripts(){},Date:{now:()=>state.clock},
    chrome:{tabs:{async query(){return state.tabs || [];},async get(id){return {...state.tabs.find(t=>t.id===id)};},
      async update(id,data){Object.assign(state.tabs.find(t=>t.id===id),data);}},runtime:{getManifest:()=>({version:state.loaded}),getURL:path=>'chrome-extension://fixture/'+path,
      reload(){if(state.reloadError) throw Error('reload failed'); state.reloads++;}},
      storage:{session:{async get(){return {blockedTabs:state.blockedTabs || {}};}},local:{async get(){return state.local;},
        async set(value){if(state.storageError) throw Error('storage unavailable'); Object.assign(state.local,value);}}}},
    async fetch(url){state.reads++; assert.equal(url,'chrome-extension://fixture/manifest.json');
      if(state.fetchError) throw Error('file being replaced');return {ok:true,async json(){return {version:state.installed};}};}});
  vm.runInContext(source,context);
  return {state,check:expected=>context.checkLocalExtensionUpdate(expected)};
}

test('unchanged or absent desktop version has no file or storage work',async()=>{
  const f=workerFixture();
  for (const version of [undefined,null,'bad',123,f.state.loaded]) assert.equal(await f.check(version),false);
  assert.equal(f.state.reads,0); assert.equal(f.state.reloads,0);
});

test('worker waits for installed files to match the completed desktop upgrade',async()=>{
  const f=workerFixture({installed:'2.39.22'});
  assert.equal(await f.check('2.39.23'),false); assert.equal(f.state.reloads,0);
  f.state.installed='2.39.23'; assert.equal(await f.check('2.39.23'),false);
  assert.equal(f.state.reads,1); f.state.clock+=60000;
  assert.equal(await f.check('2.39.23'),true); assert.equal(f.state.reloads,1);
});

test('parallel requests coalesce and a failed reload can retry without losing pairing',async()=>{
  const f=workerFixture({reloadError:true});
  assert.deepEqual(await Promise.all([f.check('2.39.23'),f.check('2.39.23')]),[false,false]);
  assert.equal(f.state.reads,1); assert.equal(f.state.local.localUpdateAttempt,'');
  f.state.reloadError=false; f.state.clock+=60000;
  assert.equal(await f.check('2.39.23'),true); assert.equal(f.state.local.pairing.token,'fixture');
  f.state.clock+=60000; assert.equal(await f.check('2.39.23'),false); assert.equal(f.state.reloads,1);
});

test('storage and file failures retain the running worker and retry at most once per minute',async()=>{
  for (const failure of ['fetchError','storageError']) {
    const f=workerFixture({[failure]:true});
    assert.equal(await f.check('2.39.23'),false); assert.equal(await f.check('2.39.23'),false);
    assert.equal(f.state.reads,1); assert.equal(f.state.reloads,0);
    f.state[failure]=false; f.state.clock+=60000;
    assert.equal(await f.check('2.39.23'),true);
  }
});

test('covered tabs hand off without exposing their original URL and roll back if reload fails',async()=>{
  for (const reloadError of [false,true]) {
    const token='b'.repeat(32),before='chrome-extension://fixture/blocked.html?key='+token;
    const f=workerFixture({reloadError,tabs:[{id:1,url:before,incognito:false}],
      blockedTabs:{1:{host:'example.com',url:'https://example.com/original',token}}});
    assert.equal(await f.check('2.39.23'),!reloadError);
    assert.equal(f.state.tabs[0].url,reloadError?before:'http://127.0.0.1:12345/browser-update#'+token);
    assert.equal(f.state.local.returnPages[token].url,'https://example.com/original');
  }
});

test('new extension pages leave updates to their background worker',async()=>{
  let reads=0;
  const context=vm.createContext({chrome:{runtime:{getManifest:()=>({version:'2.39.23'})}},fetch(){reads++;throw Error('Unexpected read');}});
  await vm.runInContext(source,context);assert.equal(reads,0);
});
