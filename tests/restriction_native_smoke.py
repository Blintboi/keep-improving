"""Only operates on the disposable FixtureRestriction process launched here.

Compile and Defender-scan the fixture before invoking this script. Optional
--guard-exe verifies the packaged windowed helper after its own clean scan.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import wave
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from gametime import win32
from gametime.restriction_audio import Mutes, query, call, release, AudioGuard
from gametime.restriction_native import close_target


def wait(check, message, seconds=8):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        result=check()
        if result: return result
        time.sleep(.1)
    raise AssertionError(message)


def muted(pid):
    audio=Mutes()
    try:
        for _,owner,control in audio.sessions():
            if owner!=pid: continue
            volume=query(control,'87CE5498-68D6-44E5-9215-6DA47EF883D8')
            try:
                result=W.BOOL(); call(volume,6,[C.POINTER(W.BOOL)],C.byref(result))
                return bool(result.value)
            finally: release(volume)
    finally: audio.close()
    return None


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('fixture',type=Path); parser.add_argument('--guard-exe',type=Path)
    args=parser.parse_args(); fixture=args.fixture.resolve()
    assert fixture.name=='FixtureRestriction.exe' and fixture.is_file()
    report=[]
    with tempfile.TemporaryDirectory(prefix='gtm-restriction-native-') as directory:
        wav=Path(directory)/'silence.wav'
        with wave.open(str(wav),'wb') as sound:
            sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(22050); sound.writeframes(b'\0'*44100)
        process=subprocess.Popen([str(fixture),str(wav),'ignore-close'])
        guard=AudioGuard(); owner=None; helper=None
        try:
            path,identity=wait(lambda:win32.process_image(process.pid)[0] and win32.process_image(process.pid),'fixture identity')
            wait(lambda:muted(process.pid) is False,'fixture shared-mode sound session')
            target=[{'path':path,'identity':identity}]
            if args.guard_exe:
                helper=subprocess.Popen([str(args.guard_exe),'--restriction-audio-guard'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                helper.stdin.write(json.dumps(target)+'\n'); helper.stdin.flush()
            else: guard.update(target)
            wait(lambda:muted(process.pid) is True,'target was not muted')
            report.append('exact target muted')
            if helper: helper.stdin.close(); helper.wait(timeout=8)
            else: guard.close()
            wait(lambda:muted(process.pid) is False,'owned mute was not restored')
            report.append('EOF restores audio')
            # Kill only this disposable owner Python process, never the user's app.
            code='from gametime.restriction_audio import AudioGuard; import time,json,sys; g=AudioGuard(); g.update(json.loads(sys.argv[1])); time.sleep(60)'
            owner=subprocess.Popen([sys.executable,'-B','-c',code,json.dumps(target)],cwd=str(Path(__file__).resolve().parent.parent),
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            wait(lambda:muted(process.pid) is True,'crash fixture was not muted')
            owner.terminate(); owner.wait(timeout=8)
            wait(lambda:muted(process.pid) is False,'parent crash left the fixture muted')
            report.append('parent crash restores audio')
            wrong=identity.split(':')[0]+':1'
            assert not close_target(path,wrong,100)
            assert process.poll() is None
            report.append('wrong process creation time rejected')
            assert close_target(path,identity,100)
            process.wait(timeout=8)
            report.append('only the refusing fixture was terminated')
        finally:
            guard.close()
            if helper and helper.poll() is None:
                if helper.stdin and not helper.stdin.closed: helper.stdin.close()
                helper.wait(timeout=8)
            if owner and owner.poll() is None: owner.terminate(); owner.wait(timeout=8)
            if process.poll() is None: process.terminate(); process.wait(timeout=8)
    print(json.dumps({'passed':report},ensure_ascii=False))


if __name__=='__main__': main()
