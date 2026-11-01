"""Persistent counters for budgets with independent local day boundaries.

The ordinary statistics ledger remains unchanged.  This ledger is populated
only for budgets which explicitly choose their own renewal time.
"""
from collections import defaultdict
from datetime import timedelta
import json
import re
from .quota import period_day, period_slices


class BudgetPeriods:
    def __init__(self, store):
        self.db = store.db
        self.db.execute('''CREATE TABLE IF NOT EXISTS independent_budget_clock (
            budget TEXT PRIMARY KEY, minute INTEGER NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS independent_budget_usage (
            budget TEXT NOT NULL, day TEXT NOT NULL, item TEXT NOT NULL, seconds REAL NOT NULL,
            PRIMARY KEY(budget,day,item))''')
        self.clocks = dict(self.db.execute('SELECT budget,minute FROM independent_budget_clock'))
        self.cache = {}
        self.pending = defaultdict(float)

    @staticmethod
    def day(wall, minute):
        return period_day(wall, (minute,) * 7).isoformat()

    def totals(self, key, minute, wall, seed, *, marker_key=None, previous_day=None):
        """Return a mutable in-memory counter for this budget and period.

        When a clock is first chosen or changed, carry current usage forward.
        Old daily totals cannot be accurately split at a new boundary; carrying
        them avoids granting extra usage in the first period.
        """
        old = self.clocks.get(key)
        day = self.day(wall, minute)
        if old != minute:
            self.flush()
            if old is None:
                values = dict(seed())
            else:
                values = dict(self._load(key, self.day(wall, old)))
            with self.db:
                self.db.execute('DELETE FROM independent_budget_usage WHERE budget=?', (key,))
                self.db.executemany('INSERT INTO independent_budget_usage VALUES (?,?,?,?)',
                                    [(key, day, item, seconds) for item, seconds in values.items() if seconds])
                self.db.execute('INSERT OR REPLACE INTO independent_budget_clock VALUES (?,?)', (key, minute))
                self._carry_markers(marker_key, self.day(wall,old) if old is not None else previous_day, day)
            self.clocks[key] = minute
            self.cache = {k:v for k,v in self.cache.items() if k[0] != key}
            self.cache[(key, day)] = values
        return self._load(key, day)

    def _carry_markers(self, key, old, new):
        if not key or not old or old==new: return
        exists=lambda table: self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
        if exists('restriction_state'):
            row=self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',(old,key)).fetchone()
            if row:
                previous=json.loads(row[0])
                target=self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',(new,key)).fetchone()
                if target:
                    from .restriction_policy import merge_breaks
                    merged=json.loads(target[0]); merged['used_extension'] |= previous['used_extension']
                    merge_breaks(merged,previous)
                    merged['delivered']=sorted(set(merged['delivered'])|set(previous['delivered']))
                    if previous.get('grant') and (not merged.get('grant') or previous['grant']['until']<merged['grant']['until']):
                        merged['grant']=previous['grant']
                    previous=merged
                self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',(new,key,json.dumps(previous)))
        if exists('alerts'):
            def matches(value):
                suffix=re.sub(r'^budget:\d+:','',value)
                if key=='shared-games': return suffix.startswith(('warning:','limit:','session:'))
                if key.startswith('game:'):
                    gid=key[5:]; return suffix.startswith(f'game-limit:{len(gid)}:{gid}:')
                return value.startswith('wellbeing:'+key+':')
            rows=[(new,value) for value, in self.db.execute('SELECT key FROM alerts WHERE day=?',(old,)) if matches(value)]
            self.db.executemany('INSERT OR IGNORE INTO alerts VALUES (?,?)',rows)

    def _load(self, key, day):
        cache_key = key, day
        if cache_key not in self.cache:
            self.cache[cache_key] = dict(self.db.execute(
                'SELECT item,seconds FROM independent_budget_usage WHERE budget=? AND day=?', cache_key))
        return self.cache[cache_key]

    def credit(self, key, minute, item, start, end, seconds, seed):
        self.totals(key, minute, start, seed)
        for day, amount in period_slices(start, end, seconds, (minute,) * 7):
            counter = self._load(key, day)
            counter[item] = counter.get(item, 0) + amount
            self.pending[(key, day, item)] += amount

    def flush(self):
        if not self.pending: return
        with self.db:
            self.write_pending()
        self.pending.clear()

    def write_pending(self):
        self.db.executemany('''INSERT INTO independent_budget_usage VALUES (?,?,?,?)
            ON CONFLICT(budget,day,item) DO UPDATE SET seconds=seconds+excluded.seconds''',
            [(*key, seconds) for key, seconds in self.pending.items()])

    def forget_clock(self, key):
        """Re-seed if a removed override is later enabled again."""
        self.flush()
        with self.db: self.db.execute('DELETE FROM independent_budget_clock WHERE budget=?',(key,))
        self.clocks.pop(key,None)
        self.cache={item:value for item,value in self.cache.items() if item[0]!=key}

    def prune(self, wall):
        """Bound storage outside the foreground sampling hot path."""
        self.flush()
        before = (wall.date() - timedelta(days=8)).isoformat()
        with self.db:
            self.db.execute('DELETE FROM independent_budget_usage WHERE day<?', (before,))
        self.cache = {key:value for key,value in self.cache.items() if key[1] >= before}
