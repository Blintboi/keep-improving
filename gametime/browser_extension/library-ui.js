import {
  api,
  el,
  button,
  card,
  check,
  field,
  note,
  t,
  modal,
  confirmAction,
} from "./client.js";
import { pickApplication } from "./forms.js";

export function addActivity(ctx, kind) {
  if (kind === "site") {
    let value = "";
    const dialog = modal(
      "Add website",
      field("Domain or website URL", "", (v) => (value = v)),
      [
        button(
          "Add",
          async () => {
            await ctx.command("activity.add", { kind, value });
            dialog.close();
          },
          "primary",
        ),
      ],
    );
    return;
  }
  pickApplication(ctx, (path) => {
    if (kind === "app") {
      ctx.command("activity.add", { kind, value: path });
      return;
    }
    let name = path
      .split(/[\\/]/)
      .at(-1)
      .replace(/\.exe$/i, "");
    const dialog = modal(
      "Add game",
      field("Game name", name, (v) => (name = v), { maxLength: 120 }),
      [
        button(
          "Add",
          async () => {
            await ctx.command("game.add", { path, name });
            dialog.close();
          },
          "primary",
        ),
      ],
    );
  });
}

export function gameActions(ctx, game) {
  const dialog = modal(
    game.name,
    el(
      "div",
      { class: "stack" },
      el("p", { class: "hint wrap" }, game.root),
      button("Assign executable", () => {
        dialog.close();
        pickApplication(ctx, (path) =>
          ctx.command("rule.save", { path, game: game.id }),
        );
      }),
      button(
        "Uninstall game",
        async () => {
          dialog.close();
          const plan = await ctx.command(
            "game.removal",
            { id: game.id },
            false,
          );
          const confirm = modal(plan.title, el("p", {}, plan.instructions), [
            button(
              "Continue",
              async () => {
                await ctx.command(
                  "game.removal",
                  { id: game.id, confirm: plan.confirm },
                  false,
                );
                confirm.close();
              },
              "danger",
            ),
          ]);
        },
        "quiet danger",
      ),
    ),
  );
}

export function rulesPanel(ctx) {
  let path = "",
    game = "";
  const box = el("div", { class: "stack" });
  const dialog = modal("Executable exclusions and assignments", box);
  function fill() {
    box.replaceChildren(
      ...Object.entries(ctx.state.executable_rules).map(([path, id]) =>
        el(
          "div",
          { class: "item" },
          el(
            "div",
            { class: "grow wrap" },
            el(
              "strong",
              {},
              ctx.state.games.find((g) => g.id === id)?.name || t("Excluded"),
            ),
            el("div", { class: "hint" }, path),
          ),
          button(
            "Remove",
            async () => {
              await ctx.command("rule.delete", { path }, false);
              dialog.close();
              await ctx.load();
            },
            "quiet",
          ),
        ),
      ),
      button("Add", () => {
        dialog.close();
        pickApplication(ctx, (selected) => {
          path = selected;
          const form = el(
            "div",
            { class: "stack" },
            note(path),
            field("Assignment", "", (v) => (game = v), {
              options: [
                ["", "Excluded"],
                ...ctx.state.games.map((g) => [g.id, g.name]),
              ],
            }),
          );
          const next = modal("Assignment", form, [
            button(
              "Save",
              async () => {
                await ctx.command(
                  "rule.save",
                  { path, game: game || null },
                  false,
                );
                next.close();
                await ctx.load();
              },
              "primary",
            ),
          ]);
        });
      }),
    );
  }
  fill();
}

export function protectedDisplay(ctx, saved = () => ctx.load()) {
  const current = ctx.state.protected_display;
  if (current.enabled) {
    ctx
      .command("display.consent", { enabled: false }, false)
      .then(saved).catch(ctx.fail);
    return;
  }
  let accepted = false;
  const enable = button(
    "Enable at my own risk",
    async () => {
      if (!accepted) return;
      try {
        await ctx.command(
          "display.consent",
          { enabled: true, accepted: true },
          false,
        );
        dialog.close();
        await saved();
      } catch (error) { ctx.fail(error); }
    },
    "primary",
  );
  enable.disabled = true;
  const dialog = modal(
    "Display in protected games",
    el(
      "div",
      { class: "stack" },
      el("p", {}, current.notice),
      check("I understand and accept the risk.", false, (v) => {
        accepted = v;
        enable.disabled = !v;
      }),
    ),
    [enable],
  );
}

export function updatesPanel(ctx) {
  const status = el("p", { class: "hint" }),
    download = button(
      "Download and install update",
      async () => { await ctx.command("update.command", { action: "download" }, false); poll(); },
      "primary",
    );
  download.hidden = true;
  const box = card(
    el("h2", {}, t("Updates")),
    status,
    el(
      "div",
      { class: "row" },
      button("Check for updates", async () => {
        await ctx.command("update.command", { action: "check" }, false);
        poll();
      }),
      download,
    ),
  );
  async function poll() {
    if (!box.isConnected || document.hidden) return;
    try {
      const value = (await api("update.state")).result;
      status.textContent = value.message;
      download.hidden = !value.version;
      download.disabled = value.pending;
      if (value.pending) setTimeout(poll, 1000);
    } catch (e) {
      status.textContent = e.message;
    }
  }
  setTimeout(poll, 0);
  return box;
}

export function iconUpload(ctx, selected) {
  const status = el("p", { class: "hint upload-status" });
  const input = el("input", {
    type: "file",
    hidden: true,
    accept: "image/png,image/jpeg,image/webp",
    onchange: async () => {
      const file = input.files?.[0];
      if (!file) return;
      try {
        if (file.size > 330000)
          throw Error(t("Choose an image smaller than 330 KB."));
        const bytes = new Uint8Array(await file.arrayBuffer());
        let value = "";
        for (let i = 0; i < bytes.length; i += 8192)
          value += String.fromCharCode(...bytes.subarray(i, i + 8192));
        const result = await ctx.command(
          "icon.upload",
          { image: btoa(value) },
          false,
        );
        selected(result);
        status.textContent = "";
      } catch (e) {
        status.textContent = e.message;
      }
    },
  });
  return el(
    "div",
    { class: "row" },
    input,
    button("Choose image…", () => input.click()),
    status,
  );
}
