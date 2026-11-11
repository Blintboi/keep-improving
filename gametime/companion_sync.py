"""Desktop settings and notification receipts for the encrypted phone companion.

No credentials, installation directories or remote imports are exported.
Phone-local rules remain separate; Windows edits use explicit targeted commands.
"""
from dataclasses import asdict
from datetime import date, timedelta
import hashlib
import json
import ntpath
import time

FORMAT='KeepImproving.companion.v1'
PRIVATE={'statistics_sync_group','games_root','steam_roots','epic_manifest_dirs','ubisoft_roots',
         'notification_sound_path','overlay_rtss_paths','overlay_screen','scope_device'}

def initialize(store):
    store.db.execute('CREATE TABLE IF NOT EXISTS companion_alerts (id TEXT PRIMARY KEY,at INTEGER NOT NULL,value TEXT NOT NULL)')

def portable_action(action):
    action=dict(action or {'kind':'none'})
    if action.get('kind')=='app': return {'kind':'desktop_app','name':ntpath.basename(action.get('path',''))}
    return action

def notification(rule):
    from .notification_rules import normalized
    value=normalized(rule); value['action']=portable_action(value['action'])
    if not value['icon'].startswith('preset:'): value['icon']='preset:bell'
    return value

def remember_alert(app,alert):
    import sqlite3
    import logging
    try:_remember_alert(app,alert)
    except (sqlite3.Error,OSError):logging.getLogger(__name__).warning('Could not queue phone notification',exc_info=True)

def _remember_alert(app,alert):
    if not app.settings.statistics_sync_enabled:return
    store=app.store; initialize(store)
    day=str(alert.day); raw=json.dumps([day,list(alert.keys),alert.kind],ensure_ascii=False)
    identity=hashlib.sha256(raw.encode()).hexdigest()
    cache=getattr(store,'_companion_receipts',None)
    if cache is None or cache[0]!=day:cache=(day,set());store._companion_receipts=cache
    if identity in cache[1]:return
    rule_id=next((key.split(':')[1] for key in alert.keys if key.startswith('scheduled:')),'')
    value=dict(id=identity,day=day,rule_id=rule_id,title=(getattr(alert,'title','') or app.t('Reminder'))[:100],
               text=alert.text[:2000],sound=bool(alert.sound),action=portable_action(getattr(alert,'action',None)),
               timeout=getattr(alert,'timeout',None),kind=alert.kind)
    with store.db:
        store.db.execute('INSERT OR IGNORE INTO companion_alerts VALUES (?,?,?)',(identity,int(time.time()*1000),json.dumps(value,ensure_ascii=False)))
        store.db.execute('DELETE FROM companion_alerts WHERE at<?',(int((time.time()-86400*7)*1000),))
    cache[1].add(identity)
    if hasattr(app,'schedule_statistics_event'):app.schedule_statistics_event()

def snapshot(store,focus):
    from .notification_rules import items,builtin
    from .notification_text import KINDS
    config=store.settings(); raw=asdict(config)
    settings={key:value for key,value in raw.items() if key not in PRIVATE and key not in {'scheduled_notifications','notification_overrides','wellbeing_rules'}}
    # Nested per-game screen selections are local monitor identities.
    for key in ('game_overlays','counter_overlays','activity_overlays'):
        settings[key]={identity:{name:value for name,value in options.items() if name!='overlay_screen'} for identity,options in settings[key].items()}
    focus_values=asdict(focus.settings) if focus else {}
    for key in ('block_apps','excluded_apps','included_apps'):focus_values[key]=[ntpath.basename(value) for value in focus_values.get(key,[])]
    rules=[notification(rule) for rule in items(config)]
    identities={rule['id'] for rule in rules}
    for kind in KINDS:
        rule=builtin(config,kind)
        if rule and rule['id'] not in identities:rules.append(notification(rule))
    from .companion_commands import budgets as budget_views,digest,resource,results
    budgets=budget_views(store)
    from .statistics_sync import game_key
    games=[dict(id=game.id,statistics_id=game_key(game.id,game.name,game.source),name=game.name,source=game.source) for game in store.games()]
    initialize(store)
    events=[]
    for at,raw in store.db.execute('SELECT at,value FROM companion_alerts WHERE at>=? ORDER BY at DESC LIMIT 200',(int((time.time()-86400)*1000),)):
        event=json.loads(raw);event['at']=at;events.append(event)
    hashes={}
    for kind,rows in (('budget',budgets),('notification',rules)):
        for rule in rows:hashes[kind+':'+rule['id']]=digest(rule)
    for key in settings:
        try:hashes['setting:'+key]=digest(resource(store,focus,'setting',key))
        except ValueError:pass
    hashes['focus:']=digest(resource(store,focus,'focus',''))
    value=dict(format=FORMAT,settings=settings,focus=focus_values,budgets=budgets,notifications=rules,games=games,activities=local_activities(store,config,focus),events=events,hashes=hashes,
               empty_hash=digest(None),command_results=results(store,config.statistics_sync_group),icons=cached_icons(store,focus))
    if focus:
        # Only a ticking timer needs a wall-clock anchor for remote countdowns.
        # Idle/paused snapshots must retain their revision and cached ciphertext.
        value['focus_state']=dict(running=focus.running,phase=focus.phase,remaining=max(0,focus.remaining),round=focus.round,at=int(time.time()*1000) if focus.running else 0,active=not focus.finished and (focus.running or focus.remaining!=focus.settings.work*60 or focus.phase!='focus'))
    from .device_sharing import schema
    from .device_scopes import connection
    schema(store)
    value['shared_ids']={kind+':'+native:id for id,kind,native in store.db.execute('SELECT id,kind,native FROM device_rule_alias WHERE connection=?',(connection(config.statistics_sync_group),))}
    validate(value)
    return value

