"""Per-budget steps coordinated with the existing foreground sampler."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
import math
import os
import threading
import time
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QApplication
from .qt_widgets import label, button
from .restriction_policy import Budget, RestrictionState, RANK
from .restriction_audio import AudioGuard
from . import restriction_native as native
from . import win32
from .focus import app_key, matches
from .quota import current_day
from .budget import quota_plan
from .wellbeing import applies
from .tracker import Alert
from .sound import play_notification


class RestrictionScreen(QDialog):
    def __init__(self, runtime):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.runtime = runtime; self.target = None; self.keys = []; self.subject = ''
        self.setWindowTitle(runtime.app.t('Time budget reached'))
        self.setStyleSheet('QDialog {background:#10191b;color:#edf4f2;} QLabel {color:#edf4f2;}')
        layout = QVBoxLayout(self); layout.setContentsMargins(40, 35, 40, 35); layout.addStretch()
        self.heading = label(runtime.app.t('Time budget reached'), 'title'); self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.note = label(); self.note.setWordWrap(True); layout.addWidget(self.note)
        self.status = label(); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout()
        self.extra = button('', self.extend, 'primary'); row.addWidget(self.extra)
        self.quit = button(runtime.app.t('Close now'), self.close_target); row.addWidget(self.quit)
        row.addWidget(button(runtime.app.t('Use another application'), self.leave))
        layout.addLayout(row); layout.addStretch()
    def extend(self):
        if self.runtime.extend(self.keys, self.subject):
            self.hide()
            if self.target: native.restore_target(self.target.path,self.target.identity)
    def close_target(self):
        if self.target: self.runtime.close_target(self.target, self.keys)
    def leave(self):
        if self.target: native.minimize_target(self.target.path, self.target.identity)
        self.hide()
    def reject(self): self.leave()
    def closeEvent(self, event): self.leave(); event.ignore()


class RestrictionRuntime:
    def __init__(self, app):
        self.app = app; self.state = RestrictionState(app.store)
        self.screen = None; self.audio = AudioGuard(); self.targets = {}; self.jobs = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='budget-close')
        self.blocked = False; self.current = None; self.stopped = False; self.failed = {}
        self._clock = None; self._max_now = 0
        self.save_counter = None

    def budgets(self, wall):
        app = self.app; totals = app.tracker.quota_totals(wall); result = []
        if app.settings.game_budget_enabled:
            result.append(Budget('shared-games', str(app.t('Games · shared budget')), quota_plan(app.settings, wall).limit_seconds,
                                 sum(totals.values()), ({'kind': 'category', 'value': 'games'},)))
        for gid, limit in app.settings.game_limits.items():
            game = app.catalog.games.get(gid)
            if game and app.catalog.enabled(game):
                result.append(Budget('game:' + gid, game.name, limit, totals.get(gid, 0), ({'kind': 'game', 'value': gid},)))
        for value in app.wellbeing.states(wall):
            result.append(Budget(value.rule['id'], value.rule['name'], value.rule['seconds'], value.used, tuple(value.rule['members'])))
        return result

    def prepare(self, wall):
        # A clock correction during a run cannot lengthen a granted countdown.
        stamp = wall.timestamp(); mono = time.monotonic()
        if self._clock is None: self._clock = (stamp, mono)
        now = max(stamp, self._clock[0] + mono - self._clock[1], self._max_now)
        self._max_now = now
        self.state.update(current_day(self.app.settings, wall).isoformat(), now,
                          self.budgets(wall), self.app.settings.restriction_plans)
        self.prepared_at=mono

    def save_remaining(self, path):
        now=self.state.now+max(0,time.monotonic()-getattr(self,'prepared_at',time.monotonic()))
        grants=[self.state.grant(key,'app:'+app_key(path)) for key in self.state.budgets]
        deadlines=[g['until'] for g in grants if g and g['until']>now]
        return max(0,min(deadlines)-now) if deadlines else None

    def matching(self, atom):
        return [key for key, budget in self.state.budgets.items() if applies(budget.members, atom)]

    def legacy_block(self, atom):
        app = self.app
        if app.focus.restricting and (app.focus.settings.app_blocked(atom[1]) or atom[2] and any(
                matches(atom[2], host) for host in app.focus.settings.block_sites)):
            return True
        if atom[0] and app.restriction_reached(game=app.catalog.resolve(atom[1])): return True
        return any(s.rule['id'] not in app.settings.restriction_plans and s.rule['enforce'] and not s.remaining
                   for s in app.wellbeing.states(datetime.now().astimezone(), atom))

    def extend(self, keys, subject):
        self.prepare(datetime.now().astimezone())
        if subject.startswith('app:'):
            path = subject[4:]; game = self.app.catalog.resolve(path)
            atom = (game.id if game else '', path, '')
            active = [k for k in self.matching(atom) if self.state.action(k, subject)]
            if set(active) != set(keys) or self.legacy_block(atom): return None
        until = self.state.extend(keys, subject)
        if until:
            self.audio.close()
            self.app.update_focus_policy()
        return until

    def close_target(self, target, keys):
        if target.identity in self.jobs or not native.permitted(target.path, target.identity): return
        if not any(self.app.settings.restriction_plans.get(k, {}).get('close_confirmed') for k in keys): return
        cancel = threading.Event()
        future = self.executor.submit(native.close_target, target.path, target.identity, 5000, cancel)
        self.jobs[target.identity] = (future, cancel, target, tuple(keys))

    def tick(self, current, bedtime=False):
        self.current = current; self.prepare(current.wall); self.blocked = False
        app = self.app
        website = app.browser_bridge.website(current.path) if app.browser_bridge else ''
        atom = app.wellbeing.atom(current, website)
        subject = 'app:' + app_key(current.path)
        if atom and current.identity:
            keys = self.matching(atom)
            if keys: self.targets[current.identity] = (current, atom)
            pending=[(key,warning) for key in keys for warning in self.state.warnings(key)]
            if pending and not app.popup_window:
                messages=[app.t('{name}: {minutes:g} minutes remaining.',name=self.state.budgets[key].name,
                    minutes=max(0,math.ceil((self.state.budgets[key].limit-self.state.budgets[key].used)/60)))
                    for key in dict.fromkeys(key for key,_ in pending)]
                alert=Alert(self.state.day,(),'wellbeing','\n'.join(messages),app.t('OK'),
                            title=app.t('Time budget reminder'),sound=any(w['sound'] for _,w in pending))
                delivered=app.popup(alert) if any(w['popup'] for _,w in pending) else play_notification(app.settings)
                if delivered:
                    for key,warning in pending: self.state.delivered(key,warning['id'])
        owned = bool(self.screen and self.screen.isVisible() and win32.u.GetForegroundWindow()==int(self.screen.winId()))
        mute = []; display = None; save_until = None
        for identity, (target, target_atom) in list(self.targets.items()):
            keys = self.matching(target_atom); target_subject = 'app:' + app_key(target.path)
            # Site-only actions never minimize or close the browser process.
            native_keys = [key for key in keys if applies([m for m in self.state.budgets[key].members
                if m['kind'] != 'site' and m != {'kind': 'category', 'value': 'sites'}], target_atom)]
            actions = {key: self.state.action(key, target_subject) for key in native_keys}
            active = [key for key, action in actions.items() if action]
            grant = [self.state.grant(key, target_subject) for key in native_keys]
            if not active and not any(grant): self.targets.pop(identity, None); continue
            if any(actions[k] == 'minimize' for k in active) and all(actions[k] == 'minimize' for k in active):
                if current.identity == identity and self.app.minimization_allowed(target.path, identity):
                    win32.minimize_game(target.path, identity, consented=True); self.blocked = True
                continue
            handle = native.open_target(target.path, identity)
            if not handle:
                self.targets.pop(identity,None)
                if active and current.identity==identity and time.monotonic()>=self.failed.get(identity,0):
                    app.set_status('Could not apply this restriction to the application.')
                    self.failed[identity]=time.monotonic()+30
                continue
            win32.k.CloseHandle(handle)
            if current.identity == identity:
                remaining_grants = [g['until'] for g in grant if g and g['until'] > self.state.now]
                if remaining_grants: save_until = min(remaining_grants)
            if not current.interactive or bedtime: continue
            mode = max((actions[k] for k in active), key=RANK.get) if active else ''
            foreground = current.identity == identity
            if mode == 'close':
                if time.monotonic() >= self.failed.get(identity, 0): self.close_target(target, active)
                if foreground: self.blocked = True
            elif mode == 'cover':
                mute.append({'path': target.path, 'identity': identity})
                if foreground or owned and self.screen.target.identity == identity:
                    display = (target, active, target_subject, target_atom); self.blocked = True
            elif mode == 'minimize' and foreground:
                native.minimize_target(target.path, identity); self.blocked = True
        for identity, (future, cancel, target, keys) in list(self.jobs.items()):
            if not any(self.app.settings.restriction_plans.get(k, {}).get('close_confirmed') and
                       self.state.action(k, 'app:' + app_key(target.path)) in ('close', 'cover') for k in keys): cancel.set()
            if future.done():
                try: success = future.result()
                except Exception: success = False
                if not success and not cancel.is_set():
                    app.set_status('Could not close the application. Close it manually.')
                    self.failed[identity] = time.monotonic() + 30
                self.jobs.pop(identity)
        try: self.audio.update(mute)
        except (OSError, ValueError): self.audio.close(); app.set_status('Application audio could not be muted.')
        if display: self.present(*display)
        elif self.screen: self.screen.hide()
        self.show_save_counter(save_until)
        self.process_browser_requests()
        return self.blocked

    def show_save_counter(self, until):
        if self.app.tracker.active: until=None  # The existing desktop/RTSS renderer displays the save timer.
        if until is None:
            if self.save_counter: self.save_counter.hide()
            return
        if self.save_counter is None:
            self.save_counter=label()
            self.save_counter.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowDoesNotAcceptFocus)
            self.save_counter.setAttribute(Qt.WA_ShowWithoutActivating)
            self.save_counter.setStyleSheet('background:#182a28;color:#edf4f2;padding:14px;font-size:20px;')
            win32.nonactivating_window(int(self.save_counter.winId()))
        seconds=max(0,math.ceil(until-self.state.now))
        self.save_counter.setText(self.app.t('Save time: {time}',time=f'{seconds//60}:{seconds%60:02d}'))
        self.save_counter.adjustSize()
        area=QApplication.primaryScreen().availableGeometry()
        self.save_counter.move(area.right()-self.save_counter.width()-20,area.top()+20)
        self.save_counter.show()

    def present(self, target, keys, subject, atom):
        app = self.app
        if self.screen is None: self.screen = RestrictionScreen(self)
        screen = self.screen
        same = screen.isVisible() and screen.target and screen.target.identity == target.identity
        screen.target, screen.keys, screen.subject = target, keys, subject
        minutes = 0 if self.legacy_block(atom) else self.state.allowance(keys, subject)
        screen.extra.setText(app.t('Another {minutes:g} minutes to save', minutes=minutes)); screen.extra.setVisible(minutes > 0)
        screen.quit.setVisible(any(app.settings.restriction_plans[k]['close_confirmed'] for k in keys))
        screen.heading.setText(app.t('Time budget reached'))
        screen.note.setText('\n'.join(self.state.budgets[k].name for k in keys))
        screen.status.setText(app.t('Applications close when the save allowance ends.') if minutes else app.t('This budget is blocked until it renews.'))
        if self.audio.status.get('ok') is False: screen.status.setText(app.t('Application audio could not be muted.'))
        if same and getattr(screen,'fullscreen',False): return
        rectangle = native.target_rect(target.path, target.identity, background=same)
        if not rectangle: return
        x, y, w, h = rectangle
        from .overlay import MonitorInfo, monitor_from_window, monitor_info, choose_screen
        import ctypes
        info=MonitorInfo(); info.size=ctypes.sizeof(info)
        hwnds=native.windows(target.identity)
        handle=monitor_from_window(hwnds[0],2) if hwnds else None
        if not handle or not monitor_info(handle,ctypes.byref(info)): return
        monitor=choose_screen(automatic_name=info.device); area=monitor.geometry()
        fullscreen = w >= info.monitor.right-info.monitor.left-8 and h >= info.monitor.bottom-info.monitor.top-8
        screen.fullscreen=fullscreen
        if fullscreen:
            if not native.minimize_target(target.path, target.identity): return
            screen.setGeometry(monitor.availableGeometry())
        else:
            ratio=monitor.devicePixelRatio()
            screen.setGeometry(area.x()+round((x-info.monitor.left)/ratio),area.y()+round((y-info.monitor.top)/ratio),
                               max(520,round(w/ratio)),max(260,round(h/ratio)))
        if same: return
        screen.show(); screen.raise_(); screen.activateWindow()
        win32.u.SetForegroundWindow(int(screen.winId()))

    def browser_policy(self, base):
        policy = dict(base); entries = []
        for key, budget in self.state.budgets.items():
            domains = [m['value'] for m in budget.members if m['kind'] == 'site']
            all_sites = {'kind': 'category', 'value': 'sites'} in budget.members
            if not domains and not all_sites: continue
            action = self.state.action(key, 'site:')
            if not action: continue
            row = self.state.rows[key]
            entries.append(dict(key=key, name=budget.name, domains=domains, all=all_sites, kind=action,
                                minutes=self.state.plans[key]['extension_minutes'] if not row['used_extension'] else 0,
                                grant=row['grant']))
        policy.update(restriction_version=1, restrictions=entries, language=self.app.settings.language, lease_seconds=30)
        return policy

    def process_browser_requests(self):
        bridge = self.app.browser_bridge
        if not bridge: return
        for data, answer, event in bridge.take_requests():
            try:
                from .focus import domain
                host = domain(data['domain']); token = data['token']
                if not isinstance(token, str) or not __import__('re').fullmatch('[a-zA-Z0-9_-]{16,100}', token): raise ValueError()
                atom = ('', '', host); subject = 'site:' + host + ':' + token
                keys = self.matching(atom); active = [k for k in keys if self.state.action(k, subject)]
                base = self.app.wellbeing.policy(self.app.focus.policy(), datetime.now().astimezone())
                from .focus import matches
                legacy = base['active'] and (any(matches(host, h) for h in base['block']) or base['mode'] == 'allowlist')
                until = None if legacy else self.extend(active, subject)
                answer.update(ok=bool(until), until=until)
            except (ValueError, KeyError, TypeError): answer.update(ok=False)
            finally: event.set()

    def close(self):
        self.stopped = True
        for future, cancel, _, _ in self.jobs.values(): cancel.set()
        self.audio.close()
        if self.screen: self.screen.hide(); self.screen.deleteLater(); self.screen = None
        if self.save_counter: self.save_counter.hide(); self.save_counter.deleteLater(); self.save_counter=None
        self.executor.shutdown(wait=False, cancel_futures=True)
