import {
  api,
  el,
  button,
  card,
  check,
  field,
  note,
  t,
  icon,
  clone,
  uid,
  timeText,
  minutes,
  modal,
  confirmAction,
} from "./client.js";
import {
  rulesPanel,
  protectedDisplay,
  updatesPanel,
  iconUpload,
} from "./library-ui.js";
import { activityImage } from "./activity-images.js";
import { choiceFields } from './session-choice-fields.js';
const grid = (...items) => el("div", { class: "grid" }, items);
const number = (name, obj, key, min, max, scale = 1) =>
  field(name, obj[key] / scale, (v) => (obj[key] = v * scale), {
    type: "number",
    min,
    max,
    required: true,
    step: 1,
  });
function weekdays(value, changed) {
  return el(
    "div",
    { class: "stack" },
    el("h3", {}, t("Active days")),
    el(
      "div",
      { class: "days" },
      ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((name, day) =>
        check(name, value.includes(day), (enabled) => {
          if (enabled) value.push(day);
          else value.splice(value.indexOf(day), 1);
          value.sort();
          changed();
        }),
      ),
    ),
  );
}

function deviceScope(ctx, rule, budget, changed) {
  const data = ctx.state.device_scopes;
  if (!data) return note("Devices");
  const selections = (data.devices || []).map(d => [{mode: "device", device: d.id}, d.name]);
  if (data.connection) {
    selections.push([{mode: "all"}, t("All linked devices")]);
    for (const [id, group] of Object.entries(data.groups || {}))
      if (group.connection === data.connection) selections.push([{mode: "group", group: id}, group.name]);
  }
  const key = s => s.mode + ":" + (s.device || s.group || "");
  const current = rule.devices || {mode: "device", device: data.local};
  if (!selections.some(([s]) => key(s) === key(current))) selections.push([current, t("Unavailable device or group")]);
  return el("div", {class: "stack"},
    field("Devices", key(current), value => {
      rule.devices = clone(selections.find(([s]) => key(s) === value)[0]);
      if (data.connection) rule.devices.connection = data.connection;
      if (budget) rule.devices.accounting = "shared";
      changed();
    }, {options: selections.map(([s, name]) => [key(s), name])}),
    note(budget ? "Selected devices share one allowance. Offline totals use the last synchronization." : "This notification appears on the selected devices."));
}

