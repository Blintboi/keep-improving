from dataclasses import asdict
import json
import sqlite3
from .model import Game, Settings, norm


class Store:
    def __init__(self, path):
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
            PRAGMA user_version=1;
        """)

    def settings(self):
        row = self.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
        return Settings(**json.loads(row[0])) if row else Settings()

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
                    if prior.id != game.id and prior.id.startswith("pending:") and norm(prior.root) == norm(game.root):
                        self._merge(prior.id, game.id)
                        aliases[prior.id] = game.id
            self.upsert(games)
        return aliases

    def _merge(self, old_id, new_id):
        rows = list(self.db.execute("SELECT day,seconds FROM usage WHERE game_id=?", (old_id,)))
        self.db.executemany("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                            "DO UPDATE SET seconds=seconds+excluded.seconds",
                            [(day, new_id, seconds) for day, seconds in rows])
        self.db.execute("DELETE FROM usage WHERE game_id=?", (old_id,))
        self.db.execute("UPDATE OR IGNORE overrides SET game_id=? WHERE game_id=?", (new_id, old_id))
        self.db.execute("UPDATE rules SET game_id=? WHERE game_id=?", (new_id, old_id))
        self.db.execute("UPDATE games SET installed=0 WHERE id=?", (old_id,))

    def totals(self, day):
        return dict(self.db.execute("SELECT game_id,seconds FROM usage WHERE day=?", (str(day),)))

    def add_usage(self, entries):
        with self.db:
            self.db.executemany("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(day,game_id) "
                                "DO UPDATE SET seconds=seconds+excluded.seconds",
                                [(day, gid, seconds) for (day, gid), seconds in entries.items()])

    def overrides(self):
        return {key: bool(val) for key, val in self.db.execute("SELECT * FROM overrides")}

    def set_enabled(self, gid, enabled):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO overrides VALUES (?,?)", (gid, int(enabled)))

    def rules(self):
        return dict(self.db.execute("SELECT path,game_id FROM rules"))

    def set_rule(self, path, gid):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO rules VALUES (?,?)", (norm(path), gid))

    def delete_rule(self, path):
        with self.db:
            self.db.execute("DELETE FROM rules WHERE path=?", (norm(path),))

    def alert_keys(self, day):
        return {r[0] for r in self.db.execute("SELECT key FROM alerts WHERE day=?", (str(day),))}

    def mark_alert(self, day, keys):
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO alerts VALUES (?,?)", [(str(day), k) for k in keys])

    def close(self):
        self.db.close()
