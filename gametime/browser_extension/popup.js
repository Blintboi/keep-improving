import {
  api,
  el,
  button,
  card,
  note,
  t,
  setLanguage,
  clock,
} from "./client.js";
import { offlineView } from './offline-view.js';
import { OperationFeedback } from './operation-feedback.js';
import './sites.js';
const feedback=new OperationFeedback(document.body);
const content = document.querySelector("#popup-content"),
  status = document.querySelector("#status");
let state,
  revision,
  pending,
  refreshTimer,
  timerList,
  breakList,
  breakStarting='',
  currentDomain='';
const timerRows = new Map();
const breakRows = new Map();
function paintBreaks(live) {
  const budgets=new Map(state.budgets.map(b=>[b.key,b]));
  const matches=b=>(b?.members || []).some(m=>m.kind==='category' && m.value==='sites' || m.kind==='site' &&
    (currentDomain.replace(/^www\./,'')===m.value.replace(/^www\./,'') || currentDomain.endsWith('.'+m.value.replace(/^www\./,''))));
  const actions=Object.entries(live.break_actions || {}).filter(([key])=>budgets.has(key) && budgets.get(key).enabled!==false)
    .sort(([a],[b])=>Number(matches(budgets.get(b)))-Number(matches(budgets.get(a))) || budgets.get(a).name.localeCompare(budgets.get(b).name));
  const keys=new Set(actions.map(([key])=>key));
  actions.forEach(([key,action],index)=>{
    let row=breakRows.get(key);
    if(!row) {
      const name=el('strong',{class:'wrap'}),detail=el('div',{class:'hint'});
      const run=button('Break now',()=>command('break.start',{key,step:row.action.step}),'primary');
      row={name,detail,run,node:card(el('div',{class:'popup-break-line'},el('div',{class:'popup-break-title'},name,detail),run))};
      row.node.dataset.breakKey=key;breakRows.set(key,row);
    }
    row.action=action;row.name.textContent=budgets.get(key).name;
    const running=action.remaining>0;
    row.run.disabled=!action.step || feedback.busy;
    row.run.textContent=t(feedback.busy && breakStarting===key?'Starting…':running?'On break':'Break now');
    row.run.setAttribute('aria-label',t('Break now')+' · '+budgets.get(key).name);
    row.detail.textContent=running?t('Break remaining: {time}').replace('{time}',clock(action.remaining)):
      action.step?t('{minutes} min break').replace('{minutes}',action.minutes):
      t({inactive:'This budget is inactive.',limit:'Daily limit reached',restricted:'Break unavailable during a restriction.'}[action.unavailable] || 'This break is no longer available.');
    if(breakList.children[index]!==row.node)breakList.insertBefore(row.node,breakList.children[index] || null);
  });
  for(const [key,row] of breakRows)if(!keys.has(key)){row.node.remove();breakRows.delete(key);}
  breakList.hidden=!actions.length;
}
// The desktop tray prioritizes the foreground activity. Here all relevant
// timers are visible, ordered by their next event instead of tray position.
const priority = { save: -1, limit: 0, clock_limit: 0, quota: 1,
  break_active: 2, break: 3, warning: 4 };
