import { nativeHu } from "./desktop-text.js";
export let language = "hu";
export function setLanguage(value) {
  language = value === "en" ? "en" : "hu";
  document.documentElement.lang = language;
}
const hu = {
  "Browser mode": "Böngészős mód",
  "The desktop application is unavailable. Browser tracking, focus and saved website budgets continue here.": "Az asztali alkalmazás nem érhető el. A böngészős mérés, a fókusz és a mentett webes keretek itt működnek tovább.",
  "Recorded time transfers automatically when the application returns, without counting it twice.": "A mért idő az alkalmazás visszatérésekor automatikusan átkerül, dupla elszámolás nélkül.",
  "Other applications and settings need the desktop application.": "Más alkalmazások figyeléséhez és a beállítások módosításához az asztali alkalmazás szükséges.",
  "This action needs the desktop application.": "Ehhez a művelethez az asztali alkalmazás szükséges.",
  "Browser storage is full. Reconnect the desktop application.": "A böngészős tárhely megtelt. Indítsd el az asztali alkalmazást az adatok átvételéhez.",
  Overview: "Áttekintés",
  Activities: "Tevékenységek",
  "Budgets": "Keretek",
  Notifications: "Értesítések",
  "Focus mode": "Fókusz mód",
  Settings: "Beállítások",
  "Connected to the local application": "Kapcsolódva a helyi alkalmazáshoz",
  "Connect your browser": "Böngésző csatlakoztatása",
  "Pairing code": "Párosítási kód",
  Browser: "Böngésző",
  "Copy the pairing code from Activities → Websites → Browser connection in the application.":
    "Másold ide a párosítási kódot az alkalmazás Tevékenységek → Weboldalak → Böngésző csatlakoztatása oldaláról.",
  "Save & connect": "Mentés és kapcsolódás",
  Disconnect: "Leválasztás",
  "Invalid pairing code.": "Érvénytelen párosítási kód.",
  "The local application is unavailable. Start Keep Improving and try again.":
    "A helyi alkalmazás nem érhető el. Indítsd el a Keep Improving programot, majd próbáld újra.",
  "Pair this browser first.": "Először csatlakoztasd ezt a böngészőt.",
  "Open dashboard": "Kezelőfelület megnyitása",
  "No active timers": "Nincs aktív időzítő",
  "Open desktop application": "Asztali alkalmazás megnyitása",
  Refresh: "Frissítés",
  "Save changes": "Módosítások mentése",
  "Saved.": "Mentve.",
  Cancel: "Mégse",
  Delete: "Törlés",
  Edit: "Szerkesztés",
  "Add new": "Új hozzáadása",
  Back: "Vissza",
  "Delete this item?": "Törlöd ezt az elemet?",
  "History is preserved.": "Az előzmények megmaradnak.",
  "Discard changes?": "Elveted a módosításokat?",
  "Your unapplied draft is saved in this browser.":
    "A még nem alkalmazott piszkozat ebben a böngészőben megmarad.",
  "Discard draft": "Piszkozat elvetése",
  "Continue editing": "Szerkesztés folytatása",
  "Restore draft": "Piszkozat folytatása",
  "A saved draft is available.": "Van egy mentett piszkozatod.",
  "Settings changed in another window. Refresh before saving; your draft is kept.":
    "A beállítások egy másik ablakban megváltoztak. Mentés előtt frissíts; a piszkozatod megmarad.",
  Today: "Ma",
  "Last 7 days": "Elmúlt 7 nap",
  "Last 30 days": "Elmúlt 30 nap",
  "Custom period": "Egyéni időszak",
  Start: "Kezdet",
  End: "Vége",
  Show: "Megjelenítés",
  "All activity": "Összes tevékenység",
  Games: "Játékok",
  Applications: "Alkalmazások",
  Websites: "Weboldalak",
  "All computers": "Összes számítógép",
  "This computer": "Ez a számítógép",
  "Total time": "Összes idő",
  "Daily average": "Napi átlag",
  "Most used": "Legtöbbet használt",
  "Daily activity": "Napi tevékenység",
  Activity: "Tevékenység",
  Time: "Idő",
  "No activity yet": "Még nincs tevékenység",
  "Search…": "Keresés…",
  "No matches.": "Nincs találat.",
  "Show hidden games": "Rejtett játékok megjelenítése",
  "Show excluded": "Kizártak megjelenítése",
  Excluded: "Kizárva",
  Hidden: "Rejtett",
  Play: "Indítás",
  Exclude: "Kizárás",
  Restore: "Visszaállítás",
  Hide: "Elrejtés",
  "Show in library": "Megjelenítés",
  "Set budget": "Keret beállítása",
  Countdown: "Számláló",
  "Shared budget": "Közös keret",
  "Budget name": "Keret neve",
  Enabled: "Bekapcsolva",
  Members: "Tagok",
  "Add member": "Tag hozzáadása",
  "Daily limit (minutes)": "Napi keret (perc)",
  "Limit daily usage": "Napi használat korlátozása",
  "Active days": "Aktív napok",
  Mon: "H",
  Tue: "K",
  Wed: "Sze",
  Thu: "Cs",
  Fri: "P",
  Sat: "Szo",
  Sun: "V",
  "All games": "Összes játék",
  "All applications": "Összes alkalmazás",
  "All websites": "Összes weboldal",
  Group: "Csoport",
  Groups: "Csoportok",
  "Domain or website URL": "Domain vagy webcím",
  "Choose application": "Alkalmazás választása",
  "Executable path": "Alkalmazás elérési útja",
  "Computer-use period": "Géphasználati időszak",
  "Add computer-use period": "Géphasználati időszak hozzáadása",
  Bedtime: "Lefekvés",
  Resume: "Folytatás",
  Reminder: "Emlékeztető",
  "Bedtime reminder": "Lefekvési emlékeztető",
  "Enforce bedtime": "Lefekvés érvényesítése",
  "Include bedtime in remaining time":
    "Lefekvés figyelembevétele a hátralévő időben",
  Actions: "Műveletek",
  "Add action": "Művelet hozzáadása",
  Warning: "Figyelmeztetés",
  Break: "Szünet",
  Restriction: "Korlátozás",
  When: "Mikor",
  "After usage (minutes)": "Használat után (perc)",
  "Relative to limit (minutes)": "Kerethez képest (perc)",
  "At a time of day": "Adott időpontban",
  Sound: "Hang",
  Popup: "Felugró értesítés",
  Minimize: "Kis méret",
  Cover: "Takarófelület",
  Close: "Bezárás",
  Redirect: "Átirányítás",
  Mode: "Mód",
  "Save allowance (minutes)": "Mentési idő (perc)",
  "Break length (minutes)": "Szünet hossza (perc)",
  "Redirect URL": "Átirányítás webcíme",
  "Apply to applications": "Alkalmazásokra",
  "Apply to websites": "Weboldalakra",
  "Closing may lose unsaved work.":
    "A bezárás mentetlen munka elvesztésével járhat.",
  "I allow closing applications and tabs for this budget.":
    "Engedélyezem az alkalmazások és lapok bezárását ennél a keretnél.",
  "No budgets yet.": "Még nincs keret.",
  "No notifications yet.": "Még nincs értesítés.",
  Title: "Cím",
  Message: "Szöveg",
  "Show notification": "Mikor jelenjen meg?",
  Icon: "Ikon",
  "Notification button": "Értesítés gombja",
  "No button": "Nincs gomb",
  "Open application": "Alkalmazás megnyitása",
  "Start Pomodoro": "Pomodoro indítása",
  Preview: "Előnézet",
  Closing: "Bezárás",
  "Default duration": "Alapértelmezett időtartam",
  "After a delay": "Megadott idő után",
  "Manual closing only": "Csak kézi bezárás",
  Seconds: "Másodperc",
  "Completed rounds today": "Mai befejezett körök",
  Presets: "Előre elkészített értesítések",
  "Focus minutes": "Fókusz (perc)",
  "Short break minutes": "Rövid szünet (perc)",
  "Long break minutes": "Hosszú szünet (perc)",
  "Rounds before long break": "Körök a hosszú szünetig",
  "Start focus": "Fókusz indítása",
  Pause: "Szüneteltetés",
  Continue: "Folytatás",
  Stop: "Leállítás",
  Ready: "Indításra kész",
  Running: "Fut",
  Paused: "Szüneteltetve",
  Completed: "Befejezve",
  Focus: "Fókusz",
  "Short break": "Rövid szünet",
  "Long break": "Hosszú szünet",
  "Completed rounds in total": "Összes befejezett kör",
  "Timer settings": "Időzítő beállításai",
  "0-minute breaks are skipped. Zero rounds means one focus session without a break or repetition.":
    "A 0 perces szünet kimarad. A 0 kör egyetlen fókuszszakaszt jelent, szünet és ismétlés nélkül.",
  "What should stay out of your focus session?":
    "Mit tiltsunk a fókusz idejére?",
  "Add group": "Csoport hozzáadása",
  Remove: "Eltávolítás",
  "From groups": "Csoportból",
  "Direct entry": "Külön hozzáadva",
  "Change inherited members in Budgets, or remove their group.":
    "A csoportból származó tagokat az Kereteknél módosíthatod, vagy vedd ki a csoportjukat.",
  "Day starts at": "Napváltás",
  "This day boundary applies to all budgets, statistics and daily reminders.":
    "Ez a naphatár minden keretre, statisztikára és napi értesítésre érvényes.",
  General: "Általános",
  Language: "Nyelv",
  "Track applications and websites": "Alkalmazások és weboldalak mérése",
  "Games folder": "Játékmappa",
  "Create game shortcuts": "Játékparancsikonok létrehozása",
  "Check for updates automatically": "Frissítések automatikus keresése",
  "Game sources": "Játékforrások",
  "One folder per line": "Mappánként egy sor",
  "Notification sound": "Értesítési hang",
  Default: "Alapértelmezett",
  Silent: "Néma",
  "Custom sound": "Egyéni hang",
  "Sound file path": "Hangfájl elérési útja",
  "Countdown appearance": "Számláló megjelenése",
  "Show countdown": "Számláló megjelenítése",
  "Text size": "Betűméret",
  "Opacity (%)": "Átlátszatlanság (%)",
  "Normal color": "Normál szín",
  "Warning color": "Figyelmeztetés színe",
  "Horizontal position (%)": "Vízszintes hely (%)",
  "Vertical position (%)": "Függőleges hely (%)",
  Monitor: "Monitor",
  Automatic: "Automatikus",
  "Use RTSS": "RTSS használata",
  "Detailed RTSS countdown": "Részletes RTSS-számláló",
  "Use countdown for early warning": "Korai figyelmeztetés helyett számláló",
  "Daily limit popup": "Értesítés a napi keret végén",
  "Use default appearance": "Alapértelmezett megjelenés használata",
  "Browser connection": "Böngészőkapcsolat",
  Paired: "Csatlakoztatva",
  "Change pairing": "Párosítás módosítása",
  "Computer name": "Számítógép neve",
  "Linked computers": "Összekapcsolt számítógépek",
  Connected: "Kapcsolódva",
  "Not connected": "Nincs csatlakoztatva",
  "Refresh data": "Adatok frissítése",
  "Only active-tab domains are measured. Private tabs, full URLs, page titles and content are not collected.":
    "Csak az aktív lap domainjét méri. Privát lapot, teljes URL-t, oldalcímet és tartalmat nem rögzít.",
  "The desktop application runs tracking and restrictions; keep it running in the background.":
    "A mérést és a korlátozásokat az asztali alkalmazás végzi; maradjon futva a háttérben.",
  Choose: "Kiválasztás",
  Add: "Hozzáadás",
  Save: "Mentés",
  "Restore preset": "Előkészített értesítés hozzáadása",
  "Today’s focus rounds": "Mai fókuszkörök",
  "No active countdown": "Nincs aktív visszaszámlálás",
  "Current website": "Aktuális weboldal",
  "Block during focus": "Tiltás fókusz alatt",
  "New focus session": "Új fókuszszakasz",
};
Object.assign(hu, {
  "Manage linked computers": "Összekapcsolt gépek kezelése",
  "Connection code": "Kapcsolódási kód",
  "Paste a connection code or reveal the current code":
    "Illessz be egy kódot, vagy jelenítsd meg a jelenlegit",
  "Enable synchronization": "Szinkronizálás engedélyezése",
  "Reveal code": "Kód megjelenítése",
  "New code": "Új kód",
  "Copy code": "Kód másolása",
  "Keep your code private. Anyone with it can link a computer.":
    "Tartsd titokban a kódot. Bárki, aki ismeri, csatlakoztathat egy számítógépet.",
  "Sync now": "Szinkronizálás most",
  "Signed in": "Bejelentkezve",
  "Not signed in": "Nincs bejelentkezve",
  "Working…": "Folyamatban…",
  "Sign out": "Kijelentkezés",
  "Sign in with GitHub": "Bejelentkezés GitHubbal",
  "Revoke connection code": "Kapcsolódási kód visszavonása",
  "Server copies are removed and linked computers stop synchronizing. Local history is preserved.":
    "A szerverpéldányok törlődnek, és az összekapcsolt gépek szinkronizálása leáll. A helyi előzmények megmaradnak.",
  Rename: "Átnevezés",
  "No linked computers yet.": "Még nincs összekapcsolt számítógép.",
  "Replace connection code": "Kapcsolódási kód cseréje",
});
Object.assign(hu, {
  "Restrict when the budget runs out": "Korlátozás a keret elfogyásakor",
  "Add website": "Weboldal hozzáadása",
  "Add game": "Játék hozzáadása",
  "Game name": "Játék neve",
  "Assign executable": "Alkalmazás hozzárendelése",
  "Uninstall game": "Játék eltávolítása",
  "Executable exclusions and assignments":
    "Alkalmazások kizárása és hozzárendelése",
  Assignment: "Hozzárendelés",
  "Enable at my own risk": "Engedélyezés saját felelősségre",
  "Display in protected games": "Megjelenítés védett játékokban",
  "Disable display in protected games":
    "Megjelenítés kikapcsolása védett játékokban",
  "I understand and accept the risk.": "Megértettem és elfogadom a kockázatot.",
  Updates: "Frissítések",
  "Download update": "Frissítés letöltése",
  "Check for updates": "Frissítések keresése",
  "Choose image": "Kép választása",
  "Choose an image smaller than 330 KB.": "Válassz 330 KB-nál kisebb képet.",
  "Advanced settings": "További beállítások",
  "More…": "Továbbiak…",
});
export function t(key) {
  return language === "hu" ? (nativeHu[key] ?? hu[key] ?? key) : key;
}
export const clone = (value) => structuredClone(value);
export const uid = () => crypto.randomUUID().replaceAll("-", "");
export const clock = (seconds) => {
  const s = Math.max(0, Math.ceil(seconds || 0));
  return (
    (s >= 3600
      ? `${Math.floor(s / 3600)
          .toString()
          .padStart(2, "0")}:`
      : "") +
    `${Math.floor((s % 3600) / 60)
      .toString()
      .padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`
  );
};
export const duration = (s) =>
  `${Math.floor((s || 0) / 3600)}${language === "hu" ? " ó" : "h"} ${Math.floor(((s || 0) % 3600) / 60)}${language === "hu" ? " p" : "m"}`;
