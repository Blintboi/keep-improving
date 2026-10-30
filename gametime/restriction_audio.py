"""Short-lived Core Audio mute owner. EOF/parent exit restores owned sessions.

Uses only documented COM interfaces. No system volume, input hooks or injection.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


class GUID(C.Structure):
    _fields_ = [('bytes', C.c_ubyte * 16)]
    def __init__(self, value): super().__init__((C.c_ubyte * 16).from_buffer_copy(uuid.UUID(value).bytes_le))


def call(obj, slot, args, *values):
    table = C.cast(obj, C.POINTER(C.POINTER(C.c_void_p))).contents
    result = C.WINFUNCTYPE(C.c_long, C.c_void_p, *args)(table[slot])(obj, *values)
    if result < 0: raise OSError('Core Audio operation unavailable')
    return result


def release(obj):
    if obj:
        table = C.cast(obj, C.POINTER(C.POINTER(C.c_void_p))).contents
        C.WINFUNCTYPE(C.c_ulong, C.c_void_p)(table[2])(obj)


def query(obj, iid):
    result = C.c_void_p()
    call(obj, 0, [C.POINTER(GUID), C.POINTER(C.c_void_p)], C.byref(GUID(iid)), C.byref(result))
    return result


class Mutes:
    def __init__(self):
        self.owned = {}
        self.ole = C.OleDLL('ole32')
        self.ole.CoInitializeEx(None, 0)
        self.ole.CoTaskMemFree.argtypes = [C.c_void_p]
        self.ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, W.DWORD, C.POINTER(GUID), C.POINTER(C.c_void_p)]

    def sessions(self):
        enumerator = C.c_void_p(); collection = C.c_void_p()
        self.ole.CoCreateInstance(C.byref(GUID('BCDE0395-E52F-467C-8E3D-C4579291692E')), None, 23,
                                 C.byref(GUID('A95664D2-9614-4F35-A746-DE8DB63617E6')), C.byref(enumerator))
        try:
            call(enumerator, 3, [C.c_int, W.DWORD, C.POINTER(C.c_void_p)], 0, 1, C.byref(collection))
            count = W.UINT(); call(collection, 3, [C.POINTER(W.UINT)], C.byref(count))
            for i in range(count.value):
                device = C.c_void_p(); manager = C.c_void_p(); sessions = C.c_void_p()
                try:
                    call(collection, 4, [W.UINT, C.POINTER(C.c_void_p)], i, C.byref(device))
                    call(device, 3, [C.POINTER(GUID), W.DWORD, C.c_void_p, C.POINTER(C.c_void_p)],
                         C.byref(GUID('77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F')), 23, None, C.byref(manager))
                    call(manager, 5, [C.POINTER(C.c_void_p)], C.byref(sessions))
                    size = C.c_int(); call(sessions, 3, [C.POINTER(C.c_int)], C.byref(size))
                    for j in range(size.value):
                        control = C.c_void_p(); control2 = None
                        try:
                            call(sessions, 4, [C.c_int, C.POINTER(C.c_void_p)], j, C.byref(control))
                            control2 = query(control, 'BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D')
                            pid = W.DWORD()
                            # AUDCLNT_S_NO_SINGLE_PROCESS: never mute a shared owner.
                            if call(control2, 14, [C.POINTER(W.DWORD)], C.byref(pid)) != 0: continue
                            text = C.c_void_p()
                            call(control2, 13, [C.POINTER(C.c_void_p)], C.byref(text))
                            try: key = C.wstring_at(text)
                            finally: self.ole.CoTaskMemFree(text)
                            yield key, pid.value, control
                        finally: release(control2); release(control)
                finally: release(sessions); release(manager); release(device)
        finally: release(collection); release(enumerator)

    def update(self, targets):
        from . import win32
        from .restriction_native import open_target
        verified = {}
        for target in targets:
            handle = open_target(target['path'], target['identity'])
            if handle:
                win32.k.CloseHandle(handle)
                verified[int(target['identity'].split(':')[0])] = target
        wanted = set()
        for key, pid, control in self.sessions():
            if pid not in verified: continue
            target = verified[pid]
            handle = open_target(target['path'], target['identity'])
            if not handle: continue
            win32.k.CloseHandle(handle); wanted.add(key)
            if key in self.owned: continue
            volume = query(control, '87CE5498-68D6-44E5-9215-6DA47EF883D8')
            original = W.BOOL()
            try:
                call(volume, 6, [C.POINTER(W.BOOL)], C.byref(original))
                if original.value: release(volume); continue
                call(volume, 5, [W.BOOL, C.c_void_p], True, None)
                self.owned[key] = volume
            except Exception: release(volume); raise
        for key in list(self.owned):
            if key not in wanted: self.restore(key)
        return len(wanted)

    def restore(self, key):
        volume = self.owned.pop(key)
        try: call(volume, 5, [W.BOOL, C.c_void_p], False, None)
        except OSError: pass
        finally: release(volume)

    def close(self):
        for key in list(self.owned): self.restore(key)
        self.ole.CoUninitialize()


def run_guard():
    # PyInstaller's windowed bootloader sets sys.std* to None even when the
    # parent supplied real pipe handles. Reattach only this private helper mode.
    if sys.stdin is None or sys.stdout is None:
        import io
        import msvcrt
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.GetStdHandle.argtypes=[W.DWORD]; kernel.GetStdHandle.restype=W.HANDLE
        if sys.stdin is None:
            sys.stdin=io.open(msvcrt.open_osfhandle(kernel.GetStdHandle(-10),os.O_RDONLY),
                             'r',encoding='utf-8',closefd=False)
        if sys.stdout is None:
            sys.stdout=io.open(msvcrt.open_osfhandle(kernel.GetStdHandle(-11),os.O_WRONLY),
                              'w',encoding='utf-8',buffering=1,closefd=False)
    # Input is a bounded list of exact process identities. No commands/paths execute.
    stopped = threading.Event(); changed = threading.Event(); state = {'targets': []}
    def reader():
        try:
            for line in sys.stdin:
                if len(line) > 65536: break
                data = json.loads(line)
                if not isinstance(data, list) or len(data) > 20: break
                if any(not isinstance(t, dict) or set(t) != {'path', 'identity'} or
                       any(not isinstance(t[k], str) for k in t) for t in data): break
                state['targets'] = data; changed.set()
        except (ValueError, OSError): pass
        finally: stopped.set(); changed.set()
    threading.Thread(target=reader, daemon=True).start()
    owner = Mutes()
    try:
        while not stopped.is_set():
            try: result = {'muted': owner.update(state['targets']), 'ok': True}
            except (OSError, ValueError): result = {'ok': False}
            print(json.dumps(result), flush=True)
            changed.wait(2); changed.clear()
    finally: owner.close()


class AudioGuard:
    def __init__(self):
        self.process = None; self.targets = None; self.status = {}; self.retry_at = 0
    def update(self, targets):
        if not targets: self.close(); return
        if self.process and self.process.poll() is not None:
            self.close(); self.retry_at = time.monotonic() + 30; self.status = {'ok': False}
        if self.process is None:
            if time.monotonic() < self.retry_at: return
            command = [sys.executable] + ([] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve().parent.parent / 'main.py')])
            try:
                self.process = subprocess.Popen(command + ['--restriction-audio-guard'], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except OSError:
                self.retry_at = time.monotonic() + 30; self.status = {'ok': False}; return
            process = self.process
            def read():
                try:
                    for line in process.stdout:
                        if process is self.process: self.status = json.loads(line)
                except (OSError, ValueError): pass
                finally: process.stdout.close()
            threading.Thread(target=read, daemon=True).start()
        if self.targets != targets:
            self.process.stdin.write(json.dumps(targets) + '\n'); self.process.stdin.flush()
            self.targets = targets
    def close(self):
        if self.process:
            try: self.process.stdin.close()
            except OSError: pass
            self.process = None
        self.targets = None; self.status = {}
