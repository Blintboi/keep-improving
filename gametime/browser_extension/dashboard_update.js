// Preserve the user's dashboard tabs during the application's extension reload.
(() => {
  const panel = () => new URL(chrome.runtime.getURL("panel.html"));
  const handoff = (port, key) =>
    `http://127.0.0.1:${port}/browser-update#dashboard-${key}`;
  globalThis.prepareDashboardUpgrade = async (pairing) => {
    if (
      !Number.isInteger(pairing?.port) ||
      pairing.port < 1024 ||
      pairing.port > 65535
    )
      return [];
    const records = {},
      moved = [],
      base = panel();
    for (const tab of await chrome.tabs.query({})) {
      if (tab.incognito) continue;
      let url;
      try {
        url = new URL(tab.url);
      } catch {
        continue;
      }
      if (
        url.protocol !== base.protocol ||
        url.host !== base.host ||
        url.pathname !== base.pathname
      )
        continue;
      const key = crypto.randomUUID().replaceAll("-", ""),
        section = url.hash.slice(1);
      records[key] = {
        section:
          /^(overview|activities|budgets|notifications|focus|settings)$/.test(
            section,
          )
            ? section
            : "overview",
        port: pairing.port,
        savedAt: Date.now(),
      };
      moved.push({
        id: tab.id,
        before: tab.url,
        handoff: handoff(pairing.port, key),
      });
    }
    await chrome.storage.local.set({ dashboardReturns: records });
    try {
      for (const tab of moved) {
        const current = await chrome.tabs.get(tab.id).catch(() => null);
        if (current?.url === tab.before)
          await chrome.tabs.update(tab.id, { url: tab.handoff });
      }
      return moved;
    } catch (error) {
      for (const tab of moved) {
        const current = await chrome.tabs.get(tab.id).catch(() => null);
        if (current?.url === tab.handoff)
          await chrome.tabs.update(tab.id, { url: tab.before }).catch(() => {});
      }
      throw error;
    }
  };
  globalThis.restoreDashboardTabs = async () => {
    const { dashboardReturns = {} } =
      await chrome.storage.local.get("dashboardReturns");
    if (!Object.keys(dashboardReturns).length) return;
    const allowed = new Map();
    for (const [key, item] of Object.entries(dashboardReturns).slice(0, 64)) {
      if (
        !/^[a-f0-9]{32}$/.test(key) ||
        !Number.isInteger(item?.port) ||
        item.port < 1024 ||
        item.port > 65535 ||
        !Number.isFinite(item.savedAt) ||
        Date.now() - item.savedAt > 86400000 ||
        !/^(overview|activities|budgets|notifications|focus|settings)$/.test(
          item.section,
        )
      )
        continue;
      allowed.set(
        handoff(item.port, key),
        chrome.runtime.getURL("panel.html") + "#" + item.section,
      );
    }
    for (const tab of await chrome.tabs.query({})) {
      if (tab.incognito) continue;
      const url = allowed.get(tab.url);
      if (url) await chrome.tabs.update(tab.id, { url });
    }
    await chrome.storage.local.set({ dashboardReturns: {} });
  };
  globalThis.dashboardRestored = restoreDashboardTabs().catch(() => {});
})();
