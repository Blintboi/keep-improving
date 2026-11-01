"""One timer selection shared by the desktop/RTSS HUD and native tray."""
from dataclasses import replace
from datetime import datetime
from collections import Counter
import math
from .timer_view import TimerView,project,ordered,clock
from .wellbeing import applies
from .focus import app_key
from .quota import budget_day
from .activities import activity_settings,foreground_target
from .budget import quota_plan,remaining_budget
from .restriction_policy import legacy_warning_active,legacy_restriction_active,step


class TimerActions:
    def timer_budget_key(self,wall):
        return (int(wall.timestamp()),id(self.settings),id(self.tracker.previous),id(self.wellbeing.current),self.wellbeing.revision)

    def timer_views(self,current=None,wall=None,*,overlays=False):
        runtime=self.restrictions; current=current or runtime.current or self.tracker.previous
        wall=wall or (current.wall if current else datetime.now().astimezone()); now=wall.timestamp()
        cache_key=self.timer_budget_key(wall)
        if getattr(self,'_timer_budget_key',None)!=cache_key:
            self._timer_budget_key=cache_key; self._timer_budgets=runtime.budgets(wall)
        website=self.browser_bridge.website(current.path) if current and self.browser_bridge else ''
        atom=self.wellbeing.atom(current,website) if current and abs(now-current.wall.timestamp())<3 else None
        redirect=getattr(self.browser_bridge,'redirect_budget',lambda path:'')(current.path) if current and self.browser_bridge else ''
        member=foreground_target(self.settings,atom) if atom else None
        scopes=[]
        if atom:
            scopes.append('app:'+app_key(current.path))
            if atom[2]: scopes.append('site:'+atom[2])
        prepared=getattr(runtime,'timer_wall',None)
        event_now=max(now,runtime.state.now+max(0,now-prepared.timestamp())) if prepared else now
        result=[]; rules={rule['id']:rule for rule in self.settings.wellbeing_rules}
        for budget in self._timer_budgets:
            plan=self.settings.restriction_plans.get(budget.key)
            legacy=[]; rule=rules.get(budget.key)
            if math.isfinite(budget.limit):
                if budget.key=='shared-games':
                    daily=quota_plan(self.settings,wall)
                    if legacy_warning_active(self.settings.restriction_plans,budget.key) and budget.used<daily.warning_seconds:
                        legacy.append(step('notify',daily.warning_seconds,usage=True,popup=True,identity='legacy-warning'))
                    if legacy_restriction_active(self.settings.restriction_plans,budget.key) and daily.restriction_enabled:
                        legacy.append(step('minimize',daily.restriction_seconds,usage=True,identity='legacy-limit'))
                elif legacy_restriction_active(self.settings.restriction_plans,budget.key) and (budget.key.startswith('game:') or rule and rule['enforce']):
                    legacy.append(step('minimize',budget.limit,usage=True,identity='legacy-limit'))
            if legacy: plan=dict(plan or {},steps=[*(plan or {}).get('steps',()),*legacy])
            row=runtime.state.rows.get(budget.key,{}) if runtime.state.days.get(budget.key)==budget.day else {}
            present=set()
            for subject in scopes:
                relevant=[m for m in budget.members if (m['kind']=='site' or m=={'kind':'category','value':'sites'})==subject.startswith('site:')]
                if budget.key==redirect or not applies(relevant,atom): continue
                if overlays:
                    if not activity_settings(self.settings,member,rule).overlay_enabled: continue
                elapsed=0
                previous=self.tracker.previous if budget.key=='shared-games' or budget.key.startswith('game:') else self.wellbeing.current[0] if self.wellbeing.current else None
                if previous and current.identity==previous.identity and budget_day(self.settings,budget.key,previous.wall)==budget_day(self.settings,budget.key,wall):
                    delta=current.awake-previous.awake
                    if 0<delta<=1.5 and abs((wall-previous.wall).total_seconds()-delta)<1.5: elapsed=delta
                event=project(budget,plan,row,event_now,subject,elapsed,current.identity)
                if event: result.append(replace(event,active=True)); present.add(event.scope)
            if overlays: continue
            # A running break/save countdown is independent of foreground use.
            for scope in ('app','site'):
                if scope in present: continue
                members=[m for m in budget.members if (m['kind']=='site' or m=={'kind':'category','value':'sites'})==(scope=='site')]
                if not members: continue
                grant=row.get('grant') or {}; subject=grant.get('subject',scope+':')
                if not subject.startswith(scope+':'): subject=scope+':'
                event=project(budget,plan,row,event_now,subject,running_only=True)
                if event and event.wall_clock and event.seconds>0: result.append(event)
        # Existing scheduled computer-use caps remain part of game countdowns.
        if not overlays or atom and atom[0]:
            budget=remaining_budget(self.settings,wall,sum(self.tracker.quota_totals(wall).values()))
            if budget.bedtime:
                result.append(TimerView('computer-window',str(self.t('Computer use')),'clock_limit',budget.remaining,budget.quota_remaining,True,'app',bool(atom and atom[0])))
        if not overlays and self.focus.running:
            result.append(TimerView('focus',str(self.t('Focus mode')),'focus' if self.focus.phase=='focus' else 'break_active',self.focus.remaining,wall_clock=True))
        # Identical native/site timers in a mixed budget share one tray row.
        unique={}
        for event in result:
            key=(event.key,event.event,math.ceil(event.seconds),event.total)
            if key not in unique or event.active: unique[key]=event
        values=list(unique.values())
        counts=Counter(value.key for value in values); repeated={key for key,count in counts.items() if count>1}
        values=[replace(value,name=value.name+' · '+str(self.t('Websites' if value.scope=='site' else 'Applications')))
                if value.key in repeated else value for value in values]
        return ordered(values)

    def overlay_timer_view(self,current):
        events=self.timer_views(current,overlays=True)
        if not events: return None
        # A granted save interval suppresses the same activity's break display.
        saves=[event for event in events if event.event=='save']
        blocking=[event for event in events if event.event in ('limit','clock_limit') and event.seconds<=0]
        event=min(blocking or saves or events,key=lambda event:event.order)
        return replace(event,total=min(value.total for value in events))

    def timer_menu_items(self):
        events=self.timer_views(wall=datetime.now().astimezone()); self._tray_timer_targets={}
        items=[(0,self.t('Timers'))]
        for index,event in enumerate(events):
            command=1000+index; self._tray_timer_targets[command]=event.key
            caption=f'{event.name} · {event.label(self.t)} {clock(event.seconds)}'
            if event.secondary(self.t): caption+=' · '+event.secondary(self.t)
            items.append((command,caption))
        if not events: items.append((0,self.t('No active timers')))
        return items

    def open_timer(self,command):
        key=getattr(self,'_tray_timer_targets',{}).get(command)
        if not key: return False
        self.show()
        if key=='focus': self.switch_page(4)
        else: self.open_budget(); self.budget_editor.show_editor(key)
        return True
