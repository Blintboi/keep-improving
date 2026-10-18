"""Non-activating, click-through desktop countdown and its in-Hub position editor."""
import ctypes as C
import logging
import math
import time
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget
from . import win32

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


def choose_screen(name="", automatic_name=""):
    screens = QApplication.screens()
    wanted = name or automatic_name
    return next((screen for screen in screens if screen.name() == wanted),
                QApplication.primaryScreen())


def placement(area, size, x, y, margin=16):
    """Normalized coordinates survive resolution, DPI and monitor changes."""
    left = area.x() + min(margin, max(0, (area.width()-size.width())//2))
    top = area.y() + min(margin, max(0, (area.height()-size.height())//2))
    width = max(0, area.width()-size.width()-2*(left-area.x()))
    height = max(0, area.height()-size.height()-2*(top-area.y()))
    return left + round(width*x), top + round(height*y)


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
        self.timer_font = QFont("Consolas", 25, QFont.Bold)
        metrics = QFontMetrics(self.timer_font, self)
        self.setFixedSize(metrics.horizontalAdvance("00:00:00")+4, metrics.height()+4)
        self.seconds = 0
        self.warning = False
        self.preview = False
        self.opacity = .72
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

    def present(self, remaining, total, settings, screen, preview=False):
        state = (max(0, math.ceil(remaining)), total >= settings.warning_seconds, preview, settings.overlay_opacity)
        if getattr(self, "_state", None) != state:
            self._state = state
            self.seconds, self.warning, self.preview, self.opacity = state
            self.update()
        self.move(*placement(screen.availableGeometry(), self.size(),
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
        color = QColor("#ff5c65" if self.warning else "#ffffff")
        color.setAlphaF(self.opacity)
        painter.setPen(color)
        seconds = self.seconds
        text = f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}"
        painter.setFont(self.timer_font)
        painter.drawText(self.rect(), Qt.AlignCenter, text)


class PositionPicker(QWidget):
    positionChanged = Signal(float, float)

    def __init__(self, x, y, screen):
        super().__init__()
        self.x_ratio, self.y_ratio = x, y
        self.screen = screen
        self.dragging = False
        self.offset = QPointF()
        self.setMinimumHeight(168)
        self.setMaximumHeight(210)
        self.setMinimumWidth(320)
        self.setCursor(Qt.OpenHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Countdown position")

    def rectangles(self):
        geometry = self.screen.availableGeometry()
        ratio = geometry.width()/max(1, geometry.height())
        width = min(self.width()-8, (self.height()-8)*ratio)
        height = width/ratio
        monitor = QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)
        hud_width = min(88, width*.40)
        hud = QRectF(monitor.x()+8+(width-hud_width-16)*self.x_ratio,
                     monitor.y()+8+(height-38)*self.y_ratio, hud_width, 22)
        return monitor, hud

    def set_position(self, x, y):
        self.x_ratio, self.y_ratio = max(0, min(1, x)), max(0, min(1, y))
        self.positionChanged.emit(self.x_ratio, self.y_ratio)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        monitor, hud = self.rectangles()
        painter.setPen(QPen(QColor("#3c575b"), 1))
        painter.setBrush(QColor("#101c23"))
        painter.drawRoundedRect(monitor, 10, 10)
        painter.setPen(QPen(QColor("#1d3037"), 1, Qt.DotLine))
        painter.drawLine(QPointF(monitor.center().x(), monitor.top()+6),
                         QPointF(monitor.center().x(), monitor.bottom()-6))
        painter.drawLine(QPointF(monitor.left()+6, monitor.center().y()),
                         QPointF(monitor.right()-6, monitor.center().y()))
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.drawText(hud, Qt.AlignCenter, "00:20:00" if hud.width()>=80 else "20:00")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            _, hud = self.rectangles()
            self.offset = event.position()-hud.topLeft() if hud.contains(event.position()) else QPointF(hud.width()/2, hud.height()/2)
            self.dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            self._move(event.position())
            event.accept()

    def _move(self, point):
        monitor, hud = self.rectangles()
        self.set_position((point.x()-self.offset.x()-monitor.x()-8)/max(1, monitor.width()-hud.width()-16),
                          (point.y()-self.offset.y()-monitor.y()-8)/max(1, monitor.height()-hud.height()-16))

    def mouseMoveEvent(self, event):
        if self.dragging:
            self._move(event.position())

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.setCursor(Qt.OpenHandCursor)

    def keyPressEvent(self, event):
        changes = {Qt.Key_Left: (-.02, 0), Qt.Key_Right: (.02, 0),
                   Qt.Key_Up: (0, -.02), Qt.Key_Down: (0, .02)}
        if event.key() in changes:
            dx, dy = changes[event.key()]
            self.set_position(self.x_ratio+dx, self.y_ratio+dy)
        else:
            super().keyPressEvent(event)
