"""Anti-cheat policy and every active presentation entry point, with fixtures only."""
from dataclasses import replace
from datetime import datetime,date,timedelta
from contextlib import contextmanager
from types import SimpleNamespace
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from gametime.game_safety import SafetyPolicy,PROTECTED,UNCHECKED
from gametime.model import Game,Catalog,Settings,norm


class SafetyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.game=Game('fixture','Unlisted game','Steam',str(self.root))
        self.policy=SafetyPolicy()

    def test_known_games_cannot_be_renamed_or_reassigned_to_bypass_protection(self):
        for exe in ('CS2.exe','VALORANT-Win64-Shipping.exe','RainbowSix.exe','Destiny2.exe','TslGame.exe','R5Apex.exe'):
            with self.subTest(exe=exe): self.assertEqual(self.policy.reason(str(self.root/exe),self.game),PROTECTED)
        for game in (replace(self.game,id='steam:730'),replace(self.game,source='Riot'),replace(self.game,name='Fortnite')):
            self.assertEqual(self.policy.reason(str(self.root/'renamed.exe'),game),PROTECTED)

    def test_unlisted_game_with_anticheat_marker_is_blocked(self):
        for name in ('EasyAntiCheat','BattlEye','EAanticheat','AntiCheatExpert'):
            with self.subTest(name=name):
                folder=self.root/name; folder.mkdir()
                self.assertEqual(SafetyPolicy().reason(str(self.root/'renamed.exe'),self.game),PROTECTED)
                folder.rmdir()
        folder=self.root/'Binaries/Win64'; folder.mkdir(parents=True)
        (folder/'BECLIENT_X64.DLL').touch()
        self.assertEqual(self.policy.reason(str(folder/'opaque.exe'),self.game),PROTECTED)

    def test_bounded_inspection_fails_closed_and_rechecks_after_cache_expiry(self):
        self.assertEqual(self.policy.reason(str(self.root/'ordinary.exe'),self.game),'')
        (self.root/'EasyAntiCheat').mkdir()
        with patch('gametime.game_safety.time.monotonic',return_value=time.monotonic()+61):
            self.assertEqual(self.policy.reason(str(self.root/'ordinary.exe'),self.game),PROTECTED)
        with patch('gametime.game_safety.os.scandir',side_effect=PermissionError()):
            self.assertEqual(SafetyPolicy().reason(game=self.game),UNCHECKED)
        missing=replace(self.game,root=str(self.root/'missing'))
        self.assertEqual(self.policy.reason(game=missing),UNCHECKED)

    def test_cached_policy_does_not_repeatedly_read_hidden_game_installations(self):
        with patch.object(self.policy,'inspect',return_value='') as inspect:
            for _ in range(100): self.assertEqual(self.policy.reason(str(self.root/'ordinary.exe'),self.game),'')
            inspect.assert_called_once()

    def test_network_or_over_budget_inspection_never_enables_an_overlay(self):
        with patch('gametime.game_safety.os.scandir') as inspect:
            self.assertEqual(self.policy.reason(r'\\server\share\game.exe'),UNCHECKED)
            inspect.assert_not_called()
        @contextmanager
        def many_entries(_):
            yield iter(SimpleNamespace(name='unrelated-'+str(i)) for i in range(513))
        with patch('gametime.game_safety.os.scandir',side_effect=many_entries):
            self.assertEqual(SafetyPolicy().reason(game=self.game),UNCHECKED)

    def test_anticheat_services_are_never_games_even_with_an_exact_manual_rule(self):
        path=str(self.root/'BEService_x64.exe')
        catalog=Catalog(Settings(),[self.game],rules={norm(path):self.game.id})
        self.assertIsNone(catalog.resolve(path))
        self.assertTrue(catalog.explicitly_ignored(path))


