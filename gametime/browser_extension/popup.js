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
const content = document.querySelector("#popup-content"),
  status = document.querySelector("#status");
let state,
  revision,
  last = 0;
function open(page = "overview") {
  chrome.tabs.create({ url: chrome.runtime.getURL("panel.html") + "#" + page });
  window.close();
}
async function command(action, data = {}) {
  try {
    await api(action, data, revision);
    await refresh();
  } catch (e) {
    status.textContent = e.message;
  }
}
async function refresh() {
  try {
    const result = await api("state");
    state = result.result;
    revision = result.revision;
    setLanguage(state.live.language);
    last = performance.now();
    document.querySelector("#connected").classList.add("online");
    const f = state.live.focus;
    content.replaceChildren(
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
        el("p", { class: "hint" }, t("Today’s focus rounds") + ": " + f.today),
      ),
    );
    const event = state.live.timers.find((timer) => timer.key !== "focus");
    if (event)
      content.append(
        card(
          el("div", { class: "muted" }, event.name + " · " + event.label),
          el("strong", { class: "large" }, clock(event.seconds)),
          event.detail ? el("div", { class: "hint" }, event.detail) : null,
        ),
      );
    const tab = (
      await chrome.tabs.query({ active: true, currentWindow: true })
    )[0];
    let domain = "";
    try {
      const url = new URL(tab?.url);
      if (!tab.incognito && ["http:", "https:"].includes(url.protocol))
        domain = url.hostname;
    } catch {}
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
            button(
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
        button("Time budgets", () => open("budgets"), "quiet"),
        button("Notifications", () => open("notifications"), "quiet"),
      ),
    );
    status.textContent = "";
  } catch (e) {
    content.replaceChildren(
      note(
        "The desktop application runs tracking and restrictions; keep it running in the background.",
      ),
      button("Connect your browser", () => open("settings"), "primary full"),
    );
    status.textContent = e.message;
  }
}
setInterval(() => {
  if (document.hidden) return;
  const node = document.querySelector("#clock");
  if (node && state)
    node.textContent = clock(
      state.live.focus.remaining -
        (state.live.focus.running ? (performance.now() - last) / 1000 : 0),
    );
}, 1000);
refresh();
