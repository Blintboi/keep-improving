"""Encrypted per-rule registers and origin-owned shared budget counters.

Registers converge by (logical clock, writer). Usage replaces the last snapshot
from its measuring device; a receiving device never republishes that usage.
Native rule aliases preserve existing counters, drafts and local permissions.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,date,timedelta
import hashlib
import json
import math
import ntpath
import time
from . import device_scopes as scopes


def schema(store):
    if getattr(store,'_sharing_schema',False):return
    store.db.executescript('''
      CREATE TABLE IF NOT EXISTS device_rule_state (connection TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS device_rule_alias (connection TEXT NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,native TEXT NOT NULL,baseline TEXT NOT NULL,PRIMARY KEY(connection,id));
      CREATE TABLE IF NOT EXISTS device_rule_usage (connection TEXT NOT NULL,device TEXT NOT NULL,id TEXT NOT NULL,day TEXT NOT NULL,minute INTEGER NOT NULL,seconds REAL NOT NULL,PRIMARY KEY(connection,device,id,day));
      CREATE TABLE IF NOT EXISTS device_rule_sessions (connection TEXT NOT NULL,device TEXT NOT NULL,id TEXT NOT NULL,day TEXT NOT NULL,minute INTEGER NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(connection,device,id,day));
    ''')
    store._sharing_schema=True


def state(store,connection):
    schema(store)
    row=store.db.execute('SELECT value FROM device_rule_state WHERE connection=?',(connection,)).fetchone()
    return json.loads(row[0]) if row else {}


def write(store,connection,records):
    raw=json.dumps(records,ensure_ascii=False)
    row=store.db.execute('SELECT value FROM device_rule_state WHERE connection=?',(connection,)).fetchone()
    if row and row[0]==raw:return
    store.db.execute('INSERT OR REPLACE INTO device_rule_state VALUES (?,?)',(connection,raw))


def validate(payload):
    if not isinstance(payload,dict) or set(payload) not in ({'records','usage'},{'records','usage','session_usage'}):raise ValueError('Invalid shared rules.')
    records=payload['records'];usage=payload['usage']
    if not isinstance(records,dict) or len(records)>500 or len(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode())>240000:raise ValueError('Too many shared rules.')
    for id,r in records.items():
        if not isinstance(id,str) or not scopes.IDENTITY.fullmatch(id) or not isinstance(r,dict) or set(r)!={'clock','device','kind','value'}:raise ValueError('Invalid shared rule.')
        if type(r['clock']) is not int or not 0<r['clock']<2**53 or not scopes.IDENTITY.fullmatch(r['device']) or r['kind'] not in ('group','budget','notification'):raise ValueError('Invalid shared revision.')
        v=r['value']
        if v is None:continue
        if r['kind']=='group':scopes.validate_groups({id:v});continue
        if not isinstance(v,dict):raise ValueError('Invalid shared value.')
        scopes.validate(v.get('devices'))
        if not v.get('devices') or 'connection' not in v['devices']:raise ValueError('Missing device selection.')
        if r['kind']=='notification':
            from .notification_rules import validate_item
            validate_item(dict(v,id=id))
            if v.get('action',{}).get('kind')=='app' or not v.get('icon','').startswith('preset:'):raise ValueError('Local paths cannot be shared.')
        else:
            required={'name','seconds','enabled','enforce','days','usage_limit','reset_minute','members','devices'}
            if set(v)!=required or not isinstance(v['name'],str) or not 1<=len(v['name'])<=80:raise ValueError('Invalid shared budget.')
            if type(v['seconds']) not in (int,float) or not math.isfinite(v['seconds']) or not 0<=v['seconds']<=86400:raise ValueError('Invalid shared limit.')
            if any(type(v[k]) is not bool for k in ('enabled','enforce','usage_limit')):raise ValueError('Invalid shared switch.')
            if type(v['reset_minute']) is not int or not 0<=v['reset_minute']<1440:raise ValueError('Invalid renewal.')
            if not isinstance(v['days'],list) or len(set(v['days']))!=len(v['days']) or any(type(d) is not int or not 0<=d<7 for d in v['days']):raise ValueError('Invalid days.')
            if not isinstance(v['members'],list) or not 1<=len(v['members'])<=200:raise ValueError('Invalid members.')
            from .wellbeing import target
            for m in v['members']:
                if not isinstance(m,dict) or set(m)!={'kind','value'}:raise ValueError('Invalid member.')
                if m['kind']=='android':
                    import re
                    if not isinstance(m['value'],str) or len(m['value'])>255 or not re.fullmatch(r'[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+',m['value']):raise ValueError('Invalid Android package.')
                else:target(m['kind'],m['value'])
    if not isinstance(usage,list) or len(usage)>2000:raise ValueError('Invalid shared usage.')
    seen=set()
    for row in usage:
        if not isinstance(row,list) or len(row)!=4:raise ValueError('Invalid shared usage.')
        id,day,minute,seconds=row
        if not isinstance(id,str) or not scopes.IDENTITY.fullmatch(id) or date.fromisoformat(day).isoformat()!=day or type(minute) is not int or not 0<=minute<1440 or type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<=seconds<=172800 or (id,day) in seen:raise ValueError('Invalid shared usage.')
        seen.add((id,day))
    session_usage=payload.get('session_usage',[]);seen=set()
    if not isinstance(session_usage,list) or len(session_usage)>2000:raise ValueError('Invalid shared sessions.')
    for row in session_usage:
        if not isinstance(row,list) or len(row)!=4:raise ValueError('Invalid shared sessions.')
        id,day,minute,count=row
        if (not isinstance(id,str) or not scopes.IDENTITY.fullmatch(id) or date.fromisoformat(day).isoformat()!=day
                or type(minute) is not int or not 0<=minute<1440 or type(count) is not int or not 0<=count<=1000000 or (id,day) in seen):raise ValueError('Invalid shared sessions.')
        seen.add((id,day))
    return payload


def native_values(store,s):
    from .companion_commands import budgets
    from .notification_rules import items,builtin
    from .notification_text import KINDS
    # budgets accepts a draft, so observing a save never reads an older config.
    result={('budget',b['id']):b for b in budgets(store,s)}
    result.update({('notification',n['id']):n for n in [*items(s),*(builtin(s,k) for k in KINDS)] if n})
    return result


def portable(store,s,kind,value,previous=None):
    if value is None:return None
    if kind=='notification':
        from .notification_rules import normalized
        v=normalized(value);v.pop('id',None)
        if v['action']['kind']=='app':v['action']={'kind':'none'}
        if not v['icon'].startswith('preset:'):v['icon']='preset:bell'
        return v
    from .statistics_sync import game_key
    games={g.id:game_key(g.id,g.name,g.source) for g in store.games()}
    v={k:deepcopy(value[k]) for k in ('name','seconds','enabled','days','usage_limit','reset_minute','members')}
    v['enforce']=value.get('enforce',False);v['devices']=scopes.normalize(s.budget_devices[value['id']],s,budget=True)
    for member in v['members']:
        if member['kind']=='app':member['value']=ntpath.basename(member['value']).lower()
        if member['kind']=='game':member['value']=games.get(member['value'],member['value'])
    # A desktop edit must not drop the phone packages it cannot execute.
    for member in (previous or {}).get('members',[]):
        if member['kind']=='android' and member not in v['members']:v['members'].append(member)
    return v


def observe(store,s):
    if getattr(store,'_sharing_apply',False) or not s.statistics_sync_enabled or not s.statistics_sync_group:return
    connection=scopes.connection(s.statistics_sync_group);records=state(store,connection);values=native_values(store,s)
    aliases={id:(kind,native,json.loads(baseline)) for id,kind,native,baseline in store.db.execute('SELECT id,kind,native,baseline FROM device_rule_alias WHERE connection=?',(connection,))}
    counter=max([int(time.time()*1000),*(r['clock'] for r in records.values())])+1
    def update(id,kind,v):
        nonlocal counter
        records[id]=dict(clock=counter,device=s.scope_device,kind=kind,value=v);counter+=1
    for id,g in s.device_groups.items():
        if g['connection']==connection and (id not in aliases or aliases[id][2]!=g):update(id,'group',g)
        if g['connection']==connection:aliases[id]=('group',id,g)
    for id,(kind,native,baseline) in list(aliases.items()):
        if kind=='group' and baseline is not None and id not in s.device_groups:update(id,'group',None);aliases[id]=(kind,native,None)
    reverse={(kind,native):id for id,(kind,native,_) in aliases.items()}
    for (kind,native),v in values.items():
        selector=s.budget_devices.get(native) if kind=='budget' else v.get('devices')
        if selector is None:continue
        if selector.get('connection')!=connection:continue
        id=reverse.get((kind,native)) or hashlib.sha256((s.scope_device+':'+kind+':'+native).encode()).hexdigest()[:32]
        if id not in aliases or aliases[id][2]!=v:
            update(id,kind,portable(store,s,kind,v,(records.get(id) or {}).get('value')))
            aliases[id]=(kind,native,v)
    for id,(kind,native,baseline) in list(aliases.items()):
        if kind!='group' and baseline is not None and (kind,native) not in values:
            update(id,kind,None);aliases[id]=(kind,native,None)
    validate(dict(records=records,usage=[]))
    with store.db:
        write(store,connection,records)
        for id,(kind,native,v) in aliases.items():store.db.execute('''INSERT INTO device_rule_alias VALUES (?,?,?,?,?) ON CONFLICT(connection,id) DO UPDATE SET kind=excluded.kind,native=excluded.native,baseline=excluded.baseline WHERE kind!=excluded.kind OR native!=excluded.native OR baseline!=excluded.baseline''',(connection,id,kind,native,json.dumps(v,ensure_ascii=False)))


def merge(store,code,device,payload):
    validate(payload);connection=scopes.connection(code);records=state(store,connection)
    for id,r in payload['records'].items():
        old=records.get(id)
        if old and old['kind']!=r['kind']:raise ValueError('Shared rule kind changed.')
        if not old or (r['clock'],r['device'])>(old['clock'],old['device']):records[id]=r
    validate(dict(records=records,usage=[]));write(store,connection,records)
    store.db.execute('DELETE FROM device_rule_usage WHERE connection=? AND device=?',(connection,device))
    store.db.executemany('INSERT INTO device_rule_usage VALUES (?,?,?,?,?,?)',[(connection,device,*row) for row in payload['usage']])
    store.db.execute('DELETE FROM device_rule_sessions WHERE connection=? AND device=?',(connection,device))
    store.db.executemany('INSERT INTO device_rule_sessions VALUES (?,?,?,?,?,?)',[(connection,device,*row) for row in payload.get('session_usage',[])])
    store._shared_session_cache={}
    store.db.execute("INSERT OR REPLACE INTO settings VALUES ('device_rules_pending','1')")
    store.db.execute("INSERT OR REPLACE INTO settings VALUES ('device_rules_received_at',?)",(str(int(time.time())),))


def apply(store):
    s=store.settings()
    if not s.statistics_sync_enabled or not s.statistics_sync_group:return False
    connection=scopes.connection(s.statistics_sync_group);records=state(store,connection)
    if not records:return False
    # Capture local edits before applying incoming revisions, at the existing UI draft gate.
    aliases={id:(kind,native) for id,kind,native in store.db.execute('SELECT id,kind,native FROM device_rule_alias WHERE connection=?',(connection,))}
    from .statistics_sync import game_key
    games={game_key(g.id,g.name,g.source):g.id for g in store.games()}
    groups={id:r['value'] for id,r in records.items() if r['kind']=='group' and r['value'] is not None}
    proposed=replace(s,device_groups=groups,budget_devices=deepcopy(s.budget_devices),budget_active_days=deepcopy(s.budget_active_days),budget_usage_limits=dict(s.budget_usage_limits),budget_reset_overrides=dict(s.budget_reset_overrides),game_limits=dict(s.game_limits),wellbeing_rules=deepcopy(s.wellbeing_rules),scheduled_notifications=deepcopy(s.scheduled_notifications),notification_overrides=deepcopy(s.notification_overrides),removed_notifications=list(s.removed_notifications))
    from .notification_rules import BUILTIN_IDS
    for id,r in records.items():
        kind=r['kind'];v=deepcopy(r['value'])
        if kind=='group':continue
        native=aliases.get(id,(kind,id))[1];aliases[id]=(kind,native)
        if kind=='budget':
            existing=next((x for x in proposed.wellbeing_rules if x['id']==native),None)
            proposed.wellbeing_rules[:]=[x for x in proposed.wellbeing_rules if x['id']!=native]
            if v is None:
                if native=='shared-games':proposed.game_budget_enabled=False
                elif native.startswith('game:'):proposed.game_limits.pop(native[5:],None)
                proposed.budget_devices.pop(native,None)
                continue
            proposed.budget_devices[native]=v['devices'];proposed.budget_active_days[native]=v['days'];proposed.budget_usage_limits[native]=v['usage_limit'];proposed.budget_reset_overrides[native]=v['reset_minute']
            if native=='shared-games':proposed.limit_seconds=v['seconds'];proposed.warning_seconds=min(proposed.warning_seconds,v['seconds']*5/6);proposed.game_budget_enabled=v['enabled']
            elif native.startswith('game:'):proposed.game_limits[native[5:]]=v['seconds'];proposed.budget_active_days[native]=v['days'] if v['enabled'] else []
            else:
                members=[]
                for m in v['members']:
                    if m['kind']=='android':continue
                    if m['kind']=='game':
                        if m['value'] not in games:continue
                        m['value']=games[m['value']]
                    members.append(m)
                if members:proposed.wellbeing_rules.append(dict(id=native,name=v['name'],members=members,seconds=v['seconds'],enabled=v['enabled'],enforce=v['enforce'],overlay=(existing or {}).get('overlay',False)))
        else:
            builtin=next((k for k,x in BUILTIN_IDS.items() if x==native),None)
            old=next((x for x in proposed.scheduled_notifications if x['id']==native),None) or (proposed.notification_overrides.get(builtin) if builtin else None)
            proposed.scheduled_notifications[:]=[x for x in proposed.scheduled_notifications if x['id']!=native]
            if v is not None:
                v['id']=native
                if old and old.get('action',{}).get('kind')=='app':v['action']=old['action']
            if builtin:
                if v is None:
                    proposed.notification_overrides.pop(builtin,None)
                    if builtin not in proposed.removed_notifications:proposed.removed_notifications.append(builtin)
                else:
                    proposed.notification_overrides[builtin]=v
                    if builtin not in proposed.removed_notifications:proposed.removed_notifications.append(builtin)
            elif v is not None:proposed.scheduled_notifications.append(v)
    proposed.validate();changed=proposed!=s
    store._sharing_apply=True
    try:
        if changed:store.save_settings(proposed)
        values=native_values(store,proposed)
        with store.db:
            for id in groups:aliases[id]=('group',id)
            for id,(kind,native) in aliases.items():store.db.execute('INSERT OR REPLACE INTO device_rule_alias VALUES (?,?,?,?,?)',(connection,id,kind,native,json.dumps(groups.get(id) if kind=='group' else values.get((kind,native)),ensure_ascii=False)))
            store.db.execute("DELETE FROM settings WHERE key='device_rules_pending'")
    finally:store._sharing_apply=False
    return changed


def local_usage(store,s,native,rule):
    """Read only the local ledger. No StatisticsData aggregate enters an export."""
    tables={r[0] for r in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    key='quota:'+native if native=='shared-games' or native.startswith('game:') else native
    independent='independent_budget_clock' in tables and store.db.execute('SELECT 1 FROM independent_budget_clock WHERE budget=? AND minute=?',(key,rule['reset_minute'])).fetchone()
    before=(date.today()-timedelta(days=7)).isoformat();totals={}
    if independent:
        rows=store.db.execute('SELECT day,item,seconds FROM independent_budget_usage WHERE budget=? AND day>=?',(key,before))
    elif key.startswith('quota:'):
        table='budget_usage' if s.budget_reset_minute else 'usage'
        rows=store.db.execute('SELECT day,game_id,seconds FROM '+table+' WHERE day>=?',(before,))
    elif 'wellbeing_usage' in tables:rows=((day,json.dumps([game,app,site]),seconds) for day,game,app,site,seconds in store.db.execute('SELECT day,game_id,app,site,seconds FROM wellbeing_usage WHERE day>=?',(before,)))
    else:return {}
    members=next((r['members'] for r in s.wellbeing_rules if r['id']==native),[])
    from .wellbeing import applies
    for day,item,seconds in rows:
        matched=(not native.startswith('game:') or item==native[5:]) if key.startswith('quota:') else applies(members,json.loads(item),budget=native)
        if matched:totals[day]=totals.get(day,0)+seconds
    return totals


def snapshot(store,s):
    observe(store,s);connection=scopes.connection(s.statistics_sync_group);records=state(store,connection);usage=[];sessions=[]
    from .budget_sessions import local_counts
    for id,native in store.db.execute("SELECT id,native FROM device_rule_alias WHERE connection=? AND kind='budget'",(connection,)):
        r=records.get(id,{}).get('value')
        if r and scopes.applies(r['devices'],s):
            usage.extend([id,day,r['reset_minute'],seconds] for day,seconds in local_usage(store,s,native,r).items())
            members=([{'kind':'category','value':'games'}] if native=='shared-games' else [{'kind':'game','value':native[5:]}] if native.startswith('game:') else next((x['members'] for x in s.wellbeing_rules if x['id']==native),[]))
            sessions.extend([id,day,r['reset_minute'],count] for day,count in local_counts(store,s,native,members,r['reset_minute']).items() if count)
    return validate(dict(records=records,usage=usage,session_usage=sessions))


def remote_sessions(store,s,key,wall):
    scope=s.budget_devices.get(key)
    if not scope or scope.get('accounting','shared')!='shared' or not s.statistics_sync_enabled:return 0
    from .quota import budget_day,budget_minute
    connection=scopes.connection(s.statistics_sync_group);schema(store)
    day=str(budget_day(s,key,wall));minute=budget_minute(s,key)
    marker=(id(s),getattr(store,'statistics_revision',0),key,day)
    cache=getattr(store,'_shared_session_cache',{})
    if marker in cache:return cache[marker]
    alias=store.db.execute("SELECT id FROM device_rule_alias WHERE connection=? AND kind='budget' AND native=?",(connection,key)).fetchone()
    total=0
    if alias:
        for device,count in store.db.execute('SELECT device,count FROM device_rule_sessions WHERE connection=? AND id=? AND day=? AND minute=?',(connection,alias[0],day,minute)):
            if device!=s.scope_device and scopes.applies(scope,s,device):total+=count
    if len(cache)>500:cache.clear()
    cache[marker]=total;store._shared_session_cache=cache
    return total


def remote_seconds(store,s,key,wall):
    scope=s.budget_devices.get(key)
    if not scope or scope.get('accounting','shared')!='shared' or not s.statistics_sync_enabled:return 0
    from .quota import period_day
    connection=scopes.connection(s.statistics_sync_group);schema(store)
    day=period_day(wall,(s.budget_reset_overrides.get(key,s.budget_reset_minute),)*7).isoformat()
    marker=(id(s),getattr(store,'statistics_revision',0),key,day)
    cache=getattr(store,'_shared_usage_cache',{})
    if marker in cache:return cache[marker]
    alias=store.db.execute("SELECT id FROM device_rule_alias WHERE connection=? AND kind='budget' AND native=?",(connection,key)).fetchone()
    total=0
    if alias:
        for device,minute,seconds in store.db.execute('SELECT device,minute,seconds FROM device_rule_usage WHERE connection=? AND id=? AND day=?',(connection,alias[0],day)):
            if device!=s.scope_device and minute==s.budget_reset_overrides.get(key,s.budget_reset_minute) and scopes.applies(scope,s,device):total+=seconds
    if len(cache)>500:cache.clear()
    cache[marker]=total;store._shared_usage_cache=cache
    return total
