"""Overlay policy, native input transparency, countdown and placement regressions."""
import ctypes as C
from dataclasses import asdict,replace
from datetime import date,datetime,timedelta
import json
import os
from pathlib import Path
from queue import Queue
import tempfile
import time
import unittest
from unittest.mock import patch
from gametime.model import Settings,popup_required
from gametime.store import Store

class OverlaySettingsTests(unittest.TestCase):
    def test_legacy_profile_keeps_popup_behavior_until_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'usage.sqlite3')
            config={'games_root':str(Path(tmp)/'Games'),'warning_seconds':6000,'limit_seconds':7200}
            with store.db: store.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)",(json.dumps(config),))
            settings=store.settings(); settings.validate()
            self.assertEqual(settings.overlay_font_size,25)
            self.assertFalse(settings.overlay_enabled); self.assertTrue(settings.limit_popup_enabled)
            self.assertTrue(popup_required(settings,'warning')); self.assertTrue(popup_required(settings,'limit'))
            store.close()

    def test_warning_and_expiry_policy_are_independent(self):
        settings=Settings(overlay_enabled=True)
        self.assertFalse(popup_required(settings,'warning')); self.assertTrue(popup_required(settings,'limit'))
        self.assertTrue(popup_required(replace(settings,overlay_replace_warning=False),'warning'))
        self.assertTrue(popup_required(replace(settings,overlay_enabled=False),'warning'))
        self.assertFalse(popup_required(replace(settings,limit_popup_enabled=False),'limit'))
        self.assertFalse(popup_required(replace(settings,limit_popup_enabled=False),'session'))

    @unittest.skipUnless(os.name=='nt','Windows paths required')
    def test_invalid_opacity_position_and_switches_are_rejected(self):
        for fields in ({'overlay_opacity':float('nan')},{'overlay_opacity':.1},{'overlay_opacity':1.01},
                       {'overlay_x':-1},{'overlay_y':2},{'overlay_x':True},{'overlay_enabled':'yes'},
                       {'overlay_screen':None}):
            with self.subTest(fields=fields),self.assertRaises(ValueError): replace(Settings(),**fields).validate()

    def test_text_size_rejects_invalid_or_unbounded_values(self):
        for size in (7,73,25.5,True,None,float('nan'),float('inf'),'25'):
            with self.subTest(size=size),self.assertRaises(ValueError): replace(Settings(),overlay_font_size=size).validate()
        for size in (8,25,72): replace(Settings(),overlay_font_size=size).validate()

