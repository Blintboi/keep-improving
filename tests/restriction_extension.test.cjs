const {test}=require('node:test');
const assert=require('node:assert/strict');
const {siteDecision,focusRules}=require('../gametime/browser_extension/policy.js');
const base={active:false,mode:'blocklist',block:[],allow:[]};
const entry={key:'a',name:'Fixture',domains:['example.com'],all:false,kind:'cover',minutes:3,grant:null};
test('custom restriction works independently of focus and covers subdomains',()=>{
  const p={...base,restrictions:[entry]};
  assert.equal(siteDecision('video.example.com',p).kind,'cover');
  assert.equal(siteDecision('example.com.attacker.com',p).kind,'');
  assert.equal(focusRules(p).length,1);
});
test('save allowance is limited to its tab token and expires',()=>{
  const p={...base,restrictions:[{...entry,minutes:0,grant:{subject:'site:example.com:abc',until:200}}]};
  assert.equal(siteDecision('example.com',p,'abc',100).kind,'');
  assert.equal(siteDecision('example.com',p,'other',100).kind,'cover');
  assert.equal(siteDecision('example.com',p,'abc',200).kind,'cover');
});
test('another restriction or focus block cannot be bypassed by a grant',()=>{
  const p={...base,restrictions:[{...entry,grant:{subject:'site:example.com:abc',until:Date.now()/1000+100}},
    {...entry,key:'b',minutes:0}],tabGrants:[{tabId:7,host:'example.com',token:'abc'}]};
  assert.equal(siteDecision('example.com',p,'abc').minutes,0);
  assert.ok(focusRules(p).every(r=>r.action.type!=='allow'));
  p.restrictions.pop(); p.active=true; p.block=['example.com'];
  assert.equal(siteDecision('example.com',p,'abc').kind,'cover');
});
test('allow rules are restricted to one tab and matching domain',()=>{
  const p={...base,restrictions:[{...entry,grant:{subject:'site:example.com:abc',until:Date.now()/1000+100}}],
    tabGrants:[{tabId:7,host:'example.com',token:'abc'}]};
  const allow=focusRules(p).find(r=>r.action.type==='allow');
  assert.deepEqual(allow.condition.tabIds,[7]); assert.deepEqual(allow.condition.requestDomains,['example.com']);
});
test('explicit close wins over covering',()=>{
  assert.equal(siteDecision('example.com',{...base,restrictions:[entry,{...entry,kind:'close'}]}).kind,'close');
});
