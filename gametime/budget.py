"""Shared-game budget and its optional bedtime cap."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
from . import budget_access
from .schedule import day_settings, bedtime_occurrence
from .quota import period_day, reset_clock, budget_day


def quota_plan(settings, wall=None):
    return day_settings(settings, budget_day(settings, 'shared-games', wall))


def game_remaining(settings, game_id, used, wall=None):
    key='game:'+game_id
    if game_id not in settings.game_limits or not budget_access.active(settings,key,wall): return None
    cap=budget_access.limit(settings,key,settings.game_limits[game_id],wall)
    remaining=min(max(0,cap-used),budget_access.clock_remaining(settings,key,wall,'app:'))
    return remaining if math.isfinite(remaining) else None


def gameplay_budget(settings, wall, totals, game_id, elapsed=0, game_used=None, game_elapsed=None):
    """Overlay time is the smallest applicable cap; the Hub keeps the shared cap."""
    budget = remaining_budget(settings, wall, sum(totals.values()) + elapsed)
    own = game_remaining(settings, game_id, (totals.get(game_id, 0) if game_used is None else game_used)
                         + (elapsed if game_elapsed is None else game_elapsed),wall)
    if own is not None and own <= budget.remaining:
        warning_at=min(600,settings.game_limits[game_id]/5) if budget_access.usage_enabled(settings,'game:'+game_id) else 600
        return RemainingBudget(own, budget.quota_remaining,
                               budget.warning or own <= warning_at)
    return budget


@dataclass(frozen=True)
class RemainingBudget:
    remaining: float
    quota_remaining: float
    warning: bool
    bedtime: datetime | None = None


def _deadline(day, plan, wall):
    day+=timedelta(days=plan.bedtime_warning_minute<plan.budget_reset_minute)
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
    enabled=settings.game_budget_enabled and budget_access.active(settings,'shared-games',wall)
    usage=enabled and budget_access.usage_enabled(settings,'shared-games')
    quota = max(0, plan.limit_seconds - used) if usage else math.inf
    clock=budget_access.clock_remaining(settings,'shared-games',wall,'app:') if enabled else math.inf
    remaining=min(quota,clock)
    warning = usage and used >= plan.warning_seconds or clock<=600
    # No date searches or extra work for existing profiles with this option off.
    if not (settings.bedtime_caps_budget
            or settings.weekend_enabled and settings.weekend_schedule.get('bedtime_caps_budget')
            or any(value.get('bedtime_caps_budget') for value in settings.daily_schedules.values())):
        return RemainingBudget(remaining, quota, warning)
    state, day, night = bedtime_occurrence(settings, wall)
    if state != 'off':
        deadline = _deadline(datetime.fromisoformat(day).date(), night, wall)
    else:
        candidates = []
        for offset in (-1, 0, 1):
            day = period_day(wall,reset_clock(settings)) + timedelta(days=offset)
            night = day_settings(settings, day)
            if night.bedtime_enabled and day.weekday() in settings.budget_active_days.get('computer-window',range(7)):
                deadline = _deadline(day, night, wall)
                if deadline.timestamp() > wall.timestamp():
                    candidates.append((deadline, night))
        if not candidates:
            return RemainingBudget(remaining, quota, warning)
        deadline, night = min(candidates, key=lambda item: item[0].timestamp())
    if night.bedtime_caps_budget:
        seconds = max(0, deadline.timestamp() - wall.timestamp())
        if seconds <= remaining:
            return RemainingBudget(seconds, quota, warning or state in ('warning', 'bedtime'), deadline)
    return RemainingBudget(remaining, quota, warning)
