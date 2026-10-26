const {test} = require('node:test');
const assert = require('node:assert/strict');
const {siteBlocked, focusRules} = require('../gametime/browser_extension/policy.js');

test('allowlist domains include subdomains and block entries take priority', () => {
  const policy = {active: true, mode: 'allowlist', allow: ['example.com'], block: ['ads.example.com']};
  assert.equal(siteBlocked('docs.example.com', policy), false);
  assert.equal(siteBlocked('ads.example.com', policy), true);
  assert.equal(siteBlocked('example.com.evil.com', policy), true);
  assert.equal(siteBlocked('evil-example.com', policy), true);
  const rules = focusRules(policy);
  assert.equal(rules.length, 3);
  assert.deepEqual(rules.map(r => r.priority), [1, 2, 3]);
  assert.ok(rules.every(r => r.condition.resourceTypes[0] === 'main_frame'));
});
test('pause, reset, breaks and a disconnected desktop remove restrictions', () => {
  const policy = {active: false, mode: 'allowlist', allow: [], block: ['example.com']};
  assert.deepEqual(focusRules(policy), []);
  assert.equal(siteBlocked('example.com', policy), false);
});
test('blocklist redirects only configured domains', () => {
  const policy = {active: true, mode: 'blocklist', allow: [], block: ['example.com']};
  assert.equal(siteBlocked('other.com', policy), false);
  assert.equal(siteBlocked('a.example.com', policy), true);
  assert.deepEqual(focusRules(policy)[0].condition.requestDomains, ['example.com']);
});