export function budgetEditor(ctx, source) {
  ctx.edit(
    source.name || "Shared budget",
    "budget:" + source.key,
    clone(source),
    (body, b, redraw, changed) => {
      const basic = card(
        el(
          "div",
          { class: "row spread" },
          el(
            "h2",
            {},
            t(b.kind === "computer" ? "Computer-use period" : "Shared budget"),
          ),
          check("Enabled", b.enabled, (v) => {
            b.enabled = v;
            if (b.kind === "computer") b.values.bedtime_enabled = v;
          }),
        ),
        field("Budget name", b.name, (v) => (b.name = v), {
          maxLength: 80,
          required: true,
        }),
      );
      if (b.kind === "computer")
        basic.append(
          grid(
            field(
              "Reminder",
              timeText(b.values.bedtime_warning_minute),
              (v) => (b.values.bedtime_warning_minute = minutes(v)),
              { type: "time", required: true },
            ),
            field(
              "Bedtime",
              timeText(b.values.bedtime_minute),
              (v) => (b.values.bedtime_minute = minutes(v)),
              { type: "time", required: true },
            ),
            field(
              "Resume",
              timeText(b.values.bedtime_resume_minute),
              (v) => (b.values.bedtime_resume_minute = minutes(v)),
              { type: "time", required: true },
            ),
          ),
          el(
            "div",
            { class: "stack" },
            check(
              "Bedtime reminder",
              b.values.bedtime_warning_enabled,
              (v) => (b.values.bedtime_warning_enabled = v),
            ),
            check(
              "Enforce bedtime",
              b.values.bedtime_minimize,
              (v) => (b.values.bedtime_minimize = v),
            ),
            check(
              "Include bedtime in remaining time",
              b.values.bedtime_caps_budget,
              (v) => (b.values.bedtime_caps_budget = v),
            ),
          ),
        );
      else {
        basic.append(
          el("div", { class: "separator" }),
          check("Limit daily usage", b.usage, (v) => {
            b.usage = v;
            changed();
            redraw();
          }),
          ...(b.usage
            ? [number("Daily limit (minutes)", b, "seconds", 0, 1440, 60)]
            : []),
        );
        const members = el("div", { class: "list" });
        for (const [i, m] of b.members.entries()) {
          const name =
            m.kind === "category"
              ? t(
                  {
                    games: "All games",
                    apps: "All applications",
                    sites: "All websites",
                  }[m.value],
                )
              : m.kind === "game"
                ? ctx.state.games.find((g) => g.id === m.value)?.name || m.value
                : m.value;
          members.append(
            el(
              "div",
              { class: "item" },
              activityImage(m, name),
              el("span", { class: "grow" }, name),
              b.kind === "group"
                ? button(
                    "Remove",
                    () => {
                      b.members.splice(i, 1);
                      changed();
                      redraw();
                    },
                    "quiet",
                  )
                : null,
            ),
          );
        }
        basic.append(
          el("div", { class: "separator" }),
          el(
            "div",
            { class: "row spread" },
            el("h3", {}, t("Members")),
            b.kind === "group"
              ? button(
                  "Add member",
                  () =>
                    pickMember(ctx, (m) => {
                      if (
                        !b.members.some(
                          (old) => old.kind === m.kind && old.value === m.value,
                        )
                      )
                        b.members.push(m);
                      changed();
                      redraw();
                    }),
                  "quiet",
                )
              : null,
          ),
          members,
        );
      }
      basic.append(
        el("div", { class: "separator" }),
        weekdays(b.days, changed),
      );
      if (b.kind !== "computer") basic.append(deviceScope(ctx, b, true, changed));
      body.append(basic);
      if (b.kind !== "computer")
        body.append(
          actionsEditor(ctx, b, redraw, changed),
          card(
            el("h2", {}, t("Countdown appearance")),
            check("Show countdown", b.overlay, (v) => {
              b.overlay = v;
              if (b.kind === "game") (b.appearance ??= {}).overlay_enabled = v;
            }),
            el(
              "details",
              {},
              el("summary", {}, t("Countdown appearance")),
              appearanceFields(
                b.appearance ?? (b.appearance = {}),
                ctx.state.settings,
                false,
              ),
            ),
          ),
        );
    },
    "budget.save",
  );
}

