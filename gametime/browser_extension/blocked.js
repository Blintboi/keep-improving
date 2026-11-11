const hu = {title:'Korlátozás aktív.', desktop:'Indítsd el a Keep Improving asztali alkalmazást a megnyitás céljának kiválasztásához.', extra:n=>`Még ${n} perc`, back:'Visszatérés az oldalra',
  pause:t=>`Szünetből hátra: ${t}`, once:'Ez a hosszabbítás keretenként naponta egyszer kérhető.', error:'Most nem oldható fel. Ellenőrizd a figyelőben.',
  generic:'Ezt az oldalt aktív fókusztiltás vagy kerethez tartozó szabály korlátozza.'};
const en = {title:'Restriction active.', desktop:'Start the Keep Improving desktop application to choose why you are opening this website.', extra:n=>`Another ${n} minutes`, back:'Return to the website',
  pause:t=>`Break remaining: ${t}`, once:'This allowance is available once per budget per day.', error:'Cannot unlock now. Check the monitor.',
  generic:'A focus rule or budget action restricts this website.'};
let text = hu;
async function refresh() {
  const state = await chrome.runtime.sendMessage({action:'status'}).catch(()=>({ok:false}));
  text = state?.language === 'en' ? en : hu;
  document.documentElement.lang = text === hu ? 'hu' : 'en';
  document.getElementById('heading').textContent = text.title;
  document.getElementById('reason').textContent = state?.requires_desktop ? text.desktop : state?.names?.join(' · ') || text.generic;
  const once = document.getElementById('once');
  once.hidden = !(state?.minutes > 0);
  once.textContent = once.hidden ? '' : text.once;
  const status = document.getElementById('status');
  const remaining = Math.max(0, Math.ceil((state?.break_until || 0) - Date.now()/1000));
  if (remaining) { status.textContent = text.pause(`${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`); status.dataset.breakCountdown = 'true'; }
  else if (status.dataset.breakCountdown === 'true') { status.textContent = ''; status.dataset.breakCountdown = 'false'; }
  const extra = document.getElementById('extra'); extra.hidden = !state?.minutes;
  extra.textContent = text.extra(state?.minutes || 0);
  const back = document.getElementById('return'); back.hidden = !state?.ok || !!state.kind; back.textContent = text.back;
}
async function act(action) {
  document.getElementById('extra').disabled = true;
  const result = await chrome.runtime.sendMessage({action}).catch(()=>({ok:false}));
  if (!result?.ok) document.getElementById('status').textContent = text.error;
  document.getElementById('extra').disabled = false; await refresh();
}
document.getElementById('extra').addEventListener('click',()=>act('extend'));
document.getElementById('return').addEventListener('click',()=>act('return'));
refresh(); setInterval(refresh,2000);
