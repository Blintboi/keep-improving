"""Local Direct3D fixture: RTSS acknowledgement, image pixels and focus.

Uses a unique temporary fixture and a fixture-only RTSS profile; never launches a
real game or sends input. The synthetic game becomes foreground briefly.
"""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import configparser,ctypes,json,os,subprocess,sys,tempfile,time
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from gametime import win32
from gametime.model import Game,Settings,norm
from gametime.qt_ui import setup_application,App
from gametime.qt_fullscreen_notifications import present
from gametime.rtss import Backend,configure_profile,installation,countdown
from gametime.tracker import Alert


def run(fullscreen=False):
    root=Path(__file__).resolve().parents[1]; qt=setup_application(); server=installation()
    if not server: raise RuntimeError('RTSS is not installed')
    source=root/'build/fullscreen-fixture/GtmNotificationFixture.exe'
    profile=server.parent/'Profiles'/f'{source.name}.cfg'
    if profile.exists(): raise RuntimeError('Fixture RTSS profile already exists; preserved')
    checks={}; child=None; backend=None
    with tempfile.TemporaryDirectory(prefix='gtm-d3d-smoke-') as folder:
        base=Path(folder); app=None
        try:
            # Exercise removal of a real inherited/old delay with triggers that
            # are loaded in every fixture, not only Steam's optional overlay.
            profile.write_text('[Hooking]\nInjectionDelay=15000\nInjectionDelayTriggers=KERNEL32.dll,USER32.dll\n',encoding='ascii')
            configure_profile(server,source)
            hooks=ctypes.CDLL(str(server.with_name('RTSSHooks64.dll')))
            hooks.LoadProfile.argtypes=[ctypes.c_char_p]; hooks.LoadProfile(source.name.encode('mbcs'))
            hooks.GetProfileProperty.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_uint32]; hooks.GetProfileProperty.restype=ctypes.c_int
            configured=configparser.ConfigParser(); configured.read(profile,encoding='mbcs')
            checks['rtss_startup_delay_disabled']=configured.getint('Hooking','InjectionDelay')==0
            for name in (b'EnableOSD',b'Implementation',b'AppDetectionLevel',b'PositionX',b'PositionY'):
                value=ctypes.c_int32(); ok=hooks.GetProfileProperty(name,ctypes.byref(value),4); print(name.decode(),ok,value.value)
            launched=time.monotonic()
            child=subprocess.Popen([str(source),folder]+(['fullscreen'] if fullscreen else []))
            deadline=time.monotonic()+15
            while not (base/'ready').exists() and not (base/'error').exists() and time.monotonic()<deadline:
                qt.processEvents(); time.sleep(.05)
            if (base/'error').exists(): raise RuntimeError((base/'error').read_text())
            if not (base/'ready').exists(): raise RuntimeError('D3D fixture did not start')
            hwnd=int((base/'ready').read_text())
            fixture_path,fixture_identity=win32.process_image(child.pid)
            if norm(fixture_path)!=norm(source): raise RuntimeError('Fixture identity mismatch')
            from gametime.tracker import Sample
            current=Sample(datetime.now().astimezone(),win32.awake_seconds(),fixture_path,fixture_identity,True)
            foreground=win32.u.GetForegroundWindow()
            checks['fixture_identity_verified']=bool(fixture_identity)
            print('fixture is actual foreground:',foreground==hwnd)
            game=Game('fixture:d3d','Synthetic fixture','Games',str(source.parent))
            class Catalog:
                def resolve(self,path): return game if norm(path)==norm(source) else None
            class Fake(QObject): pass
            app=Fake(); app.closed=False; app.settings=replace(Settings(),overlay_rtss_auto=True,notification_sound='silent')
            app.t=lambda value:value; app.update_overlay=lambda:None
            app.catalog=Catalog(); app.overlay=None; app.overlay_consents=SimpleNamespace(allows=lambda g:False)
            app._rtss_consent_paths=frozenset(); app.rtss_available=lambda:True
            app.rtss=backend=Backend(base); backend.server=server
            app.popup_window=None; app.notification_mode=lambda:'defer'
            app.fullscreen_scheduled_notification=lambda alert,sample:present(app,alert,sample)
            timer_text=countdown(120,False,1)
            def restore_countdown():
                backend.present(current.path,current.identity,timer_text,(0,0,1920,1080,25),retry=backend.retry_due(current.identity))
            app.update_overlay=restore_countdown
            from PySide6.QtGui import QImage
            def capture():
                image=base/'capture.png'; image.unlink(missing_ok=True); (base/'capture').touch()
                deadline=time.monotonic()+3
                while not image.exists() and not (base/'capture-error').exists() and time.monotonic()<deadline:
                    qt.processEvents(); time.sleep(.04)
                if (base/'capture-error').exists(): raise RuntimeError((base/'capture-error').read_text())
                if not image.exists(): raise RuntimeError('Fixture screenshot unavailable')
                # Wait for the child to close the file before Qt reads it.
                for _ in range(20):
                    result=QImage(str(image))
                    if not result.isNull(): return result
                    time.sleep(.05)
                raise RuntimeError('Fixture screenshot unreadable')
            before_capture=capture()
            def visible_capture():
                if win32.u.GetForegroundWindow()!=hwnd: return None
                frame=qt.primaryScreen().grabWindow(0).toImage()
                if win32.u.GetForegroundWindow()!=hwnd or frame.isNull(): return None
                samples=[frame.pixelColor(x,y).rgb() for x in range(0,frame.width(),40) for y in range(0,frame.height(),40)]
                return frame if sum(c==0xff234563 for c in samples)>len(samples)*.7 else None
            visible_before=visible_capture()
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                restore_countdown(); qt.processEvents(); time.sleep(.05)
                if backend.present(current.path,current.identity,timer_text,(0,0,1920,1080,25)):
                    break
            checks['countdown_connected']=backend.result[1]
            elapsed=time.monotonic()-launched
            print('Seconds from fixture launch to countdown receipt:',round(elapsed,3))
            checks['countdown_without_startup_delay']=backend.result[1] and elapsed<5
            for _ in range(5): qt.processEvents(); time.sleep(.05)
            timer_frame=visible_capture()
            checks['countdown_visible']=bool(timer_frame and visible_before and any(
                timer_frame.pixelColor(x,y)!=visible_before.pixelColor(x,y)
                for x in range(8,300,3) for y in range(8,100,3)))
            icon=QImage(32,32,QImage.Format_ARGB32); icon.fill(0xffee3344); icon_path=base/'test-icon.png'; icon.save(str(icon_path))
            alert=Alert(str(datetime.now().date()),('fixture',),'limit','Árvíztűrő tükörfúrógép 🍎\nLejárt a játékidő.','',title='Játékidő emlékeztető',icon=str(icon_path))
            with patch('gametime.qt_fullscreen_notifications.win32.sample',return_value=current),patch('gametime.win32.u.SendInput') as keys,patch('gametime.win32.u.SetForegroundWindow') as focus:
                App.popup(app,alert); active=app._fullscreen_alert
                if not active: raise RuntimeError('Fullscreen notification not prepared')
                if '--text' in sys.argv: active.text='RTSS TEST 123456'
                if '--trailing' in sys.argv: active.text+=' TRAILING'
                if '--sample' in sys.argv: active.text='<LI=\"'+str(server.parent/'Plugins/Client/Overlays/sample.png')+'\"><I=0,0,256,384,128,128> SAMPLE'
                deadline=time.monotonic()+15
                while not active.confirmed and not active.closing and time.monotonic()<deadline:
                    qt.processEvents(); time.sleep(.05)
                checks['rtss_consumed_new_image']=active.confirmed
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenFileMappingW.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_wchar_p]; kernel.OpenFileMappingW.restype=ctypes.c_void_p
                kernel.MapViewOfFile.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_size_t]; kernel.MapViewOfFile.restype=ctypes.c_void_p
                kernel.UnmapViewOfFile.argtypes=[ctypes.c_void_p]; kernel.CloseHandle.argtypes=[ctypes.c_void_p]
                mapping=kernel.OpenFileMappingW(6,False,'RTSSSharedMemoryV2'); address=kernel.MapViewOfFile(mapping,6,0,0,0)
                def u32(offset): return ctypes.c_uint32.from_address(address+offset).value
                version=u32(4); appsize,appoffset,appcount=u32(8),u32(12),u32(16); osdsize,osdoffset,osdcount=u32(20),u32(24),u32(28)
                print('RTSS layout:',hex(version),'entry size',osdsize,'global frame',u32(32))
                for i in range(appcount):
                    off=appoffset+i*appsize
                    if u32(off)==child.pid:
                        print('fixture flags/OSD fields:',hex(u32(off+264)),[u32(off+n) for n in (316,320,324,328,332)])
                        if fullscreen and win32.u.GetForegroundWindow()==hwnd:
                            screenshot=str(base/'rtss-capture.png').encode('ascii')
                            if len(screenshot)<259:
                                ctypes.memset(address+off+340,0,260); ctypes.memmove(address+off+340,screenshot,len(screenshot)); ctypes.c_uint32.from_address(address+off+336).value=17
                for i in range(1,osdcount):
                    off=osdoffset+i*osdsize; owner=ctypes.string_at(address+off+256,256).split(b'\0',1)[0]
                    if owner==backend.owner.encode():
                        o=266752 if version>=0x20014 and osdsize>=299520 else 512
                        print('fixture OSD slot:',i,'text bytes:',repr(ctypes.string_at(address+off+o,128).split(b'\0',1)[0]))
                kernel.UnmapViewOfFile(address); kernel.CloseHandle(mapping)
                if fullscreen:
                    deadline=time.monotonic()+3
                    while time.monotonic()<deadline and not (base/'rtss-capture.png').exists(): qt.processEvents(); time.sleep(.05)
                    print('RTSS capture files:',[p.name for p in base.iterdir() if 'capture' in p.name])
                    if (base/'rtss-capture.png').exists():
                        for _ in range(30):
                            img=QImage(str(base/'rtss-capture.png'))
                            if not img.isNull(): break
                            qt.processEvents(); time.sleep(.05)
                        print('RTSS capture dimensions:',img.width(),img.height())
                        if not img.isNull(): img.save(str(root/'test-reports'/'rtss-native-fixture.png'))
                checks['foreground_unchanged']=win32.u.GetForegroundWindow()==foreground
                checks['no_focus_or_input_calls']=not focus.called and not keys.called
                for _ in range(10): qt.processEvents(); time.sleep(.05)
                after=capture(); before=before_capture
                output=root/'test-reports'/('rtss-fullscreen-fixture.png' if fullscreen else 'rtss-windowed-fixture.png')
                after.save(str(output))
                changed=0
                if before.size()==after.size():
                    for y in range(0,after.height(),4):
                        for x in range(0,after.width(),4):
                            if before.pixelColor(x,y)!=after.pixelColor(x,y): changed+=1
                non_background=sum(1 for y in range(0,after.height(),8) for x in range(0,after.width(),8) if after.pixelColor(x,y).rgb()!=0xff234563)
                visible_after=visible_capture()
                if visible_before and visible_after and visible_before.size()==visible_after.size():
                    distinct=sum(1 for y in range(0,visible_after.height(),6) for x in range(0,visible_after.width(),6) if visible_after.pixelColor(x,y)!=visible_before.pixelColor(x,y))
                    checks['visible_fixture_pixels_changed']=distinct>100
                    checks['custom_icon_drawn']=any(visible_after.pixelColor(x,y).red()>220 and visible_after.pixelColor(x,y).green()<90 and visible_after.pixelColor(x,y).blue()<110 for x in range(20,90,2) for y in range(20,90,2))
                    if checks['visible_fixture_pixels_changed']: visible_after.save(str(root/'test-reports'/'rtss-visible-fixture.png'))
                elif fullscreen:
                    checks['visible_fixture_capture_available']=False
                    print('Fullscreen fixture capture unavailable; surface changed pixels:',non_background)
                active.finish(); deadline=time.monotonic()+5
                while getattr(app,'_fullscreen_alert',None) and time.monotonic()<deadline:
                    qt.processEvents(); time.sleep(.05)
                checks['overlay_removed']=getattr(app,'_fullscreen_alert',None) is None
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and not backend.result[1]:
                    restore_countdown(); qt.processEvents(); time.sleep(.05)
                checks['countdown_restored']=backend.result[1] and backend.state[2]==timer_text
                for _ in range(5): qt.processEvents(); time.sleep(.05)
                restored=visible_capture()
                checks['countdown_visible_after_reminder']=bool(restored and timer_frame and all(
                    restored.pixelColor(x,y)==timer_frame.pixelColor(x,y)
                    for x in range(8,700,6) for y in range(8,430,6)))
            return checks
        finally:
            if app and getattr(app,'_fullscreen_alert',None): app._fullscreen_alert.shutdown()
            if backend: backend.close()
            (base/'stop').touch()
            if child:
                try: child.wait(timeout=8)
                except subprocess.TimeoutExpired: child.terminate(); child.wait(timeout=5)
            if profile.exists(): profile.unlink()
            hooks=ctypes.CDLL(str(server.with_name('RTSSHooks64.dll'))); hooks.UpdateProfiles()

if __name__=='__main__':
    checks=run('--fullscreen' in sys.argv); print(json.dumps(checks,indent=2));
    if not all(checks.values()): raise SystemExit('RTSS fixture verification failed')
