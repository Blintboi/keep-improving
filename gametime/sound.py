"""Non-blocking Windows reminder audio; failures never prevent the popup."""
import logging
import winsound

SOUNDS={'default':'SystemExclamation','information':'SystemAsterisk','error':'SystemHand'}
log=logging.getLogger(__name__)


def play_notification(settings):
    if settings.notification_sound=='silent': return True
    custom=settings.notification_sound=='custom'
    source=settings.notification_sound_path if custom else SOUNDS[settings.notification_sound]
    flags=(winsound.SND_FILENAME if custom else winsound.SND_ALIAS)|winsound.SND_ASYNC|winsound.SND_NODEFAULT
    try:
        winsound.PlaySound(source,flags); return True
    except (RuntimeError,OSError):
        log.warning('Notification sound unavailable; window remains visible')
        if custom:
            try:
                winsound.PlaySound(SOUNDS['default'],winsound.SND_ALIAS|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
                return True
            except (RuntimeError,OSError): pass
        return False
