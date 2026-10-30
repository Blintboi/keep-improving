"""Render game and scheduled reminders into the RTSS overlay without input hooks.

RTSS's documented image tag lets Qt render the text and icon as pixels, keeping
Unicode intact despite RTSS's ANSI text protocol. The normal per-game safety
and overlay-consent policy remains in force.
"""
import ctypes
import logging
from pathlib import Path
import tempfile
import time
from PySide6.QtCore import Qt,QRectF,QSizeF,QTimer
from PySide6.QtGui import QColor,QFont,QIcon,QImage,QPainter,QTextDocument,QTextCursor,QTextCharFormat
from . import win32
from .model import norm
from .overlay_consent import display_reason as overlay_reason
from .qt_widgets import glyph,ACCENT
from .sound import play_notification
from .notification_text import notification_presentation

log=logging.getLogger(__name__)
WIDTH,HEIGHT=620,400
BODY_TOP,BODY_HEIGHT=119,255
PAGE_SECONDS=10


def ansi_path(path):
    """RTSS parses the image-tag path as ANSI; use a short path when needed."""
    path=str(path)
    try: path.encode('ascii')
    except UnicodeEncodeError:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        func=kernel.GetShortPathNameW
        func.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32]; func.restype=ctypes.c_uint32
        buf=ctypes.create_unicode_buffer(32768)
        length=func(path,buf,len(buf))
        if not length or length>=len(buf): raise ValueError('RTSS image path cannot be represented safely.')
        path=buf.value
        try: path.encode('ascii')
        except UnicodeEncodeError: raise ValueError('RTSS image path cannot be represented safely.')
    if any(ch in path for ch in '"<>\r\n') or len(path)>3000: raise ValueError('Invalid RTSS image path.')
    return path


