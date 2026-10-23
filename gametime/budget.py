"""Optional bedtime cap on displayed time; measured usage stays calendar-based."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from .schedule import day_settings, bedtime_occurrence


@dataclass(frozen=True)
class RemainingBudget:
    remaining: float
    quota_remaining: float
    warning: bool
    bedtime: datetime | None = None


def _deadline(day, plan, wall):
    # Bedtimes after midnight belong to the day their reminder starts.
    minutes = plan.bedtime_warning_minute + (plan.bedtime_minute - plan.bedtime_warning_minute) % 1440
    value = datetime.combine(day, time.min) + timedelta(minutes=minutes)
    # Native samples carry today's fixed local UTC offset. Ask Windows for the
    # deadline's own offset so an overnight DST change cannot add/remove an hour.
    if wall.tzinfo is not None and wall.tzinfo == wall.astimezone().tzinfo:
        return value.astimezone()
    return value.replace(tzinfo=wall.tzinfo)


def remaining_budget(settings, wall, used):
    plan = day_settings(settings, wall)
    quota = max(0, plan.limit_seconds - used)
    warning = used >= plan.warning_seconds
    # No date searches or extra work for existing profiles with this option off.
    if not (settings.bedtime_caps_budget
            or settings.weekend_enabled and settings.weekend_schedule.get('bedtime_caps_budget')
            or any(value.get('bedtime_caps_budget') for value in settings.daily_schedules.values())):
        return RemainingBudget(quota, quota, warning)
    state, day, night = bedtime_occurrence(settings, wall)
    if state != 'off':
        deadline = _deadline(datetime.fromisoformat(day).date(), night, wall)
    else:
        candidates = []
        for offset in (-1, 0, 1):
            day = wall.date() + timedelta(days=offset)
            night = day_settings(settings, day)
            if night.bedtime_enabled:
                deadline = _deadline(day, night, wall)
                if deadline.timestamp() > wall.timestamp():
                    candidates.append((deadline, night))
        if not candidates:
            return RemainingBudget(quota, quota, warning)
        deadline, night = min(candidates, key=lambda item: item[0].timestamp())
    if night.bedtime_caps_budget:
        seconds = max(0, deadline.timestamp() - wall.timestamp())
        if seconds <= quota:
            return RemainingBudget(seconds, quota, warning or state in ('warning', 'bedtime'), deadline)
    return RemainingBudget(quota, quota, warning)
