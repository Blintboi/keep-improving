from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
from .model import blocked
from .i18n import tr
from .notification_text import notification_text
from .schedule import day_settings
from .budget import remaining_budget


@dataclass(frozen=True)
class Sample:
    wall: datetime
    awake: float
    path: str = ""
    identity: str = ""  # PID + process creation FILETIME, never PID alone
    interactive: bool = True


@dataclass(frozen=True)
class Alert:
    day: str
    keys: tuple
    kind: str
    text: str
    button: str


def day_slices(start, end, duration):
    """Split a verified short interval at local midnight, conserving measured time."""
    cursor = start
    span = end.timestamp() - start.timestamp()
    if span <= 0:
        return
    while cursor < end:
        midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=cursor.tzinfo)
        stop = min(end, midnight)
        seconds = duration * (stop.timestamp() - cursor.timestamp()) / span
        yield cursor.date().isoformat(), seconds
        cursor = stop


class Tracker:
    FLUSH_SECONDS = 10
    PENDING_SECONDS = 120

    def __init__(self, store, catalog):
        self.store, self.catalog = store, catalog
        self.previous = None
        self.unclassified = deque()
        self.pending = defaultdict(float)
        self.cache = {}
        self.alerts = deque()
        self.queued = set()
        self.last_flush = None
        self.active = None
        self.identity = ""

    def totals(self, day):
        day = str(day)
        if day not in self.cache:
            self.cache[day] = self.store.totals(day)
        return self.cache[day]

    def tick(self, sample):
        prev = self.previous
        self.previous = sample
        if prev:
            delta = sample.awake - prev.awake
            wall = sample.wall.timestamp() - prev.wall.timestamp()
            # Drop scheduler stalls, sleep/resume gaps, clock jumps, secure desktops.
            if (0 < delta <= 3 and abs(wall - delta) <= 1.5 and wall > 0
                    and prev.interactive and sample.interactive and prev.path and not blocked(prev.path)):
                self._interval(prev.path, prev.wall, sample.wall, delta)
        self.replay(sample.wall)
        self.active = self.catalog.resolve(sample.path) if sample.interactive else None
        self.identity = sample.identity if self.active else ""
        self.evaluate(sample.wall)
        if self.last_flush is None:
            self.last_flush = sample.awake
        if sample.awake - self.last_flush >= self.FLUSH_SECONDS:
            self.flush()
            self.last_flush = sample.awake

    def _interval(self, path, start, end, seconds):
        game = self.catalog.resolve(path)
        if game:
            self._credit(game, start, end, seconds)
        elif not self.catalog.explicitly_ignored(path):
            # Keep only sampled foreground intervals, never infer background use.
            self.unclassified.append((path, start, end, seconds))

    def _credit(self, game, start, end, seconds):
        for day, amount in day_slices(start, end, seconds):
            self.pending[(day, game.id)] += amount
            totals = self.totals(day)
            totals[game.id] = totals.get(game.id, 0) + amount

    def replay(self, now):
        remaining = deque()
        resolved = {}
        for path, start, end, seconds in self.unclassified:
            if now.timestamp() - end.timestamp() > self.PENDING_SECONDS:
                continue
            if path not in resolved:
                resolved[path] = self.catalog.resolve(path)
            game = resolved[path]
            if game:
                self._credit(game, start, end, seconds)
            else:
                remaining.append((path, start, end, seconds))
        self.unclassified = remaining

    def reconcile(self, games, scope):
        self.flush()
        aliases = self.store.reconcile(games, scope)
        self.catalog.apply(games, scope)
        for old_id in aliases:
            self.catalog.games.pop(old_id, None)
            if old_id in self.catalog.settings.game_overlays:
                value=self.catalog.settings.game_overlays.pop(old_id)
                self.catalog.settings.game_overlays.setdefault(aliases[old_id],value)
        self.catalog.overrides = self.store.overrides()
        self.catalog.rules = self.store.rules()
        self.cache.clear()
        if self.previous:
            self.replay(self.previous.wall)

    def evaluate(self, now):
        day = now.date().isoformat()
        total = sum(self.totals(day).values())
        settings = day_settings(self.catalog.settings,day)
        delivered = self.store.alert_keys(day) | {key for d, key in self.queued if d == day}
        warning = f"warning:{settings.warning_seconds:g}"
        limit = f"limit:{settings.limit_seconds:g}"
        session = f"session:{settings.limit_seconds:g}:" + self.identity
        if total >= settings.limit_seconds:
            if limit not in delivered:
                keys = (limit, warning, session) if self.identity else (limit, warning)
                text=notification_text(settings,'limit',day=day)
                self._queue(Alert(day, keys, "limit", text, tr("OK, I’ll stop", settings.language)))
            elif self.identity and session not in delivered:
                self._queue(Alert(day, (session,), "session",
                                  notification_text(settings,'session',day=day), tr("OK, I’ll stop", settings.language)))
        elif total >= settings.warning_seconds and warning not in delivered:
            remaining = math.ceil(remaining_budget(self.catalog.settings,now,total).remaining / 60)
            self._queue(Alert(day, (warning,), "warning", notification_text(settings,'warning',remaining,day=day), tr("OK", settings.language)))

    def _queue(self, alert):
        self.alerts.append(alert)
        self.queued.update((alert.day, key) for key in alert.keys)

    def delivered(self, alert):
        # Persist time before the alert marker, so a crash cannot lose a threshold.
        self.flush()
        self.store.mark_alert(alert.day, alert.keys)
        self.queued.difference_update((alert.day, key) for key in alert.keys)

    def flush(self):
        if self.pending:
            self.store.upsert(self.catalog.games.values())
            self.store.add_usage(self.pending)
            self.pending.clear()

    def close(self):
        self.flush()