@unittest.skipUnless(os.name=='nt','Windows required')
class NativeSafetyTests(unittest.TestCase):
    def test_capture_activation_and_escape_do_not_touch_a_protected_game(self):
        from gametime.game_preview import GameWindow,capture_window
        from gametime import win32
        target=GameWindow(123,456,r'C:\Game\cs2.exe','456:789','steam:730')
        with patch('gametime.game_preview.u.PrintWindow') as capture,patch('gametime.game_preview.u.SetForegroundWindow') as activate,patch.object(win32.u,'SendInput') as keys:
            self.assertIsNone(capture_window(target)); self.assertFalse(target.activate())
            self.assertFalse(win32.escape_game(target.path,target.identity))
            capture.assert_not_called(); activate.assert_not_called(); keys.assert_not_called()

    def test_old_rtss_hook_is_revoked_without_changing_performance_or_global_settings(self):
        from gametime.rtss import disable_profiles,configure_profile,position_profile
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); profiles=root/'Profiles'; profiles.mkdir()
            (profiles/'Global').write_text('[Hooking]\nEnableHooking=1\n')
            target=profiles/'cs2.exe.cfg'; target.write_text('[Hooking]\nEnableHooking=1\n[OSD]\nEnableOSD=1\n[Framerate]\nLimit=144\n')
            with patch('gametime.rtss.C.CDLL') as load:
                disable_profiles(root/'RTSS.exe',['cs2.exe']); load.return_value.UpdateProfiles.assert_called_once()
                self.assertIn('EnableHooking=0',target.read_text()); self.assertIn('EnableOSD=0',target.read_text()); self.assertIn('Limit=144',target.read_text())
                self.assertIn('EnableHooking=1',(profiles/'Global').read_text())
                original=target.read_bytes(); load.reset_mock()
                with self.assertRaises(ValueError): configure_profile(root/'RTSS.exe',root/'cs2.exe')
                with self.assertRaises(ValueError): position_profile(root/'RTSS.exe',root/'cs2.exe',16,16)
                self.assertEqual(target.read_bytes(),original); load.assert_not_called()

    def test_protected_rtss_never_launches_server_or_bridge_and_revokes_the_profile(self):
        from gametime.rtss import Backend
        backend=Backend('C:/isolated/anti-cheat')
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.disable_profiles') as disable,patch('gametime.rtss.configure_profile') as enable,patch('gametime.rtss.start_server') as start,patch.object(backend,'exchange') as exchange:
            try:
                self.assertFalse(backend.present('C:/Game/cs2.exe','7:8','timer'))
                deadline=time.monotonic()+2
                while not disable.called and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(disable.called); self.assertIn('cs2.exe',disable.call_args.args[1])
                backend.prepare(['C:/Game/cs2.exe']); self.assertEqual(backend.profiles,{})
                enable.assert_not_called(); start.assert_not_called(); exchange.assert_not_called(); self.assertIsNone(backend.process)
            finally: backend.close()

    def test_failed_profile_revocation_prevents_any_further_rtss_activation(self):
        from gametime.rtss import Backend
        backend=Backend('C:/isolated/failed-anti-cheat')
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.disable_profiles',side_effect=PermissionError('fixture')),patch('gametime.rtss.configure_profile') as enable,patch('gametime.rtss.start_server') as start,patch.object(backend,'exchange') as exchange:
            try:
                backend.protect(); deadline=time.monotonic()+2
                while not backend.protection_error and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(backend.protection_error)
                self.assertFalse(backend.present('C:/Game/ordinary.exe','7:8','timer'))
                self.assertFalse(backend.configure(Path('C:/fixture/RTSS.exe'),'C:/Game/ordinary.exe'))
                enable.assert_not_called(); start.assert_not_called(); exchange.assert_not_called()
            finally: backend.close()

    def test_shared_rtss_basename_cannot_reenable_a_revoked_cached_profile(self):
        from gametime.rtss import Backend
        backend=Backend('C:/isolated/basename-anti-cheat')
        with patch('gametime.rtss.installation',return_value=Path('C:/fixture/RTSS.exe')),patch('gametime.rtss.disable_profiles'),patch('gametime.rtss.configure_profile') as enable,patch.object(backend,'exchange') as exchange:
            try:
                backend.configured.add(norm('C:/other/shared.exe'))
                backend.protect(['C:/protected/shared.exe'])
                self.assertFalse(backend.configure(Path('C:/fixture/RTSS.exe'),'C:/other/shared.exe'))
                self.assertFalse(backend.present('C:/other/shared.exe','7:8','timer'))
                enable.assert_not_called(); exchange.assert_not_called()
            finally: backend.close()


