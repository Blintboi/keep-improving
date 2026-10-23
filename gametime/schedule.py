"""Local day plans; an overnight sleep window belongs to its reminder day."""
from dataclasses import replace
from datetime import date,datetime,timedelta

SCHEDULE_FIELDS=('warning_seconds','limit_seconds','restriction_enabled','restriction_seconds',
                 'bedtime_enabled','bedtime_warning_minute','bedtime_minute','bedtime_resume_minute','bedtime_minimize','bedtime_caps_budget')
DAY_NAMES=('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')


class DayScheduleError(ValueError):
    def __init__(self,day,error):
        self.day,self.error=day,error
        super().__init__(f'Day {day+1}: {error}')


def day_settings(settings,day=None):
    day=day or date.today()
    if isinstance(day,str): day=date.fromisoformat(day)
    if isinstance(day,datetime): day=day.date()
    if str(day.weekday()) in settings.daily_schedules:
        return replace(settings,weekend_enabled=False,daily_schedules={},**settings.daily_schedules[str(day.weekday())])
    if settings.weekend_enabled and day.weekday()>=5 and settings.weekend_schedule:
        return replace(settings,weekend_enabled=False,daily_schedules={},**settings.weekend_schedule)
    return settings


def week_plans(settings):
    # An arbitrary Monday anchors weekday numbers without depending on today.
    monday=date(2026,1,5)
    return {day:{key:getattr(day_settings(settings,monday+timedelta(days=day)),key) for key in SCHEDULE_FIELDS} for day in range(7)}


def bedtime_occurrence(settings,wall):
    minute=wall.hour*60+wall.minute
    # Finish an overnight window at its own resume time before applying the
    # next day's plan, including overlapping reminder times on that next day.
    for offset in (1,0):
        day=wall.date()-timedelta(days=offset); plan=day_settings(settings,day)
        elapsed=offset*1440+minute-plan.bedtime_warning_minute
        warning=(plan.bedtime_minute-plan.bedtime_warning_minute)%1440
        end=warning+(plan.bedtime_resume_minute-plan.bedtime_minute)%1440
        if plan.bedtime_enabled and 0<=elapsed<end:
            return ('warning' if elapsed<warning else 'bedtime'),day.isoformat(),plan
    plan=day_settings(settings,wall.date())
    day=wall.date()-timedelta(days=minute<plan.bedtime_warning_minute)
    return 'off',day.isoformat(),plan


def game_settings(settings,gid):
    override=settings.game_overlays.get(gid,{})
    return replace(settings,**override) if override else settings


def any_countdown(settings):
    return settings.overlay_enabled or any(value.get('overlay_enabled',False) for value in settings.game_overlays.values())
