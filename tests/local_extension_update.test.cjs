const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('gametime/browser_extension/local_update.js','utf8');

test('local desktop upgrade reloads the cached extension once and preserves pairing',async()=>{
  const storage={pairing:{token:'fixture',port:12345}}; let reloads=0,installed='2.39.19',loaded='2.31.1';
  const context=vm.createContext({chrome:{runtime:{getManifest:()=>({version:loaded}),getURL:p=>'chrome-extension://fixture/'+p,reload:()=>reloads++},
    storage:{local:{async get(){return {...storage};},async set(v){Object.assign(storage,v);}}}},
    async fetch(url,options){assert.equal(url,'chrome-extension://fixture/manifest.json');assert.equal(options.cache,'no-store');
      return {ok:true,async json(){return {version:installed};}};}});
  await vm.runInContext(source,context); assert.equal(reloads,1); assert.equal(storage.pairing.token,'fixture');
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
