"""Local foreground activity and Pomodoro state, independent of game budgets/sync."""
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date,datetime
import ipaddress
import json
import math
import ntpath
import re
from urllib.parse import urlsplit

from .tracker import day_slices
from .activity_identity import is_idle_app
from .quota import period_day

BROWSERS = {'brave.exe': 'brave', 'chrome.exe': 'chrome', 'msedge.exe': 'edge',
            'firefox.exe': 'firefox', 'vivaldi.exe': 'vivaldi', 'opera.exe': 'opera'}
BROWSER_IDLE = '__brave_newtab_idle__'
SHELLS = {'explorer.exe', 'shellexperiencehost.exe', 'startmenuexperiencehost.exe',
          'searchhost.exe', 'lockapp.exe', 'applicationframehost.exe'}


def app_key(path):
    return ntpath.normcase(ntpath.normpath(path)) if path else ''


def domain(value):
    """Only public HTTP(S) hostnames. Never retain URL paths, queries or titles."""
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Enter a website domain, for example youtube.com.')
    raw = value.strip().lower()
    if raw.startswith('*.'): raw = raw[2:]
    parsed = urlsplit(raw if '://' in raw else 'https://' + raw)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        raise ValueError('Enter a website domain, for example youtube.com.')
    host = (parsed.hostname or '').rstrip('.')
    try: host = host.encode('idna').decode('ascii')
    except UnicodeError: host = ''
    try:
        ipaddress.ip_address(host)
        host = ''  # Do not collect local network addresses or numeric hosts.
    except ValueError: pass
    if (len(host) > 253 or '.' not in host or host.endswith(('.local', '.localhost', '.internal', '.test', '.invalid'))
            or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part) for part in host.split('.'))):
        raise ValueError('Enter a website domain, for example youtube.com.')
    return host


def matches(host, rule):
    return host == rule or host.endswith('.' + rule)