function actionsEditor(ctx, b, redraw, changed) {
  const box = card(
    el(
      "div",
      { class: "row spread" },
      el("h2", {}, t("Actions")),
      button("Add action", () => {
        if (!b.plan)
          b.plan = {
            ...clone(ctx.state.default_plan),
            legacy: true,
            legacy_warning: true,
          };
        const step = clone(ctx.state.default_step);
        step.id = uid();
        step.targets = {
          app: { enabled: true, mode: "cover" },
          site: { enabled: true, mode: "cover" },
        };
        b.plan.steps.push(step);
        changed();
        redraw();
      }),
    ),
  );
  if (b.legacy?.active) {
    const legacy = el("div", { class: "subcard stack" });
    if (b.kind === "shared") {
      legacy.append(
        check("Warning", b.legacy.warning, (v) => {
          b.legacy.warning = v;
          changed();
          redraw();
        }),
        ...(b.legacy.warning
          ? [
              number(
                "After usage (minutes)",
                b.legacy,
                "warning_seconds",
                0,
                1440,
                60,
              ),
            ]
          : []),
        check("Restriction", b.legacy.restriction, (v) => {
          b.legacy.restriction = v;
          changed();
          redraw();
        }),
        ...(b.legacy.restriction
          ? [
              number(
                "After usage (minutes)",
                b.legacy,
                "restriction_seconds",
                1,
                1440,
                60,
              ),
            ]
          : []),
      );
    } else
      legacy.append(
        check(
          "Restrict when the budget runs out",
          b.kind === "game" ? b.legacy.enforce : b.enforce,
          (v) => {
            b.legacy.enforce = v;
            b.enforce = v;
          },
        ),
      );
    box.append(legacy);
  }
  if (!b.plan) return box;
  for (const [index, s] of b.plan.steps.entries()) {
    const type =
        s.kind === "notify"
          ? "notify"
          : s.kind === "break"
            ? "break"
            : "restrict",
      section = el("section", { class: "subcard" });
    section.append(
      el(
        "div",
        { class: "row spread" },
        s.session_choice ? el('h3', {}, t('Opening choice')) : field(
          "Actions",
          type,
          (v) => {
            const fresh = clone(ctx.state.default_step);
            fresh.id = s.id;
            if (s.time_mode) {fresh.time_mode=s.time_mode;fresh.offset=s.offset;if(s.time_mode==='clock')fresh.clock_minute=s.clock_minute;}
            fresh.kind = v === "restrict" ? "cover" : v;
            if (v === "notify") fresh.popup = true;
            if (v === "break")
              Object.assign(fresh, {
                time_mode: s.time_mode || "usage",
                offset: s.time_mode ? s.offset : 1800,
                break_mode: "cover",
                break_minutes: 5,
              });
            fresh.targets = { app: { enabled: true }, site: { enabled: true } };
            if (v === "restrict") {
              fresh.targets.app.mode = "cover";
              fresh.targets.site.mode = "cover";
            }
            b.plan.steps[index] = fresh;
            changed();
            redraw();
          },
          {
            options: [
              ["notify", "Warning"],
              ["break", "Break"],
              ["restrict", "Restriction"],
            ],
          },
        ),
        button(
          "Delete",
          () => {
            b.plan.steps.splice(index, 1);
            changed();
            redraw();
          },
          "quiet danger",
        ),
      ),
    );
    section.append(
      grid(
        field(
          "When",
          s.time_mode || "relative",
          (v) => {
            if (v !== 'sessions') delete s.session_choice;
            if (v !== 'usage') delete s.allow_early_break;
            if (v === "relative") {
              delete s.time_mode;
              delete s.clock_minute;
              s.offset = 0;
            } else {
              s.time_mode = v;
              s.offset = v === "sessions" ? 5 : v === "usage" ? (type === "break" ? 1800 : 0) : 0;
              if (v === "clock") s.clock_minute = 1200;
              else delete s.clock_minute;
            }
            changed();
            redraw();
          },
          {
            options:
              type === "break"
                ? [
                    ["usage", "After usage (minutes)"],
                    ["clock", "At a time of day"],
                    ["sessions", "Daily session limit"],
                  ]
                : [
                    ["usage", "After usage (minutes)"],
                    ["relative", "Relative to limit (minutes)"],
                    ["clock", "At a time of day"],
                    ["sessions", "Daily session limit"],
                  ],
          },
        ),
        s.time_mode === "clock"
          ? field(
              "Time",
              timeText(s.clock_minute),
              (v) => (s.clock_minute = minutes(v)),
              { type: "time", required: true },
            )
          : s.time_mode === "sessions" ? (s.session_choice ? null : number("Allowed sessions",s,"offset",1,10000)) : number(
              s.time_mode === "usage"
                ? "After usage (minutes)"
                : "Relative to limit (minutes)",
              s,
              "offset",
              s.time_mode === "usage"
                ? type === "break"
                  ? 1
                  : 0
                : type === "notify"
                  ? -1440
                  : 0,
              1440,
              60,
            ),
      ),
    );
    if(s.time_mode==='sessions') section.append(choiceFields(s,changed,redraw));
    if (s.session_choice) {box.append(section);continue;}
    if(s.time_mode==='sessions') section.append(note("The action starts on the next session after the allowed count. The count resets at the budget renewal."));
    if(s.time_mode==='sessions' && type==='break') section.append(note("After the break, the same number of new sessions is allowed before the next break."));
    if (type === "notify")
      section.append(
        el(
          "div",
          { class: "row" },
          check("Sound", s.sound, (v) => (s.sound = v)),
          check("Popup", s.popup, (v) => (s.popup = v)),
        ),
      );
    if (type === "break")
      section.append(
        number("Break length (minutes)", s, "break_minutes", 1, 1440),
      );
    if(type==='break' && s.time_mode==='usage') section.append(
      check('Allow “Break now”',!!s.allow_early_break,v=>{
        if(v)s.allow_early_break=true;else delete s.allow_early_break;changed();redraw();
      }),
      ...(s.allow_early_break?[note('After the full break, a fresh usage interval begins. Unused minutes do not carry over; the daily budget is not reset.')]:[]));
    const targets = el("div", { class: "grid" });
    for (const scope of ["app", "site"]) {
      const options = s.targets?.[scope] || {},
        target = card(
          check(
            scope === "app" ? "Apply to applications" : "Apply to websites",
            options.enabled !== false,
            (v) => {
              s.targets ??= {};
              s.targets[scope] = { ...options, enabled: v };
              changed();
              redraw();
            },
          ),
        );
      if (options.enabled !== false && type !== "notify") {
        const modeKey = type === "break" ? "break_mode" : "mode",
          mode = options[modeKey] || (type === "break" ? s.break_mode : s.kind),
          values =
            scope === "app"
              ? [
                  ["cover", "Cover"],
                  ["minimize", "Minimize"],
                  ["close", "Close"],
                ]
              : [
                  ["cover", "Cover"],
                  ["redirect", "Redirect"],
                  ["close", "Close"],
                ];
        if (mode === "restrict") values.push(["restrict", "Restriction"]);
        target.append(
          field(
            "Mode",
            mode,
            (v) => {
              s.targets ??= {};
              const entry = (s.targets[scope] ??= { enabled: true });
              entry[modeKey] = v;
              if (v === "redirect") entry.redirect_url ??= "";
              else delete entry.redirect_url;
              changed();
              redraw();
            },
            { options: values },
          ),
        );
        if (mode === "redirect")
          target.append(
            field(
              "Redirect URL",
              options.redirect_url || s.redirect_url || "",
              (v) => {
                s.targets ??= {};
                (s.targets[scope] ??= {
                  enabled: true,
                  break_mode: "redirect",
                }).redirect_url = v;
              },
              { type: "url", required: true },
            ),
          );
        target.append(
          field(
            "Save allowance (minutes)",
            options.extension_minutes ?? b.plan.extension_minutes,
            (v) => {
              s.targets ??= {};
              (s.targets[scope] ??= { enabled: true }).extension_minutes = v;
            },
            { type: "number", min: 0, max: 60, required: true },
          ),
        );
      } else if (type === "notify")
        target.append(
          check("Sound", options.sound ?? s.sound, (v) => {
            s.targets ??= {};
            (s.targets[scope] ??= { enabled: true }).sound = v;
          }),
          check("Popup", options.popup ?? s.popup, (v) => {
            s.targets ??= {};
            (s.targets[scope] ??= { enabled: true }).popup = v;
          }),
        );
      targets.append(target);
    }
    section.append(targets);
    box.append(section);
  }
  box.append(
    note("Closing may lose unsaved work."),
    check(
      "I allow closing applications and tabs for this budget.",
      b.plan.close_confirmed,
      (v) => (b.plan.close_confirmed = v),
    ),
  );
  return box;
}

