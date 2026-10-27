from dataclasses import asdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
import logging
from .model import Game, Settings, norm, LAUNCHER_SOURCES
from .secrets import PREFIX,protect,unprotect
from .launcher_defs import PLATFORM_SOURCES

log=logging.getLogger(__name__)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA secure_delete=ON")
        self.credentials_unavailable=False; self._unavailable_credential=''; self._secret_migrated=False
        self._budget_pruned_day = None
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS games (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
              root TEXT NOT NULL, metadata TEXT NOT NULL, installed INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS usage (
              day TEXT NOT NULL, game_id TEXT NOT NULL, seconds REAL NOT NULL,
              PRIMARY KEY(day, game_id));
            CREATE TABLE IF NOT EXISTS budget_usage (
              day TEXT NOT NULL, game_id TEXT NOT NULL, seconds REAL NOT NULL,
              PRIMARY KEY(day, game_id));
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS overrides (game_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS rules (path TEXT PRIMARY KEY, game_id TEXT);
            CREATE TABLE IF NOT EXISTS alerts (day TEXT NOT NULL, key TEXT NOT NULL,
              PRIMARY KEY(day, key));
            CREATE TABLE IF NOT EXISTS game_preferences (game_id TEXT PRIMARY KEY, hidden INTEGER NOT NULL);
            PRAGMA user_version=2;
        """)
        self.tracking_started_on()

    def tracking_started_on(self):
        """Preserve the profile's first installation day, including legacy history."""
        row = self.db.execute("SELECT value FROM settings WHERE key='tracking_started_on'").fetchone()
        try:
            started = date.fromisoformat(row[0])
        except (TypeError, ValueError):
            try:
                info = self.path.stat()
                started = datetime.fromtimestamp(getattr(info, 'st_birthtime', info.st_ctime)).date()
            except OSError:
                started = date.today()
        # Restored/imported old history must retain its original recording period.
        earliest = self.db.execute("SELECT MIN(day) FROM usage WHERE seconds>0").fetchone()[0]
        if earliest:
            try:
                started = min(started, date.fromisoformat(earliest))
            except ValueError:
                pass
        value = started.isoformat()
        if not row or row[0] != value:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO settings VALUES ('tracking_started_on',?)", (value,))
        return value

    def settings(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
        if not row:
            return Settings()
        config = json.loads(row[0])
        # Accept old profiles without retaining the retired category-wide filter.
        config.pop("exclude_chess", None)
        # Folder identifiers were short routing labels, never internet secrets.
        # Keep the old group's cached history but require opting into a new code.
        if 'statistics_sync_folder' in config:
            config.pop('statistics_sync_folder')
            config['statistics_sync_enabled'] = False
        credential=config.get('statistics_sync_group','')
        if credential.startswith(PREFIX):
            try:
                config['statistics_sync_group']=unprotect(credential)
                self.credentials_unavailable=False; self._unavailable_credential=''
            except (OSError,ValueError):
                self.credentials_unavailable=True; self._unavailable_credential=credential
                config['statistics_sync_group']=''; config['statistics_sync_enabled']=False
        settings=Settings(**config)
        if credential and not credential.startswith(PREFIX):
            self.save_settings(settings); self._secret_migrated=True
        return settings

    def save_settings(self, settings):
        settings.validate()
        config=asdict(settings); credential=settings.statistics_sync_group
        if credential:
            current=self.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
            saved=json.loads(current[0]).get('statistics_sync_group','') if current else ''
            try: reuse=saved.startswith(PREFIX) and unprotect(saved)==credential
            except (OSError,ValueError): reuse=False
            config['statistics_sync_group']=saved if reuse else protect(credential)
            self.credentials_unavailable=False; self._unavailable_credential=''
        elif self._unavailable_credential:
            config['statistics_sync_group']=self._unavailable_credential
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)",
                            (json.dumps(config, ensure_ascii=False),))
        self.observe_preferences(settings)

    def observe_preferences(self,settings=None):
        """Only active linked profiles maintain a local preference revision."""
        settings=settings or self.settings()
        if not settings.statistics_sync_enabled or len(settings.statistics_sync_group)!=32: return
        try:
            from .preferences_sync import identity,observe
            observe(self,settings.statistics_sync_group,identity(self))
        except (OSError,ValueError,sqlite3.Error):
            log.warning('Could not record settings for synchronization',exc_info=True)

    def checkpoint_credentials(self):
        if self._secret_migrated:
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            self._secret_migrated=False

    def client_cache(self):
        from .clients import decode_client_cache
        row=self.db.execute("SELECT value FROM settings WHERE key='launcher_clients'").fetchone()
        if not row: return None
        try: return decode_client_cache(json.loads(row[0]))
        except (ValueError,TypeError,KeyError): return None

    def save_client_cache(self,clients):
        value=json.dumps({'version':1,'clients':[asdict(client) for client in clients]},ensure_ascii=False)
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('launcher_clients',?)",(value,))

    def account_session(self):
        from .statistics_auth import validate_session
        row=self.db.execute("SELECT value FROM settings WHERE key='statistics_auth_session'").fetchone()
        if not row: return None
        try: return validate_session(json.loads(unprotect(row[0])))
        except (OSError,ValueError,TypeError): return None

    def save_account_session(self,session):
        from .statistics_auth import validate_session
        with self.db:
            if session is None: self.db.execute("DELETE FROM settings WHERE key='statistics_auth_session'")
            else:
                value=protect(json.dumps(validate_session(session),separators=(',',':')))
                self.db.execute("INSERT OR REPLACE INTO settings VALUES ('statistics_auth_session',?)",(value,))

    def pending_connection(self,value=None,*,clear=False):
        if value is not None or clear:
            with self.db:
                if clear: self.db.execute("DELETE FROM settings WHERE key='statistics_pending_connection'")
                else:
                    if not isinstance(value,str) or len(value)!=32 or any(ch not in '0123456789abcdef' for ch in value): raise ValueError('Invalid connection code.')
                    self.db.execute("INSERT OR REPLACE INTO settings VALUES ('statistics_pending_connection',?)",(protect(value),))
        row=self.db.execute("SELECT value FROM settings WHERE key='statistics_pending_connection'").fetchone()
        if not row: return ''
        try: return unprotect(row[0])
        except (OSError,ValueError): return ''

    def games(self, installed_only=False):
        sql = "SELECT id,name,source,root,metadata,installed FROM games"
        if installed_only:
            sql += " WHERE installed=1"
        return [Game(*row) for row in self.db.execute(sql)]

    def upsert(self, games):
        with self.db:
            self.db.executemany("INSERT OR REPLACE INTO games VALUES (?,?,?,?,?,?)",
                                [(g.id, g.name, g.source, g.root, g.metadata, int(g.installed)) for g in games])

    def reconcile(self, games, scope):
        """Only a successfully enumerated source/scope may retire old entries."""
        old = self.games(True)
        aliases = {}
        with self.db:
            for prior in old:
                if scope(prior):
                    self.db.execute("UPDATE games SET installed=0 WHERE id=?", (prior.id,))
            for game in games:
                for prior in old:
                    if (prior.id != game.id and norm(prior.root) == norm(game.root)
                            and (prior.id.startswith("pending:") or
                                 (prior.source in {"Kézi", "Games"} and game.source in LAUNCHER_SOURCES) or
                                 (prior.source == game.source and game.source in PLATFORM_SOURCES))):
                        self._merge(prior.id, game.id)
                        aliases[prior.id] = game.id
            self.upsert(games)
        return aliases

    def _merge(self, old_id, new_id):
        row=self.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
        if row:
            config=json.loads(row[0]); changed=False
            for field in ('game_overlays', 'game_limits'):
                values=config.get(field,{})
                if old_id in values:
                    value=values.pop(old_id)
                    if field == 'game_limits': values[new_id]=min(value,values.get(new_id,value))
                    else: values.setdefault(new_id,value)
                    changed=True
            if changed: self.db.execute("UPDATE settings SET value=? WHERE key='config'",(json.dumps(config,ensure_ascii=False),))
        preferred = self.launch_executable(old_id)
        if preferred and not self.launch_executable(new_id):
            self.db.execute("INSERT INTO settings VALUES (?,?)", ('launch_exe:' + new_id, preferred))
        self.db.execute("DELETE FROM settings WHERE key=?", ('launch_exe:' + old_id,))
        for table in ('usage', 'budget_usage'):
            rows = list(self.db.execute(f"SELECT day,seconds FROM {table} WHERE game_id=?", (old_id,)))
            self.db.executemany(f"INSERT INTO {table} VALUES (?,?,?) ON CONFLICT(day,game_id) "
                                "DO UPDATE SET seconds=seconds+excluded.seconds",
                                [(day, new_id, seconds) for day, seconds in rows])
            self.db.execute(f"DELETE FROM {table} WHERE game_id=?", (old_id,))
        self.db.execute("UPDATE OR IGNORE overrides SET game_id=? WHERE game_id=?", (new_id, old_id))
        self.db.execute("UPDATE OR IGNORE game_preferences SET game_id=? WHERE game_id=?", (new_id, old_id))
        self.db.execute("UPDATE rules SET game_id=? WHERE game_id=?", (new_id, old_id))
        self.db.execute("UPDATE games SET installed=0 WHERE id=?", (old_id,))

    def totals(self, day):
        return dict(self.db.execute("SELECT game_id,seconds FROM usage WHERE day=?", (str(day),)))

    def history(self, start, end):
        """Recorded time includes hidden, excluded and removed games, even orphans."""
        return list(self.db.execute(
            "SELECT u.day,u.game_id,COALESCE(g.name,u.game_id),COALESCE(g.source,''),u.seconds "
            "FROM usage u LEFT JOIN games g ON g.id=u.game_id "
            "WHERE u.day>=? AND u.day<=? AND u.seconds>0 ORDER BY u.day,u.game_id",
            (str(start), str(end))))

    def launch_executable(self, game_id):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", ('launch_exe:' + game_id,)).fetchone()
        return row[0] if row else ""

    def set_launch_executable(self, game_id, path):
        # Callers also record the exact tracking rule; never interpret command text.
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", ('launch_exe:' + game_id, str(path)))

    def add_usage(self, entries, budget_entries=None):
        with self.db:
            self.db.executemany("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                                "DO UPDATE SET seconds=seconds+excluded.seconds",
                                [(day, gid, seconds) for (day, gid), seconds in entries.items()])
            if budget_entries:
                self.db.executemany("INSERT INTO budget_usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                                    "DO UPDATE SET seconds=seconds+excluded.seconds",
                                    [(day, gid, seconds) for (day, gid), seconds in budget_entries.items()])
                # Only current/recent quota periods are needed; history lives in usage.
                latest = max(day for day, gid in budget_entries)
                if self._budget_pruned_day != latest:
                    oldest = (date.fromisoformat(latest) - timedelta(days=2)).isoformat()
                    self.db.execute('DELETE FROM budget_usage WHERE day < ?', (oldest,))
                    self._budget_pruned_day = latest

    def budget_clock(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='budget_clock'").fetchone()
        return json.loads(row[0]) if row else None

    def budget_totals(self, day):
        return dict(self.db.execute('SELECT game_id,seconds FROM budget_usage WHERE day=?', (str(day),)))

    def reset_budget_clock(self, clock, revision, day, totals, alert_keys):
        with self.db:
            self.db.execute('DELETE FROM budget_usage')
            self.db.executemany('INSERT INTO budget_usage VALUES (?,?,?)', [(str(day), gid, seconds) for gid, seconds in totals.items()])
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('budget_clock',?)", (json.dumps({'minutes':clock,'revision':revision}),))
            self.db.executemany('INSERT OR IGNORE INTO alerts VALUES (?,?)', [(str(day), key) for key in alert_keys])

    def overrides(self):
        return {key: bool(val) for key, val in self.db.execute("SELECT * FROM overrides")}

    def hidden_ids(self):
        return {gid for gid, hidden in self.db.execute("SELECT * FROM game_preferences") if hidden}

    def set_hidden(self, gid, hidden):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO game_preferences VALUES (?,?)", (gid, int(hidden)))
        self.observe_preferences()

    def set_enabled(self, gid, enabled):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO overrides VALUES (?,?)", (gid, int(enabled)))
        self.observe_preferences()

    def rules(self):
        return dict(self.db.execute("SELECT path,game_id FROM rules"))

    def set_rule(self, path, gid):
        with self.db:
            old = self.db.execute("SELECT game_id FROM rules WHERE path=?", (norm(path),)).fetchone()
            if old and old[0] != gid:
                self._forget_launch_rule(path, old[0])
            self.db.execute("INSERT OR REPLACE INTO rules VALUES (?,?)", (norm(path), gid))

    def delete_rule(self, path):
        with self.db:
            old = self.db.execute("SELECT game_id FROM rules WHERE path=?", (norm(path),)).fetchone()
            if old:
                self._forget_launch_rule(path, old[0])
            self.db.execute("DELETE FROM rules WHERE path=?", (norm(path),))

    def _forget_launch_rule(self, path, gid):
        if gid and norm(self.launch_executable(gid)) == norm(path):
            self.db.execute("DELETE FROM settings WHERE key=?", ('launch_exe:' + gid,))

    def alert_keys(self, day):
        return {r[0] for r in self.db.execute("SELECT key FROM alerts WHERE day=?", (str(day),))}

    def mark_alert(self, day, keys):
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO alerts VALUES (?,?)", [(str(day), k) for k in keys])

    def close(self):
        self.db.close()
