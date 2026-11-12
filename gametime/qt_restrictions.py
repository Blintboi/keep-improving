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
from .restriction_policy import Budget, RestrictionState, RANK, legacy_active
from .restriction_audio import AudioGuard
from . import restriction_native as native
from . import win32
from .focus import app_key, matches
from .quota import current_day,budget_day
from .budget import quota_plan,remaining_budget
from .wellbeing import applies
from . import budget_access
from .tracker import Alert,Sample
from .sound import play_notification


class RestrictionScreen(QDialog):
    def __init__(self, runtime):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.runtime = runtime; self.target = None; self.keys = []; self.subject = ''
        self.setWindowTitle(runtime.app.t('Restriction active'))
        self.setStyleSheet('QDialog {background:#10191b;color:#edf4f2;} QLabel {color:#edf4f2;}')
        layout = QVBoxLayout(self); layout.setContentsMargins(40, 35, 40, 35); layout.addStretch()
        self.heading = label(runtime.app.t('Restriction active'), 'title'); self.heading.setWordWrap(True)
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
        from .budget_sessions import Counter
        self.session_counts = Counter(app)
        from .qt_choice_runtime import ChoiceRuntime
        self.choices = ChoiceRuntime(self)

    def budgets(self, wall):
        app = self.app; totals = app.tracker.quota_totals(wall); result = []
        if app.settings.game_budget_enabled and budget_access.active(app.settings,'shared-games',wall):
            used=sum(totals.values())
            has_break=any(item['kind']=='break' for item in app.settings.restriction_plans.get('shared-games',{}).get('steps',()))
            allowed=not has_break or remaining_budget(app.settings,wall,used).remaining>0
            result.append(Budget('shared-games', str(app.t('Games · shared budget')), budget_access.limit(app.settings,'shared-games',quota_plan(app.settings, wall).limit_seconds,wall),
                                 used, ({'kind': 'category', 'value': 'games'},),
                                 breaks_allowed=allowed,day=budget_day(app.settings,'shared-games',wall).isoformat()))
        for gid, limit in app.settings.game_limits.items():
            game = app.catalog.games.get(gid)
            if game and app.catalog.enabled(game) and budget_access.active(app.settings,'game:'+gid,wall):
                result.append(Budget('game:' + gid, game.name, budget_access.limit(app.settings,'game:'+gid,limit,wall), app.tracker.game_quota_total(wall,gid), ({'kind': 'game', 'value': gid},),
                                     day=budget_day(app.settings,'game:'+gid,wall).isoformat()))
        for value in app.wellbeing.states(wall):
            used=sum(app.tracker.quota_totals(wall,value.rule['id']).values()) if value.rule['id'].startswith('games-') and value.rule['members']==[{'kind':'category','value':'games'}] else value.used
            result.append(Budget(value.rule['id'], value.rule['name'], budget_access.limit(app.settings,value.rule['id'],value.rule['seconds'],wall), used, tuple(value.rule['members']),
                                 day=budget_day(app.settings,value.rule['id'],wall).isoformat()))
        counts=self.session_counts.counts(result,wall)
        return [replace(budget,sessions=counts.get(budget.key,0),clock_deadlines=budget_access.clock_deadlines(app.settings,budget.key,wall),
                        breaks_allowed=budget.breaks_allowed and budget_access.clock_remaining(app.settings,budget.key,wall)>0) for budget in result]

    def prepare(self, wall):
        # A clock correction during a run cannot lengthen a granted countdown.
        stamp = wall.timestamp(); mono = time.monotonic()
        if self._clock is None: self._clock = (stamp, mono)
        now = max(stamp, self._clock[0] + mono - self._clock[1], self._max_now)
        self._max_now = now
        budgets=self.budgets(wall)
        self.timer_wall=wall
        self.app._timer_budget_key=getattr(self.app,'timer_budget_key',lambda wall:None)(wall); self.app._timer_budgets=budgets
        self.state.update(current_day(self.app.settings, wall).isoformat(), now,
                          budgets, self.app.settings.restriction_plans)
        for key,row in self.state.rows.items():
            grant=row.get('grant') or {}; identity=grant.get('identity',''); subject=grant.get('subject','')
            if (key not in self.state.budgets or not identity or not subject.startswith('app:')
                    or identity in self.targets or mono<self.failed.get(identity,0)): continue
            path=subject[4:]; sample=Sample(wall,mono,path,identity)
            atom=self.app.wellbeing.atom(sample,'')
            if atom and applies(self.state.budgets[key].members,atom):
                self.targets[identity]=(sample,atom)
        self.prepared_at=mono

    def save_remaining(self, path):
        now=self.state.now+max(0,time.monotonic()-getattr(self,'prepared_at',time.monotonic()))
        identity=self.current.identity if self.current and app_key(self.current.path)==app_key(path) else None
        grants=[self.state.grant(key,'app:'+app_key(path),identity) for key in self.state.budgets]
        deadlines=[g['until'] for g in grants if g and g['until']>now]
        return max(0,min(deadlines)-now) if deadlines else None

    def matching(self, atom):
        return [key for key, budget in self.state.budgets.items() if applies(budget.members, atom)]

    def legacy_block(self, atom, permitted=()):
        app = self.app
        if app.focus.restricting and (app.focus_application_blocked(atom[1],atom[0]) or
                app.focus.settings.site_blocked(atom[2],app.settings.wellbeing_rules)):
            return True
        if atom[0]:
            from .restriction_policy import legacy_restriction_active
            wall=datetime.now().astimezone(); plan=quota_plan(app.settings,wall); game=app.catalog.resolve(atom[1])
            if ('shared-games' not in permitted and plan.game_budget_enabled and plan.restriction_enabled
                    and budget_access.active(plan,'shared-games',wall) and budget_access.usage_enabled(plan,'shared-games')
                    and legacy_active(plan.restriction_plans,'shared-games')
                    and sum(app.tracker.quota_totals(wall).values())>=plan.restriction_seconds): return True
            key='game:'+atom[0]; cap=app.settings.game_limits.get(atom[0])
            if (key not in permitted and game and app.catalog.enabled(game) and cap is not None
                    and budget_access.active(plan,key,wall) and budget_access.usage_enabled(plan,key) and legacy_restriction_active(plan.restriction_plans,key)
                    and app.tracker.game_quota_total(wall,atom[0])>=cap): return True
        return any(s.rule['id'] not in permitted and budget_access.usage_enabled(app.settings,s.rule['id']) and legacy_active(app.settings.restriction_plans,s.rule['id']) and s.rule['enforce'] and s.used>=s.rule['seconds']
                   for s in app.wellbeing.states(datetime.now().astimezone(), atom))

    def extend(self, keys, subject):
        self.prepare(datetime.now().astimezone())
        identity=''
        if subject.startswith('app:'):
            path = subject[4:]; game = self.app.catalog.resolve(path)
            atom = (game.id if game else '', path, '')
            if self.screen and self.screen.target and self.screen.subject==subject: identity=self.screen.target.identity
            elif self.current and app_key(self.current.path)==app_key(path): identity=self.current.identity
            dominant=self.state.dominant(self.matching(atom),subject,identity or None)
            active = [k for k in dominant if self.state.action(k, subject,identity or None)]
            if set(active) != set(keys) or self.legacy_block(atom,keys): return None
        until = self.state.extend(keys, subject,identity)
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
        for observed,media_atom in getattr(getattr(app,'background_media',None),'targets',()):
            if self.matching(media_atom):self.targets[observed.identity]=(observed,media_atom)
        if atom and current.identity:
            keys = self.matching(atom)
            if keys: self.targets[current.identity] = (current, atom)
        pending=[];seen=set()
        observations=([atom] if atom and current.identity else [])+list(getattr(getattr(app,'background_media',None),'atoms',()))
        for observed in observations:
            for key in self.matching(observed):
                members=self.state.budgets[key].members
                scopes=[]
                if applies([m for m in members if m['kind']!='site' and m!={'kind':'category','value':'sites'}],observed): scopes.append('app:'+observed[1])
                if observed[2] and applies([m for m in members if m['kind']=='site' or m=={'kind':'category','value':'sites'}],observed): scopes.append('site:'+observed[2].split('\0')[0])
                for scope in scopes:
                    for warning in self.state.warnings(key,scope):
                        identity=(key,warning['id'])
                        if identity not in seen: pending.append((key,warning)); seen.add(identity)
        if pending and not app.popup_window:
            messages=[]
            for key in dict.fromkeys(key for key,_ in pending):
                budget=self.state.budgets[key]
                clock_warning=next((warning for k,warning in pending if k==key and warning.get('time_mode')=='clock'),None)
                if clock_warning:
                    minute=clock_warning['clock_minute']
                    messages.append(app.t('{name}: the daily time {time} has been reached.',name=budget.name,time=f'{minute//60:02d}:{minute%60:02d}'))
                elif any(k==key and warning.get('time_mode')=='usage' for k,warning in pending):
                    messages.append(app.t('{name}: {minutes:g} minutes of use.',name=budget.name,minutes=round(budget.used/60,2)))
                elif any(k==key and warning.get('time_mode')=='sessions' for k,warning in pending):
                    messages.append(app.t('{name}: {count} sessions today.',name=budget.name,count=budget.sessions))
                else:
                    messages.append(app.t('{name}: {minutes:g} minutes remaining.',name=budget.name,
                        minutes=max(0,math.ceil((budget.limit-budget.used)/60))))
            alert=Alert(self.state.day,(),'wellbeing','\n'.join(messages),app.t('OK'),
                        title=app.t('Budget reminder'),sound=any(w['sound'] for _,w in pending))
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
            native_keys=self.state.dominant(native_keys,target_subject,identity)
            actions = {key: self.state.action(key, target_subject,identity) for key in native_keys}
            active = [key for key, action in actions.items() if action]
            grant = [self.state.grant(key, target_subject,identity) for key in native_keys]
            if not active and not any(grant): self.targets.pop(identity, None); continue
            if any(actions[k] == 'minimize' for k in active) and all(actions[k] == 'minimize' for k in active):
                foreground=current.identity==identity
                screen_owned=owned and self.screen.target and self.screen.target.identity==identity
                if (foreground or screen_owned) and self.app.minimization_allowed(target.path, identity):
                    if (self.state.allowance(active,target_subject)>0 and not self.legacy_block(target_atom,active)
                            and native.permitted(target.path,identity)):
                        display=(target,active,target_subject,target_atom)
                    elif foreground:
                        win32.minimize_game(target.path, identity, consented=True)
                    self.blocked = True
                continue
            handle = native.open_target(target.path, identity)
            if not handle:
                self.targets.pop(identity,None)
                notify=bool(active and current.identity==identity and time.monotonic()>=self.failed.get(identity,0))
                if any(grant):
                    # An access failure need not mean the process has exited.
                    # Keep the promise and retry; only discard it if the PID
                    # is known to have been reused for a different process.
                    try: observed=win32.process_image(int(identity.split(':',1)[0]))[1]
                    except (ValueError,TypeError,OSError): observed=''
                    if observed and observed!=identity:
                        for key in native_keys: self.state.finish_grant(key,target_subject,identity)
                    else: self.failed[identity]=time.monotonic()+5
                if notify:
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
            if not any(not self.state.zero_budget(k) and self.app.settings.restriction_plans.get(k, {}).get('close_confirmed') and
                       self.state.action(k, 'app:' + app_key(target.path),identity) in ('close', 'cover', 'minimize') for k in keys): cancel.set()
            if future.done():
                try: success = future.result()
                except Exception: success = False
                if not success and not cancel.is_set():
                    app.set_status('Could not close the application. Close it manually.')
                    self.failed[identity] = time.monotonic() + 30
                if success:
                    for key in keys: self.state.finish_grant(key,'app:'+app_key(target.path),identity)
                self.jobs.pop(identity)
        choosing = self.choices.tick(current, website, bool(display) or self.blocked or bedtime)
        if choosing and self.choices.target:
            mute.append({'path': self.choices.target.path, 'identity': self.choices.target.identity})
            self.blocked = True
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
        minutes = 0 if self.legacy_block(atom,keys) else self.state.allowance(keys, subject)
        screen.extra.setText(app.t('Another {minutes:g} minutes to save', minutes=minutes)); screen.extra.setVisible(minutes > 0)
        screen.quit.setVisible(any(not self.state.zero_budget(k) and app.settings.restriction_plans.get(k,{}).get('close_confirmed') for k in keys))
        screen.heading.setText(app.t('Restriction active'))
        screen.note.setText('\n'.join(self.state.budgets[k].name for k in keys))
        remaining=max((self.state.break_remaining(k,subject) for k in keys if not self.state.has_restriction(k,subject,target.identity)),default=0)
        if any(self.state.zero_budget(k) for k in keys):
            screen.status.setText(app.t('Access is blocked because the daily budget is 0.'))
        elif remaining:
            seconds=math.ceil(remaining)
            screen.status.setText(app.t('Break remaining: {time}',time=f'{seconds//60}:{seconds%60:02d}'))
        else:
            screen.status.setText(app.t('Applications close when the save allowance ends.') if minutes else app.t('This budget is blocked until it renews.'))
        if self.audio.status.get('ok') is False: screen.status.setText(app.t('Application audio could not be muted.'))
        self.position_screen(screen, target, same)

    def position_screen(self, screen, target, same=False):
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
        policy = dict(base); entries = []; zero_domains = []; zero_all = False
        for key, budget in self.state.budgets.items():
            domains = [m['value'] for m in budget.members if m['kind'] == 'site']
            all_sites = {'kind': 'category', 'value': 'sites'} in budget.members
            if not domains and not all_sites: continue
            if self.state.zero_budget(key):
                zero_domains.extend(domains); zero_all |= all_sites
            row = self.state.rows[key]
            grant=row['grant'] if row['grant'] and row['grant']['subject'].startswith('site:') else None
            if (grant and grant.get('carried') and grant['until']>self.state.now
                    and not self.state.has_restriction(key,'site:')):
                entries.append(dict(key=key,name=budget.name,domains=domains,all=all_sites,kind='cover',
                                    minutes=0,grant=grant,is_break=False,grant_only=True))
            action = self.state.action(key, 'site:')
            if not action: continue
            is_break=not self.state.has_restriction(key,'site:')
            entry=dict(key=key, name=budget.name, domains=domains, all=all_sites, kind='cover' if action=='minimize' else action,
                       minutes=self.state.allowance([key],'site:'), grant=grant, is_break=is_break)
            if action=='redirect':
                redirect=next((step.get('redirect_url','') for step in self.state.due(key,'site:')
                               if step['kind']=='redirect' or step['kind']=='break' and step['break_mode']=='redirect'),None)
                if redirect is not None: entry['redirect_url']=redirect
            remaining=self.state.break_remaining(key,'site:')
            if remaining and is_break: entry['break_until']=self.state.now+remaining
            entries.append(entry)
        from .browser_choices import rules as choice_rules
        policy.update(restriction_version=1, restrictions=entries, language=self.app.settings.language, lease_seconds=30,
                      choice_rules=choice_rules(self))
        # An unpacked extension can keep its old worker after a desktop upgrade.
        # Zero budgets have no exceptions, so the original blocking protocol can
        # enforce them too, including on an already-open tab. Never activate
        # dormant focus lists when adding this unconditional block.
        if zero_domains or zero_all:
            active = base.get('active', False)
            policy.update(active=True,
                          mode='allowlist' if zero_all else base.get('mode','blocklist') if active else 'blocklist',
                          allow=list(base.get('allow',())) if active and not zero_all else [],
                          block=list(dict.fromkeys([*(base.get('block',()) if active else ()), *zero_domains])),
                          remaining=max(base.get('remaining',0) if active else 0,30))
        return policy

    def early_break_actions(self):
        from .restriction_policy import target_steps
        result={}
        for key,plan in self.app.settings.restriction_plans.items():
            if not any(s['kind']=='break' and s.get('time_mode')=='usage' and s.get('allow_early_break') for s in target_steps(plan)):continue
            steps=self.state.early_break_steps(key)
            states=self.state.rows.get(key,{}).get('breaks',{})
            upcoming=min(steps,key=lambda s:(states.get(s['id'],{}).get('next_at',s['offset']),s['id']),default=None)
            budget=self.state.budgets.get(key)
            unavailable=('inactive' if budget is None else 'limit' if budget.used>=budget.limit or not budget.breaks_allowed else 'restricted')
            result[key]=dict(step=upcoming['id'].split(':')[-1] if upcoming else '',remaining=self.state.break_remaining(key),
                             minutes=upcoming['break_minutes'] if upcoming else 0,unavailable='' if upcoming else unavailable)
        return result

    def start_early_break(self,key,step):
        self.prepare(datetime.now().astimezone())
        if not self.state.start_early_break(key,step):return False
        self.app._timer_budget_key=None
        self.app.update_focus_policy()
        self.tick(win32.sample());self.app.update_overlay()
        return True

    def delegated_website_rules(self):
        return {key for key,budget in self.state.budgets.items() if self.state.has_restriction(key,'site:')
                and self.state.action(key,'site:') and any(member['kind']=='site' or member=={'kind':'category','value':'sites'} for member in budget.members)}

    def process_browser_requests(self):
        bridge = self.app.browser_bridge
        if not bridge: return
        for data, answer, event in bridge.take_requests():
            try:
                from .focus import domain
                host = domain(data['domain']); token = data['token']
                if not isinstance(token, str) or not __import__('re').fullmatch('[a-zA-Z0-9_-]{16,100}', token): raise ValueError()
                atom = ('', '', host); subject = 'site:' + host + ':' + token
                keys = self.state.dominant(self.matching(atom),subject); active = [k for k in keys if self.state.action(k, subject)]
                base = self.app.wellbeing.policy(self.app.focus.policy(self.app.settings.wellbeing_rules), datetime.now().astimezone(),self.delegated_website_rules())
                from .focus import matches
                legacy = base['active'] and (any(matches(host, h) for h in base['block']) or base['mode'] == 'allowlist')
                until = None if legacy else self.extend(active, subject)
                answer.update(ok=bool(until), until=until)
            except (ValueError, KeyError, TypeError): answer.update(ok=False)
            finally: event.set()

    def close(self):
        self.stopped = True
        self.choices.close()
        for future, cancel, _, _ in self.jobs.values(): cancel.set()
        self.audio.close()
        if self.screen: self.screen.hide(); self.screen.deleteLater(); self.screen = None
        if self.save_counter: self.save_counter.hide(); self.save_counter.deleteLater(); self.save_counter=None
        self.executor.shutdown(wait=False, cancel_futures=True)
