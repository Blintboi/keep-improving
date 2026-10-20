"""Per-computer statistics snapshots and the separate local import cache.

SQLite stays local. Only each computer's own cumulative daily measurements are
published; imported snapshots are never republished or added to local budgets.
The retained folder worker also supplies the cancellable queue used by HTTPS.
"""
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Queue, Empty, Full
import re
import socket
import threading
import time
import unicodedata
import uuid

FORMAT = 'GameTimeMonitor.statistics.v1'
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 100_000
MAX_DEVICES = 100
ID = re.compile(r'[0-9a-f]{32}')
GROUP = re.compile(r'(?:[0-9a-f]{12}|[0-9a-f]{32})')


def group_code(value):
    return value.replace('-', '').replace(' ', '').lower()


def display_code(value):
    return '-'.join(value[i:i+4].upper() for i in range(0, len(value), 4))

def local_group(group):
    if not group or group.startswith('local-v1:'): return group
    return 'local-v1:'+hashlib.sha256(('GameTimeMonitor/local-group/v1\0'+group).encode()).hexdigest()


def computer_name():
    return socket.gethostname()[:80] or 'Computer'


def game_key(gid, name, source):
    if source in ('Steam', 'Epic', 'Ubisoft', 'Riot', 'Minecraft') and not gid.startswith('pending:'):
        return gid
    if name == gid:
        return 'unknown:' + hashlib.sha256(gid.encode()).hexdigest()
    title = ' '.join(unicodedata.normalize('NFKC', name).casefold().split())
    return 'title:' + hashlib.sha256((source+'\0'+title).encode()).hexdigest()


def validate_snapshot(value, group):
    try:
        if not isinstance(value, dict) or value['format'] != FORMAT or value['group'] != group:
            raise ValueError()
        if not GROUP.fullmatch(group) or not ID.fullmatch(value['device']):
            raise ValueError()
        if not isinstance(value['name'], str) or not 1 <= len(value['name']) <= 80:
            raise ValueError()
        revision = value['revision']
        if type(revision) is not int or not 0 < revision < 2**63:
            raise ValueError()
        if date.fromisoformat(value['started']).isoformat() != value['started']:
            raise ValueError()
        rows = value['rows']
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError()
        seen = set()
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != 5:
                raise ValueError()
            day, gid, name, source, seconds = row
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError()
            if not all(isinstance(text, str) and len(text) <= limit for text, limit in ((gid, 512), (name, 512), (source, 80))):
                raise ValueError()
            if not gid or not name or type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 172800:
                raise ValueError()
            key = (day, gid)
            if key in seen:
                raise ValueError()
            seen.add(key)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError('Invalid statistics file.') from None
    return value


