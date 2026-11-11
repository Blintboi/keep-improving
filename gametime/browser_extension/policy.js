/* Shared pure policy functions, also exercised by the Node regression tests. */
const policySites=typeof module!=='undefined'?require('./sites.js'):globalThis.SiteIdentity;
const localAllowed=(host,policy)=>!policySites.local(host) ||
  host!==`127.0.0.1:${policy.bridge_port}` && (policy.local_sites || []).includes(host);
function siteConditions(domains,policy) {
  const result=[],publicDomains=domains.filter(s=>!policySites.local(s));
  if(publicDomains.length)result.push({requestDomains:publicDomains});
  for(const host of domains.filter(s=>policySites.local(s)&&localAllowed(s,policy)))result.push({regexFilter:policySites.pattern(host)});
  return result;
}
function allSiteConditions(policy) {
  return [{regexFilter:'^https?://',excludedRequestDomains:['localhost','127.0.0.1','[::1]']},
    ...siteConditions((policy.local_sites || []).filter(s=>policySites.local(s)),policy)];
}
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
  if(!localAllowed(host,policy))return false;
  const matches = rule => host === rule || host.endsWith('.' + rule);
  return policy.active && (policy.block.some(matches) ||
    (policy.mode === 'allowlist' && !policy.allow.some(matches)));
}

function focusRules(policy) {
  if (!policy.active && !(policy.restrictions || []).length) return [];
  const redirect = {type: 'redirect', redirect: {extensionPath: '/blocked.html'}};
  const rules = [];
  let id = 1;
  const add=(conditions,priority,action)=>{for(const condition of conditions)rules.push({id:id++,priority,action,condition:{...condition,resourceTypes:['main_frame']}});};
  if (policy.active && policy.mode === 'allowlist') {
    add(allSiteConditions(policy),1,redirect);
    add(siteConditions(policy.allow,policy),2,{type:'allow'});
  }
  if (policy.active)add(siteConditions(policy.block,policy),3,redirect);
  for (const entry of policy.restrictions || []) {
    if (entry.grant_only) continue;
    if (!entry.all && !entry.domains.length) continue;
    add(entry.all?allSiteConditions(policy):siteConditions(entry.domains,policy),3,redirect);
  }
  for (const grant of policy.tabGrants || []) {
    if (siteDecision(grant.host, policy, grant.token).kind) continue;
    rules.push({id: id++, priority: 4, action: {type: 'allow'},
      condition: {tabIds: [grant.tabId],...(!policySites.local(grant.host)?{requestDomains:[grant.host]}:{}),resourceTypes: ['main_frame'],
        regexFilter:policySites.pattern(grant.host)}});
  }
  for (const grant of policy.redirectGrants || []) {
    const allowed = redirectTarget(grant, policy);
    if (!allowed) continue;
    try {
      const target = new URL(allowed);
      if (!['http:', 'https:'].includes(target.protocol)) continue;
      target.hash = '';
      const exact = target.href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      rules.push({id: id++, priority: 4, action: {type: 'allow'},
        condition: {tabIds: [grant.tabId], regexFilter: '^' + exact + '$', isUrlFilterCaseSensitive: true, resourceTypes: ['main_frame']}});
    } catch { /* Invalid or expired destinations get no exception. */ }
  }
  return rules;
}

function redirectTarget(grant, policy) {
  const decision = siteDecision(grant.host, policy, grant.token);
  if (decision.kind !== 'redirect' || decision.redirect_url !== grant.url) return '';
  if (grant.url === '') return 'about:newtab';
  try {
    const target = new URL(grant.url);
    if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password) return '';
    const others = {...policy, restrictions: (policy.restrictions || []).filter(e => e.key !== decision.redirect_key)};
    if (siteDecision(policySites.key(target.href), others).kind) return '';
    return target.href;
  } catch { return ''; }
}

function siteDecision(host, policy, token = '', now = Date.now() / 1000) {
  if(!localAllowed(host,policy))return {kind:'',minutes:0,names:[]};
  if (siteBlocked(host, policy)) return {kind: 'cover', minutes: 0, names: []};
  const matches = entry => (!entry.grant_only || entry.grant && entry.grant.subject === `site:${host}:${token}` && entry.grant.until > now) &&
    (entry.all || entry.domains.some(rule => host === rule || host.endsWith('.' + rule)));
  const matched = (policy.restrictions || []).filter(matches);
  const prioritized = matched.some(entry => !entry.is_break) ? matched.filter(entry => !entry.is_break) : matched;
  const active = prioritized.filter(entry =>
    !(entry.grant && entry.grant.subject === `site:${host}:${token}` && entry.grant.until > now));
  const redirect = active.find(e => e.kind === 'redirect' && typeof e.redirect_url === 'string');
  const kind = active.some(e => e.kind === 'close') ? 'close' :
    active.some(e => e.kind !== 'redirect') ? 'cover' : redirect ? 'redirect' : '';
  const result = {kind,
    minutes: active.length && active.every(e => e.kind === 'cover') ? Math.min(...active.map(e => e.minutes)) : 0,
    names: active.map(e => e.name)};
  if (kind === 'redirect') { result.redirect_url = redirect.redirect_url; result.redirect_key = redirect.key; }
  const breakUntil = Math.max(0, ...active.map(e => e.break_until || 0));
  if (active.some(e => e.requires_desktop)) result.requires_desktop = true;
  if (breakUntil > now) result.break_until = breakUntil;
  return result;
}
if (typeof module !== 'undefined') module.exports = {siteBlocked, siteDecision, focusRules, braveNewTab, redirectTarget};
