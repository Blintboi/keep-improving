"""Read-only Win32 process inspection, native tray and directory notifications."""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
import struct
import threading
from .tracker import Sample

log = logging.getLogger(__name__)
if os.name != "nt":
    raise ImportError("This module requires Windows")
k = C.WinDLL("kernel32", use_last_error=True)
u = C.WinDLL("user32", use_last_error=True)
s = C.WinDLL("shell32", use_last_error=True)
LRESULT = C.c_ssize_t
WPARAM = C.c_size_t
LPARAM = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, WPARAM, LPARAM)


def api(dll, name, args, result):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = args, result
    return fn


api(k, "CloseHandle", [W.HANDLE], W.BOOL)
api(k, "OpenProcess", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
api(k, "QueryFullProcessImageNameW", [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)
api(k, "GetProcessTimes", [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4, W.BOOL)
api(k, "QueryUnbiasedInterruptTime", [C.POINTER(C.c_ulonglong)], W.BOOL)
api(k, "CreateMutexW", [C.c_void_p, W.BOOL, W.LPCWSTR], W.HANDLE)
api(u, "GetForegroundWindow", [], W.HWND)
api(u, "GetWindowThreadProcessId", [W.HWND, C.POINTER(W.DWORD)], W.DWORD)
api(u, "OpenInputDesktop", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
api(u, "CloseDesktop", [W.HANDLE], W.BOOL)
api(u, "GetUserObjectInformationW", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL)
api(u, "SetForegroundWindow", [W.HWND], W.BOOL)


def awake_seconds():
    value = C.c_ulonglong()
    if not k.QueryUnbiasedInterruptTime(C.byref(value)):
        raise C.WinError(C.get_last_error())
    return value.value / 10_000_000


def interactive_desktop():
    desktop = u.OpenInputDesktop(0, False, 1)  # DESKTOP_READOBJECTS
    if not desktop:
        return False
    try:
        name, needed = C.create_unicode_buffer(256), W.DWORD()
        return bool(u.GetUserObjectInformationW(desktop, 2, name, C.sizeof(name), C.byref(needed))
                    and name.value.lower() == "default")
    finally:
        u.CloseDesktop(desktop)


def process_image(pid):
    handle = k.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return "", ""
    try:
        text, length = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not k.QueryFullProcessImageNameW(handle, 0, text, C.byref(length)):
            return "", ""
        times = [W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle, *(C.byref(t) for t in times)):
            return "", ""
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return text.value, f"{pid}:{created}"
    finally:
        k.CloseHandle(handle)


def sample():
    active = interactive_desktop()
    pid = W.DWORD()
    window = u.GetForegroundWindow() if active else None
    if window:
        u.GetWindowThreadProcessId(window, C.byref(pid))
    path, identity = process_image(pid.value) if pid.value else ("", "")
    return Sample(datetime.now().astimezone(), awake_seconds(), path, identity, active)


class Instance:
    def __init__(self, directory):
        digest = hashlib.sha256(str(Path(directory).resolve()).lower().encode()).hexdigest()[:24]
        self.handle = k.CreateMutexW(None, False, "Local\\GameTimeMonitor-" + digest)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        self.acquired = C.get_last_error() != 183

    def close(self):
        if self.handle:
            k.CloseHandle(self.handle)
            self.handle = None


class OVERLAPPED(C.Structure):
    _fields_ = [("Internal", C.c_size_t), ("InternalHigh", C.c_size_t),
                ("Offset", W.DWORD), ("OffsetHigh", W.DWORD), ("hEvent", W.HANDLE)]


api(k, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
api(k, "CreateEventW", [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE)
api(k, "SetEvent", [W.HANDLE], W.BOOL)
api(k, "ResetEvent", [W.HANDLE], W.BOOL)
api(k, "WaitForMultipleObjects", [W.DWORD, C.POINTER(W.HANDLE), W.BOOL, W.DWORD], W.DWORD)
api(k, "ReadDirectoryChangesW", [W.HANDLE, C.c_void_p, W.DWORD, W.BOOL, W.DWORD,
                               C.POINTER(W.DWORD), C.POINTER(OVERLAPPED), C.c_void_p], W.BOOL)
api(k, "GetOverlappedResult", [W.HANDLE, C.POINTER(OVERLAPPED), C.POINTER(W.DWORD), W.BOOL], W.BOOL)
api(k, "CancelIoEx", [W.HANDLE, C.POINTER(OVERLAPPED)], W.BOOL)


def decode_changes(data):
    offset = 0
    while offset + 12 <= len(data):
        following, action, size = struct.unpack_from("<III", data, offset)
        if offset + 12 + size > len(data):
            raise ValueError("Truncated directory notification")
        yield action, data[offset + 12:offset + 12 + size].decode("utf-16-le")
        if not following:
            break
        offset += following


class DirectoryWatcher:
    def __init__(self, directory, recursive, callback):
        self.directory, self.recursive, self.callback = Path(directory), recursive, callback
        self.stop_event = k.CreateEventW(None, True, False, None)
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True, name="directory-events")
        self.thread.start()

    def _run(self):
        handle = k.CreateFileW(str(self.directory), 1, 7, None, 3, 0x42000000, None)
        if handle == C.c_void_p(-1).value:
            self.error = str(C.WinError(C.get_last_error()))
            self.ready.set()
            return
        event = k.CreateEventW(None, True, False, None)
        ov = OVERLAPPED(hEvent=event)
        buffer = C.create_string_buffer(64 * 1024)
        count = W.DWORD()
        handles = (W.HANDLE * 2)(self.stop_event, event)
        try:
            while True:
                k.ResetEvent(event)
                if not k.ReadDirectoryChangesW(handle, buffer, len(buffer), self.recursive, 0x1B,
                                               None, C.byref(ov), None):
                    code = C.get_last_error()
                    if code != 997:
                        raise C.WinError(code)
                self.ready.set()
                wait = k.WaitForMultipleObjects(2, handles, False, 0xFFFFFFFF)
                if wait == 0:
                    break
                if wait != 1:
                    raise C.WinError(C.get_last_error())
                if not k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), False):
                    code = C.get_last_error()
                    if code == 1022:
                        self.callback(None)  # Buffer overflow: recover this source only.
                        continue
                    raise C.WinError(code)
                if not count.value:
                    self.callback(None)
                else:
                    for action, name in decode_changes(buffer.raw[:count.value]):
                        self.callback(self.directory / name)
        except Exception as exc:
            self.error = str(exc)
            log.exception("A könyvtárfigyelés megszakadt: %s", self.directory)
            self.callback(None)
        finally:
            self.ready.set()
            k.CancelIoEx(handle, C.byref(ov))
            # Wait for cancellation before releasing OVERLAPPED/buffer memory.
            k.GetOverlappedResult(handle, C.byref(ov), C.byref(count), True)
            k.CloseHandle(handle)
            k.CloseHandle(event)

    def close(self):
        if self.stop_event:
            k.SetEvent(self.stop_event)
            self.thread.join(timeout=2)
            if not self.thread.is_alive():
                k.CloseHandle(self.stop_event)
                self.stop_event = None


class WNDCLASS(C.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", C.c_int),
                ("cbWndExtra", C.c_int), ("hInstance", W.HINSTANCE), ("hIcon", W.HICON),
                ("hCursor", W.HANDLE), ("hbrBackground", W.HANDLE),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


class GUID(C.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", C.c_ubyte * 8)]


class NOTIFYICONDATA(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT), ("uFlags", W.UINT),
                ("uCallbackMessage", W.UINT), ("hIcon", W.HICON), ("szTip", W.WCHAR * 128),
                ("dwState", W.DWORD), ("dwStateMask", W.DWORD), ("szInfo", W.WCHAR * 256),
                ("uVersion", W.UINT), ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", W.HICON)]


api(k, "GetModuleHandleW", [W.LPCWSTR], W.HMODULE)
api(u, "RegisterClassW", [C.POINTER(WNDCLASS)], W.WORD)
api(u, "UnregisterClassW", [W.LPCWSTR, W.HINSTANCE], W.BOOL)
api(u, "RegisterWindowMessageW", [W.LPCWSTR], W.UINT)
api(u, "CreateWindowExW", [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int,
                         C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p], W.HWND)
api(u, "DefWindowProcW", [W.HWND, W.UINT, WPARAM, LPARAM], LRESULT)
api(u, "DestroyWindow", [W.HWND], W.BOOL)
api(u, "LoadIconW", [W.HINSTANCE, C.c_void_p], W.HICON)
api(s, "Shell_NotifyIconW", [W.DWORD, C.POINTER(NOTIFYICONDATA)], W.BOOL)


class Tray:
    """Hidden Win32 window; Tk's message loop dispatches its callbacks."""
    def __init__(self, on_open, on_menu, on_devices):
        self.on_open, self.on_menu, self.on_devices = on_open, on_menu, on_devices
        self.taskbar_created = u.RegisterWindowMessageW("TaskbarCreated")
        self.proc = WNDPROC(self._message)
        self.class_name = "GameTimeTray-" + str(os.getpid())
        self.module = k.GetModuleHandleW(None)
        self.wc = WNDCLASS(lpfnWndProc=self.proc, hInstance=self.module, lpszClassName=self.class_name)
        if not u.RegisterClassW(C.byref(self.wc)):
            raise C.WinError(C.get_last_error())
        self.window = u.CreateWindowExW(0, self.class_name, "Játékidőfigyelő", 0, 0, 0, 0, 0,
                                        None, None, self.module, None)
        if not self.window:
            raise C.WinError(C.get_last_error())
        self.data = NOTIFYICONDATA(cbSize=C.sizeof(NOTIFYICONDATA), hWnd=self.window, uID=1,
                                   uFlags=7, uCallbackMessage=0x8001, hIcon=u.LoadIconW(None, C.c_void_p(32516)))
        self.data.szTip = "Játékidőfigyelő – kattints a megnyitáshoz"
        self._add()

    def _add(self):
        self.available = bool(s.Shell_NotifyIconW(0, C.byref(self.data)))
        if not self.available:
            log.warning("A tálcaikon nem adható hozzá; a kezelőablak elérhető marad.")
        self.data.uVersion = 4
        s.Shell_NotifyIconW(4, C.byref(self.data))

    def _message(self, hwnd, msg, wp, lp):
        try:
            if msg == 0x8001:
                event = lp & 0xFFFF
                if event in (0x202, 0x203, 0x400, 0x401):
                    self.on_open()
                elif event in (0x205, 0x7B):
                    self.on_menu()
                return 0
            if msg == self.taskbar_created and hasattr(self, "data"):
                self._add()
            if msg == 0x219:
                self.on_devices()
        except Exception:
            log.exception("Tálcaesemény kezelési hiba")
        return u.DefWindowProcW(hwnd, msg, wp, lp)

    def update(self, text):
        self.data.szTip = text[:127]
        s.Shell_NotifyIconW(1, C.byref(self.data))

    def close(self):
        s.Shell_NotifyIconW(2, C.byref(self.data))
        u.DestroyWindow(self.window)
        u.UnregisterClassW(self.class_name, self.module)
