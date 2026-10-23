import logging
import os
from pathlib import Path
from queue import Queue
import threading
import time
from .discovery import Discovery
from .model import norm, within
from .background import BackgroundFailures

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
    def __init__(self, settings, watcher_factory=None, discovery=None, registry_factory=None):
        if watcher_factory is None:
            from .win32 import DirectoryWatcher
            watcher_factory = DirectoryWatcher
        self.factory = watcher_factory
        self.registry_factory = registry_factory
        self.discovery = discovery or Discovery(settings, minecraft=True)
        self.results = Queue()
        self.condition = threading.Condition()
        self.debounce = Debouncer()
        self.watchers = {}
        self.registry_watchers = {}
        self.running = True
        self.problems = BackgroundFailures()
        self._problem_visible = False
        self._watch_retry = False
        self.known_game_roots = set()
        self.reconfigure = None
        self.manual_specs = {}
        self.manual_pending = None
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

    def watch_manual(self, games, rules):
        """Watch exact manually assigned EXEs and their installation roots only."""
        wanted = {}
        for game in games:
            if game.source != "Kézi":
                continue
            exes = [path for path, gid in rules.items() if gid == game.id]
            if not exes:
                continue  # Superseded manual records have no remaining assignments.
            targets = exes + [game.root]
            for target in targets:
                parent = Path(target).parent
                # WindowsApps' container is protected; the package's EXE directory
                # itself still reports deletion without opening the container.
                if parent.name.lower() == "windowsapps":
                    continue
                wanted.setdefault(str(parent), set()).add(str(target))
        wanted = {key: tuple(sorted(values)) for key, values in wanted.items()}
        with self.condition:
            if wanted != (self.manual_pending if self.manual_pending is not None else self.manual_specs):
                self.manual_pending = wanted
                self.condition.notify()

    def _event(self, kind, target, path):
        targets = target if isinstance(target, tuple) else (target,)
        if path is not None and not any(within(path, t) or within(t, path) for t in targets):
            return
        if kind in ("manual", "installs"):
            if path is None or any(norm(path) == norm(t) or within(t, path) for t in targets):
                self.request(kind)
            return
        if kind == "shortcuts":
            if path is None or Path(path).suffix.lower() in (".lnk", ".url", "") or Path(path).is_dir():
                self.request("shortcuts")
            return
        if kind in ("launchers", "riot", "publishers"):
            suffixes = ((".yaml", ".json", "") if kind == "riot" else
                        (".sqlite", ".sqlite-wal", ".sqlite-shm", ".db", ".config", ".xml", "") if kind == "publishers" else
                        (".acf", ".vdf", ".item", ".dat", ""))
            if (path is None or Path(path).suffix.lower() in suffixes or Path(path).is_dir()
                    or (kind == "riot" and norm(Path(path).parent) == norm(self.discovery.riot.metadata_root))):
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
        try:
            errors = self._configure_watches()
        except Exception as exc:
            log.exception("Could not update installation watchers")
            errors = [str(exc)]
        self._watch_retry = bool(errors)
        self._problem("watchers", errors)

    def _configure_watches(self):
        errors = []
        desired = self.discovery.watch_specs()
        for directory, targets in self.manual_specs.items():
            existing = Path(directory)
            while not existing.is_dir() and existing.parent != existing:
                existing = existing.parent
            if existing.name.lower() == "windowsapps":
                continue
            if existing.is_dir():
                key = (str(existing), False, "manual")
                desired[key] = tuple(sorted(set(desired.get(key, ())) | set(targets)))
        for key in list(self.watchers):
            watcher, target = self.watchers[key]
            if key not in desired or watcher.error or not watcher.thread.is_alive() or desired[key] != target:
                if key in desired and (watcher.error or not watcher.thread.is_alive()):
                    errors.append(f"{key[0]}: {watcher.error or 'watcher stopped'}")
                watcher.close()
                del self.watchers[key]
        for key, target in desired.items():
            if key not in self.watchers:
                directory, recursive, kind = key
                try:
                    watcher = self.factory(directory, recursive,
                                           lambda path, k=kind, t=target: self._event(k, t, path))
                    self.watchers[key] = watcher, target
                except Exception as exc:
                    log.exception("Could not start installation watcher: %s", directory)
                    errors.append(str(exc))
        registry_specs = self.discovery.registry_watch_specs()
        for spec in list(self.registry_watchers):
            watcher = self.registry_watchers[spec]
            if spec not in registry_specs or watcher.error or not watcher.thread.is_alive():
                if spec in registry_specs and (watcher.error or not watcher.thread.is_alive()):
                    errors.append(f"{spec}: {watcher.error or 'watcher stopped'}")
                watcher.close()
                del self.registry_watchers[spec]
        for spec in registry_specs:
            if spec not in self.registry_watchers:
                if self.registry_factory is None:
                    from .win32 import RegistryWatcher
                    self.registry_factory = RegistryWatcher
                try:
                    self.registry_watchers[spec] = self.registry_factory(*spec, lambda: self.request("launchers"))
                except Exception as exc:
                    log.exception("Could not start installation registry watcher: %s", spec)
                    errors.append(str(exc))
        errors.extend(f"{key[0]}: {w.error or 'watcher stopped'}" for key, (w, _) in self.watchers.items()
                      if w.error or not w.thread.is_alive())
        errors.extend(f"{spec}: {w.error or 'watcher stopped'}" for spec, w in self.registry_watchers.items()
                      if w.error or not w.thread.is_alive())
        return errors

    def _problem(self, key, errors):
        recovering = key in self.problems.failures and not errors
        attempt = self.problems.update(key, bool(errors))
        if errors:
            log.warning("Background discovery issue (%s), attempt %d: %s", key, attempt, errors)
        elif recovering:
            log.info("Background discovery recovered: %s", key)
            if isinstance(key, tuple):
                with self.condition:
                    self.debounce.jobs.pop(key, None)
        visible = bool(self.problems.reported)
        if visible != self._problem_visible:
            self._problem_visible = visible
            self.results.put(("discovery_problem", visible))
        return attempt

    def _retry(self, kind, group, attempt):
        first = self.problems.failures[(kind, group)][0]
        remaining = first + self.problems.PERSISTENT_SECONDS - time.monotonic()
        if attempt <= self.problems.MAX_RETRIES or remaining > 0:
            with self.condition:
                now = time.monotonic()
                due = now + (self.problems.retry_delay(attempt) if attempt <= self.problems.MAX_RETRIES else remaining)
                existing = self.debounce.jobs.get((kind, group))
                if existing is None or due < existing[1]:
                    self.debounce.jobs[(kind, group)] = now, due
                self.condition.notify()

    def _scan(self, kind, group=""):
        try:
            if kind == "installs":
                self._scan("launchers")
                self.results.put(("availability",))
            elif kind == "manual":
                self._watches()
                self.results.put(("manual",))
            elif kind == "shortcuts":
                self.results.put(("shortcuts",))
            elif kind == "launchers":
                games = self.discovery.scan_launchers()
                self.results.put(("launchers", games, list(self.discovery.libraries), list(self.discovery.hints),
                                  list(self.discovery.errors), list(self.discovery.ubisoft_game_roots),
                                  list(self.discovery.riot_hints)))
                self._watches()
                attempt = self._problem((kind, group), self.discovery.errors)
                if attempt:
                    self._retry(kind, group, attempt)
            elif kind == "games":
                games = self.discovery.scan_games(group or None)
                if not group:
                    self.known_game_roots.clear()
                else:
                    self.known_game_roots.discard(norm(group))
                self.known_game_roots.update(norm(g.root) for g in games)
                self.results.put(("games", games, group))
                self._watches()
            if kind != "launchers":
                self._problem((kind, group), None)
                if kind == "games" and not group:
                    for key in list(self.problems.failures):
                        if isinstance(key, tuple) and key[0] == "games":
                            self._problem(key, None)
        except Exception as exc:
            log.exception("Game discovery failed")
            attempt = self._problem((kind, group), [str(exc)])
            self._retry(kind, group, attempt)

    def _run(self):
        try:
            try:
                self.discovery.libraries_from_metadata()
            except Exception:
                log.exception("Initial installation metadata read failed; retrying in discovery")
            self._watches()  # Subscribe before the initial scan, closing startup races.
            self._scan("launchers")
            self._scan("games")
            last_repair = time.monotonic()
            while self.running:
                with self.condition:
                    if self.manual_pending is not None:
                        self.manual_specs, self.manual_pending = self.manual_pending, None
                        self.debounce.add(("manual", ""), time.monotonic() - 2)
                    if self.reconfigure:
                        self.discovery = Discovery(self.reconfigure, minecraft=True)
                        self.reconfigure = None
                        self.debounce.jobs.clear()
                        self.known_game_roots.clear()
                        self.problems = BackgroundFailures()
                        self._problem("watchers", None)
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
                    registry_broken = any(w.error or not w.thread.is_alive() for w in self.registry_watchers.values())
                    if broken or registry_broken or self._watch_retry:
                        self._watches()
                        for _, _, kind in broken:
                            self.request(kind)
                        if registry_broken:
                            self.request("launchers")
                    last_repair = time.monotonic()
        finally:
            for watcher, _ in list(self.watchers.values()):
                watcher.close()
            for watcher in list(self.registry_watchers.values()):
                watcher.close()

    def close(self):
        with self.condition:
            self.running = False
            self.condition.notify()
        self.thread.join(timeout=5)
