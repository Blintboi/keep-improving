"""Portable preferences carried inside the existing encrypted statistics snapshot.

Each field is a last-writer-wins register. Device credentials, computer identity,
local paths and explicit protected-game consent never leave the computer.
"""
from dataclasses import asdict, fields, replace
import json
from pathlib import Path
import re
from .model import Settings

LOCAL_FIELDS={'games_root','steam_roots','epic_manifest_dirs','ubisoft_roots',
              'overlay_screen','overlay_rtss_paths','notification_sound_path',
              'statistics_sync_enabled','statistics_sync_group','statistics_device_name'}
CONFIG_FIELDS={item.name for item in fields(Settings)}-LOCAL_FIELDS
CONFIG_FIELDS-={'game_limits','game_overlays','limit_seconds','warning_seconds',
                'bedtime_warning_minute','bedtime_minute','bedtime_resume_minute'}
PAIRED_FIELDS={'settings.play_window':('limit_seconds','warning_seconds'),
               'settings.bedtime_window':('bedtime_warning_minute','bedtime_minute','bedtime_resume_minute')}
FOCUS_FIELDS={'tracking','work','short_break','long_break','rounds','block_sites','block_apps','excluded_apps'}
MAX_FIELDS=4000
MAX_REGISTER_BYTES=128*1024
IDENTITY=re.compile(r'[0-9a-f]{32}')


def key(group):
    from .statistics_sync import local_group
    return 'preferences_sync:'+local_group(group)


def pending_key(group): return key(group)+':pending'
def initialized_key(group): return key(group)+':initialized'


def read(store, name):
    row=store.db.execute('SELECT value FROM settings WHERE key=?',(name,)).fetchone()
    if not row: return {}
    try: return validate(json.loads(row[0]))
    except (ValueError,TypeError): return {}


def write(store, name, value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if len(raw.encode('utf-8'))>MAX_REGISTER_BYTES: raise ValueError('Synchronized settings are too large.')
    store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(name,raw))


def identity(store):
    import uuid
    row=store.db.execute("SELECT value FROM settings WHERE key='statistics_device_id'").fetchone()
    if row and IDENTITY.fullmatch(row[0]): return row[0]
    value=uuid.uuid4().hex
    with store.db: store.db.execute("INSERT OR REPLACE INTO settings VALUES ('statistics_device_id',?)",(value,))
    return value


def values(store, settings=None):
    from .focus import FocusSettings
    settings=settings or store.settings()
    config=asdict(settings)
    row=store.db.execute("SELECT value FROM settings WHERE key='focus_config'").fetchone()
    try:
        focus=json.loads(row[0]) if row else {}
        for name in ('mode','allow_apps','allow_sites'): focus.pop(name,None)
        focus=asdict(FocusSettings(**focus).validate())
    except (ValueError,TypeError): focus=asdict(FocusSettings())
    result={**{'settings.'+name:config[name] for name in CONFIG_FIELDS},
            **{'focus.'+name:focus[name] for name in FOCUS_FIELDS}}
    result.update({key:{name:config[name] for name in names} for key,names in PAIRED_FIELDS.items()})
    from .statistics_sync import game_key
    overrides=store.overrides(); hidden=store.hidden_ids()
    for game in store.games():
        identity=game_key(game.id,game.name,game.source)
        overlay=dict(settings.game_overlays.get(game.id,{})); overlay.pop('overlay_screen',None)
        for kind,value in (('enabled',overrides.get(game.id,True)),('hidden',game.id in hidden),
                           ('limit',settings.game_limits.get(game.id)),('overlay',overlay)):
            result[f'game.{kind}.{identity}']=value
    return result


def defaults():
    from .focus import FocusSettings
    config=asdict(Settings()); focus=asdict(FocusSettings())
    result={**{'settings.'+name:config[name] for name in CONFIG_FIELDS},
            **{'focus.'+name:focus[name] for name in FOCUS_FIELDS}}
    result.update({key:{name:config[name] for name in names} for key,names in PAIRED_FIELDS.items()})
    return result


ALLOWED={'settings.'+name for name in CONFIG_FIELDS}|{'focus.'+name for name in FOCUS_FIELDS}|set(PAIRED_FIELDS)
GAME_FIELD=re.compile(r'game\.(enabled|hidden|limit|overlay)\.(.{1,512})')
GAME_DEFAULTS={'enabled':True,'hidden':False,'limit':None,'overlay':{}}


def validate(value):
    if not isinstance(value,dict) or len(value)>MAX_FIELDS: raise ValueError('Invalid synchronized settings.')
    accepted={}
    try:
        if len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8'))>MAX_REGISTER_BYTES: raise ValueError()
        for name,entry in value.items():
            if not isinstance(name,str) or len(name)>530 or not isinstance(entry,dict) or set(entry)!={'clock','device','value'}: raise ValueError()
            if type(entry['clock']) is not int or not 0<entry['clock']<2**63: raise ValueError()
            if not isinstance(entry['device'],str) or not IDENTITY.fullmatch(entry['device']): raise ValueError()
            game=GAME_FIELD.fullmatch(name)
            if name not in ALLOWED and not game:
                if name.startswith(('settings.','focus.','game.')): continue
                raise ValueError()
            if game and game[1] in ('enabled','hidden') and type(entry['value']) is not bool: raise ValueError()
            if game and game[1]=='limit' and entry['value'] is not None and type(entry['value']) not in (int,float): raise ValueError()
            if game and game[1]=='overlay' and (not isinstance(entry['value'],dict) or 'overlay_screen' in entry['value']): raise ValueError()
            if name in PAIRED_FIELDS and (not isinstance(entry['value'],dict) or set(entry['value'])!=set(PAIRED_FIELDS[name])): raise ValueError()
            accepted[name]=entry
    except (TypeError,ValueError,OverflowError,RecursionError):
        raise ValueError('Invalid synchronized settings.') from None
    return accepted


