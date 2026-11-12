import {
  overviewView,
  activitiesView,
  budgetsView,
  notificationsView,
  focusView,
} from "./desktop-views.js";
import {
  api,
  el,
  button,
  card,
  field,
  note,
  t,
  setLanguage,
  language,
  icon,
  clock,
  clone,
  uid,
  savePairing,
  confirmAction,
  modal,
} from "./client.js";
import { budgetEditor, notificationEditor, settingsEditor } from "./forms.js";
import { languagePicker } from "./language-picker.js";
import { offlineView } from './offline-view.js';
import { keepScroll, scrollRoot } from './scroll-position.js';
import { OperationFeedback } from './operation-feedback.js';
const feedback=new OperationFeedback(document.querySelector('#main'));
const picker = languagePicker(document.querySelector("#language"));
const content = document.querySelector("#content"),
  status = document.querySelector("#status");
const pages = [
  ["overview", "Overview", "overview"],
  ["activities", "Activities", "activities"],
  ["budgets", "Budgets", "clock"],
  ["notifications", "Notifications", "bell"],
  ["focus", "Focus mode", "focus"],
  ["settings", "Settings", "settings"],
];
let flushActiveDraft = () => {};
let paintTimer;
let changingLanguage = false, loadGeneration = 0;
const pagePositions=new Map();let nextScroll;
function rememberPosition(){if(!editing)pagePositions.set(page,scrollRoot(content).scrollTop);}
let state,
  revision,
  page = location.hash.slice(1) || "overview",
  editing = false,
  polling = false,
  timer,
  liveAt = 0,
  currentLive,
  draftTimer,
  namespace = "";
