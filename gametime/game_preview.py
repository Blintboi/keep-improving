"""On-demand, game-window-only snapshots and explicit preview activation."""
from dataclasses import dataclass,field
import ctypes as C
import os
from queue import SimpleQueue,Empty
import threading
from PySide6.QtCore import QObject,QTimer,Signal,Qt
from PySide6.QtGui import QImage
from . import win32
from .overlay import MonitorInfo,monitor_from_window,monitor_info
from .model import norm
from .game_safety import policy as safety
from .overlay_consent import Consents,token

u=win32.u; W=win32.W
ENUMPROC=C.WINFUNCTYPE(W.BOOL,W.HWND,win32.LPARAM)
win32.api(u,'EnumWindows',[ENUMPROC,win32.LPARAM],W.BOOL)
win32.api(u,'GetClientRect',[W.HWND,C.POINTER(W.RECT)],W.BOOL)
win32.api(u,'ClientToScreen',[W.HWND,C.POINTER(W.POINT)],W.BOOL)
win32.api(u,'PrintWindow',[W.HWND,W.HDC,W.UINT],W.BOOL)
g=C.WinDLL('gdi32',use_last_error=True)
win32.api(g,'CreateCompatibleDC',[W.HDC],W.HDC)
win32.api(g,'CreateDIBSection',[W.HDC,C.c_void_p,W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD],W.HBITMAP)
win32.api(g,'SelectObject',[W.HDC,W.HANDLE],W.HANDLE)
win32.api(g,'DeleteObject',[W.HANDLE],W.BOOL)
win32.api(g,'DeleteDC',[W.HDC],W.BOOL)


@dataclass(frozen=True)
class GameWindow:
    hwnd:int
    pid:int
    path:str
    identity:str
    game_id:str
    restriction:str=''
    consent:object=field(default=None,compare=False,repr=False)
    consent_token:str=''
    game:object=field(default=None,compare=False,repr=False)

    def blocked(self):
        from .game_safety import PROTECTED,anti_helper
        reason=self.restriction or safety.reason(self.path)
        if reason==PROTECTED and not anti_helper(self.path) and isinstance(self.consent,Consents) and self.consent_token in self.consent.accepted:
            return bool(safety.overlay_reason(self.path,self.game,consented=True))
        return bool(reason)

    def valid(self):
        pid=W.DWORD()
        if not u.IsWindowVisible(self.hwnd) or not u.GetWindowThreadProcessId(self.hwnd,C.byref(pid)) or pid.value!=self.pid:
            return False
        path,identity=win32.process_image(pid.value)
        return identity==self.identity and norm(path)==norm(self.path)

    def matches(self,sample):
        return (sample.interactive and sample.identity==self.identity and norm(sample.path)==norm(self.path)
                and u.GetForegroundWindow()==self.hwnd and self.valid())

    def activate(self):
        # Called only from the user's Preview action. No input synthesis or
        # repeated focus attempts: Alt+Tab immediately ends a live preview.
        if self.blocked() or not win32.interactive_desktop() or not self.valid(): return False
        if u.IsIconic(self.hwnd): u.ShowWindowAsync(self.hwnd,9)
        return bool(self.valid() and u.SetForegroundWindow(self.hwnd))


def running_window(catalog,game_id=None):
    if not win32.interactive_desktop(): return None
    found=[]; processes={}; foreground=u.GetForegroundWindow()
    @ENUMPROC
    def visit(hwnd,_):
        if not u.IsWindowVisible(hwnd): return True
        pid=W.DWORD(); u.GetWindowThreadProcessId(hwnd,C.byref(pid))
        if not pid.value or pid.value==os.getpid(): return True
        if pid.value not in processes: processes[pid.value]=win32.process_image(pid.value)
        path,identity=processes[pid.value]
        game=catalog.resolve(path,fallback=False)
        if not identity or not game or game_id and game.id!=game_id: return True
        rect=W.RECT(); iconic=bool(u.IsIconic(hwnd))
        if (not u.GetClientRect(hwnd,C.byref(rect)) or rect.right<80 or rect.bottom<60) and not iconic: return True
        target=GameWindow(int(hwnd),pid.value,path,identity,game.id,safety.reason(path,game),getattr(catalog,'overlay_consents',None),token(game),game)
        found.append(((hwnd==foreground,not iconic,rect.right*rect.bottom),target))
        return True
    u.EnumWindows(visit,0)
    return max(found,key=lambda value:value[0])[1] if found else None


