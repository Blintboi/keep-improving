"""One local day boundary for statistics, budgets and daily reminders."""
from datetime import datetime, time, timedelta


def reset_clock(settings):
    # Keep the existing persisted/synchronized field for upgrade compatibility.
    # Legacy per-weekday values no longer override the universal clock.
    return (settings.budget_reset_minute,) * 7


def current_day(settings,wall=None):
    return period_day(wall or datetime.now().astimezone(),reset_clock(settings))


def _minute(clock, day):
    return clock[day.weekday()]


def reset_at(day, minute, wall):
    value = datetime.combine(day, time(minute // 60, minute % 60))
    if wall.tzinfo is None:
        return value
    if wall.tzinfo == wall.astimezone().tzinfo:
        result = value.astimezone()
        # A nonexistent spring-forward time must not renew the quota early.
        if result.replace(tzinfo=None) < value:
            result = (value + timedelta(hours=1)).astimezone()
        return result
    return value.replace(tzinfo=wall.tzinfo, fold=0)


def period_day(wall, clock):
    day = wall.date()
    return day if wall.timestamp() >= reset_at(day, _minute(clock, day), wall).timestamp() else day - timedelta(days=1)


def period_slices(start, end, duration, clock):
    span = end.timestamp() - start.timestamp()
    if span <= 0:
        return
    cursor = start
    while cursor.timestamp() < end.timestamp():
        day = period_day(cursor, clock)
        tomorrow = day + timedelta(days=1)
        boundary = reset_at(tomorrow, _minute(clock, tomorrow), cursor)
        stop = min((end, boundary), key=lambda value: value.timestamp())
        yield day.isoformat(), duration * (stop.timestamp() - cursor.timestamp()) / span
        cursor = stop
