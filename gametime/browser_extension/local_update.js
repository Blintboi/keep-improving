// Reuse the paired desktop connection: no extra polling, downloads or tabs.
(() => {
  let pending, retryAfter=0;
  const version=value=>typeof value==='string' && /^\d+(?:\.\d+){1,3}$/.test(value);
  const worker=typeof importScripts==='function';
  async function update(expected) {
    const moved=[];
    try {
      const loaded=chrome.runtime.getManifest().version;
      // Workers from this version manage their own update. Older pages are the
      // one-time bootstrap, and must not race an update already in the worker.
      const [major,minor,patch=0]=loaded.split('.').map(Number);
      if (!worker && (major>2 || major===2 && (minor>39 || minor===39 && patch>=23))) return false;
      if (worker && (!version(expected) || expected===loaded)) return false;
      if (Date.now()<retryAfter) return false;
      retryAfter=Date.now()+60000;
      const response=await fetch(chrome.runtime.getURL('manifest.json'),{cache:'no-store'});
      if (!response.ok) return false;
      const installed=(await response.json()).version;
      if (!version(installed) || installed===loaded || worker && installed!==expected) return false;
      const attempt=loaded+'>'+installed;
      const previous=await chrome.storage.local.get('localUpdateAttempt');
      if (previous.localUpdateAttempt===attempt) return false;
      // Reload clears session storage. Save original URLs before replacing an
      // older worker; leave pairing and all other preferences intact.
      const session=await chrome.storage.session.get('blockedTabs');
      const saved=await chrome.storage.local.get('returnPages');
      const {pairing}=await chrome.storage.local.get('pairing');
      const returnPages={...(saved.returnPages || {})};
      for (const record of Object.values(session.blockedTabs || {})) {
        if (!/^[a-f0-9]{32}$/.test(record?.token || '') || typeof record.url!=='string') continue;
        let url; try { url=new URL(record.url); } catch { continue; }
        if (['http:','https:'].includes(url.protocol) && !url.username && !url.password && (globalThis.SiteIdentity?.key(record.url) || url.hostname)===record.host)
          returnPages[record.token]={host:record.host,url:record.url,token:record.token,savedAt:Date.now()};
      }
      await chrome.storage.local.set({returnPages});
      // Chromium closes extension-page tabs on reload. Move covered tabs to an
      // inert URL in the SAME tab first; the new worker recovers by opaque token.
      const cover=new URL(chrome.runtime.getURL('blocked.html'));
      for (const tab of await chrome.tabs.query({})) {
        if (tab.incognito) continue;
        let url; try {url=new URL(tab.url);} catch {continue;}
        if (url.protocol!==cover.protocol || url.host!==cover.host || url.pathname!==cover.pathname) continue;
        const token=url.searchParams.get('key') || session.blockedTabs?.[tab.id]?.token;
        if (!/^[a-f0-9]{32}$/.test(token || '') || !returnPages[token]) continue;
        const current=await chrome.tabs.get(tab.id).catch(()=>null);
        if (!current || current.url!==tab.url || current.incognito) continue;
        if (!Number.isInteger(pairing?.port) || pairing.port<1 || pairing.port>65535) throw Error('Pairing unavailable');
        const handoff=`http://127.0.0.1:${pairing.port}/browser-update#${token}`;
        moved.push({id:tab.id,before:tab.url,handoff});
        await chrome.tabs.update(tab.id,{url:handoff});
      }
      if (typeof prepareDashboardUpgrade==='function') moved.push(...await prepareDashboardUpgrade(pairing));
      // Wait for navigation to commit: pendingUrl still leaves the old extension
      // document eligible for closure. Poll only during this bounded handoff.
      const deadline=Date.now()+3000;
      for (const tab of moved) {
        for (;;) {
          const current=await chrome.tabs.get(tab.id).catch(()=>null);
          if (!current || current.url===tab.handoff) break;
          if (Date.now()>=deadline) throw Error('Tab handoff did not finish');
          await new Promise(resolve=>setTimeout(resolve,25));
        }
      }
      await chrome.storage.local.set({localUpdateAttempt:attempt});
      try { chrome.runtime.reload(); }
      catch (error) { await chrome.storage.local.set({localUpdateAttempt:''}); throw error; }
      return true;
    } catch {
      for (const tab of moved) {
        const current=await chrome.tabs.get(tab.id).catch(()=>null);
        if (current?.url===tab.handoff) await chrome.tabs.update(tab.id,{url:tab.before}).catch(()=>{});
      }
      return false; // Keep the current worker usable; retry at most once a minute.
    }
  }
  globalThis.checkLocalExtensionUpdate=expected=> {
    if (!pending) pending=update(expected).finally(()=>{pending=null;});
    return pending;
  };
  // Pages also bootstrap workers installed before automatic background updates.
  if (!worker) return checkLocalExtensionUpdate();
})();