export function notificationEditor(ctx, source) {
  const data = clone({ key: source.key, value: source.value });
  data.value.id ||= data.key.slice(10);
  data.value.days ||= [0,1,2,3,4,5,6];
  ctx.edit(
    source.title || "Notifications",
    "notification:" + data.key,
    data,
    (body, data, redraw, changed) => {
      const n = data.value,
        first = card(
          el(
            "div",
            { class: "row spread" },
            el("span", {}, t("Title")),
            check("Enabled", n.enabled, (v) => (n.enabled = v)),
          ),
          field("", n.title, (v) => (n.title = v), {
            "aria-label": t("Title"),
            maxLength: 80,
            required: !n.template,
            placeholder: source.title || "",
          }),
          field("Message", n.text, (v) => (n.text = v), {
            type: "textarea",
            maxLength: 1000,
            required: !n.template,
            rows: 4,
            placeholder: source.message || "",
          }),
          field(
            "Show notification",
            n.trigger,
            (v) => {
              n.trigger = v;
              changed();
              redraw();
            },
            { options: ctx.state.triggers.map((v) => [v.id, v.name]) },
          ),
        );
      first.classList.add("notification-editor");
      first.append(deviceScope(ctx, n, false, changed));
      first.append(weekdays(n.days, changed));
      if (n.trigger === "time")
        first.append(
          field("Time", timeText(n.minute), (v) => (n.minute = minutes(v)), {
            type: "time",
            required: true,
          }),
        );
      if (n.trigger === "pomodoros")
        first.append(number("Completed rounds today", n, "count", 1, 1000));
      first.append(
        el("div", {}, t("Icon")),
        el(
          "div",
          { class: "icons" },
          ctx.state.icons.map((i) =>
            el(
              "button",
              {
                type: "button",
                class:
                  "icon-choice" +
                  (n.icon === "preset:" + i.id ? " selected" : ""),
                "aria-pressed": n.icon === "preset:" + i.id,
                onclick: () => {
                  n.icon = "preset:" + i.id;
                  changed();
                  redraw();
                },
              },
              icon(i.id),
              i.name,
            ),
          ),
        ),
        iconUpload(ctx, (result) => {
          n.icon = result.path;
          changed();
          redraw();
        }),
        el(
          "details",
          {},
          el("summary", {}, t("Custom icon path")),
          field(
            "Icon",
            n.icon.startsWith("preset:") ? "" : n.icon,
            (v) => (n.icon = v),
            { placeholder: "C:\\Pictures\\icon.png" },
          ),
        ),
      );
      body.append(first);
      const action = card(
        field(
          "Notification button",
          n.action.kind,
          (v) => {
            n.action =
              v === "pomodoro"
                ? {
                    kind: v,
                    work: 25,
                    short_break: 5,
                    long_break: 15,
                    rounds: 4,
                  }
                : v === "app"
                  ? { kind: v, path: "" }
                  : { kind: "none" };
            changed();
            redraw();
          },
          {
            options: [
              ["none", "No button"],
              ["app", "Open application"],
              ["pomodoro", "Start Pomodoro"],
            ],
          },
        ),
      );
      if (n.action.kind === "app")
        action.append(
          field("Executable path", n.action.path, (v) => (n.action.path = v), {
            required: true,
          }),
          button("Choose application", () =>
            pickApplication(ctx, (path) => {
              n.action.path = path;
              changed();
              redraw();
            }),
          ),
        );
      if (n.action.kind === "pomodoro") action.append(pomodoroFields(n.action));
      body.append(action);
      const closing =
          n.timeout === null ? "default" : n.timeout === 0 ? "manual" : "delay",
        last = card(
          field(
            "Closing",
            closing,
            (v) => {
              n.timeout = v === "default" ? null : v === "manual" ? 0 : 15;
              changed();
              redraw();
            },
            {
              options: [
                ["default", "Default duration"],
                ["delay", "After a delay"],
                ["manual", "Manual closing only"],
              ],
            },
          ),
        );
      if (closing === "delay")
        last.append(number("Seconds", n, "timeout", 1, 3600));
      last.append(
        button("Preview", async () => {
          await ctx.command("notification.preview", { value: n }, false);
          const action = clone(n.action);
          let dialog;
          dialog = modal(
            n.title || source.title || "Notifications",
            el(
              "div",
              { class: "stack" },
              el("div", { class: "badge-icon" }, icon(n.icon.slice(7))),
              el("p", {}, n.text || source.message || ""),
              action.kind === "pomodoro" ? pomodoroFields(action) : null,
              action.kind !== "none"
                ? button(
                    action.kind === "app"
                      ? "Open application"
                      : "Start Pomodoro",
                    async () => {
                      await ctx.command(
                        "notification.action",
                        { action },
                        false,
                      );
                      dialog.close();
                      if (action.kind === "pomodoro") {
                        await ctx.load();
                        ctx.go("focus");
                      }
                    },
                    "primary",
                  )
                : null,
            ),
          );
        }),
      );
      body.append(last);
    },
    "notification.save",
  );
}

