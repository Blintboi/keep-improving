/* Shared pure policy functions, also exercised by the Node regression tests. */
// The URL itself stays inside the extension; only a boolean is sent locally.
function braveNewTab(tab, browser) {
  if (browser !== 'brave' || !tab || tab.incognito || !tab.url) return false;
  try {
    const url = new URL(tab.url);
    return (url.protocol === 'brave:' && url.hostname === 'newtab') ||
      (url.protocol === 'chrome:' && ['newtab', 'new-tab-page'].includes(url.hostname));
  } catch { return false; }
}

function siteBlocked(host, policy) {
  const matches = rule => host === rule || host.endsWith('.' + rule);
  return policy.active && (policy.block.some(matches) ||
    (policy.mode === 'allowlist' && !policy.allow.some(matches)));
}

function focusRules(policy) {
  if (!policy.active && !(policy.restrictions || []).length) return [];
  const redirect = {type: 'redirect', redirect: {extensionPath: '/blocked.html'}};
  const rules = [];
  let id = 1;
  if (policy.active && policy.mode === 'allowlist') {
    rules.push({id: id++, priority: 1, action: redirect,
      condition: {regexFilter: '^https?://', excludedRequestDomains: ['localhost', '127.0.0.1'], resourceTypes: ['main_frame']}});
    if (policy.allow.length) rules.push({id: id++, priority: 2, action: {type: 'allow'},
      condition: {requestDomains: policy.allow, resourceTypes: ['main_frame']}});
  }
  if (policy.active && policy.block.length) rules.push({id: id++, priority: 3, action: redirect,
    condition: {requestDomains: policy.block, resourceTypes: ['main_frame']}});
  for (const entry of policy.restrictions || []) {
    if (!entry.all && !entry.domains.length) continue;
    const condition = {resourceTypes: ['main_frame']};
    if (entry.all) Object.assign(condition, {regexFilter: '^https?://', excludedRequestDomains: ['localhost', '127.0.0.1']});
    else condition.requestDomains = entry.domains;
    rules.push({id: id++, priority: 3, action: redirect, condition});
  }
  for (const grant of policy.tabGrants || []) {
    if (siteDecision(grant.host, policy, grant.token).kind) continue;
    rules.push({id: id++, priority: 4, action: {type: 'allow'},
      condition: {tabIds: [grant.tabId], requestDomains: [grant.host], resourceTypes: ['main_frame'],
        regexFilter: '^https?://' + grant.host.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?::[0-9]+)?/'}});
  }
  return rules;
}

function siteDecision(host, policy, token = '', now = Date.now() / 1000) {
  if (siteBlocked(host, policy)) return {kind: 'cover', minutes: 0, names: []};
  const matches = entry => entry.all || entry.domains.some(rule => host === rule || host.endsWith('.' + rule));
  const active = (policy.restrictions || []).filter(matches).filter(entry =>
    !(entry.grant && entry.grant.subject === `site:${host}:${token}` && entry.grant.until > now));
  return {kind: active.some(e => e.kind === 'close') ? 'close' : active.length ? 'cover' : '',
    minutes: active.length && active.every(e => e.kind === 'cover') ? Math.min(...active.map(e => e.minutes)) : 0,
    names: active.map(e => e.name)};
}
if (typeof module !== 'undefined') module.exports = {siteBlocked, siteDecision, focusRules, braveNewTab};
