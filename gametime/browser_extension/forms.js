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
import { syncPanel } from "./sync-ui.js";
import {
  rulesPanel,
  protectedDisplay,
  updatesPanel,
  iconUpload,
} from "./library-ui.js";
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
        field(
          "Actions",
          type,
          (v) => {
            const fresh = clone(ctx.state.default_step);
            fresh.id = s.id;
            fresh.kind = v === "restrict" ? "cover" : v;
            if (v === "notify") fresh.popup = true;
            if (v === "break")
              Object.assign(fresh, {
                time_mode: "usage",
                offset: 1800,
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
            if (v === "relative") {
              delete s.time_mode;
              delete s.clock_minute;
              s.offset = 0;
            } else {
              s.time_mode = v;
              s.offset = v === "usage" ? (type === "break" ? 1800 : 0) : 0;
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
                  ]
                : [
                    ["usage", "After usage (minutes)"],
                    ["relative", "Relative to limit (minutes)"],
                    ["clock", "At a time of day"],
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
          : number(
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
            el("h2", {}, t("Notifications")),
            check("Enabled", n.enabled, (v) => (n.enabled = v)),
          ),
          field("Title", n.title, (v) => (n.title = v), {
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
        el("h3", {}, t("Icon")),
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
        el(
          "details",
          {},
          el("summary", {}, t("Icon")),
          field(
            "Icon",
            n.icon.startsWith("preset:") ? "" : n.icon,
            (v) => (n.icon = v),
            { placeholder: "C:\\Pictures\\icon.png" },
          ),
        ),
      );
      first.append(
        iconUpload(ctx, (result) => {
          n.icon = result.path;
          changed();
          redraw();
        }),
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

export function settingsEditor(ctx) {
  ctx.edit(
    "Settings",
    "settings",
    { ...ctx.state.settings, tracking: ctx.state.focus.tracking },
    (body, s, redraw, changed) => {
      body.append(
        card(
          el("h2", {}, t("General")),
          grid(
            field("Language", s.language, (v) => (s.language = v), {
              options: [
                ["hu", "Magyar"],
                ["en", "English"],
              ],
            }),
            field(
              "Day starts at",
              timeText(s.budget_reset_minute),
              (v) => (s.budget_reset_minute = minutes(v)),
              { type: "time", required: true },
            ),
          ),
          note(
            "This day boundary applies to all budgets, statistics and daily reminders.",
          ),
          check(
            "Check for updates automatically",
            s.check_updates,
            (v) => (s.check_updates = v),
          ),
        ),
      );
      body.append(
        card(
          el("h2", {}, t("Activities")),
          check(
            "Track applications and websites",
            s.tracking,
            (v) => (s.tracking = v),
          ),
          field("Games folder", s.games_root, (v) => (s.games_root = v), {
            required: true,
          }),
          check(
            "Create game shortcuts",
            s.hub_enabled,
            (v) => (s.hub_enabled = v),
          ),
          el(
            "details",
            {},
            el("summary", {}, t("Game sources")),
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
        ),
      );
      body.append(
        card(
          el("h2", {}, t("Countdown appearance")),
          appearanceFields(s, ctx.state.settings),
          check(
            "Detailed RTSS countdown",
            s.overlay_rtss_details,
            (v) => (s.overlay_rtss_details = v),
          ),
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
      );
      const sound = card(
        el("h2", {}, t("Notifications")),
        field(
          "Notification sound",
          s.notification_sound,
          (v) => {
            s.notification_sound = v;
            changed();
            redraw();
          },
          {
            options: [
              ["default", "Default"],
              ["information", "Information"],
              ["error", "Error"],
              ["silent", "Silent"],
              ["custom", "Custom sound"],
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
      body.append(sound);
      body.append(
        card(
          el("h2", {}, t("Linked computers")),
          field(
            "Computer name",
            s.statistics_device_name,
            (v) => (s.statistics_device_name = v),
            { maxLength: 80 },
          ),
          el(
            "p",
            { class: "pill" },
            t(ctx.state.sync.enabled ? "Connected" : "Not connected"),
          ),
          button("Manage linked computers", () => syncPanel(ctx)),
        ),
      );
      body.append(
        card(
          el("h2", {}, t("Advanced settings")),
          button("Executable exclusions and assignments", () =>
            rulesPanel(ctx),
          ),
          button(
            ctx.state.protected_display.enabled
              ? "Disable display in protected games"
              : "Display in protected games",
            () => protectedDisplay(ctx),
          ),
        ),
        updatesPanel(ctx),
      );
      body.append(
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
          .map((v) => button(v.name, () => select(v.member), "quiet")),
      );
    }
  }
  function select(member) {
    dialog.close();
    choose(clone(member));
  }
  fill();
}
