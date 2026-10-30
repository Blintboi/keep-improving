const {test}=require('node:test');
const assert=require('node:assert/strict');
const {braveNewTab}=require('../gametime/browser_extension/policy.js');

test('only the known Brave new-tab pages are idle',()=>{
  for(const url of ['brave://newtab/','chrome://newtab/','chrome://new-tab-page/'])
    assert.equal(braveNewTab({url,incognito:false},'brave'),true,url);
  for(const url of ['https://example.com/','http://192.168.1.1/','brave://settings/','chrome://downloads/','about:blank','chrome-extension://abc/newtab.html'])
    assert.equal(braveNewTab({url,incognito:false},'brave'),false,url);
  assert.equal(braveNewTab({url:'chrome://newtab/',incognito:true},'brave'),false);
  assert.equal(braveNewTab({url:'chrome://newtab/',incognito:false},'chrome'),false);
  assert.equal(braveNewTab(null,'brave'),false);
});
