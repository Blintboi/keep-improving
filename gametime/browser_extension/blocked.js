const hu = {title:'Elfogyott az időkereted.', extra:n=>`Még ${n} perc`, back:'Visszatérés az oldalra',
  once:'Ez a hosszabbítás keretenként naponta egyszer kérhető.', error:'Most nem oldható fel. Ellenőrizd a figyelőben.',
  generic:'Ezt az oldalt aktív fókusztiltás vagy egy elfogyott időkeret korlátozza.'};
const en = {title:'Your time budget has run out.', extra:n=>`Another ${n} minutes`, back:'Return to the website',
  once:'This allowance is available once per budget per day.', error:'Cannot unlock now. Check the monitor.',
  generic:'A focus rule or exhausted time budget restricts this website.'};
let text = hu;
async function refresh() {
  const state = await chrome.runtime.sendMessage({action:'status'}).catch(()=>({ok:false}));
  text = state?.language === 'en' ? en : hu;
  document.documentElement.lang = text === hu ? 'hu' : 'en';
  document.getElementById('heading').textContent = text.title;
  document.getElementById('reason').textContent = state?.names?.join(' · ') || text.generic;
  document.getElementById('once').textContent = text.once;
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