function pomodoroFields(values) {
  return el(
    "div",
    { class: "stack" },
    grid(
      number("Focus minutes", values, "work", 1, 240),
      number("Short break minutes", values, "short_break", 0, 60),
      number("Long break minutes", values, "long_break", 0, 120),
      number("Rounds before long break", values, "rounds", 0, 12),
    ),
    note(
      "0-minute breaks are skipped. Zero rounds means one focus session without a break or repetition.",
    ),
  );
}
export function focusEditor(ctx) {
  const data = {};
  for (const key of ["work", "short_break", "long_break", "rounds"])
    data[key] = ctx.state.focus[key];
  ctx.edit(
    "Timer settings",
    "focus",
    data,
    (body, value) => body.append(card(pomodoroFields(value))),
    "focus.save",
  );
}

function appearanceFields(value, defaults, includeEnabled = true) {
  const model = { ...defaults, ...value },
    box = el("div", { class: "stack" }),
    rows = [];
  for (const [key, label, min, max, scale] of [
    ["overlay_font_size", "Text size", 8, 72, 1],
    ["overlay_opacity", "Opacity (%)", 25, 100, 0.01],
    ["overlay_x", "Horizontal position (%)", 0, 100, 0.01],
    ["overlay_y", "Vertical position (%)", 0, 100, 0.01],
  ])
    rows.push(
      field(
        label,
        Math.round(model[key] / scale),
        (v) => (value[key] = v * scale),
        { type: "number", min, max, required: true },
      ),
    );
  rows.push(
    field(
      "Normal color",
      model.overlay_color_normal,
      (v) => (value.overlay_color_normal = v),
      { type: "color" },
    ),
    field(
      "Warning color",
      model.overlay_color_warning,
      (v) => (value.overlay_color_warning = v),
      { type: "color" },
    ),
  );
  box.append(
    grid(rows),
    field("Monitor", model.overlay_screen, (v) => (value.overlay_screen = v), {
      placeholder: t("Automatic"),
    }),
    ...(includeEnabled
      ? [
          check(
            "Show countdown",
            model.overlay_enabled,
            (v) => (value.overlay_enabled = v),
          ),
        ]
      : []),
    check(
      "Use RTSS",
      model.overlay_rtss_auto,
      (v) => (value.overlay_rtss_auto = v),
    ),
  );
  return box;
}
export function appearanceEditor(ctx, member) {
  const key = member.kind + ":" + member.value;
  ctx.edit(
    "Countdown appearance",
    "appearance:" + key,
    { key, value: clone(ctx.state.activity_appearances[key] || {}) },
    (body, d) =>
      body.append(
        card(
          appearanceFields(d.value, ctx.state.settings),
          button(
            "Use default appearance",
            async () => {
              await ctx.command("activity.appearance", { key, value: null });
              ctx.go("activities");
            },
            "quiet",
          ),
        ),
      ),
    "activity.appearance",
  );
}