function paintTimers(live) {
  const events = live.timers
    .filter((event) => event.key !== "focus" && Number.isFinite(event.seconds))
    .filter(event=>!breakRows.has(event.key) || event.event!=='break_active')
    .slice()
    .sort((a, b) => Math.max(0, a.seconds) - Math.max(0, b.seconds) ||
      (priority[a.event] ?? 5) - (priority[b.event] ?? 5) ||
      a.name.localeCompare(b.name) || a.key.localeCompare(b.key) ||
      a.scope.localeCompare(b.scope));
  const keys = new Set();
  events.forEach((event, index) => {
    const key = JSON.stringify([event.key, event.scope]);
    keys.add(key);
    let row = timerRows.get(key);
    if (!row) {
      const label = el("div", { class: "muted wrap" }),
        value = el("strong", { class: "large" }),
        detail = el("div", { class: "hint" });
      row = { node: card(label, value, detail), label, value, detail };
      row.node.dataset.timerKey = event.key;
      timerRows.set(key, row);
    }
    for (const [node, text] of [[row.label, event.name + " · " + event.label],
      [row.value, clock(event.seconds)], [row.detail, event.detail || ""]])
      if (node.textContent !== text) node.textContent = text;
    row.detail.hidden = !event.detail;
    if (timerList.children[index] !== row.node)
      timerList.insertBefore(row.node, timerList.children[index] || null);
  });
  for (const [key, row] of timerRows) {
    if (!keys.has(key)) { row.node.remove(); timerRows.delete(key); }
  }
  document.querySelector("#no-timers").hidden = events.length > 0 || breakRows.size>0;
}
function open(page = "overview") {
  chrome.tabs.create({ url: chrome.runtime.getURL("panel.html") + "#" + page });
  window.close();
}
async function command(action, data = {}) {
  if(feedback.busy)return;
  breakStarting=action==='break.start'?data.key:'';
  try {
    await feedback.run(action==='break.start'?'Starting…':'Working…',async()=>{
      status.textContent='';
      const result=await api(action, data, revision);revision=result.revision;
      await refresh(true);
    },{button:action==='break.start'?breakRows.get(data.key)?.run:null,success:action==='break.start'?'Break started.':''});
  } catch {}
  finally {breakStarting='';if(state && !state.offline && breakList?.isConnected)paintBreaks(state.live);}
}
async function update(full) {
  try {
    let result;
    if (state && !full && !state.offline) {
      result = await api("live");
      if(result.result.offline) {showOffline(result.result);return;}
      const live = result.result;
      const previous = state.live.focus;
      if (result.revision === revision && live.language === state.live.language &&
          live.focus.running === previous.running && live.focus.phase === previous.phase &&
          live.focus.finished === previous.finished) {
        state.live = live;
        document.querySelector("#clock").textContent = clock(live.focus.remaining);
        document.querySelector("#focus-rounds").textContent = t("Today’s focus rounds") + ": " + live.focus.today;
        paintBreaks(live);
        paintTimers(live);
        return;
      }
    }
    result = await api("state");
    state = result.result;
    if(state.offline) {showOffline(state);return;}
    revision = result.revision;
    setLanguage(state.live.language);
    document.querySelector("#connected").classList.add("online");
    const tab=(await chrome.tabs.query({active:true,currentWindow:true}))[0];
    currentDomain=tab && !tab.incognito ? SiteIdentity.key(tab.url || '') : '';
    breakRows.clear();breakList=el('section',{id:'quick-breaks','aria-label':t('Break now')});
    const f = state.live.focus;
    content.replaceChildren(
      breakList,
      card(
        el(
          "div",
          { class: "row spread" },
          el("strong", {}, t("Focus")),
          el(
            "span",
            { class: "pill" },
            t(f.running ? "Running" : f.finished ? "Completed" : "Ready"),
          ),
        ),
        el("div", { class: "timer", id: "clock" }, clock(f.remaining)),
        el(
          "div",
          { class: "row" },
          button(
            f.running ? "Pause" : "Start focus",
            () => command(f.running ? "focus.pause" : "focus.start"),
            "primary",
          ),
          button("Stop", () => command("focus.stop"), "quiet"),
        ),
        el("p", { class: "hint", id: "focus-rounds" }, t("Today’s focus rounds") + ": " + f.today),
      ),
    );
    timerRows.clear();
    timerList = el("div", { id: "timers" });
    content.append(timerList,
      el("p", { class: "hint", id: "no-timers" }, t("No active timers")));
    paintBreaks(state.live);
    paintTimers(state.live);
    const domain=currentDomain;
    if (domain)
      content.append(
        card(
          el("div", { class: "muted" }, t("Current website")),
          el("strong", { class: "wrap" }, domain),
          el(
            "div",
            { class: "row" },
            button(
              "Set budget",
              async () => {
                await chrome.storage.session.set({
                  panelQuickMember: { kind: "site", value: domain },
                });
                open("budgets");
              },
              "quiet",
            ),
            !(state.focus_site_rules.all || state.focus_site_rules.domains.some(
              rule => domain === rule || domain.endsWith("." + rule),
            )) && button(
              "Block during focus",
              () =>
                command("focus.save", {
                  block_sites: [
                    ...new Set([...state.focus.block_sites, domain]),
                  ],
                }),
              "quiet",
            ),
          ),
        ),
      );
    content.append(
      button("Open dashboard", () => open(), "primary full"),
      el(
        "div",
        { class: "row" },
        button("Budgets", () => open("budgets"), "quiet"),
        button("Notifications", () => open("notifications"), "quiet"),
      ),
    );
    status.textContent = "";
  } catch (e) {
    state = null;
    timerRows.clear();
    breakRows.clear();
    document.querySelector("#connected").classList.remove("online");
    content.replaceChildren(
      note(
        "The desktop application runs tracking and restrictions; keep it running in the background.",
      ),
      button("Connect your browser", () => open("settings"), "primary full"),
    );
    status.textContent = e.message;
  }
}
function showOffline(value) {
  state=value;revision='offline';timerRows.clear();breakRows.clear();status.textContent='';
  document.querySelector('#connected').classList.remove('online');
  offlineView(content,value,async action=>{await api(action);await refresh(true);});
}
async function refresh(full = false) {
  if (pending) {
    await pending;
    if (full) return refresh(true);
    return;
  }
  clearTimeout(refreshTimer);
  if (document.hidden) return;
  pending = update(full);
  try { await pending; }
  finally {
    pending = null;
    if (!document.hidden)
      refreshTimer = setTimeout(refresh,
        state && (state.offline ? state.focus.running : state.live.focus.running || state.live.timers.length ||
          Object.values(state.live.break_actions || {}).some(action=>action.remaining>0)) ? 1000 : 3000);
  }
}
document.addEventListener("visibilitychange", () => {
  clearTimeout(refreshTimer);
  if (!document.hidden) refresh();
});
refresh();
