import {
  api,
  el,
  button,
  card,
  check,
  field,
  note,
  helpNote,
  t,
  icon,
  clock,
  duration,
  timeText,
  modal,
  confirmAction,
} from "./client.js";
import {
  budgetEditor,
  notificationEditor,
  focusEditor,
  appearanceEditor,
  pickApplication,
} from "./forms.js";
import { addActivity, gameActions } from "./library-ui.js";
import { syncPanel } from "./sync-ui.js";
import { chartGroups, detailRows, sessionText } from "./statistics-model.js";
import { activityImage } from "./activity-images.js";
import { keepScroll } from "./scroll-position.js";

const fullTime = (s) => {
  s = Math.max(0, Math.floor(s || 0));
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60]
    .map((n) => String(n).padStart(2, "0"))
    .join(":");
};
const shortTime = (s) => {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60);
  const text =
    s < 60
      ? t("{seconds} sec")
      : h
        ? m
          ? t("{hours} h {minutes} min")
          : t("{hours} h")
        : t("{minutes} min");
  return text
    .replace("{seconds}", s)
    .replace("{hours}", h)
    .replace("{minutes}", m);
};
const tabs = (items, current, choose, kind = "segments") =>
  el(
    "div",
    { class: kind },
    items.map(([id, name]) =>
      button(name, () => choose(id), id === current ? "selected" : ""),
    ),
  );
export function iconButton(name, glyph, action, extra = "") {
  const b = button("", action, "quiet icon-button " + extra);
  b.append(icon(glyph));
  b.title = t(name);
  b.setAttribute("aria-label", t(name));
  return b;
}
function daysText(days) {
  const active = days ?? [0, 1, 2, 3, 4, 5, 6];
  return active.length === 7
    ? t("Every day")
    : active.length
      ? active.map((d) => t(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d])).join(", ")
      : t("No active days");
}
function memberName(ctx, m) {
  return m.kind === "category"
    ? t(
        { games: "All games", apps: "All applications", sites: "All websites" }[
          m.value
        ],
      )
    : m.kind === "game"
      ? ctx.state.games.find((g) => g.id === m.value)?.name || m.value
      : m.value.split(/[\\/]/).at(-1);
}
const help = (title, text) => modal(title, note(text));

let period = "7",
  category = "all",
  scope = "all";
