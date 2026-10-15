"""Small dark Tk interface. All state changes go through the main Tk thread."""
from datetime import datetime
from dataclasses import replace
import logging
import os
from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import ttk, filedialog
import uuid
import winsound
import ctypes
from .model import Catalog, Game, norm, LAUNCHER_SOURCES
from .service import DiscoveryService
from .tracker import Tracker, Alert
from . import win32

log = logging.getLogger(__name__)
BG, PANEL, FG, MUTED, BLUE = "#15171b", "#23262d", "#f1f2f5", "#aeb5c2", "#86b9ff"


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def dark_title(window):
    window.update_idletasks()
    hwnd = win32.api(win32.u, "GetParent", [win32.W.HWND], win32.W.HWND)(window.winfo_id()) or window.winfo_id()
    try:
        fn = ctypes.WinDLL("dwmapi").DwmSetWindowAttribute
        fn.argtypes = [win32.W.HWND, win32.W.DWORD, ctypes.c_void_p, win32.W.DWORD]
        value = ctypes.c_int(1)
        fn(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        # Explicit Windows 11 caption colors also keep inactive titles dark.
        for attribute, color in ((35, 0x202020), (36, 0xF5F2F1)):
            caption = ctypes.c_uint(color)
            fn(hwnd, attribute, ctypes.byref(caption), ctypes.sizeof(caption))
    except OSError:
        pass
    return hwnd


def theme(root):
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", "#345579")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10), bordercolor="#414752")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
    style.configure("Total.TLabel", font=("Segoe UI", 25, "bold"), foreground=BLUE)
    style.configure("TButton", background=PANEL, foreground=FG, padding=(10, 7), borderwidth=1)
    style.map("TButton", background=[("active", "#354760"), ("pressed", "#293d59")])
    style.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=FG, padding=6)
    style.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
              selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)])
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG,
                    rowheight=29, borderwidth=0)
    style.configure("Treeview.Heading", background="#303540", foreground=FG, padding=7)
    style.map("Treeview", background=[("selected", "#345579")], foreground=[("selected", FG)])
    style.map("Treeview.Heading", background=[("active", "#414c60")])
    style.configure("Horizontal.TProgressbar", background=BLUE, troughcolor=PANEL, borderwidth=0)
    style.configure("Vertical.TScrollbar", background="#414752", troughcolor=BG, arrowcolor=FG)


