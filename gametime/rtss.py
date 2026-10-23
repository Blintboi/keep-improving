"""Optional RTSS countdown. Component I/O runs off the GUI thread.

RTSS is installed separately. Our .NET helper uses its documented V2 shared
memory ABI and CLR interlocked operations, with no redistributed SDK binaries.
"""
import configparser
from collections import OrderedDict
import ctypes as C
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import threading
import time
from .model import norm, helper,hex_color
from .win32 import process_running
from .game_safety import policy as safety,PROTECTED_EXES,PROTECTED,anti_helper

log = logging.getLogger(__name__)


def installation():
    for variable, suffix in (("LOCALAPPDATA", "Programs/RivaTunerStatisticsServer"),
                             ("ProgramFiles(x86)", "RivaTuner Statistics Server"),
                             ("ProgramFiles", "RivaTuner Statistics Server")):
        root = os.environ.get(variable)
        if root:
            path = Path(root) / suffix / "RTSS.exe"
            if path.is_file(): return path
    return None


def configure_profile(server, executable, *, consented=False):
    """Preserve unrelated settings, including global hooking/performance options."""
    executable = Path(executable)
    reason=safety.overlay_reason(str(executable),consented=consented)
    if reason:
        disable_profiles(server,[executable.name])
        raise ValueError(reason)
    if not executable.is_absolute() or executable.suffix.lower() != ".exe" or helper(executable):
        raise ValueError("Choose a game executable.")
    if not executable.is_file(): raise ValueError("The game's installation folder is unavailable.")
    profiles = Path(server).parent / "Profiles"
    profiles.mkdir(exist_ok=True)
    target = profiles / (executable.name + ".cfg")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if target.exists(): parser.read(target, encoding="mbcs")
    changed=False
    for section, values in {
        "Hooking": {"EnableHooking": "1"},
        "OSD": {"EnableOSD": "1", "EnableBgnd": "0", "EnableFill": "0", "EnableStat": "0",
                "ZoomRatio": "1", "CoordinateSpace": "1"},
    }.items():
        if not parser.has_section(section): parser.add_section(section)
        for key, value in values.items():
            if parser.get(section,key,fallback=None)!=value: parser.set(section,key,value); changed=True
    if not changed: return
    temporary = target.with_suffix(".cfg.gametime.tmp")
    try:
        with temporary.open("w", encoding="mbcs") as stream: parser.write(stream, space_around_delimiters=False)
        os.replace(temporary, target)
    finally: temporary.unlink(missing_ok=True)
    # The documented profile-reload API. No game process is opened by the Hub.
    library = Path(server).with_name("RTSSHooks64.dll" if C.sizeof(C.c_void_p) == 8 else "RTSSHooks.dll")
    hooks = C.CDLL(str(library)); hooks.UpdateProfiles.argtypes = []; hooks.UpdateProfiles.restype = None
    hooks.UpdateProfiles()


def disable_profiles(server,names):
    """Revoke old per-EXE hooking without changing global/performance settings.

    This also overrides a global RTSS hook for protected executable names. No
    service is started/stopped, and no running game's protection is bypassed.
    """
    profiles=Path(server).parent/'Profiles'; profiles.mkdir(exist_ok=True)
    changed=False
    for name in dict.fromkeys(names):
        if Path(name).name!=name or not name.lower().endswith('.exe'): continue
        target=profiles/(name+'.cfg')
        parser=configparser.ConfigParser(interpolation=None,strict=False); parser.optionxform=str
        if target.exists(): parser.read(target,encoding='mbcs')
        dirty=False
        for section,key in (('Hooking','EnableHooking'),('OSD','EnableOSD')):
            if not parser.has_section(section): parser.add_section(section)
            if parser.get(section,key,fallback=None)!='0': parser.set(section,key,'0'); dirty=True
        if not dirty: continue
        temporary=target.with_suffix('.cfg.gametime.tmp')
        try:
            with temporary.open('w',encoding='mbcs') as stream: parser.write(stream,space_around_delimiters=False)
            os.replace(temporary,target); changed=True
        finally: temporary.unlink(missing_ok=True)
    if changed:
        library=Path(server).with_name('RTSSHooks64.dll' if C.sizeof(C.c_void_p)==8 else 'RTSSHooks.dll')
        hooks=C.CDLL(str(library)); hooks.UpdateProfiles.argtypes=[]; hooks.UpdateProfiles.restype=None
        hooks.UpdateProfiles()


def server_running():
    """Check the existing SDK mapping without starting a bridge process."""
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.OpenFileMappingW.argtypes=[C.c_uint32,C.c_int,C.c_wchar_p]; kernel.OpenFileMappingW.restype=C.c_void_p
    kernel.CloseHandle.argtypes=[C.c_void_p]; kernel.CloseHandle.restype=C.c_int
    handle=kernel.OpenFileMappingW(4,False,'RTSSSharedMemoryV2')
    if handle: kernel.CloseHandle(handle)
    return bool(handle)