const statisticsSnapshots = new Map(), artworkSnapshots = new Map();
function remember(cache, key, value, limit) {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > limit) cache.delete(cache.keys().next().value);
}
export async function overviewView(ctx) {
  ctx.heading("Statistics");
  ctx.content.append(note("See where your time goes."));
  ctx.header(
    button("Computers & sync", () => syncPanel(ctx), "quiet"),
    button(
      "What is measured?",
      () =>
        help(
          "What is measured?",
          "Website time is part of browser time and is counted only once.",
        ),
      "quiet",
    ),
  );
  const content = ctx.content,
    results = el("div");
  let chartMetric = "time";
  try { if (localStorage.getItem("overview.chartMetric") === "sessions") chartMetric = "sessions"; } catch {}
  let end = ctx.state.live.day,
    start = end,
    query = 0,
    selectedDay = "",
    search = "",
    detailScope = "all",
    detailSort = "time_desc",
    combine = false,
    rendered = "";
  const subtract = (d, n) => {
    const date = new Date(d + "T12:00:00");
    date.setDate(date.getDate() - n);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  };
  function range() {
    start = end = ctx.state.live.day;
    if (period === "yesterday") start = end = subtract(end, 1);
    else if (period === "month") start = end.slice(0, 8) + "01";
    else if (period !== "0")
      start = subtract(end, period === "custom" ? 6 : Number(period) - 1);
  }
  range();
  const custom = el(
    "div",
    { class: "row custom-period", hidden: period !== "custom" },
    field("From", start, (v) => (start = v), { type: "date" }),
    field("To", end, (v) => (end = v), { type: "date" }),
    button("Show period", () => show()),
  );
  const filter = card(
    el(
      "div",
      { class: "filter-grid" },
      field(
        "Show activity",
        category + (chartMetric === "sessions" ? ":sessions" : ""),
        (v) => {
          const [next, measure] = v.split(":");
          category = next; chartMetric = measure === "sessions" ? "sessions" : "time";
          try { localStorage.setItem("overview.chartMetric",chartMetric); } catch {}
          const saved = statisticsSnapshots.get(cacheKey());
          if (saved) { paint(saved); return; }
          show();
        },
        {
          options: ["time", "sessions"].flatMap(measure => [
            ["all", "Everything"],
            ["games", "Games"],
            ["apps", "Applications"],
            ["websites", "Websites"],
          ].map(([id, name]) => [id + (measure === "sessions" ? ":sessions" : ""), t(name) + " · " + t(measure === "sessions" ? "Sessions" : "Time")])),
        },
      ),
      field(
        "Period",
        period,
        (v) => {
          period = v;
          range();
          custom.hidden = period !== "custom";
          const dates = custom.querySelectorAll("input");
          dates[0].value = start;
          dates[1].value = end;
          selectedDay = "";
          show();
        },
        {
          options: [
            ["0", "Today"],
            ["yesterday", "Yesterday"],
            ["7", "Last 7 days"],
            ["30", "Last 30 days"],
            ["month", "This month"],
            ["custom", "Custom dates…"],
          ],
        },
      ),
      field(
        "Computer",
        scope,
        (v) => {
          scope = v;
          show();
        },
        {
          options: [
            ["local", "This computer"],
            ["all", "All computers"],
            ...ctx.state.sync.computers.map(([id, name]) => [id, name]),
          ],
        },
      ),
    ),
    custom,
    note("Website time is part of browser time and is counted only once."),
  );
  filter.classList.add("statistics-filters");
  content.append(filter, results);
  const cacheKey = () => JSON.stringify([ctx.namespace, start, end, category, scope]);
  const cached = statisticsSnapshots.get(cacheKey());
  if (cached) paint(cached);
  ctx.refresh = async () => {
    if (results.isConnected && !results.contains(document.activeElement)) await show();
  };
  await show();
  async function show() {
    const request = ++query;
    const key = cacheKey();
    try {
      const data = (await api("statistics", { start, end, category, scope }))
        .result;
      if (request !== query || !results.isConnected) return;
      remember(statisticsSnapshots, key, data, 3);
      paint(data);
    } catch (e) {
      ctx.fail(e);
    }
  }
  function paint(data) {
      return keepScroll(results,()=>paintContents(data));
  }
  function paintContents(data) {
      const signature = JSON.stringify([start, end, category, scope, chartMetric, data]);
      if (signature === rendered) return;
      rendered = signature;
      const colors = data.colors || {},
        most = data.games[0];
      const metric = (label, value, extra) =>
        el(
          "div",
          { class: "metric" },
          el("div", { class: "muted" }, t(label)),
          el("strong", {}, value),
          extra,
        );
      const top = metric(
        "Most used",
        most?.[1] || "—",
        most
          ? el(
              "div",
              { class: "hint" },
              shortTime(most[3]) +
                " · " +
                ((100 * most[3]) / Math.max(1, data.total)).toFixed(1) +
                "%",
            )
          : null,
      );
      top.classList.add("top-metric");
      if (most) top.querySelector("strong").style.color = colors[most[0]];
      const sessionRows = detailRows(data, "", "all", false);
      results.replaceChildren(
        el(
          "div",
          { class: "metrics session-metrics" },
          metric("Total time", shortTime(data.total)),
          metric("Daily average", shortTime(data.average), note(t("Average: {days} days · since {date}").replace("{days}", data.average_days).replace("{date}", data.started))),
          metric("Total sessions", sessionText(sessionRows.reduce((n,r)=>n+r.sessions,0),sessionRows.some(r=>r.partial))),
          top,
        ),
      );
      results.append(note("A session is continuous foreground use, counted on its starting day."));
      const sessionMode = chartMetric === "sessions";
      const groupedDays = new Map(Object.keys(data.days).map(day => [day,chartGroups(data,day,chartMetric)]));
      const dailyValues = [...groupedDays.values()].map(groups=>groups.reduce((n,g)=>n+g.value,0));
      const maximum = Math.max(sessionMode ? 1 : 60,...dailyValues);
      const unit = sessionMode ? (maximum<=10?2:maximum<=100?10:maximum<=1000?100:1000) : 1800;
      const ceiling = Math.ceil(maximum/unit)*unit;
      const chart = card(
        el("h2", {}, t(sessionMode ? "Sessions by day" : "How your time changed")),
        note(start + " – " + end),
      );
      const plot = el(
        "div",
        { class: "daily-chart" },
        el(
          "div",
          { class: "chart-axis" },
          [ceiling, ceiling / 2, 0].map((n) => el("span", {}, sessionMode ? String(n) : shortTime(n))),
        ),
      );
      const columns = el("div", { class: "chart-columns" });
      const multi = Object.keys(data.computer_names).length > 1;
      const itemName = (id, name) => id === "activity:browser:other" ? t(name) : name;
      // Refresh names/aliases from the same snapshot as the chart.
      const computerSelect = filter.querySelectorAll("select")[2];
      computerSelect.replaceChildren(
        el("option", { value: "all" }, t(multi ? "All linked computers" : "This computer")),
        ...Object.entries(data.computer_names).map(([id, name]) => el("option", { value: id }, name)),
      );
      computerSelect.value = scope;
      computerSelect.disabled = !multi;
      for (const [day, total] of Object.entries(data.days)) {
        const groups = groupedDays.get(day);
        const daySessions = sessionText(groups.reduce((n,g)=>n+g.sessions,0),groups.some(g=>g.partial));
        const value = groups.reduce((n,g)=>n+g.value,0);
        const b = button(
          "",
          () => {
            selectedDay = selectedDay === day ? "" : day;
            showRows();
          },
          "day-column",
        );
        b.title = day + " · " + shortTime(total) + " · " + t("Sessions") + ": " + daySessions;
        b.setAttribute("aria-label", b.title);
        const stack = el(
          "div",
          {
            class: "chart-stack",
            style: { height: Math.max(1, (value / ceiling) * 100) + "%" },
            "data-value": String(value),
          },
          el("span", { class: "bar-total" }, sessionMode ? daySessions : shortTime(total)),
        );
        const visibleGroups=groups.filter(g=>g.value>0);
        stack.style.gap = visibleGroups.length > 1 ? "3px" : "0";
        for (const group of visibleGroups) {
          const block = el("span", {
            class: "computer-stack" + (multi ? " marked" : ""),
            "data-computer": group.computer,
            title: data.computer_names[group.computer] + " · " + shortTime(group.total) + " · " + t("Sessions") + ": " + sessionText(group.sessions,group.partial),
            style: { flex: String(group.value) },
          });
          block.style.setProperty("--computer-color", data.computer_colors[group.computer]);
          for (const row of group.activities.filter(r=>r.value>0)) block.append(
            el("span", {
              class: "chart-segment",
              title: data.computer_names[group.computer] + " · " + itemName(row.id, row.name) + " · " + shortTime(row.seconds) + " · " + t("Sessions") + ": " + sessionText(row.sessions,row.partial),
              style: {
                flex: String(row.value),
                background: colors[row.id] || "#7de5bf",
              },
            }),
          );
          stack.append(block);
        }
        b.append(stack, el("span", { class: "day-label" }, day.slice(5)));
        columns.append(b);
      }
      plot.append(columns);
      chart.append(
        plot,
        multi ? el("div", { class: "row computer-legend", "aria-label": t("Computer colors") },
          ...Object.entries(data.computer_names).filter(([id]) => scope === "all" || scope === id).map(([id, name]) =>
            el("span", {}, el("span", { class: "series-dot", style: { background: data.computer_colors[id] } }), name))) : null,
        helpNote(multi ? "The side color identifies the computer. Spaces separate computers; activity colors match the list below." : "Each color is one activity. Click a day to see its details.",
          sessionMode ? "Column height shows session counts. Hover over a block for details." : "Column height shows recorded time. Hover over a block for details."),
      );
      const detail = card(),
        rowsBox = el("div", { class: "table-wrap statistics-details" }),
        dayField = field(
          "",
          selectedDay,
          (v) => {
            selectedDay = v;
            showRows();
          },
          {
            options: [
              ["", "Whole period"],
              ...Object.keys(data.days).map((d) => [d, d]),
            ],
          },
        ),
        searchBox = el("input", {
          type: "search",
          class: "search",
          placeholder: t("Search the list…"),
          value: search,
          oninput: (e) => {
            search = e.target.value;
            showRows();
          },
        });
      detail.append(
        el(
          "div",
          { class: "row spread breakdown-heading" },
          el("h2", {}, t("Where did the time go?")),
          el("div", { class: "row" }, dayField, searchBox),
        ),
        rowsBox,
      );
      detail.insertBefore(el("div", { class: "row detail-filters" },
        field("Computer", detailScope, (v) => { detailScope = v; showRows(); }, {
          options: [["all", "All linked computers"], ...Object.entries(data.computer_names)],
        }),
        check("Combine matching names", combine, (v) => { combine = v; showRows(); }),
        field("Sort by", detailSort, (v) => { detailSort = v; showRows(); }, {options:[["time_desc","Time: most first"],["time_asc","Time: least first"],["sessions_desc","Sessions: most first"],["sessions_asc","Sessions: least first"]]}),
      ), rowsBox);
      results.append(chart, detail);
      showRows();
      function showRows() {
        return keepScroll(rowsBox,()=>paintRows());
      }
      function paintRows() {
        dayField.querySelector("select").value = selectedDay;
        const allRows = detailRows(data, selectedDay, detailScope, combine, detailSort);
        const total = allRows.reduce((sum, row) => sum + row.seconds, 0);
        const rows = allRows.filter((r) =>
          (itemName(r.id, r.name) + " " + [...r.computers].map(id => data.computer_names[id]).join(" ")).toLocaleLowerCase().includes(search.toLocaleLowerCase()),
        );
        const dot = (color) => color ? el("span", { class: "series-dot", style: { background: color } }) : null;
        rowsBox.replaceChildren(
          rows.length
            ? el(
                "table",
                {},
                el(
                  "thead",
                  {},
                  el(
                    "tr",
                    {},
                    ...["Activity", ...(multi ? ["Computer"] : []), ...(category === "all" ? ["Type"] : []), "Time", "Share", "Sessions"].map((v) =>
                      el("th", {}, t(v)),
                    ),
                  ),
                ),
                el(
                  "tbody",
                  {},
                  rows.map((r) =>
                    el(
                      "tr",
                      {},
                      el(
                        "td",
                        {},
                        r.ids.size === 1 ? dot(colors[r.id]) : null,
                        itemName(r.id, r.name),
                      ),
                      multi ? el("td", {}, r.computers.size === 1 ? dot(data.computer_colors[[...r.computers][0]]) : null,
                        [...r.computers].map(id => data.computer_names[id]).join(", ")) : null,
                      category === "all" ? el("td", {}, t(r.type)) : null,
                      el("td", {}, shortTime(r.seconds)),
                      el(
                        "td",
                        {},
                        (
                          (100 * r.seconds) / Math.max(1, total)
                        ).toFixed(1) + "%",
                      ),
                      el("td", {}, sessionText(r.sessions, r.partial)),
                    ),
                  ),
                ),
              )
            : note("No activity yet"),
        );
        for (const col of columns.children)
          col.classList.toggle(
            "chosen",
            !!selectedDay &&
              col.getAttribute("aria-label").startsWith(selectedDay),
          );
      }
  }
}

