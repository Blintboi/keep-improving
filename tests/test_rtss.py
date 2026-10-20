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
    def test_backend_clears_once_then_sleeps_until_resumed_or_closed(self):
        backend=Backend('C:/isolated/idle-rtss'); cleared=threading.Event()
        backend.process=Mock(); backend.process.poll.return_value=None
        def exchange(**request):
            if request.get('clear'): cleared.set()
            return {'available':True,'healthy':True}
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

    def test_automatic_rtss_is_default_but_countdown_still_opt_in_and_legacy_paths_load(self):
        self.assertTrue(Settings().overlay_rtss_auto); self.assertFalse(Settings().overlay_enabled)
        self.assertEqual(Settings().overlay_rtss_paths,[])
        with self.assertRaises(ValueError): replace(Settings(),overlay_rtss_auto='yes').validate()
        for paths in ('all',[None],['relative.exe'],[r'C:\game\setup.exe'],[r'C:\game\file.txt']):
            with self.subTest(paths=paths),self.assertRaises(ValueError): replace(Settings(),overlay_rtss_paths=paths).validate()
        replace(Settings(),overlay_rtss_paths=[r'C:\game\Stardew Valley.exe']).validate()

    def test_profile_changes_preserve_global_and_performance_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'Profiles').mkdir(); server=root/'RTSS.exe'; executable=root/'game.exe'; executable.touch()
            global_profile=root/'Profiles/Global'; global_profile.write_text('[Hooking]\nEnableHooking=0\n')
            target=root/'Profiles/game.exe.cfg'; target.write_text('[Framerate]\nLimit=144\n[Hooking]\nEnableHooking=0\n[OSD]\nEnableStat=1\nPositionX=-16\nPositionY=16\n')
            with patch('gametime.rtss.C.CDLL') as load: configure_profile(server,executable); load.return_value.UpdateProfiles.assert_called_once()
            text=target.read_text(); self.assertIn('Limit=144',text); self.assertIn('EnableHooking=1',text); self.assertIn('EnableStat=0',text)
            self.assertIn('CoordinateSpace=1',text)  # Whole framebuffer, never the game's last HUD viewport.
            self.assertIn('PositionX=-16',text); self.assertIn('PositionY=16',text)
            self.assertEqual(global_profile.read_text(),'[Hooking]\nEnableHooking=0\n')
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
        now=time.monotonic(); backend.result=('7:8',True,now,'')
        self.assertTrue(backend.present('C:/game/game.exe','7:8','00:20:00'))
        self.assertFalse(backend.present('C:/game/game.exe','7:9','00:20:00'))
        backend.result=('7:9',True,now-3,''); self.assertFalse(backend.present('C:/game/game.exe','7:9','00:20:00'))
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
