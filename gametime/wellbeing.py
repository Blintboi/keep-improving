"""Local, overlapping daily budgets over disjoint foreground activity intervals.

One row describes one foreground interval (game, executable and optional host).
Matching a browser and its website therefore never charges a group twice.
History and budget ledgers are independent, with one shared day boundary.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
import math
import json
import ntpath
import os
import re

from .focus import app_key, domain, matches, BROWSERS, SHELLS, BROWSER_IDLE
from .activity_identity import app_identity,site_identity,is_idle_app
from .tracker import day_slices
from .quota import current_day,period_day

CATEGORIES=('games','apps','sites')


def target(kind,value):
    if not isinstance(value,str) or not value or '\0' in value:
        raise ValueError('Choose a valid budget member.')
    if kind=='category':
        if value not in CATEGORIES: raise ValueError('Choose a valid budget member.')
    elif kind=='game':
        if len(value)>2048: raise ValueError('Choose a valid budget member.')
    elif kind=='app':
        value=app_key(value)
        if (not ntpath.isabs(value) and (ntpath.basename(value)!=value or ':' in value)
                or not value.endswith('.exe') or len(value)>2048):
            raise ValueError('Choose an application executable (.exe).')
    elif kind=='site': value=domain(value)
    else: raise ValueError('Choose a valid budget member.')
    return {'kind':kind,'value':value}


def validate_rules(rules):
    if not isinstance(rules,list) or len(rules)>100: raise ValueError('Use at most 100 time budgets.')
    ids=set()
    for rule in rules:
        if not isinstance(rule,dict) or set(rule)!={'id','name','members','seconds','enabled','enforce','overlay'}:
            raise ValueError('Invalid time budget.')
        if not isinstance(rule['id'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',rule['id']) or rule['id'] in ids:
            raise ValueError('Invalid time budget.')
        ids.add(rule['id'])
        if not isinstance(rule['name'],str) or not rule['name'].strip() or len(rule['name'])>80 or '\0' in rule['name']:
            raise ValueError('Give the budget a name (up to 80 characters).')
        value=rule['seconds']
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=86400:
            raise ValueError('Choose a daily limit between 0 and 1440 minutes.')
        if any(type(rule[key]) is not bool for key in ('enabled','enforce','overlay')): raise ValueError('Invalid time budget.')
        if not isinstance(rule['members'],list) or not 1<=len(rule['members'])<=200:
            raise ValueError('Choose between 1 and 200 members for a shared budget.')
        seen=set()
        for member in rule['members']:
            if not isinstance(member,dict) or set(member)!={'kind','value'}: raise ValueError('Choose a valid budget member.')
            normalized=target(member['kind'],member['value'])
            pair=(normalized['kind'],normalized['value'])
            if normalized!=member or pair in seen: raise ValueError('Choose distinct, valid budget members.')
            seen.add(pair)
    return rules


def applies(members,atom):
    if atom is None: return False
    game,app,site=atom
    for member in members:
        kind,value=member['kind'],member['value']
        if kind=='game' and game==value: return True
        if kind=='app' and app and app_identity(app)==app_identity(value): return True
        if kind=='site' and site and matches(site_identity(site),site_identity(value)): return True
        if kind=='category' and ((value=='games' and game) or (value=='apps' and app and not game) or (value=='sites' and site)):
            return True
    return False


def remap_rules(rules,aliases):
    from copy import deepcopy
    rules=deepcopy(rules)
    for rule in rules:
        members=[]
        for member in rule['members']:
            if member['kind']=='game': member['value']=aliases.get(member['value'],member['value'])
            if member not in members: members.append(member)
        rule['members']=members
    return rules


def counter_settings(settings,rule):
    from dataclasses import replace
    return replace(settings,overlay_enabled=rule['overlay'],**settings.counter_overlays.get(rule['id'],{}))


@dataclass(frozen=True)
class BudgetState:
    rule: dict
    used: float

    @property
    def remaining(self): return max(0,self.rule['seconds']-self.used)
    @property
    def warning(self): return self.remaining<=min(600,self.rule['seconds']/5)


class Wellbeing:
    def __init__(self,store,catalog,focus):
        self.store,self.catalog,self.focus=store,catalog,focus
        store.db.execute('''CREATE TABLE IF NOT EXISTS wellbeing_usage (
            day TEXT NOT NULL, game_id TEXT NOT NULL, app TEXT NOT NULL, site TEXT NOT NULL,
            seconds REAL NOT NULL, PRIMARY KEY(day,game_id,app,site))''')
        self.previous=None; self.current=None; self.pending=defaultdict(float)
        self.day=None; self.atoms={}; self.totals={}; self.source=None; self.rules=[]
        self.last_flush=None; self.revision=0
        row=store.db.execute("SELECT value FROM settings WHERE key='wellbeing_day_start'").fetchone()
        self.day_start_minute=json.loads(row[0]) if row else 0

    def change_clock(self,wall,minute):
        self.flush()
        old_day=period_day(wall,(self.day_start_minute,)*7).isoformat()
        new_day=period_day(wall,(minute,)*7).isoformat()
        rows=list(self.store.db.execute('SELECT game_id,app,site,seconds FROM wellbeing_usage WHERE day=?',(old_day,)))
        keys=[key for key in self.store.alert_keys(old_day) if key.startswith('wellbeing:')]
        with self.store.db:
            self.store.db.execute('DELETE FROM wellbeing_usage')
            self.store.db.executemany('INSERT INTO wellbeing_usage VALUES (?,?,?,?,?)',[(new_day,*row) for row in rows])
            self.store.db.execute("INSERT OR REPLACE INTO settings VALUES ('wellbeing_day_start',?)",(json.dumps(minute),))
        if keys: self.store.mark_alert(new_day,keys)
        self.day_start_minute=minute; self.day=None; self.source=None; self.previous=None; self.current=None

    def configure(self,wall):
        if self.day_start_minute!=self.catalog.settings.budget_reset_minute:
            self.change_clock(wall,self.catalog.settings.budget_reset_minute)
        source=self.catalog.settings.wellbeing_rules
        day=current_day(self.catalog.settings,wall).isoformat()
        if self.day!=day:
            self.flush(); self.day=day
            self.atoms={(game,app,site):seconds for game,app,site,seconds in self.store.db.execute(
                'SELECT game_id,app,site,seconds FROM wellbeing_usage WHERE day=?',(day,)) if not is_idle_app(app)}
            with self.store.db:
                self.store.db.execute('DELETE FROM wellbeing_usage WHERE day<?',((current_day(self.catalog.settings,wall)-timedelta(days=8)).isoformat(),))
            self.source=None
        if source is not self.source:
            self.source=source; self.rules=[rule for rule in source if rule['enabled']]
            self.totals={rule['id']:sum(seconds for atom,seconds in self.atoms.items() if applies(rule['members'],atom)) for rule in self.rules}
            self.revision+=1

    def atom(self,sample,website=''):
        if not sample.interactive or not sample.path or not sample.identity or sample.identity.startswith(str(os.getpid())+':'): return None
        app=app_key(sample.path); filename=ntpath.basename(app)
        if filename in SHELLS or filename in BROWSERS and website==BROWSER_IDLE or self.focus.settings.app_excluded(app): return None
        game=self.catalog.resolve(app)
        # Browser/helper filtering belongs to games, not to general applications.
        from .model import helper
        if not game and (app in self.catalog.rules or not helper(app)) and self.catalog.explicitly_ignored(app): return None
        if not game and not self.focus.settings.tracking: return None
        return (game.id if game else '',app,website if filename in BROWSERS and self.focus.settings.tracking else '')

    def tick(self,sample,website=''):
        if self.day_start_minute!=self.catalog.settings.budget_reset_minute: self.configure(sample.wall)
        atom=self.atom(sample,website); previous=self.previous
        self.previous=(sample,atom); self.current=(sample,atom)
        if previous:
            prev,old=previous; delta=sample.awake-prev.awake; wall=sample.wall.timestamp()-prev.wall.timestamp()
            if old and self.atom(prev,old[2]) and sample.interactive and 0<delta<=3 and wall>0 and abs(wall-delta)<=1.5:
                for day,seconds in day_slices(prev.wall,sample.wall,delta,self.day_start_minute):
                    instant=prev.wall if day==current_day(self.catalog.settings,prev.wall).isoformat() else sample.wall
                    self.configure(instant)
                    self.atoms[old]=self.atoms.get(old,0)+seconds
                    self.pending[(day,*old)]+=seconds
                    for rule in self.rules:
                        if applies(rule['members'],old): self.totals[rule['id']]+=seconds
                    self.revision+=1
        self.configure(sample.wall)
        if self.last_flush is None: self.last_flush=sample.awake
        if sample.awake-self.last_flush>=10: self.flush(); self.last_flush=sample.awake

    def states(self,wall,atom=None):
        self.configure(wall)
        return [BudgetState(rule,self.totals.get(rule['id'],0)) for rule in self.rules if atom is None or applies(rule['members'],atom)]

    def active(self):
        if not self.current or not self.current[1]: return []
        sample,atom=self.current
        return self.states(sample.wall,atom)

    def remap(self,aliases):
        # The caller flushes before Store migrates the ledger atomically.
        if not aliases: return
        for name in ('previous','current'):
            value=getattr(self,name)
            if value and value[1]:
                sample,(game,app,site)=value
                setattr(self,name,(sample,(aliases.get(game,game),app,site)))
        self.day=None; self.source=None

    def policy(self,base,wall):
        policy=dict(base); blocked=list(base['block']) if base['active'] else []; all_sites=False
        for state in self.states(wall):
            if state.rule['id'] in self.catalog.settings.restriction_plans: continue
            if state.remaining or not state.rule['enforce']: continue
            for member in state.rule['members']:
                if member['kind']=='site': blocked.append(member['value'])
                if member=={'kind':'category','value':'sites'}: all_sites=True
        if blocked or all_sites:
            policy.update(active=True,block=list(dict.fromkeys(blocked)),mode='allowlist' if all_sites else 'blocklist',
                          allow=[],remaining=max(base['remaining'],30))
        return policy

    def flush(self):
        if not self.pending: return
        with self.store.db:
            self.store.db.executemany('''INSERT INTO wellbeing_usage VALUES (?,?,?,?,?)
                ON CONFLICT(day,game_id,app,site) DO UPDATE SET seconds=seconds+excluded.seconds''',
                [(*key,value) for key,value in self.pending.items()])
        self.pending.clear()