if os.name=='nt':
    import test_qt_ui as fixtures

@unittest.skipUnless(os.name=='nt','Windows Qt required')
class ProtectedGameInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name=='nt' else classmethod(lambda cls:None)
    if os.name=='nt':
        setUp=fixtures.QtInterfaceTests.setUp; tearDown=fixtures.QtInterfaceTests.tearDown; pump=fixtures.QtInterfaceTests.pump

    def protected(self):
        game=replace(self.games[0],id='steam:730',name='Renamed game')
        self.app.catalog.games[game.id]=game; self.app.catalog.rules[norm(self.exe)]=game.id
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=True,
            game_overlays={game.id:{'overlay_enabled':True}})
        return game

    def test_enabled_global_and_custom_preferences_cannot_present_or_capture(self):
        from gametime.tracker import Sample
        game=self.protected(); target=Mock(path=str(self.exe),game_id=game.id)
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34')
        self.app.tracker.tick(current)
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.rtss,'present') as rtss,patch.object(self.app.overlay,'present') as desktop,patch('gametime.qt_ui.running_window',return_value=target),patch('gametime.qt_game_preview.running_window',return_value=target),patch.object(self.app.game_snapshots,'request') as snapshot:
            self.app.update_overlay(); self.assertFalse(self.app.overlay_timer.isActive())
            self.app.preview_overlay(); target.activate.assert_not_called()
            from PySide6.QtWidgets import QWidget
            self.app.show(); self.app.game_countdown_dialog(game.id); self.pump(.05)
            fields={w.accessibleName():w for w in self.app._dialogs[-1].findChildren(QWidget) if w.accessibleName()}
            picker=fields[self.app.t('Countdown position')]
            self.assertIsNone(picker.game_background)
            self.assertIn('Anticheat',picker._background_controller.status.text())
            rtss.assert_not_called(); desktop.assert_not_called(); snapshot.assert_not_called()
        self.assertEqual(self.store.settings().game_overlays,{})

    def test_warning_popup_still_works_without_automatic_escape(self):
        from gametime.tracker import Sample,Alert
        game=self.protected(); self.app.tracker.active=game; self.app.tracker.identity='12:34'
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34')
        alert=Alert(date.today().isoformat(),('warning:6000',),'warning','Warning','OK'); self.app.tracker._queue(alert)
        with patch('gametime.controller.win32.sample',return_value=current),patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.controller.win32.escape_game') as escape,patch.object(self.app,'popup',return_value=True) as popup:
            self.app.notify(alert); escape.assert_not_called(); popup.assert_called_once_with(alert)

    def test_protected_game_keeps_foreground_time_accounting(self):
        from gametime.tracker import Sample
        game=self.protected(); current=Sample(datetime.now().astimezone(),100,str(self.exe),'12:34')
        self.app.tracker.tick(current)
        self.app.tracker.tick(replace(current,wall=current.wall+timedelta(seconds=1),awake=101))
        self.app.tracker.flush()
        self.assertEqual(self.store.totals(current.wall.date())[game.id],1)

    def test_per_game_editor_explains_automatic_protection_and_disables_preview(self):
        from PySide6.QtWidgets import QPushButton
        game=self.protected(); self.app.game_countdown_dialog(game.id); window=self.app._dialogs[-1]
        preview=next(button for button in window.findChildren(QPushButton) if button.text()==self.app.t('Preview (10s)'))
        self.assertFalse(preview.isEnabled())
