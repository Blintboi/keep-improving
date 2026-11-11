const {test}=require('node:test'),assert=require('node:assert/strict');
const sites=require('../gametime/browser_extension/sites.js');
const {siteBlocked,siteDecision,focusRules}=require('../gametime/browser_extension/policy.js');
const local='127.0.0.1:8766';
const base={active:false,block:[],allow:[],mode:'blocklist',local_sites:[local],bridge_port:47853,restrictions:[{key:'local',name:'Local',kind:'cover',domains:[local],all:false,minutes:2}]};
test('loopback aliases preserve ports but strip private URL parts',()=>{
  for(const value of ['http://127.0.0.1:8766/path?q=secret','http://localhost:8766/','http://[::1]:8766/'])assert.equal(sites.key(value),local);
  assert.equal(sites.key('127.0.0.1:443'),'127.0.0.1:443');assert.equal(sites.key('https://localhost/'),'127.0.0.1:443');
  for(const value of ['http://localhost:0','http://localhost:65536','http://192.168.1.1/','http://secret@localhost:8766/','file:///local'])assert.equal(sites.key(value),'');
});
test('restrictions and DNR rules isolate the configured port and aliases',()=>{
  assert.equal(siteDecision(local,base).kind,'cover');assert.equal(siteDecision('127.0.0.1:8767',base).kind,'');
  const rule=focusRules(base)[0];assert.equal(rule.condition.requestDomains,undefined);
  const regex=new RegExp(rule.condition.regexFilter);
  for(const value of ['http://127.0.0.1:8766/','http://localhost:8766/','http://[::1]:8766/'])assert.ok(regex.test(value));
  for(const value of ['http://127.0.0.1:8767/','http://127.0.0.1:47853/control','http://localhost:87660/','http://localhost.evil.com:8766/'])assert.ok(!regex.test(value));
});
test('all-sites restrictions include only opted-in local ports, never the bridge',()=>{
  const policy={...base,active:true,mode:'allowlist',local_sites:[local,'127.0.0.1:47853'],restrictions:[]};
  assert.ok(siteBlocked(local,policy));assert.ok(!siteBlocked('127.0.0.1:8767',policy));assert.ok(!siteBlocked('127.0.0.1:47853',policy));
  const rules=focusRules(policy);assert.equal(rules.length,2);assert.ok(!new RegExp(rules[1].condition.regexFilter).test('http://127.0.0.1:47853/browser-update'));
});
test('a local save allowance applies only to its port and tab',()=>{
  const policy={...base,restrictions:[{...base.restrictions[0],grant:{subject:'site:'+local+':token',until:Date.now()/1000+30}}],tabGrants:[{tabId:7,host:local,token:'token'}]};
  assert.equal(siteDecision(local,policy,'token').kind,'');const allow=focusRules(policy).find(r=>r.action.type==='allow');
  assert.deepEqual(allow.condition.tabIds,[7]);assert.ok(!new RegExp(allow.condition.regexFilter).test('http://localhost:8767/'));
});