def start_server(server):
    info = subprocess.STARTUPINFO(); info.dwFlags = subprocess.STARTF_USESHOWWINDOW; info.wShowWindow = 0
    # RTSS requests elevation in its manifest even in its per-user install.
    # Start the optional renderer with the monitor's existing privileges.
    environment=os.environ.copy(); environment['__COMPAT_LAYER']='RunAsInvoker'
    subprocess.Popen([str(server)], cwd=server.parent, startupinfo=info,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,env=environment)


def countdown(remaining, warning, opacity, font_size=25,normal_color='#ffffff',warning_color='#ff5c65'):
    seconds = max(0, math.ceil(remaining))
    alpha = round(max(.25, min(1, opacity)) * 255)
    color=hex_color(warning_color if warning else normal_color)[1:].upper()
    # RTSS 7.3.7 FNT font override and ARGB color, per its installed SDK.
    height=round(font_size*96/72)
    return (f"<FNT=Consolas,-{height},700,1><C={alpha:02X}{color}>"
            f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}<C>")


def native_position(x, y, width, height, font_size=25):
    # RTSS negative coordinates anchor the corresponding edge of the entire OSD.
    return tuple(round(16 + max(0, length - padding) * ratio) if ratio <= .5 else
                 -round(16 + max(0, length - padding) * (1-ratio))
                 for ratio,length,padding in ((x,width,32+168*font_size/25),(y,height,32+42*font_size/25)))


def position_profile(server, executable, x, y, *, consented=False):
    reason=safety.overlay_reason(executable,consented=consented)
    if reason: raise ValueError(reason)
    library=Path(server).with_name('RTSSHooks64.dll' if C.sizeof(C.c_void_p)==8 else 'RTSSHooks.dll')
    hooks=C.CDLL(str(library))
    for name in ('LoadProfile','SaveProfile'):
        fn=getattr(hooks,name); fn.argtypes=[C.c_char_p]; fn.restype=None
    hooks.SetProfileProperty.argtypes=[C.c_char_p,C.c_void_p,C.c_uint32]; hooks.SetProfileProperty.restype=C.c_int
    hooks.UpdateProfiles.argtypes=[]; hooks.UpdateProfiles.restype=None
    profile=Path(executable).name.encode('mbcs'); hooks.LoadProfile(profile)
    for name,value in ((b'PositionX',x),(b'PositionY',y),(b'CoordinateSpace',1)):
        parameter=C.c_int32(value)
        if not hooks.SetProfileProperty(name,C.byref(parameter),4): raise OSError('RTSS position update failed')
    hooks.SaveProfile(profile); hooks.UpdateProfiles()


