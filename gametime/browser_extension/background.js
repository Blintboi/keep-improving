importScripts('sites.js','media.js','policy.js', 'dashboard_update.js', 'local_update.js', 'continuity.js','site-choices.js');
const continuity = new BrowserContinuityWorker();
const websiteChoices = new WebsiteChoices();
let timer, busy = false, rerun = false, signature = '', leaseUntil = 0, mediaPlaying=false;
let policy = {active: false, tracking: true, allow: [], block: [], mode: 'blocklist'};
let blockedTabs = {};
let returnPages = {}, savedReturns = '';
function validRecord(record) {
  return record && typeof record.host==='string' && record.host && /^[a-f0-9]{32}$/.test(record.token || '') && typeof record.url === 'string' &&
    record.url.length <= 32768 && publicHost({url:record.url}) === record.host;
}
function blockKey(url) {
  try {
    if (/^http:\/\/127\.0\.0\.1:\d{1,5}\/browser-update#[a-f0-9]{32}$/.test(url)) return url.slice(-32);
    const value=new URL(url), page=new URL(chrome.runtime.getURL('blocked.html'));
    return value.protocol===page.protocol && value.host===page.host && value.pathname===page.pathname ? value.searchParams.get('key') || '' : null;
  } catch { return null; }
}
const restored = Promise.all([chrome.storage.session.get('blockedTabs'),chrome.storage.local.get('returnPages')]).then(([session,local]) => {
  blockedTabs=Object.fromEntries(Object.entries(session.blockedTabs || {}).filter(([,record])=>validRecord(record)));
  returnPages=Object.fromEntries(Object.entries(local.returnPages || {}).filter(([token,record])=>validRecord(record) && token===record.token));
  savedReturns=JSON.stringify(returnPages);
});
let saving=Promise.resolve();
function saveBlocked() { saving=saving.catch(()=>{}).then(persistBlocked); return saving; }
async function persistBlocked() {
  await chrome.storage.session.set({blockedTabs});
  for (const record of Object.values(blockedTabs)) {
    if (!validRecord(record)) continue;
    const old=returnPages[record.token];
    if (!old || old.url!==record.url || Date.now()-(old.savedAt || 0)>86400000)
      returnPages[record.token]={host:record.host,url:record.url,token:record.token,savedAt:Date.now()};
  }
  // Bound stale closed-window recovery records while retaining all live tabs.
  const live=new Set(Object.values(blockedTabs).map(record=>record.token));
  const stale=Object.entries(returnPages).filter(([token])=>!live.has(token)).sort((a,b)=>(b[1].savedAt||0)-(a[1].savedAt||0));
  for (const [token] of stale.slice(Math.max(0,1024-live.size))) delete returnPages[token];
  const signature=JSON.stringify(returnPages);
  if (signature!==savedReturns) { await chrome.storage.local.set({returnPages}); savedReturns=signature; }
}
async function recoverTabs() {
  const tabs=await chrome.tabs.query({}), open=new Set(tabs.map(tab=>String(tab.id)));
  for (const id of Object.keys(blockedTabs)) if (!open.has(id)) delete blockedTabs[id];
  for (const tab of tabs) {
    if (tab.incognito) { delete blockedTabs[tab.id]; continue; }
    const key=blockKey(tab.url || tab.pendingUrl);
    if (key) {
      const record=returnPages[key];
      if (validRecord(record)) blockedTabs[tab.id]={host:record.host,url:record.url,token:record.token};
      else if (blockedTabs[tab.id]?.token!==key) delete blockedTabs[tab.id];
    } else if (key===null) {
      const record=blockedTabs[tab.id];
      if (record && publicHost(tab)!==record.host && !atRedirectDestination(record,tab.url)) delete blockedTabs[tab.id];
    }
  }
  await saveBlocked(); return tabs;
}
async function restoreReleasedTabs() {
  for (const tab of await recoverTabs()) {
    const record=blockedTabs[tab.id];
    if (blockKey(tab.url)===null || !validRecord(record) || tab.incognito || siteDecision(record.host,policy,record.token).kind) continue;
    const current=await chrome.tabs.get(tab.id).catch(()=>null);
    if (current && !current.incognito && current.url===tab.url) await chrome.tabs.update(tab.id,{url:record.url});
  }
}
function grantTabs() { return Object.entries(blockedTabs).map(([id, r]) => ({tabId: Number(id), host: r.host, token: r.token})); }
function redirectGrants() { return Object.entries(blockedTabs).filter(([,r]) => r.redirect_url)
  .map(([id,r]) => ({tabId:Number(id),host:r.host,token:r.token,url:r.redirect_url})); }
function atRedirectDestination(record, url) {
  if (!record || typeof record.redirect_url !== 'string' || !url) return false;
  if (record.redirect_url==='') {
    try {
      const value=new URL(url);
      return value.protocol==='about:' && value.pathname==='newtab' ||
        ['chrome:','brave:','edge:'].includes(value.protocol) && ['newtab','new-tab-page'].includes(value.hostname);
    } catch { return false; }
  }
  try { return new URL(url).href === new URL(record.redirect_url).href; } catch { return false; }
}
function isRedirectLanding(record, url) {
  if (!atRedirectDestination(record,url)) return false;
  return !!redirectTarget({host:record.host,token:record.token,url:record.redirect_url},policy);
}

async function setPolicy(next) {
  policy = next;
  leaseUntil = Date.now() + Math.max(0, next.lease_seconds || next.remaining || 0) * 1000;
  const rules = focusRules({...next, tabGrants: grantTabs(), redirectGrants: redirectGrants()});
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
  return SiteIdentity.key(tab.url || '');
}
function trackedHost(tab) {
  const host=publicHost(tab);
  return SiteIdentity.local(host) && !(policy.local_sites || []).includes(host)?'':host;
}

async function applyPolicyTabs(tab) {
  // Include matching background media tabs; re-read before each mutation.
  for (const candidate of await chrome.tabs.query({})) {
    const recordBefore = blockedTabs[candidate.id];
    if (isRedirectLanding(recordBefore,candidate.url)) continue;
    const blockedPage = blockKey(candidate.url)!==null;
    const fromRedirect=atRedirectDestination(recordBefore,candidate.url) &&
      !!siteDecision(recordBefore.host,policy,recordBefore.token).kind;
    const host = fromRedirect ? recordBefore.host : trackedHost(candidate) || (blockedPage ? recordBefore?.host : '');
    if (!host || candidate.incognito) continue;
    let record = recordBefore;
    if (!record || record.host !== host) record = {host, url: candidate.url, token: crypto.randomUUID().replaceAll('-', '')};
    const decision = siteDecision(host, policy, record.token);
    if (!decision.kind) continue;
    if (blockedPage && decision.kind !== 'close' && decision.kind !== 'redirect') {
      if ((!blockKey(candidate.url) || candidate.url.startsWith('http://127.0.0.1:')) && validRecord(record)) {
        const current=await chrome.tabs.get(candidate.id).catch(()=>null);
        if (current && current.url===candidate.url && !current.incognito)
          await chrome.tabs.update(current.id,{url:chrome.runtime.getURL('blocked.html')+'?key='+record.token});
      }
      continue;
    }
    const current = await chrome.tabs.get(candidate.id).catch(() => null);
    if (!current || current.url !== candidate.url || current.incognito) continue;
    let target='';
    if (decision.kind === 'redirect') {
      target=redirectTarget({host:record.host,token:record.token,url:decision.redirect_url},policy);
      if (target) record.redirect_url=decision.redirect_url;
      else delete record.redirect_url;
    } else delete record.redirect_url;
    blockedTabs[current.id] = record; await saveBlocked();
    if (decision.kind === 'close') await chrome.tabs.remove(current.id);
    else if (target) {
      await setPolicy(policy);
      await chrome.tabs.update(current.id, {url: target});
      if (current.id === tab?.id) rerun = true;
    } else if (!blockedPage) await chrome.tabs.update(current.id, {url: chrome.runtime.getURL('blocked.html') + '?key=' + record.token});
  }
  await restoreReleasedTabs();
}

async function sync() {
  if (busy) { rerun = true; return; }
  busy = true;
  clearTimeout(timer);
  try {
    await restored;
    await recoverTabs();
    const {pairing, browser = 'brave'} = await chrome.storage.local.get(['pairing', 'browser']);
    await continuity.load(pairing,browser);
    if (!pairing) {
      mediaPlaying=false;
      await setPolicy({active: false, tracking: true, allow: [], block: [], mode: 'blocklist'});
      await restoreReleasedTabs();
      return;
    }
    const tab = await activeTab();
    const host = trackedHost(tab);
    const landing=tab && blockedTabs[tab.id];
    const redirectBudget=isRedirectLanding(landing,tab?.url) ? siteDecision(landing.host,policy,landing.token).redirect_key : '';
    // A full journal must still be able to reconnect and drain its durable
    // records. sample rolls back unsaved mutations before this recovery path.
    const choosing=websiteChoices.pending?.tabId===tab?.id && websiteChoices.pending?.host===host;
    try {await continuity.sample(tab,choosing?'':host,redirectBudget || '');}
    catch {continuity.error='Browser storage is full. Reconnect the desktop application.';}
    const audibleTabs=policy.tracking && policy.background_media_sites?.length ? await chrome.tabs.query({audible:true}) : [];
    const media=BackgroundMediaTabs.select(audibleTabs,policy.background_media_sites)
      .filter(item=>websiteChoices.pending?.tabId!==item.tabId)
      .map(item=>{
        const record=blockedTabs[item.tabId],tab=audibleTabs.find(tab=>tab.id===item.tabId);
        const redirect=isRedirectLanding(record,tab?.url) ? siteDecision(record.host,policy,record.token).redirect_key : '';
        return {domain:item.domain,redirect_budget:redirect || ''};
      });
    mediaPlaying=media.length>0;
    const response = await fetch(`http://127.0.0.1:${pairing.port}/activity`, {
      method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(3000),
      headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pairing.token},
      body: JSON.stringify({browser, media, restriction_version: 1, choice_version:1, local_version:1, domain: policy.tracking ? host : '', focused: !!tab, private: !!tab?.incognito,
        idle: braveNewTab(tab, browser), redirect_budget: policy.tracking ? redirectBudget || '' : ''})
    });
    if ([401,403].includes(response.status)) {continuity.model.value.snapshot=null;await continuity.save();}
    if (!response.ok) throw new Error('Connection unavailable');
    const next=await response.json();
    if(next.continuity_version===1) await continuity.exchange(pairing);
    const selected=next.continuity_version===1 && continuity.model.value.snapshot ?
      (continuity.connected ? continuity.policy || next : offlinePolicy(continuity.model.value.snapshot)) : next;
    await setPolicy(selected);
    if(host!==trackedHost(tab))rerun=true;
    if (redirectBudget && !isRedirectLanding(landing,tab?.url)) rerun = true;
    await applyPolicyTabs(tab);
    await websiteChoices.sync(tab,host,selected,pairing,browser);
    await chrome.storage.session.set({connected: next.continuity_version===1 ? continuity.connected : true, lastContact: Date.now()});
    await saving;
    await checkLocalExtensionUpdate(next.extension_version);
  } catch (error) {
    mediaPlaying=false;
    if(/storage|quota/i.test(error?.message || '')) continuity.error='Browser storage is full. Reconnect the desktop application.';
    const fallback=await continuity.offline().catch(()=>continuity.model?.value.snapshot ? offlinePolicy(continuity.model.value.snapshot) : null);
    await setPolicy(fallback || {active: false, tracking: true, allow: [], block: [], mode: 'blocklist'});
    await applyPolicyTabs(null);
    const tab=await activeTab();
    const {pairing,browser='brave'}=await chrome.storage.local.get(['pairing','browser']);
    await websiteChoices.sync(tab,trackedHost(tab),policy,pairing,browser);
    await chrome.storage.session.set({connected: false});
  } finally {
    busy = false;
    if (continuity.connected && (policy.active || (policy.restrictions || []).length) && Date.now() >= leaseUntil)
      await setPolicy({...policy, active: false, restrictions: []});
    timer = setTimeout(sync, mediaPlaying ? 1000 : websiteChoices.pending || policy.active || (policy.restrictions || []).length || continuity.model?.value.snapshot?.focus.running ? 2000 : 10000);
    if (rerun) { rerun = false; clearTimeout(timer); timer = setTimeout(sync, 0); }
  }
}
chrome.tabs.onActivated.addListener(sync);
chrome.tabs.onUpdated.addListener((id, change, tab) => { if (tab.active && (change.url || change.status === 'complete') || policy.background_media_sites?.length && ('audible' in change || 'mutedInfo' in change)) sync(); });
chrome.tabs.onRemoved.addListener(async (id,info) => {
  await restored;
  const record=blockedTabs[id]; delete blockedTabs[id];
  if (record && !info?.isWindowClosing && !Object.values(blockedTabs).some(other=>other.token===record.token)) delete returnPages[record.token];
  await saveBlocked(); sync();
});
chrome.windows.onFocusChanged.addListener(sync);
chrome.idle?.onStateChanged.addListener(sync);
chrome.storage.onChanged.addListener((changes, area) => { if (area === 'local' && (changes.pairing || changes.browser)) sync(); });
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
  if (isRedirectLanding(previous,details.url)) return;
  if (siteDecision(host, policy, previous?.token || '').kind) {
    blockedTabs[details.tabId] = {host, url: details.url,
      token: previous?.host === host ? previous.token : crypto.randomUUID().replaceAll('-', '')};
    await saveBlocked();
  }
});
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || !sender.tab ||
      blockKey(sender.url)===null) return;
  (async () => {
    await restored;
    await recoverTabs();
    const record = blockedTabs[sender.tab.id];
    const key = new URL(sender.url).searchParams.get('key');
    if (!record || key && key !== record.token)
      return {ok: false, language: policy.language || 'en', minutes: 0};
    const decision = siteDecision(record.host, policy, record.token);
    if (message.action === 'status') return {...decision, ok: true, language: policy.language || 'en'};
    if (message.action === 'extend' && decision.minutes > 0) {
      if(!continuity.connected && continuity.model?.value.snapshot) {
        if(!await continuity.extend(record.host,record.token)) return {ok:false};
        await setPolicy(offlinePolicy(continuity.model.value.snapshot));await applyPolicyTabs(null);
      } else {
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
    }
    if (message.action === 'return' || message.action === 'extend') {
      const current = await chrome.tabs.get(sender.tab.id);
      const destination = new URL(record.url);
      if (!siteDecision(record.host, policy, record.token).kind && current.url === record.url) return {ok:true};
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
chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message.action!=='choice.accept' || sender.id!==chrome.runtime.id) return;
  (async()=>{
    const {pairing}=await chrome.storage.local.get('pairing');
    const result=await websiteChoices.choose(message,sender,pairing);
    if(result.ok) sync();
    return result;
  })().then(sendResponse,()=>sendResponse({ok:false}));
  return true;
});
chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(message.action!=='continuity.control' || sender.id!==chrome.runtime.id ||
      !['/panel.html','/popup.html'].includes(new URL(sender.url || chrome.runtime.getURL('/')).pathname)) return;
  (async()=>{
    const deadline=Date.now()+4000;
    while(busy && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,25));
    if(busy || continuity.connected) return {ok:false};
    busy=true;
    try {return await continuity.control(message.command);}
    finally {busy=false;}
  })().then(sendResponse,()=>sendResponse({ok:false}));
  return true;
});
sync();

// Clear legacy toolbar labels once, including unpaired and offline starts.
chrome.action.setBadgeText({text: ''});
