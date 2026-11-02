const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),{webcrypto}=require('node:crypto');
const source=fs.readFileSync('gametime/browser_extension/dashboard_update.js','utf8');
function fixture(tabs,local={}){const updates=[];const context=vm.createContext({URL,crypto:webcrypto,chrome:{runtime:{getURL:path=>'chrome-extension://fixture/'+path},storage:{local:{async get(){return local;},async set(value){Object.assign(local,value);}}},tabs:{async query(){return tabs;},async get(id){return tabs.find(t=>t.id===id);},async update(id,value){updates.push({id,...value});Object.assign(tabs.find(t=>t.id===id),value);}}}});vm.runInContext(source,context);return {context,local,tabs,updates};}
test('dashboard handoff retains tab, section and browser drafts',async()=>{
 const f=fixture([{id:7,url:'chrome-extension://fixture/panel.html#notifications'},{id:8,url:'https://example.com'},{id:9,url:'chrome-extension://fixture/panel.html#focus',incognito:true}],{'draft:fixture':{title:'Unapplied'}});
 await f.context.dashboardRestored;const moved=await f.context.prepareDashboardUpgrade({port:12345});assert.equal(moved.length,1);assert.equal(moved[0].id,7);assert.match(f.tabs[0].url,/\/browser-update#dashboard-[a-f0-9]{32}$/);
 await f.context.restoreDashboardTabs();assert.equal(f.tabs[0].url,'chrome-extension://fixture/panel.html#notifications');assert.equal(f.tabs[1].url,'https://example.com');assert.equal(f.tabs[2].url,'chrome-extension://fixture/panel.html#focus');assert.equal(f.local['draft:fixture'].title,'Unapplied');assert.deepEqual(Object.keys(f.local.dashboardReturns),[]);
});
test('restoration rejects external destinations, old records and reused tabs',async()=>{
 const key='a'.repeat(32),url='http://127.0.0.1:12345/browser-update#dashboard-'+key;
 for(const record of [{section:'https://attacker.example',port:12345,savedAt:Date.now()},{section:'settings',port:12345,savedAt:0},{section:'settings',port:1,savedAt:Date.now()}]){const f=fixture([{id:7,url}],{dashboardReturns:{[key]:record}});await f.context.dashboardRestored;assert.equal(f.updates.length,0);}
 const f=fixture([{id:7,url:'https://example.com/new'}],{dashboardReturns:{[key]:{section:'settings',port:12345,savedAt:Date.now()}}});await f.context.dashboardRestored;assert.equal(f.updates.length,0);
});
