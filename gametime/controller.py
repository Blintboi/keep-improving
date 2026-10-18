"""UI-neutral monitor actions shared by the Qt interface and regression fixture."""
from dataclasses import replace
from datetime import datetime
import logging
import os
from pathlib import Path
from queue import Empty
from .model import norm, LAUNCHER_SOURCES, popup_required
from .tracker import Alert
from . import win32

log=logging.getLogger(__name__)

class MonitorActions:
    RESTRICTION_GRACE_SECONDS = 10

    def sync_hub(self):
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
            self.tray_timer = self.call_later(75, self.poll_tray)


    def open_game_folder(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
            return
        try:
            os.startfile(game.root)
        except OSError:
            self.message("The game's installation folder is unavailable.")


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
        if self.launch_restricted(game):
            self.restriction_notice()
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
                    if self.launch_restricted(current):
                        self.restriction_notice()
                        continue
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


    def toggle_hidden(self):
        game = self.selected()
        if not game:
            self.message("Select a game in the list first.")
            return
        self.store.set_hidden(game.id, game.id not in self.hidden_ids)
        self.hidden_ids = self.store.hidden_ids()
        self.refresh_view()


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


    def refresh_rules(self):
        self.tracker.flush()
        self.catalog.rules = self.store.rules()
        self.refresh_manual_availability()
        self.tracker.unclassified.clear()
        self.tracker.previous = None


    def test_popup(self):
        self.popup(Alert(datetime.now().date().isoformat(), (), "limit",
                         self.t("Test: Your daily game time limit has been reached. Time to finish playing."), self.t("OK, I’ll stop")))


    def consume_silent_alert(self, alert):
        # A color warning counts as delivered without Escape, sound or a popup.
        # Keep the original warning if the optional renderer failed to initialize.
        required = popup_required(self.settings, alert.kind)
        if alert.kind == "warning" and getattr(self, "overlay_failed", False):
            required = True
        if self.restriction_reached(alert.day):
            required = False  # The persistent restriction notice replaces queued reminders.
        if required:
            return False
        if self.tracker.alerts and self.tracker.alerts[0] == alert:
            self.tracker.delivered(alert)
            self.tracker.alerts.popleft()
        return True

    def notify(self, alert):
        """Let the current game process Escape before mapping the alert window."""
        if self.consume_silent_alert(alert):
            return
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
            self.notification_timer = self.call_later(200, lambda: self.finish_notification(alert))
        else:
            self.finish_notification(alert)


    def finish_notification(self, alert):
        self.notification_timer = None
        if self.closed or alert.day != datetime.now().date().isoformat():
            return
        if not self.tracker.alerts or self.tracker.alerts[0] != alert:
            return
        if self.consume_silent_alert(alert):
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


    def restriction_reached(self, day=None):
        return (self.settings.restriction_enabled and
                sum(self.tracker.totals(day or datetime.now().date()).values()) >= self.settings.restriction_seconds)

    def launch_restricted(self, game):
        return self.catalog.enabled(game) and self.restriction_reached()

    def restriction_notice(self):
        self.open_games()
        self.set_status("Today's {minutes:g}-minute play restriction is active. Change it in Settings.",
                        minutes=self.settings.restriction_seconds/60)

    def enforce_gameplay(self, current):
        if not self.restriction_reached(current.wall.date()) or not current.interactive:
            self._restriction_grace = None
            return False
        game = self.catalog.resolve(current.path)
        if not game or not current.identity or current.identity != self.tracker.identity:
            self._restriction_grace = None
            return False
        if getattr(self, "restriction_timer", None) is not None:
            return True
        key = (current.wall.date().isoformat(), current.identity)
        target = (*key, norm(current.path))
        previous = getattr(self, "_restriction_grace", None)
        if previous:
            elapsed = current.awake-previous[2].awake
            wall = current.wall.timestamp()-previous[2].wall.timestamp()
        if (not previous or previous[0] != target or not 0 <= elapsed <= 3
                or abs(wall-elapsed) > 1.5):
            # A fresh foreground visit gets its own save/quit window. Do not
            # consume that grace while away, locked, asleep or the GUI is stalled.
            self._restriction_grace = (target, current.awake, current)
            return True
        self._restriction_grace = (target, previous[1], current)
        if current.awake-previous[1] < self.RESTRICTION_GRACE_SECONDS:
            return True
        escaped = getattr(self, "_restriction_escaped", set())
        self._restriction_escaped = {item for item in escaped if item[0] == key[0]}
        if key not in self._restriction_escaped:
            self._restriction_escaped.add(key)
            try:
                win32.escape_game(current.path, current.identity)
            except Exception:
                log.exception("Escape before play restriction failed; minimization will still be attempted")
        # Give the guarded Escape time to reach the game before changing focus.
        self.restriction_timer = self.call_later(200, lambda: self.finish_restriction(current.path, current.identity, key[0]))
        return True

    def finish_restriction(self, path, identity, day):
        self.restriction_timer = None
        # A return to the game, or a failed minimize, must allow a new full grace.
        self._restriction_grace = None
        if self.closed or day != datetime.now().date().isoformat() or not self.restriction_reached(day):
            return
        try:
            current = win32.sample()
            if (not current.interactive or current.identity != identity or norm(current.path) != norm(path)
                    or not self.catalog.resolve(current.path)):
                return
            if win32.minimize_game(path, identity):
                log.info("Play restriction: requested minimization of tracked game %s", self.catalog.resolve(path).id)
                self.restriction_notice()
            else:
                self.set_status("Could not minimize the game. Close it manually or change Play restriction in Settings.")
        except Exception:
            log.exception("Play restriction could not minimize the game")
            self.set_status("Could not minimize the game. Close it manually or change Play restriction in Settings.")

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
            current = win32.sample()
            self.tracker.tick(current)
            restricting = self.enforce_gameplay(current)
            today = datetime.now().date().isoformat()
            if self.popup_window and self.popup_day != today:
                self.dismiss_popup()
                self.popup_window = self.popup_day = None
            if not restricting and not self.popup_window and self.notification_timer is None and self.tracker.alerts:
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
        self.tick_timer = self.call_later(1000, self.tick)