def observe(store, group, identity):
    """Record only changed values; unchanged syncs make no database writes."""
    name=key(group); state=read(store,name); current=values(store); default=defaults()
    clock=max((entry['clock'] for entry in state.values()),default=0)+1
    changed=False
    for field,value in current.items():
        prior=state.get(field)
        baseline=default.get(field,GAME_DEFAULTS.get(field.split('.')[1]) if field.startswith('game.') else None)
        if prior is None and value==baseline: continue
        if prior is not None and prior['value']==value: continue
        state[field]={'clock':clock,'device':identity,'value':value}; changed=True
    initialized=store.db.execute('SELECT 1 FROM settings WHERE key=?',(initialized_key(group),)).fetchone()
    if changed or not initialized:
        with store.db:
            if changed: write(store,name,state)
            if not initialized: store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(initialized_key(group),'1'))
    return state


def stage(store, group, remote, *, force=False):
    remote=validate(remote); name=pending_key(group); pending=read(store,name)
    current={} if force else read(store,key(group))
    changed=False
    for field,entry in remote.items():
        previous=pending.get(field) or current.get(field)
        if previous is None or (entry['clock'],entry['device'])>(previous['clock'],previous['device']):
            pending[field]=entry; changed=True
    if changed:
        with store.db: write(store,name,pending)
    return changed


def apply(store, group, identity, focus):
    """Merge atomically after the UI has no unsaved settings or open editors."""
    pending=read(store,pending_key(group))
    if not pending: return False
    state=read(store,key(group)); merged=dict(state)
    for field,entry in pending.items():
        old=merged.get(field)
        if old is None or (entry['clock'],entry['device'])>(old['clock'],old['device']): merged[field]=entry
    settings=store.settings(); config={field[9:]:entry['value'] for field,entry in merged.items() if field.startswith('settings.') and field not in PAIRED_FIELDS}
    for field in PAIRED_FIELDS:
        if field in merged: config.update(merged[field]['value'])
    # A WAV path is machine-specific. Do not switch to a custom sound that
    # cannot be played on this computer or reject unrelated preferences.
    if config.get('notification_sound')=='custom' and not Path(settings.notification_sound_path).is_file():
        config.pop('notification_sound')
        if 'settings.notification_sound' in state: merged['settings.notification_sound']=state['settings.notification_sound']
        else: merged.pop('settings.notification_sound',None)
    from .statistics_sync import game_key
    limits=dict(settings.game_limits); overlays=dict(settings.game_overlays); game_changes=[]
    for game in store.games():
        gid=game_key(game.id,game.name,game.source)
        for kind in ('enabled','hidden','limit','overlay'):
            item=merged.get(f'game.{kind}.{gid}')
            if item is None: continue
            value=item['value']
            if kind=='limit':
                if value is None: limits.pop(game.id,None)
                else: limits[game.id]=value
            elif kind=='overlay':
                local_screen=overlays.get(game.id,{}).get('overlay_screen')
                combined=dict(value)
                if local_screen: combined['overlay_screen']=local_screen
                if not combined: overlays.pop(game.id,None)
                else: overlays[game.id]=combined
            else: game_changes.append((kind,game.id,value))
    config.update(game_limits=limits,game_overlays=overlays)
    from .focus import FocusSettings
    focus_values=asdict(focus.settings)
    focus_values.update({field[6:]:entry['value'] for field,entry in merged.items() if field.startswith('focus.')})
    # Validate the complete proposed configuration before touching local data.
    candidate=replace(settings,**config).validate()
    focus_candidate=FocusSettings(**focus_values).validate()
    changed=candidate!=settings or focus_candidate!=focus.settings
    overrides=store.overrides(); hidden=store.hidden_ids()
    changed=changed or any((overrides.get(gid,True) if kind=='enabled' else gid in hidden)!=value for kind,gid,value in game_changes)
    if changed: focus.flush()
    with store.db:
        if changed:
            # Preserve the local DPAPI-protected connection credential verbatim.
            row=store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
            old=json.loads(row[0]) if row else {}
            config_data=asdict(candidate)
            config_data['statistics_sync_group']=old.get('statistics_sync_group','')
            store.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)",(json.dumps(config_data,ensure_ascii=False),))
            store.db.execute("INSERT OR REPLACE INTO settings VALUES ('focus_config',?)",(json.dumps(asdict(focus_candidate)),))
            for kind,gid,value in game_changes:
                table,column=('overrides','enabled') if kind=='enabled' else ('game_preferences','hidden')
                store.db.execute(f'INSERT OR REPLACE INTO {table} (game_id,{column}) VALUES (?,?)',(gid,int(value)))
        write(store,key(group),merged)
        store.db.execute('DELETE FROM settings WHERE key=?',(pending_key(group),))
    if changed: focus.configure(focus_candidate)
    return changed
