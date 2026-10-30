"""Foreground-safe presentation and opt-in enforcement for digital budgets."""
from dataclasses import replace
import logging
import time
from . import win32
from .overlay import choose_screen,foreground_screen_name
from .overlay_consent import display_reason as overlay_reason
from .tracker import Alert
from .quota import current_day
from .wellbeing import applies,counter_settings
from .activities import activity_settings,foreground_target

log=logging.getLogger(__name__)


class WellbeingActions:
    def wellbeing_states(self,current):
        website=self.browser_bridge.website(current.path) if self.browser_bridge else ''
        atom=self.wellbeing.atom(current,website)
        return self.wellbeing.states(current.wall,atom) if atom else []

    def wellbeing_tick(self,current,bedtime=False):
        states=self.wellbeing_states(current)
        exhausted=[state for state in states if state.remaining<=0 and state.rule['id'] not in self.settings.restriction_plans]
        if not exhausted or bedtime:
            self._wellbeing_grace=None; return False
        day=current_day(self.settings,current.wall).isoformat()
        # One delivery per budget, threshold and day, durable across restart.
        if not self.popup_window:
            if getattr(self,'_wellbeing_alert_day',None)!=day:
                self._wellbeing_alert_day=day; self._wellbeing_delivered=self.store.alert_keys(day)
            delivered=self._wellbeing_delivered
            for state in exhausted:
                key=f'wellbeing:{state.rule["id"]}:{state.rule["seconds"]:g}'
                if key in delivered: continue
                alert=Alert(day,(key,),'wellbeing',self.t('{name}: your {minutes:g}-minute budget is used up.',
                    name=self.t(state.rule['name']) if state.rule['id'].startswith('category-') else state.rule['name'],minutes=state.rule['seconds']/60),self.t('OK'))
                if self.popup(alert):
                    self.wellbeing.flush(); self.store.mark_alert(day,(key,)); delivered.add(key)
                break
        website=self.browser_bridge.website(current.path) if self.browser_bridge else ''
        atom=self.wellbeing.atom(current,website)
        enforced=[state for state in exhausted if state.rule['enforce'] and applies(
            [m for m in state.rule['members'] if m['kind']!='site' and m!={'kind':'category','value':'sites'}],atom)]
        if not enforced or not current.identity or not self.minimization_allowed(current.path,current.identity):
            self._wellbeing_grace=None; return False
        key=(day,current.identity,current.path,tuple(state.rule['id'] for state in enforced))
        previous=getattr(self,'_wellbeing_grace',None)
        if (not previous or previous[0]!=key or not 0<=current.awake-previous[2].awake<=3
                or abs((current.wall-previous[2].wall).total_seconds()-(current.awake-previous[2].awake))>1.5):
            self._wellbeing_grace=(key,current.awake,current); return True
        self._wellbeing_grace=(key,previous[1],current)
        if current.awake-previous[1]<10: return True
        self._wellbeing_grace=None
        # Native helper rechecks foreground identity; never close or kill a process.
        if win32.minimize_game(current.path,current.identity,consented=True):
            self.set_status('Time budget reached. Take a break or adjust it on the Time budgets page.')
        return True

    def update_wellbeing_overlay(self):
        try:
            # Do not sample at 5 Hz without a visible or applicable countdown.
            active=self.wellbeing.active()
            if not active or not self.wellbeing.current:
                self.overlay_timer.stop(); self.hide_countdown(); return
            member=foreground_target(self.settings,self.wellbeing.current[1])
            if not any(activity_settings(self.settings,member,state.rule).overlay_enabled for state in active):
                self.overlay_timer.stop(); self.hide_countdown(); return
            current=win32.sample()
            website=self.browser_bridge.website(current.path) if self.browser_bridge else ''
            current_atom=self.wellbeing.atom(current,website)
            if not current_atom: self.hide_countdown(); self.overlay_timer.stop(); return
            member=foreground_target(self.settings,current_atom)
            states=[state for state in self.wellbeing_states(current) if activity_settings(self.settings,member,state.rule).overlay_enabled]
            if not states:
                self.overlay_timer.stop(); self.hide_countdown(); return
            if overlay_reason(self.catalog,current.path,self.catalog.resolve(current.path)):
                self.overlay_timer.stop(); self.hide_countdown(); return
            state=min(states,key=lambda value:value.remaining); remaining=state.remaining
            sample,atom=self.wellbeing.current
            website=self.browser_bridge.website(current.path) if self.browser_bridge else ''
            if current.identity!=sample.identity or self.wellbeing.atom(current,website)!=atom:
                self.hide_countdown(); return
            elapsed=current.awake-sample.awake
            if 0<elapsed<=1.5 and current_day(self.settings,current.wall)==current_day(self.settings,sample.wall) and abs((current.wall-sample.wall).total_seconds()-elapsed)<1.5:
                remaining=max(0,remaining-elapsed)
            if not self.overlay: return
            if self._rtss_publishing or self.rtss.identity: self.rtss.hide(); self._rtss_publishing=False
            if not self.rtss.desktop_ready: self.overlay.hide(); return
            settings=activity_settings(self.settings,member,state.rule)
            self.overlay.present(remaining,state.used,settings,choose_screen(settings.overlay_screen,foreground_screen_name()),warning=state.warning)
            self._overlay_backend='desktop'; self._overlay_identity=current.identity; self._overlay_updated=time.monotonic()
            self.overlay_failed=False
            if not self.overlay_timer.isActive(): self.overlay_timer.start()
        except Exception:
            log.exception('Digital budget countdown unavailable'); self.hide_countdown(); self.overlay_timer.stop()