let settingsSection = "general";
export function settingsEditor(ctx, requested = settingsSection) {
  settingsSection = requested;
  ctx.edit(
    "Settings",
    "settings",
    { ...ctx.state.settings, tracking: ctx.state.focus.tracking },
    (body, s, redraw, changed, editorCommand) => {
      const pages = {};
      const navigation = el("div", { class: "segments settings-tabs" });
      function select(key) {
        settingsSection = key;
        for (const [id, node] of Object.entries(pages))
          node.hidden = id !== key;
        for (const b of navigation.children)
          b.classList.toggle("selected", b.dataset.section === key);
      }
      for (const [key, title] of [
        ["general", "General"],
        ["reminders", "Reminders"],
        ["games", "Game folders"],
        ["other", "Updates"],
      ]) {
        const b = button(title, () => select(key));
        b.dataset.section = key;
        navigation.append(b);
        pages[key] = el("div", {
          class: "settings-section",
          hidden: key !== settingsSection,
        });
      }
      body.append(navigation, ...Object.values(pages));
      pages.general.append(
        card(
          el("h2", {}, t("Day starts at")),
          note(
            "One daily boundary for statistics, all budgets and daily reminders.",
          ),
          field(
            "",
            timeText(s.budget_reset_minute),
            (v) => (s.budget_reset_minute = minutes(v)),
            { type: "time", required: true, "aria-label": t("Day starts at") },
          ),
          note("Earlier statistics and already used time are kept."),
          check("Measure application and website time", s.tracking,
            (v) => (s.tracking = v)),
        ),
      );
      const sound = card(
        el("h2", {}, t("Notification sound")),
        field(
          "",
          s.notification_sound,
          (v) => {
            s.notification_sound = v;
            changed();
            redraw();
          },
          {
            "aria-label": t("Notification sound"),
            options: [
              ["default", "Default sound"],
              ["information", "Information sound"],
              ["error", "Attention sound"],
              ["silent", "Silent"],
              ["custom", "Custom WAV file"],
            ],
          },
        ),
      );
      if (s.notification_sound === "custom")
        sound.append(
          field(
            "Sound file path",
            s.notification_sound_path,
            (v) => (s.notification_sound_path = v),
            { required: true },
          ),
        );
      const protectedToggle = check("Also show in anti-cheat games",
        ctx.state.protected_display.enabled, () => {
          const enabled = ctx.state.protected_display.enabled;
          protectedToggle.querySelector("input").checked = enabled;
          protectedDisplay({ ...ctx, command: editorCommand }, () => {
            ctx.state.protected_display.enabled = !enabled;
            redraw();
          });
        });
      pages.reminders.append(
        sound,
        card(
          check("Show over fullscreen games", s.overlay_rtss_auto,
            (v) => (s.overlay_rtss_auto = v)),
          protectedToggle,
          note("Applies to countdowns and notifications."),
          el("div", { class: "separator" }),
          check("Detailed RTSS countdown", s.overlay_rtss_details,
            (v) => (s.overlay_rtss_details = v)),
          note("Show the event name and daily budget remaining. Turn off to show only the countdown."),
        ),
        card(
          el("h2", {}, t("Reminder messages")),
          button("Notifications", () => ctx.go("notifications")),
          check(
            "Use countdown for early warning",
            s.overlay_replace_warning,
            (v) => (s.overlay_replace_warning = v),
          ),
          check(
            "Daily limit popup",
            s.limit_popup_enabled,
            (v) => (s.limit_popup_enabled = v),
          ),
        ),
        el(
          "details",
          { class: "card" },
          el("summary", {}, t("Countdown appearance")),
          appearanceFields(s, ctx.state.settings),
        ),
      );
      pages.games.append(
        card(
          el("h2", {}, t("Games folder")),
          field("", s.games_root, (v) => (s.games_root = v), {
            "aria-label": t("Games folder"),
          }),
          check(
            "Maintain game shortcuts",
            s.hub_enabled,
            (v) => (s.hub_enabled = v),
          ),
          el(
            "details",
            {},
            el("summary", {}, t("Advanced")),
            note("One folder per line"),
            ...["steam_roots", "epic_manifest_dirs", "ubisoft_roots"].map(
              (key) =>
                field(
                  {
                    steam_roots: "Steam",
                    epic_manifest_dirs: "Epic Games",
                    ubisoft_roots: "Ubisoft",
                  }[key],
                  s[key].join("\n"),
                  (v) =>
                    (s[key] = v
                      .split("\n")
                      .map((v) => v.trim())
                      .filter(Boolean)),
                  { type: "textarea" },
                ),
            ),
          ),
          button(
            "Executable exclusions and assignments",
            () => rulesPanel(ctx),
            "quiet",
          ),
        ),
      );
      pages.other.append(
        card(
          check(
            "Check for updates automatically",
            s.check_updates,
            (v) => (s.check_updates = v),
          ),
          updatesPanel(ctx),
        ),
        card(
          el("h2", {}, t("Browser connection")),
          note("Connected to the local application"),
          note(
            "The desktop application runs tracking and restrictions; keep it running in the background.",
          ),
          button(
            "Disconnect",
            async () => {
              if (await confirmAction("Disconnect", "")) {
                await chrome.storage.local.remove("pairing");
                location.reload();
              }
            },
            "quiet danger",
          ),
        ),
      );
      select(settingsSection);
    },
    "settings.save",
  );
}