class Backend:
    def __init__(self, data_dir):
        self.owner = "GameTimeMonitor:" + hashlib.sha256(norm(data_dir).encode()).hexdigest()[:24]
        self.condition = threading.Condition(); self.state = None
        self.result = ("", False, 0, ""); self.thread = self.process = None
        self.stopping = False; self.configured = set(); self.failed_paths = set()
        self.identity = ""; self.error = ""; self.operation_started = 0
        self.positions={}; self.resolutions={}
        self.profiles=OrderedDict(); self.server=None; self.last_start=0
        self.protected=set(); self.protection_pending=set(); self.protection_seeded=False
        self.denied_names=set(PROTECTED_EXES)
        self.protection_error=''
        self.approved=frozenset()
        self._withdrawn=True; self._published_pid=0
        self._fallback_identity=''; self._unhealthy_since=None
        self._generation=0

    @property
    def desktop_ready(self):
        """No publication in flight, and the game has consumed our OSD removal."""
        if self.operation_started and time.monotonic()-self.operation_started>3:
            self.terminate_bridge()
        with self.condition:
            return self._withdrawn and (self.state is None or self.state[1]==self._fallback_identity)

    def fallback_for(self,identity):
        with self.condition:
            return self._withdrawn and self._fallback_identity==identity and self.state is not None and self.state[1]==identity

    def authorize(self,executables):
        """Exact paths derived from explicit per-game consent on the GUI thread."""
        approved=frozenset(norm(path) for path in executables if not helper(path))
        with self.condition:
            previous=self.approved
            if previous==approved: return
            self.approved=approved; self.configured.difference_update(previous|approved)
            active_names={Path(path).name.casefold() for path in approved}
            revoked={Path(path).name.casefold() for path in previous-approved}-active_names
            self.denied_names.update(revoked)
            self.protected.difference_update(revoked); self.protection_pending.update(revoked)
            for key,path in tuple(self.profiles.items()):
                if Path(path).name.casefold() in revoked: self.profiles.pop(key,None)
            if self.state and norm(self.state[0]) in previous-approved:
                self._generation+=1
                self.state=None; self.identity=''; self.result=('',False,0,'')
            if revoked: self._start_worker()
            self.condition.notify()

    def protect(self,executables=()):
        with self.condition:
            if self.stopping: return
            names={Path(path).name.casefold() for path in executables}
            if not self.protection_seeded:
                names.update(PROTECTED_EXES); self.protection_seeded=True
            self.denied_names.update(names)
            self.protection_pending.update(names-self.protected)
            if self.protection_pending:
                self._start_worker(); self.condition.notify()

    def prepare(self,executables):
        """Reuse already discovered EXEs; no extra game-directory scan or IPC."""
        with self.condition:
            if self.stopping: return
            for executable in executables:
                path=Path(executable)
                if not path.is_absolute() or path.suffix.lower()!='.exe' or helper(path): continue
                consented=norm(executable) in self.approved
                reason=safety.overlay_reason(executable,consented=consented)
                if (path.name.casefold() in self.denied_names and not consented
                        or reason): continue
                key=norm(executable)
                if key not in self.configured and key not in self.failed_paths and len(self.profiles)<1024:
                    self.profiles[key]=str(executable)
            if self.profiles:
                self._start_worker(); self.condition.notify()

    def _start_worker(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.run, name="rtss-countdown", daemon=True); self.thread.start()

    def cancel_preparation(self):
        with self.condition: self.profiles.clear()

    def configure(self,server,executable):
        key=norm(executable)
        if self.protection_error: return False
        consented=key in self.approved; reason=safety.overlay_reason(executable,consented=consented)
        if (Path(executable).name.casefold() in self.denied_names and not consented
                or reason):
            disable_profiles(server,[Path(executable).name]); self.configured.discard(key); return False
        if key in self.configured: return True
        if key in self.failed_paths: return False
        try:
            if consented: configure_profile(server,executable,consented=True)
            else: configure_profile(server,executable)
        except Exception:
            self.failed_paths.add(key); log.warning('RTSS profile unavailable: %s',executable,exc_info=True); return False
        self.configured.add(key); return True

    def ensure_server(self,server):
        now=time.monotonic()
        if now-self.last_start<10: return
        self.last_start=now
        # The SDK mapping can be temporarily absent while RTSS is starting or
        # unavailable across integrity levels. An existing process still owns
        # its tray icon; invoking RTSS again can disturb that icon/session.
        if not server_running() and process_running(server) is False: start_server(server)

    def present(self, executable, identity, text, position=None):
        consented=norm(executable) in self.approved
        reason=safety.overlay_reason(executable,consented=consented)
        if Path(executable).name.casefold() in self.denied_names and not consented: reason=reason or PROTECTED
        if self.protection_error: reason=self.protection_error
        if reason:
            self.hide(); self.error=reason; self.protect([executable]); return False
        with self.condition:
            if self.identity!=identity:
                self._generation+=1; self.result=('',False,0,'')
                self._fallback_identity=''; self._unhealthy_since=None
            self.identity = identity; self.state = (executable, identity, text, position)
            self._start_worker()
            prior, healthy, timestamp, self.error = self.result
            fallback=self._fallback_identity==identity
            self.condition.notify()
        now = time.monotonic()
        if self.operation_started and now - self.operation_started > 3:
            self.terminate_bridge(); return False
        return not fallback and prior == identity and healthy and now - timestamp <= 1.5

    def terminate_bridge(self):
        process = self.process
        if process and process.poll() is None:
            try: process.terminate()
            except OSError: pass

    def exchange(self, **request):
        if self.process is None or self.process.poll() is not None:
            if self.process:
                for stream in (self.process.stdin,self.process.stdout): stream.close()
            info = subprocess.STARTUPINFO(); info.dwFlags = subprocess.STARTF_USESHOWWINDOW; info.wShowWindow = 0
            self.process = subprocess.Popen([str(Path(__file__).with_name("rtss_bridge.exe"))],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", startupinfo=info, creationflags=subprocess.CREATE_NO_WINDOW)
        process = self.process
        process.stdin.write(json.dumps(dict(owner=self.owner, **request)) + "\n"); process.stdin.flush()
        line = process.stdout.readline(16384)
        if not line: raise OSError("RTSS bridge stopped")
        return json.loads(line)

    def run(self):
        last_state = None
        try:
            while True:
                with self.condition:
                    if self._withdrawn and (self.state is None or self.state[1]==self._fallback_identity):
                        self.condition.wait_for(lambda: self.stopping or bool(self.protection_pending)
                            or self.state is None and bool(self.profiles) or not self._withdrawn
                            or self.state is not None and self.state[1]!=self._fallback_identity)
                    elif self.state == last_state:
                        self.condition.wait(.2)
                    if self.stopping and not self.protection_pending: break
                    state = None if self.stopping else self.state
                    generation=self._generation
                    fallback=state is not None and state[1]==self._fallback_identity
                    protection=tuple(self.protection_pending); self.protection_pending.clear()
                    # Prepare other games only while idle; active rendering has
                    # priority and never waits for a whole catalog of profiles.
                    profile=self.profiles.popitem(last=False)[1] if state is None and self.profiles and not self.stopping else None
                self.operation_started = time.monotonic()
                try:
                    if protection:
                        self.server=self.server or installation()
                        if self.server:
                            authorized_names={Path(path).name.casefold() for path in self.approved}
                            protection=tuple(name for name in protection if name.casefold() not in authorized_names)
                            disable_profiles(self.server,protection); self.protected.update(protection); self.protection_error=''
                    if self.stopping: break
                    if state is None or fallback:
                        if not self._withdrawn:
                            reply=self.exchange(clear=True,pid=self._published_pid)
                            with self.condition: self._withdrawn=reply.get('cleared') is True
                            if not self._withdrawn: continue
                        if profile:
                            self.server=self.server or installation()
                            if self.server and self.configure(self.server,profile): self.ensure_server(self.server)
                        continue
                    executable, identity, text, position = state; key = norm(executable)
                    if key in self.failed_paths:
                        with self.condition:
                            if self._generation==generation and self.state==state: self._fallback_identity=identity
                        continue
                    server = self.server or installation(); self.server=server
                    if not server: raise OSError("Install RTSS 7.3.7 or newer first.")
                    if not self.configure(server,executable):
                        with self.condition:
                            if self._generation==generation and self.state==state: self._fallback_identity=identity
                        continue
                    with self.condition:
                        if self.stopping or self._generation!=generation or self.state != state: continue
                    if position is not None:
                        dimensions=self.resolutions.get(identity,position[2:4])
                        coordinates_native=native_position(position[0],position[1],*dimensions,position[4] if len(position)>4 else 25)
                        if self.positions.get(key)!=coordinates_native:
                            if key in self.approved: position_profile(server,executable,*coordinates_native,consented=True)
                            else: position_profile(server,executable,*coordinates_native)
                            self.positions[key]=coordinates_native
                    pid=int(identity.split(":",1)[0])
                    with self.condition:
                        if self.stopping or self._generation!=generation or self.state!=state: continue
                        # Set before IPC: cancellation may race with the write.
                        self._withdrawn=False; self._published_pid=pid
                    reply = self.exchange(identity=identity, pid=pid, text=text)
                    if reply.get('width') and reply.get('height'):
                        self.resolutions[identity]=(reply['width'],reply['height'])
                    if not reply.get('available'): self.ensure_server(server)
                    with self.condition:
                        if self._generation!=generation or self.state!=state: continue
                        now=time.monotonic(); healthy=bool(reply.get('healthy'))
                        self.result = (identity, healthy, now, reply.get("error", ""))
                        if healthy: self._unhealthy_since=None
                        else:
                            if self._unhealthy_since is None: self._unhealthy_since=now
                            elif now-self._unhealthy_since>=1.5: self._fallback_identity=identity
                except Exception as exc:
                    if protection:
                        self.protection_error='Could not disable protected RTSS profiles. RTSS countdown is disabled.'
                    if state is None or fallback: self.terminate_bridge()
                    error = str(exc)
                    with self.condition:
                        if self._generation==generation and self.state==state:
                            self.result = ("", False, 0, error)
                            if state is not None: self._fallback_identity=state[1]
                    if error != self.error: log.warning("RTSS countdown: %s", error)
                    self.error = error
                finally: self.operation_started = 0; last_state = state
        finally:
            if self.process:
                try:
                    if self.process.poll() is None:
                        self.exchange(clear=True,pid=self._published_pid); self.process.stdin.close(); self.process.wait(timeout=1)
                except (OSError, ValueError, subprocess.TimeoutExpired): self.terminate_bridge()
                finally:
                    for stream in (self.process.stdin, self.process.stdout):
                        try: stream.close()
                        except OSError: pass

    def hide(self):
        with self.condition:
            if self.state is not None: self._generation+=1
            self.state = None; self.identity = ""; self.result = ("", False, 0, "")
            self._fallback_identity=''; self._unhealthy_since=None; self.condition.notify()

    def close(self):
        self.hide()
        with self.condition: self.stopping = True; self.condition.notify()
        if self.thread:
            self.thread.join(1.5)
            if self.thread.is_alive(): self.terminate_bridge(); self.thread.join(.5)
