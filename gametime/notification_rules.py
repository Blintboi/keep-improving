"""Shared notification fields; legacy reminders are editable presets, not UI types."""
from dataclasses import replace
import ntpath
import re
import uuid
from .notification_text import KINDS,default_notification_template,notification_text

TITLES=dict(zip(KINDS,('Before the daily limit','Daily limit reached','Playing again after the limit','Bedtime reminder')))
TRIGGERS={'time':'At a time of day','startup':'When Keep Improving starts','pomodoros':'After daily Pomodoro count',**TITLES}
ICONS={'bell':'Reminder','clock':'Time','focus':'Pomodoro','moon':'Rest','water':'Water','book':'Reading','stretch':'Movement','check':'Completed','heart':'Health','star':'Goal'}
POMODORO={'work':25,'short_break':5,'long_break':15,'rounds':4}
BUILTIN_IDS={kind:uuid.uuid5(uuid.NAMESPACE_URL,'keep-improving/notification/'+kind).hex for kind in KINDS}


def normalized(item):
    return {'trigger':'time','count':4,'action':{'kind':'none'},'timeout':None,'template':'','days':list(range(7)),**item}


def builtin(settings,kind):
    if kind in settings.notification_overrides: return dict(settings.notification_overrides[kind])
    if kind in settings.removed_notifications: return None
    return dict(id=BUILTIN_IDS[kind],title='',text=settings.notification_messages.get(kind,''),
                icon='preset:moon' if kind=='bedtime' else 'preset:bell',minute=settings.bedtime_warning_minute if kind=='bedtime' else 720,
                enabled=True,trigger=kind,count=4,action={'kind':'none'},timeout=None,template=kind)


def items(settings):
    return [normalized(item) for item in [*settings.scheduled_notifications,*settings.notification_overrides.values()]]


def executable(value):
    if (not isinstance(value,str) or len(value)>32767 or '\0' in value or
            not re.match(r'^[A-Za-z]:[\\/]',value) or ntpath.splitext(value)[1].lower()!='.exe'):
        raise ValueError('Choose a local Windows application (.exe).')
    return value


def validate_action(action):
    if not isinstance(action,dict): raise ValueError('Invalid notification button.')
    kind=action.get('kind')
    if kind=='none' and set(action)=={'kind'}: return
    if kind=='app' and set(action)=={'kind','path'}: executable(action['path']); return
    if kind=='pomodoro' and set(action)=={'kind',*POMODORO}:
        from .focus import FocusSettings
        FocusSettings(**{key:action[key] for key in POMODORO}).validate(); return
    raise ValueError('Invalid notification button.')


def validate_item(item):
    required={'id','title','text','icon','minute','enabled'}
    if not isinstance(item,dict) or not required<=set(item) or set(item)-required-{'trigger','count','action','timeout','template','devices','days'}:
        raise ValueError('Invalid notification.')
    rule=normalized(item)
    from .device_scopes import validate as validate_scope
    validate_scope(rule.get('devices'))
    days=rule['days']
    if not isinstance(days,list) or any(type(d) is not int or not 0<=d<7 for d in days) or len(set(days))!=len(days):raise ValueError('Choose distinct weekdays.')
    if not isinstance(rule['id'],str) or not re.fullmatch('[0-9a-f]{32}',rule['id']): raise ValueError('Invalid notification.')
    for key,limit in (('title',80),('text',1000),('icon',32767)):
        if not isinstance(rule[key],str) or len(rule[key])>limit or '\0' in rule[key]: raise ValueError('Invalid notification.')
    if (not isinstance(rule['template'],str) or not isinstance(rule['trigger'],str) or
            rule['template'] not in ('',*KINDS) or rule['trigger'] not in TRIGGERS): raise ValueError('Invalid notification trigger.')
    if (not rule['title'].strip() or not rule['text'].strip()) and not rule['template']: raise ValueError('Enter a title and message.')
    icon=rule['icon']
    if icon and icon not in {'preset:'+name for name in ICONS} and not ntpath.isabs(icon): raise ValueError('Choose an absolute icon path.')
    if type(rule['minute']) is not int or not 0<=rule['minute']<1440 or type(rule['enabled']) is not bool: raise ValueError('Invalid notification.')
    if type(rule['count']) is not int or not 1<=rule['count']<=1000: raise ValueError('Choose a Pomodoro count from 1 to 1000.')
    if rule['timeout'] is not None and (type(rule['timeout']) is not int or not 0<=rule['timeout']<=3600):
        raise ValueError('Choose a duration from 1 to 3600 seconds, or manual closing.')
    validate_action(rule['action'])


def title(rule,t): return rule['title'] or t(TITLES.get(rule.get('template'),'New notification'))


def message(rule,settings,remaining=None,day=None):
    template=rule.get('template')
    if not template: return rule['text']
    return notification_text(replace(settings,notification_messages={template:rule['text']}),template,remaining,day=day)


def validate_files(rule):
    from pathlib import Path
    if rule['icon'] and not rule['icon'].startswith('preset:') and not Path(rule['icon']).is_file(): raise ValueError('Icon file was not found.')
    action=rule.get('action',{})
    if action.get('kind')=='app' and not Path(executable(action['path'])).is_file(): raise ValueError('Application file was not found.')


def needs_interaction(alert): return alert.timeout==0 or bool(alert.action and alert.action.get('kind')!='none')
