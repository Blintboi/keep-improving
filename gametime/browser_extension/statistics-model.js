// Keep computer origins and a stable activity order, as in the desktop chart.
export function chartGroups(data, day, metric = "time") {
  const devices = new Map();
  for (const [date, id, , , seconds, computer] of data.rows) {
    if (date !== day || seconds <= 0) continue;
    if (!devices.has(computer)) devices.set(computer, new Map());
    const values = devices.get(computer);
    values.set(id, (values.get(id) || 0) + seconds);
  }
  return [...devices].sort(([a], [b]) =>
    (a !== "local") - (b !== "local") ||
    data.computer_names[a].localeCompare(data.computer_names[b]) || a.localeCompare(b),
  ).map(([computer, values]) => {
    const snapshot = data.sessions?.[computer], counts = new Map();
    for (const [date, kind, key, count] of snapshot?.rows || [])
      if (date === day) counts.set(kind === "game" ? key : `activity:${kind}:${key}`, count);
    const partial = !snapshot || day <= snapshot.since;
    const activities = data.games.filter(([id]) => values.has(id)).map(([id, name]) => ({ id, name, seconds: values.get(id), sessions: counts.get(id) || 0, partial,
      value: metric === "sessions" ? counts.get(id) || 0 : values.get(id) }));
    return { computer, total: [...values.values()].reduce((a, b) => a + b, 0), activities,
      sessions: activities.reduce((n, row) => n + row.sessions, 0), value: activities.reduce((n,row)=>n+row.value,0), partial };
  });
}

export function sessionText(count, partial) { return String(count); }

export function detailRows(data, day, computer, combine, order = "time_desc") {
  const groups = new Map();
  const counts = new Map(), since = new Map();
  for (const [device, snapshot] of Object.entries(data.sessions || {})) {
    since.set(device, snapshot.since);
    for (const [date, kind, key, count] of snapshot.rows) counts.set(JSON.stringify([date, kind === "game" ? key : `activity:${kind}:${key}`, device]), count);
  }
  for (const [date, id, name, source, seconds, device] of data.rows) {
    if (seconds <= 0 || (day && date !== day) || (computer !== "all" && device !== computer)) continue;
    const type = ["Application", "Website", "Browser"].includes(source) ? source : "Game";
    const key = JSON.stringify(combine ? [type, name.normalize("NFKC").toLocaleLowerCase().trim().replace(/\s+/g, " ")] : [id, device]);
    if (!groups.has(key)) groups.set(key, { id, name, type, seconds: 0, sessions: 0, partial: false, computers: new Set(), ids: new Set() });
    const row = groups.get(key);
    row.seconds += seconds;
    row.sessions += counts.get(JSON.stringify([date, id, device])) || 0;
    row.partial ||= !since.has(device) || date <= since.get(device);
    row.computers.add(device);
    row.ids.add(id);
  }
  const sessions = order.startsWith("sessions"), direction = order.endsWith("asc") ? 1 : -1;
  return [...groups.values()].sort((a, b) => direction * (sessions ? a.sessions - b.sessions : a.seconds - b.seconds) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}
