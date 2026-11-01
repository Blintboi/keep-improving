// Desktop upgrades replace unpacked files while Chromium may keep the old worker.
// Reload only when the installed manifest differs, at most once per version pair.
// This reads our packaged file; no download or browser restart is involved.
(async () => {
  try {
    const loaded = chrome.runtime.getManifest().version;
    const response = await fetch(chrome.runtime.getURL('manifest.json'), {cache: 'no-store'});
    if (!response.ok) return;
    const installed = (await response.json()).version;
    if (!/^\d+(?:\.\d+){1,3}$/.test(installed) || installed === loaded) return;
    const attempt = loaded + '>' + installed;
    const previous = await chrome.storage.local.get('localUpdateAttempt');
    if (previous.localUpdateAttempt === attempt) return;
    await chrome.storage.local.set({localUpdateAttempt: attempt});
    chrome.runtime.reload();
  } catch { /* The existing blocking page remains usable when an update is unavailable. */ }
})();
