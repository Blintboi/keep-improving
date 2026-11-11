import { api, el, icon, uid } from "./client.js";

// One visible queue for libraries, focus lists and selectors, independent of Hub visibility.
const client = uid(), nodes = new Map(), cache = new Map();
let timer, running = false, failures = 0;
const observer = new IntersectionObserver(entries => {
  for (const entry of entries) {
    const value = nodes.get(entry.target);
    if (value) value.visible = entry.isIntersecting;
  }
  schedule();
}, { rootMargin: "80px" });

export function activityImage(member, name = "", size = 36) {
  if (member.kind === "category") return icon(member.value === "games" ? "activities" : "focus");
  const key = member.kind + ":" + member.value;
  const node = el("span", { class: "activity-image", "data-activity-image": key, "aria-hidden": "true", style: { width: size + "px", height: size + "px" } },
    (name || member.value).split(/[\\/]/).at(-1).slice(0, 1).toUpperCase());
  const previous = cache.get(key);
  if (previous) paint(node, previous);
  return node;
}

function paint(node, image) {
  if (node.firstElementChild?.getAttribute("src") !== image)
    node.replaceChildren(el("img", { src: image, alt: "" }));
}
function attach(node) {
  if (nodes.has(node)) return;
  nodes.set(node, { key: node.dataset.activityImage, visible: false, pending: true });
  observer.observe(node);
}
new MutationObserver(records => {
  let changed = false;
  for (const record of records) for (const node of record.addedNodes) {
    if (node.nodeType !== 1) continue;
    if (node.matches("[data-activity-image]")) { attach(node); changed = true; }
    for (const child of node.querySelectorAll("[data-activity-image]")) { attach(child); changed = true; }
  }
  for (const node of nodes.keys()) if (!node.isConnected) {
    observer.unobserve(node); nodes.delete(node); changed = true;
  }
  if (changed) { failures = 0; schedule(); }
}).observe(document.body, { childList: true, subtree: true });

function schedule(wait = 0) {
  clearTimeout(timer);
  if (!document.hidden && failures < 3) timer = setTimeout(load, wait);
}
async function release() {
  if (!running) await api("library.icons", { client, ids: [] }).catch(() => {});
}
async function load() {
  if (document.hidden || running) return;
  const ids = [...new Set([...nodes].filter(([node, value]) => node.isConnected && value.visible && value.pending)
    .map(([, value]) => value.key))].slice(0, 24);
  if (!ids.length) { release(); return; }
  running = true;
  try {
    const images = (await api("library.icons", { client, ids })).result;
    for (const [key, value] of Object.entries(images)) {
      if (value.image) {
        cache.delete(key); cache.set(key, value.image);
        while (cache.size > 256) cache.delete(cache.keys().next().value);
      }
      for (const [node, state] of nodes) if (state.key === key) {
        if (value.image) paint(node, value.image);
        state.pending = value.pending;
      }
    }
    failures = 0;
  } catch { failures++; }
  finally {
    running = false;
    if (document.hidden) release();
    else if ([...nodes.values()].some(value => value.visible && value.pending)) schedule(1000);
    else release();
  }
}
document.addEventListener("visibilitychange", () => {
  clearTimeout(timer);
  if (document.hidden) release();
  else { failures = 0; schedule(); }
});
window.addEventListener("pagehide", () => { clearTimeout(timer); release(); });
