from dataclasses import asdict
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
from .model import Game, Settings, norm, LAUNCHER_SOURCES


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.db = sqlite3.connect(str(path), timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS games (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
              root TEXT NOT NULL, metadata TEXT NOT NULL, installed INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS usage (
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
        # Existing profiles had automatic chess exclusions. Preserve that choice;
        # a fresh installation counts chess just like any other game.
        config.setdefault("exclude_chess", True)
        return Settings(**config)

    def save_settings(self, settings):
        settings.validate()
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)",
                            (json.dumps(asdict(settings), ensure_ascii=False),))

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
                                 (prior.source == "Kézi" and game.source in LAUNCHER_SOURCES))):
                        self._merge(prior.id, game.id)
                        aliases[prior.id] = game.id
            self.upsert(games)
        return aliases

    def _merge(self, old_id, new_id):
        preferred = self.launch_executable(old_id)
        if preferred and not self.launch_executable(new_id):
            self.db.execute("INSERT INTO settings VALUES (?,?)", ('launch_exe:' + new_id, preferred))
        self.db.execute("DELETE FROM settings WHERE key=?", ('launch_exe:' + old_id,))
        rows = list(self.db.execute("SELECT day,seconds FROM usage WHERE game_id=?", (old_id,)))
        self.db.executemany("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                            "DO UPDATE SET seconds=seconds+excluded.seconds",
                            [(day, new_id, seconds) for day, seconds in rows])
        self.db.execute("DELETE FROM usage WHERE game_id=?", (old_id,))
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

    def add_usage(self, entries):
        with self.db:
            self.db.executemany("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                                "DO UPDATE SET seconds=seconds+excluded.seconds",
                                [(day, gid, seconds) for (day, gid), seconds in entries.items()])

    def overrides(self):
        return {key: bool(val) for key, val in self.db.execute("SELECT * FROM overrides")}

    def hidden_ids(self):
        return {gid for gid, hidden in self.db.execute("SELECT * FROM game_preferences") if hidden}

    def set_hidden(self, gid, hidden):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO game_preferences VALUES (?,?)", (gid, int(hidden)))

    def set_enabled(self, gid, enabled):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO overrides VALUES (?,?)", (gid, int(enabled)))

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
