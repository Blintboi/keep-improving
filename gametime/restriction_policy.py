"""Versioned, local restriction plans and a durable once-per-period save allowance.

No Windows or UI dependencies. Notifications are events; restrictions are states.
"""
from dataclasses import dataclass
import json
import math
import re

KINDS = ('notify', 'minimize', 'cover', 'close')
RANK = {'minimize': 1, 'cover': 2, 'close': 3}


def validate_plans(plans):
    if not isinstance(plans, dict) or len(plans) > 2200:
        raise ValueError('Invalid restriction plan.')
    for key, plan in plans.items():
        if not isinstance(key, str) or not key or len(key) > 2100 or '\0' in key:
            raise ValueError('Invalid restriction plan.')
        if (not isinstance(plan, dict) or set(plan) != {'version', 'steps', 'extension_minutes', 'close_confirmed'}
                or type(plan['version']) is not int or plan['version'] != 1
                or type(plan['extension_minutes']) is not int or not 0 <= plan['extension_minutes'] <= 60
                or type(plan['close_confirmed']) is not bool
                or not isinstance(plan['steps'], list) or len(plan['steps']) > 20):
            raise ValueError('Invalid restriction plan.')
        seen = set()
        for step in plan['steps']:
            if (not isinstance(step, dict) or set(step) != {'id', 'kind', 'offset', 'sound', 'popup'}
                    or not isinstance(step['id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', step['id'])
                    or step['id'] in seen or step['kind'] not in KINDS
                    or type(step['offset']) not in (float, int) or not math.isfinite(step['offset'])
                    or not -86400 <= step['offset'] <= 86400
                    or any(type(step[k]) is not bool for k in ('sound', 'popup'))):
                raise ValueError('Invalid restriction plan.')
            seen.add(step['id'])
            if step['kind'] == 'notify' and not (step['sound'] or step['popup']):
                raise ValueError('Choose a sound or popup for each warning.')
            if step['kind'] != 'notify' and step['offset'] < 0:
                raise ValueError('Restrictions start at or after the limit.')
        if (plan['extension_minutes'] or any(s['kind'] == 'close' for s in plan['steps'])) and not plan['close_confirmed']:
            raise ValueError('Confirm that unsaved work may be lost.')
    return plans


def new_plan():
    return {'version': 1, 'steps': [], 'extension_minutes': 0, 'close_confirmed': False}


def remap_state(db, old, new):
    """Keep one-time rights consumed when discovery merges a manual game."""
    for day, raw in db.execute('SELECT day,value FROM restriction_state WHERE budget=?',(old,)).fetchall():
        value=json.loads(raw)
        existing=db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',(day,new)).fetchone()
        if existing:
            current=json.loads(existing[0])
            current['used_extension'] |= value['used_extension']
            current['delivered']=sorted(set(current['delivered'])|set(value['delivered']))
            if value['grant'] and (not current['grant'] or value['grant']['until']<current['grant']['until']):
                current['grant']=value['grant']
            value=current
        db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',(day,new,json.dumps(value)))
    db.execute('DELETE FROM restriction_state WHERE budget=?',(old,))


def step(kind, offset=0, *, sound=False, popup=False, identity=None):
    import uuid
    return dict(id=identity or uuid.uuid4().hex, kind=kind, offset=offset, sound=sound, popup=popup)


@dataclass(frozen=True)
class Budget:
    key: str
    name: str
    limit: float
    used: float
    members: tuple


class RestrictionState:
    def __init__(self, store):
        self.db = store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS restriction_state (day TEXT NOT NULL, '
                        'budget TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(day,budget))')
        self.day = None
        self.rows = {}
        self.budgets = {}
        self.plans = {}
        self.now = 0

    def _save(self, key):
        self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)',
                        (self.day, key, json.dumps(self.rows[key], separators=(',', ':'))))

    def update(self, day, now, budgets, plans):
        if self.day != day:
            self.day = day
            self.rows = {key: json.loads(value) for key, value in self.db.execute(
                'SELECT budget,value FROM restriction_state WHERE day=?', (day,))}
        self.now = now
        self.budgets = {b.key: b for b in budgets if b.key in plans}
        self.plans = plans
        with self.db:
            for key in self.rows.keys() | self.budgets.keys():
                before = json.dumps(self.rows.get(key))
                row = self.rows.setdefault(key, {'expired': None, 'used_extension': False,
                                                'grant': None, 'delivered': []})
                budget = self.budgets.get(key)
                signature = json.dumps(plans.get(key), sort_keys=True)
                if row.get('plan') != signature:
                    row['grant'] = None
                    row['plan'] = signature
                if not budget or budget.used < budget.limit:
                    row['expired'] = None
                    row['grant'] = None
                elif row['expired'] is None:
                    row['expired'] = now
                if before != json.dumps(row): self._save(key)

    def due(self, key):
        budget = self.budgets.get(key)
        if not budget: return []
        row = self.rows[key]
        return [s for s in self.plans[key]['steps'] if
                (s['offset'] <= 0 and budget.used >= max(0, budget.limit + s['offset'])) or
                (s['offset'] > 0 and row['expired'] is not None and self.now >= row['expired'] + s['offset'])]

    def grant(self, key, subject):
        row = self.rows.get(key, {})
        grant = row.get('grant')
        return grant if grant and grant['subject'] == subject and row.get('expired') is not None else None

    def action(self, key, subject):
        if key not in self.budgets: return ''
        grant = self.grant(key, subject)
        if grant:
            if self.now < grant['until']: return ''
            return 'cover' if subject.startswith('site:') else 'close'
        kinds = [s['kind'] for s in self.due(key) if s['kind'] != 'notify']
        return max(kinds, key=RANK.get) if kinds else ''

    def warnings(self, key):
        return [s for s in self.due(key) if s['kind'] == 'notify' and s['id'] not in self.rows[key]['delivered']]

    def delivered(self, key, identity):
        with self.db:
            if identity not in self.rows[key]['delivered']:
                self.rows[key]['delivered'].append(identity)
                self._save(key)

    def allowance(self, keys, subject):
        if not keys: return 0
        minutes = []
        for key in keys:
            if (key not in self.budgets or self.rows[key]['used_extension']
                    or self.action(key, subject) != 'cover'):
                return 0
            minutes.append(self.plans[key]['extension_minutes'])
        return min(minutes)

    def extend(self, keys, subject):
        keys = sorted(set(keys))
        minutes = self.allowance(keys, subject)
        if not minutes: return None
        until = self.now + minutes * 60
        # SQLite is the authority, not a GUI button's cached enabled state.
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            for key in keys:
                raw = self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?',
                                      (self.day, key)).fetchone()
                if raw and json.loads(raw[0])['used_extension']: return None
            for key in keys:
                self.rows[key].update(used_extension=True, grant={'subject': subject, 'until': until})
                self._save(key)
        return until

    def move_day(self, old, new):
        if old == new: return
        with self.db:
            for key, raw in self.db.execute('SELECT budget,value FROM restriction_state WHERE day=?', (old,)).fetchall():
                previous = json.loads(raw)
                target = self.db.execute('SELECT value FROM restriction_state WHERE day=? AND budget=?', (new, key)).fetchone()
                if target:
                    merged = json.loads(target[0])
                    merged['used_extension'] |= previous['used_extension']
                    merged['delivered'] = sorted(set(merged['delivered']) | set(previous['delivered']))
                    if previous['grant'] and (not merged['grant'] or previous['grant']['until'] < merged['grant']['until']):
                        merged['grant'] = previous['grant']
                    previous = merged
                self.db.execute('INSERT OR REPLACE INTO restriction_state VALUES (?,?,?)', (new, key, json.dumps(previous)))
        self.day = None