export async function pickApplication(ctx, choose) {
  const box = el("div", { class: "stack" }),
    list = el("div", { class: "scroll-list list" });
  let query = "",
    manual = "";
  const dialog = modal("Choose application", box);
  box.append(
    el("input", {
      class: "search",
      type: "search",
      placeholder: t("Search…"),
      "aria-label": t("Search…"),
      oninput: (e) => {
        query = e.target.value.toLowerCase();
        fill();
      },
    }),
    list,
    el(
      "details",
      {},
      el("summary", {}, t("Executable path")),
      field("Executable path", "", (v) => (manual = v), {
        placeholder: "C:\\Program Files\\App\\app.exe",
      }),
      button("Choose", () => {
        dialog.close();
        choose(manual);
      }),
    ),
  );
  let apps = [];
  try {
    apps = (await api("applications")).result;
    fill();
  } catch (e) {
    list.textContent = e.message;
  }
  function fill() {
    list.replaceChildren(
      ...apps
        .filter((a) => (a.name + " " + a.path).toLowerCase().includes(query))
        .map((a) =>
          el(
            "button",
            {
              type: "button",
              class: "item",
              title: a.path,
              onclick: () => {
                dialog.close();
                choose(a.path);
              },
            },
            activityImage({ kind: "app", value: a.path }, a.name),
            el(
              "div",
              { class: "grow" },
              el("strong", {}, a.name),
              el("div", { class: "hint wrap" }, a.path),
            ),
          ),
        ),
    );
    if (!list.childElementCount) list.append(note("No matches."));
  }
}

