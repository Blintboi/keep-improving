"""Game-only captures, single-shot focus and local palette isolation."""
from dataclasses import replace
from datetime import datetime,date
import os
import threading
import time
import unittest
from unittest.mock import patch,Mock
from gametime.model import Settings
from gametime.schedule import game_settings
from gametime.tracker import Sample
import test_qt_ui as fixtures


class GamePaletteTests(unittest.TestCase):
    def test_colors_inherit_independently_and_validate_nested_profiles(self):
        settings=replace(Settings(),overlay_color_warning='#ab1234',game_overlays={'a':{'overlay_color_normal':'#12ab34'}}).validate()
        self.assertEqual(game_settings(settings,'a').overlay_color_warning,'#ab1234')
        self.assertEqual(game_settings(settings,'b').overlay_color_normal,'#ffffff')
        for color in ('red','#abc','#ffffff00',None,'<C=123456>'):
            with self.subTest(color=color),self.assertRaises(ValueError):
                replace(settings,game_overlays={'a':{'overlay_color_warning':color}}).validate()


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class GamePreviewTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
    setUp=fixtures.QtInterfaceTests.setUp
    tearDown=fixtures.QtInterfaceTests.tearDown
    pump=fixtures.QtInterfaceTests.pump

    def target(self):
        return Mock(hwnd=123,pid=456,path=str(self.exe),identity='fixture:1',game_id=self.games[0].id,
                    **{'activate.return_value':True,'valid.return_value':True,'matches.return_value':True})

    def countdown_fields(self):
        from PySide6.QtWidgets import QWidget
        self.app.show(); self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        fields={w.accessibleName():w for w in window.findChildren(QWidget) if w.accessibleName()}
        fields[self.app.t('Hide this countdown')].setChecked(False)
        return window,fields

    def test_explicit_preview_uses_live_rtss_draft_palette_and_alt_tab_clears_it(self):
        target=self.target(); current=Sample(datetime.now().astimezone(),100,str(self.exe),target.identity)
        self.app._overlay_preview_game_id=self.games[0].id; self.app._overlay_game_preview_state='normal'
        settings=replace(self.app.settings,overlay_rtss_auto=True,overlay_color_normal='#12ab34',overlay_color_warning='#bc56ef')
        with patch('gametime.qt_ui.running_window',return_value=target) as find,patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
            self.app.preview_game_overlay(settings)
            find.assert_called_once_with(self.app.catalog,self.games[0].id); target.activate.assert_called_once()
            self.assertIn('12AB34',present.call_args.args[2]); self.assertEqual(self.app._overlay_backend,'rtss')
            self.assertEqual(self.app._overlay_identity,''); self.assertFalse(self.app.overlay.isVisible())
            self.app._overlay_game_preview_state='warning'; self.app.update_overlay(); self.assertIn('BC56EF',present.call_args.args[2])
            target.matches.return_value=False
            with patch.object(self.app.rtss,'hide') as hide:
                self.app.update_overlay(); hide.assert_called_once(); self.assertEqual(self.app._overlay_preview_until,0)
                self.app.update_overlay(); self.assertFalse(self.app.overlay_timer.isActive())
            target.activate.assert_called_once()
        self.assertEqual(self.store.totals(date.today()),{}); self.assertEqual(self.store.alert_keys(date.today()),set())
        self.assertEqual(self.store.settings().game_overlays,{})

    def test_unavailable_focus_never_presents_or_retries_and_no_game_stays_on_desktop(self):
        self.app.overlay_enabled.setChecked(True); target=self.target(); target.activate.return_value=False
        with patch('gametime.qt_ui.running_window',return_value=target),patch('gametime.qt_ui.win32.sample') as sample,patch.object(self.app.overlay,'present') as present:
            self.app.preview_overlay(); sample.assert_not_called(); present.assert_not_called(); self.assertEqual(self.app._overlay_preview_until,0)
        with patch('gametime.qt_ui.running_window',return_value=None),patch.object(self.app.rtss,'present') as rtss,patch.object(self.app.overlay,'present') as present:
            self.app.preview_overlay(); self.assertTrue(present.called); rtss.assert_not_called(); self.assertIsNone(self.app._overlay_preview_target)

    def test_expiry_returns_to_real_playtime_and_saved_colors(self):
        target=self.target(); current=Sample(datetime.now().astimezone(),100,str(self.exe),target.identity)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True,overlay_rtss_auto=False,overlay_color_normal='#112233')
        self.app.tracker.active=self.games[0]; self.app.tracker.identity=current.identity
        self.app.tracker.cache[current.wall.date().isoformat()]={self.games[0].id:123}
        with patch('gametime.qt_ui.running_window',return_value=target),patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.overlay,'present') as present:
            self.app.preview_game_overlay(replace(self.app.settings,overlay_color_normal='#aabbcc'))
            self.assertEqual(present.call_args.args[2].overlay_color_normal,'#aabbcc')
            self.app._overlay_preview_until=0; self.app.update_overlay()
            self.assertEqual(present.call_args.args[:2],(7077,123)); self.assertEqual(present.call_args.args[2].overlay_color_normal,'#112233')
            self.assertIsNone(self.app._overlay_preview_target)

    def test_hung_capture_has_one_worker_and_bounded_shutdown(self):
        worker=self.app.game_snapshots; unblock=threading.Event(); started=threading.Event()
        def blocked(target): started.set(); unblock.wait(5); return None
        try:
            with patch('gametime.game_preview.capture_window',side_effect=blocked) as capture:
                self.assertTrue(worker.request(self.target(),self.app)); self.assertTrue(started.wait(1))
                worker.expired(); self.assertFalse(worker.timer.isActive())
                for _ in range(10): self.assertFalse(worker.request(self.target(),self.app))
                start=time.monotonic(); worker.close(); self.assertLess(time.monotonic()-start,.1); capture.assert_called_once()
                unblock.set(); worker.thread.join(1); self.assertFalse(worker.thread.is_alive())
        finally: unblock.set()

    def test_background_is_cached_hidden_ticks_and_language_do_not_recapture(self):
        from PySide6.QtGui import QImage,QColor
        from gametime.overlay import screen_device
        target=self.target(); image=QImage(200,100,QImage.Format_RGB32); image.fill(QColor('#dc8430'))
        with patch('gametime.qt_game_preview.running_window',return_value=target),patch('gametime.game_preview.capture_window',return_value=(image,screen_device(self.qt.primaryScreen()),(0,0,1,1))) as capture:
            window,fields=self.countdown_fields(); picker=fields[self.app.t('Countdown position')]
            deadline=time.monotonic()+3
            while picker.game_background is None and time.monotonic()<deadline: self.pump(.03)
            self.assertIsNotNone(picker.game_background); self.assertEqual(capture.call_count,1)
            self.assert_background_painted(picker)
            before=picker.game_background[0].cacheKey(); self.app.set_language('en'); self.pump(.03)
            self.assertEqual(picker.game_background[0].cacheKey(),before); self.assertEqual(capture.call_count,1)
            window.hide(); self.app.hide()
            for _ in range(5): self.app.render_tick(); self.app.update_overlay()
            self.assertIsNone(picker.game_background); self.assertEqual(capture.call_count,1)

    def assert_background_painted(self,picker):
        # Storing a successful capture is insufficient: the monitor-name bug
        # left that state populated while paintEvent silently skipped the image.
        monitor,_=picker.rectangles(); point=(round(monitor.x()+monitor.width()*.25),round(monitor.y()+monitor.height()*.3))
        painted=picker.grab().toImage().pixelColor(*point)
        background=picker.game_background; picker.game_background=None
        try: empty=picker.grab().toImage().pixelColor(*point)
        finally: picker.game_background=background
        self.assertGreater(painted.red()-empty.red(),40)

    def test_position_diagram_recovers_replaced_screen_without_running_game(self):
        from PySide6.QtGui import QColor
        saved=self.store.settings()
        obsolete=Mock(); obsolete.geometry.side_effect=RuntimeError('Internal C++ object (QScreen) already deleted.')
        with patch('gametime.qt_game_preview.running_window',return_value=None),patch.object(self.app.game_snapshots,'request') as capture:
            window,fields=self.countdown_fields(); picker=fields[self.app.t('Countdown position')]; self.pump(.05)
            picker.set_position(.4,.6); picker.screen=obsolete; picker._background_controller.refresh()
            self.assertIs(picker.screen,self.app.screen())
            monitor,hud=picker.rectangles()
            self.assertTrue(monitor.contains(hud))
            point=(round(monitor.x()+monitor.width()*.25),round(monitor.y()+monitor.height()*.3))
            self.assertEqual(picker.grab().toImage().pixelColor(*point),QColor('#101c23'))
            self.assertEqual(tuple(int(fields[self.app.t(name)].value()) for name in ('Horizontal (px)','Vertical (px)')),picker.pixel_position())
            self.assertEqual((picker.x_ratio,picker.y_ratio),(.4,.6))
            self.assertEqual(self.store.settings(),saved)
            capture.assert_not_called()

    def test_refresh_rebinds_selected_monitor_and_does_no_work_while_hidden(self):
        with patch('gametime.qt_game_preview.running_window',return_value=None):
            window,fields=self.countdown_fields(); picker=fields[self.app.t('Countdown position')]; controller=picker._background_controller; self.pump(.05)
            fields[self.app.t('Monitor')].setCurrentIndex(1)
            wanted=fields[self.app.t('Monitor')].currentData()
            with patch('gametime.qt_game_preview.choose_screen',return_value=self.qt.primaryScreen()) as choose:
                picker.screen=None
                controller.refresh()
                choose.assert_called_once_with(wanted,self.app.screen().name())
                self.assertIs(picker.screen,self.qt.primaryScreen())
                window.hide(); self.app.hide(); choose.reset_mock()
                controller.refresh(); choose.assert_not_called()

    def test_per_game_editor_paints_native_monitor_capture_after_refresh(self):
        from PySide6.QtGui import QImage,QColor
        from gametime.overlay import PositionPicker,screen_device
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True)
        target=self.target(); image=QImage(200,100,QImage.Format_RGB32); image.fill(QColor('#dc8430'))
        with patch('gametime.qt_game_preview.running_window',return_value=target),patch('gametime.game_preview.capture_window',return_value=(image,screen_device(self.qt.primaryScreen()),(0,0,1,1))) as capture:
            self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]; self.pump(.2)
            picker=window.findChild(PositionPicker); self.assertIsNotNone(picker.game_background)
            self.assert_background_painted(picker)
            picker._background_controller.refresh(); self.pump(.15)
            self.assertEqual(capture.call_count,2); self.assert_background_painted(picker)

    def test_native_monitor_identity_wins_over_dpi_geometry_and_friendly_names(self):
        from PySide6.QtCore import QRect
        from gametime.overlay import choose_screen,screen_device,screen_matches
        first,second=Mock(),Mock()
        first.name.return_value='Same monitor model'; second.name.return_value='Same monitor model'
        first.nativeInterface.return_value.handle.return_value=101
        second.nativeInterface.return_value.handle.return_value=202
        first.geometry.return_value=QRect(0,0,1920,1080)
        second.geometry.return_value=QRect(-2560,0,1707,960)  # 150% DPI, negative native origin.
        def info(handle,out):
            out._obj.device={101:r'\\.\DISPLAY1',202:r'\\.\DISPLAY2'}[handle]; return True
        with patch('gametime.overlay.monitor_info',side_effect=info),patch('gametime.overlay.QApplication.screens',return_value=[first,second]),patch('gametime.overlay.QApplication.primaryScreen',return_value=first):
            self.assertEqual(screen_device(second),r'\\.\DISPLAY2')
            self.assertIs(choose_screen('',r'\\.\display2'),second)
            self.assertIs(choose_screen(r'\\.\DISPLAY2',r'\\.\DISPLAY1'),second)
            self.assertTrue(screen_matches(first,'Same monitor model'))
            self.assertFalse(screen_matches(first,r'\\.\DISPLAY2'))
            self.assertIs(choose_screen('disconnected'),first)
        second.nativeInterface.side_effect=RuntimeError('Screen disconnected')
        self.assertEqual(screen_device(second),'Same monitor model')

    def test_late_capture_does_not_replace_another_selected_game(self):
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QComboBox
        from gametime.overlay import PositionPicker
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]; self.pump(.02)
        picker=window.findChild(PositionPicker); controller=picker._background_controller; target=self.target()
        controller.target=None
        controller.receive(controller,target,(QImage(10,10,QImage.Format_RGB32),'',(0,0,1,1)))
        self.assertIsNone(picker.game_background)
        combos=[item for item in window.findChildren(QComboBox) if item.accessibleName()==self.app.t('Countdown target')]
        combos[0].setCurrentIndex(1); self.assertIsNone(picker.game_background)

    def test_per_game_color_drafts_switch_cancel_save_reset_and_local_only_sync(self):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QComboBox,QPushButton,QWidget
        def field(window,key): return next(item for item in window.findChildren(QWidget) if item.accessibleName()==self.app.t(key))
        def click(window,key): next(item for item in window.findChildren(QPushButton) if item.text()==self.app.t(key)).click()
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]
        field(window,'Hide this countdown').setChecked(False)
        with patch('gametime.qt_personalization.QColorDialog.getColor',return_value=QColor('#12ab34')): field(window,'Normal color').click()
        games=field(window,'Countdown target'); games.setCurrentIndex(1)
        field(window,'Hide this countdown').setChecked(False)
        with patch('gametime.qt_personalization.QColorDialog.getColor',return_value=QColor('#bc56ef')): field(window,'Warning color').click()
        games.setCurrentIndex(0); self.assertEqual(field(window,'Normal color').text(),'#12AB34')
        self.app.set_language('en'); self.assertEqual(field(window,'Normal color').text(),'#12AB34')
        self.assertEqual(self.store.settings().game_overlays,{}); click(window,'Save')
        saved=self.store.settings(); self.assertEqual(saved.game_overlays[self.games[0].id]['overlay_color_normal'],'#12ab34')
        self.assertEqual(saved.game_overlays[self.games[0].id]['overlay_color_warning'],saved.overlay_color_warning)
        self.assertEqual(saved.game_overlays[self.games[1].id]['overlay_color_warning'],'#bc56ef')
        from gametime.statistics_sync import StatisticsData
        import json
        self.assertNotIn('#12ab34',json.dumps(StatisticsData(self.store).snapshot('a'*32,'Fixture')))
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]; click(window,'Default colors'); click(window,'Cancel')
        self.assertEqual(self.store.settings(),saved)
        self.app.game_countdown_dialog(self.games[0].id); window=self.app._dialogs[-1]; click(window,'Default colors'); click(window,'Save')
        self.assertEqual(self.store.settings().game_overlays[self.games[0].id]['overlay_color_normal'],saved.overlay_color_normal)
        self.assertEqual(self.store.settings().game_overlays[self.games[1].id]['overlay_color_warning'],'#bc56ef')

    def test_window_identity_reuse_and_foreground_handle_are_guarded(self):
        from gametime.game_preview import GameWindow
        from gametime import win32
        target=GameWindow(123,456,str(self.exe),'456:789',self.games[0].id)
        def pid(hwnd,out): out._obj.value=456; return 1
        current=Sample(datetime.now().astimezone(),100,str(self.exe),target.identity)
        with patch.object(win32.u,'IsWindowVisible',return_value=True),patch.object(win32.u,'GetWindowThreadProcessId',side_effect=pid),patch('gametime.game_preview.win32.process_image',return_value=(str(self.exe),'456:790')),patch.object(win32.u,'SetForegroundWindow') as focus:
            self.assertFalse(target.valid()); self.assertFalse(target.activate()); focus.assert_not_called()
        with patch.object(GameWindow,'valid',return_value=True),patch.object(win32.u,'GetForegroundWindow',return_value=999): self.assertFalse(target.matches(current))

    def test_minimized_game_with_no_client_area_is_still_found_for_restore(self):
        from gametime.game_preview import running_window
        from gametime import win32
        def pid(hwnd,out): out._obj.value=456; return 1
        with patch('gametime.game_preview.win32.interactive_desktop',return_value=True),patch.object(win32.u,'EnumWindows',side_effect=lambda callback,data:callback(123,0)),patch.object(win32.u,'IsWindowVisible',return_value=True),patch.object(win32.u,'GetWindowThreadProcessId',side_effect=pid),patch('gametime.game_preview.win32.process_image',return_value=(str(self.exe),'456:789')),patch.object(win32.u,'IsIconic',return_value=True),patch.object(win32.u,'GetClientRect',return_value=False):
            target=running_window(self.app.catalog,self.games[0].id)
            self.assertIsNotNone(target); self.assertEqual((target.hwnd,target.pid,target.game_id),(123,456,self.games[0].id))

    def test_asynchronous_activation_waits_without_refocusing_then_alt_tab_cancels(self):
        from gametime import win32
        target=self.target(); target.matches.return_value=False
        current=Sample(datetime.now().astimezone(),100,'unrelated.exe','hub:1')
        with patch('gametime.qt_ui.running_window',return_value=target),patch.object(self.app,'rtss_available',return_value=False),patch.object(win32.u,'GetForegroundWindow',return_value=987),patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app.overlay,'present') as present:
            self.app.preview_game_overlay(self.app.settings)
            self.assertIs(self.app._overlay_preview_target,target); present.assert_not_called(); self.assertTrue(self.app.overlay_timer.isActive())
            target.activate.assert_called_once()
            target.matches.return_value=True; self.app.update_overlay(); self.assertTrue(present.called); self.assertEqual(self.app._overlay_preview_focus_until,0)
            target.matches.return_value=False; self.app.update_overlay(); self.assertEqual(self.app._overlay_preview_until,0); target.activate.assert_called_once()

    def test_minimized_preview_waits_for_restore_before_drawing(self):
        from gametime import win32
        target=self.target()
        with patch('gametime.qt_ui.running_window',return_value=target),patch.object(self.app,'rtss_available',return_value=False),patch.object(win32.u,'IsIconic',return_value=True),patch.object(self.app.overlay,'present') as present:
            self.app.preview_game_overlay(self.app.settings)
            present.assert_not_called(); self.assertGreater(self.app._overlay_preview_delay_until,time.monotonic())
            self.app._overlay_preview_delay_until=0; self.app.update_overlay(); self.assertTrue(present.called); target.activate.assert_called_once()