@unittest.skipUnless(os.name=='nt','Windows required')
class OverlayInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gametime.qt_ui import setup_application
        cls.qt=setup_application()

    def setUp(self):
        from gametime.qt_ui import App
        from gametime.discovery import Discovery
        from gametime.model import Game
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.store=Store(self.base/'usage.sqlite3')
        self.settings=Settings(games_root=str(self.base/'Games'),overlay_enabled=True,overlay_rtss_auto=False,language='hu')
        self.store.save_settings(self.settings)
        self.game=Game('overlay:fixture','Overlay fixture','Kézi',str(self.base))
        self.exe=self.base/'fixture.exe'; self.exe.write_bytes(b'MZ fixture')
        self.store.upsert([self.game]); self.store.set_rule(str(self.exe),self.game.id)
        class Service:
            def __init__(me): me.results=Queue(); me.discovery=Discovery(self.settings,[],[],self.base/'none',platforms=False, ubisoft=False,riot=False)
            def start(me): pass
            def close(me): pass
            def request(me,*args): pass
            def configure(me,*args): pass
            def watch_manual(me,*args): pass
        class Hub:
            def __init__(me): me.results=Queue()
            def request(me,*args): pass
            def close(me): pass
        self.sound=patch('gametime.qt_ui.winsound.PlaySound'); self.sound_mock=self.sound.start()
        self.rtss_installation=patch('gametime.rtss.installation',return_value=None); self.rtss_installation.start()
        self.desktop=patch('gametime.qt_ui.win32.desktop_overlay_available',return_value=True); self.desktop.start()
        isolated=patch('gametime.win32.s.Shell_NotifyIconW',return_value=True); isolated.start(); self.addCleanup(isolated.stop)
        self.app=App(self.store,self.base,background=True,service=Service(),hub=Hub())
        self.app.tick_timer.stop(); self.app.overlay_timer.stop(); self.pump(.02)

    def tearDown(self):
        self.app.close(); self.pump(.02); self.sound.stop(); self.desktop.stop(); self.rtss_installation.stop(); self.store.close(); self.tmp.cleanup()

    def pump(self,seconds=.06):
        until=time.monotonic()+seconds
        while time.monotonic()<until: self.qt.processEvents(); time.sleep(.005)

    def sample(self,seconds=0,identity='overlay:1',interactive=True,path=None):
        from gametime.tracker import Sample
        return Sample(datetime.now().astimezone(),100+seconds,str(self.exe) if path is None else path,identity,interactive)

    def display(self,total):
        current=self.sample(); self.app.tracker.tick(current)
        self.app.tracker.cache[current.wall.date().isoformat()]={self.game.id:total}
        with patch('gametime.qt_ui.win32.sample',return_value=current): self.app.update_overlay()
        self.pump()
        return self.app.overlay

    def test_countdown_normal_warning_and_expired_states(self):
        overlay=self.display(5999); self.assertTrue(overlay.isVisible()); self.assertEqual(overlay.seconds,1201); self.assertFalse(overlay.warning)
        overlay=self.display(6000); self.assertEqual(overlay.seconds,1200); self.assertTrue(overlay.warning)
        overlay=self.display(7205); self.assertEqual(overlay.seconds,0); self.assertTrue(overlay.warning)

    def test_overlay_hides_for_other_apps_exclusions_lock_and_process_change(self):
        overlay=self.display(100)
        for current in (self.sample(path='C:/Windows/notepad.exe'),self.sample(identity='another:2'),self.sample(interactive=False)):
            with patch('gametime.qt_ui.win32.sample',return_value=current): self.app.update_overlay()
            self.assertFalse(overlay.isVisible())
            self.display(100)
        self.app.catalog.overrides[self.game.id]=False
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample()): self.app.update_overlay()
        self.assertFalse(overlay.isVisible())

    def test_hidden_game_still_has_countdown_and_hidden_hub_does_not_hide_it(self):
        self.store.set_hidden(self.game.id,True); self.app.hide()
        overlay=self.display(100); self.assertTrue(overlay.isVisible()); self.assertFalse(self.app.isVisible())
        self.assertIsNone(overlay.parent())

    def test_overlay_native_flags_and_foreground_do_not_change(self):
        from gametime import win32
        from gametime.overlay import EX_FLAGS,get_style
        before=win32.u.GetForegroundWindow(); overlay=self.display(100)
        self.assertEqual(win32.u.GetForegroundWindow(),before)
        hwnd=int(overlay.winId()); self.assertTrue(win32.u.IsWindowVisible(hwnd))
        self.assertEqual(get_style(hwnd,-20)&EX_FLAGS,EX_FLAGS)
        self.assertTrue(get_style(hwnd,-20)&0x8)  # Topmost.
        self.assertFalse(get_style(hwnd,-20)&0x40000)  # No taskbar application window.

    def test_warning_is_delivered_without_popup_escape_or_sound(self):
        from gametime.tracker import Alert
        alert=Alert(date.today().isoformat(),('warning:6000',),'warning','Warning','OK')
        self.app.tracker._queue(alert); self.app.tracker.active=self.game; self.app.tracker.identity='overlay:1'
        self.display(6000)
        with patch.object(self.app,'popup') as popup,patch('gametime.controller.win32.escape_game') as escape,patch('gametime.qt_ui.win32.sample',return_value=self.sample()):
            self.app.notify(alert); popup.assert_not_called(); escape.assert_not_called()
        self.sound_mock.assert_not_called()
        self.assertFalse(self.app.tracker.alerts); self.assertIn('warning:6000',self.store.alert_keys(alert.day))

    def test_expiry_popup_can_be_disabled_including_later_sessions(self):
        from gametime.tracker import Alert
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,limit_popup_enabled=False)
        for kind,key in (('limit','limit:7200'),('session','session:7200:overlay:1')):
            alert=Alert(date.today().isoformat(),(key,),kind,'Expired','OK'); self.app.tracker._queue(alert)
            with patch.object(self.app,'popup') as popup,patch('gametime.controller.win32.escape_game') as escape:
                self.app.notify(alert); popup.assert_not_called(); escape.assert_not_called()
            self.assertIn(key,self.store.alert_keys(alert.day))

    def test_enabled_limit_still_uses_popup_and_rechecks_delayed_preference(self):
        from gametime.tracker import Alert
        alert=Alert(date.today().isoformat(),('limit:7200',),'limit','Expired','OK')
        self.app.tracker._queue(alert); self.app.tracker.active=self.game; self.app.tracker.identity='overlay:1'
        with patch.object(self.app,'popup',return_value=True) as popup,patch('gametime.controller.win32.sample',return_value=self.sample()),patch('gametime.controller.win32.escape_game',return_value=True):
            self.app.notify(alert); popup.assert_not_called(); self.pump(.3); popup.assert_called_once_with(alert)
        other=replace(alert,keys=('session:7200:overlay:2',),kind='session'); self.app.tracker._queue(other)
        with patch.object(self.app,'popup') as popup,patch('gametime.controller.win32.sample',return_value=self.sample()),patch('gametime.controller.win32.escape_game',return_value=True):
            self.app.notify(other); self.app.settings=replace(self.app.settings,limit_popup_enabled=False)
            self.pump(.3); popup.assert_not_called()
        self.assertFalse(self.app.tracker.alerts)

    def test_renderer_failure_restores_warning_popup(self):
        from gametime.tracker import Alert
        alert=Alert(date.today().isoformat(),('warning:6000',),'warning','Warning','OK')
        self.app.overlay_failed=True; self.app.tracker._queue(alert)
        with patch.object(self.app,'popup',return_value=True) as popup: self.app.notify(alert); popup.assert_called_once_with(alert)

    def test_position_opacity_monitor_and_options_persist_without_changing_budget(self):
        self.app.overlay_picker.set_position(.2,.8); self.app.overlay_opacity.setValue(100)
        self.app.limit_popup.setChecked(False); self.app.overlay_warning.setChecked(False)
        self.app.overlay_screen.setCurrentIndex(1); self.app.save_settings()
        saved=self.store.settings(); self.assertTrue(saved.overlay_enabled); self.assertFalse(saved.overlay_replace_warning); self.assertFalse(saved.limit_popup_enabled)
        self.assertEqual((saved.overlay_x,saved.overlay_y,saved.overlay_opacity),(.2,.8,1))
        self.assertEqual(saved.overlay_screen,self.qt.primaryScreen().name()); self.assertEqual(saved.limit_seconds,7200); self.assertEqual(saved.language,'hu')
        reader=Store(self.base/'usage.sqlite3'); self.assertEqual(reader.settings(),saved); reader.close()

    def test_preview_is_temporary_and_does_not_credit_time_or_mark_alerts(self):
        self.app.preview_overlay(); self.assertTrue(self.app.overlay.preview); self.assertTrue(self.app.overlay.isVisible()); self.assertTrue(self.app.overlay.warning)
        self.assertEqual(self.store.totals(date.today()),{}); self.assertEqual(self.store.alert_keys(date.today().isoformat()),set())
        self.app._overlay_preview_until=0
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample(path='C:/Windows/notepad.exe')): self.app.update_overlay()
        self.assertFalse(self.app.overlay.isVisible())

    def test_placement_clamps_on_small_and_negative_coordinate_monitors(self):
        from PySide6.QtCore import QRect,QSize
        from gametime.overlay import placement
        area=QRect(-1920,0,1920,1080); size=QSize(244,86)
        for x,y in ((0,0),(1,1),(.5,.5)):
            left,top=placement(area,size,x,y)
            self.assertGreaterEqual(left,area.left()); self.assertLessEqual(left+size.width(),area.right()+1)
            self.assertGreaterEqual(top,area.top()); self.assertLessEqual(top+size.height(),area.bottom()+1)
        self.assertEqual(placement(QRect(0,0,200,70),size,1,1),(0,0))

    def test_bottom_position_uses_full_display_instead_of_taskbar_work_area(self):
        from PySide6.QtCore import QPoint
        from unittest.mock import Mock
        from gametime.overlay import placement
        area=self.qt.primaryScreen().geometry()
        work_area=area.adjusted(0,0,0,-48)
        screen=Mock(); screen.geometry.return_value=area; screen.availableGeometry.return_value=work_area
        settings=replace(self.app.settings,overlay_x=.5,overlay_y=1)
        overlay=self.app.overlay
        overlay.present(1200,6000,settings,screen,preview=True)
        self.assertEqual(overlay.pos(),QPoint(*placement(area,overlay.size(),.5,1)))
        self.assertGreater(overlay.geometry().bottom(),work_area.bottom())
        self.assertTrue(area.contains(overlay.geometry()))

    def test_position_picker_uses_full_display_aspect_ratio(self):
        from PySide6.QtCore import QRect
        from unittest.mock import Mock
        picker=self.app.overlay_picker; picker.resize(400,200)
        screen=Mock(); screen.geometry.return_value=QRect(-1920,0,1920,1080)
        screen.availableGeometry.return_value=QRect(-1920,0,1920,1032)
        picker.screen=screen; picker.set_position(.5,1)
        monitor,hud=picker.rectangles()
        self.assertAlmostEqual(monitor.width()/monitor.height(),1920/1080)
        self.assertAlmostEqual(hud.bottom(),monitor.bottom()-16*monitor.height()/1080)
        scale=monitor.width()/1920
        self.assertAlmostEqual(hud.width(),picker.hud_size().width()*scale)

    def test_position_picker_keyboard_and_missing_monitor_fallback(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from gametime.overlay import choose_screen
        picker=self.app.overlay_picker; picker.set_position(.5,.5); before=picker.pixel_position()
        QTest.keyClick(picker,Qt.Key_Left)
        self.assertEqual(picker.pixel_position(),(before[0]-1,before[1]))
        QTest.keyClick(picker,Qt.Key_Down,Qt.ShiftModifier)
        self.assertEqual(picker.pixel_position(),(before[0]-1,before[1]+10))
        self.assertEqual(choose_screen('missing-monitor'),self.qt.primaryScreen())
        self.app.overlay_screen.addItem('missing','missing-monitor'); self.app.overlay_screen.setCurrentIndex(self.app.overlay_screen.count()-1)
        self.app.refresh_overlay_screens(); self.assertEqual(self.app.overlay_screen.currentData(),'missing-monitor')
        self.assertEqual(self.app.overlay_picker.screen,self.qt.primaryScreen())

    def test_precise_coordinates_size_preview_and_persistence_share_the_same_geometry(self):
        from PySide6.QtCore import QPoint
        from gametime.overlay import countdown_size
        picker=self.app.overlay_picker; x,y=self.app.overlay_coordinates
        self.app.preview_overlay(); overlay=self.app.overlay; area=picker.screen.geometry()
        original=overlay.size()
        x.setValue(137); y.setValue(219)
        self.assertEqual(overlay.pos(),QPoint(area.x()+137,area.y()+219))
        self.assertEqual(picker.pixel_position(),(137,219))
        self.assertEqual(self.store.settings().overlay_font_size,25)
        self.app.overlay_font_size.setValue(48)
        self.assertEqual(picker.pixel_position(),(137,219))
        self.assertGreater(overlay.width(),original.width()); self.assertGreater(overlay.height(),original.height())
        self.assertEqual(overlay.size(),countdown_size(48,overlay))
        self.assertEqual(overlay.pos(),QPoint(area.x()+int(x.value()),area.y()+int(y.value())))
        self.assertEqual(overlay.size(),picker.hud_size())
        for a,b in ((0,0),(1,1),(.3456,.6789)):
            picker.set_position(a,b)
            self.assertEqual((int(x.value()),int(y.value())),picker.pixel_position())
            self.assertTrue(area.contains(overlay.geometry()))
        x.setValue(137); y.setValue(219); self.app.save_settings()
        saved=self.store.settings(); self.assertEqual(saved.overlay_font_size,48)
        self.assertEqual((saved.overlay_x,saved.overlay_y),(picker.x_ratio,picker.y_ratio))
        self.assertEqual(saved.limit_seconds,7200); self.assertEqual(self.store.totals(date.today()),{})
        self.assertEqual(self.store.alert_keys(date.today().isoformat()),set())
        reader=Store(self.base/'usage.sqlite3'); self.assertEqual(reader.settings(),saved); reader.close()

    def test_typed_pixels_and_size_survive_translation_and_preview_has_no_focus(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from gametime import win32
        self.app.show(); self.app.switch_page(2)
        x,y=self.app.overlay_coordinates; x.setFocus(); x.selectAll()
        QTest.keyClicks(x,'314'); QTest.keyClick(x,Qt.Key_Return)
        self.assertEqual(self.app.overlay_picker.pixel_position()[0],314)
        self.app.overlay_font_size.setValue(36); self.app.set_language('en')
        self.assertEqual(self.app.overlay_font_size.value(),36); self.assertEqual(x.value(),self.app.overlay_picker.pixel_position()[0])
        self.assertEqual(x.accessibleName(),'Horizontal (px)'); self.assertEqual(self.app.overlay_font_size.accessibleName(),'Text size')
        before=win32.u.GetForegroundWindow(); self.app.preview_overlay()
        self.assertEqual(win32.u.GetForegroundWindow(),before); self.assertEqual(self.store.settings().overlay_font_size,25)
        self.app.set_language('hu'); self.assertEqual(self.app.overlay_font_size.value(),36)

    def test_pixel_fields_follow_monitor_resolution_and_font_limits_without_ratio_drift(self):
        from PySide6.QtCore import QRect
        from unittest.mock import Mock
        picker=self.app.overlay_picker; screen=Mock(); picker.screen=screen
        for width,height in ((1920,1080),(1080,1920),(1280,720)):
            screen.geometry.return_value=QRect(-width,-height,width,height)
            for size in (8,25,72):
                self.app.overlay_font_size.setValue(size); picker.set_position(.25,.75); self.app.update_overlay_coordinates()
                before=(picker.x_ratio,picker.y_ratio); self.app.update_overlay_coordinates()
                self.assertEqual((picker.x_ratio,picker.y_ratio),before)
                for edit,limits,value in zip(self.app.overlay_coordinates,picker.pixel_limits(),picker.pixel_position()):
                    self.assertEqual((edit.minimum(),edit.maximum()),limits); self.assertEqual(edit.value(),value)
                picker.set_pixel_position(-100,100000)
                self.assertEqual(picker.pixel_position(),(picker.pixel_limits()[0][0],picker.pixel_limits()[1][1]))

    def test_interpolated_display_does_not_write_extra_game_time(self):
        from gametime.tracker import Sample
        previous=self.sample(); self.app.tracker.tick(previous)
        self.store.add_usage({(previous.wall.date().isoformat(),self.game.id):6000}); self.app.tracker.cache.clear()
        current=Sample(previous.wall+timedelta(seconds=1.1),previous.awake+1.1,previous.path,previous.identity)
        with patch('gametime.qt_ui.win32.sample',return_value=current): self.app.update_overlay()
        self.assertEqual(self.app.overlay.seconds,1199); self.assertEqual(self.store.totals(previous.wall.date())[self.game.id],6000)

    def test_threshold_crossing_changes_color_without_escape_or_popup(self):
        from gametime.tracker import Sample
        initial=self.sample(); self.app.tracker.tick(initial)
        self.store.add_usage({(initial.wall.date().isoformat(),self.game.id):5999}); self.app.tracker.cache.clear()
        current=Sample(initial.wall+timedelta(seconds=1),initial.awake+1,initial.path,initial.identity)
        self.app.tracker.tick(current)
        self.assertEqual(len(self.app.tracker.alerts),1)
        with patch.object(self.app,'popup') as popup,patch('gametime.controller.win32.escape_game') as escape,patch('gametime.qt_ui.win32.sample',return_value=current):
            self.app.update_overlay(); self.app.notify(self.app.tracker.alerts[0])
            popup.assert_not_called(); escape.assert_not_called()
        self.assertTrue(self.app.overlay.warning); self.assertEqual(self.app.overlay.seconds,1200)
        self.assertEqual(self.store.totals(initial.wall.date())[self.game.id],6000)

    def test_exclusive_fullscreen_retains_popup_despite_visible_desktop_hwnd(self):
        from gametime.tracker import Alert
        self.display(6000); alert=Alert(date.today().isoformat(),('warning:6000',),'warning','Warning','OK'); self.app.tracker._queue(alert)
        self.assertTrue(self.app.overlay.isVisible())
        with patch('gametime.qt_ui.win32.desktop_overlay_available',return_value=False),patch('gametime.qt_ui.win32.sample',return_value=self.sample()),patch('gametime.controller.win32.escape_game',return_value=False),patch.object(self.app,'popup',return_value=True) as popup:
            self.app.notify(alert); popup.assert_called_once_with(alert)

    def test_preview_and_stale_renderer_cannot_suppress_warning(self):
        current=self.sample(); self.app.tracker.tick(current)
        with patch('gametime.qt_ui.win32.sample',return_value=current):
            self.app.preview_overlay(); self.assertFalse(self.app.overlay_warning_visible())
            self.app._overlay_preview_until=0; self.app.update_overlay(); self.assertTrue(self.app.overlay_warning_visible())
            self.app._overlay_updated-=3; self.assertFalse(self.app.overlay_warning_visible())
            self.app.update_overlay()
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample(identity='other:2')): self.assertFalse(self.app.overlay_warning_visible())

    def test_automatic_rtss_requires_ack_and_clears_on_alt_tab(self):
        self.app.settings=replace(self.app.settings,overlay_rtss_auto=True); self.app.catalog.settings=self.app.settings
        self.app._rtss_checked=time.monotonic(); self.app._rtss_available=True
        with patch.object(self.app.rtss,'present',return_value=False) as present:
            self.display(6000); present.assert_called_once(); self.assertTrue(self.app.overlay.isVisible()); self.assertFalse(self.app.overlay_failed)
        with patch.object(self.app.rtss,'present',return_value=True),patch('gametime.qt_ui.win32.sample',return_value=self.sample()),patch('gametime.qt_ui.win32.desktop_overlay_available',return_value=False):
            self.app.update_overlay(); self.assertFalse(self.app.overlay.isVisible())
            self.app._overlay_desktop_until=0  # The compositor guard interval has elapsed.
            self.app.update_overlay(); self.assertTrue(self.app.overlay_warning_visible())
        with patch.object(self.app.rtss,'hide') as hide,patch('gametime.qt_ui.win32.sample',return_value=self.sample(path='')):
            self.app.update_overlay(); hide.assert_called_once(); self.assertEqual(self.app._overlay_backend,'none')

    def test_rtss_receives_saved_font_size_and_preview_stays_on_the_desktop(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True,overlay_font_size=48)
        self.app._rtss_checked=time.monotonic(); self.app._rtss_available=True
        with patch.object(self.app.rtss,'present',return_value=True) as present:
            self.display(6000)
            args=present.call_args.args
            self.assertIn('<FNT=Consolas,-64,700,1>',args[2]); self.assertEqual(args[3][4],48)
            self.assertEqual(self.app._overlay_backend,'rtss')
            self.app.overlay_font_size.setValue(36); self.assertEqual(present.call_args.args[3][4],48)
            present.reset_mock(); self.app.preview_overlay(); present.assert_not_called(); self.assertEqual(self.app.overlay.font_size,36)

    def test_position_picker_drag_moves_and_clamps_the_saved_coordinates(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        picker=self.app.overlay_picker; picker.resize(400,200)
        picker.set_position(1,0); monitor,hud=picker.rectangles()
        QTest.mousePress(picker,Qt.LeftButton,pos=hud.center().toPoint())
        QTest.mouseMove(picker,monitor.bottomLeft().toPoint()+QPoint(-100,100))
        QTest.mouseRelease(picker,Qt.LeftButton,pos=monitor.bottomLeft().toPoint())
        self.assertEqual((picker.x_ratio,picker.y_ratio),(0,1)); self.assertFalse(picker.dragging)

    def test_position_picker_does_not_start_dragging_outside_the_monitor(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest,QSignalSpy
        picker=self.app.overlay_picker; picker.resize(640,200); picker.set_position(.4,.6)
        changed=QSignalSpy(picker.positionChanged)
        monitor,_=picker.rectangles(); outside=QPoint(1,1)
        self.assertFalse(monitor.contains(outside))
        QTest.mousePress(picker,Qt.LeftButton,pos=outside)
        self.assertFalse(picker.dragging)
        QTest.mouseMove(picker,monitor.center().toPoint())
        QTest.mouseRelease(picker,Qt.LeftButton,pos=monitor.center().toPoint())
        self.assertEqual((picker.x_ratio,picker.y_ratio),(.4,.6)); self.assertEqual(changed.count(),0)

    def test_position_picker_keeps_the_whole_timer_inside_all_monitor_shapes(self):
        from PySide6.QtCore import QRect,QPointF
        from unittest.mock import Mock
        picker=self.app.overlay_picker; screen=Mock(); picker.screen=screen
        for width,height in ((1920,1080),(1080,1920),(5120,1440),(720,2560)):
            screen.geometry.return_value=QRect(-width,0,width,height)
            for widget_width,widget_height in ((320,168),(1000,200)):
                picker.resize(widget_width,widget_height)
                for x,y in ((0,0),(1,0),(0,1),(1,1),(.5,.5)):
                    with self.subTest(screen=(width,height),widget=(widget_width,widget_height),position=(x,y)):
                        picker.set_position(x,y)
                        monitor,hud=picker.rectangles()
                        self.assertTrue(monitor.contains(hud))
                        self.assertTrue(picker._bounds(monitor).adjusted(-.001,-.001,.001,.001).contains(hud))
                        picker.offset=QPointF(hud.width()/2,hud.height()/2)
                        picker._move(QPointF(-100,-100))
                        self.assertTrue(picker.rectangles()[0].contains(picker.rectangles()[1]))
                        picker._move(QPointF(widget_width+100,widget_height+100))
                        self.assertTrue(picker.rectangles()[0].contains(picker.rectangles()[1]))

if __name__=='__main__': unittest.main()
