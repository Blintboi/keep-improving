"""Optional RTSS countdown. Component I/O runs off the GUI thread.

RTSS is installed separately. Our .NET helper uses its documented V2 shared
memory ABI and CLR interlocked operations, with no redistributed SDK binaries.
"""
import configparser
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
from .model import norm, helper

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


def configure_profile(server, executable):
    """Preserve unrelated settings, including global hooking/performance options."""
    executable = Path(executable)
    if not executable.is_absolute() or executable.suffix.lower() != ".exe" or helper(executable):
        raise ValueError("Choose a game executable.")
    if not executable.is_file(): raise ValueError("The game's installation folder is unavailable.")
    profiles = Path(server).parent / "Profiles"
    profiles.mkdir(exist_ok=True)
    target = profiles / (executable.name + ".cfg")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    if target.exists(): parser.read(target, encoding="mbcs")
    for section, values in {
        "Hooking": {"EnableHooking": "1"},
        "OSD": {"EnableOSD": "1", "EnableBgnd": "0", "EnableFill": "0", "EnableStat": "0",
                "ZoomRatio": "1", "CoordinateSpace": "1"},
    }.items():
        if not parser.has_section(section): parser.add_section(section)
        for key, value in values.items(): parser.set(section, key, value)
    temporary = target.with_suffix(".cfg.gametime.tmp")
    try:
        with temporary.open("w", encoding="mbcs") as stream: parser.write(stream, space_around_delimiters=False)
        os.replace(temporary, target)
    finally: temporary.unlink(missing_ok=True)
    # The documented profile-reload API. No game process is opened by the Hub.
    library = Path(server).with_name("RTSSHooks64.dll" if C.sizeof(C.c_void_p) == 8 else "RTSSHooks.dll")
    hooks = C.CDLL(str(library)); hooks.UpdateProfiles.argtypes = []; hooks.UpdateProfiles.restype = None
    hooks.UpdateProfiles()


def countdown(remaining, warning, opacity):
    seconds = max(0, math.ceil(remaining))
    alpha = round(max(.25, min(1, opacity)) * 255)
    color = "FF5C65" if warning else "FFFFFF"
    # RTSS 7.3.7 FNT font override and ARGB color, per its installed SDK.
    return (f"<FNT=Consolas,-33,700,1><C={alpha:02X}{color}>"
            f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}<C>")


def native_position(x, y, width, height):
    # RTSS negative coordinates anchor the corresponding edge of the entire OSD.
    return tuple(round(16 + max(0, length - padding) * ratio) if ratio <= .5 else
                 -round(16 + max(0, length - padding) * (1-ratio))
                 for ratio,length,padding in ((x,width,200),(y,height,74)))


def position_profile(server, executable, x, y):
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

    def present(self, executable, identity, text, position=None):
        with self.condition:
            self.identity = identity; self.state = (executable, identity, text, position)
            if self.thread is None:
                self.thread = threading.Thread(target=self.run, name="rtss-countdown", daemon=True); self.thread.start()
            prior, healthy, timestamp, self.error = self.result
            self.condition.notify()
        now = time.monotonic()
        if self.operation_started and now - self.operation_started > 3:
            self.terminate_bridge(); return False
        return prior == identity and healthy and now - timestamp <= 1.5

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
        last_start = 0
        try:
            while True:
                with self.condition:
                    self.condition.wait(.2)
                    if self.stopping: break
                    state = self.state
                self.operation_started = time.monotonic()
                try:
                    if state is None:
                        if self.process and self.process.poll() is None: self.exchange(clear=True)
                        continue
                    executable, identity, text, position = state; key = norm(executable)
                    if key in self.failed_paths: continue
                    server = installation()
                    if not server: raise OSError("Install RTSS 7.3.7 or newer first.")
                    if key not in self.configured:
                        try: configure_profile(server, executable)
                        except Exception:
                            self.failed_paths.add(key); raise
                        self.configured.add(key)
                    with self.condition:
                        if self.stopping or self.state != state: continue
                    if position is not None:
                        dimensions=self.resolutions.get(identity,position[2:4])
                        coordinates_native=native_position(position[0],position[1],*dimensions)
                        if self.positions.get(key)!=coordinates_native:
                            position_profile(server,executable,*coordinates_native); self.positions[key]=coordinates_native
                    reply = self.exchange(identity=identity, pid=int(identity.split(":", 1)[0]), text=text)
                    if reply.get('width') and reply.get('height'):
                        self.resolutions[identity]=(reply['width'],reply['height'])
                    if not reply.get('available') and time.monotonic() - last_start > 10:
                        info = subprocess.STARTUPINFO(); info.dwFlags = subprocess.STARTF_USESHOWWINDOW; info.wShowWindow = 0
                        subprocess.Popen([str(server)], cwd=server.parent, startupinfo=info,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        last_start = time.monotonic()
                    with self.condition:
                        self.result = (identity, bool(reply.get("healthy")), time.monotonic(), reply.get("error", ""))
                except Exception as exc:
                    error = str(exc)
                    with self.condition: self.result = ("", False, 0, error)
                    if error != self.error: log.warning("RTSS countdown: %s", error)
                    self.error = error
                finally: self.operation_started = 0
        finally:
            if self.process:
                try:
                    if self.process.poll() is None:
                        self.exchange(clear=True); self.process.stdin.close(); self.process.wait(timeout=1)
                except (OSError, ValueError, subprocess.TimeoutExpired): self.terminate_bridge()
                finally:
                    for stream in (self.process.stdin, self.process.stdout):
                        try: stream.close()
                        except OSError: pass

    def hide(self):
        with self.condition:
            self.state = None; self.identity = ""; self.result = ("", False, 0, ""); self.condition.notify()

    def close(self):
        self.hide()
        with self.condition: self.stopping = True; self.condition.notify()
        if self.thread:
            self.thread.join(1.5)
            if self.thread.is_alive(): self.terminate_bridge(); self.thread.join(.5)
