importScripts('policy.js');
let timer, busy = false, rerun = false, signature = '', leaseUntil = 0;
let policy = {active: false, tracking: true, allow: [], block: [], mode: 'blocklist'};

async function setPolicy(next) {
  policy = next;
  leaseUntil = Date.now() + Math.max(0, next.remaining || 0) * 1000;
  const rules = focusRules(next);
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
      body: JSON.stringify({browser, domain: policy.tracking ? host : '', focused: !!tab, private: !!tab?.incognito})
    });
    if (!response.ok) throw new Error('Connection unavailable');
    await setPolicy(await response.json());
    await chrome.action.setBadgeText({text: policy.active ? 'FOCUS' : ''});
    // Recheck the tab after the response: never redirect a newly selected page
    // using a response describing the previous tab.
    const current = await activeTab();
    const currentHost = publicHost(current);
    if (currentHost && siteBlocked(currentHost, policy))
      await chrome.tabs.update(current.id, {url: chrome.runtime.getURL('blocked.html')});
    await chrome.storage.session.set({connected: true, lastContact: Date.now()});
  } catch {
    // A closed monitor, expired pairing or network error must release browser restrictions.
    await setPolicy({active: false, tracking: true, allow: [], block: [], mode: 'blocklist'});
    await chrome.action.setBadgeText({text: '!'});
    await chrome.storage.session.set({connected: false});
  } finally {
    busy = false;
    if (policy.active && Date.now() >= leaseUntil)
      await setPolicy({...policy, active: false});
    timer = setTimeout(sync, policy.active ? 2000 : 10000);
    if (rerun) { rerun = false; clearTimeout(timer); timer = setTimeout(sync, 0); }
  }
}
chrome.tabs.onActivated.addListener(sync);
chrome.tabs.onUpdated.addListener((id, change, tab) => { if (tab.active && (change.url || change.status === 'complete')) sync(); });
chrome.tabs.onRemoved.addListener(sync);
chrome.windows.onFocusChanged.addListener(sync);
chrome.storage.onChanged.addListener((changes, area) => { if (area === 'local') sync(); });
chrome.alarms.onAlarm.addListener(sync);
chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onInstalled.addListener(() => { chrome.alarms.create('connection', {periodInMinutes: 0.5}); sync(); });
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage());
sync();
