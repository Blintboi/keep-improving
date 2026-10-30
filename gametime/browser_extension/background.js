importScripts('policy.js');
let timer, busy = false, rerun = false, signature = '', leaseUntil = 0;
let policy = {active: false, tracking: true, allow: [], block: [], mode: 'blocklist'};
let blockedTabs = {};
const restored = chrome.storage.session.get('blockedTabs').then(data => { blockedTabs = data.blockedTabs || {}; });
async function saveBlocked() { await chrome.storage.session.set({blockedTabs}); }
function grantTabs() { return Object.entries(blockedTabs).map(([id, r]) => ({tabId: Number(id), host: r.host, token: r.token})); }

async function setPolicy(next) {
  policy = next;
  leaseUntil = Date.now() + Math.max(0, next.lease_seconds || next.remaining || 0) * 1000;
  const rules = focusRules({...next, tabGrants: grantTabs()});
  const key = JSON.stringify(rules);
  if (key === signature) return;
  const old = await chrome.declarativeNetRequest.getSessionRules();
  await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds: old.map(r => r.id), addRules: rules});
  signature = key;
}

async function activeTab() {
  const win = await chrome.windows.getLastFocused();
  if (!win || !win.focused) return null;
  const tabs = await chrome.tabs.query({active: true, windowId: win.id});
  return tabs[0] || null;
}

function publicHost(tab) {
  if (!tab || tab.incognito) return '';
  try {
    const url = new URL(tab.url || '');
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return '';
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    if (!host.includes('.') || /^[\d.]+$/.test(host) || host.includes(':') ||
      /\.(local|localhost|internal|test|invalid)$/.test(host)) return '';
    return host;
  } catch { return ''; }
}

async function sync() {
  if (busy) { rerun = true; return; }
  busy = true;
  clearTimeout(timer);
  try {
    await restored;
    const {pairing, browser = 'brave'} = await chrome.storage.local.get(['pairing', 'browser']);
    if (!pairing) {
      await setPolicy({active: false, tracking: true, allow: [], block: [], mode: 'blocklist'});
      return;
    }
    const tab = await activeTab();
    const host = publicHost(tab);
    const response = await fetch(`http://127.0.0.1:${pairing.port}/activity`, {
      method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(3000),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pairing.token},
      body: JSON.stringify({browser, domain: policy.tracking ? host : '', focused: !!tab, private: !!tab?.incognito, idle: braveNewTab(tab, browser)})
    });
    if (!response.ok) throw new Error('Connection unavailable');
    await setPolicy(await response.json());
    await chrome.action.setBadgeText({text: policy.active ? 'LIMIT' : ''});
    // Include matching background media tabs; re-read before each mutation.
    for (const candidate of await chrome.tabs.query({})) {
      const recordBefore = blockedTabs[candidate.id];
      const blockedPage = candidate.url?.startsWith(chrome.runtime.getURL('blocked.html'));
      const host = publicHost(candidate) || (blockedPage ? recordBefore?.host : '');
      if (!host || candidate.incognito) continue;
      let record = recordBefore;
      if (!record || record.host !== host) record = {host, url: candidate.url, token: crypto.randomUUID().replaceAll('-', '')};
      const decision = siteDecision(host, policy, record.token);
      if (!decision.kind || blockedPage && decision.kind !== 'close') continue;
      const current = await chrome.tabs.get(candidate.id).catch(() => null);
      if (!current || current.url !== candidate.url || current.incognito) continue;
      blockedTabs[current.id] = record; await saveBlocked();
      if (decision.kind === 'close') await chrome.tabs.remove(current.id);
      else await chrome.tabs.update(current.id, {url: chrome.runtime.getURL('blocked.html') + '?key=' + record.token});
    }
    await chrome.storage.session.set({connected: true, lastContact: Date.now()});
  } catch {
    // A closed monitor, expired pairing or network error must release browser restrictions.
    await setPolicy({active: false, tracking: true, allow: [], block: [], mode: 'blocklist'});
    await chrome.action.setBadgeText({text: '!'});
    await chrome.storage.session.set({connected: false});
  } finally {
    busy = false;
    if ((policy.active || (policy.restrictions || []).length) && Date.now() >= leaseUntil)
      await setPolicy({...policy, active: false, restrictions: []});
    timer = setTimeout(sync, policy.active || (policy.restrictions || []).length ? 2000 : 10000);
    if (rerun) { rerun = false; clearTimeout(timer); timer = setTimeout(sync, 0); }
  }
}
chrome.tabs.onActivated.addListener(sync);
chrome.tabs.onUpdated.addListener((id, change, tab) => { if (tab.active && (change.url || change.status === 'complete')) sync(); });
chrome.tabs.onRemoved.addListener(id => { delete blockedTabs[id]; saveBlocked(); sync(); });
chrome.windows.onFocusChanged.addListener(sync);
chrome.storage.onChanged.addListener((changes, area) => { if (area === 'local') sync(); });
chrome.alarms.onAlarm.addListener(sync);
chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onInstalled.addListener(() => { chrome.alarms.create('connection', {periodInMinutes: 0.5}); sync(); });
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
chrome.webNavigation.onBeforeNavigate.addListener(async details => {
  if (details.frameId !== 0) return;
  await restored;
  const tab = await chrome.tabs.get(details.tabId).catch(()=>null);
  if (!tab || tab.incognito) return;
  const host = publicHost({...tab, url: details.url});
  if (!host) return;
  const previous = blockedTabs[details.tabId];
  if (siteDecision(host, policy, previous?.token || '').kind) {
    blockedTabs[details.tabId] = {host, url: details.url,
      token: previous?.host === host ? previous.token : crypto.randomUUID().replaceAll('-', '')};
    await saveBlocked();
  }
});
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || !sender.tab ||
      !sender.url?.startsWith(chrome.runtime.getURL('blocked.html'))) return;
  (async () => {
    await restored;
    const record = blockedTabs[sender.tab.id];
    const key = new URL(sender.url).searchParams.get('key');
    if (!record || key && key !== record.token)
      return {ok: false, language: policy.language || 'en', minutes: 0};
    const decision = siteDecision(record.host, policy, record.token);
    if (message.action === 'status') return {...decision, ok: true, language: policy.language || 'en'};
    if (message.action === 'extend' && decision.minutes > 0) {
      const {pairing} = await chrome.storage.local.get('pairing');
      const response = await fetch(`http://127.0.0.1:${pairing.port}/restriction-extension`, {
        method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(4000),
        headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pairing.token},
        body: JSON.stringify({domain: record.host, token: record.token})});
      const result = await response.json();
      if (!result.ok) return {ok: false};
      const timeout = Date.now() + 4000;
      while (busy && Date.now() < timeout) await new Promise(resolve => setTimeout(resolve, 50));
      if (busy) return {ok: false};
      await sync();
    }
    if (message.action === 'return' || message.action === 'extend') {
      const current = await chrome.tabs.get(sender.tab.id);
      const destination = new URL(record.url);
      if (!siteDecision(record.host, policy, record.token).kind && current.url === sender.url &&
          ['http:', 'https:'].includes(destination.protocol) && !destination.username && !destination.password &&
          destination.hostname === record.host) {
        await chrome.tabs.update(sender.tab.id, {url: record.url}); return {ok: true};
      }
    }
    return {ok: false};
  })().then(sendResponse, () => sendResponse({ok: false}));
  return true;
});
sync();