@dataclass
class FocusSettings:
    tracking: bool = True
    work: int = 25
    short_break: int = 5
    long_break: int = 15
    rounds: int = 4
    block_apps: list = field(default_factory=list)
    block_sites: list = field(default_factory=list)
    excluded_apps: list = field(default_factory=list)

    def validate(self):
        if type(self.tracking) is not bool:
            raise ValueError('Invalid focus settings.')
        for key, maximum in (('work', 240), ('short_break', 60), ('long_break', 120), ('rounds', 12)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('Invalid focus settings.')
        for key in ('block_apps', 'block_sites', 'excluded_apps'):
            items = getattr(self, key)
            if not isinstance(items, list) or len(items) > 200:
                raise ValueError('Use at most 200 entries in each focus list.')
            normalized = []
            for value in items:
                if not isinstance(value, str) or not value.strip() or len(value) > 2048:
                    raise ValueError('Invalid focus settings.')
                if key.endswith('sites'):
                    value = domain(value)
                else:
                    value = app_key(value.strip())
                    if not ntpath.isabs(value) or not value.endswith('.exe'):
                        raise ValueError('Choose an application executable (.exe).')
                if value not in normalized: normalized.append(value)
            setattr(self, key, normalized)
        return self

    def app_blocked(self, path):
        key = app_key(path)
        if not key or ntpath.basename(key) in SHELLS: return False
        return key in self.block_apps

    def site_blocked(self, host):
        return any(matches(host, item) for item in self.block_sites)

    def app_excluded(self, path):
        return app_key(path) in self.excluded_apps


class Focus:
    """Single GUI-thread owner. Buffer writes; browser bridge owns no database handle."""
    def __init__(self, store):
        self.store = store
        store.db.executescript('''
            CREATE TABLE IF NOT EXISTS activity_items (
                kind TEXT NOT NULL, key TEXT NOT NULL, name TEXT NOT NULL,
                PRIMARY KEY(kind,key));
            CREATE TABLE IF NOT EXISTS activity_usage (
                day TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, seconds REAL NOT NULL,
                PRIMARY KEY(day,kind,key));
            CREATE TABLE IF NOT EXISTS focus_completions (
                day TEXT PRIMARY KEY, rounds INTEGER NOT NULL);
        ''')
        config = self._load('focus_config', {})
        # Retire allowlists without changing existing blacklist entries or timer preferences.
        for key in ('mode', 'allow_apps', 'allow_sites'): config.pop(key, None)
        self.settings = FocusSettings(**config).validate()
        self.day_start_minute=store.settings().budget_reset_minute
        earliest = store.db.execute('SELECT MIN(day) FROM activity_usage').fetchone()[0]
        self.started_on = self._load('activity_started_on', earliest or self.day(datetime.now().astimezone()).isoformat())
        self._started_dirty=False
        with store.db: self._save('activity_started_on', self.started_on)
        state = self._load('focus_timer', {})
        self.phase = state.get('phase', 'focus')
        if self.phase not in ('focus', 'short_break', 'long_break'): self.phase = 'focus'
        self.remaining = float(state.get('remaining', self.settings.work * 60))
        if not math.isfinite(self.remaining) or not 0 < self.remaining <= 14400:
            self.remaining = self.settings.work * 60
        self.round = max(0, min(10000, int(state.get('round', 0))))
        self.running = False  # Explicitly resume after restart, never surprise the user with restrictions.
        self.previous = None
        self.last_awake = None
        self.last_flush = None
        self.pending = defaultdict(float)
        self.items = {}
        self.revision = 0
        self.notice = ''
        self._dirty = False

    def _load(self, key, default):
        row = self.store.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _save(self, key, value):
        self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

    def day(self,wall): return period_day(wall,(self.day_start_minute,)*7)

    def configure_day_start(self,minute):
        if minute==self.day_start_minute: return
        self.flush(); self.previous=None; self.day_start_minute=minute

    @property
    def restricting(self):
        return self.running and self.phase == 'focus'

    def configure(self, settings):
        settings.validate()
        previous_settings=self.settings
        self.flush()
        self.previous = None
        old_duration = getattr(self.settings, 'work' if self.phase == 'focus' else self.phase) * 60
        if not self.running and self.remaining == old_duration:
            self.remaining = getattr(settings, 'work' if self.phase == 'focus' else self.phase) * 60
        self.settings = settings
        with self.store.db: self._save('focus_config', asdict(settings))
        if previous_settings!=settings: self.store.observe_preferences()
        self.revision += 1
        self._dirty = True
        self.flush()

    def start(self, awake):
        self.running = True
        self.last_awake = awake
        self.notice = ''
        self._dirty = True
        self.flush()

    def pause(self, awake):
        self.advance(awake)
        self.running = False
        self._dirty = True
        self.flush()

    def stop(self):
        self.running = False
        self.phase = 'focus'
        self.remaining = self.settings.work * 60
        self.round = 0
        self.notice = ''
        self._dirty = True
        self.flush()

    def advance(self, awake, wall=None):
        delta = 0 if self.last_awake is None else max(0, awake - self.last_awake)
        self.last_awake = awake
        if not self.running: return
        self.remaining = max(0, self.remaining - delta)
        self._dirty = True
        if self.remaining > 0: return
        if self.phase == 'focus':
            self.round += 1
            day = str(self.day(wall or datetime.now().astimezone()))
            with self.store.db:
                self.store.db.execute('INSERT INTO focus_completions VALUES (?,1) '
                                      'ON CONFLICT(day) DO UPDATE SET rounds=rounds+1', (day,))
            self.phase = 'long_break' if self.round % self.settings.rounds == 0 else 'short_break'
            self.remaining = getattr(self.settings, self.phase) * 60
            self.notice = 'Focus complete. Time for a break.'
        else:
            self.phase = 'focus'
            self.remaining = self.settings.work * 60
            self.running = False
            self.notice = 'Break complete. Start the next focus session when ready.'
        self.flush()

    def tick(self, sample, website=''):
        self.advance(sample.awake, sample.wall)
        previous = self.previous
        self.previous = (sample, website)
        if previous and self.settings.tracking:
            prev, prev_site = previous
            delta = sample.awake - prev.awake
            wall = sample.wall.timestamp() - prev.wall.timestamp()
            if (0 < delta <= 3 and wall > 0 and abs(wall - delta) <= 1.5 and prev.interactive
                    and sample.interactive and prev.path and prev.identity):
                key = app_key(prev.path)
                if (not is_idle_app(key) and not self.settings.app_excluded(key)
                        and not (prev_site==BROWSER_IDLE and ntpath.basename(key) in BROWSERS)):
                    self._credit('app', key, ntpath.basename(prev.path), prev.wall, sample.wall, delta)
                    # Website totals are a breakdown of browser time, not additional screen time.
                    if prev_site and ntpath.basename(key) in BROWSERS:
                        self._credit('site', prev_site, prev_site, prev.wall, sample.wall, delta)
        if self.last_flush is None: self.last_flush = sample.awake
        if sample.awake - self.last_flush >= 10:
            self.flush()
            self.last_flush = sample.awake

    def _credit(self, kind, key, name, start, end, seconds):
        self.items[(kind, key)] = name
        for day, amount in day_slices(start, end, seconds,self.day_start_minute):
            self.pending[(day, kind, key)] += amount
            if day<self.started_on: self.started_on=day; self._started_dirty=True
        self.revision += 1

    def flush(self):
        if not self.pending and not self._dirty: return
        with self.store.db:
            self.store.db.executemany('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)',
                                     [(kind, key, name) for (kind, key), name in self.items.items()])
            self.store.db.executemany('INSERT INTO activity_usage VALUES (?,?,?,?) ON CONFLICT(day,kind,key) '
                                     'DO UPDATE SET seconds=seconds+excluded.seconds',
                                     [(*key, value) for key, value in self.pending.items()])
            self._save('focus_timer', {'phase': self.phase, 'remaining': self.remaining, 'round': self.round})
            if self._started_dirty: self._save('activity_started_on',self.started_on)
        self._started_dirty=False
        self.pending.clear()
        self.items.clear()
        self._dirty = False

    def usage(self, day):
        rows = {(kind, key): [name, seconds] for kind, key, name, seconds in self.store.db.execute(
            'SELECT u.kind,u.key,i.name,u.seconds FROM activity_usage u '
            'JOIN activity_items i ON i.kind=u.kind AND i.key=u.key WHERE u.day=?', (str(day),))
                if kind!='app' or not is_idle_app(key)}
        for (pending_day, kind, key), seconds in self.pending.items():
            if pending_day != str(day) or kind=='app' and is_idle_app(key): continue
            row = rows.setdefault((kind, key), [self.items.get((kind, key), key), 0])
            row[1] += seconds
        return [(kind, key, name, seconds) for (kind, key), (name, seconds) in rows.items()]

    def policy(self):
        # Keep the wire shape compatible with already paired 2.29 browser extensions.
        return {'active': self.restricting, 'tracking': self.settings.tracking, 'mode': 'blocklist',
                'allow': [], 'block': self.settings.block_sites,
                'remaining': math.ceil(self.remaining) if self.restricting else 0}

    def history(self, start, end, category):
        """Local statistics. All splits browser time into sites plus an unclassified remainder."""
        from .model import within, norm, blocked
        games = self.store.games()
        games_root = self.store.settings().games_root
        game_ids = {game.id for game in games}
        rules = self.store.rules()
        def is_game(path):
            if blocked(path): return False
            if rules.get(norm(path)) in game_ids: return True
            if ntpath.basename(path) in ('java.exe', 'javaw.exe') and any(game.source == 'Minecraft' for game in games):
                from .minecraft import is_runtime
                if is_runtime(path): return True
            return any(game.source != 'Kézi' and within(path, game.root) and
                       not (game.source == 'Games' and norm(game.root) == norm(games_root)
                            and norm(ntpath.dirname(path)) != norm(game.root)) for game in games)
        # Resolve each executable once per visible report, never during hidden ticks.
        rows = list(self.store.db.execute(
            'SELECT u.day,u.kind,u.key,i.name,u.seconds FROM activity_usage u '
            'JOIN activity_items i ON i.kind=u.kind AND i.key=u.key WHERE u.day>=? AND u.day<=?', (str(start), str(end))))
        rows=[row for row in rows if row[1]!='app' or not is_idle_app(row[2])]
        game_paths = {key for key in {row[2] for row in rows if row[1]=='app'} if is_game(key)}
        apps = [(day, 'activity:app:' + key, name, 'Application', seconds)
                for day, kind, key, name, seconds in rows if kind == 'app' and key not in game_paths
                and not self.settings.app_excluded(key)]
        sites = [(day, 'activity:site:' + key, name, 'Website', seconds)
                 for day, kind, key, name, seconds in rows if kind == 'site']
        if category == 'apps': return apps
        if category == 'websites': return sites
        if category != 'all': return []
        browser_totals = defaultdict(float)
        output = []
        for row in apps:
            if ntpath.basename(row[1][len('activity:app:'):]) in BROWSERS: browser_totals[row[0]] += row[4]
            else: output.append(row)
        site_totals = defaultdict(float)
        for row in sites: site_totals[row[0]] += row[4]
        for day, key, name, source, seconds in sites:
            scale = min(1, browser_totals[day] / site_totals[day]) if site_totals[day] else 0
            if scale: output.append((day, key, name, source, seconds * scale))
        for day, seconds in browser_totals.items():
            remainder = max(0, seconds - site_totals[day])
            if remainder: output.append((day, 'activity:browser:other', 'Other browser time', 'Browser', remainder))
        return output

    def close(self):
        self.flush()
