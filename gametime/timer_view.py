"""Read-only projections of the next real event in each time budget."""
from dataclasses import dataclass,replace
import math
from .restriction_policy import target_steps


LABELS={'break':'Break in','break_active':'Break remaining','limit':'Restriction in',
        'clock_limit':'Daily closing in','quota':'Budget remaining','warning':'Warning in',
        'save':'Save time remaining','focus':'Focus remaining'}
PRIORITY={'save':-1,'limit':0,'clock_limit':0,'quota':1,'break_active':2,'break':3,'warning':4,'focus':5}


@dataclass(frozen=True)
class TimerView:
    key: str
    name: str
    event: str
    seconds: float
    total: float=math.inf
    wall_clock: bool=False
    scope: str=''
    active: bool=False

    @property
    def order(self): return (max(0,self.seconds),PRIORITY[self.event],self.name.casefold(),self.key,self.scope)

    def label(self,t): return t(LABELS[self.event])

    def secondary(self,t):
        return t('Daily budget left: {time}',time=clock(self.total)) if math.isfinite(self.total) and self.event!='quota' else ''


def clock(seconds):
    value=max(0,math.ceil(seconds))
    return f'{value//3600:02d}:{value%3600//60:02d}:{value%60:02d}' if value>=3600 else f'{value//60:02d}:{value%60:02d}'


def project(budget,plan,row,now,subject,elapsed=0,identity=None,*,running_only=False):
    """No state transitions or writes: break scheduling belongs to RestrictionState."""
    used=budget.used+elapsed; total=max(0,budget.limit-used)
    def item(event,seconds,wall=False):
        return TimerView(budget.key,budget.name,event,max(0,seconds),total,wall,subject.split(':',1)[0])
    if budget.limit==0: return item('limit',0)
    grant=row.get('grant') or {}; owner=grant.get('subject','')
    matches=owner==subject or subject.startswith('site:') and owner.startswith(subject+':')
    if matches and (not identity or not grant.get('identity') or grant['identity']==identity):
        if grant['until']>now: return item('save',grant['until']-now,True)
        return item('limit',0)
    choices=[item('quota',total)] if math.isfinite(total) and not running_only else []
    regular=[]; breaks=[]
    for step in target_steps(plan or {'steps':[]},subject):
        kind=step['kind']; mode=step.get('time_mode'); wall=mode=='clock'
        if kind=='notify' and (step['id'] in row.get('delivered',()) or not (step['sound'] or step['popup'])): continue
        if wall: seconds=(budget.clock_deadlines or {}).get(step['clock_minute'],math.inf)-now
        elif mode=='usage': seconds=step['offset']-used
        elif step['offset']<=0: seconds=max(0,budget.limit+step['offset'])-used
        else: seconds=(row['expired']+step['offset']-now) if row.get('expired') is not None else total+step['offset']
        if kind=='break':
            state=row.get('breaks',{}).get(step['id'],{}); until=state.get('until')
            if until is not None and until>now:
                breaks.append(item('break_active',until-now,True)); continue
            if not budget.breaks_allowed or used>=budget.limit: continue
            if wall:
                # A missed/finished clock break never restarts later that day.
                if seconds<=0 or state.get('triggered'): continue
            else:
                if running_only: continue
                threshold=state.get('next_at',step['offset'])
                if until is not None: threshold=used+step['offset']
                if threshold>=budget.limit: continue
                seconds=threshold-used
            if math.isfinite(seconds): breaks.append(item('break',seconds,wall))
        elif math.isfinite(seconds) and (not running_only or wall or seconds<=0 or mode is None and step['offset']>0 and row.get('expired') is not None):
            event='warning' if kind=='notify' else 'clock_limit' if wall else 'limit'
            event_item=item(event,seconds,wall or mode is None and step['offset']>0 and row.get('expired') is not None); choices.append(event_item)
            if kind!='notify': regular.append(event_item)
    # A due restriction takes precedence over a simultaneous ongoing break.
    if not any(event.seconds<=0 for event in regular):
        active=[event for event in breaks if event.event=='break_active']
        if running_only and active: return min(active,key=lambda event:event.order)
        if active: choices=[event for event in choices if event.event!='quota' and (event.wall_clock or event.seconds<=0)]
        choices.extend(breaks)
    if total<=0 and any(event.event!='quota' for event in choices):
        choices=[event for event in choices if event.event!='quota']
    return min(choices,key=lambda event:event.order) if choices else None


def ordered(events):
    # Current activity first; ongoing breaks remain visible after redirect/switch.
    def priority(event):
        if not event.active: return int(event.event not in ('save','break_active'))
        if event.event in ('limit','clock_limit') and event.seconds<=0: return 0
        return 1 if event.event=='save' else 2
    return sorted(events,key=lambda event:(not event.active,priority(event),event.order))


def tooltip(events,t,limit=127):
    current=next((event for event in events if event.active),None)
    rest=sorted((event for event in events if event.event=='break_active' and event!=current),key=lambda event:event.order)
    main=current or (rest.pop(0) if rest else next(iter(events),None))
    lines=['Keep Improving']
    if main:
        lines.append(f'{main.name[:24]} · {main.label(t)} {clock(main.seconds)}')
        if main.secondary(t): lines.append(main.secondary(t))
        if rest: lines.append(f'{rest[0].name[:20]} · {t("Break remaining")} {clock(rest[0].seconds)}')
        if len(rest)>1: lines.append(t('+{count} more timers',count=len(rest)-1))
    else: lines.append(t('No active timers'))
    # Windows measures this field in UTF-16 units, including names with emoji.
    return '\n'.join(lines).encode('utf-16-le')[:limit*2].decode('utf-16-le',errors='ignore')
