"""Countdown transition sequences use temporary profiles and isolated renderers."""
from dataclasses import replace
import os
import time
import unittest
from unittest.mock import Mock,patch
import test_rtss_auto as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class CountdownTransitionTests(unittest.TestCase):
    setUpClass=fixtures.AutomaticRTSSInterfaceTests.__dict__['setUpClass']
    pump=fixtures.AutomaticRTSSInterfaceTests.pump
    sample=fixtures.AutomaticRTSSInterfaceTests.sample
    display=fixtures.AutomaticRTSSInterfaceTests.display
    tearDown=fixtures.AutomaticRTSSInterfaceTests.tearDown

    def setUp(self):
        from PySide6.QtCore import QObject,QEvent
        from gametime.model import Game,norm
        fixtures.AutomaticRTSSInterfaceTests.setUp(self)
        root=self.base/'second'; root.mkdir(); self.other_exe=root/'second.exe'; self.other_exe.write_bytes(b'MZ fixture')
        self.other=Game('second:fixture','Second fixture','Kézi',str(root))
        self.app.catalog.games[self.other.id]=self.other; self.app.catalog.rules[norm(self.other_exe)]=self.other.id
        self.events=[]
        events=self.events
        class Visibility(QObject):
            def eventFilter(me,obj,event):
                if event.type() in (QEvent.Show,QEvent.Hide): events.append(event.type().name)
                return False
        self.visibility=Visibility(self.app.overlay); self.app.overlay.installEventFilter(self.visibility)

    def frame(self,current,tracked=False):
        if tracked: self.app.tracker.tick(current)
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.foreground_screen_name',return_value=''):
            self.app.update_overlay(); self.qt.processEvents()
        self.app.overlay_timer.stop()

    def target(self,current):
        return Mock(path=current.path,identity=current.identity,game_id=self.game.id,hwnd=123,
                    matches=Mock(return_value=True),activate=Mock(return_value=True))

    def preview(self,current,target):
        with patch('gametime.qt_ui.running_window',return_value=target),patch('gametime.qt_ui.win32.sample',return_value=current),patch('gametime.qt_ui.foreground_screen_name',return_value=''),patch('gametime.qt_ui.win32.u.IsIconic',return_value=False):
            self.app.preview_game_overlay(self.app.settings); self.qt.processEvents()
        self.app.overlay_timer.stop()

    def test_desktop_alt_tab_and_game_switch_show_once_per_foreground_visit(self):
        self.app.settings=replace(self.app.settings,overlay_rtss_auto=False,
            game_overlays={self.other.id:{'overlay_color_normal':'#12ab34','overlay_font_size':36}})
        first=self.sample(); second=replace(first,path=str(self.other_exe),identity='88:9')
        away=replace(first,path='C:/Windows/notepad.exe',identity='outside:1')
        self.frame(first,tracked=True)
        for _ in range(12): self.frame(first)
        self.assertEqual(self.events,['Show'])
        for _ in range(6): self.frame(away)
        self.assertEqual(self.events,['Show','Hide'])
        self.frame(away,tracked=True); self.frame(first,tracked=True)
        for _ in range(12): self.frame(first)
        self.assertEqual(self.events,['Show','Hide','Show'])
        for _ in range(6): self.frame(second)  # Wait for accounting to validate the new game.
        self.frame(second,tracked=True)
        for _ in range(12): self.frame(second)
        self.assertEqual(self.events,['Show','Hide','Show','Hide','Show'])
        self.assertEqual(self.app.overlay.color,'#12ab34'); self.assertEqual(self.app.overlay.font_size,36)
        self.backend.present.assert_not_called()

    def test_rtss_alt_tab_and_game_switch_never_flash_desktop(self):
        first=self.sample(); second=replace(first,path=str(self.other_exe),identity='88:9')
        away=replace(first,path='C:/Windows/notepad.exe',identity='outside:1')
        for _ in range(8):
            self.frame(first,tracked=True); self.frame(away); self.frame(first,tracked=True)
            self.frame(second); self.frame(second,tracked=True)
            self.assertEqual(self.app._overlay_backend,'rtss')
            self.assertEqual(self.backend.present.call_args.args[:2],(second.path,second.identity))
        self.assertEqual(self.events,[]); self.assertFalse(self.app.overlay.isVisible())

    def test_repeated_desktop_preview_on_off_updates_one_window_in_place(self):
        self.app.settings=replace(self.app.settings,overlay_rtss_auto=False)
        current=self.sample(); self.frame(current,tracked=True); target=self.target(current)
        hwnd=self.app.overlay.winId(); previous=self.app.tracker.previous; stored=self.store.settings()
        for _ in range(10):
            self.preview(current,target); self.assertTrue(self.app.overlay.preview)
            self.app._overlay_preview_until=0; self.frame(current)
            self.assertFalse(self.app.overlay.preview); self.assertEqual(self.app.overlay.winId(),hwnd)
        self.assertEqual(self.events,['Show']); self.assertEqual(self.store.settings(),stored)
        self.assertIs(self.app.tracker.previous,previous)

    def test_repeated_rtss_preview_on_off_does_not_clear_or_switch_renderer(self):
        current=self.sample(); self.frame(current,tracked=True); target=self.target(current)
        for _ in range(10):
            self.preview(current,target); self.assertEqual(self.app._overlay_backend,'rtss')
            self.app._overlay_preview_until=0; self.frame(current)
            self.assertEqual(self.app._overlay_backend,'rtss')
        self.backend.hide.assert_not_called(); self.assertEqual(self.events,[])

    def test_preview_alt_tab_then_other_game_cannot_restore_demo(self):
        current=self.sample(); self.frame(current,tracked=True); target=self.target(current)
        self.preview(current,target); target.matches.return_value=False
        away=replace(current,path='C:/Windows/notepad.exe',identity='outside:1')
        self.frame(away)
        self.assertEqual(self.app._overlay_preview_until,0); self.assertIsNone(self.app._overlay_preview_target)
        self.backend.present.reset_mock()
        second=replace(current,path=str(self.other_exe),identity='88:9')
        self.frame(second,tracked=True)
        self.assertEqual(self.backend.present.call_args.args[:2],(second.path,second.identity))
        for _ in range(10): self.frame(second)
        self.assertEqual(self.events,[]); target.activate.assert_called_once()

    def test_pending_and_late_receipts_do_not_toggle_desktop(self):
        current=self.sample(); self.frame(current,tracked=True)
        self.backend.desktop_ready=False; self.backend.present.return_value=False
        for _ in range(10): self.frame(current)
        self.assertEqual(self.app._overlay_backend,'none'); self.assertEqual(self.events,[])
        self.backend.present.return_value=True
        for _ in range(10): self.frame(current)
        self.assertEqual(self.app._overlay_backend,'rtss'); self.assertEqual(self.events,[])

    def test_retry_hides_desktop_and_observes_compositor_guard_before_publication(self):
        current=self.sample(); self.backend.present.return_value=False
        self.backend.fallback_for.return_value=True
        self.frame(current,tracked=True); self.assertTrue(self.app.overlay.isVisible())
        self.backend.present.reset_mock(); self.backend.retry_due.return_value=True
        self.frame(current); self.assertFalse(self.app.overlay.isVisible())
        self.backend.present.assert_not_called()
        deadline=self.app._overlay_desktop_until
        with patch('gametime.qt_ui.time.monotonic',return_value=deadline-.01): self.frame(current)
        self.backend.present.assert_not_called()
        self.backend.desktop_ready=False
        with patch('gametime.qt_ui.time.monotonic',return_value=deadline+.01): self.frame(current)
        self.assertTrue(self.backend.present.call_args.kwargs['retry'])
        self.assertFalse(self.app.overlay.isVisible())
        self.backend.present.return_value=True; self.backend.fallback_for.return_value=False
        with patch('gametime.qt_ui.time.monotonic',return_value=deadline+.1): self.frame(current)
        self.assertEqual(self.app._overlay_backend,'rtss')

    def test_rapid_callbacks_cannot_skip_the_compositor_guard(self):
        current=self.sample(); self.app._rtss_available=False; self.frame(current,tracked=True)
        self.app._rtss_available=True; self.frame(current)
        deadline=time.monotonic()+.2
        with patch('gametime.qt_ui.time.monotonic',return_value=deadline-.01):
            for _ in range(20): self.frame(current)
        self.backend.present.assert_not_called(); self.assertEqual(self.events,['Show','Hide'])
        with patch('gametime.qt_ui.time.monotonic',return_value=deadline+.01): self.frame(current)
        self.backend.present.assert_called_once(); self.assertEqual(self.events,['Show','Hide'])

    def test_preview_stopped_while_withdrawal_pending_never_flashes_desktop(self):
        current=self.sample(); self.frame(current,tracked=True)
        self.backend.desktop_ready=False
        self.app._overlay_preview_until=time.monotonic()+10; self.app._overlay_preview_target=None
        self.frame(current); self.assertEqual(self.app._overlay_backend,'none')
        self.app._overlay_preview_until=0; self.frame(current)
        self.assertEqual(self.app._overlay_backend,'rtss'); self.assertEqual(self.events,[])
