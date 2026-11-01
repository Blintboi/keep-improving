const {test}=require('node:test');
const assert=require('node:assert/strict');
const {siteDecision,focusRules,redirectTarget}=require('../gametime/browser_extension/policy.js');
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

test('active break exposes its deadline without permitting save allowance',()=>{
  const p={...base,restrictions:[{...entry,minutes:0,break_until:200}]};
  const result=siteDecision('example.com',p,'',100);
  assert.equal(result.kind,'cover'); assert.equal(result.minutes,0); assert.equal(result.break_until,200);
  assert.equal(siteDecision('example.com',p,'',200).break_until,undefined);
});
test('break redirects only to its explicit website and cannot override another block',()=>{
  const redirect={...entry,kind:'redirect',minutes:0,redirect_url:'https://example.com/rest?q=1'};
  const grant={tabId:7,host:'example.com',token:'abc',url:redirect.redirect_url};
  const p={...base,restrictions:[redirect],redirectGrants:[grant]};
  assert.equal(siteDecision('example.com',p).kind,'redirect');
  assert.equal(redirectTarget(grant,p),'https://example.com/rest?q=1');
  const allow=focusRules(p).find(r=>r.action.type==='allow');
  assert.deepEqual(allow.condition.tabIds,[7]);
  assert.match('https://example.com/rest?q=1',new RegExp(allow.condition.regexFilter));
  assert.doesNotMatch('https://example.com/rest?q=2',new RegExp(allow.condition.regexFilter));
  const blocked={...p,restrictions:[redirect,{...entry,key:'other'}]};
  assert.equal(redirectTarget(grant,blocked),'');
  assert.ok(focusRules(blocked).every(r=>r.action.type!=='allow'));
  const dotted={...redirect,redirect_url:'https://example.com./rest'};
  const dottedGrant={...grant,url:dotted.redirect_url};
  assert.equal(redirectTarget(dottedGrant,{...base,restrictions:[dotted,{...entry,key:'other'}]}),'');
});
test('an empty destination means the browser new tab without an HTTP allow rule',()=>{
  const redirect={...entry,kind:'redirect',minutes:0,redirect_url:''};
  const grant={tabId:7,host:'example.com',token:'abc',url:''};
  const policy={...base,restrictions:[redirect],redirectGrants:[grant]};
  assert.equal(siteDecision('example.com',policy).kind,'redirect');
  assert.equal(redirectTarget(grant,policy),'about:newtab');
  assert.ok(focusRules(policy).every(rule=>rule.action.type!=='allow'));
});
test('a regular restriction takes priority over a simultaneous break and allows saving',()=>{
  const regular={...entry,key:'regular',minutes:3,is_break:false,
    grant:{subject:'site:example.com:abc',until:Date.now()/1000+100}};
  const pause={...entry,key:'pause',kind:'close',minutes:0,is_break:true,break_until:Date.now()/1000+60};
  const policy={...base,restrictions:[pause,regular],tabGrants:[{tabId:7,host:'example.com',token:'abc'}]};
  assert.equal(siteDecision('example.com',policy,'other').kind,'cover');
  assert.equal(siteDecision('example.com',policy,'other').minutes,3);
  assert.equal(siteDecision('example.com',policy,'other').break_until,undefined);
  assert.equal(siteDecision('example.com',policy,'abc').kind,'');
  assert.deepEqual(focusRules(policy).find(rule=>rule.action.type==='allow').condition.tabIds,[7]);
  policy.restrictions=[pause];
  assert.equal(siteDecision('example.com',policy,'abc').kind,'close');
});
test('a carried grant outranks a break only in the granted tab',()=>{
  const grant={subject:'site:example.com:abc',until:Date.now()/1000+100};
  const primary={...entry,key:'regular',grant,minutes:0,is_break:false,grant_only:true};
  const pause={...entry,key:'pause',kind:'close',minutes:0,is_break:true,break_until:Date.now()/1000+200};
  const policy={...base,restrictions:[primary,pause],tabGrants:[{tabId:7,host:'example.com',token:'abc'}]};
  assert.equal(siteDecision('example.com',policy,'abc').kind,'');
  assert.equal(siteDecision('example.com',policy,'other').kind,'close');
  const rules=focusRules(policy);
  assert.equal(rules.filter(rule=>rule.action.type==='redirect').length,1);
  assert.deepEqual(rules.find(rule=>rule.action.type==='allow').condition.tabIds,[7]);
});
