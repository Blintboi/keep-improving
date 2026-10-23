"""Automatic RTSS routing uses isolated game fixtures and a mocked renderer."""
from dataclasses import replace
from datetime import datetime,timedelta
import os
import time
import unittest
from unittest.mock import patch
import test_overlay as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class AutomaticRTSSInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OverlayInterfaceTests.setUpClass.__func__)
    pump=fixtures.OverlayInterfaceTests.pump

    def setUp(self):
        self.backend_patch=patch('gametime.qt_ui.RTSSBackend',autospec=True); self.backend_patch.start()
        fixtures.OverlayInterfaceTests.setUp(self)
        self.backend=self.app.rtss; self.backend.identity=''; self.backend.error=''
        self.backend.configured=set(); self.backend.failed_paths=set(); self.backend.present.return_value=True
        self.backend.desktop_ready=True; self.backend.fallback_for.return_value=False
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True)
        self.app._rtss_checked=time.monotonic(); self.app._rtss_available=True

    def tearDown(self):
        try: fixtures.OverlayInterfaceTests.tearDown(self)
        finally: self.backend_patch.stop()

    def display(self,current):
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.foreground_screen_name',return_value=''):
            self.app.update_overlay()

    def test_non_protected_game_sources_route_to_rtss_without_a_manual_selection(self):
        from gametime.model import Game,norm
        from gametime.tracker import Sample
        start=datetime.now().astimezone()
        self.app.settings=replace(self.app.settings,overlay_rtss_paths=[str(self.base/'Stardew Valley.exe')])
        for number,source in enumerate(('Steam','Epic','Ubisoft','Minecraft','Kézi','Games')):
            root=self.base/str(number); root.mkdir(); executable=root/'OtherGame.exe'; executable.write_bytes(b'MZ fixture')
            game=Game('auto:'+str(number),'Automatic '+source,source,str(root))
            self.app.catalog.games[game.id]=game; self.app.catalog.rules[norm(executable)]=game.id
            current=Sample(start+timedelta(seconds=number),100+number,str(executable),str(number+10)+':1')
            self.app.tracker.tick(current); self.display(current)
            self.assertEqual(self.backend.present.call_args.args[:2],(str(executable),current.identity))
            self.assertEqual(self.app._overlay_backend,'rtss'); self.assertFalse(self.app.overlay.isVisible())
        self.assertEqual(self.backend.present.call_count,6)

    def test_profile_preparation_reuses_artwork_candidates_and_respects_exclusions(self):
        from gametime.model import Game,norm
        extra=self.base/'Additional.exe'; extra.write_bytes(b'MZ fixture')
        ignored=self.base/'Ignored.exe'; ignored.write_bytes(b'MZ fixture')
        setup=self.base/'setup.exe'; setup.write_bytes(b'MZ fixture')
        key=self.app.art.key(self.game)
        self.app.art.executables[key]=(str(extra),str(ignored),str(setup),'C:/Outside/Unknown.exe')
        self.app.catalog.rules[norm(extra)]=self.game.id
        self.app.catalog.rules[norm(ignored)]=None
        self.app.catalog.rules[norm(setup)]=self.game.id
        other=Game('excluded','Excluded','Steam',str(self.base/'Excluded'))
        self.app.catalog.games[other.id]=other; self.app.catalog.overrides[other.id]=False
        self.app.catalog.rules[norm(self.base/'Excluded'/'game.exe')]=other.id
        self.app.prepare_rtss_profiles()
        paths=set(self.backend.prepare.call_args.args[0])
        self.assertEqual({norm(path) for path in paths},{norm(self.exe),norm(extra)})
        self.backend.prepare.reset_mock(); self.app.catalog.overrides[self.game.id]=False
        self.app.prepare_rtss_profiles(); self.assertEqual(self.backend.prepare.call_args.args[0],[])

    def test_missing_rtss_uses_desktop_without_starting_a_worker(self):
        current=self.sample(); self.app.tracker.tick(current)
        self.app._rtss_available=False
        self.app.prepare_rtss_profiles(); self.display(current)
        self.backend.prepare.assert_not_called(); self.backend.present.assert_not_called()
        self.assertTrue(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'desktop')

    sample=fixtures.OverlayInterfaceTests.sample

    def test_unhealthy_rtss_keeps_desktop_only_after_confirmed_withdrawal(self):
        current=self.sample(); self.app.tracker.tick(current); self.backend.present.return_value=False
        self.backend.fallback_for.return_value=True
        self.display(current)
        self.assertTrue(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'desktop')
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.win32.desktop_overlay_available',return_value=False):
            self.assertFalse(self.app.overlay_warning_visible())
        self.display(replace(current,path='',identity='other:1'))
        self.backend.hide.assert_called_once(); self.assertFalse(self.app.overlay.isVisible())

    def test_desktop_is_hidden_before_any_asynchronous_rtss_publication(self):
        current=self.sample(); self.app.tracker.tick(current)
        self.app._rtss_available=False; self.display(current)
        self.assertTrue(self.app.overlay.isVisible())
        def publish(*args):
            self.assertFalse(self.app.overlay.isVisible())
            return False
        self.backend.present.side_effect=publish; self.backend.desktop_ready=False
        self.app._rtss_available=True; self.display(current)
        self.backend.present.assert_not_called()
        self.assertFalse(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'none')
        self.app._overlay_desktop_until=0  # The compositor guard interval has elapsed.
        self.display(current); self.backend.present.assert_called_once()
        with patch('gametime.qt_ui.win32.sample',return_value=current):
            self.assertFalse(self.app.overlay_warning_visible())
        self.backend.present.side_effect=None; self.backend.present.return_value=True
        self.display(current); self.assertEqual(self.app._overlay_backend,'rtss')

    def test_desktop_waits_for_rtss_removal_when_disabled_or_previewed(self):
        current=self.sample(); self.app.tracker.tick(current); self.display(current)
        self.backend.desktop_ready=False
        for preview in (False,True):
            self.app._overlay_preview_until=time.monotonic()+10 if preview else 0
            self.app.settings=replace(self.app.settings,overlay_rtss_auto=False)
            self.display(current)
            self.assertFalse(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'none')
        self.backend.desktop_ready=True; self.display(current)
        self.assertTrue(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'desktop')

    def test_lost_rtss_receipt_cannot_show_a_second_counter(self):
        current=self.sample(); self.app.tracker.tick(current); self.display(current)
        self.backend.present.return_value=False; self.backend.desktop_ready=False
        for _ in range(3):
            self.display(current)
            self.assertFalse(self.app.overlay.isVisible()); self.assertEqual(self.app._overlay_backend,'none')
        self.backend.desktop_ready=True; self.backend.fallback_for.return_value=True
        self.display(current); self.assertTrue(self.app.overlay.isVisible())
        with patch.object(self.app.overlay,'hide') as hide:
            self.display(current); hide.assert_not_called()

    def test_preview_and_disabled_mode_never_publish_to_rtss(self):
        current=self.sample(); self.app.tracker.tick(current)
        self.app._overlay_preview_until=time.monotonic()+10; self.display(current)
        self.backend.present.assert_not_called(); self.assertTrue(self.app.overlay.isVisible())
        self.app._overlay_preview_until=0
        self.app.settings=replace(self.app.settings,overlay_rtss_auto=False)
        self.display(current); self.backend.present.assert_not_called()
        self.app.prepare_rtss_profiles(); self.backend.prepare.assert_not_called()

    def test_untracked_excluded_locked_and_changed_process_never_publish(self):
        current=self.sample(); self.app.tracker.tick(current)
        for invalid in (replace(current,path='C:/Windows/notepad.exe'),replace(current,interactive=False),replace(current,identity='different:1')):
            self.display(invalid)
        self.backend.present.assert_not_called()
        self.app.catalog.overrides[self.game.id]=False; self.display(current)
        self.backend.present.assert_not_called(); self.assertFalse(self.app.overlay.isVisible())

    def test_automatic_mode_can_be_disabled_and_persists_without_erasing_legacy_data(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QCheckBox,QDialog,QPushButton
        self.app.settings=replace(self.app.settings,overlay_rtss_paths=[str(self.exe)])
        def save():
            dialog=self.app.findChild(QDialog)
            automatic=dialog.findChild(QCheckBox); automatic.setChecked(False)
            next(button for button in dialog.findChildren(QPushButton) if button.text()==self.app.t('Save')).click()
        QTimer.singleShot(20,save); self.app.rtss_dialog()
        saved=self.store.settings(); self.assertFalse(saved.overlay_rtss_auto)
        self.assertEqual(saved.overlay_rtss_paths,[str(self.exe)])
        self.backend.cancel_preparation.assert_called_once()
