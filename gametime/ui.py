"""Small dark Tk interface. All state changes go through the main Tk thread."""
from datetime import datetime
from dataclasses import replace
import logging
import os
import time
from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import ttk, filedialog
import uuid
import winsound
import ctypes
import gc
from .model import Catalog, Game, norm, LAUNCHER_SOURCES
from .service import DiscoveryService
from .tracker import Tracker, Alert
from . import win32
from .i18n import tr, LANGUAGES

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
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(18, 9))
    style.map("TNotebook.Tab", background=[("selected", "#345579"), ("active", "#354760")])
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
    style.configure("Total.TLabel", font=("Segoe UI", 25, "bold"), foreground=BLUE)
    style.configure("TButton", background=PANEL, foreground=FG, padding=(10, 7), borderwidth=1)
    style.map("TButton", background=[("active", "#354760"), ("pressed", "#293d59")])
    style.configure("Play.TButton", background="#63e2ca", foreground="#10211e", font=("Segoe UI", 11, "bold"))
    style.map("Play.TButton", background=[("disabled", "#303540"), ("active", "#8aefdc")], foreground=[("disabled", MUTED)])
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
        self.notification_timer = None
        self.escape_attempts = set()
        self.closed = False
        self.last_rows = None
        self.launcher = None
        self.launching = None
        self.hidden_ids = store.hidden_ids()
        self.show_hidden = tk.BooleanVar(value=False)
        self.status_key = "Discovering games…"
        self.status_values = {}
        self.status = tk.StringVar(value=self.t(self.status_key))
        self.total_text = tk.StringVar(value="00:00:00")
        self.remaining_text = tk.StringVar()
        self.active_text = tk.StringVar(value=self.t("Active game: none"))
        root.title(self.t("Game Time Monitor"))
        root.geometry(f"{min(1100, root.winfo_screenwidth() - 80)}x{min(760, root.winfo_screenheight() - 100)}")
        root.minsize(850, 600)
        theme(root)
        root.protocol("WM_DELETE_WINDOW", root.withdraw)
        self._build()
        dark_title(root)
        try:
            root.iconbitmap(default=str(Path(__file__).with_name("app.ico")))
        except tk.TclError:
            log.warning("Application icon is unavailable")
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
            self.poll_launch()
        except Exception:
            log.exception("Tray event dispatch failed")
        if not self.closed:
            self.tray_timer = self.root.after(75, self.poll_tray)

    def _build(self):
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)
        bar = ttk.Frame(self.main_frame, padding=(18, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text=self.t("Game Time Monitor")).pack(side="left")
        self.language_choice = tk.StringVar(value=next(name for name, code in LANGUAGES.items() if code == self.settings.language))
        language = ttk.Combobox(bar, textvariable=self.language_choice, values=list(LANGUAGES), state="readonly", width=10)
        language.pack(side="right")
        language.bind("<<ComboboxSelected>>", lambda e: self.set_language(LANGUAGES[self.language_choice.get()]))
        ttk.Label(bar, text=self.t("Language / Nyelv")).pack(side="right", padx=8)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        frame = ttk.Frame(self.notebook, padding=18)
        self.notebook.add(frame, text="Gaming Hub")
        from .statistics_ui import StatisticsView
        self.statistics = StatisticsView(self.notebook, self)
        self.notebook.add(self.statistics, text=self.t("Statistics"))
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_changed)
        hero = ttk.Frame(frame)
        hero.pack(fill="x")
        title = ttk.Frame(hero)
        title.pack(side="left", anchor="n")
        ttk.Label(title, text="Gaming Hub", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text=self.t("Your games, play time and reminders in one place."), style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
        budget = ttk.Frame(hero)
        budget.pack(side="right")
        ttk.Label(budget, text=self.t("Today’s game time"), style="Muted.TLabel").pack(anchor="e")
        ttk.Label(budget, textvariable=self.total_text, style="Total.TLabel").pack(anchor="e")
        ttk.Label(frame, textvariable=self.remaining_text).pack(anchor="w")
        self.progress = ttk.Progressbar(frame, maximum=self.settings.limit_seconds)
        self.progress.pack(fill="x", pady=12)
        ttk.Label(frame, textvariable=self.active_text).pack(anchor="w", pady=(0, 12))
        library = ttk.Frame(frame)
        library.pack(fill="x", pady=(0, 10))
        self.search = tk.StringVar()
        ttk.Label(library, text=self.t("Search")).pack(side="left", padx=(0, 8))
        ttk.Entry(library, textvariable=self.search).pack(side="left", fill="x", expand=True)
        self.source_filter = tk.StringVar(value=self.t("All sources"))
        self.source_choices = {self.t("All sources"): None}
        self.source_menu = ttk.Combobox(library, textvariable=self.source_filter, values=list(self.source_choices), state="readonly", width=17)
        self.source_menu.pack(side="left", padx=10)
        self.source_menu.bind("<<ComboboxSelected>>", lambda e: self.refresh_view())
        self.launch_button = ttk.Button(library, text=self.t("▶ Play"), command=self.launch_selected,
                                        style="Play.TButton", width=16, state="disabled")
        self.launch_button.pack(side="right")
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("name", "source", "today", "state", "path"), show="headings", selectmode="browse", height=5)
        for key, label, width in [("name", "Game", 200), ("source", "Source", 100), ("today", "Today", 90),
                                  ("state", "Tracking", 110), ("path", "Installation folder", 310)]:
            self.tree.heading(key, text=self.t(label))
            self.tree.column(key, width=width, minwidth=60, stretch=key in ("name", "path"))
        self.tree.tag_configure("excluded", foreground=MUTED)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_launch_button())
        self.tree.bind("<Return>", lambda e: self.launch_selected())
        self.tree.bind("<Double-1>", self.double_click_game)
        self.search.trace_add("write", lambda *args: self.refresh_view())
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(14, 8))
        for index, (label, command) in enumerate([("Exclude / track", self.toggle_game), ("Add game", self.add_manual),
                               ("Assign EXE", self.assign_exe), ("EXE rules", self.rules_dialog),
                               ("Hide / restore", self.toggle_hidden), ("Uninstall game…", self.uninstall_game)]):
            ttk.Button(actions, text=self.t(label), command=command).grid(row=index//3, column=index%3, sticky="ew", padx=3, pady=3)
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        ttk.Checkbutton(frame, text=self.t("Show hidden games (hiding does not stop tracking)"),
                        variable=self.show_hidden, command=self.refresh_view).pack(anchor="w", pady=(0, 8))
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        ttk.Button(bottom, text=self.t("Settings"), command=self.settings_dialog).pack(side="left")
        ttk.Button(bottom, text=self.t("Test alert"), command=self.test_popup).pack(side="left", padx=6)
        ttk.Button(bottom, text=self.t("Open game folder"), command=self.open_game_folder).pack(side="left", padx=6)
        ttk.Button(bottom, text=self.t("Hide to tray"), command=self.root.withdraw).pack(side="right")
        ttk.Label(frame, textvariable=self.status, style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(12, 0))

    def t(self, text, **values):
        return tr(text, self.settings.language, **values)

    def set_status(self, text, **values):
        self.status_key = text
        self.status_values = values
        self.status.set(self.t(text, **values))

    def set_language(self, language):
        if language == self.settings.language:
            return
        current_tab = self.notebook.index(self.notebook.select())
        dates = self.statistics.start.get(), self.statistics.end.get(), self.statistics.selected_day
        search, source, selection = self.search.get(), self.source_choices.get(self.source_filter.get()), self.tree.selection()
        self.tracker.flush()
        settings = replace(self.settings, language=language).validate()
        self.store.save_settings(settings)
        self.settings = self.catalog.settings = settings
        self.main_frame.destroy()
        self.root.title(self.t("Game Time Monitor"))
        self.status.set(self.t(self.status_key, **self.status_values))
        self.last_rows = None
        self._build()
        self.statistics.start.set(dates[0])
        self.statistics.end.set(dates[1])
        self.statistics.selected_day = dates[2]
        self.notebook.select(current_tab)
        self.render()
        self.search.set(search)
        self.source_filter.set(next((label for label, value in self.source_choices.items() if value == source), self.t("All sources")))
        self.refresh_view()
        if selection and self.tree.exists(selection[0]):
            self.tree.selection_set(selection[0])
        self.update_launch_button()
        # Retired widgets contain Tcl variables in Python reference cycles.
        # Finalize them here, before a discovery worker could trigger GC.
        gc.collect()
        self.root.after_idle(gc.collect)

    def tab_changed(self, event=None):
        if self.notebook.select() == str(self.statistics):
            self.statistics.refresh()

    def show(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        win32.u.SetForegroundWindow(dark_title(self.root))

    def open_games(self):
        self.notebook.select(0)
        self.show()

    def open_game_folder(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
            return
        try:
            os.startfile(game.root)
        except OSError:
            self.message("The game's installation folder is unavailable.")

    def update_launch_button(self):
        game = self.selected()
        self.launch_button.configure(text=self.t("Starting…" if self.launching else "▶ Play"),
                                      state="normal" if game and game.installed and not self.launching else "disabled")

    def double_click_game(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.launch_selected()
        return "break"

    def launch_selected(self):
        game = self.selected()
        if self.launching:
            return "break"
        if not game:
            self.message("Select a game in the list first.")
            return "break"
        if not game.installed:
            self.message("This game is no longer installed. Refresh the library.")
            return "break"
        if self.launcher is None:
            from .launch import LaunchWorker
            self.launcher = LaunchWorker(self.data_dir)
        self.launching = game.id
        self.launcher.request(game, self.settings, self.catalog.rules, self.store.launch_executable(game.id))
        self.set_status("Preparing {name}…", name=game.name)
        self.update_launch_button()
        return "break"

    def poll_launch(self):
        if self.closed or self.launcher is None:
            return
        while not self.launcher.results.empty():
            game, plan, error = self.launcher.results.get_nowait()
            self.launching = None
            self.update_launch_button()
            if not error:
                try:
                    from .launch import execute
                    current = self.catalog.games.get(game.id)
                    if not current or not current.installed:
                        raise ValueError("This game is no longer installed. Refresh the library.")
                    execute(plan)
                    log.info("Game launch requested: game=%s kind=%s", game.id, plan.kind)
                    self.set_status("Launch requested: {name}. Play time starts when the game is in the foreground.", name=game.name)
                except (OSError, ValueError) as exc:
                    error = str(exc)
            if error:
                self.set_status("Could not start {name}.", name=game.name)
                self.message(self.t(error))

    def tray_menu(self):
        if self.closed:
            return
        items = [(1, "Open Game Time Monitor"), (2, "Open Gaming Hub"),
                                       (3, "Settings"), (4, "Refresh games and hub"),
                                       None, (5, "Exit monitor")]
        choice = self.tray.popup_menu([(item[0], self.t(item[1])) if item else None for item in items])
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

    def _dialog(self, title, size="550x250", transient=True):
        window = tk.Toplevel(self.root)
        window.configure(bg=BG)
        window.title(self.t(title))
        window.geometry(size)
        if transient and self.root.state() != "withdrawn":
            window.transient(self.root)
        dark_title(window)
        return window

    def message(self, text):
        window = self._dialog("Game Time Monitor", "560x220")
        ttk.Label(window, text=self.t(text), wraplength=510, padding=20).pack(fill="both", expand=True)
        ttk.Button(window, text=self.t("OK"), command=window.destroy).pack(pady=(0, 20))

    def prompt(self, title, label, initial=""):
        window = self._dialog(title)
        value, result = tk.StringVar(value=initial), []
        ttk.Label(window, text=self.t(label), padding=18, wraplength=500).pack(anchor="w")
        entry = ttk.Entry(window, textvariable=value)
        entry.pack(fill="x", padx=18)
        def accept():
            if value.get().strip():
                result.append(value.get().strip())
                window.destroy()
        ttk.Button(window, text=self.t("Save"), command=accept).pack(pady=20)
        window.bind("<Return>", lambda e: accept())
        window.bind("<Escape>", lambda e: window.destroy())
        entry.focus_set()
        window.grab_set()
        self.root.wait_window(window)
        return result[0] if result else None

    def selected(self):
        selected = self.tree.selection()
        if not selected:
            return None
        return self.catalog.games.get(selected[0]) or next((g for g in self.store.games() if g.id == selected[0]), None)

    def refresh_view(self):
        self.last_rows = None
        self.render()

    def toggle_hidden(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
            return
        self.store.set_hidden(game.id, game.id not in self.hidden_ids)
        self.hidden_ids = self.store.hidden_ids()
        self.refresh_view()

    def uninstall_game(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
            return
        from .removal import plan_removal, execute, localize_plan
        plan = localize_plan(plan_removal(game), game, self.settings.language)
        window = self._dialog(self.t("Uninstall game — {name}", name=game.name), "680x440")
        frame = ttk.Frame(window, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=plan.title, style="Title.TLabel", wraplength=590).pack(anchor="w")
        ttk.Label(frame, text=plan.instructions, wraplength=590).pack(fill="x", pady=14)
        ttk.Label(frame, text=self.t("Your play history will be kept. Hiding a game does not uninstall it."),
                  wraplength=590, style="Muted.TLabel").pack(anchor="w")
        status = tk.StringVar()
        ttk.Label(frame, textvariable=status, wraplength=590).pack(fill="x", pady=10)
        buttons = ttk.Frame(frame)
        buttons.pack(side="bottom", fill="x")
        def proceed():
            try:
                execute(plan)
                launch.configure(state="disabled")
                status.set(self.t("Opened. Complete the steps above in the publisher's window. You can then close this guide."))
                self.devices_changed()
            except (OSError, ValueError) as exc:
                status.set(self.t("Could not open the removal tool. Use Installed apps below. ") + str(exc))
        def installed_apps():
            try:
                from .removal import apps_plan
                execute(apps_plan(game))
            except OSError as exc:
                status.set(self.t("Open Windows Settings → Apps → Installed apps manually. ") + str(exc))
        launch = ttk.Button(buttons, text=self.t("Continue…"), command=proceed)
        launch.pack(side="left")
        ttk.Button(buttons, text=self.t("Installed apps"), command=installed_apps).pack(side="left", padx=8)
        ttk.Button(buttons, text=self.t("Close"), command=window.destroy).pack(side="right")
        window.bind("<Escape>", lambda e: window.destroy())
        window.grab_set()

    def toggle_game(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
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
        return filedialog.askopenfilename(parent=self.root, title=self.t("Choose application"),
                                           filetypes=[(self.t("Windows application"), "*.exe")])

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
            self.message("Browsers and launcher clients cannot be assigned to a game.")
            return
        name = self.prompt("Add game", "Game name:", Path(path).stem)
        if name:
            game = Game("manual:" + uuid.uuid4().hex, name, "Kézi", str(Path(path).parent))
            self.catalog.games[game.id] = game
            self.store.upsert([game])
            self.store.set_rule(path, game.id)
            self.store.set_launch_executable(game.id, path)
            self.refresh_rules()
            self.last_rows = None

    def assign_exe(self):
        game = self.selected()
        if not game:
            self.message("Select the game to assign this executable to first.")
            return
        path = self.pick_exe()
        if path:
            from .model import blocked
            if blocked(path):
                self.message("Browsers and launcher clients do not count as game time.")
                return
            self.store.set_rule(path, game.id)
            self.store.set_launch_executable(game.id, path)
            self.refresh_rules()

    def rules_dialog(self):
        window = self._dialog("Executable exclusions and assignments", "850x440")
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.t("Use Exclude / track in the main list to change tracking for an entire game.")).pack(anchor="w", pady=(0, 12))
        tree = ttk.Treeview(frame, columns=("path", "target"), show="headings")
        tree.heading("path", text=self.t("Application path"))
        tree.heading("target", text=self.t("Tracking"))
        tree.column("path", width=540)
        tree.column("target", width=230)
        tree.pack(fill="both", expand=True)
        def refresh():
            tree.delete(*tree.get_children())
            for index, (path, gid) in enumerate(self.store.rules().items()):
                name = self.catalog.games[gid].name if gid in self.catalog.games else gid
                tree.insert("", "end", iid=str(index), values=(path, name or self.t("Excluded")))
        def exclude():
            path = filedialog.askopenfilename(parent=window, title=self.t("Exclude application"), filetypes=[(self.t("Application"), "*.exe")])
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
        ttk.Button(buttons, text=self.t("Exclude EXE"), command=exclude).pack(side="left")
        ttk.Button(buttons, text=self.t("Remove selected rule"), command=remove).pack(side="left", padx=8)
        refresh()

    def settings_dialog(self):
        window = self._dialog("Settings", "740x700")
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        variables = {}
        for key, label, initial in [("limit", "Daily limit (minutes)", self.settings.limit_seconds / 60),
                                    ("warning", "Warn after (minutes)", self.settings.warning_seconds / 60),
                                    ("games", "Games and optional shortcuts folder (full path)", self.settings.games_root),
                                    ("steam", "Additional Steam installations (separated by semicolons)", ";".join(self.settings.steam_roots)),
                                    ("epic", "Additional Epic manifest folders (separated by semicolons)", ";".join(self.settings.epic_manifest_dirs)),
                                    ("ubisoft", "Additional Ubisoft Connect installations (separated by semicolons)", ";".join(self.settings.ubisoft_roots))]:
            ttk.Label(frame, text=self.t(label)).pack(anchor="w", pady=(7, 3))
            variables[key] = tk.StringVar(value=f"{initial:g}" if isinstance(initial, float) else initial)
            ttk.Entry(frame, textvariable=variables[key]).pack(fill="x")
        def browse():
            path = filedialog.askdirectory(parent=window, title=self.t("Gaming Hub"))
            if path:
                variables["games"].set(path)
        ttk.Button(frame, text=self.t("Browse Gaming Hub folder"), command=browse).pack(anchor="w", pady=10)
        hub_enabled = tk.BooleanVar(value=self.settings.hub_enabled)
        ttk.Checkbutton(frame, text=self.t("Also maintain a shortcuts folder (optional)"),
                        variable=hub_enabled).pack(anchor="w", pady=6)
        exclude_chess = tk.BooleanVar(value=self.settings.exclude_chess)
        ttk.Checkbutton(frame, text=self.t("Exclude chess games by default (optional personal preference)"),
                        variable=exclude_chess).pack(anchor="w", pady=6)
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
                                    hub_enabled.get(), exclude_chess.get(), self.settings.language).validate()
                self.tracker.flush()
                self.store.save_settings(settings)
                self.settings = self.catalog.settings = settings
                self.tracker.unclassified.clear()
                self.tracker.previous = None
                self.service.configure(settings)
                window.destroy()
            except (ValueError, OSError) as exc:
                error.set(self.t("Enter valid numbers for the warning and limit.")
                          if str(exc).startswith("could not convert string to float") else self.t(str(exc)))
        ttk.Button(frame, text=self.t("Save"), command=save).pack(anchor="e", pady=8)

    def popup(self, alert):
        if self.popup_window:
            return False
        # A transient of an iconic main window is withdrawn by Tk/Windows.
        # Alerts must remain independent even if the main window is hidden later.
        window = self._dialog("Game time alert", "590x260", transient=False)
        self.popup_window, self.popup_day = window, alert.day
        window.attributes("-topmost", True)
        title = "Time to stop playing" if alert.kind in ("limit", "session") else "Game time reminder"
        ttk.Label(window, text=self.t(title), style="Title.TLabel", padding=(22, 18, 22, 4)).pack(anchor="w")
        ttk.Label(window, text=alert.text, wraplength=540, padding=(22, 10)).pack(fill="x")
        def dismiss():
            self.popup_window = None
            self.popup_day = None
            window.destroy()
        ttk.Button(window, text=self.t(alert.button), command=dismiss).pack(pady=18)
        window.protocol("WM_DELETE_WINDOW", dismiss)
        window.bind("<Return>", lambda e: dismiss())
        window.bind("<Escape>", lambda e: dismiss())
        window.update_idletasks()
        x = (window.winfo_screenwidth() - 590) // 2
        y = (window.winfo_screenheight() - 260) // 2
        window.geometry(f"+{max(0, x)}+{max(0, y)}")
        window.deiconify()
        window.lift()
        hwnd = dark_title(window)
        try:
            foreground = win32.present_notification(hwnd)
            window.focus_force()
            window.update_idletasks()
            if not window.winfo_viewable() or not win32.u.IsWindowVisible(hwnd):
                raise RuntimeError("Notification window did not become visible")
        except Exception:
            log.exception("Notification presentation failed; will retry")
            dismiss()
            return False
        log.info("Notification presented: kind=%s day=%s main=%s foreground=%s",
                 alert.kind, alert.day, self.root.state(), foreground)
        try:
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except RuntimeError:
            log.warning("Notification sound unavailable; window remains visible")
        return True

    def test_popup(self):
        self.popup(Alert(datetime.now().date().isoformat(), (), "limit",
                         self.t("Test: Your daily game time limit has been reached. Time to finish playing."), self.t("OK, I’ll stop")))

    def notify(self, alert):
        """Let the current game process Escape before mapping the alert window."""
        escaped = False
        self.escape_attempts = {prior for prior in self.escape_attempts if prior.day == alert.day}
        if self.tracker.active and alert not in self.escape_attempts:
            self.escape_attempts.add(alert)
            try:
                current = win32.sample()
                if self.catalog.resolve(current.path) and current.interactive and current.identity == self.tracker.identity:
                    escaped = win32.escape_game(current.path, current.identity)
            except Exception:
                log.exception("Escape before notification failed")
        if escaped:
            log.info("Escape sent to tracked game; notification in 200 ms")
            self.notification_timer = self.root.after(200, lambda: self.finish_notification(alert))
        else:
            self.finish_notification(alert)

    def finish_notification(self, alert):
        self.notification_timer = None
        if self.closed or alert.day != datetime.now().date().isoformat():
            return
        if not self.tracker.alerts or self.tracker.alerts[0] != alert:
            return
        try:
            if self.popup(alert):
                self.tracker.delivered(alert)
                self.tracker.alerts.popleft()
        except Exception:
            log.exception("Notification failed")

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
                self.set_status(result[1])
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
        fingerprint = (self.settings.games_root, self.settings.hub_enabled, self.settings.exclude_chess,
                       tuple(sorted((g.id, g.name, g.root, g.metadata, g.installed) for g in self.catalog.games.values())),
                       tuple(sorted(self.catalog.rules.items())), tuple(sorted(self.catalog.overrides.items())))
        if fingerprint != self.hub_fingerprint:
            self.hub_fingerprint = fingerprint
            self.hub.request(self.settings, self.catalog.games.values(), self.catalog.rules, self.catalog.overrides)
        while not self.hub.results.empty():
            result = self.hub.results.get_nowait()
            if result.get("error"):
                self.set_status("Gaming Hub: " + result["error"])
        day = datetime.now().date().isoformat()
        totals = self.tracker.totals(day)
        total = sum(totals.values())
        self.total_text.set(duration(total))
        self.remaining_text.set(self.t("Time remaining: {remaining}  ·  Daily limit: {minutes:g} min",
                                       remaining=duration(self.settings.limit_seconds-total), minutes=self.settings.limit_seconds/60))
        self.active_text.set(self.t("Active game: {name}", name=self.tracker.active.name if self.tracker.active else self.t("none")))
        self.progress.configure(maximum=self.settings.limit_seconds, value=min(total, self.settings.limit_seconds))
        games = dict((g.id, g) for g in self.store.games())
        games.update(self.catalog.games)
        self.hidden_ids = self.store.hidden_ids()  # Also follows discovery's ID merges.
        rows = []
        selected_source = self.source_choices.get(self.source_filter.get())
        self.source_choices = {self.t("All sources"): None}
        for source in sorted({game.source for game in games.values()}):
            label = self.t("Manual") if source == "Kézi" else self.t("Games folder") if source == "Games" else source
            self.source_choices[label] = source
        self.source_menu.configure(values=list(self.source_choices))
        if selected_source not in self.source_choices.values():
            selected_source = None
            self.source_filter.set(self.t("All sources"))
        query = self.search.get().strip().casefold()
        for game in sorted(games.values(), key=lambda g: g.name.casefold()):
            if game.id in self.hidden_ids and not self.show_hidden.get():
                continue
            if not game.installed and game.id not in totals:
                continue
            if selected_source and game.source != selected_source:
                continue
            source_label = self.t("Manual") if game.source == "Kézi" else self.t("Games folder") if game.source == "Games" else game.source
            if query and query not in (game.name + " " + game.source + " " + source_label).casefold():
                continue
            enabled = self.catalog.enabled(game)
            state = self.t(("Tracked" if enabled else "Excluded") if game.installed else "Removed")
            if game.id in self.hidden_ids:
                state += " · " + self.t("hidden")
            rows.append((game.id, game.name, self.t("Manual") if game.source == "Kézi" else self.t("Games folder") if game.source == "Games" else game.source,
                         duration(totals.get(game.id, 0)), state, game.root))
        if rows != self.last_rows:
            selected = self.tree.selection()
            scroll = self.tree.yview()
            self.tree.delete(*self.tree.get_children())
            for gid, *values in rows:
                self.tree.insert("", "end", iid=gid, values=values, tags=("excluded",) if values[3] != self.t("Tracked") else ())
            if selected and self.tree.exists(selected[0]):
                self.tree.selection_set(selected[0])
            if scroll:
                self.tree.yview_moveto(scroll[0])
            self.last_rows = rows
        self.update_launch_button()
        self.tray.update(self.t("Game Time Monitor\nToday: {total} · remaining: {remaining}\nLeft click: open · right click: menu",
                                total=duration(total), remaining=duration(self.settings.limit_seconds-total)))
        if self.notebook.select() == str(self.statistics) and time.monotonic()-self.statistics.last_refresh >= 10:
            self.statistics.refresh()

    def tick(self):
        self.tick_timer = None
        if self.closed:
            return
        try:
            if (self.data_dir / "stop.request").exists():
                (self.data_dir / "stop.request").unlink(missing_ok=True)
                self.close()
                return
            if (self.data_dir / "show-hub.request").exists():
                (self.data_dir / "show-hub.request").unlink(missing_ok=True)
                self.open_games()
            elif (self.data_dir / "show.request").exists():
                (self.data_dir / "show.request").unlink(missing_ok=True)
                self.show()
            self.drain_discovery()
            self.tracker.tick(win32.sample())
            today = datetime.now().date().isoformat()
            if self.popup_window and self.popup_day != today:
                self.popup_window.destroy()
                self.popup_window = self.popup_day = None
            if not self.popup_window and self.notification_timer is None and self.tracker.alerts:
                alert = self.tracker.alerts[0]
                if alert.day == today:
                    self.notify(alert)
                elif alert.day != today:
                    self.tracker.alerts.popleft()
                    self.tracker.queued.difference_update((alert.day, key) for key in alert.keys)
            self.render()
        except Exception as exc:
            log.exception("Game time measurement failed")
            self.set_status("An error occurred; see monitor.log: " + str(exc))
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
        if self.notification_timer is not None:
            self.root.after_cancel(self.notification_timer)
            self.notification_timer = None
        self.tracker.close()
        self.service.close()
        self.hub.close()
        if self.launcher is not None:
            self.launcher.close()
        self.tray.close()
        self.root.destroy()
