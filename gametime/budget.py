"""Optional bedtime cap on displayed time; measured usage stays calendar-based."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from .schedule import day_settings, bedtime_occurrence
from .quota import period_day, reset_clock


def quota_plan(settings, wall=None):
    return day_settings(settings, period_day(wall or datetime.now().astimezone(), reset_clock(settings)))


def game_remaining(settings, game_id, used):
    limit = settings.game_limits.get(game_id)
    return max(0, limit - used) if limit is not None else None


def gameplay_budget(settings, wall, totals, game_id, elapsed=0):
    """Overlay time is the smallest applicable cap; the Hub keeps the shared cap."""
    budget = remaining_budget(settings, wall, sum(totals.values()) + elapsed)
    own = game_remaining(settings, game_id, totals.get(game_id, 0) + elapsed)
    if own is not None and own <= budget.remaining:
        return RemainingBudget(own, budget.quota_remaining,
                               budget.warning or own <= min(600, settings.game_limits[game_id] / 5))
    return budget


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
    plan = quota_plan(settings, wall)
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