let activityTab = "game",
  search = "",
  source = "all",
  sort = "name",
  showHidden = false,
  showExcluded = false;
export function activitiesView(ctx) {
  const content = ctx.content,
    initialSummary = ctx.state.library || { games: {}, activities: {} };
  let summary = initialSummary;
  ctx.header(
    button("Add", () => addActivity(ctx, activityTab)),
    iconButton("Refresh data", "refresh", () => ctx.command("library.refresh")),
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
        ctx.render();
      },
    ),
  );
  if (activityTab === "game") {
    content.append(
      el(
        "section",
        { class: "game-summary" },
        el("div", { class: "budget-ring" }, icon("clock")),
        el(
          "div",
          {},
          el("span", { class: "muted" }, t("Today")),
          el("strong", {}, fullTime(summary.total)),
        ),
        el(
          "div",
          {},
          el("span", { class: "muted" }, t("Remaining")),
          el(
            "strong",
            {},
            summary.remaining == null
              ? t("No shared limit")
              : fullTime(summary.remaining),
          ),
        ),
      ),
    );
  }
  const rows = el("div", {
      class: activityTab === "game" ? "game-grid" : "activity-table",
    }),
    toolbar = el("div", { class: "row library-toolbar" });
  toolbar.append(
    el("input", {
      type: "search",
      class: "search",
      value: search,
      placeholder: t(activityTab === "game" ? "Search your games…" : "Search…"),
      oninput: (e) => {
        search = e.target.value;
        fill();
      },
    }),
  );
  if (activityTab === "game")
    toolbar.append(
      field(
        "",
        source,
        (v) => {
          source = v;
          fill();
        },
        {
          options: [
            ["all", "All sources"],
            ...new Set(ctx.state.games.map((g) => g.source)),
          ].map((v) => (Array.isArray(v) ? v : [v, v])),
        },
      ),
      check("Show hidden games", showHidden, (v) => {
        showHidden = v;
        fill();
      }),
    );
  else
    toolbar.append(
      check("Show excluded", showExcluded, (v) => {
        showExcluded = v;
        fill();
      }),
    );
  toolbar.append(
    field(
      "",
      sort,
      (v) => {
        sort = v;
        fill();
      },
      {
        options: [
          ["name", "Name: A–Z"],
          ["time", "Time today"],
        ],
      },
    ),
  );
  if (activityTab === "site")
    toolbar.append(
      button("Browser connection", () => ctx.settings("other"), "quiet"),
    );
  content.append(toolbar, rows);
  let disposeArt = () => {};
  ctx.dispose = () => disposeArt();
  ctx.refresh = async () => {
    const next = (await api("library.summary")).result;
    if (!rows.isConnected) return;
    summary = next;
    const metrics = content.querySelectorAll(".game-summary strong");
    if (metrics.length) {
      metrics[0].textContent = fullTime(next.total);
      metrics[1].textContent =
        next.remaining == null
          ? t("No shared limit")
          : fullTime(next.remaining);
    }
    for (const node of rows.querySelectorAll("[data-usage]")) {
      const [kind, ...parts] = node.dataset.usage.split(":");
      const key = parts.join(":");
      const seconds =
        kind === "game"
          ? next.games[key] || 0
          : next.activities[node.dataset.usage] || 0;
      node.textContent = fullTime(seconds);
      node.hidden = kind === "game" && !seconds;
    }
  };
  fill();
  function fill() {
    return keepScroll(rows,()=>fillRows());
  }
  function fillRows() {
    disposeArt();
    let values =
      activityTab === "game"
        ? ctx.state.games
            .filter(
              (g) =>
                (showHidden || !g.hidden) &&
                (g.installed || g.id in summary.games) &&
                (source === "all" || g.source === source),
            )
            .map((g) => ({
              member: { kind: "game", value: g.id },
              name: g.name,
              game: g,
              excluded: !g.enabled,
              seconds: summary.games[g.id] || 0,
            }))
        : ctx.state.activities
            .filter(
              (a) =>
                a.member.kind === activityTab && (showExcluded || !a.excluded),
            )
            .map((a) => ({
              ...a,
              seconds:
                summary.activities[a.member.kind + ":" + a.member.value] || 0,
            }));
    values = values
      .filter((v) =>
        (v.name + " " + v.member.value)
          .toLocaleLowerCase()
          .includes(search.toLocaleLowerCase()),
      )
      .sort((a, b) =>
        sort === "time"
          ? b.seconds - a.seconds || a.name.localeCompare(b.name)
          : a.name.localeCompare(b.name),
      );
    rows.replaceChildren();
    const names = new Map();
    for (const v of values) names.set(v.name.toLocaleLowerCase(), (names.get(v.name.toLocaleLowerCase()) || 0) + 1);
    const tiles = new Map();
    for (const v of values) {
      if (v.game) {
        const initials = v.name
            .split(/\s+/)
            .slice(0, 2)
            .map((w) => w[0])
            .join("")
            .toUpperCase(),
          tile = el(
            "div",
            { class: "game-tile" },
            el("span", { class: "initials" }, initials),
          );
        const launch = button(
          "",
          () => ctx.command("game.launch", { id: v.game.id }),
          "game-art",
        );
        launch.disabled = !v.game.installed;
        launch.setAttribute("aria-label", t("Play") + " " + v.name);
        launch.title = t("Play");
        launch.append(tile, el("span", { class: "play-cue" }, icon("play")));
        const entry = el(
          "article",
          { class: "game-card" + (v.excluded ? " excluded" : "") },
          launch,
          el(
            "div",
            { class: "game-info" },
            el(
              "div",
              { class: "row spread" },
              el("h3", {}, v.name),
              iconButton("Game options", "dots", () => options(v)),
            ),
            el(
              "div",
              {
                class: "muted game-time",
                "data-usage": "game:" + v.game.id,
                hidden: !v.seconds,
              },
              fullTime(v.seconds),
            ),
            v.excluded ? note("Excluded") : null,
            names.get(v.name.toLocaleLowerCase()) > 1 ? note(t({ Kézi: "Manual", Games: "Games folder" }[v.game.source] || v.game.source)) : null,
          ),
        );
        rows.append(entry);
        tiles.set(v.game.id, { entry, tile });
      } else
        rows.append(
          el(
            "article",
            { class: "item activity-row" },
            activityImage(v.member, v.name, 42),
            el(
              "div",
              { class: "grow" },
              el("h3", {}, v.name),
              v.excluded ? note("Excluded") : null,
            ),
            el(
              "span",
              {
                class: "muted tabular",
                "data-usage": v.member.kind + ":" + v.member.value,
              },
              fullTime(v.seconds),
            ),
            iconButton("More…", "dots", () => options(v)),
          ),
        );
    }
    if (!values.length)
      rows.append(el("div", { class: "empty" }, t("No matches.")));
    if (tiles.size) disposeArt = loadArtwork(tiles, rows, ctx.namespace);
  }
  function options(v) {
    const box = el("div", { class: "menu-actions" }),
      dialog = modal(v.name, box);
    const action = (name, run, kind = "quiet") =>
      button(
        name,
        () => {
          dialog.close();
          run();
        },
        kind,
      );
    if (v.game?.installed)
      box.append(
        action(
          "Play",
          () => ctx.command("game.launch", { id: v.game.id }),
          "primary",
        ),
      );
    box.append(
      action("Set budget", () => ctx.newBudget([v.member])),
      action("Countdown", () => appearanceEditor(ctx, v.member)),
    );
    if (v.game)
      box.append(
        action("More…", () => gameActions(ctx, v.game)),
        action(v.game.hidden ? "Show in library" : "Hide", () =>
          ctx.command("activity.change", {
            kind: "game",
            key: v.game.id,
            hidden: !v.game.hidden,
          }),
        ),
      );
    if(['app','site'].includes(v.member.kind)) {
      const enabled=(ctx.state.background_media || []).some(m=>m.kind===v.member.kind && m.value===v.member.value);
      box.append(check('Count background playback',enabled,async value=>{
        try {await ctx.command('activity.media',{kind:v.member.kind,key:v.member.value,enabled:value});dialog.close();}
        catch {dialog.close();}
      }),helpNote('Counts audible playback while the desktop application is running on this computer, including while another window is active. Paused or muted playback is not counted. Time counts toward matching budgets; shared budgets count each second once. Session counts still follow foreground visits. Simultaneous activities can make total activity time exceed elapsed time.'));
    }
    if (v.member.kind !== "site")
      box.append(
        action(v.excluded ? "Restore" : "Exclude", async () => {
          if (
            !v.excluded &&
            !(await confirmAction("Exclude", "History is preserved."))
          )
            return;
          await ctx.command("activity.change", {
            kind: v.member.kind,
            key: v.member.value,
            enabled: v.excluded,
          });
        }),
      );
  }
}
function paintArtwork(target, art) {
  target.entry.style.setProperty("--game-hue", art.hue);
  if (art.image && target.tile.querySelector("img")?.src !== art.image)
    target.tile.replaceChildren(el("img", { src: art.image, alt: "", class: art.cover ? "cover" : "" }));
}
function loadArtwork(tiles, root, namespace) {
  const pending = new Set(),
    attempts = new Map();
  let running = false,
    timer,
    disposed = false;
  const observer = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting) {
          const id = e.target.dataset.game;
          observer.unobserve(e.target);
          pending.add(id);
        }
      run();
    },
    { rootMargin: "100px" },
  );
  for (const [id, { entry }] of tiles) {
    entry.dataset.game = id;
    const cached = artworkSnapshots.get(namespace + ":" + id);
    if (cached) paintArtwork(tiles.get(id), cached);
    observer.observe(entry);
  }
  async function run() {
    if (
      disposed ||
      running ||
      document.hidden ||
      !root.isConnected ||
      !pending.size
    ) {
      if (!root.isConnected) observer.disconnect();
      return;
    }
    running = true;
    const ids = [...pending].slice(0, 24);
    ids.forEach((id) => pending.delete(id));
    try {
      const images = (await api("artwork", { ids })).result;
      if (disposed || !root.isConnected) return;
      for (const [id, art] of Object.entries(images)) {
        const target = tiles.get(id);
        if (art.image || !art.pending) remember(artworkSnapshots, namespace + ":" + id, art, 96);
        paintArtwork(target, art);
        if (art.pending && (attempts.get(id) || 0) < 12) {
          attempts.set(id, (attempts.get(id) || 0) + 1);
          pending.add(id);
        }
      }
    } catch {
    } finally {
      running = false;
      if (!disposed && pending.size && root.isConnected && !document.hidden)
        timer = setTimeout(run, Math.min(3000, 500 * (1 + Math.min(...[...pending].map(id => attempts.get(id) || 0)))));
    }
  }
  const resume = () => {
    if (!root.isConnected) {
      observer.disconnect();
      document.removeEventListener("visibilitychange", resume);
    } else if (!document.hidden) run();
    else clearTimeout(timer);
  };
  document.addEventListener("visibilitychange", resume);
  return () => {
    disposed = true;
    observer.disconnect();
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", resume);
  };
}

