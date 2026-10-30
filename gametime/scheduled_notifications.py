"""Local daily notifications, delivered once per shared accounting day."""
import ntpath
import re
from .tracker import Alert
from .quota import current_day


def validate_notifications(items):
    if not isinstance(items,list) or len(items)>100:
        raise ValueError('Use at most 100 scheduled notifications.')
    ids=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!={'id','title','text','icon','minute','enabled'}:
            raise ValueError('Invalid scheduled notification.')
        ident=item['id']
        if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{32}',ident) or ident in ids:
            raise ValueError('Invalid scheduled notification.')
        ids.add(ident)
        for key,limit in (('title',80),('text',1000),('icon',32767)):
            value=item[key]
            if not isinstance(value,str) or len(value)>limit or '\0' in value:
                raise ValueError('Invalid scheduled notification.')
        if not item['title'].strip() or not item['text'].strip():
            raise ValueError('Enter a title and message.')
        if item['icon'] and not ntpath.isabs(item['icon']):
            raise ValueError('Choose an absolute icon path.')
        if type(item['minute']) is not int or not 0<=item['minute']<1440 or type(item['enabled']) is not bool:
            raise ValueError('Invalid scheduled notification.')
    return items


def tick(app,current):
    day=current_day(app.settings,current.wall).isoformat()
    if getattr(app,'_scheduled_day',None)!=day:
        app._scheduled_day=day; app._scheduled_pending=[]
        app._scheduled_delivered=app.store.alert_keys(day)
    pending=app._scheduled_pending
    for item in app.settings.scheduled_notifications:
        key='scheduled:'+item['id']
        if item['enabled'] and item['minute']==current.wall.hour*60+current.wall.minute and key not in app._scheduled_delivered and key not in pending:
            pending.append(key)
    if not current.interactive or app.popup_window or not pending: return
    items={('scheduled:'+item['id']):item for item in app.settings.scheduled_notifications if item['enabled']}
    while pending and pending[0] not in items: pending.pop(0)
    if not pending: return
    key=pending[0]; item=items[key]
    alert=Alert(day,(key,),'scheduled',item['text'],'',title=item['title'],icon=item['icon'])
    mode=app.notification_mode()
    fullscreen=getattr(app,'fullscreen_scheduled_notification',None)
    active=getattr(app,'_fullscreen_alert',None)
    if active or mode not in ('passive','normal'):
        # Sound alone cannot convey user text; wait for an actual visual receipt.
        delivered=bool(fullscreen and fullscreen(alert,current))
    else:
        delivered=app.popup(alert)
    if delivered:
        app.store.mark_alert(day,(key,)); app._scheduled_delivered.add(key); pending.pop(0)
