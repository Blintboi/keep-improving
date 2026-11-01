"""Independent, named computer schedules, retaining the original schedule identity."""
from copy import deepcopy
from dataclasses import replace
import re

FIELDS=('bedtime_enabled','bedtime_warning_enabled','bedtime_warning_minute','bedtime_minute',
        'bedtime_resume_minute','bedtime_minimize','bedtime_caps_budget')


def validate(settings):
    periods=settings.computer_periods
    if not isinstance(periods,list) or len(periods)>100: raise ValueError('Invalid computer-use period.')
    keys=set()
    for item in periods:
        if (not isinstance(item,dict) or set(item)!={'id','name','values'}
                or not isinstance(item['id'],str) or not re.fullmatch(r'computer-[a-zA-Z0-9_-]{1,55}',item['id'])
                or item['id']=='computer-window' or item['id'] in keys
                or not isinstance(item['name'],str) or not item['name'].strip() or len(item['name'])>80 or '\0' in item['name']
                or not isinstance(item['values'],dict) or set(item['values'])!=set(FIELDS)):
            raise ValueError('Invalid computer-use period.')
        keys.add(item['id'])
        replace(settings,computer_periods=[],daily_schedules={},weekend_schedule={},weekend_enabled=False,
                game_overlays={},counter_overlays={},activity_overlays={},**item['values']).validate()


def project(settings,item):
    days=dict(settings.budget_active_days)
    days['computer-window']=days.get(item['id'],list(range(7)))
    resets=dict(settings.budget_reset_overrides)
    resets['computer-window']=resets.get(item['id'],settings.budget_reset_minute)
    return replace(settings,computer_periods=[],daily_schedules={},weekend_schedule={},weekend_enabled=False,
                   budget_active_days=days,budget_reset_overrides=resets,budget_reset_minute=resets['computer-window'],
                   **item['values'])


def schedules(settings):
    primary=settings if not settings.computer_periods and 'computer-window' not in settings.budget_reset_overrides else replace(settings,computer_periods=[],
        budget_reset_minute=settings.budget_reset_overrides.get('computer-window',settings.budget_reset_minute))
    yield 'computer-window','Computer use',primary
    for item in settings.computer_periods: yield item['id'],item['name'],project(settings,item)


def split_weekly(settings):
    """Prepare editable fixed budgets without changing the applied configuration."""
    from .schedule import week_plans
    from .restriction_policy import new_plan,step,legacy_warning_active,legacy_restriction_active
    from .i18n import tr
    from hashlib import sha256
    import json
    plans=week_plans(settings); values={}; days=deepcopy(settings.budget_active_days)
    rules=deepcopy(settings.wellbeing_rules); periods=deepcopy(settings.computer_periods)
    actions=deepcopy(settings.restriction_plans); resets=dict(settings.budget_reset_overrides)
    usage=dict(settings.budget_usage_limits)
    for key,fields in (('shared-games',('limit_seconds','warning_seconds','restriction_enabled','restriction_seconds')),
                       ('computer-window',FIELDS)):
        groups={}
        for day,plan in plans.items():
            group=tuple(plan[field] for field in fields)
            groups.setdefault(group,[]).append(day)
        first=True
        for group,weekdays in groups.items():
            selected=[d for d in weekdays if d in settings.budget_active_days.get(key,range(7))]
            data=dict(zip(fields,group))
            if first:
                values.update(data); first=False
                if len(groups)>1: days[key]=selected
                continue
            identity=sha256(json.dumps([key,group,weekdays]).encode()).hexdigest()[:20]
            newkey=('computer-' if key=='computer-window' else 'games-')+identity
            if key=='computer-window':
                if not data['bedtime_enabled']: continue
                periods.append(dict(id=newkey,name=tr('Computer use',settings.language),values=data))
            else:
                if not settings.game_budget_enabled: continue
                rule=dict(id=newkey,name=tr('Games · shared budget',settings.language),members=[{'kind':'category','value':'games'}],
                          seconds=data['limit_seconds'],enabled=True,overlay=settings.overlay_enabled,enforce=False)
                rules.append(rule)
                plan=deepcopy(actions.get(key)) or new_plan(legacy=False)
                if legacy_warning_active(actions,key): plan['steps'].append(step('notify',data['warning_seconds'],usage=True,popup=True,identity='legacy-warning'))
                if legacy_restriction_active(actions,key) and data['restriction_enabled']:
                    plan['steps'].append(step('minimize',data['restriction_seconds'],usage=True,identity='legacy-limit'))
                for field in ('legacy','legacy_warning','legacy_enforce'): plan.pop(field,None)
                actions[newkey]=plan
                usage[newkey]=settings.budget_usage_limits.get(key,True)
            days[newkey]=selected
            if key in resets: resets[newkey]=resets[key]
    return replace(settings,weekend_enabled=False,weekend_schedule={},daily_schedules={},
                   wellbeing_rules=rules,computer_periods=periods,restriction_plans=actions,
                   budget_active_days=days,budget_reset_overrides=resets,budget_usage_limits=usage,**values)


def carry_runtime(store,previous,current,wall=None):
    """Preserve already granted save time and breaks when splitting old weekdays."""
    if not previous.daily_schedules and not previous.weekend_enabled: return
    import json
    from datetime import date
    from .quota import budget_day
    old_ids={r['id'] for r in previous.wellbeing_rules}
    new=[r['id'] for r in current.wellbeing_rules if r['id'].startswith('games-') and r['id'] not in old_ids]
    if not new or not store.db.execute("SELECT 1 FROM sqlite_master WHERE name='restriction_state'").fetchone(): return
    rows=dict(store.db.execute("SELECT day,value FROM restriction_state WHERE budget='shared-games'"))
    rows.setdefault(budget_day(previous,'shared-games',wall).isoformat(),json.dumps(dict(expired=None,used_extension=False,grant=None,delivered=[])))
    with store.db:
        for key in new:
            for day,raw in rows.items():
                if date.fromisoformat(day).weekday() not in current.budget_active_days.get(key,range(7)): continue
                value=json.loads(raw)
                value['plan']=json.dumps(current.restriction_plans[key],sort_keys=True)
                warning=next((s for s in current.restriction_plans[key]['steps'] if s['id']=='legacy-warning'),None)
                def already_warned():
                    for alert in store.alert_keys(day):
                        parts=alert.split(':')
                        if len(parts)<2 or parts[-2]!='warning': continue
                        try:
                            if float(parts[-1])==warning['offset']: return True
                        except ValueError: pass
                    return False
                if warning and already_warned():
                    value['delivered']=sorted(set(value.get('delivered',[]))|{'legacy-warning'})
                store.db.execute('INSERT OR IGNORE INTO restriction_state VALUES (?,?,?)',(day,key,json.dumps(value)))