export function budgetsView(ctx) {
  ctx.header();
  ctx.savedDrafts("budget", (v) => budgetEditor(ctx, v));
  ctx.content.append(
    el(
      "div",
      { class: "row spread budget-toolbar" },
      note("Your individual and shared budgets, all in one place."),
      el(
        "div",
        { class: "row" },
        button("Add computer-use period", () => ctx.newComputerBudget()),
        button("Add new", () => ctx.newBudget(), "primary"),
      ),
    ),
  );
  const list = el("div", { class: "list budget-list" });
  const breaks=new Map();
  for (const b of ctx.state.budgets) {
    const pause=button('Break now',()=>{
      const action=ctx.live?.break_actions?.[b.key];
      if(action?.step)return ctx.command('break.start',{key:b.key,step:action.step});
    },'primary');pause.hidden=true;breaks.set(b.key,pause);
    const members =
        b.kind === "computer"
          ? t("Scheduled period")
          : b.members.map((m) => memberName(ctx, m)).join(", "),
      amount =
        b.kind === "computer"
          ? timeText(b.values.bedtime_minute) +
            "–" +
            timeText(b.values.bedtime_resume_minute)
          : b.usage
            ? `${b.seconds / 60} ${t("min / day")}`
            : t("At a time of day");
    list.append(
      el(
        "article",
        { class: "item budget-row" },
        el(
          "div",
          { class: "grow" },
          el("h3", {}, b.name),
          el("div", { class: "budget-members muted" }, b.kind === "computer" ? members : b.members.map(m =>
            el("span", { class: "activity-caption" }, activityImage(m, memberName(ctx, m), 24), memberName(ctx, m)))),
        ),
        el(
          "span",
          { class: "budget-amount" },
          [amount, daysText(b.days), b.enabled ? "" : t("Disabled")]
            .filter(Boolean)
            .join(" · "),
        ),
        pause,
        button("Edit", () => budgetEditor(ctx, b)),
        iconButton("Delete", "trash", async () => {
          if (await confirmAction("Delete this item?", "History is preserved."))
            await ctx.command("budget.delete", { key: b.key });
        }),
      ),
    );
  }
  ctx.content.append(
    list.childElementCount ? list : card(note("No budgets yet.")),
  );
  ctx.refresh=()=>{
    for(const [key,pause] of breaks){
      const action=ctx.live?.break_actions?.[key];pause.hidden=!action;pause.disabled=!action?.step;
      pause.title=action?.remaining?t('Break remaining: {time}').replace('{time}',clock(action.remaining)):t('Break now');
    }
  };ctx.refresh();
}
export function notificationsView(ctx) {
  const presets = () => {
    const box = el("div", { class: "list" });
    for (const p of ctx.state.presets)
      box.append(
        button(
          ctx.state.triggers.find((v) => v.id === p.value.trigger)?.name ||
            p.value.trigger,
          () => {
            document.querySelector("#dialog").close();
            notificationEditor(ctx, p);
          },
        ),
      );
    modal("Restore preset", box);
  };
  ctx.header(
    button("Presets", presets, "quiet"),
    button("Add new", () => ctx.newNotification(), "primary"),
  );
  ctx.content.append(
    note("Create reminders with your own triggers and actions."),
  );
  ctx.savedDrafts("notification", (v) => notificationEditor(ctx, v));
  const list = el("div", { class: "list notification-list" });
  for (const n of ctx.state.notifications) {
    let when =
      ctx.state.triggers.find((v) => v.id === n.value.trigger)?.name || "";
    if (n.value.trigger === "time")
      when = t("Daily at") + " " + timeText(n.value.minute);
    if (n.value.trigger === "pomodoros")
      when = t("Completed rounds today") + ": " + n.value.count;
    list.append(
      el(
        "article",
        { class: "item notification-row" },
        el(
          "span",
          { class: "notification-icon" },
          n.value.icon.startsWith("preset:") ? icon(
            n.value.icon.startsWith("preset:") ? n.value.icon.slice(7) : "bell",
          ) : activityImage({ kind: "notification", value: n.key }, n.title, 36),
        ),
        el(
          "div",
          { class: "grow" },
          el("h3", {}, n.title),
          el(
            "p",
            { class: "muted" },
            when + " · " + t(n.value.enabled ? "Enabled" : "Disabled"),
          ),
          el("p", { class: "muted" }, n.message),
        ),
        button("Edit", () => notificationEditor(ctx, n), "quiet"),
        iconButton("Delete", "trash", async () => {
          if (await confirmAction("Delete this item?"))
            await ctx.command("notification.delete", { key: n.key });
        }),
      ),
    );
  }
  ctx.content.append(
    list.childElementCount ? list : card(note("No notifications yet.")),
  );
}

