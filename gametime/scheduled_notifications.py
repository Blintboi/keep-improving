"""Local notification triggers, queued until their complete UI can be presented."""
import math
from .tracker import Alert
from .quota import current_day
from .notification_rules import items as rule_items,validate_item,title,message,needs_interaction


def validate_notifications(items):
    if not isinstance(items,list) or len(items)>100:
        raise ValueError('Use at most 100 scheduled notifications.')
    ids=set()
    for item in items:
        validate_item(item)
        ident=item['id']
        if ident in ids:
            raise ValueError('Invalid scheduled notification.')
        ids.add(ident)
    return items


def initialize_startup(app):
    app._notification_startup_ids={item['id'] for item in rule_items(app.settings) if item['enabled'] and item['trigger']=='startup'}
    app._notification_startup_shown=set()


def triggered(app,item,current,day):
    trigger=item['trigger']
    if trigger=='time': return item['minute']==current.wall.hour*60+current.wall.minute
    if trigger=='startup': return item['id'] in app._notification_startup_ids and item['id'] not in app._notification_startup_shown
    if trigger=='pomodoros': return app.focus.completed_on(day)>=item['count']
    if trigger=='bedtime':
        from .schedule import bedtime_occurrence
        state,_,plan=bedtime_occurrence(app.settings,current.wall)
        return state=='warning' and plan.bedtime_warning_enabled and current.wall.hour*60+current.wall.minute==plan.bedtime_warning_minute
    from .budget import quota_plan
    from . import budget_access
    plan=quota_plan(app.settings,current.wall)
    if not (app.settings.game_budget_enabled and plan.limit_seconds>0 and budget_access.active(app.settings,'shared-games',current.wall)
            and budget_access.usage_enabled(app.settings,'shared-games')): return False
    total=sum(app.tracker.quota_totals(current.wall).values())
    if trigger=='warning': return plan.warning_seconds<=total<plan.limit_seconds
    return total>=plan.limit_seconds and (trigger!='session' or bool(app.tracker.identity))


def tick(app,current):
    if not hasattr(app,'_notification_startup_ids'): initialize_startup(app)
    day=current_day(app.settings,current.wall).isoformat()
    if getattr(app,'_scheduled_day',None)!=day:
        app._scheduled_day=day; app._scheduled_pending=[]
        app._scheduled_delivered=app.store.alert_keys(day)
    if getattr(app,'_notification_rule_source',None) is not app.settings:
        app._notification_rule_source=app.settings
        app._notification_rules={item['id']:item for item in rule_items(app.settings) if item['enabled']}
    rules=app._notification_rules; pending=app._scheduled_pending
    pending[:]=[entry for entry in pending if rules.get(entry[1]['id'])==entry[1]]
    queued={key for key,_ in pending}
    for item in rules.values():
        key='scheduled:'+item['id']
        if item['trigger']=='session': key+=':session:'+app.tracker.identity
        if ((item['trigger']=='startup' or key not in app._scheduled_delivered) and key not in queued
                and triggered(app,item,current,day)):
            pending.append((key,item)); queued.add(key)
    if not current.interactive or app.popup_window or not pending: return
    key,item=pending[0]
    remaining=None
    if item['template']:
        from .budget import remaining_budget
        seconds=remaining_budget(app.settings,current.wall,sum(app.tracker.quota_totals(current.wall).values())).remaining
        remaining=math.ceil(seconds/60) if math.isfinite(seconds) else app.t('No shared limit')
    alert=Alert(day,(key,),'scheduled',message(item,app.settings,remaining,day),'',title=title(item,getattr(app,'t',lambda value:value)),
                icon=item['icon'],action=item['action'],timeout=item['timeout'])
    mode=app.notification_mode()
    fullscreen=getattr(app,'fullscreen_scheduled_notification',None)
    active=getattr(app,'_fullscreen_alert',None)
    if active or mode not in ('passive','normal'):
        # Sound alone cannot convey user text; wait for an actual visual receipt.
        delivered=bool(not needs_interaction(alert) and fullscreen and fullscreen(alert,current))
    else:
        delivered=app.popup(alert)
    if delivered:
        if item['trigger']=='startup': app._notification_startup_shown.add(item['id'])
        else: app.store.mark_alert(day,(key,)); app._scheduled_delivered.add(key)
        pending.pop(0)
