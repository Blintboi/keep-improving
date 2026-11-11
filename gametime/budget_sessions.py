"""Budget counts from measured visits, including unflushed foreground samples.

Overlapping app/game/site representations of the same visit count once.
Touching intervals of different activities remain separate visits. Renewal
counts starts, so a visit spanning midnight is not a second session.
"""
from collections import defaultdict
from datetime import timedelta
from .activity_sessions import EPSILON
from .quota import budget_day,budget_minute,reset_at
from .wellbeing import applies


def intervals(rows):
    grouped=defaultdict(list)
    for kind,key,start,finish,*_ in rows:
        grouped[kind,key].append((start,finish))
    result=[]
    for (kind,key),spans in grouped.items():
        merged=[]
        for start,finish in sorted(spans):
            if merged and start<=merged[-1][1]+EPSILON:
                merged[-1]=(merged[-1][0],max(finish,merged[-1][1]))
            else:merged.append((start,finish))
        result.extend((kind,key,start,finish) for start,finish in merged)
    return result


def count(rows,members,start,end,resolve=lambda key:''):
    selected=[]
    for kind,key,begin,finish in intervals(rows):
        atom=(key,'','') if kind=='game' else (resolve(key),key,'') if kind=='app' else ('','',key) if kind=='site' else None
        if applies(members,atom):selected.append((begin,finish))
    merged=[]
    for begin,finish in sorted(selected):
        if merged and begin<merged[-1][1]-EPSILON:
            merged[-1]=(merged[-1][0],max(finish,merged[-1][1]))
        else:merged.append((begin,finish))
    return sum(start<=begin<end for begin,_ in merged)


class Counter:
    def __init__(self,app):self.app=app;self.marker=None;self.rows=[]

    def counts(self,budgets,wall):
        app=self.app
        selected=[b for b in budgets if any(s.get('time_mode')=='sessions' and not s.get('session_choice') for s in app.settings.restriction_plans.get(b.key,{}).get('steps',()))]
        if not selected:return {}
        boundaries={b.key:reset_at(budget_day(app.settings,b.key,wall),budget_minute(app.settings,b.key),wall).timestamp() for b in selected}
        earliest=min(boundaries.values());db=app.store.db
        # SQLite is read only after a ledger flush/import or a period change.
        revision=db.execute("SELECT value FROM settings WHERE key='session_revision'").fetchone()
        marker=(earliest,revision)
        if marker!=self.marker:
            self.rows=list(db.execute('SELECT kind,key,start,finish FROM activity_sessions WHERE finish>=?',(earliest,)))
            self.marker=marker
        rows=[*self.rows,*app.focus.sessions.pending,*app.tracker.sessions.pending]
        resolved={}
        def resolve(path):
            if path not in resolved:
                game=app.catalog.resolve(path);resolved[path]=game.id if game else ''
            return resolved[path]
        from .device_sharing import remote_sessions
        return {b.key:count(rows,b.members,boundaries[b.key],wall.timestamp()+EPSILON,resolve)+remote_sessions(app.store,app.settings,b.key,wall) for b in selected}


def local_counts(store,settings,key,members,minute,days=8):
    """Origin-owned shared counts with the rule's own renewal, never aggregates."""
    from datetime import datetime
    from .model import Catalog
    wall=datetime.now().astimezone();today=budget_day(settings,key,wall)
    first=today-timedelta(days=days-1);start=reset_at(first,minute,wall).timestamp()
    rows=list(store.db.execute('SELECT kind,key,start,finish FROM activity_sessions WHERE finish>=?',(start,)))
    catalog=Catalog(settings,store.games(True),store.overrides(),store.rules())
    def resolve(path):
        game=catalog.resolve(path);return game.id if game else ''
    return {str(day):count(rows,members,reset_at(day,minute,wall).timestamp(),reset_at(day+timedelta(days=1),minute,wall).timestamp(),resolve)
            for day in (first+timedelta(days=i) for i in range(days))}
