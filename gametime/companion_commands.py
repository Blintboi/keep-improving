"""Idempotent, explicitly targeted phone edits with per-resource conflict checks."""
from dataclasses import asdict,replace
import hashlib
import json
import re
import time
from .companion_sync import PRIVATE,notification

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def budgets(store,settings=None):
    s=settings or store.settings(); result=[]
    sources=[dict(id='shared-games',name='Shared game budget',scope='shared',seconds=s.limit_seconds,warning_seconds=s.warning_seconds,enabled=s.game_budget_enabled,members=[dict(kind='category',value='games')])]
    for game in store.games():
        if game.id in s.game_limits:sources.append(dict(id='game:'+game.id,name=game.name,scope='game',seconds=s.game_limits[game.id],enabled=bool(s.budget_active_days.get('game:'+game.id,list(range(7)))),members=[dict(kind='game',value=game.id)]))
    for rule in s.wellbeing_rules:sources.append({**rule,'scope':'group'})
    for source in sources:
        key=source['id'];days=s.budget_active_days.get(key,list(range(7)))
        result.append({**source,'days':days,'usage_limit':s.budget_usage_limits.get(key,True),'reset_minute':s.budget_reset_overrides.get(key,s.budget_reset_minute),'plan':s.restriction_plans.get(key),**({'devices':s.budget_devices[key]} if key in s.budget_devices else {})})
    return result

def resource(store,focus,kind,key):
    if kind=='budget':return next((b for b in budgets(store) if b['id']==key),None)
    if kind=='notification':
        from .notification_rules import items,builtin
        from .notification_text import KINDS
        rules=items(store.settings())+[rule for name in KINDS if (rule:=builtin(store.settings(),name))]
        return next((notification(rule) for rule in rules if rule['id']==key),None)
    if kind=='setting':
        if key in PRIVATE or key in {'statistics_sync_enabled','statistics_device_name','scheduled_notifications','notification_overrides','removed_notifications','wellbeing_rules','restriction_plans','game_limits','budget_active_days','budget_usage_limits','budget_reset_overrides'}:raise ValueError('This setting is managed on its own page.')
        value=asdict(store.settings())
        if key not in value:raise ValueError('Unknown setting.')
        return value[key]
    if kind=='focus':return {k:getattr(focus.settings,k) for k in ('tracking','work','short_break','long_break','rounds')} if focus else None
    raise ValueError('Unsupported remote change.')

def initialize(store):
    store.db.execute('CREATE TABLE IF NOT EXISTS companion_commands (group_id TEXT NOT NULL,id TEXT NOT NULL,origin TEXT NOT NULL,value TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,at INTEGER NOT NULL,PRIMARY KEY(group_id,id))')

def validate(commands):
    if not isinstance(commands,list) or len(commands)>100:raise ValueError('Invalid remote changes.')
    seen=set()
    for item in commands:
        if (not isinstance(item,dict) or set(item)!={'id','target','kind','key','base','value','created'} or
                not isinstance(item['id'],str) or not re.fullmatch('[0-9a-f]{32}',item['id']) or item['id'] in seen or
                not isinstance(item['target'],str) or not re.fullmatch('[0-9a-f]{32}',item['target']) or
                item['kind'] not in ('budget','notification','setting','focus') or
                not isinstance(item['key'],str) or len(item['key'])>2100 or '\0' in item['key'] or
                not isinstance(item['base'],str) or not re.fullmatch('[0-9a-f]{64}',item['base']) or
                type(item['created']) is not int or item['created']<0 or len(json.dumps(item,ensure_ascii=False,allow_nan=False))>128*1024):raise ValueError('Invalid remote changes.')
        seen.add(item['id'])

def stage(store,group,local,origin,commands,*,transaction=True):
    from contextlib import nullcontext
    from .statistics_sync import local_group
    validate(commands);initialize(store)
    with store.db if transaction else nullcontext():
        for item in commands:
            if item['target']!=local:continue
            store.db.execute('INSERT OR IGNORE INTO companion_commands VALUES (?,?,?,?,?,?,?)',(local_group(group),item['id'],origin,json.dumps(item,ensure_ascii=False),'pending','',int(time.time()*1000)))

def results(store,group):
    from .statistics_sync import local_group
    initialize(store)
    return [dict(id=id,origin=origin,status=status,reason=reason,at=at) for id,origin,status,reason,at in store.db.execute('SELECT id,origin,status,reason,at FROM companion_commands WHERE group_id=? ORDER BY at DESC LIMIT 2000',(local_group(group),))]

