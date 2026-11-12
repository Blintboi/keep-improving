"""Opt-in, read-only audio observations on a dedicated COM thread."""
import ctypes as C
from ctypes import wintypes as W
import threading
import time


class AudioSampler:
    def __init__(self):
        self.condition=threading.Condition(); self.enabled=False; self.stopped=False
        self.thread=None; self.result=(0,()); self.last_signal={}

    def sample(self,enabled):
        with self.condition:
            if enabled!=self.enabled:
                self.enabled=enabled; self.result=(0,()); self.condition.notify_all()
            if enabled and self.thread is None:
                self.thread=threading.Thread(target=self.run,name='media-audio',daemon=True);self.thread.start()
            at,rows=self.result
        return rows if enabled and time.monotonic()-at<4 else ()

    def run(self):
        from .restriction_audio import Mutes
        reader=Mutes()
        try:
            while True:
                with self.condition:
                    while not self.enabled and not self.stopped:self.condition.wait()
                    if self.stopped:return
                now=time.monotonic();found=self.scan(reader,now)
                with self.condition:
                    if self.enabled:self.result=(now,tuple(set(found)))
                    if self.stopped:return
                    self.condition.wait(1 if found else 3)
        finally:reader.close()

    def scan(self,reader,now):
        from .restriction_audio import query,call,release
        from .win32 import process_image
        found=[];live=set()
        try:
            for key,pid,control in reader.sessions(audible_only=True):
                if not pid:continue
                live.add(key);volume=meter=None
                try:
                    state=C.c_int();call(control,3,[C.POINTER(C.c_int)],C.byref(state))
                    volume=query(control,'87CE5498-68D6-44E5-9215-6DA47EF883D8')
                    muted=W.BOOL();level=C.c_float()
                    call(volume,6,[C.POINTER(W.BOOL)],C.byref(muted));call(volume,4,[C.POINTER(C.c_float)],C.byref(level))
                    if state.value!=1 or muted.value or level.value<=0:
                        self.last_signal.pop(key,None);continue
                    meter=query(control,'C02216F6-8C67-4B5B-9D00-D008E73E0064')
                    peak=C.c_float();call(meter,3,[C.POINTER(C.c_float)],C.byref(peak))
                    if peak.value>0.00001:self.last_signal[key]=now
                    # Bridge brief silence between audio samples, never a stopped stream.
                    if now-self.last_signal.get(key,0)<=1.5:
                        path,identity=process_image(pid)
                        if path and identity:found.append((path,identity))
                except (OSError,ValueError):pass
                finally:release(meter);release(volume)
        except (OSError,ValueError):found=[]
        self.last_signal={key:stamp for key,stamp in self.last_signal.items() if key in live}
        return tuple(set(found))

    def close(self):
        with self.condition:self.stopped=True;self.result=(0,());self.condition.notify_all()
