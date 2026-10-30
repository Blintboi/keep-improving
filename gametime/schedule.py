"""Local day plans; an overnight sleep window belongs to its reminder day."""
from dataclasses import replace
from datetime import date,datetime,timedelta
from .quota import current_day

SCHEDULE_FIELDS=('warning_seconds','limit_seconds','budget_reset_minute','restriction_enabled','restriction_seconds',
                 'bedtime_enabled','bedtime_warning_minute','bedtime_minute','bedtime_resume_minute','bedtime_minimize','bedtime_caps_budget')
DAY_NAMES=('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')


class DayScheduleError(ValueError):
    def __init__(self,day,error):
        self.day,self.error=day,error
        super().__init__(f'Day {day+1}: {error}')


def day_settings(settings,day=None):
    day=day or current_day(settings)
    if isinstance(day,str): day=date.fromisoformat(day)
    if isinstance(day,datetime): day=day.date()
    if str(day.weekday()) in settings.daily_schedules:
        values={k:v for k,v in settings.daily_schedules[str(day.weekday())].items() if k!='budget_reset_minute'}
        return replace(settings,weekend_enabled=False,daily_schedules={},**values)
    if settings.weekend_enabled and day.weekday()>=5 and settings.weekend_schedule:
        values={k:v for k,v in settings.weekend_schedule.items() if k!='budget_reset_minute'}
        return replace(settings,weekend_enabled=False,daily_schedules={},**values)
    return settings


def week_plans(settings):
    # An arbitrary Monday anchors weekday numbers without depending on today.
    monday=date(2026,1,5)
    return {day:{key:getattr(day_settings(settings,monday+timedelta(days=day)),key) for key in SCHEDULE_FIELDS if key!='budget_reset_minute'} for day in range(7)}


def bedtime_occurrence(settings,wall):
    minute=wall.hour*60+wall.minute
    today=current_day(settings,wall)
    # Finish an overnight window at its own resume time before applying the
    # next day's plan, including overlapping reminder times on that next day.
    for offset in (1,0):
        day=today-timedelta(days=offset); plan=day_settings(settings,day)
        warning_day=day+timedelta(days=plan.bedtime_warning_minute<settings.budget_reset_minute)
        elapsed=(wall.date()-warning_day).days*1440+minute-plan.bedtime_warning_minute
        warning=(plan.bedtime_minute-plan.bedtime_warning_minute)%1440
        end=warning+(plan.bedtime_resume_minute-plan.bedtime_minute)%1440
        if plan.bedtime_enabled and 0<=elapsed<end:
            return ('warning' if elapsed<warning else 'bedtime'),day.isoformat(),plan
    plan=day_settings(settings,today)
    day=today-timedelta(days=(minute-settings.budget_reset_minute)%1440<(plan.bedtime_warning_minute-settings.budget_reset_minute)%1440)
    return 'off',day.isoformat(),plan


def game_settings(settings,gid):
    override=settings.game_overlays.get(gid,{})
    return replace(settings,**override) if override else settings


def any_countdown(settings):
    return settings.overlay_enabled or any(value.get('overlay_enabled',False) for value in settings.game_overlays.values())
