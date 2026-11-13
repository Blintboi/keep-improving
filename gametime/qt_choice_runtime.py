"""Opening choices on the same native surface as application covers."""
import json
import os
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget
from .qt_widgets import label, button
from .session_choices import ChoiceLedger, Visits, allowance_activity
from .focus import app_key
from .wellbeing import applies
from . import restriction_native as native, win32


class ChoiceScreen(QDialog):
    def __init__(self, gate):
        super().__init__(None, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.gate = gate; self.target = None; self.signature = None
        t = gate.app.t; self.setWindowTitle(t('Opening choice'))
        self.setStyleSheet('QDialog {background:#10191b;color:#edf4f2;} QLabel {color:#edf4f2;}')
        layout = QVBoxLayout(self); layout.setContentsMargins(32, 24, 32, 24); layout.setSpacing(16)
        self.budget_name = label('', 'eyebrow'); self.budget_name.setWordWrap(True); layout.addWidget(self.budget_name)
        self.question = label('', 'title'); self.question.setWordWrap(True); layout.addWidget(self.question)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.NoFrame)
        self.options = QWidget(); self.options_box = QVBoxLayout(self.options); self.options_box.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.options); layout.addWidget(scroll, 1)
        self.note = label(t('Choose a reason to continue. Each accepted choice counts as one visit.'), 'muted')
        self.note.setWordWrap(True); layout.addWidget(self.note)
        self.leave_button = button(t('Use another application'), self.leave, 'quiet'); layout.addWidget(self.leave_button)
        self.choice_buttons = {}

    def render(self, budget, value, options, activity=''):
        signature = json.dumps((budget.name, value, options, activity, self.gate.app.settings.language), sort_keys=True)
        if signature == self.signature: return
        self.signature = signature; self.budget_name.setText(budget.name); self.question.setText(value['question'])
        while self.options_box.count():
            item = self.options_box.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.choice_buttons = {}; t = self.gate.app.t
        self.setWindowTitle(t('Opening choice'))
        allocation = t('Separate allowance for this activity') if value.get('allocation')=='activity' else t('Shared allowance across this budget')
        self.note.setText(allocation + '. ' + t('Choose a reason to continue. Each accepted choice counts as one visit.'))
        self.leave_button.setText(t('Use another application'))
        for option in options:
            remaining = option['remaining']
            detail = t('Unlimited') if remaining is None else t('No visits left today') if remaining == 0 else t('{remaining} of {limit} visits left today', remaining=remaining, limit=option['limit'])
            pick = button('', lambda checked=False, identity=option['id']: self.gate.choose(identity), 'primary' if remaining != 0 else 'quiet')
            pick.setMinimumHeight(76); pick.setEnabled(remaining != 0)
            pick.setAccessibleName(option['label'] + ' · ' + detail)
            content = QVBoxLayout(pick); content.setContentsMargins(16, 10, 16, 10)
            name = label(option['label'], 'section'); name.setWordWrap(True)
            subtitle = label(detail, 'muted'); subtitle.setWordWrap(True)
            name.setStyleSheet('color:#10221d;' if remaining != 0 else 'color:#879591;')
            subtitle.setStyleSheet('color:#234b40;' if remaining != 0 else 'color:#879591;')
            for child in (name, subtitle):
                child.setAttribute(Qt.WA_TransparentForMouseEvents); content.addWidget(child)
            self.choice_buttons[option['id']] = pick; self.options_box.addWidget(pick)
        self.options_box.addStretch()

    def leave(self): self.gate.leave()
    def reject(self): self.leave()
    def closeEvent(self, event): self.leave(); event.ignore()


