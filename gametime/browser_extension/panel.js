import { addActivity, gameActions } from "./library-ui.js";
import {
  api,
  el,
  button,
  card,
  check,
  field,
  note,
  t,
  setLanguage,
  language,
  icon,
  clock,
  duration,
  clone,
  uid,
  timeText,
  savePairing,
  confirmAction,
  modal,
} from "./client.js";
import {
  budgetEditor,
  notificationEditor,
  focusEditor,
  settingsEditor,
  appearanceEditor,
  pickMember,
  pickApplication,
} from "./forms.js";
const content = document.querySelector("#content"),
  status = document.querySelector("#status");
const pages = [
  ["overview", "Overview", "overview"],
  ["activities", "Activities", "activities"],
  ["budgets", "Time budgets", "clock"],
  ["notifications", "Notifications", "bell"],
  ["focus", "Focus mode", "focus"],
  ["settings", "Settings", "settings"],
];
let flushActiveDraft = () => {};
let paintTimer;
let state,
  revision,
  page = location.hash.slice(1) || "overview",
  editing = false,
  polling = false,
  timer,
  liveAt = 0,
  currentLive,
  draftTimer,
  namespace = "",
  range = "7",
  category = "all",
  scope = "all",
  activityTab = "game",
  focusTab = "site";
