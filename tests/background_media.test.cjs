const {test}=require('node:test'),assert=require('node:assert/strict');
global.SiteIdentity=require('../gametime/browser_extension/sites.js');
const {select}=require('../gametime/browser_extension/media.js');
test('media observations require opt-in, audible, public and unmuted tabs',()=>{
  const tabs=[
    {id:1,url:'https://music.example.com/watch?secret=one',audible:true},
    {id:2,url:'https://music.example.com/other',audible:true},
    {id:3,url:'https://video.example.com/',audible:false},
    {id:4,url:'https://muted.example.com/',audible:true,mutedInfo:{muted:true}},
    {id:5,url:'https://private.example.com/',audible:true,incognito:true},
    {id:6,url:'https://unselected.example.com/',audible:true},
    {id:7,url:'https://sub.music.example.com/',audible:true},
    {id:8,url:'chrome://newtab',audible:true}
  ];
  assert.deepEqual(select(tabs,[]),[]);
  assert.deepEqual(select(tabs,['music.example.com','video.example.com','muted.example.com','private.example.com']),[{tabId:1,domain:'music.example.com'}]);
});
test('media matching retains canonical www and explicit local ports without paths',()=>{
  assert.deepEqual(select([{id:1,url:'http://localhost:8766/private?token=secret',audible:true},{id:2,url:'https://www.example.com/private',audible:true}],['127.0.0.1:8766','example.com']),[{tabId:1,domain:'127.0.0.1:8766'},{tabId:2,domain:'www.example.com'}]);
});
test('media observations are bounded and stop as soon as paused or tab-muted',()=>{
  const tabs=Array.from({length:30},(_,id)=>({id,url:`https://site${id}.example.com/`,audible:true}));
  const sites=tabs.map(t=>new URL(t.url).hostname);
  assert.equal(select(tabs,sites).length,16);
  assert.deepEqual(select(tabs.map(t=>({...t,mutedInfo:{muted:true}})),sites),[]);
  assert.deepEqual(select(tabs.map(t=>({...t,audible:false})),sites),[]);
});
