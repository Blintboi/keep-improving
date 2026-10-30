"""Non-activating, click-through desktop countdown and its in-Hub position editor."""
import ctypes as C
import logging
import math
import time
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
from . import win32
from .model import hex_color

log = logging.getLogger(__name__)
win32.api(win32.u, "ShowWindow", [win32.W.HWND, C.c_int], win32.W.BOOL)
EX_FLAGS = 0x80000 | 0x20 | 0x08000000 | 0x80  # Layered, transparent, no activate, tool.
get_style = win32.api(win32.u, "GetWindowLongPtrW", [win32.W.HWND, C.c_int], C.c_ssize_t)
set_style = win32.api(win32.u, "SetWindowLongPtrW", [win32.W.HWND, C.c_int, C.c_ssize_t], C.c_ssize_t)


class MonitorInfo(C.Structure):
    _fields_ = [("size", win32.W.DWORD), ("monitor", win32.W.RECT),
                ("work", win32.W.RECT), ("flags", win32.W.DWORD),
                ("device", win32.W.WCHAR * 32)]


monitor_from_window = win32.api(win32.u, "MonitorFromWindow",
                               [win32.W.HWND, win32.W.DWORD], win32.W.HANDLE)
monitor_info = win32.api(win32.u, "GetMonitorInfoW",
                        [win32.W.HANDLE, C.POINTER(MonitorInfo)], win32.W.BOOL)


def foreground_screen_name():
    monitor = monitor_from_window(win32.u.GetForegroundWindow(), 2)
    info = MonitorInfo()
    info.size = C.sizeof(info)
    return info.device if monitor and monitor_info(monitor, C.byref(info)) else ""


def screen_device(screen):
    r"""Match Qt's friendly display name to the Win32 capture/foreground device.

    QScreen.name() may be a monitor model (Qt 6.12), not \\.\DISPLAY1.
    Use its native HMONITOR; names and logical/DPI-scaled geometry are not IDs.
    """
    info = MonitorInfo(); info.size = C.sizeof(info)
    try:
        native = screen.nativeInterface()
        handle = native.handle() if native else None
        if handle and monitor_info(handle, C.byref(info)):
            return info.device
    except (AttributeError, RuntimeError, TypeError):
        pass  # A disconnected screen can disappear during a display change.
    return screen.name()


def screen_matches(screen, name):
    return bool(name) and (name.casefold() == screen.name().casefold()
                           or name.casefold() == screen_device(screen).casefold())


def choose_screen(name="", automatic_name=""):
    screens = QApplication.screens()
    wanted = name or automatic_name
    return next((screen for screen in screens if screen_matches(screen, wanted)),
                QApplication.primaryScreen())


