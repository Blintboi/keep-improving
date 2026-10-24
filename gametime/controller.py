"""UI-neutral monitor actions shared by the Qt interface and regression fixture."""
from dataclasses import replace
from datetime import datetime
import logging
import math
import os
import time
from pathlib import Path
from queue import Empty
from .model import norm, LAUNCHER_SOURCES, popup_required
from .tracker import Alert
from .notification_text import notification_text
from .schedule import day_settings,game_settings
from . import win32
from .game_safety import policy as safety
from .background import DISCOVERY_PROBLEM, HUB_PROBLEM
from .budget import remaining_budget, quota_plan
from .quota import period_day, reset_clock

log=logging.getLogger(__name__)

class MonitorActions:
    RESTRICTION_GRACE_SECONDS = 10

    def notification_mode(self):
        """Keep protected fullscreen games free of focus/render transitions."""
        try:
            current=win32.sample()
            if not current.interactive: return 'defer'
            if safety.reason(current.path,self.catalog.resolve(current.path)):
                return 'passive' if win32.desktop_overlay_available() else 'audio'
            return 'normal'
        except Exception:
            log.exception('Notification context unavailable; visual notification deferred')
            return 'defer'

    def audio_notification(self,alert):
        from .sound import play_notification
        if self.settings.notification_sound=='silent': return False
        now=time.monotonic(); prior=getattr(self,'_audio_retry',None)
        if prior and prior[0]==alert and now-prior[1]<30: return False
        self._audio_retry=(alert,now)
        return play_notification(self.settings)

    def minimization_allowed(self,path,identity=None):
        game=self.catalog.resolve(path)
        if not safety.reason(path,game): return True
        consent=getattr(self,'minimize_consents',None)
        return bool(consent and consent.allows(game) and not consent.reason(path,game))

    def render_tick(self):
        self.render()

    def sync_hub(self):
        fingerprint = (self.settings.games_root, self.settings.hub_enabled,
                       tuple(sorted((g.id, g.name, g.root, g.metadata, g.installed) for g in self.catalog.games.values())),
                       tuple(sorted(self.catalog.rules.items())), tuple(sorted(self.catalog.overrides.items())))
        if fingerprint != self.hub_fingerprint:
            self.hub_fingerprint = fingerprint
            self.hub.request(self.settings, self.catalog.games.values(), self.catalog.rules, self.catalog.overrides)
        while not self.hub.results.empty():
            result = self.hub.results.get_nowait()
            if result.get("error"):
                log.warning("Gaming Hub background update failed: %s", result["error"])
                self.background_problem("hub", HUB_PROBLEM, bool(result.get("persistent")))
            else:
                self.background_problem("hub", HUB_PROBLEM, False)

    def background_problem(self, source, message, failed):
        problems = getattr(self, "_background_problems", {})
        self._background_problems = problems
        if failed:
            if source not in problems:
                problems[source] = message
                self.set_status(message)
        elif source in problems:
            del problems[source]
            if self.status_key == message:
                self.set_status(next(iter(problems.values()), ""))

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
        updates=getattr(self,'updates',None)
        if updates:
            items.insert(3,(6,self.t('Update {version} available',version=updates.available.version) if updates.available else 'Check for updates'))
        choice = self.tray.popup_menu([(item[0], self.t(item[1])) if item else None for item in items])
        if choice==6 and updates:
            updates.open(); return
        action = {1: self.show, 2: self.open_games, 3: self.settings_dialog,
                  4: self.refresh_sources, 5: self.close}.get(choice)
        if action:
            action()


    def refresh_sources(self):
        self.devices_changed()
        self.hub_fingerprint = None

    def catalog_changed(self):
        refresh=getattr(self,'refresh_game_dialogs',None)
        if refresh: refresh()


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
            self.catalog_changed()
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
        self.catalog_changed()
        self.tracker.unclassified.clear()
        self.tracker.previous = None


    def test_popup(self):
        self.popup(Alert(period_day(datetime.now().astimezone(),reset_clock(self.settings)).isoformat(), (), "limit",
                         notification_text(quota_plan(self.settings),'limit',test=True), self.t("OK, I’ll stop")))


    def consume_silent_alert(self, alert):
        # A color warning replaces a popup only with a healthy renderer for this
        # foreground game. A topmost desktop HWND can be hidden by fullscreen.
        settings=game_settings(self.settings,self.tracker.active.id) if self.tracker.active else self.settings
        required = popup_required(settings, alert.kind)
        if alert.kind == "warning" and not required:
            try:
                required = not self.overlay_warning_visible()
            except (AttributeError, OSError, RuntimeError):
                required = True
        if self.restriction_reached(alert.day, self.tracker.active) and not getattr(self,'_restriction_reminder_only',False):
            required = False  # The persistent restriction notice replaces queued reminders.
        if required:
            return False
        if self.tracker.alerts and self.tracker.alerts[0] == alert:
            log.info("Alert delivered without popup: kind=%s day=%s renderer=%s", alert.kind, alert.day,
                     getattr(self, '_overlay_backend', 'none'))
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
                game=self.catalog.resolve(current.path)
                if game and not safety.reason(current.path,game) and current.interactive and current.identity == self.tracker.identity:
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
        if self.closed or alert.day != period_day(datetime.now().astimezone(), reset_clock(self.settings)).isoformat():
            return
        if not self.tracker.alerts or self.tracker.alerts[0] != alert:
            return
        if not self.tracker.alert_current(alert, datetime.now().astimezone()):
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
            elif kind == "discovery_problem":
                self.background_problem("discovery", DISCOVERY_PROBLEM, result[1])
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
                self.catalog_changed()
                if self.status_key == "Discovering games…":
                    self.set_status("")
            elif kind == "games":
                _, games, group = result
                self.tracker.reconcile(games, lambda g, p=group: g.source == "Games" and (not p or norm(g.root) == norm(p)))
                self.last_rows = None
                self.catalog_changed()


    def restriction_reached(self, day=None, game=None):
        wall=day if isinstance(day,datetime) else datetime.now().astimezone()
        self.tracker.configure_budget(wall)
        day=period_day(wall,reset_clock(self.settings)) if day is None or isinstance(day,datetime) else day
        settings=day_settings(self.settings,day)
        totals=self.tracker.quota_day_totals(day)
        shared=settings.restriction_enabled and sum(totals.values())>=settings.restriction_seconds
        cap=self.settings.game_limits.get(game.id) if game and self.catalog.enabled(game) else None
        return shared or (cap is not None and totals.get(game.id,0)>=cap)

    def launch_restricted(self, game):
        return self.catalog.enabled(game) and self.restriction_reached(game=game)

    def restriction_notice(self):
        self.open_games()
        self.set_status("Today's {minutes:g}-minute play restriction is active. Change it in Settings.",
                        minutes=quota_plan(self.settings).restriction_seconds/60)

    def enforce_gameplay(self, current):
        self._restriction_reminder_only=False
        game = self.catalog.resolve(current.path)
        if not current.interactive or not self.restriction_reached(current.wall, game):
            self._restriction_grace = None
            return False
        if not game or not current.identity or current.identity != self.tracker.identity:
            self._restriction_grace = None
            return False
        if not self.minimization_allowed(current.path,current.identity):
            self._restriction_grace=None
            self._restriction_reminder_only=True
            return False  # Keep ordinary reminders; do not interrupt this match.
        if getattr(self, "restriction_timer", None) is not None:
            return True
        key = (period_day(current.wall,reset_clock(self.settings)).isoformat(), current.identity)
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
                if not safety.reason(current.path,game): win32.escape_game(current.path, current.identity)
            except Exception:
                log.exception("Escape before play restriction failed; minimization will still be attempted")
        # Give the guarded Escape time to reach the game before changing focus.
        self.restriction_timer = self.call_later(200, lambda: self.finish_restriction(current.path, current.identity, key[0]))
        return True

    def finish_restriction(self, path, identity, day):
        self.restriction_timer = None
        # A return to the game, or a failed minimize, must allow a new full grace.
        self._restriction_grace = None
        if self.closed or day != period_day(datetime.now().astimezone(),reset_clock(self.settings)).isoformat():
            return
        try:
            current = win32.sample()
            if (not current.interactive or current.identity != identity or norm(current.path) != norm(path)
                    or not self.catalog.resolve(current.path)):
                return
            if not self.restriction_reached(day, self.catalog.resolve(current.path)): return
            if not self.minimization_allowed(path,identity): return
            consented=bool(safety.reason(path,self.catalog.resolve(path)))
            minimized=win32.minimize_game(path,identity,consented=True) if consented else win32.minimize_game(path,identity)
            if minimized:
                log.info("Play restriction: requested minimization of tracked game %s", self.catalog.resolve(path).id)
                self.restriction_notice()
            else:
                self.set_status("Could not minimize the game. Close it manually or change Play restriction in Settings.")
        except Exception:
            log.exception("Play restriction could not minimize the game")
            self.set_status("Could not minimize the game. Close it manually or change Play restriction in Settings.")

    def bedtime_message(self,day,wall=None):
        settings=day_settings(self.settings,day)
        remaining=None
        if '{remaining}' in settings.notification_messages.get('bedtime',''):
            now=wall or datetime.now().astimezone()
            total=sum(self.tracker.quota_totals(now).values())
            remaining=math.ceil(remaining_budget(self.settings,now,total).remaining/60)
        return notification_text(settings,'bedtime',remaining,day=day)

    def bedtime_tick(self, current):
        from .bedtime import Bedtime
        if not hasattr(self, 'bedtime'):
            self.bedtime = Bedtime(self.store)
        state, marker, minimize = self.bedtime.update(self.settings, current)
        if marker:
            if self.popup_window: self.dismiss_popup()
            alert = Alert(str(current.wall.date()), (), 'bedtime',
                          self.bedtime_message(marker[0],current.wall),
                          self.t('OK, I’ll finish'))
            # Bedtime is independent of game budgets, exclusions and Escape.
            if self.popup(alert): self.bedtime.delivered(marker)
        active = self.bedtime.active
        update = getattr(self, 'update_bedtime_banner', None)
        if update: update(active)
        if minimize:
            try:
                win32.minimize_foreground(allow=self.minimization_allowed)
            except Exception:
                log.exception('Bedtime could not minimize the foreground window')
                self.set_status('Could not minimize the window. Change Bedtime reminder in Settings.')
        return active

    def test_bedtime_popup(self):
        self.popup(Alert(str(datetime.now().date()), (), 'bedtime',
                   self.bedtime_message(datetime.now().date().isoformat()),
                   self.t('OK, I’ll finish')))

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
            was_playing = self.tracker.active is not None
            self.tracker.tick(current)
            activity_changed = getattr(self, 'statistics_activity_changed', None)
            if activity_changed and was_playing != (self.tracker.active is not None):
                activity_changed(self.tracker.active is not None)
            update_overlay = getattr(self, 'update_overlay', None)
            if update_overlay: update_overlay()
            bedtime_restricting = self.bedtime_tick(current)
            if bedtime_restricting:
                self._restriction_grace = None
                if getattr(self, 'restriction_timer', None) is not None:
                    self.restriction_timer.stop(); self.restriction_timer = None
            restricting = bedtime_restricting or self.enforce_gameplay(current)
            today = period_day(current.wall,reset_clock(self.settings)).isoformat()
            popup_day = current.wall.date().isoformat() if getattr(self,'popup_kind',None)=='bedtime' else today
            if self.popup_window and self.popup_day != popup_day:
                self.dismiss_popup()
                self.popup_window = self.popup_day = None
            if not restricting and not self.popup_window and self.notification_timer is None and self.tracker.alerts:
                alert = self.tracker.alerts[0]
                if alert.day == today:
                    self.notify(alert)
                elif alert.day != today:
                    self.tracker.alerts.popleft()
                    self.tracker.queued.difference_update((alert.day, key) for key in alert.keys)
            self.render_tick()
        except Exception as exc:
            log.exception("Game time measurement failed")
            self.set_status("An error occurred; see monitor.log: " + str(exc))
            self.tracker.previous = None
        self.tick_timer = self.call_later(1000, self.tick)
