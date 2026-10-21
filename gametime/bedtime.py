"""Local daily bedtime schedule. No additional resident process or timer."""
from datetime import timedelta


def clock_text(minute):
    return f'{minute//60:02d}:{minute%60:02d}'


def phase(settings, wall):
    """Return phase and the reminder's date, including windows across midnight."""
    minute = wall.hour*60+wall.minute
    elapsed = (minute-settings.bedtime_warning_minute) % 1440
    warning = (settings.bedtime_minute-settings.bedtime_warning_minute) % 1440
    end = warning+(settings.bedtime_resume_minute-settings.bedtime_minute) % 1440
    day = wall.date()-timedelta(days=minute < settings.bedtime_warning_minute)
    return ('off' if not settings.bedtime_enabled or elapsed >= end else
            'warning' if elapsed < warning else 'bedtime'), day.isoformat()


class Bedtime:
    def __init__(self, store):
        self.store = store
        self.ledger = None
        self.keys = set()
        self.previous = None
        self.next_minimize = None
        self.warning_suppressed = False

    def update(self, settings, current, popup_available=True):
        state, day = phase(settings, current.wall)
        schedule = (settings.bedtime_enabled, settings.bedtime_warning_minute,
                    settings.bedtime_minute, settings.bedtime_resume_minute, settings.bedtime_minimize)
        ledger = (day, schedule)
        if ledger != self.ledger:
            if self.ledger is not None and self.ledger[1] != schedule:
                self.previous = self.next_minimize = None
            self.ledger = ledger
            self.keys = self.store.alert_keys(day) if settings.bedtime_enabled else set()
            self.warning_suppressed = False
        previous = self.previous
        self.previous = current
        continuous = False
        if previous and previous.interactive and current.interactive:
            awake = current.awake-previous.awake
            wall = current.wall.timestamp()-previous.wall.timestamp()
            continuous = 0 <= awake <= 3 and abs(wall-awake) <= 1.5
        # A reminder is never caught up after a missed minute, sleep or a clock
        # jump. A process started in the scheduled minute may show it once.
        key = 'bedtime:'+':'.join(map(str, schedule[1:4]))
        if state == 'warning' and (not current.interactive or previous is not None and not continuous):
            self.warning_suppressed = True
        warning = (state == 'warning' and current.interactive and popup_available
                   and current.wall.hour*60+current.wall.minute == settings.bedtime_warning_minute
                   and not self.warning_suppressed and key not in self.keys)
        active = state == 'bedtime' and settings.bedtime_minimize
        minimize = False
        if not active or not current.interactive:
            self.next_minimize = None
        elif self.next_minimize is None or not continuous:
            self.next_minimize = current.awake+10
        elif current.awake >= self.next_minimize:
            self.next_minimize = current.awake+10
            minimize = True
        return state, (day, key) if warning else None, minimize

    def delivered(self, marker):
        day, key = marker
        self.store.mark_alert(day, (key,))
        self.keys.add(key)
