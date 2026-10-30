"""Optional RTSS protocol and lifecycle regressions use isolated named mappings."""
from dataclasses import replace
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import threading
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from gametime.model import Settings
from gametime.rtss import Backend, countdown, configure_profile, native_position, position_profile,server_running,start_server


@unittest.skipUnless(os.name == 'nt', 'Windows required')
class RTSSTests(unittest.TestCase):
    def setUp(self):
        isolated=patch('gametime.rtss.process_running',return_value=False); isolated.start(); self.addCleanup(isolated.stop)

    def wait_for(self,predicate):
        deadline=time.monotonic()+3
        while not predicate() and time.monotonic()<deadline: time.sleep(.01)
        self.assertTrue(predicate())

    def test_rapid_return_to_same_game_discards_old_receipts_and_errors(self):
        for transition in ('alt-tab','game-switch'):
            for old_result in ('healthy','failure'):
                with self.subTest(transition=transition,old_result=old_result):
                    backend=Backend('C:/isolated/rapid-'+transition+'-'+old_result)
                    backend.process=Mock(); backend.process.poll.return_value=None
                    entered=threading.Event(); finish_old=threading.Event(); resumed=threading.Event(); finish_new=threading.Event()
                    publications=[]
                    def exchange(**request):
                        if request.get('clear'): return {'cleared':True,'available':True}
                        publications.append(request)
                        if len(publications)==1:
                            entered.set(); finish_old.wait(2)
                            if old_result=='failure': raise OSError('old foreground session')
                        else: resumed.set(); finish_new.wait(2)
                        return {'healthy':True,'available':True}
                    with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile'),patch.object(backend,'exchange',side_effect=exchange):
                        try:
                            backend.present('C:/fixture/game.exe','77:8','same text'); self.assertTrue(entered.wait(1))
                            if transition=='alt-tab': backend.hide()
                            else: backend.present('C:/fixture/other.exe','88:9','other text')
                            self.assertFalse(backend.present('C:/fixture/game.exe','77:8','same text'))
                            finish_old.set(); self.assertTrue(resumed.wait(2))
                            self.assertFalse(backend.result[1]); self.assertFalse(backend.desktop_ready)
                            self.assertFalse(backend.fallback_for('77:8'))
                            finish_new.set(); self.wait_for(lambda: backend.result[1])
                            self.assertEqual(backend.result[0],'77:8')
                        finally: finish_old.set(); finish_new.set(); backend.close()

    def test_cached_health_cannot_survive_game_a_b_a_without_a_new_receipt(self):
        backend=Backend('C:/isolated/cached-receipt'); backend.thread=Mock()
        backend.identity='77:8'; backend.result=('77:8',True,time.monotonic(),'')
        self.assertTrue(backend.present('C:/fixture/game.exe','77:8','timer'))
        self.assertFalse(backend.present('C:/fixture/other.exe','88:9','timer'))
        self.assertFalse(backend.present('C:/fixture/game.exe','77:8','timer'))

    def test_strict_receipt_does_not_reuse_countdown_for_new_image(self):
        backend=Backend('C:/isolated/strict-receipt'); backend.thread=Mock()
        old=('C:/fixture/game.exe','77:8','old countdown',None)
        backend.identity='77:8'; backend.state=old; backend.result=('77:8',True,time.monotonic(),''); backend._result_state=old
        self.assertFalse(backend.present(old[0],old[1],'new image',require_current=True))
        backend._result_state=backend.state
        self.assertTrue(backend.present(old[0],old[1],'new image',require_current=True))
        self.assertFalse(backend.present(old[0],old[1],'another image',require_current=True))
        self.assertFalse(backend.present(old[0],old[1],'new image',require_current=True))
        backend._result_state=backend.state
        self.assertTrue(backend.present(old[0],old[1],'new image',require_current=True))
        backend.hide(); self.assertIsNone(backend._result_state)

    def test_resume_during_removal_cannot_authorize_desktop_over_new_publication(self):
        backend=Backend('C:/isolated/resume-during-clear'); backend.process=Mock(); backend.process.poll.return_value=None
        clearing=threading.Event(); removed=threading.Event(); publishing=threading.Event(); finish=threading.Event()
        def exchange(**request):
            if request.get('clear'):
                clearing.set(); removed.wait(2); return {'cleared':True,'available':True}
            if request['identity']=='88:9': publishing.set(); finish.wait(2)
            return {'healthy':True,'available':True}
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile'),patch.object(backend,'exchange',side_effect=exchange):
            try:
                backend.present('C:/fixture/game.exe','77:8','timer'); self.wait_for(lambda: backend.result[1])
                backend.hide(); self.assertTrue(clearing.wait(1))
                self.assertFalse(backend.present('C:/fixture/other.exe','88:9','timer'))
                removed.set(); self.assertTrue(publishing.wait(1))
                self.assertFalse(backend.desktop_ready); self.assertFalse(backend.result[1])
                finish.set(); self.wait_for(lambda: backend.result[0]=='88:9' and backend.result[1])
            finally: removed.set(); finish.set(); backend.close()

    def test_cancelled_inflight_publish_waits_for_consumed_removal_and_discards_receipt(self):
        backend=Backend('C:/isolated/cancel-publish')
        publishing=threading.Event(); finish=threading.Event(); removing=threading.Event(); consumed=threading.Event()
        backend.process=Mock(); backend.process.poll.return_value=None
        def exchange(**request):
            if request.get('clear'):
                self.assertEqual(request['pid'],77); removing.set()
                return {'available':True,'cleared':consumed.is_set()}
            publishing.set(); finish.wait(2)
            return {'healthy':True,'available':True}
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile'),patch.object(backend,'exchange',side_effect=exchange):
            try:
                backend.present('C:/fixture/game.exe','77:8','timer'); self.assertTrue(publishing.wait(1))
                backend.hide(); self.assertFalse(backend.desktop_ready)
                finish.set(); self.assertTrue(removing.wait(1))
                self.assertFalse(backend.desktop_ready); self.assertFalse(backend.result[1])
                consumed.set(); self.wait_for(lambda: backend.desktop_ready)
                self.assertFalse(backend.result[1]); self.assertEqual(backend.identity,'')
            finally: finish.set(); consumed.set(); backend.close()

    def test_fallback_waits_for_clear_and_stays_on_desktop_until_foreground_session_changes(self):
        backend=Backend('C:/isolated/unhealthy-fallback')
        publishing=threading.Event(); finish=threading.Event(); removing=threading.Event(); consumed=threading.Event()
        backend.process=Mock(); backend.process.poll.return_value=None
        def exchange(**request):
            if request.get('clear'):
                removing.set(); return {'available':True,'cleared':consumed.is_set()}
            publishing.set(); finish.wait(2); return {'available':True,'healthy':False}
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile'),patch.object(backend,'exchange',side_effect=exchange) as calls:
            try:
                backend.present('C:/fixture/game.exe','77:8','timer'); self.assertTrue(publishing.wait(1))
                with backend.condition: backend._unhealthy_since=time.monotonic()-2
                finish.set(); self.assertTrue(removing.wait(1)); self.assertFalse(backend.desktop_ready)
                consumed.set(); self.wait_for(lambda: backend.fallback_for('77:8'))
                count=calls.call_count
                for number in range(3):
                    self.assertFalse(backend.present('C:/fixture/game.exe','77:8',str(number)))
                    self.assertTrue(backend.desktop_ready); time.sleep(.1)
                self.assertEqual(calls.call_count,count)
                self.assertFalse(backend.fallback_for('77:9'))
                backend.present('C:/fixture/game.exe','77:9','timer'); self.assertFalse(backend.desktop_ready)
                self.wait_for(lambda: calls.call_count>count)
            finally: finish.set(); consumed.set(); backend.close()

    def test_failed_or_busy_clear_never_authorizes_desktop(self):
        backend=Backend('C:/isolated/failed-clear'); backend.thread=Mock()
        backend.state=('C:/fixture/game.exe','77:8','timer',None); backend.identity='77:8'
        backend._published_pid=77; backend._withdrawn=False
        backend.hide(); self.assertFalse(backend.desktop_ready)
        backend.process=Mock(); backend.process.poll.return_value=None
        clear=threading.Event(); recover=threading.Event()
        def exchange(**request):
            clear.set()
            if not recover.is_set(): raise OSError('isolated IPC failure')
            return {'available':True,'cleared':True}
        with patch.object(backend,'exchange',side_effect=exchange):
            backend.thread=threading.Thread(target=backend.run,daemon=True); backend.thread.start()
            try:
                self.assertTrue(clear.wait(1)); self.assertFalse(backend.desktop_ready)
                recover.set(); self.wait_for(lambda: backend.desktop_ready)
            finally: recover.set(); backend.close()

    def test_delayed_hook_recovers_in_same_game_only_after_explicit_guarded_retry(self):
        backend=Backend('C:/isolated/delayed-hook'); hooked=threading.Event()
        backend.process=Mock(); backend.process.poll.return_value=None
        def exchange(**request):
            return {'available':True,'cleared':True,'healthy':hooked.is_set()}
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile'),patch.object(backend,'exchange',side_effect=exchange) as calls:
            try:
                backend.present('C:/fixture/game.exe','77:8','timer')
                self.wait_for(lambda: backend._unhealthy_since is not None)
                with backend.condition: backend._unhealthy_since=time.monotonic()-2
                self.wait_for(lambda: backend.fallback_for('77:8'))
                count=calls.call_count; hooked.set()
                self.assertFalse(backend.retry_due('77:8'))
                backend.present('C:/fixture/game.exe','77:8','timer',retry=True)
                time.sleep(.1); self.assertEqual(calls.call_count,count)
                with backend.condition: backend._retry_at=time.monotonic()-1
                self.assertTrue(backend.retry_due('77:8'))
                backend.present('C:/fixture/game.exe','77:8','timer')
                time.sleep(.1); self.assertEqual(calls.call_count,count)
                backend.present('C:/fixture/game.exe','77:8','timer',retry=True)
                self.wait_for(lambda: backend.result[1])
                self.assertTrue(backend.present('C:/fixture/game.exe','77:8','timer'))
                self.assertFalse(backend.fallback_for('77:8')); self.assertEqual(backend._retry_count,0)
            finally: backend.close()

    def test_backend_clears_once_then_sleeps_until_resumed_or_closed(self):
        backend=Backend('C:/isolated/idle-rtss'); cleared=threading.Event()
        backend.process=Mock(); backend.process.poll.return_value=None
        def exchange(**request):
            if request.get('clear'): cleared.set()
            return {'available':True,'healthy':True,'cleared':True}
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')), \
             patch('gametime.rtss.configure_profile'), patch.object(backend,'exchange',side_effect=exchange) as calls:
            try:
                backend.present('C:/fixture/game.exe','7:8','00:20:00')
                deadline=time.monotonic()+2
                while not backend.result[1] and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(backend.result[1])
                backend.hide(); self.assertTrue(cleared.wait(1))
                for _ in range(3): backend.hide(); time.sleep(.15)
                self.assertEqual(sum(bool(call.kwargs.get('clear')) for call in calls.call_args_list),1)
                backend.present('C:/fixture/game.exe','7:9','00:19:59')
                deadline=time.monotonic()+2
                while backend.result[0]!='7:9' and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(backend.result[0],'7:9'); self.assertTrue(backend.result[1])
            finally: backend.close()
            self.assertFalse(backend.thread.is_alive())

    def test_native_protocol_bounds_ownership_lock_and_acknowledgement(self):
        root=Path(__file__).resolve().parents[1]
        subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',
            '. ./common.ps1; Build-GameTimeRTSSBridge $PWD.Path'],cwd=root,check=True,capture_output=True,timeout=30)
        result=subprocess.run([str(root/'gametime/rtss_bridge.exe'),'--self-test'],check=True,capture_output=True,text=True,timeout=10)
        self.assertIn('self-test passed',result.stdout)

    def test_text_only_countdown_color_opacity_position_and_expiry(self):
        text=countdown(1199.1,False,.9)
        self.assertIn('00:20:00',text); self.assertIn('<C=E6FFFFFF>',text); self.assertNotIn('<P',text)
        self.assertNotIn('<B',text)
        red=countdown(-1,True,.25)
        self.assertIn('00:00:00',red); self.assertIn('<C=40FF5C65>',red)
        self.assertEqual(native_position(1,0,1920,1080),(-16,16))
        self.assertEqual(native_position(.5,.5,1920,1080),(876,519))
        self.assertEqual(native_position(0,1,1280,720),(16,-16))

    def test_text_size_changes_font_and_interior_position_but_keeps_edge_anchors(self):
        self.assertIn('<FNT=Consolas,-33,700,1>',countdown(1200,False,1))
        for size,height in ((8,11),(36,48),(72,96)):
            text=countdown(1200,True,.5,size)
            self.assertIn(f'<FNT=Consolas,-{height},700,1>',text); self.assertIn('00:20:00',text)
            self.assertEqual(native_position(1,0,1920,1080,size),(-16,16))
        self.assertLess(native_position(.5,.5,1920,1080,72)[0],native_position(.5,.5,1920,1080,8)[0])

    def test_worker_repositions_for_size_changes_and_reuses_unchanged_profiles(self):
        backend=Backend('C:/isolated/font-size')
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.configure_profile') as configure,patch('gametime.rtss.position_profile') as position,patch.object(backend,'exchange',return_value={'healthy':True,'available':True,'width':1920,'height':1080}):
            try:
                backend.present('C:/fixture/game.exe','7:8','timer',(.5,.5,1920,1080))  # Legacy four-field position.
                deadline=time.monotonic()+2
                while not backend.result[1] and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(backend.result[1]); self.assertEqual(position.call_args.args[2:],native_position(.5,.5,1920,1080))
                backend.present('C:/fixture/game.exe','7:8','large timer',(.5,.5,1920,1080,72))
                deadline=time.monotonic()+2
                while position.call_count<2 and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(position.call_count,2); self.assertEqual(position.call_args.args[2:],native_position(.5,.5,1920,1080,72))
                time.sleep(.25); self.assertEqual(position.call_count,2); configure.assert_called_once()
            finally: backend.close()

    def test_automatic_rtss_and_countdown_are_opt_in_and_legacy_paths_load(self):
        self.assertFalse(Settings().overlay_rtss_auto); self.assertFalse(Settings().overlay_enabled)
        self.assertEqual(Settings().overlay_rtss_paths,[])
        with self.assertRaises(ValueError): replace(Settings(),overlay_rtss_auto='yes').validate()
        for paths in ('all',[None],['relative.exe'],[r'C:\game\setup.exe'],[r'C:\game\file.txt']):
            with self.subTest(paths=paths),self.assertRaises(ValueError): replace(Settings(),overlay_rtss_paths=paths).validate()
        replace(Settings(),overlay_rtss_paths=[r'C:\game\Stardew Valley.exe']).validate()

    def test_profile_changes_preserve_global_and_performance_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'Profiles').mkdir(); server=root/'RTSS.exe'; executable=root/'game.exe'; executable.touch()
            global_profile=root/'Profiles/Global'; global_profile.write_text('[Hooking]\nEnableHooking=0\nInjectionDelay=15000\n')
            target=root/'Profiles/game.exe.cfg'; target.write_text('[Framerate]\nLimit=144\n[Hooking]\nEnableHooking=0\nInjectionDelay=15000\n[OSD]\nEnableStat=1\nPositionX=-16\nPositionY=16\n')
            with patch('gametime.rtss.C.CDLL') as load: configure_profile(server,executable); load.return_value.UpdateProfiles.assert_called_once()
            text=target.read_text(); self.assertIn('Limit=144',text); self.assertIn('EnableHooking=1',text); self.assertIn('EnableStat=0',text)
            self.assertIn('CoordinateSpace=1',text)  # Whole framebuffer, never the game's last HUD viewport.
            self.assertIn('PositionX=-16',text); self.assertIn('PositionY=16',text)
            self.assertIn('InjectionDelay=0',text)
            self.assertEqual(global_profile.read_text(),'[Hooking]\nEnableHooking=0\nInjectionDelay=15000\n')
            before=target.read_bytes(); modified=target.stat().st_mtime_ns
            with patch('gametime.rtss.C.CDLL') as load: configure_profile(server,executable); load.assert_not_called()
            self.assertEqual(target.read_bytes(),before); self.assertEqual(target.stat().st_mtime_ns,modified)

    def test_automatic_profile_preparation_is_cached_idle_and_starts_server_once(self):
        backend=Backend('C:/isolated/automatic')
        paths=['C:/fixture/Alpha.exe','C:/fixture/Beta.exe']
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')), \
             patch('gametime.rtss.configure_profile') as configure, \
             patch('gametime.rtss.server_running',return_value=False),patch('gametime.rtss.start_server') as start:
            try:
                backend.prepare([*paths,*paths,'C:/fixture/setup.exe','C:/fixture/steam.exe','relative.exe'])
                deadline=time.monotonic()+2
                while len(backend.configured)<2 and time.monotonic()<deadline: time.sleep(.01)
                self.assertEqual(configure.call_count,2); start.assert_called_once()
                self.assertIsNone(backend.process); self.assertIsNone(backend.state)
                backend.prepare(paths); time.sleep(.25); self.assertEqual(configure.call_count,2)
            finally: backend.close()
            self.assertFalse(backend.thread.is_alive())

    def test_sdk_mapping_check_closes_handle_without_starting_any_process(self):
        with patch('gametime.rtss.C.WinDLL') as load:
            kernel=load.return_value; kernel.OpenFileMappingW.return_value=42
            self.assertTrue(server_running()); kernel.CloseHandle.assert_called_once_with(42)
            kernel.OpenFileMappingW.return_value=None
            self.assertFalse(server_running()); kernel.CloseHandle.assert_called_once_with(42)

    def test_server_launch_uses_existing_privileges_without_changing_parent_environment(self):
        before=dict(os.environ)
        with patch('gametime.rtss.subprocess.Popen') as launch:
            start_server(Path('C:/fixture/RTSS.exe'))
        self.assertEqual(dict(os.environ),before)
        self.assertEqual(launch.call_args.kwargs['env']['__COMPAT_LAYER'],'RunAsInvoker')
        self.assertFalse(launch.call_args.kwargs.get('shell',False))

    def test_failed_server_start_is_also_throttled(self):
        backend=Backend('C:/isolated/start-failure')
        with patch('gametime.rtss.server_running',return_value=False), \
             patch('gametime.rtss.start_server',side_effect=OSError('fixture')) as launch, \
             patch('gametime.rtss.time.monotonic',side_effect=[100,101,111]):
            with self.assertRaises(OSError): backend.ensure_server(Path('C:/fixture/RTSS.exe'))
            backend.ensure_server(Path('C:/fixture/RTSS.exe'))
            with self.assertRaises(OSError): backend.ensure_server(Path('C:/fixture/RTSS.exe'))
        self.assertEqual(launch.call_count,2)

    def test_missing_sdk_never_relaunches_a_running_or_uninspectable_server(self):
        for running in (True,None):
            backend=Backend('C:/isolated/already-running')
            with self.subTest(running=running),patch('gametime.rtss.server_running',return_value=False),patch('gametime.rtss.process_running',return_value=running) as inspect,patch('gametime.rtss.start_server') as launch,patch('gametime.rtss.time.monotonic',side_effect=[100,101,102,111]):
                for _ in range(4): backend.ensure_server(Path('C:/fixture/RTSS.exe'))
                launch.assert_not_called(); self.assertEqual(inspect.call_count,2)

    def test_server_can_restart_after_exit_but_not_while_mapping_is_temporarily_missing(self):
        backend=Backend('C:/isolated/server-exit')
        with patch('gametime.rtss.server_running',return_value=False),patch('gametime.rtss.process_running',side_effect=[True,False,True]) as inspect,patch('gametime.rtss.start_server') as launch,patch('gametime.rtss.time.monotonic',side_effect=[100,101,111,112,122]):
            for _ in range(5): backend.ensure_server(Path('C:/fixture/RTSS.exe'))
            launch.assert_called_once_with(Path('C:/fixture/RTSS.exe')); self.assertEqual(inspect.call_count,3)

    def test_available_sdk_skips_process_enumeration_and_launch(self):
        backend=Backend('C:/isolated/mapping-ready')
        with patch('gametime.rtss.server_running',return_value=True),patch('gametime.rtss.process_running') as inspect,patch('gametime.rtss.start_server') as launch:
            backend.ensure_server(Path('C:/fixture/RTSS.exe')); inspect.assert_not_called(); launch.assert_not_called()

    def test_native_position_uses_signed_edge_anchors_and_profile_reload(self):
        values={}
        def set_property(name,pointer,size):
            self.assertEqual(size,4); values[name]=C.cast(pointer,C.POINTER(C.c_int32)).contents.value; return 1
        with patch('gametime.rtss.C.CDLL') as load:
            hooks=load.return_value; hooks.SetProfileProperty.side_effect=set_property
            position_profile(Path('C:/RTSS/RTSS.exe'),'C:/game/game.exe',-16,16)
            hooks.LoadProfile.assert_called_once_with(b'game.exe'); hooks.SaveProfile.assert_called_once_with(b'game.exe'); hooks.UpdateProfiles.assert_called_once()
        self.assertEqual(values,{b'PositionX':-16,b'PositionY':16,b'CoordinateSpace':1})

    def test_backend_is_lazy_and_requires_current_receipt(self):
        backend=Backend('C:/isolated/profile'); self.assertIsNone(backend.thread)
        # Supply a dormant thread so this policy test never starts RTSS.
        backend.thread=Mock()
        now=time.monotonic(); backend.identity='7:8'; backend.result=('7:8',True,now,'')
        self.assertTrue(backend.present('C:/game/game.exe','7:8','00:20:00'))
        self.assertFalse(backend.present('C:/game/game.exe','7:9','00:20:00'))
        backend.result=('7:9',True,now-3,''); self.assertFalse(backend.present('C:/game/game.exe','7:9','00:20:00'))
        backend.result=('7:9',True,time.monotonic(),''); backend._fallback_identity='7:9'
        self.assertFalse(backend.present('C:/game/game.exe','7:9','00:20:00'))
        self.assertTrue(backend.desktop_ready)
        backend.hide(); self.assertIsNone(backend.state); self.assertEqual(backend.identity,'')

    def test_bridge_missing_server_does_not_create_a_mapping(self):
        # The native fixture covers absence of a hook independently of whether
        # this developer PC happens to have an RTSS server running.
        backend=Backend('C:/isolated/no-rtss')
        with patch('gametime.rtss.installation',return_value=None):
            backend.present('C:/game/game.exe','7:9','00:20:00')
            deadline=time.monotonic()+2
            while backend.result[3]=='' and time.monotonic()<deadline: time.sleep(.01)
            self.assertFalse(backend.result[1]); self.assertIn('Install RTSS',backend.result[3]); self.assertIsNone(backend.process)
            backend.close()
