const code = document.querySelector('#code'), browser = document.querySelector('#browser'), status = document.querySelector('#status');
chrome.storage.local.get(['pairing', 'browser']).then(data => {
  if (data.pairing) code.value = JSON.stringify(data.pairing);
  browser.value = data.browser || 'brave';
});
document.querySelector('#save').addEventListener('click', async () => {
  try {
    const pairing = JSON.parse(code.value.trim());
    if (!Number.isInteger(pairing.port) || pairing.port < 1024 || pairing.port > 65535 || !/^[a-f0-9]{64}$/.test(pairing.token)) throw new Error();
    await chrome.storage.local.set({pairing: {port: pairing.port, token: pairing.token}, browser: browser.value});
    status.textContent = 'Mentve. Kapcsolódás… / Saved. Connecting…';
    setTimeout(async () => {
      const state = await chrome.storage.session.get('connected');
      status.textContent = state.connected ? 'Csatlakoztatva. / Connected.' : 'A Hub nem érhető el. Ellenőrizd a kódot és indítsd el a programot. / Open the Hub and check the code.';
    }, 1500);
  } catch { status.textContent = 'Érvénytelen párosítási kód. / Invalid pairing code.'; }
});
document.querySelector('#disconnect').addEventListener('click', async () => {
  await chrome.storage.local.remove('pairing'); code.value = '';
  status.textContent = 'Leválasztva. / Disconnected.';
});