const ctx = {
  get live() { return currentLive || state?.live; },
  get namespace() { return namespace; },
  get state() {
    return state;
  },
  get revision() {
    return revision;
  },
  edit,
  load,
  go,
  command,
  fail,
  content,
  heading,
  render,
  animate,
  newBudget,
  savedDrafts,
  subview: (title, backPage) => {
    rememberPosition();
    flushActiveDraft();
    ctx.dispose();
    ctx.dispose = () => {};
    ctx.refresh = async () => {};
    editing = true;
    heading(title);
    ctx.header();
    const back = document.querySelector("#page-back");
    back.hidden = false;
    back.onclick = () => go(backPage);
    back.setAttribute("aria-label", t("Back"));
    const root = el("div");
    keepScroll(content,()=>content.replaceChildren(root),0);
    return root;
  },
  dispose: () => {},
  refresh: async () => {},
  header: (...items) =>
    document.querySelector("#header-actions").replaceChildren(...items),
  settings: (section) => {
    rememberPosition();
    flushActiveDraft();
    page = "settings";
    location.hash = page;
    renderNav();
    settingsEditor(ctx, section);
  },
  newComputerBudget: () =>
    budgetEditor(ctx, {
      key: "computer-" + uid(),
      kind: "computer",
      name: t("Computer-use period"),
      members: [],
      enabled: true,
      days: [0, 1, 2, 3, 4, 5, 6],
      values: {
        bedtime_enabled: true,
        bedtime_warning_enabled: true,
        bedtime_warning_minute: 1435,
        bedtime_minute: 0,
        bedtime_resume_minute: 360,
        bedtime_minimize: false,
        bedtime_caps_budget: false,
      },
      plan: null,
    }),
  newNotification: () =>
    notificationEditor(ctx, {
      key: "scheduled:" + uid(),
      value: {
        id: "",
        title: "",
        text: "",
        icon: "preset:bell",
        minute: 720,
        enabled: true,
        trigger: "time",
        count: 4,
        timeout: null,
        template: "",
        action: { kind: "none" },
      },
    }),
  acceptRevision: (value) => (revision = value),
};
function fail(error) {
  status.textContent = error.message || String(error);
}
async function command(action, data = {}, reload = true) {
  return feedback.run('Working…',async()=>{
  try {
    const result = await api(action, data, revision);
    revision = result.revision;
    if (reload) await load();
    return result.result;
  } catch (error) {
    fail(error);
    throw error;
  }
  });
}
async function load(silent=false) {
  return silent || feedback.busy ? loadState() : feedback.run('Loading…',loadState);
}
async function loadState() {
  const generation = ++loadGeneration;
  const result = await api("state");
  if (generation !== loadGeneration) return state;
  state = result.result;
  revision = result.revision;
  if(state.offline) {showOffline(state);return state;}
  document.querySelector('#language').disabled=false;
  setLanguage(state.live.language);
  currentLive = state.live;
  liveAt = performance.now();
  document.querySelector("#connection").textContent = t(
    "Connected to the local application",
  );
  picker.update(language);
  status.textContent = "";
  renderNav();
  if (!editing) render();
  const quick = (await chrome.storage.session.get("panelQuickMember"))
    .panelQuickMember;
  if (
    quick?.kind === "site" &&
    typeof quick.value === "string" &&
    quick.value.length < 254
  ) {
    await chrome.storage.session.remove("panelQuickMember");
    page = "budgets";
    location.hash = page;
    renderNav();
    const matching = state.budgets.filter((b) =>
      b.members.some(
        (m) =>
          m.kind === "site" &&
          (quick.value === m.value || quick.value.endsWith("." + m.value)),
      ),
    );
    if (matching.length === 1) budgetEditor(ctx, matching[0]);
    else newBudget([quick]);
  }
  return state;
}
function renderNav() {
  document
    .querySelector("#settings-nav")
    .replaceChildren(buttonNode("settings", "Settings", "settings"));
  document
    .querySelector("#nav")
    .replaceChildren(
      ...pages
        .filter((p) => p[0] !== "settings")
        .map(([id, name, glyph]) => buttonNode(id, name, glyph)),
    );
}
function buttonNode(id, name, glyph) {
  return el(
    "button",
    { "aria-current": page === id ? "page" : "false", onclick: () => go(id) },
    icon(glyph),
    t(name),
  );
}
function go(next) {
  if(feedback.busy)return;
  rememberPosition();
  status.textContent = "";
  flushActiveDraft();
  if (!pages.some((p) => p[0] === next)) next = "overview";
  editing = false;
  page = next;
  nextScroll=pagePositions.get(next)||0;
  location.hash = next;
  renderNav();
  render();
}
function heading(name) {
  document.querySelector("#heading").textContent = t(name);
}
function render() {
  ctx.dispose();
  ctx.dispose = () => {};
  ctx.refresh = async () => {};
  clearTimeout(paintTimer);
  if (!state) return;
  if(state.offline) {showOffline(state);return;}
  const top=nextScroll;nextScroll=undefined;
  return keepScroll(content,()=>{
  heading(pages.find((p) => p[0] === page)?.[1] || "Overview");
  content.replaceChildren();
  ctx.header();
  document.querySelector("#page-back").hidden = true;
  return ({ overview, activities, budgets, notifications, focus, settings })[page]?.();
  },top);
}
function showOffline(value) {
  flushActiveDraft();ctx.dispose();ctx.dispose=()=>{};ctx.refresh=async()=>{};
  editing=false;state=value;currentLive=null;clearTimeout(paintTimer);
  setLanguage(value.language);picker.update(language);document.querySelector('#language').disabled=true;
  document.querySelector('#connection').textContent=t('Browser mode');heading('Browser mode');ctx.header();
  document.querySelector('#page-back').hidden=true;status.textContent='';renderNav();
  keepScroll(content,()=>offlineView(content,value,async action=>{await api(action);await load();}));schedule();
}
function overview() {
  return overviewView(ctx);
}
function activities() {
  return activitiesView(ctx);
}
function newBudget(members = []) {
  budgetEditor(ctx, {
    key: uid(),
    kind: "group",
    name: "",
    members: clone(members),
    seconds: 3600,
    enabled: true,
    enforce: false,
    overlay: true,
    days: [0, 1, 2, 3, 4, 5, 6],
    usage: true,
    plan: clone(state.default_plan),
    appearance: {},
  });
}
function budgets() {
  return budgetsView(ctx);
}
function notifications() {
  return notificationsView(ctx);
}
function focus() {
  return focusView(ctx);
}
function settings() {
  settingsEditor(ctx);
}
async function savedDrafts(kind, open) {
  const holder = el("div");
  content.append(holder);
  const saved = await chrome.storage.local.get(null);
  if (!holder.isConnected) return;
  for (const [key, draft] of Object.entries(saved)) {
    if (!key.startsWith(`draft:${namespace}:${kind}:`) || !draft?.value)
      continue;
    const value = draft.value;
    holder.append(
      card(
        el(
          "div",
          { class: "row spread" },
          el(
            "div",
            { class: "grow" },
            el(
              "strong",
              {},
              value.name ||
                value.value?.title ||
                t("A saved draft is available."),
            ),
            note("Your unapplied draft is saved in this browser."),
          ),
          button("Continue editing", () => open(value)),
          button(
            "Discard draft",
            async () => {
              if (await confirmAction("Discard changes?", "")) {
                await chrome.storage.local.remove(key);
                holder.replaceChildren();
                render();
              }
            },
            "quiet",
          ),
        ),
      ),
    );
  }
}

