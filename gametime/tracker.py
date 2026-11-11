from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import math
from .model import blocked
from .i18n import tr
from .notification_text import notification_text
from .schedule import day_settings
from .budget import remaining_budget
from .quota import period_day, period_slices, reset_clock, budget_day
from .restriction_policy import legacy_warning_active


@dataclass(frozen=True)
class Sample:
    wall: datetime
    awake: float
    path: str = ""
    identity: str = ""  # PID + process creation FILETIME, never PID alone
    interactive: bool = True
    idle_seconds: float = 0


@dataclass(frozen=True)
class Alert:
    day: str
    keys: tuple
    kind: str
    text: str
    button: str
    game_id: str = ""
    title: str = ""
    icon: str = ""
    sound: bool = True
    action: dict | None = None
    timeout: int | None = None


def day_slices(start, end, duration, minute=0):
    """Split a verified interval at the chosen local boundary, conserving time."""
    yield from period_slices(start,end,duration,(minute,)*7)


class Tracker:
    FLUSH_SECONDS = 10
    PENDING_SECONDS = 120

    def __init__(self, store, catalog):
        self.store, self.catalog = store, catalog
        from .activity_sessions import Sessions
        self.sessions=Sessions(store)
        self.previous = None
        self.unclassified = deque()
        self.pending = defaultdict(float)
        self.cache = {}
        self.budget_cache = {}
        self.budget_pending = defaultdict(float)
        self.remote_budget_cache = None
        self.custom_remote_cache = {}
        from .budget_periods import BudgetPeriods
        self.periods = BudgetPeriods(store)
        for key in tuple(self.periods.clocks):
            if key.startswith('quota:') and key[6:] not in catalog.settings.budget_reset_overrides:
                self.periods.forget_clock(key)
        self.period_pruned_day = None
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
        today=now.date().isoformat()
        if self.catalog.settings.budget_reset_overrides and today!=self.period_pruned_day:
            self.periods.prune(now); self.period_pruned_day=today
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
            if suffix.startswith(('warning:','limit:','session:')) and 'shared-games' in self.catalog.settings.budget_reset_overrides: continue
            if suffix.startswith('game-limit:'):
                rest=suffix[len('game-limit:'):]
                try:
                    size_text,rest=rest.split(':',1); gid=rest[:int(size_text)]
                except (ValueError,TypeError): gid=''
                if 'game:'+gid in self.catalog.settings.budget_reset_overrides: continue
            if suffix.startswith(('warning:', 'limit:', 'session:', 'game-limit:')): keys.append(prefix + suffix)
        self.store.reset_budget_clock(clock, revision, day, totals, keys)
        for budget in self.catalog.settings.budget_reset_overrides:
            if budget!='shared-games' and not budget.startswith('game:'): continue
            custom_day=budget_day(self.catalog.settings,budget,now).isoformat()
            copied=[]
            for key in self.store.alert_keys(custom_day):
                if not key.startswith(old_prefix): continue
                suffix=key[len(old_prefix):]
                if budget=='shared-games' and suffix.startswith(('warning:','limit:','session:')):
                    copied.append(prefix+suffix)
                elif budget.startswith('game:'):
                    gid=budget[5:]
                    if suffix.startswith(f'game-limit:{len(gid)}:{gid}:'): copied.append(prefix+suffix)
            if copied: self.store.mark_alert(custom_day,copied)
        self.budget_clock = clock; self.budget_revision = revision
        self.budget_cache = {day: totals}
        self.alerts.clear(); self.queued.clear()

    def _budget_totals(self, day):
        day = str(day)
        if day not in self.budget_cache:
            self.budget_cache[day] = self.store.budget_totals(day)
        return self.budget_cache[day]

    def quota_totals(self, wall, key='shared-games'):
        self.configure_budget(wall)
        if key in self.catalog.settings.budget_devices:
            from .device_sharing import remote_seconds
            settings=self.catalog.settings;minute=settings.budget_reset_overrides.get(key)
            day=period_day(wall,reset_clock(settings))
            source=self.totals(day) if self.budget_clock is None else self._budget_totals(day)
            if minute is not None:source=self.periods.totals('quota:'+key,minute,wall,lambda:dict(source),marker_key=key,previous_day=str(day))
            result=({key[5:]:source.get(key[5:],0)} if key.startswith('game:') else dict(source))
            remote_key=key[5:] if key.startswith('game:') else 'remote:shared-rule'
            result[remote_key]=result.get(remote_key,0)+remote_seconds(self.store,settings,key,wall)
            return result
        minute=self.catalog.settings.budget_reset_overrides.get(key)
        if minute is not None:
            day=period_day(wall,reset_clock(self.catalog.settings))
            def seed():
                source=self.totals(day) if self.budget_clock is None else self._budget_totals(day)
                if key.startswith('games-') and self.catalog.settings.budget_reset_overrides.get('shared-games')==minute:
                    return dict(self.periods.totals('quota:shared-games',minute,wall,lambda:dict(source),marker_key='shared-games',previous_day=day.isoformat()))
                return {key[5:]:source.get(key[5:],0)} if key.startswith('game:') else dict(source)
            local=self.periods.totals('quota:'+key,minute,wall,seed,marker_key=key,previous_day=day.isoformat())
            remote=self.custom_remote_totals(key,minute,wall)
            result=dict(local)
            for gid,seconds in remote.items(): result[gid]=result.get(gid,0)+seconds
            return result
        return self.quota_day_totals(period_day(wall, reset_clock(self.catalog.settings)))

    def game_quota_total(self, wall, gid):
        return self.quota_totals(wall,'game:'+gid).get(gid,0)

    def custom_remote_totals(self,key,minute,wall):
        # Custom-period remote snapshots are installed by StatisticsData. Old
        # devices have only daily aggregates, so count both overlapping daily
        # records until that device has been updated rather than grant time.
        settings=self.catalog.settings
        if not settings.statistics_sync_enabled or not settings.statistics_sync_group: return {}
        from .statistics_sync import game_key,local_group
        from .quota import reset_at
        group=local_group(settings.statistics_sync_group)
        day=period_day(wall,(minute,)*7)
        cache_key=('custom',group,key,minute,str(day),getattr(self.store,'statistics_revision',0))
        cached=self.custom_remote_cache.get(key)
        if cached is not None and cached[0]==cache_key: return cached[1]
        tables={row[0] for row in self.store.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('statistics_devices','statistics_remote','statistics_remote_budget_clock','statistics_remote_budget_usage')")}
        if not {'statistics_devices','statistics_remote'}<=tables: return {}
        mapping={}
        for game in self.store.games(): mapping[game_key(game.id,game.name,game.source)]=game.id
        portable='game:'+next((p for p,g in mapping.items() if g==key[5:]),'') if key.startswith('game:') else 'shared-games'
        beginning=reset_at(day,minute,wall)
        first=period_day(beginning,reset_clock(settings)).isoformat()
        last=period_day(wall,reset_clock(settings)).isoformat()
        remote=defaultdict(float)
        devices=[row[0] for row in self.store.db.execute('SELECT device_id FROM statistics_devices WHERE group_id=?',(group,))]
        for device in devices:
            covered=False
            if {'statistics_remote_budget_clock','statistics_remote_budget_usage'}<=tables:
                covered=bool(self.store.db.execute('SELECT 1 FROM statistics_remote_budget_clock WHERE group_id=? AND device_id=? AND budget=? AND minute=?',(group,device,portable,minute)).fetchone())
            if covered:
                rows=self.store.db.execute('SELECT game_id,seconds FROM statistics_remote_budget_usage WHERE group_id=? AND device_id=? AND budget=? AND day=?',(group,device,portable,str(day)))
            else:
                rows=self.store.db.execute('SELECT game_id,SUM(seconds) FROM statistics_remote WHERE group_id=? AND device_id=? AND day>=? AND day<=? GROUP BY game_id',(group,device,first,last))
            for gid,seconds in rows:
                local=mapping.get(gid,'remote:'+gid)
                if not key.startswith('game:') or local==key[5:]: remote[local]+=seconds
        self.custom_remote_cache[key]=(cache_key,dict(remote))
        return self.custom_remote_cache[key][1]

    def quota_day_totals(self, day):
        local = self.totals(day) if self.budget_clock is None else self._budget_totals(day)
        settings = self.catalog.settings
        if not settings.statistics_sync_enabled or not settings.statistics_sync_group:
            return local
        from .statistics_sync import game_key, local_group
        group = local_group(settings.statistics_sync_group)
        key = (group, str(day), getattr(self.store, 'statistics_revision', 0))
        if self.remote_budget_cache is None or self.remote_budget_cache[0] != key:
            remote = defaultdict(float)
            exists = self.store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='statistics_remote'").fetchone()
            if exists:
                mapping = {}
                for game in self.store.games():
                    portable = game_key(game.id, game.name, game.source)
                    if portable not in mapping or game.id in local or game.id in settings.game_limits:
                        mapping[portable] = game.id
                for gid, seconds in self.store.db.execute(
                        'SELECT game_id,SUM(seconds) FROM statistics_remote WHERE group_id=? AND day=? GROUP BY game_id',
                        (group, str(day))):
                    remote[mapping.get(gid, 'remote:' + gid)] += seconds
            self.remote_budget_cache = (key, dict(remote))
        totals = dict(local)
        for gid, seconds in self.remote_budget_cache[1].items():
            totals[gid] = totals.get(gid, 0) + seconds
        return totals

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
        self.sessions.credit('game',game.id,start.timestamp(),end.timestamp(),period_day(start,reset_clock(self.catalog.settings)))
        self.configure_budget(start)
        overrides=self.catalog.settings.budget_reset_overrides
        extra=[r['id'] for r in self.catalog.settings.wellbeing_rules if r['id'].startswith('games-') and r['members']==[{'kind':'category','value':'games'}]]
        for key in (*extra,'shared-games','game:'+game.id):
            if key not in overrides: continue
            minute=overrides[key]
            day=period_day(start,reset_clock(self.catalog.settings))
            def seed():
                source=self.totals(day) if self.budget_clock is None else self._budget_totals(day)
                if key.startswith('games-') and overrides.get('shared-games')==minute:
                    return dict(self.periods.totals('quota:shared-games',minute,start,lambda:dict(source),marker_key='shared-games',previous_day=day.isoformat()))
                return {game.id:source.get(game.id,0)} if key.startswith('game:') else dict(source)
            self.periods.totals('quota:'+key,minute,start,seed,marker_key=key,previous_day=day.isoformat())
            self.periods.credit('quota:'+key,minute,game.id,start,end,seconds,seed)
        for day, amount in day_slices(start, end, seconds,self.catalog.settings.budget_reset_minute):
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
        before=getattr(self,'before_reconcile',None)
        if before: before()
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
            resets=self.catalog.settings.budget_reset_overrides
            if 'game:'+old_id in resets:
                resets.setdefault('game:'+aliases[old_id],resets.pop('game:'+old_id))
        self.catalog.overrides = self.store.overrides()
        self.catalog.rules = self.store.rules()
        if aliases:
            from .wellbeing import remap_rules
            self.catalog.settings.wellbeing_rules=remap_rules(self.catalog.settings.wellbeing_rules,aliases)
            callback=getattr(self,'on_aliases',None)
            if callback: callback(aliases)
        self.cache.clear()
        self.budget_cache.clear()
        self.remote_budget_cache = None
        self.custom_remote_cache.clear()
        self.periods.cache.clear()
        self.periods.clocks=dict(self.store.db.execute('SELECT budget,minute FROM independent_budget_clock'))
        if self.previous:
            self.replay(self.previous.wall)

    def evaluate(self, now):
        totals = self.quota_totals(now)
        total = sum(totals.values())
        for alert in tuple(self.alerts):
            if not self.alert_current(alert, now):
                self.alerts.remove(alert)
                self.queued.difference_update((alert.day, key) for key in alert.keys)
        day = budget_day(self.catalog.settings,'shared-games',now).isoformat()
        settings = day_settings(self.catalog.settings,day)
        delivered = self.store.alert_keys(day) | {key for d, key in self.queued if d == day}
        prefix = f'budget:{self.budget_revision}:' if self.budget_clock is not None else ''
        warning = prefix + f"warning:{settings.warning_seconds:g}"
        limit = prefix + f"limit:{settings.limit_seconds:g}"
        session = prefix + f"session:{settings.limit_seconds:g}:" + self.identity
        from . import budget_access
        shared=settings.game_budget_enabled and budget_access.active(settings,'shared-games',now) and budget_access.usage_enabled(settings,'shared-games')
        if shared and settings.limit_seconds>0 and 'shared-games' not in settings.restriction_plans and total >= settings.limit_seconds:
            if limit not in delivered and 'limit' not in settings.removed_notifications:
                keys = (limit, warning, session) if self.identity else (limit, warning)
                text=notification_text(settings,'limit',day=day)
                self._queue(Alert(day, keys, "limit", text, tr("OK, I’ll stop", settings.language)))
            elif self.identity and session not in delivered and 'session' not in settings.removed_notifications:
                self._queue(Alert(day, (session,), "session",
                                  notification_text(settings,'session',day=day), tr("OK, I’ll stop", settings.language)))
        elif shared and settings.limit_seconds>0 and legacy_warning_active(settings.restriction_plans,'shared-games') and total >= settings.warning_seconds and warning not in delivered and 'warning' not in settings.removed_notifications:
            remaining = math.ceil(remaining_budget(self.catalog.settings,now,total).remaining / 60)
            self._queue(Alert(day, (warning,), "warning", notification_text(settings,'warning',remaining,day=day), tr("OK", settings.language)))
        game = self.active
        cap = self.catalog.settings.game_limits.get(game.id) if game and self.catalog.enabled(game) and 'game:'+game.id not in settings.restriction_plans else None
        game_day=budget_day(self.catalog.settings,'game:'+game.id,now).isoformat() if game else day
        game_delivered=self.store.alert_keys(game_day) | {key for d,key in self.queued if d==game_day}
        if cap is not None and cap>0 and budget_access.active(settings,'game:'+game.id,now) and budget_access.usage_enabled(settings,'game:'+game.id) and self.game_quota_total(now,game.id) >= cap and (not shared or total < settings.limit_seconds):
            key = prefix + f'game-limit:{len(game.id)}:{game.id}:{cap:g}:{self.identity}'
            if key not in game_delivered:
                self._queue(Alert(game_day, (key,), 'limit',
                    tr('{name}: the {minutes:g}-minute game limit has been reached. Time to finish playing.',
                       settings.language, name=game.name, minutes=cap/60),
                    tr('OK, I’ll stop', settings.language), game.id))

    def alert_current(self, alert, now):
        from . import budget_access
        key='game:'+alert.game_id if alert.game_id else 'shared-games'
        if not budget_access.active(self.catalog.settings,key,now) or not budget_access.usage_enabled(self.catalog.settings,key): return False
        if not alert.game_id:
            if alert.kind in self.catalog.settings.removed_notifications: return False
            day=budget_day(self.catalog.settings,'shared-games',now).isoformat()
            return alert.day==day and self.catalog.settings.game_budget_enabled and day_settings(self.catalog.settings,day).limit_seconds>0 and (legacy_warning_active(self.catalog.settings.restriction_plans,'shared-games') if alert.kind=='warning' else 'shared-games' not in self.catalog.settings.restriction_plans)
        if alert.day!=budget_day(self.catalog.settings,'game:'+alert.game_id,now).isoformat(): return False
        if 'game:'+alert.game_id in self.catalog.settings.restriction_plans: return False
        game = self.active
        cap = self.catalog.settings.game_limits.get(alert.game_id)
        return bool(game and game.id == alert.game_id and self.catalog.enabled(game)
                    and cap is not None and cap>0 and self.game_quota_total(now,game.id) >= cap
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
        if self.pending or self.budget_pending or self.periods.pending:
            self.store.upsert(self.catalog.games.values())
            self.store.add_usage(self.pending, self.budget_pending,self.periods.pending,self.sessions)
            self.sessions.clear()
            self.pending.clear()
            self.budget_pending.clear()
            self.periods.pending.clear()

    def close(self):
        self.flush()
