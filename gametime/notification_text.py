"""Local reminder text. User messages stay literal apart from named time tokens."""
import math
import re
from .bedtime import clock_text
from .i18n import tr
from .schedule import day_settings

KINDS=('warning','limit','session','bedtime')
MAX_MESSAGE_LENGTH=1000


def notification_presentation(alert,t):
    """One title/icon choice for desktop and fullscreen rendering."""
    caption=alert.title or t('Bedtime reminder' if alert.kind=='bedtime' else 'Time budget reminder' if alert.kind=='wellbeing' else 'Game time alert')
    heading=alert.title or t('Get ready for bed' if alert.kind=='bedtime' else 'Time for a break' if alert.kind=='wellbeing' else 'Time to stop playing' if alert.kind in ('limit','session') else 'Game time reminder')
    return caption,heading,'moon' if alert.kind=='bedtime' else 'bell'


def default_notification_template(settings,kind,test=False):
    """Editable, localized defaults with live time tokens left intact."""
    if kind not in KINDS: raise ValueError('Unknown notification kind.')
    minutes=settings.limit_seconds/60
    if kind=='warning': key='You have {remaining} minutes of game time left today.'
    elif kind=='session': key='Your daily game time limit has already been reached. Time to finish playing.'
    elif kind=='bedtime': key='It is {time}. Finish what you are doing and get ready for bed at {bedtime}.'
    elif test: key='Test: Your daily game time limit has been reached. Time to finish playing.'
    else: key=('Your daily 2-hour game time limit has been reached. Time to finish playing.' if minutes==120 else
               'Your daily {minutes:g}-minute game time limit has been reached. Time to finish playing.')
    return tr(key,settings.language).replace('{minutes:g}','{minutes}')


def notification_text(settings,kind,remaining=None,test=False,day=None):
    settings=day_settings(settings,day)
    default=default_notification_template(settings,kind,test)
    minutes=settings.limit_seconds/60
    if remaining is None: remaining=0 if kind in ('limit','session') else math.ceil((settings.limit_seconds-settings.warning_seconds)/60)
    values={'remaining':str(remaining),
            'minutes':f'{minutes:g}','time':clock_text(settings.bedtime_warning_minute),'bedtime':clock_text(settings.bedtime_minute)}
    custom=settings.notification_messages.get(kind,'')
    # Substitute only exact known tokens, once. Braces, markup and unknown
    # tokens are ordinary text, never Python format expressions or HTML.
    return re.sub(r'\{(remaining|minutes|time|bedtime)\}',lambda match:values[match[1]],custom if custom.strip() else default)