def candidate(store,focus,item):
    s=store.settings();kind=item['kind'];key=item['key'];value=item['value'];old=resource(store,focus,kind,key)
    if digest(old)!=item['base']:raise ValueError('conflict')
    if kind=='setting':return replace(s,**{key:value}).validate(),None
    if kind=='focus':
        if not isinstance(value,dict) or set(value)!=set(old):raise ValueError('Invalid focus settings.')
        return s,replace(focus.settings,**value).validate()
    if kind=='notification':
        from .notification_rules import validate_item,BUILTIN_IDS,items
        if value is not None:
            value=dict(value)
            if value.get('id')!=key:raise ValueError('Invalid notification identity.')
            if value.get('action',{}).get('kind')=='app':raise ValueError('New executable actions must be configured on the PC.')
            if value.get('action',{}).get('kind')=='desktop_app':
                existing=next((rule for rule in items(s) if rule['id']==key),None)
                if not existing or notification(existing)['action']!=value['action']:raise ValueError('Desktop application action cannot be changed here.')
                value['action']=existing['action']
            validate_item(value)
        builtin_kind=next((kind for kind,id in BUILTIN_IDS.items() if id==key),None)
        if builtin_kind:
            overrides=dict(s.notification_overrides);removed=list(s.removed_notifications)
            if value is None:overrides.pop(builtin_kind,None);removed=list(set(removed)|{builtin_kind})
            else:
                overrides[builtin_kind]=value
                if builtin_kind not in removed:removed.append(builtin_kind)
            return replace(s,notification_overrides=overrides,removed_notifications=removed).validate(),None
        rules=[rule for rule in s.scheduled_notifications if rule['id']!=key]
        if value is not None:rules.append(value)
        return replace(s,scheduled_notifications=rules).validate(),None
    if kind=='budget':
        if value is None:
            if old is None:return s,None
            if old['scope']=='shared':return replace(s,game_budget_enabled=False).validate(),None
            if old['scope']=='game':limits=dict(s.game_limits);limits.pop(key[5:],None);return replace(s,game_limits=limits).validate(),None
            return replace(s,wellbeing_rules=[r for r in s.wellbeing_rules if r['id']!=key]).validate(),None
        if not isinstance(value,dict) or value.get('id')!=key or value.get('scope') not in ('shared','game','group'):raise ValueError('Invalid budget.')
        if old and value['scope']!=old['scope']:raise ValueError('Invalid budget scope.')
        if not old and value['scope']!='group':raise ValueError('New budgets must be groups.')
        seconds=value['seconds'];enabled=value['enabled'];days=value['days'] if enabled or value['scope']!='game' else []
        if type(enabled) is not bool or type(seconds) not in (int,float) or not 0<=seconds<=86400:raise ValueError('Invalid budget limit.')
        # Advanced plans and loss-of-work confirmations remain exactly as configured on the PC.
        if value.get('plan')!=(old or {}).get('plan'):raise ValueError('Advanced restriction plans must be changed on the PC.')
        active={**s.budget_active_days,key:days};caps={**s.budget_usage_limits,key:value['usage_limit']};resets={**s.budget_reset_overrides,key:value['reset_minute']}
        changes=dict(budget_active_days=active,budget_usage_limits=caps,budget_reset_overrides=resets)
        if value.get('devices') is not None:
            from .device_scopes import normalize
            changes['budget_devices']={**s.budget_devices,key:normalize(value['devices'],s,budget=True)}
        if value['scope']=='shared':changes.update(limit_seconds=seconds,warning_seconds=min(s.warning_seconds,seconds),game_budget_enabled=enabled)
        elif value['scope']=='game':changes['game_limits']={**s.game_limits,key[5:]:seconds}
        else:
            from .wellbeing import target
            rule=dict(id=key,name=value['name'],members=[target(m['kind'],m['value']) for m in value['members']],seconds=seconds,enabled=enabled,enforce=value.get('enforce',True),overlay=value.get('overlay',False))
            changes['wellbeing_rules']=[r for r in s.wellbeing_rules if r['id']!=key]+[rule]
        return replace(s,**changes).validate(),None
    raise ValueError('Unsupported remote change.')

def apply_pending(store,group,focus):
    from .statistics_sync import local_group
    initialize(store);changed=False
    for id,raw in store.db.execute("SELECT id,value FROM companion_commands WHERE group_id=? AND status='pending' ORDER BY at,id",(local_group(group),)).fetchall():
        item=json.loads(raw);status='applied';reason=''
        try:
            if abs(time.time()*1000-item['created'])>14*86400000:raise ValueError('expired')
            settings,new_focus=candidate(store,focus,item)
            with store.db:
                stored=json.loads(store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
                value=asdict(settings);value['statistics_sync_group']=stored.get('statistics_sync_group','')
                store.db.execute("UPDATE settings SET value=? WHERE key='config'",(json.dumps(value,ensure_ascii=False),))
                if new_focus:store.db.execute("INSERT OR REPLACE INTO settings VALUES ('focus_config',?)",(json.dumps(asdict(new_focus)),))
                store.db.execute('UPDATE companion_commands SET status=?,reason=? WHERE group_id=? AND id=?',(status,reason,local_group(group),id))
            if new_focus:focus.configure(new_focus)
            store.observe_preferences(settings);changed=True
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            reason='conflict' if str(error)=='conflict' else 'expired' if str(error)=='expired' else 'invalid'
            with store.db:store.db.execute("UPDATE companion_commands SET status='rejected',reason=? WHERE group_id=? AND id=?",(reason,local_group(group),id))
    return changed
