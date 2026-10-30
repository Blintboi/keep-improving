"""Opt-in native cross-process overlay smoke; only a synthetic Form is started.

Run with a report directory argument on an interactive Windows desktop. No input
is injected: native hit-testing proves the separate Form is under the HUD.
"""
import ctypes as C
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Queue
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gametime import win32
from gametime.discovery import Discovery
from gametime.model import Game,Settings,norm
from gametime.overlay import get_style,EX_FLAGS,choose_screen,screen_device
from gametime.game_preview import running_window,capture_window
from gametime.qt_ui import App,setup_application
from gametime.store import Store

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    qt=setup_application()
    def pump(seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until: qt.processEvents(); time.sleep(.01)
    checks={}
    with tempfile.TemporaryDirectory(prefix='gametime-overlay-') as folder:
        base=Path(folder); exe=base/'FixtureGame.exe'; stop=base/'stop'
        csc=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        subprocess.run([str(csc),'/nologo','/target:winexe','/reference:System.Windows.Forms.dll',
                        '/reference:System.Drawing.dll','/out:'+str(exe),str(Path(__file__).with_name('FixtureGame.cs'))],check=True,capture_output=True)
        settings=Settings(games_root=str(base/'Games'),language='hu',overlay_enabled=True,overlay_rtss_auto=False,overlay_x=.5,overlay_y=.5)
        store=Store(base/'usage.sqlite3'); store.save_settings(settings)
        game=Game('overlay:fixture','Synthetic overlay fixture','Kézi',str(base))
        store.upsert([game]); store.set_rule(str(exe),game.id)
        class Service:
            def __init__(self): self.results=Queue(); self.discovery=Discovery(settings,[],[],base/'none',platforms=False, ubisoft=False,riot=False)
            def start(self): pass
            def close(self): pass
            def request(self,*args): pass
            def configure(self,*args): pass
            def watch_manual(self,*args): pass
        class Hub:
            def __init__(self): self.results=Queue()
            def request(self,*args): pass
            def close(self): pass
        app=App(store,base,background=True,service=Service(),hub=Hub()); app.tick_timer.stop(); app.overlay_timer.stop()
        child=None
        try:
            child=subprocess.Popen([str(exe),str(stop),str(os.getpid())])
            pump(1.5)
            find=win32.api(win32.u,'FindWindowW',[win32.W.LPCWSTR,win32.W.LPCWSTR],win32.W.HWND)
            fixture=find(None,'Jatekido tesztablak'); assert fixture
            fixture_pid=win32.W.DWORD(); win32.u.GetWindowThreadProcessId(fixture,C.byref(fixture_pid)); assert fixture_pid.value==child.pid
            target=running_window(app.catalog,game.id)
            checks['recognized_fixture_window_only']=target is not None and target.hwnd==fixture and target.pid==child.pid
            snapshot=capture_window(target)
            checks['native_game_client_snapshot']=snapshot is not None and not snapshot[0].isNull() and snapshot[0].width()<=960 and snapshot[0].height()<=540
            checks['snapshot_has_monitor_and_client_bounds']=snapshot is not None and bool(snapshot[1]) and 0<snapshot[2][2]<=1 and 0<snapshot[2][3]<=1
            checks['native_capture_monitor_maps_to_qt_screen']=snapshot is not None and screen_device(choose_screen('',snapshot[1]))==snapshot[1]
            # Windows can refuse foreground activation while the user works in
            # another app. Test hit-through without forcing their focus away.
            win32.u.SetWindowPos(fixture,win32.W.HWND(-1),0,0,0,0,0x53)
            before=win32.u.GetForegroundWindow()
            app.overlay.present(7200,0,settings,qt.primaryScreen()); pump(.15)
            overlay=app.overlay; hwnd=int(overlay.winId())
            checks['visible_with_hub_hidden']=overlay.isVisible() and not app.isVisible() and bool(win32.u.IsWindowVisible(hwnd))
            checks['foreground_unchanged']=win32.u.GetForegroundWindow()==before
            checks['native_input_and_focus_flags']=get_style(hwnd,-20)&EX_FLAGS==EX_FLAGS
            rect=win32.W.RECT(); win32.u.GetWindowRect(hwnd,C.byref(rect))
            hit=win32.api(win32.u,'WindowFromPoint',[win32.W.POINT],win32.W.HWND)
            ancestor=win32.api(win32.u,'GetAncestor',[win32.W.HWND,win32.W.UINT],win32.W.HWND)
            under=ancestor(hit(win32.W.POINT((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)),2)
            pid=win32.W.DWORD(); win32.u.GetWindowThreadProcessId(under,C.byref(pid))
            checks['hit_test_passes_through_to_other_process']=pid.value==child.pid
            overlay.grab().save(str(output/'countdown-normal.png'))
            app.overlay.present(1200,6000,settings,qt.primaryScreen()); pump(.05)
            overlay.grab().save(str(output/'countdown-warning.png')); checks['warning_is_red']=overlay.warning and overlay.seconds<=1200
            app.show(); pump(.2); app.update_overlay()
            checks['other_app_hides_countdown']=not overlay.isVisible()
            app.switch_page(2); pump(.8)
            checks['settings_uses_game_image']=app.overlay_picker.game_background is not None
            picker=app.overlay_picker; background=picker.game_background
            painted=picker.grab().toImage(); picker.game_background=None; empty=picker.grab().toImage(); picker.game_background=background
            monitor,_=picker.rectangles(); changed=0
            if background:
                x,y,width,height=background[2]
                for i in range(1,5):
                    for j in range(1,5):
                        point=(round(monitor.x()+(x+width*i/5)*monitor.width()),round(monitor.y()+(y+height*j/5)*monitor.height()))
                        changed+=painted.pixelColor(*point)!=empty.pixelColor(*point)
            checks['settings_paints_game_pixels']=changed>=8
            app.overlay_picker.grab().save(str(output/'position-picker.png'))
            app.grab().save(str(output/'settings.png'))
            # Restore our own fixture Hub before simulating its Preview click.
            # A background test process has fewer foreground rights than a real
            # user clicking the foreground settings window.
            app.showMinimized(); pump(.1); app.show(); pump(.2)
            if win32.u.GetForegroundWindow()!=int(app.winId()):
                # Establish the simulated click's foreground precondition. The
                # synthetic game's Activated handler grants this test parent
                # foreground permission; only our own two windows are touched.
                win32.u.ShowWindowAsync(fixture,6); pump(.05)
                assert target.activate(),'Synthetic fixture could not grant foreground permission'
                pump(.3); app.activateWindow(); pump(.2)
            assert win32.u.GetForegroundWindow()==int(app.winId()),'Preview test requires its own foreground Hub'
            app._overlay_preview_game_id=game.id; app._overlay_game_preview_state='normal'
            before_preview=int(win32.u.GetForegroundWindow() or 0)
            app.preview_game_overlay(replace(settings,overlay_color_normal='#12ab34',overlay_color_warning='#bc56ef'))
            preview_debug={'before':before_preview,'immediate':int(win32.u.GetForegroundWindow() or 0),'fixture':int(fixture),'hub':int(app.winId()),'target_immediate':app._overlay_preview_target is not None,'visible_immediate':app.overlay.isVisible(),'status':str(app.overlay_preview_status.text())}
            pump(.25); preview_debug.update(after=int(win32.u.GetForegroundWindow() or 0),target_after=app._overlay_preview_target is not None,visible_after=app.overlay.isVisible())
            (output/'activation-debug.json').write_text(json.dumps(preview_debug,indent=2))
            checks['explicit_preview_activates_fixture']=win32.u.GetForegroundWindow()==fixture and app._overlay_preview_target==target
            checks['native_preview_has_game_color']=app.overlay.isVisible() and app.overlay.color=='#12ab34'
            checks['preview_keeps_profile_and_history']=store.settings()==settings and store.totals(datetime.now().date())=={} and not store.alert_keys(datetime.now().date())
            app.overlay.grab().save(str(output/'preview-game-color.png'))
            Path(str(stop)+'.yield').touch(); pump(.4)
            checks['alt_tab_clears_preview']=app._overlay_preview_until==0 and not app.overlay.isVisible() and app._overlay_preview_target is None
            preview_debug.update(return_foreground=int(win32.u.GetForegroundWindow() or 0),return_timer=app.overlay_timer.isActive(),return_deadline=app._overlay_preview_until,return_target=app._overlay_preview_target is not None)
            checks['fixture_minimized_before_preview']=bool(win32.u.IsIconic(fixture))
            app.preview_game_overlay(replace(settings,overlay_color_normal='#12ab34'))
            preview_debug.update(restore_immediate_fg=int(win32.u.GetForegroundWindow() or 0),restore_immediate_target=app._overlay_preview_target is not None,restore_immediate_visible=app.overlay.isVisible(),restore_grace=app._overlay_preview_focus_until)
            pump(.7)
            checks['preview_restores_minimized_game']=not win32.u.IsIconic(fixture) and win32.u.GetForegroundWindow()==fixture and app.overlay.isVisible()
            preview_debug.update(restore_foreground=int(win32.u.GetForegroundWindow() or 0),restore_iconic=bool(win32.u.IsIconic(fixture)),restore_target=app._overlay_preview_target is not None,restore_status=str(app.overlay_preview_status.text()))
            (output/'activation-debug.json').write_text(json.dumps(preview_debug,indent=2))
            Path(str(stop)+'.yield').touch(); pump(.4); app.show()
            app.settings=app.catalog.settings=replace(app.settings,restriction_enabled=True)
            app.restriction_enabled.setChecked(True)
            app.tracker.cache[str(datetime.now().date())]={game.id:7500}; app.render()
            app.grab().save(str(output/'restriction-settings.png'))
            # Restrict only our synthetic Form. Foreground observation is
            # supplied explicitly here because Windows may refuse activation;
            # production's actual foreground guards have separate unit tests.
            _,identity=win32.process_image(child.pid)
            with patch.object(win32.u,'GetForegroundWindow',return_value=fixture):
                checks['native_fixture_minimize_accepted']=win32.minimize_game(str(exe),identity)
            pump(.3)
            iconic=win32.api(win32.u,'IsIconic',[win32.W.HWND],win32.W.BOOL)
            checks['native_fixture_is_minimized']=bool(iconic(fixture))
            checks['fixture_still_running']=child.poll() is None
            # A regular game's window must retain focus and all input as well.
            from gametime.tracker import Alert
            win32.u.ShowWindowAsync(fixture,9); win32.u.SetForegroundWindow(fixture); pump(.2)
            assert win32.u.GetForegroundWindow()==fixture, 'Notification fixture needs focus'
            with patch.object(app,'notification_mode',return_value='normal'):
                checks['ordinary_notification_visible']=app.popup(Alert(datetime.now().date().isoformat(),(),'warning','Fixture reminder','OK'))
                pump(.15); popup_hwnd=int(app.popup_window.winId()); popup_style=get_style(popup_hwnd,-20)
                checks['ordinary_notification_keeps_focus']=win32.u.GetForegroundWindow()==fixture
                checks['ordinary_notification_input_transparent']=bool(popup_style & 0x20) and bool(popup_style & 0x08000000)
                app.dismiss_popup()
            # Reclassify only our own Form as a protected catalog entry. No
            # actual anti-cheat/game/account is launched to test this gate.
            protected=Game('steam:730','Renamed protected fixture','Steam',str(base))
            app.catalog.games[protected.id]=protected; app.catalog.rules[norm(exe)]=protected.id
            protected_target=running_window(app.catalog,protected.id)
            checks['protected_window_has_capture_restriction']=bool(protected_target and protected_target.restriction) and capture_window(protected_target) is None
            before=win32.u.GetForegroundWindow(); app._overlay_preview_game_id=protected.id
            app.preview_game_overlay(settings)
            checks['protected_preview_does_not_activate_or_present']=win32.u.GetForegroundWindow()==before and app._overlay_preview_until==0 and not app.overlay.isVisible() and app._overlay_backend=='none'
            app.overlay_consents.set(protected,True)
            win32.u.ShowWindowAsync(fixture,9); pump(.3)  # Only the synthetic Form.
            consented=running_window(app.catalog,protected.id)
            checks['consented_protected_fixture_capture_allowed']=consented is not None and not consented.blocked() and capture_window(consented) is not None
            app.overlay_consents.set(protected,False)
            checks['revoked_fixture_permission_rechecked']=consented is not None and consented.blocked() and capture_window(consented) is None
            # Normal OS reminders must leave the protected Form focused. Its
            # fullscreen/normal context is supplied explicitly, without RTSS.
            from gametime.tracker import Alert
            win32.u.SetForegroundWindow(fixture); pump(.2)
            assert win32.u.GetForegroundWindow()==fixture,'Passive notification needs its own focused fixture'
            warning=Alert(datetime.now().date().isoformat(),(),'warning','Protected fixture reminder','OK')
            with patch.object(win32,'desktop_overlay_available',return_value=True):
                checks['protected_passive_popup_visible']=app.popup(warning)
                pump(.15)
                checks['protected_popup_keeps_native_game_focus']=win32.u.GetForegroundWindow()==fixture
                popup_hwnd=int(app.popup_window.winId()); popup_style=get_style(popup_hwnd,-20)
                checks['notification_is_click_through_and_nonactivating']=bool(popup_style & 0x20) and bool(popup_style & 0x08000000)
                app.dismiss_popup()
            with patch.object(win32,'desktop_overlay_available',return_value=False),patch('gametime.sound.play_notification',return_value=True) as sound:
                checks['protected_fullscreen_audio_only']=app.popup(warning) and app.popup_window is None and sound.call_count==1
                checks['audio_only_keeps_native_game_focus']=win32.u.GetForegroundWindow()==fixture
            app.finish_restriction(str(exe),identity,datetime.now().date().isoformat());pump(.15)
            checks['protected_minimization_denied_without_separate_consent']=not win32.u.IsIconic(fixture)
            app.minimize_consents.set(protected,True)
            with patch.object(app,'restriction_notice'):app.finish_restriction(str(exe),identity,datetime.now().date().isoformat())
            pump(.2)
            checks['protected_minimization_requires_separate_consent']=bool(win32.u.IsIconic(fixture)) and child.poll() is None
            app.minimize_consents.set(protected,False)
        finally:
            stop.touch()
            if child: child.wait(timeout=10)
            app.close(); pump(.05); store.close()
    report={'checks':checks,'note':'Synthetic windowed Form only. Native game-client capture, explicit preview activation and cancellation on return to Hub verified. The fixture grants its test parent foreground permission. Cross-process hit-through and passive HUD focus preservation verified. Native minimization uses an explicitly supplied fixture foreground handle; production guards have separate tests. No real game/fullscreen trial or input injection.'}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report)); assert all(checks.values()),report

if __name__=='__main__':
    with patch('gametime.win32.s.Shell_NotifyIconW',return_value=True): run(Path(sys.argv[1]).resolve())