def placement(area, size, x, y, margin=16):
    """Normalized coordinates survive resolution, DPI and monitor changes."""
    left = area.x() + min(margin, max(0, (area.width()-size.width())//2))
    top = area.y() + min(margin, max(0, (area.height()-size.height())//2))
    width = max(0, area.width()-size.width()-2*(left-area.x()))
    height = max(0, area.height()-size.height()-2*(top-area.y()))
    return left + round(width*x), top + round(height*y)


def countdown_font(point_size):
    font=QFont('Consolas',25,QFont.Bold); font.setPointSizeF(point_size)
    return font


def countdown_size(point_size,device=None):
    metrics=QFontMetrics(countdown_font(point_size),device)
    return QSize(metrics.horizontalAdvance('00:00:00')+4,metrics.height()+4)


class CountdownOverlay(QWidget):
    def __init__(self, owner):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint |
                         Qt.WindowStaysOnTopHint | Qt.WindowTransparentForInput |
                         Qt.WindowDoesNotAcceptFocus)
        self.owner = owner  # Deliberately not a Qt parent: a hidden Hub must not hide the HUD.
        self.setObjectName("CountdownOverlay")
        self.setWindowTitle("Gaming Hub countdown")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.NoFocus)
        self.font_size=25
        self.timer_font=countdown_font(self.font_size)
        self.setFixedSize(countdown_size(self.font_size,self))
        self.seconds = 0
        self.warning = False
        self.preview = False
        self.opacity = .72
        self.color='#ffffff'
        self._raised_at = 0
        self._native_styles()

    def _native_styles(self):
        hwnd = int(self.winId())
        style = get_style(hwnd, -20)
        if style & EX_FLAGS != EX_FLAGS:
            C.set_last_error(0)
            set_style(hwnd, -20, style | EX_FLAGS)
            if get_style(hwnd, -20) & EX_FLAGS != EX_FLAGS:
                raise OSError("Could not make the countdown non-interactive")
        return hwnd

    def present(self, remaining, total, settings, screen, preview=False, warning=None):
        font_state=(settings.overlay_font_size,self.logicalDpiY())
        if getattr(self,'_font_state',None)!=font_state:
            self._font_state=font_state; self.font_size=settings.overlay_font_size
            self.timer_font=countdown_font(self.font_size)
            self.setFixedSize(countdown_size(self.font_size,self)); self.update()
        if warning is None: warning=total>=settings.warning_seconds
        color=hex_color(settings.overlay_color_warning if warning else settings.overlay_color_normal)
        state = (max(0, math.ceil(remaining)), warning, preview, settings.overlay_opacity,color)
        if getattr(self, "_state", None) != state:
            self._state = state
            self.seconds, self.warning, self.preview, self.opacity,self.color = state
            self.update()
        self.move(*placement(screen.geometry(), self.size(),
                             settings.overlay_x, settings.overlay_y))
        newly_visible = not self.isVisible()
        if newly_visible:
            self.show()  # All Qt focus/input suppression flags are set before the first show.
        hwnd = self._native_styles()
        now = time.monotonic()
        if newly_visible or now-self._raised_at >= 1:
            # ShowWindow's first call can inherit SW_HIDE from Windows startup.
            # Neither this call nor SetWindowPos activates or focuses the HUD.
            win32.u.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            if not win32.u.SetWindowPos(hwnd, win32.W.HWND(-1), 0, 0, 0, 0, 0x53):
                raise OSError("Could not display the countdown")
            self._raised_at = now

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(self.color)
        color.setAlphaF(self.opacity)
        painter.setPen(color)
        seconds = self.seconds
        text = f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}"
        painter.setFont(self.timer_font)
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class PositionPicker(QWidget):
    positionChanged = Signal(float, float)

    def __init__(self, x, y, screen, font_size=25):
        super().__init__()
        self.x_ratio, self.y_ratio = x, y
        self.screen = screen
        self.font_size=font_size
        self.text_color='#ffffff'
        self.game_background=None
        self.dragging = False
        self.offset = QPointF()
        self.setMinimumHeight(200)
        self.setMaximumHeight(240)
        self.setMinimumWidth(320)
        self.setCursor(Qt.ArrowCursor)
        self.setProperty('dynamicCursor',True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Countdown position")

    def _bounds(self, monitor):
        geometry=self.screen.geometry(); size=self.hud_size()
        margin_x=min(16,max(0,(geometry.width()-size.width())//2))*monitor.width()/max(1,geometry.width())
        margin_y=min(16,max(0,(geometry.height()-size.height())//2))*monitor.height()/max(1,geometry.height())
        return monitor.adjusted(margin_x, margin_y, -margin_x, -margin_y)

    def hud_size(self):
        key=(self.font_size,self.logicalDpiY())
        if getattr(self,'_size_key',None)!=key:
            self._size_key=key; self._hud_size=countdown_size(self.font_size,self)
        return self._hud_size

    def pixel_limits(self):
        geometry=self.screen.geometry(); size=self.hud_size()
        low=placement(geometry,size,0,0); high=placement(geometry,size,1,1)
        return (low[0]-geometry.x(),high[0]-geometry.x()),(low[1]-geometry.y(),high[1]-geometry.y())

    def pixel_position(self):
        geometry=self.screen.geometry()
        x,y=placement(geometry,self.hud_size(),self.x_ratio,self.y_ratio)
        return x-geometry.x(),y-geometry.y()

    def set_pixel_position(self,x,y):
        limits=self.pixel_limits(); current=self.pixel_position()
        ratios=[self.x_ratio,self.y_ratio]
        for axis,value in enumerate((x,y)):
            low,high=limits[axis]; value=max(low,min(high,value))
            if value!=current[axis]: ratios[axis]=(value-low)/max(1,high-low)
        self.set_position(*ratios)

    def set_font_size(self,value):
        if self.font_size!=value: self.font_size=value; self.update()

    def rectangles(self):
        geometry = self.screen.geometry()
        ratio = geometry.width()/max(1, geometry.height())
        width = min(self.width()-8, (self.height()-8)*ratio)
        height = width/ratio
        monitor = QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)
        scale=width/max(1,geometry.width()); size=self.hud_size(); x,y=self.pixel_position()
        hud=QRectF(monitor.x()+x*scale,monitor.y()+y*scale,size.width()*scale,size.height()*scale)
        return monitor, hud

    def set_position(self, x, y):
        x,y=max(0,min(1,x)),max(0,min(1,y))
        if (x,y)==(self.x_ratio,self.y_ratio): return
        self.x_ratio,self.y_ratio=x,y
        self.positionChanged.emit(self.x_ratio, self.y_ratio)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        monitor, hud = self.rectangles()
        painter.setPen(QPen(QColor("#3c575b"), 1))
        painter.setBrush(QColor("#101c23"))
        painter.drawRoundedRect(monitor, 10, 10)
        if self.game_background and screen_matches(self.screen, self.game_background[1]):
            image,_,(x,y,width,height)=self.game_background
            painter.save(); painter.setClipRect(monitor.adjusted(1,1,-1,-1)); painter.setOpacity(.42)
            painter.drawImage(QRectF(monitor.x()+x*monitor.width(),monitor.y()+y*monitor.height(),width*monitor.width(),height*monitor.height()),image)
            painter.restore()
        painter.setPen(QPen(QColor("#1d3037"), 1, Qt.DotLine))
        painter.drawLine(QPointF(monitor.center().x(), monitor.top()+6),
                         QPointF(monitor.center().x(), monitor.bottom()-6))
        painter.drawLine(QPointF(monitor.left()+6, monitor.center().y()),
                         QPointF(monitor.right()-6, monitor.center().y()))
        backdrop=QColor(245,248,250,215) if QColor(self.text_color).lightness()<105 else QColor(0,0,0,190)
        painter.setPen(QPen(QColor('#7de5bf'),1)); painter.setBrush(backdrop if self.game_background else QColor(125,229,191,25))
        painter.drawRect(hud)
        painter.setPen(QColor(self.text_color))
        scale=monitor.width()/max(1,self.screen.geometry().width())
        painter.setFont(countdown_font(max(1,self.font_size*scale)))
        painter.setClipRect(hud)
        painter.drawText(hud, Qt.AlignCenter, '00:20:00')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            monitor, hud = self.rectangles()
            if not monitor.contains(event.position()):
                event.ignore()
                return
            self.offset = event.position()-hud.topLeft() if hud.contains(event.position()) else QPointF(hud.width()/2, hud.height()/2)
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            self._move(event.position())
            event.accept()

    def _move(self, point):
        monitor, hud = self.rectangles()
        bounds = self._bounds(monitor)
        self.set_position((point.x()-self.offset.x()-bounds.x())/max(1, bounds.width()-hud.width()),
                          (point.y()-self.offset.y()-bounds.y())/max(1, bounds.height()-hud.height()))

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._move(event.position())
        else:
            monitor, _ = self.rectangles()
            self.setCursor(Qt.OpenHandCursor if monitor.contains(event.position()) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        monitor, _ = self.rectangles()
        self.setCursor(Qt.OpenHandCursor if monitor.contains(event.position()) else Qt.ArrowCursor)

    def keyPressEvent(self, event):
        changes = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
                   Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if event.key() in changes:
            dx,dy=changes[event.key()]; step=10 if event.modifiers() & Qt.ShiftModifier else 1
            x,y=self.pixel_position(); self.set_pixel_position(x+dx*step,y+dy*step)
        else:
            super().keyPressEvent(event)
