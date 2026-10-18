"""Optional RTSS protocol and lifecycle regressions use isolated named mappings."""
from dataclasses import replace
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from gametime.model import Settings
from gametime.rtss import Backend, countdown, configure_profile, native_position, position_profile


@unittest.skipUnless(os.name == 'nt', 'Windows required')
class RTSSTests(unittest.TestCase):
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

    def test_settings_are_opt_in_and_invalid_paths_rejected(self):
        self.assertEqual(Settings().overlay_rtss_paths,[])
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

    def test_native_position_uses_signed_edge_anchors_and_profile_reload(self):
        values={}
        def set_property(name,pointer,size):
            self.assertEqual(size,4); values[name]=C.cast(pointer,C.POINTER(C.c_int32)).contents.value; return 1
        with patch('gametime.rtss.C.CDLL') as load:
            hooks=load.return_value; hooks.SetProfileProperty.side_effect=set_property
            position_profile(Path('C:/RTSS/RTSS.exe'),'C:/game/game.exe',-16,16)
            hooks.LoadProfile.assert_called_once_with(b'game.exe'); hooks.SaveProfile.assert_called_once_with(b'game.exe'); hooks.UpdateProfiles.assert_called_once()
        self.assertEqual(values,{b'PositionX':-16,b'PositionY':16,b'CoordinateSpace':1})

    def test_backend_does_not_start_until_selected_and_requires_current_receipt(self):
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
