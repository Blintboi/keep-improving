"""Per-rule computer selection; missing selectors retain legacy local behavior."""
import hashlib
import re
from functools import lru_cache

IDENTITY=re.compile(r'[0-9a-f]{32}')

@lru_cache(maxsize=64)
def connection(code):
    return 'local-v1:'+hashlib.sha256(('GameTimeMonitor/local-group/v1\0'+code).encode()).hexdigest() if code else ''

def validate(scope):
    if scope is None:return
    if not isinstance(scope,dict) or scope.get('mode') not in ('device','group','all'):raise ValueError('Choose a computer or computer group.')
    allowed={'mode','connection','accounting'}|({'device'} if scope['mode']=='device' else {'group'} if scope['mode']=='group' else set())
    if set(scope)-allowed:raise ValueError('Invalid computer selection.')
    if scope['mode']!='all' and (not isinstance(scope.get(scope['mode']),str) or not IDENTITY.fullmatch(scope[scope['mode']])):raise ValueError('Choose a computer or computer group.')
    if 'connection' in scope and (not isinstance(scope['connection'],str) or not re.fullmatch('local-v1:[0-9a-f]{64}',scope['connection'])):raise ValueError('Invalid computer connection.')
    if scope.get('accounting','separate') not in ('shared','separate'):raise ValueError('Choose shared or per-computer usage.')

def validate_groups(groups):
    if not isinstance(groups,dict) or len(groups)>64:raise ValueError('Use at most 64 computer groups.')
    for identity,group in groups.items():
        if not isinstance(identity,str) or not IDENTITY.fullmatch(identity) or not isinstance(group,dict) or set(group)!={'name','devices','connection'}:raise ValueError('Invalid computer group.')
        if not isinstance(group['name'],str) or not group['name'].strip() or len(group['name'])>80 or '\0' in group['name']:raise ValueError('Give the computer group a name.')
        devices=group['devices']
        if not isinstance(devices,list) or len(devices)>20 or any(not isinstance(d,str) or not IDENTITY.fullmatch(d) for d in devices) or len(devices)!=len(set(devices)):raise ValueError('Choose up to 20 distinct computers.')
        validate(dict(mode='all',connection=group['connection']))

def applies(scope,settings,device=None):
    if scope is None:return True
    local=device or settings.scope_device
    if scope.get('connection') and scope['connection']!=connection(settings.statistics_sync_group):return False
    if scope['mode']=='all':return True
    if scope['mode']=='device':return local==scope['device']
    group=settings.device_groups.get(scope['group'],{})
    return group.get('connection')==connection(settings.statistics_sync_group) and local in group.get('devices',())

def budget(settings,key):return settings.budget_devices.get(key)

def notification(settings,rule):return applies(rule.get('devices'),settings)

def normalize(scope,settings,*,budget=False):
    scope=dict(scope or dict(mode='device',device=settings.scope_device))
    if settings.statistics_sync_group:scope['connection']=connection(settings.statistics_sync_group)
    if budget:scope['accounting']='shared'
    validate(scope)
    return scope
