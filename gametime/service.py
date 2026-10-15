import logging
import os
from pathlib import Path
from queue import Queue
import threading
import time
from .discovery import Discovery
from .model import norm, within

log = logging.getLogger(__name__)


class Debouncer:
    def __init__(self, quiet=1.2, maximum=5):
        self.quiet, self.maximum = quiet, maximum
        self.jobs = {}

    def add(self, key, now):
        first = self.jobs.get(key, (now, now))[0]
        self.jobs[key] = first, min(now + self.quiet, first + self.maximum)

    def ready(self, now):
        result = [key for key, (_, due) in self.jobs.items() if due <= now]
        for key in result:
            del self.jobs[key]
        return result


class DiscoveryService:
    def __init__(self, settings, watcher_factory=None, discovery=None):
        if watcher_factory is None:
            from .win32 import DirectoryWatcher
            watcher_factory = DirectoryWatcher
        self.factory = watcher_factory
        self.discovery = discovery or Discovery(settings)
        self.results = Queue()
        self.condition = threading.Condition()
        self.debounce = Debouncer()
        self.watchers = {}
        self.running = True
        self.retry_count = 0
        self.known_game_roots = set()
        self.reconfigure = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="game-discovery")

    def start(self):
        self.thread.start()

    def request(self, kind="launchers", group=""):
        with self.condition:
            self.debounce.add((kind, group), time.monotonic())
            self.condition.notify()

    def configure(self, settings):
        with self.condition:
            self.reconfigure = settings
            self.condition.notify()

    def _event(self, kind, target, path):
        targets = target if isinstance(target, tuple) else (target,)
        if path is not None and not any(within(path, t) or within(t, path) for t in targets):
            return
        if kind == "launchers":
            if path is None or Path(path).suffix.lower() in (".acf", ".vdf", ".item", ".dat", "") or Path(path).is_dir():
                self.request("launchers")
            return
        base = Path(self.discovery.settings.games_root)
        if path is None or not within(path, base) or norm(path) == norm(base):
            self.request("games")
        else:
            # Ignore save files, textures, logs, etc. A changed .exe or directory
            # only rechecks its one top-level game, never every Games directory.
            path = Path(path)
            if (path.suffix.lower() != ".exe" and path.suffix and not path.is_dir()
                    and norm(path) not in self.known_game_roots):
                return
            relative = os.path.relpath(path, base)
            parts = Path(relative).parts
            group = base / parts[0] if len(parts) > 1 or path.is_dir() or path.suffix.lower() != ".exe" else base
            self.request("games", str(group))

    def _watches(self):
        desired = self.discovery.watch_specs()
        for key in list(self.watchers):
            watcher, target = self.watchers[key]
            if key not in desired or watcher.error or not watcher.thread.is_alive() or desired[key] != target:
                watcher.close()
                del self.watchers[key]
        for key, target in desired.items():
            if key not in self.watchers:
                directory, recursive, kind = key
                watcher = self.factory(directory, recursive,
                                       lambda path, k=kind, t=target: self._event(k, t, path))
                self.watchers[key] = watcher, target
        errors = [f"{key[0]}: {w.error}" for key, (w, _) in self.watchers.items() if w.error]
        if errors:
            self.results.put(("status", "Fájlrendszerfigyelési hiba: " + "; ".join(errors)))

    def _scan(self, kind, group=""):
        try:
            if kind == "launchers":
                games = self.discovery.scan_launchers()
                self.results.put(("launchers", games, list(self.discovery.libraries), list(self.discovery.hints), list(self.discovery.errors)))
                self._watches()
                if self.discovery.errors:
                    self.results.put(("status", "Jegyzék olvasása késik; újrapróbálás folyamatban."))
                    # Retry only after a failing read, with a bounded rate.
                    self.retry_count += 1
                    if self.retry_count <= 6:
                        with self.condition:
                            now = time.monotonic()
                            self.debounce.jobs[("launchers", "")] = (now, now + min(2 ** self.retry_count, 30))
                else:
                    self.retry_count = 0
                    self.results.put(("status", "A játékfelismerés naprakész."))
            elif kind == "games":
                games = self.discovery.scan_games(group or None)
                if not group:
                    self.known_game_roots.clear()
                else:
                    self.known_game_roots.discard(norm(group))
                self.known_game_roots.update(norm(g.root) for g in games)
                self.results.put(("games", games, group))
                self._watches()
        except Exception as exc:
            log.exception("Játékfelismerési hiba")
            self.results.put(("status", "Játékfelismerési hiba: " + str(exc)))

    def _run(self):
        try:
            self.discovery.libraries_from_metadata()
            self._watches()  # Subscribe before the initial scan, closing startup races.
            self._scan("launchers")
            self._scan("games")
            last_repair = time.monotonic()
            while self.running:
                with self.condition:
                    if self.reconfigure:
                        self.discovery = Discovery(self.reconfigure)
                        self.reconfigure = None
                        self.debounce.jobs.clear()
                        self.known_game_roots.clear()
                        self.debounce.add(("launchers", ""), time.monotonic() - 2)
                        self.debounce.add(("games", ""), time.monotonic() - 2)
                    due = self.debounce.ready(time.monotonic())
                    if not due:
                        next_due = min((v[1] for v in self.debounce.jobs.values()), default=time.monotonic() + 30)
                        self.condition.wait(timeout=max(.05, min(30, next_due - time.monotonic())))
                for kind, group in due:
                    self._scan(kind, group)
                # Handle repair only; no periodic source or disk scans.
                if time.monotonic() - last_repair > 30:
                    broken = [key for key, (w, _) in self.watchers.items() if w.error or not w.thread.is_alive()]
                    if broken:
                        self._watches()
                        for _, _, kind in broken:
                            self.request(kind)
                    last_repair = time.monotonic()
        finally:
            for watcher, _ in list(self.watchers.values()):
                watcher.close()

    def close(self):
        with self.condition:
            self.running = False
            self.condition.notify()
        self.thread.join(timeout=5)
