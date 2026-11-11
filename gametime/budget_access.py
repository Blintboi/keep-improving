"""Selected budget days, optional usage caps and renewal-relative clock actions."""
from datetime import datetime,timedelta
import math
from .quota import budget_day,budget_minute,reset_at


def active(settings,key,wall=None):
    from .device_scopes import applies,budget
    if not applies(budget(settings,key),settings):return False
    days=settings.budget_active_days.get(key)
    return days is None or bool(days) and budget_day(settings,key,wall).weekday() in days


def usage_enabled(settings,key):
    return settings.budget_usage_limits.get(key,True)


def limit(settings,key,seconds,wall=None):
    return seconds if active(settings,key,wall) and usage_enabled(settings,key) else math.inf


def clock_deadlines(settings,key,wall=None):
    minutes={s['clock_minute'] for s in settings.restriction_plans.get(key,{}).get('steps',()) if s.get('time_mode')=='clock'}
    if not minutes: return {}
    wall=wall or datetime.now().astimezone()
    day=budget_day(settings,key,wall); renewal=budget_minute(settings,key)
    return {minute:reset_at(day+timedelta(days=minute<renewal),minute,wall).timestamp() for minute in minutes}


def clock_remaining(settings,key,wall=None,subject=None):
    plan=settings.restriction_plans.get(key)
    if plan is None: return math.inf
    wall=wall or datetime.now().astimezone()
    if not active(settings,key,wall): return math.inf
    from .restriction_policy import target_steps
    ends=clock_deadlines(settings,key,wall)
    return min((max(0,ends[s['clock_minute']]-wall.timestamp()) for s in target_steps(plan,subject)
                if s.get('time_mode')=='clock' and s['kind'] not in ('notify','break')),default=math.inf)


def validate(settings):
    for mapping in (settings.budget_active_days,settings.budget_usage_limits):
        if not isinstance(mapping,dict) or len(mapping)>2200 or any(
                not isinstance(key,str) or not key or len(key)>2053 or '\0' in key for key in mapping):
            raise ValueError('Invalid budget availability settings.')
    for days in settings.budget_active_days.values():
        if not isinstance(days,list) or any(type(day) is not int or not 0<=day<7 for day in days) or len(days)!=len(set(days)):
            raise ValueError('Choose valid active days for the budget.')
    if any(type(value) is not bool for value in settings.budget_usage_limits.values()):
        raise ValueError('Invalid budget availability settings.')