const ctx = {
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
  acceptRevision: (value) => (revision = value),
};
function fail(error) {
  status.textContent = error.message || String(error);
}
async function command(action, data = {}, reload = true) {
  try {
    const result = await api(action, data, revision);
    revision = result.revision;
    if (reload) await load();
    return result.result;
  } catch (error) {
    fail(error);
    throw error;
  }
}
async function load() {
  const result = await api("state");
  state = result.result;
  revision = result.revision;
  setLanguage(state.live.language);
  currentLive = state.live;
  liveAt = performance.now();
  document.querySelector("#connection").textContent = t(
    "Connected to the local application",
  );
  document.querySelector("#language").textContent =
    language === "hu" ? "English" : "Magyar";
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
    .querySelector("#nav")
    .replaceChildren(
      ...pages.map(([id, name, glyph]) => buttonNode(id, name, glyph)),
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
  flushActiveDraft();
  if (!pages.some((p) => p[0] === next)) next = "overview";
  editing = false;
  page = next;
  location.hash = next;
  renderNav();
  render();
}
function heading(name) {
  document.querySelector("#heading").textContent = t(name);
}
function render() {
  clearTimeout(paintTimer);
  if (!state) return;
  heading(pages.find((p) => p[0] === page)?.[1] || "Overview");
  content.replaceChildren();
  ({ overview, activities, budgets, notifications, focus, settings })[page]?.();
}
function empty(message) {
  return el("div", { class: "empty" }, t(message));
}
function tabs(items, value, change) {
  return el(
    "div",
    { class: "tabs" },
    items.map(([id, name]) =>
      button(name, () => change(id), id === value ? "selected" : ""),
    ),
  );
}
function listItem(title, subtitle, actions = [], glyph) {
  return el(
    "article",
    { class: "item" },
    glyph ? el("div", { class: "badge-icon" }, icon(glyph)) : null,
    el(
      "div",
      { class: "grow" },
      el("h3", {}, title),
      subtitle ? el("p", { class: "muted" }, subtitle) : null,
    ),
    el("div", { class: "item-actions" }, actions),
  );
}
function metrics(values) {
  return el(
    "div",
    { class: "metrics" },
    values.map(([label, value]) =>
      el(
        "div",
        { class: "metric" },
        el("span", { class: "muted" }, t(label)),
        el("strong", {}, value),
      ),
    ),
  );
}
async function overview() {
  const resultBox = el("div"),
    filter = el("div", { class: "row toolbar" });
  let end = state.live.day,
    start = dateBefore(end, range === "custom" ? 7 : Number(range));
  const custom = el(
    "div",
    { class: "row", hidden: range !== "custom" },
    field("Start", start, (v) => (start = v), { type: "date" }),
    field("End", end, (v) => (end = v), { type: "date" }),
    button("Show", show),
  );
  filter.append(
    field(
      "Time",
      range,
      (v) => {
        range = v;
        overviewRender();
      },
      {
        options: [
          ["0", "Today"],
          ["7", "Last 7 days"],
          ["30", "Last 30 days"],
          ["custom", "Custom period"],
        ],
      },
    ),
    field(
      "Activity",
      category,
      (v) => {
        category = v;
        show();
      },
      {
        options: [
          ["all", "All activity"],
          ["games", "Games"],
          ["apps", "Applications"],
          ["sites", "Websites"],
        ],
      },
    ),
    field(
      "Linked computers",
      scope,
      (v) => {
        scope = v;
        show();
      },
      {
        options: [
          ["all", "All computers"],
          ["local", "This computer"],
          ...state.sync.computers.map(([id, name]) => [id, name]),
        ],
      },
    ),
  );
  content.append(filter, custom, resultBox);
  await show();
  function overviewRender() {
    content.replaceChildren();
    overview();
  }
  async function show() {
    try {
      const data = (await api("statistics", { start, end, category, scope }))
        .result;
      if (page !== "overview" || editing) return;
      resultBox.replaceChildren(
        metrics([
          ["Total time", duration(data.total)],
          ["Daily average", duration(data.average)],
          ["Most used", data.games[0]?.[1] || "—"],
        ]),
      );
      const bars = el("div", { class: "chart" }),
        entries = Object.entries(data.days),
        maximum = Math.max(1, ...entries.map((e) => e[1]));
      for (const [day, seconds] of entries) {
        const b = el("button", {
          class: "bar",
          title: day + " · " + duration(seconds),
          "aria-label": day + " · " + duration(seconds),
          style: { height: Math.max(2, (seconds / maximum) * 100) + "%" },
          onclick: () => showRows(data.by_day[day] || [], day),
        });
        bars.append(b);
      }
      const table = el("div");
      resultBox.append(
        card(
          el(
            "div",
            { class: "row spread" },
            el("h2", {}, t("Daily activity")),
            button(
              "Show",
              () => showRows(data.games, t("All activity")),
              "quiet",
            ),
          ),
          bars,
          el(
            "div",
            { class: "chart-labels" },
            el("span", {}, start),
            el("span", {}, end),
          ),
        ),
        table,
      );
      showRows(data.games, t("All activity"));
      function showRows(rows, title) {
        table.replaceChildren(
          card(
            el("h2", {}, title),
            rows.length
              ? el(
                  "div",
                  { class: "list" },
                  rows.map((row) =>
                    el(
                      "div",
                      { class: "item" },
                      el(
                        "div",
                        { class: "grow" },
                        row[1],
                        el(
                          "div",
                          { class: "progress" },
                          el("span", {
                            style: {
                              width:
                                Math.min(
                                  100,
                                  (row[3] / Math.max(1, data.total)) * 100,
                                ) + "%",
                            },
                          }),
                        ),
                      ),
                      el("strong", {}, duration(row[3])),
                    ),
                  ),
                )
              : empty("No activity yet"),
          ),
        );
      }
    } catch (error) {
      fail(error);
    }
  }
}
function dateBefore(date, days) {
  const d = new Date(date + "T12:00:00");
  d.setDate(d.getDate() - Math.max(0, days - 1));
  return d.toISOString().slice(0, 10);
}
function activities() {
  let search = "",
    showHidden = false,
    showExcluded = false;
  const rows = el("div", { class: "list" }),
    toolbar = el(
      "div",
      { class: "row toolbar" },
      el("input", {
        type: "search",
        class: "search",
        placeholder: t("Search…"),
        "aria-label": t("Search…"),
        oninput: (e) => {
          search = e.target.value.toLowerCase();
          fill();
        },
      }),
      check("Show excluded", false, (v) => {
        showExcluded = v;
        fill();
      }),
    );
  if (activityTab === "game")
    toolbar.append(
      check("Show hidden games", false, (v) => {
        showHidden = v;
        fill();
      }),
    );
  toolbar.append(
    button("Add", () => addActivity(ctx, activityTab)),
    ...(activityTab === "game"
      ? [button("Refresh data", () => command("library.refresh"))]
      : []),
  );
  content.append(
    tabs(
      [
        ["game", "Games"],
        ["app", "Applications"],
        ["site", "Websites"],
      ],
      activityTab,
      (v) => {
        activityTab = v;
        render();
      },
    ),
    toolbar,
    rows,
  );
  fill();
  function fill() {
    const values =
      activityTab === "game"
        ? state.games
            .filter(
              (g) => (showHidden || !g.hidden) && (showExcluded || g.enabled),
            )
            .map((g) => ({
              member: { kind: "game", value: g.id },
              name: g.name,
              game: g,
              excluded: !g.enabled,
            }))
        : state.activities.filter(
            (a) =>
              a.member.kind === activityTab && (showExcluded || !a.excluded),
          );
    rows.replaceChildren(
      ...values
        .filter((v) =>
          (v.name + " " + v.member.value).toLowerCase().includes(search),
        )
        .map((v) => {
          const actions = [
            button("Set budget", () => newBudget([v.member]), "quiet"),
            button("Countdown", () => appearanceEditor(ctx, v.member), "quiet"),
          ];
          if (v.game) {
            actions.push(
              button("More…", () => gameActions(ctx, v.game), "quiet"),
            );
            if (v.game.installed)
              actions.unshift(
                button(
                  "Play",
                  () => command("game.launch", { id: v.game.id }),
                  "primary",
                ),
              );
            actions.push(
              button(
                v.game.hidden ? "Show in library" : "Hide",
                () =>
                  command("activity.change", {
                    kind: "game",
                    key: v.game.id,
                    hidden: !v.game.hidden,
                  }),
                "quiet",
              ),
            );
          }
          if (v.member.kind !== "site")
            actions.push(
              button(
                v.excluded ? "Restore" : "Exclude",
                async () => {
                  if (
                    !v.excluded &&
                    !(await confirmAction("Exclude", "History is preserved."))
                  )
                    return;
                  await command("activity.change", {
                    kind: v.member.kind,
                    key: v.game?.id || v.member.value,
                    enabled: v.excluded,
                  });
                },
                "quiet",
              ),
            );
          return listItem(
            v.name,
            [
              v.game?.source,
              v.excluded ? t("Excluded") : "",
              v.game?.hidden ? t("Hidden") : "",
            ]
              .filter(Boolean)
              .join(" · "),
            actions,
            v.member.kind === "game"
              ? "activities"
              : v.member.kind === "site"
                ? "overview"
                : "settings",
          );
        }),
    );
    if (!rows.childElementCount) rows.append(empty("No matches."));
  }
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
  savedDrafts("budget", (value) => budgetEditor(ctx, value));
  content.append(
    el(
      "div",
      { class: "row toolbar" },
      el("div", { class: "grow" }, note("History is preserved.")),
      button("Add computer-use period", () =>
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
      ),
      button("Add new", () => newBudget(), "primary"),
    ),
  );
  const rows = el("div", { class: "list" });
  for (const b of state.budgets)
    rows.append(
      listItem(
        b.name,
        (b.kind === "computer"
          ? timeText(b.values.bedtime_minute) +
            " → " +
            timeText(b.values.bedtime_resume_minute)
          : b.usage
            ? duration(b.seconds)
            : t("At a time of day")) +
          " · " +
          t(b.enabled ? "Enabled" : "Paused"),
        [
          button("Edit", () => budgetEditor(ctx, b)),
          button(
            "Delete",
            async () => {
              if (await confirmAction("Delete this item?"))
                await command("budget.delete", { key: b.key });
            },
            "quiet danger",
          ),
        ],
        b.kind === "computer" ? "moon" : "clock",
      ),
    );
  content.append(
    rows.childElementCount ? rows : card(empty("No time budgets yet.")),
  );
}
function notifications() {
  savedDrafts("notification", (value) => notificationEditor(ctx, value));
  content.append(
    el(
      "div",
      { class: "row toolbar" },
      el("div", { class: "grow" }),
      button("Presets", () => {
        const box = el("div", { class: "list" });
        for (const p of state.presets)
          box.append(
            button(
              state.triggers.find((t) => t.id === p.value.trigger)?.name ||
                p.value.trigger,
              () => {
                document.querySelector("#dialog").close();
                notificationEditor(ctx, p);
              },
            ),
          );
        modal("Restore preset", box);
      }),
      button(
        "Add new",
        () =>
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
        "primary",
      ),
    ),
  );
  const rows = el("div", { class: "list" });
  for (const n of state.notifications)
    rows.append(
      listItem(
        n.title,
        n.message,
        [
          button("Edit", () => notificationEditor(ctx, n)),
          button(
            "Delete",
            async () => {
              if (await confirmAction("Delete this item?"))
                await command("notification.delete", { key: n.key });
            },
            "quiet danger",
          ),
        ],
        n.value.icon.startsWith("preset:") ? n.value.icon.slice(7) : "bell",
      ),
    );
  content.append(
    rows.childElementCount ? rows : card(empty("No notifications yet.")),
  );
}
function focus() {
  const f = state.live.focus,
    clockNode = el(
      "div",
      { class: "timer", id: "focus-clock" },
      clock(f.remaining),
    );
  content.append(
    card(
      el(
        "div",
        { class: "row spread" },
        el("h2", {}, t("Focus")),
        button("Timer settings", () => focusEditor(ctx), "quiet"),
      ),
      el(
        "div",
        { class: "row spread" },
        clockNode,
        el(
          "div",
          { class: "row" },
          button(
            f.running
              ? "Pause"
              : f.finished
                ? "New focus session"
                : "Start focus",
            () => command(f.running ? "focus.pause" : "focus.start"),
            f.running ? "" : "primary",
          ),
          button("Stop", () => command("focus.stop"), "quiet"),
        ),
      ),
      el(
        "div",
        { class: "row spread" },
        el(
          "p",
          { class: "muted", id: "focus-phase" },
          t(
            {
              focus: "Focus",
              short_break: "Short break",
              long_break: "Long break",
            }[f.phase],
          ),
        ),
        el(
          "p",
          { class: "muted" },
          t("Completed rounds in total") + ": " + f.rounds,
        ),
      ),
      note(
        "0-minute breaks are skipped. Zero rounds means one focus session without a break or repetition.",
      ),
    ),
  );
  const group = card(
    el("h2", {}, t("What should stay out of your focus session?")),
    tabs(
      [
        ["site", "Websites"],
        ["app", "Applications"],
        ["group", "Groups"],
      ],
      focusTab,
      (v) => {
        focusTab = v;
        render();
      },
    ),
  );
  const controls = el("div", { class: "row toolbar" });
  if (focusTab === "site") {
    let site = "";
    controls.append(
      field("Domain or website URL", "", (v) => (site = v)),
      button(
        "Add",
        () =>
          command("focus.save", {
            block_sites: [...state.focus.block_sites, site],
          }),
        "primary",
      ),
    );
  } else if (focusTab === "app")
    controls.append(
      button("Choose application", () =>
        pickApplication(ctx, (path) =>
          command("focus.save", {
            block_apps: [...state.focus.block_apps, path],
          }),
        ),
      ),
    );
  else
    controls.append(
      button("Add group", () => {
        const list = el("div", { class: "list" });
        for (const g of state.groups.filter(
          (g) => !state.focus.block_groups.includes(g.id),
        ))
          list.append(
            button(g.name, async () => {
              document.querySelector("#dialog").close();
              await command("focus.save", {
                block_groups: [...state.focus.block_groups, g.id],
              });
            }),
          );
        modal(
          "Add group",
          list.childElementCount ? list : empty("No matches."),
        );
      }),
    );
  group.append(controls);
  const rows = state.members[focusTab] || [];
  for (const [key, name, detail, direct, groups] of rows) {
    const actions = direct
      ? [
          button(
            "Remove",
            () => {
              const field = {
                site: "block_sites",
                app: "block_apps",
                group: "block_groups",
              }[focusTab];
              command("focus.save", {
                [field]: state.focus[field].filter((v) => v !== key),
              });
            },
            "quiet",
          ),
        ]
      : [];
    const item = listItem(
      name,
      groups.length ? t("From groups") + ": " + groups.join(", ") : "",
      actions,
    );
    item.title = detail;
    group.append(item);
  }
  if (!rows.length) group.append(empty("No matches."));
  if (focusTab !== "group")
    group.append(
      note("Change inherited members in Time budgets, or remove their group."),
    );
  content.append(group);
  animate();
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
  flushActiveDraft();
  editing = true;
  heading(title);
  const storageKey = `draft:${namespace}:${key}`,
    saved = (await chrome.storage.local.get(storageKey))[storageKey];
  let value = clone(saved?.value ?? initial),
    baseRevision = saved?.revision ?? revision;
  const form = el("form", { class: "stack" }),
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
    build(body, value, redraw, changed);
  };
  redraw();
  form.addEventListener("input", changed);
  form.addEventListener("change", changed);
  const save = button(
    "Save changes",
    async () => {
      if (!form.reportValidity()) return;
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
        status.textContent = t("Saved.");
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
      } finally {
        save.disabled = false;
        document.querySelector("#language").disabled = false;
      }
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
    el(
      "div",
      { class: "toolbar" },
      button("Back", () => go(page), "quiet"),
    ),
    ...(saved ? [note("A saved draft is available.")] : []),
    form,
  );
  form.append(body, error, footer);
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
  if (polling || document.hidden || !state) return;
  polling = true;
  try {
    const result = await api("live");
    currentLive = result.result;
    liveAt = performance.now();
    if (
      (result.revision !== revision || state.live.day !== currentLive.day) &&
      !editing
    )
      await load();
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
    timer = setTimeout(poll, currentLive?.focus.running ? 3000 : 10000);
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
document.querySelector("#refresh").onclick = () => load().catch(fail);
document.querySelector("#language").onclick = async () => {
  if (document.querySelector("#language").disabled) return;
  editing = false;
  const next = language === "hu" ? "en" : "hu";
  if (state) await command("settings.save", { language: next });
  else {
    setLanguage(next);
    await chrome.storage.local.set({ panelLanguage: next });
    pairing();
    renderNav();
  }
};
window.addEventListener("pagehide", () => flushActiveDraft());
window.addEventListener("hashchange", () => {
  if (location.hash.slice(1) !== page) go(location.hash.slice(1));
});
window.addEventListener("unhandledrejection", (e) => {
  e.preventDefault();
  fail(e.reason);
});
boot();
