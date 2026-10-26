/* Shared pure policy functions, also exercised by the Node regression tests. */
function siteBlocked(host, policy) {
  const matches = rule => host === rule || host.endsWith('.' + rule);
  return policy.active && (policy.block.some(matches) ||
    (policy.mode === 'allowlist' && !policy.allow.some(matches)));
}

function focusRules(policy) {
  if (!policy.active) return [];
  const redirect = {type: 'redirect', redirect: {extensionPath: '/blocked.html'}};
  const rules = [];
  let id = 1;
  if (policy.mode === 'allowlist') {
    rules.push({id: id++, priority: 1, action: redirect,
      condition: {regexFilter: '^https?://', excludedRequestDomains: ['localhost', '127.0.0.1'], resourceTypes: ['main_frame']}});
    if (policy.allow.length) rules.push({id: id++, priority: 2, action: {type: 'allow'},
      condition: {requestDomains: policy.allow, resourceTypes: ['main_frame']}});
  }
  if (policy.block.length) rules.push({id: id++, priority: 3, action: redirect,
    condition: {requestDomains: policy.block, resourceTypes: ['main_frame']}});
  return rules;
}
if (typeof module !== 'undefined') module.exports = {siteBlocked, focusRules};
