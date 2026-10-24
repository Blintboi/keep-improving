from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
from .model import blocked
from .i18n import tr
from .notification_text import notification_text
from .schedule import day_settings
from .budget import remaining_budget
from .quota import period_day, period_slices, reset_clock


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
    game_id: str = ""


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
        self.budget_cache = {}
        self.budget_pending = defaultdict(float)
        budget_state = store.budget_clock()
        self.budget_clock = tuple(budget_state['minutes']) if budget_state else None
        self.budget_revision = budget_state['revision'] if budget_state else 0
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

    def configure_budget(self, now):
        clock = reset_clock(self.catalog.settings)
        if clock == (self.budget_clock or (0,) * 7):
            return
        self.flush()
        previous = self.budget_clock
        old_day = period_day(now, previous or (0,) * 7).isoformat()
        totals = dict(self.totals(old_day) if previous is None else self._budget_totals(old_day))
        day = period_day(now, clock).isoformat()
        old_prefix = f'budget:{self.budget_revision}:' if previous is not None else ''
        revision = self.budget_revision + 1
        prefix = f'budget:{revision}:'
        keys = []
        for key in self.store.alert_keys(old_day):
            if not key.startswith(old_prefix): continue
            suffix = key[len(old_prefix):]
            if suffix.startswith(('warning:', 'limit:', 'session:', 'game-limit:')): keys.append(prefix + suffix)
        self.store.reset_budget_clock(clock, revision, day, totals, keys)
        self.budget_clock = clock; self.budget_revision = revision
        self.budget_cache = {day: totals}
        self.alerts.clear(); self.queued.clear()

    def _budget_totals(self, day):
        day = str(day)
        if day not in self.budget_cache:
            self.budget_cache[day] = self.store.budget_totals(day)
        return self.budget_cache[day]

    def quota_totals(self, wall):
        self.configure_budget(wall)
        return self.quota_day_totals(period_day(wall, reset_clock(self.catalog.settings)))

    def quota_day_totals(self, day):
        return self.totals(day) if self.budget_clock is None else self._budget_totals(day)

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
        self.configure_budget(start)
        for day, amount in day_slices(start, end, seconds):
            self.pending[(day, game.id)] += amount
            totals = self.totals(day)
            totals[game.id] = totals.get(game.id, 0) + amount
        if self.budget_clock is not None:
            for day, amount in period_slices(start, end, seconds, self.budget_clock):
                self.budget_pending[(day, game.id)] += amount
                totals = self._budget_totals(day)
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
            limits=self.catalog.settings.game_limits
            if old_id in limits:
                value=limits.pop(old_id); limits[aliases[old_id]]=min(value,limits.get(aliases[old_id],value))
        self.catalog.overrides = self.store.overrides()
        self.catalog.rules = self.store.rules()
        self.cache.clear()
        self.budget_cache.clear()
        if self.previous:
            self.replay(self.previous.wall)

    def evaluate(self, now):
        totals = self.quota_totals(now)
        total = sum(totals.values())
        for alert in tuple(self.alerts):
            if alert.game_id and not self.alert_current(alert, now):
                self.alerts.remove(alert)
                self.queued.difference_update((alert.day, key) for key in alert.keys)
        day = period_day(now, reset_clock(self.catalog.settings)).isoformat()
        settings = day_settings(self.catalog.settings,day)
        delivered = self.store.alert_keys(day) | {key for d, key in self.queued if d == day}
        prefix = f'budget:{self.budget_revision}:' if self.budget_clock is not None else ''
        warning = prefix + f"warning:{settings.warning_seconds:g}"
        limit = prefix + f"limit:{settings.limit_seconds:g}"
        session = prefix + f"session:{settings.limit_seconds:g}:" + self.identity
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
        game = self.active
        cap = self.catalog.settings.game_limits.get(game.id) if game and self.catalog.enabled(game) else None
        if cap is not None and totals.get(game.id, 0) >= cap and total < settings.limit_seconds:
            key = prefix + f'game-limit:{len(game.id)}:{game.id}:{cap:g}:{self.identity}'
            if key not in delivered:
                self._queue(Alert(day, (key,), 'limit',
                    tr('{name}: the {minutes:g}-minute game limit has been reached. Time to finish playing.',
                       settings.language, name=game.name, minutes=cap/60),
                    tr('OK, I’ll stop', settings.language), game.id))

    def alert_current(self, alert, now):
        if not alert.game_id: return True
        game = self.active
        cap = self.catalog.settings.game_limits.get(alert.game_id)
        return bool(game and game.id == alert.game_id and self.catalog.enabled(game)
                    and cap is not None and self.quota_totals(now).get(game.id, 0) >= cap
                    and any(key.endswith(f':{cap:g}:{self.identity}') for key in alert.keys))

    def _queue(self, alert):
        self.alerts.append(alert)
        self.queued.update((alert.day, key) for key in alert.keys)

    def delivered(self, alert):
        # Persist time before the alert marker, so a crash cannot lose a threshold.
        self.flush()
        self.store.mark_alert(alert.day, alert.keys)
        self.queued.difference_update((alert.day, key) for key in alert.keys)

    def flush(self):
        if self.pending or self.budget_pending:
            self.store.upsert(self.catalog.games.values())
            self.store.add_usage(self.pending, self.budget_pending)
            self.pending.clear()
            self.budget_pending.clear()

    def close(self):
        self.flush()