export const timeText = (m) =>
  `${Math.floor(m / 60)
    .toString()
    .padStart(2, "0")}:${(m % 60).toString().padStart(2, "0")}`;
export const minutes = (value) => {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
};
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "style") Object.assign(node.style, value);
    else if (key in node) node[key] = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false)
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
  }
  return node;
}
export function button(text, click, kind = "") {
  return el("button", { type: "button", class: kind, onclick: click }, t(text));
}
export function note(text) {
  return el("p", { class: "hint" }, t(text));
}
export function field(
  text,
  value,
  change,
  { type = "text", options, min, max, step, placeholder, ...rest } = {},
) {
  let input;
  if (options) {
    input = el(
      "select",
      rest,
      options.map((option) => {
        const [v, label] = Array.isArray(option) ? option : [option, option];
        return el("option", { value: v }, t(label));
      }),
    );
    input.value = value;
  } else if (type === "textarea")
    input = el("textarea", { value, rows: 3, ...rest });
  else input = el("input", { type, value: value ?? "", ...rest });
  for (const [key, v] of Object.entries({ min, max, step, placeholder }))
    if (v !== undefined) input.setAttribute(key, v);
  input.addEventListener("input", () =>
    change(type === "number" ? Number(input.value) : input.value),
  );
  return el("label", { class: "field" }, t(text), input);
}
export function check(text, value, change) {
  return el(
    "label",
    { class: "check" },
    el("input", {
      type: "checkbox",
      checked: !!value,
      onchange: (e) => change(e.target.checked),
    }),
    t(text),
  );
}
export function card(...children) {
  return el("section", { class: "card" }, ...children);
}
export function icon(name) {
  const paths = {
    overview: "M3 17v4h18M7 14v3m5-9v9m5-13v13",
    activities: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
    clock: "M12 7v5l4 2",
    focus: "M12 2v3m0 14v3M2 12h3m14 0h3M7 12a5 5 0 1 0 10 0 5 5 0 0 0-10 0",
    bell: "M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 21h4",
    settings:
      "M10 3h4l1 3 3 1 2 3v4l-2 3-3 1-1 3h-4l-1-3-3-1-2-3v-4l2-3 3-1zM9 12a3 3 0 1 0 6 0 3 3 0 0 0-6 0",
    trash: "M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
    dots: "M5 12h.1M12 12h.1M19 12h.1",
    play: "m8 5 11 7-11 7z",
    folder: "M3 5h7l2 3h9v12H3z",
    refresh: "M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 14-1M19 16a8 8 0 0 1-14 1",
    moon: "M20 15A9 9 0 0 1 9 4 9 9 0 1 0 20 15",
    water: "M12 3c-3 5-7 9-7 13a7 7 0 0 0 14 0c0-4-4-8-7-13z",
    book: "M12 5v16M3 4h6l3 2 3-2h6v15h-6l-3 2-3-2H3z",
    stretch: "M12 2v3M3 8l9 3 9-3M12 11v5m0 0-6 6m6-6 6 6",
    check: "m4 12 5 5 11-12",
    heart: "M12 21 3 12C-2 4 8 0 12 7c4-7 14-3 9 5z",
    star: "m12 2 3 6 7 1-5 5 1 8-6-4-6 4 1-8-5-5 7-1z",
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  if (name === "clock") {
    const circle = document.createElementNS(svg.namespaceURI, "circle");
    for (const [k, v] of Object.entries({ cx: 12, cy: 12, r: 9 }))
      circle.setAttribute(k, v);
    svg.append(circle);
  }
  const path = document.createElementNS(svg.namespaceURI, "path");
  path.setAttribute("d", paths[name] || paths.bell);
  svg.append(path);
  return el("span", { class: "icon", "aria-hidden": "true" }, svg);
}
export async function api(action, data = {}, revision) {
  const { pairing } = await chrome.storage.local.get("pairing");
  if (
    !pairing ||
    !Number.isInteger(pairing.port) ||
    pairing.port < 1024 ||
    pairing.port > 65535 ||
    !/^[a-f0-9]{64}$/.test(pairing.token)
  )
    throw Error(t("Pair this browser first."));
  const fallback=async()=>{
    const result=await chrome.runtime.sendMessage({action:'continuity.control',command:action}).catch(()=>null);
    return result?.ok?result:null;
  };
  const connection=await chrome.storage.session.get('connected');
  if(connection.connected===false) {
    const offline=await fallback();if(offline) return offline;
  }
  let response;
  try {
    response = await fetch(`http://127.0.0.1:${pairing.port}/control`, {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(12000),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + pairing.token,
      },
      body: JSON.stringify({ action, data, revision, id: crypto.randomUUID() }),
    });
  } catch {
    const offline=await fallback();if(offline) return offline;
    throw Error(
      t(
        "The local application is unavailable. Start Keep Improving and try again.",
      ),
    );
  }
  if (!response.ok) {
    if(![401,403].includes(response.status)) {const offline=await fallback();if(offline) return offline;}
    throw Error(
      t(
        "The local application is unavailable. Start Keep Improving and try again.",
      ),
    );
  }
  const result = await response.json();
  if (!result.ok) {
    const error = Error(result.error || t("Invalid request."));
    error.conflict = result.conflict;
    throw error;
  }
  return result;
}
export function modal(title, content, actions = []) {
  const dialog = document.querySelector("#dialog");
  dialog.querySelector("#dialog-content").replaceChildren(
    el("h2", {}, t(title)),
    content,
    el(
      "div",
      { class: "footer" },
      ...actions,
      button("Cancel", () => dialog.close()),
    ),
  );
  dialog.showModal();
  return dialog;
}
export async function confirmAction(title, detail = "History is preserved.") {
  return new Promise((resolve) => {
    const dialog = modal(title, note(detail), [
      button(
        "Delete",
        () => {
          resolve(true);
          dialog.close();
        },
        "danger",
      ),
    ]);
    dialog.addEventListener("close", () => resolve(false), { once: true });
  });
}
export async function savePairing(code, browser) {
  let pairing;
  try {
    pairing = JSON.parse(code);
    if (
      !Number.isInteger(pairing.port) ||
      pairing.port < 1024 ||
      pairing.port > 65535 ||
      !/^[a-f0-9]{64}$/.test(pairing.token)
    )
      throw Error();
  } catch {
    throw Error(t("Invalid pairing code."));
  }
  await chrome.storage.local.set({
    pairing: { port: pairing.port, token: pairing.token },
    browser,
  });
}