export function pickMember(ctx, choose) {
  let kind = "site",
    value = "",
    search = "";
  const box = el("div"),
    dialog = modal("Add member", box);
  function fill() {
    const list = el("div", { class: "scroll-list list" });
    box.replaceChildren(
      field(
        "Members",
        kind,
        (v) => {
          kind = v;
          fill();
        },
        {
          options: [
            ["site", "Websites"],
            ["app", "Applications"],
            ["game", "Games"],
            ["category", "Groups"],
          ],
        },
      ),
    );
    if (kind === "site")
      box.append(
        field("Domain or website URL", value, (v) => (value = v)),
        button("Add", () => select({ kind: "site", value })),
      );
    if (kind === "app")
      box.append(
        button("Choose application", () => {
          dialog.close();
          pickApplication(ctx, (path) => choose({ kind: "app", value: path }));
        }),
      );
    box.append(
      el("input", {
        class: "search",
        type: "search",
        placeholder: t("Search…"),
        value: search,
        oninput: (e) => {
          search = e.target.value;
          filter();
        },
      }),
      list,
    );
    filter();
    function filter() {
      const values =
        kind === "game"
          ? ctx.state.games.map((g) => ({
              name: g.name,
              member: { kind: "game", value: g.id },
            }))
          : kind === "category"
            ? ["games", "apps", "sites"].map((v) => ({
                name: t(
                  {
                    games: "All games",
                    apps: "All applications",
                    sites: "All websites",
                  }[v],
                ),
                member: { kind: "category", value: v },
              }))
            : ctx.state.activities.filter((a) => a.member.kind === kind);
      list.replaceChildren(
        ...values
          .filter((v) =>
            (v.name + " " + v.member.value)
              .toLowerCase()
              .includes(search.toLowerCase()),
          )
          .map((v) => {
            const choice = button("", () => select(v.member), "quiet activity-choice");
            choice.append(activityImage(v.member, v.name), el("span", {}, v.name));
            return choice;
          }),
      );
    }
  }
  function select(member) {
    dialog.close();
    choose(clone(member));
  }
  fill();
}