def local_activities(store,settings,focus):
    from .activity_identity import canonical_member,activity_key,is_idle_app
    from .wellbeing import target
    candidates=[]
    if focus:candidates.extend(store.db.execute('SELECT kind,key,name FROM activity_items ORDER BY kind,key'))
    for rule in settings.wellbeing_rules:
        candidates.extend((m['kind'],m['value'],ntpath.basename(m['value'])) for m in rule['members'] if m['kind'] in ('app','site'))
    for key in settings.activity_overlays:
        kind,value=key.split(':',1);candidates.append((kind,value,ntpath.basename(value)))
    if focus:
        for key,kind in (('block_apps','app'),('excluded_apps','app'),('block_sites','site')):
            candidates.extend((kind,value,ntpath.basename(value)) for value in getattr(focus.settings,key))
    items={}
    for kind,value,name in candidates:
        if kind=='app' and is_idle_app(value):continue
        try:member=canonical_member(target(kind,value))
        except ValueError:continue
        identity=activity_key(member)
        items.setdefault(identity,dict(kind=kind,key=member['value'],name=ntpath.basename(name) if kind=='app' else member['value']))
    return sorted(items.values(),key=lambda item:(item['name'].casefold(),item['key']))

def cached_icons(store,focus):
    if not focus:return {}
    from .activity_identity import activity_key,canonical_member
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt,QBuffer,QByteArray,QIODevice
    import base64
    totals={};members={}
    since=(date.today()-timedelta(days=7)).isoformat()
    for kind,category,prefix in (('app','apps','activity:app:'),('site','websites','activity:site:')):
        for day,item,title,source,seconds in focus.history(since,date.today().isoformat(),category):
            key=item[len(prefix):];member=canonical_member(dict(kind=kind,value=key));identity=activity_key(member);members[identity]=member;totals[identity]=totals.get(identity,0)+seconds
    result={};size=0
    for key in sorted(totals,key=totals.get,reverse=True)[:48]:
        path=store.path.parent/'cache'/'activity-icons'/(hashlib.sha256(activity_key(members[key]).encode()).hexdigest()+'.png')
        try:
            if not path.is_file() or path.stat().st_size>256*1024:continue
            image=QImage(str(path))
            if image.isNull() or image.width()*image.height()>1000000:continue
            data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly)
            image.scaled(48,48,Qt.KeepAspectRatio,Qt.SmoothTransformation).save(buffer,'PNG');raw=bytes(data)
            if len(raw)>8192 or size+len(raw)>80*1024:continue
            result[key]=base64.b64encode(raw).decode('ascii');size+=len(raw)
        except OSError:continue
    return result

def validate(value):
    if (not isinstance(value,dict) or value.get('format')!=FORMAT or
            any(not isinstance(value.get(key),dict) for key in ('settings','focus')) or
            any(not isinstance(value.get(key),list) or len(value[key])>limit for key,limit in (('budgets',2200),('notifications',110),('games',100000),('events',200)))):
        raise ValueError('Invalid phone companion settings.')
    if PRIVATE.intersection(value['settings']) or len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())>2*1024*1024:
        raise ValueError('Invalid phone companion settings.')
    icons=value.get('icons',{})
    if (not isinstance(icons,dict) or len(icons)>48 or
            any(not isinstance(key,str) or len(key)>2100 or not isinstance(raw,str) or len(raw)>11000 for key,raw in icons.items()) or
            len(json.dumps(icons))>140000 or not isinstance(value.get('hashes',{}),dict) or
            not isinstance(value.get('command_results',[]),list) or len(value.get('command_results',[]))>2000 or
            not isinstance(value.get('activities',[]),list) or len(value.get('activities',[]))>100000):
        raise ValueError('Invalid phone companion settings.')

def focus_rows(store):
    if not store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='focus_completions'").fetchone():return []
    return [list(row) for row in store.db.execute('SELECT day,rounds FROM focus_completions WHERE rounds>0 ORDER BY day')]

def validate_focus(rows):
    if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Invalid focus history.')
    seen=set()
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=2:raise ValueError('Invalid focus history.')
        day,count=row
        if date.fromisoformat(day).isoformat()!=day or day in seen or type(count) is not int or not 0<count<=10000:raise ValueError('Invalid focus history.')
        seen.add(day)
