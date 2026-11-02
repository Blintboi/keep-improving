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

export async function syncPanel(ctx) {
  const root = ctx.content;
  let state = (await api("sync.state")).result,
    code = "",
    enabled = state.enabled,
    name = state.name;
  const status = el("p", { class: "hint", role: "status" }),
    account = el("p"),
    error = el("p", { class: "error", role: "alert" });
  const codeField = field("Connection code", "", (v) => (code = v), {
    type: "password",
    autocomplete: "off",
    spellcheck: false,
    placeholder: t("Paste a connection code or reveal the current code"),
  });
  const actions = el("div", { class: "row" }),
    devices = el("div", { class: "list" });
  root.replaceChildren(
    button("Back", () => ctx.go("settings"), "quiet"),
    card(
      el("h2", {}, t("Linked computers")),
      account,
      actions,
      check("Enable synchronization", enabled, (v) => (enabled = v)),
      field("Computer name", name, (v) => (name = v), { maxLength: 80 }),
      codeField,
      el(
        "div",
        { class: "row" },
        button("Reveal code", async () => {
          const value = await ctx.command("sync.reveal", {}, false);
          setCode(value.code);
        }),
        button("New code", async () => {
          const value = await ctx.command("sync.generate", {}, false);
          setCode(value.code);
        }),
        button("Copy code", () => navigator.clipboard.writeText(code)),
      ),
      note("Keep your code private. Anyone with it can link a computer."),
      status,
      error,
      el(
        "div",
        { class: "footer" },
        button(
          "Sync now",
          () => run("sync.command", { action: "sync" }),
          "quiet",
        ),
        button("Save changes", () => save(), "primary"),
      ),
    ),
    card(el("h2", {}, t("Linked computers")), devices),
  );
  function setCode(value) {
    code = value;
    codeField.querySelector("input").value = value;
    codeField.querySelector("input").type = "text";
  }
  async function run(action, data) {
    error.textContent = "";
    try {
      state = await ctx.command(action, data, false);
      update();
      poll();
    } catch (e) {
      error.textContent = e.message;
    }
  }
  async function save(replaceConfirmed = false) {
    if (!code && enabled) {
      try {
        code = (await ctx.command("sync.reveal", {}, false)).code;
      } catch (e) {
        error.textContent = e.message;
        return;
      }
    }
    await run("sync.save", {
      enabled,
      code,
      name,
      replace_confirmed: replaceConfirmed,
    });
  }
  function update() {
    account.textContent = state.signed_in
      ? t("Signed in") + ": " + (state.account_name || "GitHub")
      : t("Not signed in");
    status.textContent = state.busy ? t("Working…") : state.status;
    actions.replaceChildren(
      button(
        state.signed_in ? "Sign out" : "Sign in with GitHub",
        () =>
          run("sync.command", { action: state.signed_in ? "logout" : "login" }),
        state.signed_in ? "quiet" : "primary",
      ),
    );
    if (state.signed_in)
      actions.append(
        button(
          "Revoke connection code",
          async () => {
            if (
              await confirmAction(
                "Revoke connection code",
                "Server copies are removed and linked computers stop synchronizing. Local history is preserved.",
              )
            )
              await run("sync.command", { action: "revoke", confirmed: true });
          },
          "quiet danger",
        ),
      );
    for (const b of actions.querySelectorAll("button")) b.disabled = state.busy;
    devices.replaceChildren(
      ...state.computers.map(([id, label]) =>
        el(
          "div",
          { class: "item" },
          el("span", { class: "grow" }, label),
          button(
            "Rename",
            () => {
              let next = label;
              const dialog = modal(
                "Rename",
                field("Computer name", label, (v) => (next = v), {
                  maxLength: 80,
                }),
                [
                  button(
                    "Save",
                    async () => {
                      await ctx.command(
                        "sync.rename",
                        { id, name: next },
                        false,
                      );
                      dialog.close();
                      poll();
                    },
                    "primary",
                  ),
                ],
              );
            },
            "quiet",
          ),
        ),
      ),
    );
    if (!devices.childElementCount)
      devices.append(note("No linked computers yet."));
    if (state.result?.error) {
      error.textContent = state.result.error;
      if (state.result.other_group)
        error.append(
          button("Replace connection code", async () => {
            if (
              await confirmAction(
                "Replace connection code",
                "Server copies are removed and linked computers stop synchronizing. Local history is preserved.",
              )
            )
              await save(true);
          }),
        );
    } else if (state.result?.ok) error.textContent = "";
  }
  async function poll() {
    if (!root.contains(status) || document.hidden) return;
    try {
      const result = await api("sync.state");
      state = result.result;
      ctx.acceptRevision(result.revision);
      update();
      if (state.busy || state.syncing) setTimeout(poll, 1000);
    } catch (e) {
      error.textContent = e.message;
    }
  }
  update();
  poll();
}