let focusTab = "site",
  selected = "";
export function focusView(ctx) {
  const f = ctx.state.live.focus,
    s = ctx.state.focus,
    paused =
      !f.running &&
      !f.finished &&
      (f.phase !== "focus" || f.remaining !== s.work * 60),
    phase = t(
      { focus: "Focus", short_break: "Short break", long_break: "Long break" }[
        f.phase
      ],
    );
  ctx.header(
    button(
      "How does focus work?",
      () =>
        help(
          "How does focus work?",
          "Start a work interval to enable your blacklist. Pausing or stopping releases the restrictions immediately.",
        ),
      "quiet",
    ),
  );
  ctx.content.append(
    el(
      "section",
      { class: "card focus-timer" },
      el(
        "div",
        { class: "row spread" },
        el(
          "div",
          { class: "row" },
          el("h2", { id: "focus-phase" }, phase),
          el(
            "span",
            { class: "muted" },
            t(
              f.running
                ? "Running"
                : f.finished
                  ? "Completed"
                  : paused
                    ? "Paused"
                    : "Ready to start",
            ),
          ),
        ),
        button("Timer settings", () => focusEditor(ctx), "quiet"),
      ),
      el(
        "div",
        { class: "row focus-control-row" },
        el("div", { class: "timer", id: "focus-clock" }, clock(f.remaining)),
        button(
          f.running
            ? "Pause"
            : f.finished
              ? "New focus session"
              : f.phase !== "focus"
                ? "Continue break"
                : paused
                  ? "Resume focus"
                  : "Start focus",
          () => ctx.command(f.running ? "focus.pause" : "focus.start"),
          "primary",
        ),
        button("Stop", () => ctx.command("focus.stop"), "quiet"),
        el(
          "span",
          { class: "muted focus-rounds" },
          t("Completed rounds in total") + ": " + f.rounds,
        ),
      ),
      el(
        "p",
        { class: "hint" },
        s.rounds === 0
          ? t("Single focus session: {work} min").replace("{work}", s.work)
          : `${t("Work")}: ${s.work} ${t("min")} · ${t("Short break")}: ${s.short_break} ${t("min")}`,
      ),
      note(
        f.running
          ? "Your blacklist is active during work."
          : "Start when you are ready. Your blacklist is active during work.",
      ),
    ),
  );
  const rows = ctx.state.members[focusTab] || [],
    remove = button(
      "Remove",
      () => {
        const field = {
          site: "block_sites",
          app: "block_apps",
          group: "block_groups",
        }[focusTab];
        ctx.command("focus.save", {
          [field]: s[field].filter((v) => v !== selected),
        });
      },
      "quiet",
    );
  remove.disabled = !rows.some((r) => r[0] === selected && r[3]);
  const group = card(
    el(
      "div",
      { class: "row spread" },
      el("h2", {}, t("What should stay out of your focus session?")),
      remove,
    ),
    el(
      "div",
      { class: "row spread hint" },
      `${s.block_apps.length} ${t("Applications").toLocaleLowerCase()} · ${s.block_sites.length} ${t("Websites").toLocaleLowerCase()} · ${s.block_groups.length} ${t("Groups").toLocaleLowerCase()}`,
      el("span", {}, t("Browser connected")),
    ),
  );
  const pane = el("div", { class: "focus-tab-pane" }),
    tabbar = tabs(
      [
        ["site", "Websites"],
        ["app", "Applications"],
        ["group", "Groups"],
      ],
      focusTab,
      (v) => {
        focusTab = v;
        selected = "";
        ctx.render();
      },
      "focus-tabs",
    );
  group.append(tabbar, pane);
  if (focusTab === "site") {
    let site = "";
    const input = el("input", {
        placeholder: t("Paste a URL or domain, e.g. https://youtube.com"),
        "aria-label": t("Website URL or domain"),
        oninput: (e) => (site = e.target.value),
        onkeydown: (e) => {
          if (e.key === "Enter") add.click();
        },
      }),
      add = button("Add website", () =>
        ctx.command("focus.save", { block_sites: [...s.block_sites, site] }),
      );
    pane.append(
      el("div", { class: "row site-input" }, input, add),
      note("The whole domain and its subdomains will be blocked during work."),
    );
  } else if (focusTab === "app")
    pane.append(
      button("Choose from detected applications…", () =>
        pickApplication(ctx, (path) =>
          ctx.command("focus.save", { block_apps: [...s.block_apps, path] }),
        ),
      ),
    );
  else
    pane.append(
      button("Add group", () => {
        const list = el("div", { class: "list" });
        for (const g of ctx.state.groups.filter(
          (g) => !s.block_groups.includes(g.id),
        ))
          list.append(
            button(g.name, () => {
              document.querySelector("#dialog").close();
              ctx.command("focus.save", {
                block_groups: [...s.block_groups, g.id],
              });
            }),
          );
        modal("Add group", list.childElementCount ? list : note("No matches."));
      }),
    );
  const list = el("div", {
    class: "focus-members",
    role: "listbox",
    "aria-label": t(
      { site: "Websites", app: "Applications", group: "Groups" }[focusTab],
    ),
  });
  for (const [key, name, detail, direct, groups] of rows) {
    const row = button(
      "",
      () => {
        selected = key;
        for (const b of list.children)
          b.setAttribute("aria-selected", b === row ? "true" : "false");
        remove.disabled = !direct;
      },
      "focus-member",
    );
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", selected === key ? "true" : "false");
    row.title = detail;
    const member = focusTab === "site" ? { kind: "site", value: key }
      : key.startsWith("member:game:") ? { kind: "game", value: key.slice(12) }
      : focusTab === "app" ? { kind: "app", value: key.startsWith("member:app:") ? key.slice(11) : key } : null;
    row.append(
      member ? activityImage(member, name) : icon("focus"),
      el("div", { class: "grow" }, el("div", {}, name),
      groups.length
        ? el("small", {}, t("From groups") + ": " + groups.join(", "))
        : null),
    );
    list.append(row);
  }
  if (rows.length) pane.append(list);
  group.append(
    note(
      focusTab === "site"
        ? "Add the websites you want to avoid during work."
        : "Change inherited members in Budgets, or remove their group.",
    ),
  );
  ctx.content.append(group);
  ctx.animate();
}