class App:
    def __init__(self, root, store, data_dir, background=False, service=None, hub=None):
        self.root, self.store, self.data_dir = root, store, Path(data_dir)
        self.settings = store.settings()
        self.catalog = Catalog(self.settings, store.games(True), store.overrides(), store.rules())
        self.tracker = Tracker(store, self.catalog)
        from .hub import HubWorker
        self.hub = hub or HubWorker(data_dir)
        self.hub_fingerprint = None
        self.service = service or DiscoveryService(self.settings)
        # Library paths are cheap metadata reads; Games traversal runs on the worker.
        self.catalog.steam_libraries = self.service.discovery.libraries_from_metadata()
        self.popup_window = None
        self.popup_day = None
        self.closed = False
        self.last_rows = None
        self.status = tk.StringVar(value="Játékok felismerése…")
        self.total_text = tk.StringVar(value="00:00:00")
        self.remaining_text = tk.StringVar()
        self.active_text = tk.StringVar(value="Aktív játék: nincs")
        root.title("Játékidőfigyelő")
        root.geometry("1040x700")
        root.minsize(850, 600)
        theme(root)
        root.protocol("WM_DELETE_WINDOW", root.withdraw)
        self._build()
        dark_title(root)
        try:
            root.iconbitmap(default=str(Path(__file__).with_name("app.ico")))
        except tk.TclError:
            log.warning("Az alkalmazásikon nem olvasható")
        self.tray = win32.Tray(self.show, self.tray_menu, self.devices_changed)
        if background and self.tray.available:
            root.withdraw()
        self.refresh_manual_availability()
        self.service.start()
        self.tick_timer = root.after(200, self.tick)
        self.tray_timer = root.after(75, self.poll_tray)

    def poll_tray(self):
        self.tray_timer = None
        if self.closed:
            return
        try:
            self.tray.dispatch_pending()
        except Exception:
            log.exception("Tálcaesemény feldolgozási hiba")
        if not self.closed:
            self.tray_timer = self.root.after(75, self.poll_tray)

    def _build(self):
        frame = ttk.Frame(self.root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Mai játékidő", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.total_text, style="Total.TLabel").pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, textvariable=self.remaining_text).pack(anchor="w")
        self.progress = ttk.Progressbar(frame, maximum=self.settings.limit_seconds)
        self.progress.pack(fill="x", pady=12)
        ttk.Label(frame, textvariable=self.active_text).pack(anchor="w", pady=(0, 12))
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("name", "source", "today", "state", "path"), show="headings", selectmode="browse", height=5)
        for key, label, width in [("name", "Játék", 200), ("source", "Forrás", 65), ("today", "Ma", 90),
                                  ("state", "Besorolás", 110), ("path", "Telepítési hely", 310)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=60, stretch=key in ("name", "path"))
        self.tree.tag_configure("excluded", foreground=MUTED)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(14, 8))
        for label, command in [("Kizárás / engedélyezés", self.toggle_game), ("Új kézi játék", self.add_manual),
                               ("EXE hozzárendelése", self.assign_exe), ("Kivételek", self.rules_dialog)]:
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Beállítások", command=self.settings_dialog).pack(side="left")
        ttk.Button(bottom, text="Popup próba", command=self.test_popup).pack(side="left", padx=6)
        ttk.Button(bottom, text="Games mappa", command=self.open_games).pack(side="left", padx=6)
        ttk.Button(bottom, text="Tálcára", command=self.root.withdraw).pack(side="right")
        ttk.Label(frame, textvariable=self.status, style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(12, 0))

    def show(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        win32.u.SetForegroundWindow(dark_title(self.root))

    def open_games(self):
        try:
            os.startfile(self.settings.games_root)
        except OSError:
            self.message("A Games mappa még nem érhető el. Ellenőrizd az útvonalat a beállításokban.")

    def tray_menu(self):
        if self.closed:
            return
        choice = self.tray.popup_menu([(1, "Játékidőfigyelő megnyitása"), (2, "Gaming Hub megnyitása"),
                                       (3, "Beállítások"), (4, "Játéklista és hub frissítése"),
                                       None, (5, "Kilépés a figyelőből")])
        action = {1: self.show, 2: self.open_games, 3: self.settings_dialog,
                  4: self.refresh_sources, 5: self.close}.get(choice)
        if action:
            action()

    def refresh_sources(self):
        self.devices_changed()
        self.hub_fingerprint = None

    def refresh_manual_availability(self):
        games = [game for game in self.store.games() if game.source == "Kézi"
                 and any(gid == game.id for gid in self.catalog.rules.values())]
        changed = []
        for game in games:
            paths = [path for path, gid in self.catalog.rules.items() if gid == game.id]
            available = any(Path(path).is_file() for path in paths)
            current = replace(game, installed=available)
            self.catalog.games[game.id] = current
            if bool(game.installed) != available:
                changed.append(current)
        if changed:
            self.tracker.flush()
            self.store.upsert(changed)
            self.last_rows = None
        self.service.watch_manual(games, self.catalog.rules)

    def devices_changed(self):
        self.service.request("launchers")
        self.service.request("games")
        self.service.request("manual")

    def _dialog(self, title, size="550x250"):
        window = tk.Toplevel(self.root)
        window.configure(bg=BG)
        window.title(title)
        window.geometry(size)
        if self.root.state() != "withdrawn":
            window.transient(self.root)
        dark_title(window)
        return window

    def message(self, text):
        window = self._dialog("Játékidőfigyelő", "560x220")
        ttk.Label(window, text=text, wraplength=510, padding=20).pack(fill="both", expand=True)
        ttk.Button(window, text="Rendben", command=window.destroy).pack(pady=(0, 20))

    def prompt(self, title, label, initial=""):
        window = self._dialog(title)
        value, result = tk.StringVar(value=initial), []
        ttk.Label(window, text=label, padding=18, wraplength=500).pack(anchor="w")
        entry = ttk.Entry(window, textvariable=value)
        entry.pack(fill="x", padx=18)
        def accept():
            if value.get().strip():
                result.append(value.get().strip())
                window.destroy()
        ttk.Button(window, text="Mentés", command=accept).pack(pady=20)
        window.bind("<Return>", lambda e: accept())
        window.bind("<Escape>", lambda e: window.destroy())
        entry.focus_set()
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def selected(self):
        selected = self.tree.selection()
        return self.catalog.games.get(selected[0]) if selected else None

    def toggle_game(self):
        game = self.selected()
        if not game:
            self.message("Válassz ki egy játékot a listából.")
            return
        self.tracker.flush()
        enabled = not self.catalog.enabled(game)
        self.store.set_enabled(game.id, enabled)
        self.catalog.overrides[game.id] = enabled
        self.tracker.unclassified.clear()  # A correction applies from now on.
        self.tracker.previous = None
        self.last_rows = None
        self.render()

    def pick_exe(self):
        return filedialog.askopenfilename(parent=self.root, title="Alkalmazás kiválasztása",
                                           filetypes=[("Windows alkalmazás", "*.exe")])

    def refresh_rules(self):
        self.tracker.flush()
        self.catalog.rules = self.store.rules()
        self.refresh_manual_availability()
        self.tracker.unclassified.clear()
        self.tracker.previous = None

    def add_manual(self):
        path = self.pick_exe()
        if not path:
            return
        from .model import blocked
        if blocked(path):
            self.message("A böngészők és a Steam/Epic kezelőfelülete nem sorolható játékhoz.")
            return
        name = self.prompt("Kézi játék", "Játék neve:", Path(path).stem)
        if name:
            game = Game("manual:" + uuid.uuid4().hex, name, "Kézi", str(Path(path).parent))
            self.catalog.games[game.id] = game
            self.store.upsert([game])
            self.store.set_rule(path, game.id)
            self.refresh_rules()
            self.last_rows = None

    def assign_exe(self):
        game = self.selected()
        if not game:
            self.message("Előbb válaszd ki azt a játékot, amelyhez a futtatható fájlt rendeled.")
            return
        path = self.pick_exe()
        if path:
            from .model import blocked
            if blocked(path):
                self.message("A böngésző és a Steam/Epic kezelőfelülete nem számít játékidőnek.")
                return
            self.store.set_rule(path, game.id)
            self.refresh_rules()

    def rules_dialog(self):
        window = self._dialog("Alkalmazáskivételek és hozzárendelések", "850x440")
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="A teljes játék kizárása a főablak listájában is módosítható.").pack(anchor="w", pady=(0, 12))
        tree = ttk.Treeview(frame, columns=("path", "target"), show="headings")
        tree.heading("path", text="Alkalmazás útvonala")
        tree.heading("target", text="Besorolás")
        tree.column("path", width=540)
        tree.column("target", width=230)
        tree.pack(fill="both", expand=True)
        def refresh():
            tree.delete(*tree.get_children())
            for index, (path, gid) in enumerate(self.store.rules().items()):
                name = self.catalog.games[gid].name if gid in self.catalog.games else gid
                tree.insert("", "end", iid=str(index), values=(path, name or "Kizárva"))
        def exclude():
            path = filedialog.askopenfilename(parent=window, title="Kizárandó alkalmazás", filetypes=[("Alkalmazás", "*.exe")])
            if path:
                self.store.set_rule(path, None)
                self.refresh_rules()
                refresh()
        def remove():
            selected = tree.selection()
            if selected:
                self.store.delete_rule(tree.item(selected[0], "values")[0])
                self.refresh_rules()
                refresh()
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=12)
        ttk.Button(buttons, text="EXE kizárása", command=exclude).pack(side="left")
        ttk.Button(buttons, text="Kijelölt szabály törlése", command=remove).pack(side="left", padx=8)
        refresh()

    def settings_dialog(self):
        window = self._dialog("Beállítások", "700x620")
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        variables = {}
        for key, label, initial in [("limit", "Napi keret (perc)", self.settings.limit_seconds / 60),
                                    ("warning", "Előzetes figyelmeztetés ennyi perc után", self.settings.warning_seconds / 60),
                                    ("games", "Games mappa teljes útvonala", self.settings.games_root),
                                    ("steam", "További Steam-telepítések (pontosvesszővel)", ";".join(self.settings.steam_roots)),
                                    ("epic", "További Epic-jegyzékmappák (pontosvesszővel)", ";".join(self.settings.epic_manifest_dirs)),
                                    ("ubisoft", "További Ubisoft Connect-telepítések (pontosvesszővel)", ";".join(self.settings.ubisoft_roots))]:
            ttk.Label(frame, text=label).pack(anchor="w", pady=(7, 3))
            variables[key] = tk.StringVar(value=f"{initial:g}" if isinstance(initial, float) else initial)
            ttk.Entry(frame, textvariable=variables[key]).pack(fill="x")
        def browse():
            path = filedialog.askdirectory(parent=window, title="Games mappa")
            if path:
                variables["games"].set(path)
        ttk.Button(frame, text="Games mappa tallózása", command=browse).pack(anchor="w", pady=10)
        hub_enabled = tk.BooleanVar(value=self.settings.hub_enabled)
        ttk.Checkbutton(frame, text="Gaming Hub: a játékparancsikonok automatikus frissítése",
                        variable=hub_enabled).pack(anchor="w", pady=6)
        error = tk.StringVar()
        ttk.Label(frame, textvariable=error, foreground="#ffb3b3", wraplength=650).pack(anchor="w")
        def save():
            try:
                from .model import Settings
                settings = Settings(variables["games"].get().strip(),
                                    float(variables["warning"].get().replace(",", ".")) * 60,
                                    float(variables["limit"].get().replace(",", ".")) * 60,
                                    [p.strip() for p in variables["steam"].get().split(";") if p.strip()],
                                    [p.strip() for p in variables["epic"].get().split(";") if p.strip()],
                                    [p.strip() for p in variables["ubisoft"].get().split(";") if p.strip()],
                                    hub_enabled.get()).validate()
                self.tracker.flush()
                self.store.save_settings(settings)
                self.settings = self.catalog.settings = settings
                self.tracker.unclassified.clear()
                self.tracker.previous = None
                self.service.configure(settings)
                window.destroy()
            except (ValueError, OSError) as exc:
                error.set(str(exc))
        ttk.Button(frame, text="Mentés", command=save).pack(anchor="e", pady=8)

    def popup(self, alert):
        if self.popup_window:
            return False
        window = self._dialog("Játékidő – figyelmeztetés", "590x260")
        self.popup_window, self.popup_day = window, alert.day
        window.attributes("-topmost", True)
        title = "Mára elég volt" if alert.kind in ("limit", "session") else "Játékidő emlékeztető"
        ttk.Label(window, text=title, style="Title.TLabel", padding=(22, 18, 22, 4)).pack(anchor="w")
        ttk.Label(window, text=alert.text, wraplength=540, padding=(22, 10)).pack(fill="x")
        def dismiss():
            self.popup_window = None
            self.popup_day = None
            window.destroy()
        ttk.Button(window, text=alert.button, command=dismiss).pack(pady=18)
        window.protocol("WM_DELETE_WINDOW", dismiss)
        window.bind("<Return>", lambda e: dismiss())
        window.bind("<Escape>", lambda e: dismiss())
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 590) // 2
        y = (window.winfo_screenheight() - 260) // 2
        window.geometry(f"+{max(0, x)}+{max(0, y)}")
        window.lift()
        hwnd = dark_title(window)
        win32.u.SetForegroundWindow(hwnd)
        window.focus_force()
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        return True

    def test_popup(self):
        self.popup(Alert(datetime.now().date().isoformat(), (), "limit",
                         "Próba: Lejárt a mai 2 órás játékidőd. Ideje befejezni a játékot.", "Rendben, befejezem"))

    def drain_discovery(self):
        while True:
            try:
                result = self.service.results.get_nowait()
            except Empty:
                break
            kind = result[0]
            if kind == "availability":
                self.refresh_manual_availability()
                self.hub_fingerprint = None
            elif kind == "manual":
                self.refresh_manual_availability()
            elif kind == "shortcuts":
                self.hub_fingerprint = None
            elif kind == "status":
                self.status.set(result[1])
            elif kind == "launchers":
                from .discovery import preserve_unreadable
                _, games, libraries, hints, errors, ubisoft_roots, riot_hints = result
                games = preserve_unreadable(games, self.catalog.games.values(), errors)
                self.catalog.steam_libraries, self.catalog.epic_hints = libraries, hints
                self.catalog.ubisoft_libraries = ubisoft_roots
                self.catalog.riot_hints = riot_hints
                self.tracker.reconcile(games, lambda g: g.source in LAUNCHER_SOURCES)
                self.refresh_manual_availability()
                self.last_rows = None
            elif kind == "games":
                _, games, group = result
                self.tracker.reconcile(games, lambda g, p=group: g.source == "Games" and (not p or norm(g.root) == norm(p)))
                self.last_rows = None

    def render(self):
        fingerprint = (self.settings.games_root, self.settings.hub_enabled,
                       tuple(sorted((g.id, g.name, g.root, g.metadata, g.installed) for g in self.catalog.games.values())),
                       tuple(sorted(self.catalog.rules.items())), tuple(sorted(self.catalog.overrides.items())))
        if fingerprint != self.hub_fingerprint:
            self.hub_fingerprint = fingerprint
            self.hub.request(self.settings, self.catalog.games.values(), self.catalog.rules, self.catalog.overrides)
        while not self.hub.results.empty():
            result = self.hub.results.get_nowait()
            if result.get("error"):
                self.status.set("Gaming Hub: " + result["error"])
        day = datetime.now().date().isoformat()
        totals = self.tracker.totals(day)
        total = sum(totals.values())
        self.total_text.set(duration(total))
        self.remaining_text.set(f"Hátralévő idő: {duration(self.settings.limit_seconds - total)}  ·  Napi keret: {self.settings.limit_seconds / 60:g} perc")
        self.active_text.set("Aktív játék: " + (self.tracker.active.name if self.tracker.active else "nincs"))
        self.progress.configure(maximum=self.settings.limit_seconds, value=min(total, self.settings.limit_seconds))
        games = dict((g.id, g) for g in self.store.games())
        games.update(self.catalog.games)
        rows = []
        for game in sorted(games.values(), key=lambda g: g.name.casefold()):
            if not game.installed and game.id not in totals:
                continue
            enabled = self.catalog.enabled(game)
            state = ("Figyelve" if enabled else "Kizárva") if game.installed else "Eltávolítva"
            rows.append((game.id, game.name, game.source, duration(totals.get(game.id, 0)), state, game.root))
        if rows != self.last_rows:
            selected = self.tree.selection()
            scroll = self.tree.yview()
            self.tree.delete(*self.tree.get_children())
            for gid, *values in rows:
                self.tree.insert("", "end", iid=gid, values=values, tags=("excluded",) if values[3] != "Figyelve" else ())
            if selected and self.tree.exists(selected[0]):
                self.tree.selection_set(selected[0])
            if scroll:
                self.tree.yview_moveto(scroll[0])
            self.last_rows = rows
        self.tray.update(f"Játékidőfigyelő\nMa: {duration(total)} · hátra: {duration(self.settings.limit_seconds - total)}\nBal kattintás: megnyitás · jobb: menü")

    def tick(self):
        self.tick_timer = None
        if self.closed:
            return
        try:
            if (self.data_dir / "stop.request").exists():
                (self.data_dir / "stop.request").unlink(missing_ok=True)
                self.close()
                return
            if (self.data_dir / "show.request").exists():
                (self.data_dir / "show.request").unlink(missing_ok=True)
                self.show()
            self.drain_discovery()
            self.tracker.tick(win32.sample())
            today = datetime.now().date().isoformat()
            if self.popup_window and self.popup_day != today:
                self.popup_window.destroy()
                self.popup_window = self.popup_day = None
            if not self.popup_window and self.tracker.alerts:
                alert = self.tracker.alerts[0]
                if alert.day == today and self.popup(alert):
                    self.tracker.delivered(alert)
                    self.tracker.alerts.popleft()
                elif alert.day != today:
                    self.tracker.alerts.popleft()
                    self.tracker.queued.difference_update((alert.day, key) for key in alert.keys)
            self.render()
        except Exception as exc:
            log.exception("Játékidő-mérési hiba")
            self.status.set("Hiba történt; részletek a monitor.log fájlban: " + str(exc))
            self.tracker.previous = None
        self.tick_timer = self.root.after(1000, self.tick)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.tick_timer is not None:
            self.root.after_cancel(self.tick_timer)
            self.tick_timer = None
        if self.tray_timer is not None:
            self.root.after_cancel(self.tray_timer)
            self.tray_timer = None
        self.tracker.close()
        self.service.close()
        self.hub.close()
        self.tray.close()
        self.root.destroy()