def capture_window(target):
    """Print only the verified client, never an occluding desktop/application.

    A foreign renderer can block PrintWindow. This runs on the single daemon
    capture thread; the UI times out without creating additional workers.
    """
    if ((target.blocked() if isinstance(target,GameWindow) else safety.reason(target.path))
            or not win32.interactive_desktop() or not target.valid() or u.IsIconic(target.hwnd)): return None
    rect=W.RECT(); origin=W.POINT(); info=MonitorInfo(); info.size=C.sizeof(info)
    monitor=monitor_from_window(target.hwnd,2)
    if (not u.GetClientRect(target.hwnd,C.byref(rect)) or not u.ClientToScreen(target.hwnd,C.byref(origin))
            or not monitor or not monitor_info(monitor,C.byref(info))): return None
    width,height=rect.right,rect.bottom
    if width<1 or height<1 or width*height>16_777_216: return None  # At most 64 MiB, one request.
    # BITMAPINFOHEADER followed by an unused palette entry; top-down BGRA DIB.
    header=(C.c_uint32*11)(40,width,C.c_uint32(-height).value,1|(32<<16),0,width*height*4,0,0,0,0,0)
    dc=g.CreateCompatibleDC(None); bitmap=None; previous=None
    try:
        if not dc: return None
        bits=C.c_void_p(); bitmap=g.CreateDIBSection(dc,C.byref(header),0,C.byref(bits),None,0)
        if not bitmap or not bits.value: return None
        previous=g.SelectObject(dc,bitmap)
        if (not u.PrintWindow(target.hwnd,dc,3) or not target.valid() or not win32.interactive_desktop()
                or isinstance(target,GameWindow) and target.blocked()): return None
        after=W.RECT(); point=W.POINT()
        if (not u.GetClientRect(target.hwnd,C.byref(after)) or not u.ClientToScreen(target.hwnd,C.byref(point))
                or (after.right,after.bottom,point.x,point.y)!=(width,height,origin.x,origin.y)): return None
        raw=C.string_at(bits,width*height*4)
        image=QImage(raw,width,height,width*4,QImage.Format_RGB32).scaled(960,540,Qt.KeepAspectRatio,Qt.SmoothTransformation).copy()
        # A protected/GPU surface may report success but return a blank image.
        if all(image.pixelColor(x*image.width()//8,y*image.height()//8).value()<8 for x in range(1,8) for y in range(1,8)): return None
        bounds=info.monitor
        fraction=((origin.x-bounds.left)/(bounds.right-bounds.left),(origin.y-bounds.top)/(bounds.bottom-bounds.top),
                  width/(bounds.right-bounds.left),height/(bounds.bottom-bounds.top))
        return image,info.device,fraction
    finally:
        if previous: g.SelectObject(dc,previous)
        if bitmap: g.DeleteObject(bitmap)
        if dc: g.DeleteDC(dc)


class SnapshotWorker(QObject):
    ready=Signal(object,object,object)

    def __init__(self,parent):
        super().__init__(parent); self.results=SimpleQueue(); self.thread=None; self.serial=0; self.waiting=None
        self.timer=QTimer(self); self.timer.setInterval(50); self.timer.timeout.connect(self.poll)
        self.timeout=QTimer(self); self.timeout.setSingleShot(True); self.timeout.setInterval(2500); self.timeout.timeout.connect(self.expired)

    def request(self,target,recipient):
        self.poll()
        if self.thread and self.thread.is_alive(): return False
        self.serial+=1; serial=self.serial; self.waiting=(serial,target,recipient)
        def work():
            try: result=capture_window(target)
            except Exception: result=None
            self.results.put((serial,target,recipient,result))
        self.thread=threading.Thread(target=work,name='game-preview-snapshot',daemon=True); self.thread.start()
        self.timer.start(); self.timeout.start(); return True

    def poll(self):
        while not self.results.empty():
            try: serial,target,recipient,result=self.results.get_nowait()
            except Empty: break
            if self.waiting and self.waiting[0]==serial:
                self.waiting=None; self.timer.stop(); self.timeout.stop()
                self.ready.emit(recipient,target,result)

    def expired(self):
        if self.waiting:
            _,target,recipient=self.waiting; self.waiting=None; self.ready.emit(recipient,target,None)
        self.timer.stop()

    def close(self):
        self.waiting=None; self.timer.stop(); self.timeout.stop()