async function edit(title, key, initial, build, action) {
  status.textContent = "";
  ctx.dispose();
  ctx.dispose = () => {};
  ctx.refresh = async () => {};
  flushActiveDraft();
  editing = true;
  heading(title);
  ctx.header();
  const back = document.querySelector("#page-back");
  back.hidden = false;
  back.setAttribute("aria-label", t("Back"));
  back.onclick = () => go(page);
  const storageKey = `draft:${namespace}:${key}`,
    saved = (await chrome.storage.local.get(storageKey))[storageKey];
  let value = clone(saved?.value ?? initial),
    baseRevision = saved?.revision ?? revision;
  const form = el("form", { class: "stack editor-form" }),
    body = el("div"),
    error = el("p", { class: "error", role: "alert" });
  function changed() {
    clearTimeout(draftTimer);
    draftTimer = setTimeout(
      () =>
        chrome.storage.local.set({
          [storageKey]: { value, revision: baseRevision },
        }),
      250,
    );
  }
  flushActiveDraft = () => {
    if (draftTimer) {
      clearTimeout(draftTimer);
      draftTimer = null;
      chrome.storage.local.set({
        [storageKey]: { value, revision: baseRevision },
      });
    }
  };
  const redraw = () => {
    body.replaceChildren();
    build(body, value, redraw, changed, async (action, data) => {
      // Explicit local permissions may be saved while this form has a draft.
      // Use the draft's revision so another window's edits cannot be absorbed.
      const result = await api(action, data, baseRevision);
      revision = baseRevision = result.revision;
      changed();
      return result.result;
    });
  };
  redraw();
  form.addEventListener("input", changed);
  form.addEventListener("change", changed);
  const save = button(
    "Save changes",
    async () => {
      if (!form.reportValidity()) return;
      if(feedback.busy)return;
      await feedback.run('Saving…',async()=>{
      save.disabled = true;
      document.querySelector("#language").disabled = true;
      status.textContent = "";
      error.textContent = "";
      try {
        const result = await api(action, value, baseRevision);
        revision = result.revision;
        clearTimeout(draftTimer);
        await chrome.storage.local.remove(storageKey);
        draftTimer = null;
        flushActiveDraft = () => {};
        editing = false;
        await load();
        status.textContent = "";
      } catch (e) {
        error.textContent = e.message;
        if (e.conflict) {
          error.append(
            " ",
            button("Refresh", async () => {
              const latest = await api("state");
              state = latest.result;
              revision = latest.revision;
              const dialog = modal(
                "Settings changed in another window. Refresh before saving; your draft is kept.",
                note("Your unapplied draft is saved in this browser."),
                [
                  button(
                    "Continue editing",
                    () => {
                      baseRevision = revision;
                      changed();
                      dialog.close();
                      error.textContent = "";
                    },
                    "primary",
                  ),
                ],
              );
            }),
          );
        }
        throw e;
      } finally {
        save.disabled = false;
        document.querySelector("#language").disabled = false;
      }
      },{button:save,success:'Saved.'}).catch(()=>{});
    },
    "primary",
  );
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    save.click();
  });
  const footer = el(
    "div",
    { class: "footer" },
    note("Your unapplied draft is saved in this browser."),
    button(
      "Discard draft",
      async () => {
        if (await confirmAction("Discard changes?", "")) {
          clearTimeout(draftTimer);
          draftTimer = null;
          flushActiveDraft = () => {};
          await chrome.storage.local.remove(storageKey);
          go(page);
        }
      },
      "quiet",
    ),
    save,
  );
  content.replaceChildren(
    ...(saved ? [note("A saved draft is available.")] : []),
    form,
  );
  form.append(body, error, footer);
  form.addEventListener('keydown',event=>{
    if((event.ctrlKey || event.metaKey) && event.key.toLowerCase()==='s') {event.preventDefault();save.click();}
  });
}
function pairing() {
  editing = false;
  heading("Connect your browser");
  let code = "",
    browser = "brave";
  const error = el("p", { class: "error" });
  content.replaceChildren(
    card(
      note(
        "Copy the pairing code from Activities → Websites → Browser connection in the application.",
      ),
      field("Pairing code", "", (v) => (code = v), {
        type: "textarea",
        spellcheck: false,
        autocomplete: "off",
      }),
      field("Browser", browser, (v) => (browser = v), {
        options: ["brave", "chrome", "edge", "vivaldi", "opera"],
      }),
      el(
        "div",
        { class: "footer" },
        button(
          "Save & connect",
          async () => {
            try {
              await savePairing(code, browser);
              await boot();
            } catch (e) {
              error.textContent = e.message;
            }
          },
          "primary",
        ),
      ),
      error,
      note(
        "Only active-tab domains are measured. Private tabs, full URLs, page titles and content are not collected.",
      ),
      note(
        "The desktop application runs tracking and restrictions; keep it running in the background.",
      ),
    ),
  );
}
async function boot() {
  const stored = await chrome.storage.local.get(["pairing", "panelLanguage"]);
  setLanguage(stored.panelLanguage || "hu");
  picker.update(language);
  renderNav();
  if (stored.pairing?.token) {
    const hash = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(stored.pairing.token),
    );
    namespace = Array.from(new Uint8Array(hash))
      .slice(0, 8)
      .map((v) => v.toString(16).padStart(2, "0"))
      .join("");
    try {
      await load();
    } catch (error) {
      pairing();
      fail(error);
    }
  } else pairing();
  schedule();
}
async function poll() {
  if (polling || changingLanguage || document.hidden || !state) return;
  if(feedback.busy){schedule();return;}
  polling = true;
  try {
    const result = await api("live");
    if (changingLanguage) return;
    if(result.result.offline) {showOffline(result.result);return;}
    if(state.offline) {await load(true);return;}
    currentLive = result.result;
    liveAt = performance.now();
    if (
      (result.revision !== revision || state.live.day !== currentLive.day) &&
      !editing
    )
      await load(true);
    else if (
      !editing &&
      page === "focus" &&
      (state.live.focus.running !== currentLive.focus.running ||
        state.live.focus.phase !== currentLive.focus.phase ||
        state.live.focus.finished !== currentLive.focus.finished)
    ) {
      state.live = currentLive;
      render();
    } else if (result.revision !== revision && editing)
      status.textContent = t(
        "Settings changed in another window. Refresh before saving; your draft is kept.",
      );
    if (!editing) await ctx.refresh();
    document.querySelector("#connection").textContent = t(
      "Connected to the local application",
    );
  } catch (error) {
    document.querySelector("#connection").textContent = t("Not connected");
    fail(error);
  } finally {
    polling = false;
    schedule();
  }
}
function schedule() {
  clearTimeout(timer);
  if (!document.hidden)
    timer = setTimeout(poll, currentLive?.focus.running || state?.offline && state.focus.running ? 3000 : 10000);
}
document.addEventListener("visibilitychange", () => {
  clearTimeout(timer);
  clearTimeout(paintTimer);
  if (!document.hidden) {
    poll();
    animate();
  }
});
function animate() {
  clearTimeout(paintTimer);
  if (document.hidden) return;
  const node = document.querySelector("#focus-clock");
  if (node && currentLive) {
    node.textContent = clock(
      currentLive.focus.remaining -
        (currentLive.focus.running ? (performance.now() - liveAt) / 1000 : 0),
    );
    if (currentLive.focus.running) paintTimer = setTimeout(animate, 1000);
  }
}

document.querySelector("#language").onchange = async () => {
  const control = document.querySelector("#language");
  if (control.disabled || changingLanguage) return;
  const next = control.value, scroll = scrollRoot(content).scrollTop;
  if (!["hu", "en"].includes(next) || next === language) return;
  changingLanguage = true;
  ++loadGeneration;
  control.disabled = true;
  flushActiveDraft();
  try {
    if (state) {
      await command("settings.save", { language: next }, false);
      editing = false;
      await load();
    } else {
      setLanguage(next);
      await chrome.storage.local.set({ panelLanguage: next });
      pairing();
      renderNav();
    }
    scrollRoot(content).scrollTop = scroll;
  } catch (error) {
    fail(error);
  } finally {
    picker.update(language);
    changingLanguage = false;
    control.disabled = false;
    schedule();
  }
};
window.addEventListener("pagehide", () => flushActiveDraft());
window.addEventListener("hashchange", () => {
  if (location.hash.slice(1) !== page) go(location.hash.slice(1));
});
window.addEventListener("error", (e) => fail(e.error || e.message));
window.addEventListener("unhandledrejection", (e) => {
  e.preventDefault();
  fail(e.reason);
});
boot();