class FullscreenNotification:
    def __init__(self,app,alert,current):
        self.app,self.alert=app,alert
        self.path,self.identity=current.path,current.identity
        self.directory=tempfile.TemporaryDirectory(prefix='gtm-notice-')
        self.document=QTextDocument(); self.document.setDocumentMargin(0)
        self.document.setDefaultFont(QFont('Segoe UI',15))
        self.document.setPlainText(alert.text)
        cursor=QTextCursor(self.document); cursor.select(QTextCursor.Document)
        style=QTextCharFormat(); style.setForeground(QColor('#edf4f2')); cursor.mergeCharFormat(style)
        self.document.setPageSize(QSizeF(WIDTH-48,BODY_HEIGHT))
        self.pages=max(1,self.document.pageCount()); self.page=0
        self.visible_since=None; self.started=False; self.confirmed=False; self.closing=False
        self.render_page()
        self.timer=QTimer(app); self.timer.setInterval(250); self.timer.timeout.connect(self.tick); self.timer.start()

    def render_page(self):
        # RTSS loads its sprite atlas as a square power-of-two texture.
        image=QImage(1024,1024,QImage.Format_ARGB32_Premultiplied); image.fill(Qt.transparent)
        painter=QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor('#445950')); painter.setBrush(QColor('#172228'))
        painter.drawRoundedRect(QRectF(1,1,WIDTH-2,HEIGHT-2),16,16)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#284c3c')); painter.drawRoundedRect(QRectF(20,20,54,54),12,12)
        _,heading,icon_name=notification_presentation(self.alert,self.app.t)
        icon=QIcon(self.alert.icon) if self.alert.icon else QIcon()
        if icon.isNull(): icon=glyph(icon_name,ACCENT,30)
        icon.paint(painter,29,29,36,36)
        painter.setPen(QColor('#edf4f2')); title_font=QFont('Segoe UI',19,QFont.Bold); painter.setFont(title_font)
        painter.drawText(QRectF(89,18,WIDTH-114,85),Qt.AlignLeft|Qt.AlignVCenter|Qt.TextWordWrap,heading)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#1d2d31')); painter.drawRoundedRect(QRectF(16,109,WIDTH-32,HEIGHT-125),10,10)
        painter.save(); painter.setClipRect(QRectF(24,BODY_TOP,WIDTH-48,BODY_HEIGHT)); painter.translate(24,BODY_TOP-self.page*BODY_HEIGHT)
        self.document.drawContents(painter,QRectF(0,self.page*BODY_HEIGHT,WIDTH-48,BODY_HEIGHT)); painter.restore()
        if self.pages>1:
            painter.setPen(QColor('#a6bdb4')); painter.setFont(QFont('Segoe UI',9)); painter.drawText(QRectF(25,HEIGHT-28,WIDTH-50,18),Qt.AlignRight,f'{self.page+1} / {self.pages}')
        painter.end()
        path=Path(self.directory.name)/f'notice-{self.page}.png'
        if not image.save(str(path),'PNG'): raise OSError('Could not create notification image.')
        safe=ansi_path(path)
        self.text=f'<LI="{safe}"><I={WIDTH},{HEIGHT},0,0,{WIDTH},{HEIGHT}>'

    def tick(self):
        try:
            if self.closing:
                if self.app.rtss.desktop_ready: self.cleanup()
                return
            current=win32.sample()
            game=self.app.catalog.resolve(current.path)
            if (self.app.closed or not current.interactive or current.identity!=self.identity
                    or norm(current.path)!=norm(self.path) or not game
                    or overlay_reason(self.app.catalog,current.path,game)):
                self.finish(); return
            if time.monotonic()<getattr(self.app,'_overlay_desktop_until',0): return
            healthy=self.app.rtss.present(self.path,self.identity,self.text,require_current=True,
                                          retry=self.app.rtss.retry_due(self.identity))
            if healthy:
                if self.visible_since is None:
                    self.visible_since=time.monotonic()
                    if not self.started:
                        self.started=True
                        if self.alert.sound: play_notification(self.app.settings)
                    if self.page==self.pages-1: self.confirmed=True
                if time.monotonic()-self.visible_since>=PAGE_SECONDS:
                    if self.page+1>=self.pages: self.finish(); return
                    self.page+=1; self.visible_since=None; self.render_page()
            elif self.app.rtss.fallback_for(self.identity): self.finish()
        except Exception:
            log.exception('Fullscreen notification failed'); self.finish()

    def finish(self):
        if self.closing: return
        self.closing=True; self.app.rtss.hide()

    def cleanup(self):
        self.timer.stop(); self.timer.deleteLater()
        try: self.directory.cleanup()
        except OSError: log.warning('Could not remove temporary notification image',exc_info=True)
        if getattr(self.app,'_fullscreen_alert',None) is self:
            self.app._fullscreen_alert=None
            if not self.app.closed: self.app.update_overlay()

    def shutdown(self):
        self.timer.stop(); self.app.rtss.hide()
        self.cleanup()


def present(app,alert,current):
    active=getattr(app,'_fullscreen_alert',None)
    if active:
        return (active.alert==alert and active.confirmed and not active.closing and current.interactive
                and active.identity==current.identity and norm(active.path)==norm(current.path))
    prior=getattr(app,'_fullscreen_retry',None); now=time.monotonic()
    if prior and prior[0]==alert and prior[1]==current.identity and now-prior[2]<30: return False
    app._fullscreen_retry=(alert,current.identity,now)
    if not current.interactive or not current.identity or not app.settings.overlay_rtss_auto or not app.rtss_available(): return False
    game=app.catalog.resolve(current.path)
    if not game or overlay_reason(app.catalog,current.path,game): return False
    if app.rtss.fallback_for(current.identity) and not app.rtss.retry_due(current.identity): return False
    try:
        if app.overlay_consents.display_enabled and norm(current.path) not in app._rtss_consent_paths:
            app.refresh_rtss_consent((current.path,))
        if app.overlay and app.overlay.isVisible():
            app.overlay.hide(); app._overlay_desktop_until=now+.2
        app._fullscreen_alert=FullscreenNotification(app,alert,current)
        return False
    except (OSError,ValueError,RuntimeError):
        log.warning('Could not prepare fullscreen notification',exc_info=True)
        return False
