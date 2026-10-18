"""Daily summaries over existing recorded time; never infer missing gameplay."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta


def date_range(start, end):
    try:
        first, last = date.fromisoformat(str(start)), date.fromisoformat(str(end))
        if first.isoformat() != str(start) or last.isoformat() != str(end):
            raise ValueError()
    except ValueError:
        raise ValueError("Use dates in YYYY-MM-DD format.") from None
    if first > last:
        raise ValueError("The start date must not be after the end date.")
    if (last-first).days >= 366:
        raise ValueError("Choose a period of up to 366 days.")
    return [first+timedelta(days=offset) for offset in range((last-first).days+1)]


@dataclass
class Report:
    days: dict
    games: list
    by_day: dict

    @property
    def total(self):
        return sum(self.days.values())

    @property
    def average(self):
        return self.total / len(self.days) if self.days else 0


def summarize(rows, start, end):
    days = {day.isoformat(): 0.0 for day in date_range(start, end)}
    games, by_day = {}, defaultdict(dict)
    for day, gid, name, source, seconds in rows:
        if day not in days or seconds <= 0:
            continue
        days[day] += seconds
        games.setdefault(gid, [gid, name, source, 0.0])[3] += seconds
        by_day[day].setdefault(gid, [gid, name, source, 0.0])[3] += seconds
    key = lambda row: (-row[3], row[1].casefold(), row[0])
    return Report(days, sorted(games.values(), key=key),
                  {day: sorted(values.values(), key=key) for day, values in by_day.items()})
