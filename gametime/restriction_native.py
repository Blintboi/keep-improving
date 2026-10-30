"""Operations bound to an exact, ordinary user application process instance."""
import ctypes as C
from ctypes import wintypes as W
import ntpath
import os
from . import win32
from .model import norm, CLIENTS
from .focus import SHELLS
from .game_safety import policy, anti_helper

k, u = win32.k, win32.u
win32.api(k, 'TerminateProcess', [W.HANDLE, W.UINT], W.BOOL)
win32.api(k, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)
win32.api(u, 'PostMessageW', [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL)
CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
win32.api(u, 'EnumWindows', [CALLBACK, W.LPARAM], W.BOOL)
win32.api(u, 'GetWindowRect', [W.HWND, C.POINTER(W.RECT)], W.BOOL)


def permitted(path, identity):
    name = ntpath.basename(path).lower()
    if (not identity or identity.startswith(str(os.getpid()) + ':') or not ntpath.isabs(path)
            or name in SHELLS | CLIENTS or anti_helper(path)
            or norm(path).startswith(norm(os.environ.get('WINDIR', r'C:\Windows')) + '\\')
            or name in {'gametimemonitor.exe', 'python.exe', 'pythonw.exe', 'powershell.exe', 'pwsh.exe', 'cmd.exe'}):
        return False
    # New destructive operations do not inherit the older display/minimize consent.
    return not policy.reason(path)


def open_target(path, identity, terminate=False):
    if not permitted(path, identity): return None
    try: pid, created = map(int, identity.split(':'))
    except (ValueError, TypeError): return None
    handle = k.OpenProcess(0x1000 | 0x100000 | (1 if terminate else 0), False, pid)
    if not handle: return None
    times = [W.FILETIME() for _ in range(4)]
    buf, length = C.create_unicode_buffer(32768), W.DWORD(32768)
    if (not k.GetProcessTimes(handle, *(C.byref(t) for t in times))
            or (times[0].dwHighDateTime << 32 | times[0].dwLowDateTime) != created
            or not k.QueryFullProcessImageNameW(handle, 0, buf, C.byref(length))
            or norm(buf.value) != norm(path) or k.WaitForSingleObject(handle, 0) != 258):
        k.CloseHandle(handle); return None
    return handle


def windows(identity):
    pid = int(identity.split(':')[0]); found = []
    @CALLBACK
    def visit(hwnd, _):
        owner = W.DWORD(); u.GetWindowThreadProcessId(hwnd, C.byref(owner))
        if owner.value == pid and u.IsWindowVisible(hwnd): found.append(hwnd)
        return True
    u.EnumWindows(visit, 0)
    return found


def close_target(path, identity, wait_ms=5000, cancel=None):
    """Called on a worker; never waits or terminates on the GUI thread."""
    handle = open_target(path, identity, True)
    if not handle: return False
    try:
        if cancel and cancel.is_set(): return False
        for hwnd in windows(identity): u.PostMessageW(hwnd, 0x10, 0, 0)
        for _ in range(max(1, wait_ms // 100)):
            if k.WaitForSingleObject(handle, 100) == 0: return True
            if cancel and cancel.is_set(): return False
        if not k.TerminateProcess(handle, 1): return False
        return k.WaitForSingleObject(handle, 2000) == 0
    finally: k.CloseHandle(handle)


def target_rect(path, identity, background=False):
    handle = open_target(path, identity)
    if not handle: return None
    try:
        foreground = u.GetForegroundWindow()
        candidates=windows(identity)
        if foreground not in candidates:
            if not background: return None
            foreground=next((hwnd for hwnd in candidates if not u.IsIconic(hwnd)),None)
            if not foreground: return None
        rect = W.RECT()
        if not u.GetWindowRect(foreground, C.byref(rect)): return None
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    finally: k.CloseHandle(handle)


def minimize_target(path, identity):
    handle = open_target(path, identity)
    if not handle: return False
    try:
        results = [u.ShowWindowAsync(hwnd, 6) for hwnd in windows(identity)]
        return bool(results and all(results))
    finally: k.CloseHandle(handle)


def restore_target(path, identity):
    handle = open_target(path, identity)
    if not handle: return False
    try:
        candidates = windows(identity)
        if not candidates: return False
        u.ShowWindowAsync(candidates[0], 9)
        return bool(u.SetForegroundWindow(candidates[0]))
    finally: k.CloseHandle(handle)