class StatisticsData:
    """GUI-thread repository; remote data is separate from tracked usage."""
    def __init__(self, store):
        self.store = store
        store.db.executescript('''
            CREATE TABLE IF NOT EXISTS statistics_devices (
              group_id TEXT NOT NULL, device_id TEXT NOT NULL, name TEXT NOT NULL,
              revision INTEGER NOT NULL, started TEXT NOT NULL,
              PRIMARY KEY(group_id, device_id));
            CREATE TABLE IF NOT EXISTS statistics_remote (
              group_id TEXT NOT NULL, device_id TEXT NOT NULL, day TEXT NOT NULL,
              game_id TEXT NOT NULL, name TEXT NOT NULL, source TEXT NOT NULL,
              seconds REAL NOT NULL,
              PRIMARY KEY(group_id, device_id, day, game_id));
        ''')
        self._migrate_group_labels()
        store.checkpoint_credentials()

    def _migrate_group_labels(self):
        # Routing labels and snapshot-state keys must not duplicate the secret.
        groups={row[0] for row in self.store.db.execute('SELECT group_id FROM statistics_devices UNION SELECT group_id FROM statistics_remote') if GROUP.fullmatch(row[0])}
        migrated=bool(groups)
        with self.store.db:
            for group in groups:
                label=local_group(group)
                for identity,revision in self.store.db.execute('SELECT device_id,revision FROM statistics_devices WHERE group_id=?',(group,)).fetchall():
                    current=self.store.db.execute('SELECT revision FROM statistics_devices WHERE group_id=? AND device_id=?',(label,identity)).fetchone()
                    if current and current[0]>=revision:
                        self.store.db.execute('DELETE FROM statistics_remote WHERE group_id=? AND device_id=?',(group,identity))
                        self.store.db.execute('DELETE FROM statistics_devices WHERE group_id=? AND device_id=?',(group,identity))
                    else:
                        self.store.db.execute('DELETE FROM statistics_remote WHERE group_id=? AND device_id=?',(label,identity))
                        self.store.db.execute('DELETE FROM statistics_devices WHERE group_id=? AND device_id=?',(label,identity))
                        self.store.db.execute('UPDATE statistics_devices SET group_id=? WHERE group_id=? AND device_id=?',(label,group,identity))
                self.store.db.execute('UPDATE OR IGNORE statistics_remote SET group_id=? WHERE group_id=?',(label,group))
                self.store.db.execute('DELETE FROM statistics_remote WHERE group_id=?',(group,))
            for key,value in self.store.db.execute("SELECT key,value FROM settings WHERE key LIKE 'statistics_snapshot:%'").fetchall():
                group=key.partition(':')[2]
                if GROUP.fullmatch(group):
                    migrated=True
                    new_key='statistics_snapshot:'+local_group(group)
                    current=self.store.db.execute('SELECT value FROM settings WHERE key=?',(new_key,)).fetchone()
                    if not current or json.loads(current[0])['revision']<json.loads(value)['revision']:
                        self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(new_key,value))
                    self.store.db.execute('DELETE FROM settings WHERE key=?',(key,))
            if migrated: self.store._secret_migrated=True

    def device_id(self):
        row = self.store.db.execute("SELECT value FROM settings WHERE key='statistics_device_id'").fetchone()
        if row and ID.fullmatch(row[0]):
            return row[0]
        identity = uuid.uuid4().hex
        with self.store.db:
            self.store.db.execute("INSERT OR REPLACE INTO settings VALUES ('statistics_device_id',?)", (identity,))
        return identity

    def local_rows(self, start='0001-01-01', end='9999-12-31'):
        grouped = {}
        for day, gid, name, source, seconds in self.store.history(start, end):
            key = (day, game_key(gid, name, source))
            grouped.setdefault(key, [day, key[1], name, source, 0.0])[4] += seconds
        return sorted(grouped.values())

    def snapshot(self, group, name):
        value = dict(format=FORMAT, group=group, device=self.device_id(),
                     name=name or computer_name(), started=self.store.tracking_started_on(), rows=self.local_rows())
        digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        key = 'statistics_snapshot:' + local_group(group)
        row = self.store.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        old = json.loads(row[0]) if row else {}
        revision = old.get('revision', 0)
        if old.get('digest') != digest:
            revision = max(revision+1, time.time_ns())
            with self.store.db:
                self.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',
                                      (key, json.dumps(dict(digest=digest, revision=revision))))
        value['revision'] = revision
        return validate_snapshot(value, group)

    def ingest(self, value, group):
        validate_snapshot(value, group)
        if value['device'] == self.device_id():
            return False
        key = (local_group(group), value['device'])
        old = self.store.db.execute('SELECT revision FROM statistics_devices WHERE group_id=? AND device_id=?', key).fetchone()
        if old and old[0] >= value['revision']:
            return False
        with self.store.db:
            self.store.db.execute('INSERT OR REPLACE INTO statistics_devices VALUES (?,?,?,?,?)',
                                  (*key, value['name'], value['revision'], value['started']))
            self.store.db.execute('DELETE FROM statistics_remote WHERE group_id=? AND device_id=?', key)
            self.store.db.executemany('INSERT INTO statistics_remote VALUES (?,?,?,?,?,?,?)',
                                     [(*key, *row) for row in value['rows']])
        return True

    def devices(self, group):
        return list(self.store.db.execute('SELECT device_id,name,started FROM statistics_devices WHERE group_id=? ORDER BY name,device_id', (local_group(group),)))

    def revisions(self, group):
        return {identity: str(revision) for identity, revision in self.store.db.execute(
            'SELECT device_id,revision FROM statistics_devices WHERE group_id=?', (local_group(group),))}

    def history(self, start, end, group, scope='all'):
        rows = self.local_rows(start, end) if scope in ('all', 'local') else []
        if group and scope != 'local':
            sql = 'SELECT day,game_id,name,source,seconds FROM statistics_remote WHERE group_id=? AND day>=? AND day<=?'
            args = [local_group(group), str(start), str(end)]
            if scope != 'all':
                sql += ' AND device_id=?'; args.append(scope)
            rows += list(self.store.db.execute(sql, args))
        return rows

    def history_by_computer(self, start, end, group, scope='all', local_name=''):
        """Retain each row's origin for display without changing exports or budgets."""
        rows = [(*row, 'local', local_name or computer_name()) for row in self.local_rows(start, end)] if scope in ('all', 'local') else []
        if group and scope != 'local':
            sql = '''SELECT r.day,r.game_id,r.name,r.source,r.seconds,r.device_id,d.name
                     FROM statistics_remote r JOIN statistics_devices d
                     ON d.group_id=r.group_id AND d.device_id=r.device_id
                     WHERE r.group_id=? AND r.day>=? AND r.day<=?'''
            args = [local_group(group), str(start), str(end)]
            if scope != 'all':
                sql += ' AND r.device_id=?'; args.append(scope)
            rows += list(self.store.db.execute(sql, args))
        return rows

    def started_on(self, group, scope='all'):
        dates = [self.store.tracking_started_on()] if scope in ('all', 'local') else []
        dates += [started for identity, name, started in self.devices(group) if scope == 'all' or scope == identity]
        return min(dates) if dates else self.store.tracking_started_on()


