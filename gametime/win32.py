"""Read-only Win32 process inspection, native tray and directory notifications."""
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path
from queue import Empty, SimpleQueue
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
api(u, "SetWindowPos", [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT], W.BOOL)
api(u, "IsWindowVisible", [W.HWND], W.BOOL)
api(u, "ShowWindowAsync", [W.HWND, C.c_int], W.BOOL)
api(u, "GetAsyncKeyState", [C.c_int], W.SHORT)
api(s, "SHQueryUserNotificationState", [C.POINTER(C.c_int)], C.c_long)


def desktop_overlay_available():
    """Conservative fallback: a topmost HWND is not proof of fullscreen visibility."""
    state = C.c_int()
    try:
        return s.SHQueryUserNotificationState(C.byref(state)) >= 0 and state.value in (5, 6, 7)
    except OSError:
        return False


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class HARDWAREINPUT(C.Structure):
    _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]


class INPUTDATA(C.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", W.DWORD), ("data", INPUTDATA)]


api(u, "SendInput", [W.UINT, C.POINTER(INPUT), C.c_int], W.UINT)


def escape_game(expected_path, expected_identity):
    """One Escape press, only while the sampled game still owns the foreground."""
    if not expected_identity or not interactive_desktop():
        return False
    hwnd = u.GetForegroundWindow()
    pid = W.DWORD()
    if not hwnd or not u.GetWindowThreadProcessId(hwnd, C.byref(pid)):
        return False
    path, identity = process_image(pid.value)
    if (identity != expected_identity or os.path.normcase(path) != os.path.normcase(expected_path)
            or any(u.GetAsyncKeyState(key) & 0x8000 for key in (0x1B, 0x10, 0x11, 0x12, 0x5B, 0x5C))
            or u.GetForegroundWindow() != hwnd):
        return False
    keys = (INPUT * 2)(INPUT(type=1, ki=KEYBDINPUT(wVk=0x1B)),
                       INPUT(type=1, ki=KEYBDINPUT(wVk=0x1B, dwFlags=2)))
    sent = u.SendInput(2, keys, C.sizeof(INPUT))
    if sent == 1:
        # Complete a partially accepted key pair; never leave Escape held down.
        u.SendInput(1, C.byref(keys[1]), C.sizeof(INPUT))
    if sent != 2:
        log.warning("Escape could not be fully sent to the game: %s/2", sent)
    return sent == 2


def minimize_game(expected_path, expected_identity):
    """Minimize only the exact game that still owns the interactive foreground.

    No process termination/suspension or global key/mouse blocking is used.
    This is deliberately asynchronous: a hung game must not hang the monitor.
    """
    if not expected_identity or not interactive_desktop():
        return False
    hwnd = u.GetForegroundWindow()
    pid = W.DWORD()
    if not hwnd or not u.GetWindowThreadProcessId(hwnd, C.byref(pid)):
        return False
    path, identity = process_image(pid.value)
    if (identity != expected_identity or os.path.normcase(path) != os.path.normcase(expected_path)
            or u.GetForegroundWindow() != hwnd):
        return False
    return bool(u.ShowWindowAsync(hwnd, 6))  # SW_MINIMIZE


def present_notification(hwnd):
    # Show in the topmost group even when Windows refuses foreground focus.
    # NOMOVE | NOSIZE | NOACTIVATE | SHOWWINDOW | NOOWNERZORDER
    if not u.SetWindowPos(hwnd, W.HWND(-1), 0, 0, 0, 0, 0x253):
        raise C.WinError(C.get_last_error())
    return bool(u.SetForegroundWindow(hwnd))


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
            log.exception("Directory watcher interrupted: %s", self.directory)
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


advapi = C.WinDLL("advapi32", use_last_error=True)
api(advapi, "RegNotifyChangeKeyValue", [W.HANDLE, W.BOOL, W.DWORD, W.HANDLE, W.BOOL], W.LONG)


class RegistryWatcher:
    """Native registry notifications on a persistent thread, no polling."""
    def __init__(self, hive, key_path, view, recursive, callback):
        self.hive, self.key_path, self.view = hive, key_path, view
        self.recursive, self.callback = recursive, callback
        self.error = None
        self.ready = threading.Event()
        self.stop_event = k.CreateEventW(None, True, False, None)
        self.thread = threading.Thread(target=self._run, daemon=True, name="registry-events")
        self.thread.start()

    def _run(self):
        import winreg
        key, event = None, None
        try:
            hive = winreg.HKEY_CURRENT_USER if self.hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            key = winreg.OpenKey(hive, self.key_path, 0, winreg.KEY_READ | winreg.KEY_NOTIFY | self.view)
            event = k.CreateEventW(None, True, False, None)
            handles = (W.HANDLE * 2)(self.stop_event, event)
            def arm():
                k.ResetEvent(event)
                code = advapi.RegNotifyChangeKeyValue(int(key), self.recursive, 0x10000005, event, True)
                if code:
                    raise C.WinError(code)
            arm()
            self.ready.set()
            while True:
                wait = k.WaitForMultipleObjects(2, handles, False, 0xFFFFFFFF)
                if wait == 0:
                    break
                if wait != 1:
                    raise C.WinError(C.get_last_error())
                arm()  # Rearm before dispatching, so changes during a scan aren't lost.
                self.callback()
        except Exception as exc:
            self.error = str(exc)
            log.warning("Registry watcher interrupted: %s\\%s: %s", self.hive, self.key_path, exc)
            self.callback()
        finally:
            self.ready.set()
            if key is not None:
                key.Close()  # Cancels the registered notification before releasing its event.
            if event:
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
api(u, "GetSystemMetrics", [C.c_int], C.c_int)
api(u, "LoadImageW", [W.HINSTANCE, W.LPCWSTR, W.UINT, C.c_int, C.c_int, W.UINT], W.HANDLE)
api(u, "DestroyIcon", [W.HICON], W.BOOL)
api(u, "CreatePopupMenu", [], W.HMENU)
api(u, "AppendMenuW", [W.HMENU, W.UINT, WPARAM, W.LPCWSTR], W.BOOL)
api(u, "DestroyMenu", [W.HMENU], W.BOOL)
api(u, "SetMenuDefaultItem", [W.HMENU, W.UINT, W.UINT], W.BOOL)
api(u, "TrackPopupMenuEx", [W.HMENU, W.UINT, C.c_int, C.c_int, W.HWND, C.c_void_p], W.UINT)
api(u, "GetCursorPos", [C.POINTER(W.POINT)], W.BOOL)
api(u, "PostMessageW", [W.HWND, W.UINT, WPARAM, LPARAM], W.BOOL)
api(s, "Shell_NotifyIconW", [W.DWORD, C.POINTER(NOTIFYICONDATA)], W.BOOL)


class Tray:
    """Queue Win32 notifications; dispatch UI callbacks from a Tk timer only."""
    def __init__(self, on_open, on_menu, on_devices):
        self.on_open, self.on_menu, self.on_devices = on_open, on_menu, on_devices
        self.events = SimpleQueue()
        self.closed = False
        self.taskbar_created = u.RegisterWindowMessageW("TaskbarCreated")
        self.proc = WNDPROC(self._message)
        self.class_name = f"GameTimeTray-{os.getpid()}-{id(self)}"
        self.module = k.GetModuleHandleW(None)
        self.icon = u.LoadImageW(None, str(Path(__file__).with_name("app.ico")), 1,
                                u.GetSystemMetrics(49), u.GetSystemMetrics(50), 0x10)
        self.owns_icon = bool(self.icon)
        self.icon = self.icon or u.LoadIconW(None, C.c_void_p(32512))
        self.menu_pending = False
        self.menu_position = None
        self.wc = WNDCLASS(lpfnWndProc=self.proc, hInstance=self.module, hIcon=self.icon, lpszClassName=self.class_name)
        if not u.RegisterClassW(C.byref(self.wc)):
            raise C.WinError(C.get_last_error())
        self.window = u.CreateWindowExW(0, self.class_name, "Game Time Monitor", 0, 0, 0, 0, 0,
                                        None, None, self.module, None)
        if not self.window:
            raise C.WinError(C.get_last_error())
        self.data = NOTIFYICONDATA(cbSize=C.sizeof(NOTIFYICONDATA), hWnd=self.window, uID=1,
                                   uFlags=7 | 0x80, uCallbackMessage=0x8001, hIcon=self.icon)
        self.data.szTip = "Game Time Monitor – click to open"
        self._add()

    def _add(self):
        self.available = bool(s.Shell_NotifyIconW(0, C.byref(self.data)))
        if not self.available:
            log.warning("Tray icon unavailable; main window remains accessible.")
        self.data.uVersion = 4
        self.version4 = bool(s.Shell_NotifyIconW(4, C.byref(self.data)))

    def popup_menu(self, items):
        """Native context menu; only an explicit returned command can quit."""
        menu = u.CreatePopupMenu()
        if not menu:
            self.menu_pending = False
            raise C.WinError(C.get_last_error())
        try:
            for item in items:
                command, caption = item if item is not None else (0, None)
                if not u.AppendMenuW(menu, 0 if caption else 0x800, command, caption):
                    raise C.WinError(C.get_last_error())
            u.SetMenuDefaultItem(menu, 1, False)
            point = W.POINT()
            u.GetCursorPos(C.byref(point))
            x, y = self.menu_position or (point.x, point.y)
            if (x, y) == (-1, -1):
                x, y = point.x, point.y
            u.SetForegroundWindow(self.window)
            # RETURNCMD | NONOTIFY | RIGHTBUTTON | BOTTOMALIGN
            choice = u.TrackPopupMenuEx(menu, 0x100 | 0x80 | 0x02 | 0x20, x, y, self.window, None)
            u.PostMessageW(self.window, 0, 0, 0)
            if not choice:
                s.Shell_NotifyIconW(3, C.byref(self.data))
            return choice
        finally:
            self.menu_pending = False
            u.DestroyMenu(menu)

    def _message(self, hwnd, msg, wp, lp):
        try:
            if msg == 0x8001:
                event = lp & 0xFFFF
                if self.version4 and ((lp >> 16) & 0xFFFF) != self.data.uID:
                    return 0
                opens = (0x400, 0x401) if self.version4 else (0x202,)
                menu_event = 0x7B if self.version4 else 0x205
                if event in opens:
                    self.events.put("open")
                elif event == menu_event and not self.menu_pending:
                    self.menu_pending = True
                    self.menu_position = ((C.c_short(wp & 0xFFFF).value, C.c_short((wp >> 16) & 0xFFFF).value)
                                          if self.version4 else None)
                    self.events.put("menu")
                return 0
            if msg == self.taskbar_created and hasattr(self, "data"):
                self._add()
            if msg == 0x219:
                self.events.put("devices")
        except Exception:
            log.exception("Tray event handler failed")
        return u.DefWindowProcW(hwnd, msg, wp, lp)

    def dispatch_pending(self):
        # WNDPROC runs inside Tcl's native event loop with Tcl's Python thread
        # state released. Even root.after() there can fatally abort CPython.
        # A Tk timer calls this method after Tcl has restored that state.
        while not self.closed:
            try:
                event = self.events.get_nowait()
            except Empty:
                break
            {"open": self.on_open, "menu": self.on_menu, "devices": self.on_devices}[event]()

    def update(self, text):
        self.data.szTip = text[:127]
        s.Shell_NotifyIconW(1, C.byref(self.data))

    def close(self):
        if self.closed:
            return
        self.closed = True
        s.Shell_NotifyIconW(2, C.byref(self.data))
        u.DestroyWindow(self.window)
        u.UnregisterClassW(self.class_name, self.module)
        if self.owns_icon:
            u.DestroyIcon(self.icon)
            self.owns_icon = False