class ChoiceRuntime:
    def __init__(self, runtime):
        self.runtime = runtime; self.app = runtime.app
        self.ledger = ChoiceLedger(self.app.store); self.visits = Visits()
        self.screen = None; self.target = None; self.atom = None; self.entries = []; self.pending = None
        self.settings = None; self.config_signature = None; self.enabled = False; self.return_grace = 0

    def owned(self):
        return bool(self.screen and self.screen.isVisible() and win32.u.GetForegroundWindow() == int(self.screen.winId()))

    def reset(self):
        self.visits.clear(); self.entries = []; self.pending = None; self.target = None; self.atom = None
        if self.screen: self.screen.hide()

    def candidates(self, atom, current):
        result = []
        for key in self.runtime.matching(atom):
            budget = self.runtime.state.budgets[key]
            if self.runtime.state.zero_budget(key): continue
            app_members = [m for m in budget.members if m['kind'] != 'site' and m != {'kind': 'category', 'value': 'sites'}]
            site_members = [m for m in budget.members if m['kind'] == 'site' or m == {'kind': 'category', 'value': 'sites'}]
            for step in self.runtime.state.plans[key]['steps']:
                if not step.get('session_choice'): continue
                scope = next((name for name,members in (('site',site_members),('app',app_members))
                    if applies(members,atom) and step.get('targets',{}).get(name,{}).get('enabled',True)),None)
                if not scope: continue
                bridge=self.app.browser_bridge
                if scope=='site' and bridge and bridge.uses_site_choices(current.path): continue
                subject = 'app:' + app_key(current.path) if scope == 'app' else 'site:' + atom[2]
                if self.runtime.state.action(key, subject, current.identity): continue
                result.append((budget, step, current.identity + ':' + subject, allowance_activity(budget.members,atom,scope)))
        return result

    def restricted(self):
        if not self.target or not self.atom: return True
        if self.runtime.legacy_block(self.atom): return True
        for key in self.runtime.matching(self.atom):
            members = self.runtime.state.budgets[key].members
            for scope, selected in (
                ('app:' + app_key(self.target.path), [m for m in members if m['kind'] != 'site' and m != {'kind':'category','value':'sites'}]),
                ('site:' + self.atom[2], [m for m in members if m['kind'] == 'site' or m == {'kind':'category','value':'sites'}])):
                if applies(selected, self.atom) and self.runtime.state.action(key, scope, self.target.identity): return True
        return False

    def defer_to_restriction(self):
        target = self.target; self.reset()
        if target: native.restore_target(target.path, target.identity)

    def tick(self, current, website, blocked=False):
        settings = self.app.settings
        if self.settings is not settings:
            self.settings = settings
            signature = json.dumps(settings.restriction_plans, sort_keys=True)
            if self.config_signature != signature:
                self.config_signature = signature; self.reset()
                self.enabled = any(step.get('session_choice') for plan in settings.restriction_plans.values() for step in plan['steps'])
        if not self.enabled: return False
        if not current.interactive or blocked: self.reset(); return False
        if self.owned():
            handle = native.open_target(self.target.path, self.target.identity) if self.target else None
            if not handle: self.reset(); return False
            win32.k.CloseHandle(handle)
            if self.restricted(): self.defer_to_restriction(); return False
            # Renewal and editing are rechecked without manufacturing a visit.
            return self.present()
        if current.identity.startswith(str(os.getpid()) + ':') and time.monotonic() < self.return_grace:
            return False
        if (self.target and current.identity == self.target.identity and self.atom and self.atom[2]
                and not website and time.monotonic() < self.return_grace):
            # The browser reports losing focus to our question. Let its focus
            # event restore the domain before ending the accepted visit.
            return False
        atom = self.app.wellbeing.atom(current, website)
        if not atom or not native.permitted(current.path, current.identity) or self.runtime.legacy_block(atom):
            self.reset(); return False
        entries = self.candidates(atom, current)
        self.visits.observe({(budget.key, step['id']): subject for budget, step, subject, activity in entries})
        self.entries = entries; self.target = current; self.atom = atom
        if self.restricted(): self.reset(); return False
        return self.present()

    def present(self):
        self.pending = None
        for old_budget, old_step, subject, activity in self.entries:
            budget = self.runtime.state.budgets.get(old_budget.key)
            plan = self.runtime.state.plans.get(old_budget.key, {})
            step = next((s for s in plan.get('steps', ()) if s['id'] == old_step['id'] and s.get('session_choice')), None)
            if not budget or not step: continue
            visit = self.visits.current.get((budget.key, step['id']))
            if not visit: continue
            if visit['choice'] is not None: continue
            recalled=self.ledger.recalled(budget.key,step['id'],budget.day,visit['token'],step['session_choice'],self.runtime.state.now,activity)
            if recalled is not None:
                visit['choice']=recalled
                continue
            self.pending = budget, step, visit, activity
            break
        if not self.pending:
            if self.screen: self.screen.hide()
            return False
        budget, step, visit, activity = self.pending
        if self.screen is None: self.screen = ChoiceScreen(self)
        screen = self.screen
        same = bool(screen.isVisible() and screen.target and self.target and screen.target.identity == self.target.identity)
        screen.target = self.target
        options = self.ledger.options(budget.key, step['id'], budget.day, step['session_choice'], activity)
        screen.render(budget, step['session_choice'], options, activity)
        self.runtime.position_screen(screen, self.target, same)
        if not same and screen.isVisible():
            # The question is not application use. Do not count the sample that
            # opened it as an extra measured visit before the accepted visit.
            previous = self.app.focus.previous
            if previous and previous[0].identity == self.target.identity: self.app.focus.previous = None
            previous = self.app.tracker.previous
            if previous and previous.identity == self.target.identity: self.app.tracker.previous = None
        return screen.isVisible()

    def choose(self, identity):
        if not self.pending or not self.target: return False
        from datetime import datetime
        self.runtime.prepare(datetime.now().astimezone())
        if self.restricted(): self.defer_to_restriction(); return False
        budget, step, visit, activity = self.pending
        current_budget = self.runtime.state.budgets.get(budget.key)
        current_plan = self.runtime.state.plans.get(budget.key, {})
        current_step = next((s for s in current_plan.get('steps', ()) if s == step), None)
        handle = native.open_target(self.target.path, self.target.identity)
        if handle: win32.k.CloseHandle(handle)
        if not current_budget or not current_step or not handle:
            self.reset(); return False
        if not self.ledger.choose(budget.key, step['id'], current_budget.day, visit['token'], step['session_choice'], identity, self.runtime.state.now, activity):
            self.present(); return False
        visit['choice'] = identity
        target = self.target
        if not self.present():
            self.return_grace = time.monotonic() + 3
            self.runtime.audio.close(); native.restore_target(target.path, target.identity)
        return True

    def leave(self):
        target = self.target; self.reset(); self.runtime.audio.close()
        if target: native.minimize_target(target.path, target.identity)

    def close(self):
        self.reset()
        if self.screen: self.screen.deleteLater(); self.screen = None
