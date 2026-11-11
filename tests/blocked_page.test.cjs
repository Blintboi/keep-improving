const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('offline opening choice explains how to continue in both languages',async()=>{
  for(const language of ['hu','en']) {
    const elements=new Map(),element=id=>{if(!elements.has(id))elements.set(id,{dataset:{},addEventListener(){}});return elements.get(id);};
    const context={document:{documentElement:{},getElementById:element},chrome:{runtime:{sendMessage:async()=>({ok:true,kind:'cover',language,minutes:0,requires_desktop:true})}},Date,setInterval(){}};
    vm.createContext(context);vm.runInContext(fs.readFileSync('gametime/browser_extension/blocked.js','utf8'),context);await vm.runInContext('refresh()',context);
    assert.ok(element('reason').textContent.includes('Keep Improving'));assert.equal(element('extra').hidden,true);
  }
});
test('blocked page only explains an available saving allowance in both languages',async()=>{
  const code=fs.readFileSync('gametime/browser_extension/blocked.js','utf8');
  for(const language of ['hu','en'])for(const minutes of [0,3]){
    const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{hidden:false,dataset:{},addEventListener(){}});return elements.get(id);};
    const context={document:{documentElement:{},getElementById:element},chrome:{runtime:{sendMessage:async()=>({ok:true,kind:'cover',language,minutes})}},Date,setInterval(){}};
    vm.createContext(context);vm.runInContext(code,context);await vm.runInContext('refresh()',context);
    assert.equal(element('once').hidden,!minutes);assert.equal(element('extra').hidden,!minutes);
    if(!minutes)assert.equal(element('once').textContent,'');
  }
  assert.ok(!fs.readFileSync('gametime/browser_extension/blocked.html','utf8').includes('Budgets'));
});