class SyncWorker:
    """Bounded background file I/O; never touches SQLite, widgets or launchers."""
    failure_message = 'The shared folder is unavailable. Sync will retry automatically.'
    def failure_warning(self,error): return self.failure_message
    def __init__(self):
        self.jobs = Queue(maxsize=1)
        self.results = Queue()
        self.thread = None
        self.stopping = threading.Event()
        self.generation = 0

    def cancel(self):
        self.generation += 1
        while True:
            try: self.jobs.get_nowait()
            except Empty: break

    def request(self, folder, group, snapshot):
        if self.stopping.is_set(): return False
        token = (folder, group, self.generation)
        try:
            self.jobs.put_nowait((token, snapshot))
        except Full:
            return False
        if self.thread is None:
            self.thread = threading.Thread(target=self.run, name='statistics-sync', daemon=True)
            self.thread.start()
        return True

    def current(self, token):
        return not self.stopping.is_set() and token[2] == self.generation

    def exchange(self, token, snapshot):
        folder, group, generation = token
        validate_snapshot(snapshot, group)
        root = Path(folder)
        if not root.is_dir():
            raise OSError('The shared folder is unavailable. Sync will retry automatically.')
        directory = root / 'GameTimeMonitor-statistics' / group
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.resolve().is_relative_to(root.resolve()):
            raise OSError('The shared folder is unavailable. Sync will retry automatically.')
        if not self.current(token):
            return [], ''
        content = json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(content) > MAX_BYTES:
            raise ValueError('Statistics history is too large to synchronize.')
        destination = directory / (snapshot['device'] + '.json')
        # Publish a complete file atomically; never truncate a live snapshot.
        temporary = directory / ('.' + snapshot['device'] + '-' + uuid.uuid4().hex + '.tmp')
        try:
            if destination.is_symlink() or not destination.is_file() or destination.stat().st_size > MAX_BYTES or destination.read_bytes() != content:
                temporary.write_bytes(content)
                if self.current(token):
                    os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        values, warning, bytes_read = [], '', 0
        for index, path in enumerate(directory.iterdir()):
            if not self.current(token):
                break
            if index >= MAX_DEVICES * 4:
                warning = 'Some computer data could not be read. Sync will retry automatically.'; break
            if path.suffix != '.json' or not ID.fullmatch(path.stem) or path.stem == snapshot['device']:
                continue
            try:
                if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                    raise ValueError()
                with path.open('rb') as stream:
                    raw = stream.read(MAX_BYTES+1)
                if len(raw) > MAX_BYTES:
                    raise ValueError()
                bytes_read += len(raw)
                if bytes_read > 64 * 1024 * 1024:
                    warning = 'Some computer data could not be read. Sync will retry automatically.'; break
                value = validate_snapshot(json.loads(raw.decode('utf-8-sig')), group)
                if value['device'] != path.stem:
                    raise ValueError()
                values.append(value)
                if len(values) >= MAX_DEVICES:
                    break
            except (OSError, ValueError, UnicodeError, RecursionError):
                warning = 'Some computer data could not be read. Sync will retry automatically.'
        return values, warning

    def run(self):
        while not self.stopping.is_set():
            job=self.jobs.get()
            if job is None: break
            token,snapshot=job
            if not self.current(token):
                continue
            try:
                values, warning = self.exchange(token, snapshot)
            except (OSError, ValueError) as error:
                values, warning = [], self.failure_warning(error)
            if self.current(token):
                self.results.put((token, values, warning))

    def close(self):
        self.stopping.set()
        try: self.jobs.put_nowait(None)
        except Full: pass
        if self.thread:
            self.thread.join(timeout=.25)
