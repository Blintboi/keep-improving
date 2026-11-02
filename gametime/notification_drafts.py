"""Notification edits are local drafts until Save changes; budgets are untouched."""
from copy import deepcopy
from dataclasses import replace
import json
import re
from .notification_text import KINDS

KEY='notification_editor_draft_v1'


def original(settings,key):
    if key.startswith('builtin:'):
        kind=key.split(':',1)[1]
        from .notification_rules import builtin
        return builtin(settings,kind)
    return next((dict(item) for item in settings.scheduled_notifications if 'scheduled:'+item['id']==key),None)


def apply(settings,changes):
    scheduled={item['id']:dict(item) for item in settings.scheduled_notifications}
    messages=dict(settings.notification_messages); removed=set(settings.removed_notifications)
    overrides=deepcopy(settings.notification_overrides)
    for key,item in changes.items():
        group,ident=key.split(':',1)
        if group=='builtin':
            if item is None:
                removed.add(ident); messages.pop(ident,None); overrides.pop(ident,None)
            elif set(item)=={'text'}:  # Recover drafts saved by earlier versions.
                if ident not in overrides: removed.discard(ident)
                if item['text'].strip(): messages[ident]=item['text']
                else: messages.pop(ident,None)
                if ident in overrides: overrides[ident]['text']=item['text']
            else:
                overrides[ident]=deepcopy(item); removed.add(ident)
        elif item is None: scheduled.pop(ident,None)
        else: scheduled[ident]=dict(item)
    return replace(settings,scheduled_notifications=list(scheduled.values()),notification_messages=messages,
                   notification_overrides=overrides,removed_notifications=[kind for kind in KINDS if kind in removed])


def read(store):
    row=store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
    if not row: return {}
    try:
        changes=json.loads(row[0])
        if not isinstance(changes,dict) or len(changes)>204: return {}
        for key,item in changes.items():
            if not (key in {'builtin:'+kind for kind in KINDS} or re.fullmatch(r'scheduled:[0-9a-f]{32}',key)): return {}
            if item is None: continue
            if not isinstance(item,dict) or not isinstance(item.get('text'),str) or len(item['text'])>100000: return {}
            if key.startswith('builtin:'):
                if set(item)=={'text'}: continue
            if item is not None:
                from .scheduled_notifications import validate_notifications
                # Incomplete title/message is a legitimate unapplied draft.
                if not isinstance(item.get('title'),str) or len(item['title'])>80 or not isinstance(item.get('icon'),str) or len(item['icon'])>32767: return {}
                # Unselected application paths are valid unapplied drafts too.
                from .notification_rules import validate_action
                action=item.get('action',{'kind':'none'})
                if isinstance(action,dict) and action.get('kind')=='app':
                    if set(action)!={'kind','path'} or not isinstance(action['path'],str) or len(action['path'])>32767: return {}
                elif isinstance(action,dict) and action.get('kind')=='pomodoro' and type(action.get('work')) is int and action['work']==0:
                    validate_action(dict(action,work=1))  # Preserve an incomplete duration until Save validates it.
                else: validate_action(action)
                validate_notifications([dict(item,title='Draft',text='Draft',icon='',action={'kind':'none'})])
                from .notification_rules import BUILTIN_IDS
                expected=BUILTIN_IDS[key.split(':',1)[1]] if key.startswith('builtin:') else key.split(':',1)[1]
                if item['id']!=expected: return {}
        return changes
    except (ValueError,TypeError,KeyError): return {}


def write(store,changes):
    raw=json.dumps(changes,ensure_ascii=False,sort_keys=True,separators=(',',':')) if changes else None
    row=store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
    if raw==(row[0] if row else None): return
    with store.db:
        if raw is None: store.db.execute('DELETE FROM settings WHERE key=?',(KEY,))
        else: store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(KEY,raw))


def update(changes,settings,key,value):
    if value==original(settings,key): changes.pop(key,None)
    else: changes[key]=deepcopy(value)
