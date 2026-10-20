"""Qt integration tests: isolated profiles, synthetic games, no real launches/removals."""
import gc
import os
from dataclasses import replace
from datetime import date,datetime,timedelta
from pathlib import Path
from queue import Queue
import tempfile
import time
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.name=='nt','Windows required')
class QtInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gametime.qt_ui import setup_application
        cls.qt=setup_application()

    def setUp(self):
        from gametime.qt_ui import App
        from gametime.discovery import Discovery
        from gametime.store import Store
        from gametime.model import Game,Settings
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name)
        self.store=Store(self.base/'usage.sqlite3')
        self.settings=Settings(games_root=str(self.base/'Games'),language='hu')
        self.store.save_settings(self.settings)
        self.games=[Game('qt:'+str(i),name,src,str(self.base/name)) for i,(name,src) in enumerate([('Fixture Alpha','Games'),('Fixture Beta','Steam'),('Fixture Gamma','Epic')])]
        self.store.upsert(self.games)
        self.exe=self.base/'fixture.exe'; self.exe.write_bytes(b'MZ fixture')
        self.store.set_rule(str(self.exe),self.games[0].id)
        class Service:
            def __init__(me): me.results=Queue(); me.discovery=Discovery(self.settings,[],[],self.base/'none',ubisoft=False,riot=False)
            def start(me): pass
            def close(me): pass
            def request(me,*args): pass
            def configure(me,*args): pass
            def watch_manual(me,*args): pass
        class Hub:
            def __init__(me): me.results=Queue()
            def request(me,*args): pass
            def close(me): pass
        self.sound=patch('gametime.qt_ui.winsound.PlaySound'); self.sound.start()
        self.app=App(self.store,self.base,background=True,service=Service(),hub=Hub())
        self.app.tick_timer.stop(); self.pump(.03)

    def tearDown(self):
        self.app.close(); self.pump(.02); self.sound.stop(); self.store.close()
        self.app=None; gc.collect(); self.tmp.cleanup()

    def pump(self,seconds=.1):
        until=time.monotonic()+seconds
        while time.monotonic()<until: self.qt.processEvents(); time.sleep(.005)

    def test_search_source_sort_and_keyboard_card_selection(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.app.search.setText('beta'); self.assertEqual(list(self.app.cards),[self.games[1].id])
        self.app.search.clear(); self.app.source_filter.setCurrentIndex(self.app.source_filter.findData('Epic'))
        self.assertEqual(list(self.app.cards),[self.games[2].id])
        self.app.source_filter.setCurrentIndex(0)
        self.store.add_usage({(date.today().isoformat(),self.games[1].id):600})
        self.app.tracker.cache.clear(); self.app.sort.setCurrentIndex(1); self.assertEqual(next(iter(self.app.cards)),self.games[1].id)
        card=self.app.cards[self.games[1].id]; QTest.keyClick(card,Qt.Key_Space)
        self.assertEqual(self.app.selected_id,self.games[1].id)

    def test_hide_restore_and_exclude_are_independent(self):
        game=self.games[0]; self.app.select_game(game.id); self.app.toggle_hidden()
        self.assertNotIn(game.id,self.app.cards); self.assertTrue(self.app.catalog.enabled(game))
        self.app.hidden_toggle.setChecked(True); self.app.select_game(game.id); self.app.toggle_game()
        self.assertFalse(self.app.catalog.enabled(game)); self.app.toggle_hidden()
        self.assertNotIn(game.id,self.store.hidden_ids()); self.assertIn(game.id,self.app.cards)

    def test_language_rebuild_preserves_filters_selection_and_statistics_dates(self):
        self.app.search.setText('Beta'); self.app.select_game(self.games[1].id); self.app.switch_page(1)
        self.app.statistics.preset(7); self.app.statistics.choose_day(date.today().isoformat())
        original=(self.app.statistics.start.text(),self.app.statistics.end.text(),self.app.statistics.selected_day)
        self.app.set_language('en'); self.pump()
        self.assertEqual(self.app.search.text(),'Beta'); self.assertEqual(self.app.selected_id,self.games[1].id)
        self.assertEqual(self.app.pages.currentIndex(),1); self.assertEqual(self.store.settings().language,'en')
        self.assertEqual((self.app.statistics.start.text(),self.app.statistics.end.text(),self.app.statistics.selected_day),original)
        self.app.set_language('hu'); self.pump(); self.assertEqual(self.app.nav[0].text(),'Játéktár')

    def test_settings_validation_and_saved_language(self):
        self.app.limit.setValue(5); self.app.warning.setValue(10); self.app.save_settings()
        self.assertTrue(self.app.settings_error.text()); self.assertEqual(self.store.settings().limit_seconds,7200)
        self.app.warning.setValue(3); self.app.save_settings()
        self.assertEqual(self.store.settings().limit_seconds,300); self.assertEqual(self.store.settings().language,'hu')

    def test_linked_statistics_filter_computers_without_changing_local_budget(self):
        from gametime.store import Store
        from gametime.model import Game
        from gametime.statistics_sync import StatisticsData
        day=date.today().isoformat(); group='012345abcdef'
        self.store.add_usage({(day,self.games[0].id):120}); self.app.tracker.cache.clear()
        remote=Store(self.base/'other.sqlite3')
        try:
            remote.upsert([Game('other:alpha',self.games[0].name,self.games[0].source,'D:/Other')])
            remote.add_usage({(day,'other:alpha'):300})
            snapshot=StatisticsData(remote).snapshot(group,'Other PC')
        finally: remote.close()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_group=group)
        self.app.statistics_data.ingest(snapshot,group); self.app.switch_page(1); self.app.render()
        stats=self.app.statistics; self.assertEqual(stats.report.total,420); self.assertEqual(len(stats.report.games),1)
        self.assertEqual(self.app.total_label.text(),'00:02:00')
        stats.devices.setCurrentIndex(stats.devices.findData('local')); self.assertEqual(stats.report.total,120)
        stats.devices.setCurrentIndex(stats.devices.findData(snapshot['device'])); self.assertEqual(stats.report.total,300)
        self.app.set_language('en'); self.pump()
        self.assertEqual(self.app.statistics.scope,snapshot['device']); self.assertEqual(self.app.statistics.report.total,300)

    def test_sync_dialog_connects_and_disconnects_without_sharing_settings(self):
        from PySide6.QtWidgets import QLineEdit,QPushButton,QCheckBox
        from gametime.statistics_sync import StatisticsData
        from gametime.statistics_cloud import CloudSyncWorker
        from test_statistics_cloud import Relay,CODE
        from gametime.store import Store
        relay=Relay(); self.addCleanup(relay.close); group=CODE
        address=patch('gametime.qt_ui.SERVICE_URL',relay.url); address.start(); self.addCleanup(address.stop)
        self.app.statistics_sync.close(); self.app.statistics_sync=CloudSyncWorker(allow_local_http=True)
        remote=Store(self.base/'remote.sqlite3')
        try:
            snapshot=StatisticsData(remote).snapshot(group,'Other PC')
            worker=CloudSyncWorker(allow_local_http=True)
            try: worker.exchange((relay.url,group,0),(snapshot,{}))
            finally: worker.close()
        finally: remote.close()
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        fields={widget.accessibleName():widget for widget in window.findChildren(QLineEdit)}
        self.assertNotIn(self.app.t('Shared folder'),fields)
        fields[self.app.t('Connection code')].setText(group.upper())
        next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
        deadline=time.monotonic()+3
        while self.app._sync_busy and time.monotonic()<deadline: self.pump(.03)
        self.assertFalse(self.app._sync_busy); self.assertTrue(self.store.settings().statistics_sync_enabled)
        self.assertEqual(len(self.app.statistics_data.devices(group)),1)
        self.assertEqual(self.store.settings().limit_seconds,7200)
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        window.findChild(QCheckBox).setChecked(False)
        next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
        self.assertFalse(self.store.settings().statistics_sync_enabled)
        with patch.object(self.app.statistics_sync,'request') as request:
            self.app.poll_statistics_sync(); request.assert_not_called()

    def test_cloud_dialog_rejects_short_legacy_code_and_missing_service(self):
        from PySide6.QtWidgets import QLineEdit,QPushButton,QLabel
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        code=next(w for w in window.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code'))
        save=next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save'))
        code.setText('0123-45AB-CDEF')
        with patch('gametime.qt_ui.SERVICE_URL','https://example.com/sync'): save.click()
        self.assertIn(self.app.t('Use a connection code generated by the application.'),[w.text() for w in window.findChildren(QLabel)])
        self.assertFalse(self.store.settings().statistics_sync_enabled)
        code.setText('a'*32)
        with patch('gametime.qt_ui.SERVICE_URL',''): save.click()
        self.assertIn(self.app.t('The synchronization service is not configured yet.'),[w.text() for w in window.findChildren(QLabel)])
        self.assertFalse(self.store.settings().statistics_sync_enabled)

    def test_hidden_link_dialog_can_close_without_leaving_a_deleted_window(self):
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        window.hide(); window.close(); self.pump()
        self.assertFalse(self.app._dialogs); self.app.render()
        self.assertFalse(self.store.settings().statistics_sync_enabled)

    def test_statistics_average_since_installation_and_day_drilldown(self):
        today=date.today(); start=today-timedelta(days=3)
        with self.store.db: self.store.db.execute("UPDATE settings SET value=? WHERE key='tracking_started_on'",(start.isoformat(),))
        self.store.add_usage({(today.isoformat(),self.games[0].id):1200,(start.isoformat(),self.games[1].id):600})
        self.store.set_hidden(self.games[1].id,True); self.app.switch_page(1)
        stats=self.app.statistics; self.assertEqual(stats.report.average_days,4); self.assertEqual(stats.report.average,450)
        self.assertEqual(stats.games_table.rowCount(),2); stats.choose_day(today.isoformat()); self.assertEqual(stats.games_table.rowCount(),1)
        stats.show_period(); self.assertEqual(stats.games_table.rowCount(),2)
        stats.start.setText('invalid'); stats.refresh(); self.assertFalse(stats.error.isHidden())

    def test_native_tray_event_reopens_without_toggling_and_close_hides(self):
        from PySide6.QtWidgets import QMainWindow
        from gametime import win32
        self.app.show(); self.pump(); QMainWindow.close(self.app); self.pump(); self.assertFalse(self.app.isVisible()); self.assertFalse(self.app.closed)
        tray=self.app.tray
        for _ in range(2):
            self.assertTrue(win32.u.PostMessageW(tray.window,0x8001,0,(1<<16)|0x400)); self.pump(.15)
            self.assertTrue(self.app.isVisible()); self.assertTrue(win32.u.IsWindowVisible(int(self.app.winId()))); self.assertFalse(self.app.closed)
        with patch.object(tray,'popup_menu',return_value=5): self.app.tray_menu()
        self.assertTrue(self.app.closed)

    def test_hub_request_returns_to_library_in_existing_window(self):
        from gametime.tracker import Sample
        self.app.switch_page(1); self.app.hide(); (self.base/'show-hub.request').touch()
        with patch('gametime.controller.win32.sample',return_value=Sample(datetime.now().astimezone(),1,'','')): self.app.tick()
        self.assertTrue(self.app.isVisible()); self.assertEqual(self.app.pages.currentIndex(),0)
        self.assertFalse((self.base/'show-hub.request').exists())

    def test_play_is_prepared_once_and_executes_only_on_gui_delivery(self):
        from gametime.launch import LaunchPlan
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        class Worker:
            def __init__(me): me.results=Queue(); me.requests=[]
            def request(me,*args): me.requests.append(args)
            def close(me): pass
        worker=Worker(); self.app.launcher=worker; self.app.select_game(self.games[1].id)
        card=self.app.cards[self.games[0].id]
        with patch('gametime.launch.execute') as execute:
            QTest.mouseClick(card.play,Qt.LeftButton); QTest.mouseClick(card.play,Qt.LeftButton)
            self.assertEqual(len(worker.requests),1); self.assertEqual(worker.requests[0][0].id,self.games[0].id); execute.assert_not_called()
            self.assertFalse(card.play.isEnabled()); self.assertEqual(card.play.toolTip(),self.app.t('Starting…'))
            worker.results.put((self.games[0],LaunchPlan('executable',str(self.exe)),None)); self.app.poll_launch()
            execute.assert_called_once(); self.assertIsNone(self.app.launching); self.assertTrue(card.play.isEnabled())
            self.assertFalse(hasattr(self.app,'selection_panel'))

    def test_card_options_target_clicked_game_without_launching(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        game=self.games[1]; card=self.app.cards[game.id]
        self.app.select_game(self.games[0].id)
        with patch('gametime.qt_ui.QMenu') as menus,patch.object(self.app,'launch_selected') as launch:
            QTest.mouseClick(card.more,Qt.LeftButton)
            self.assertEqual(self.app.selected_id,game.id); launch.assert_not_called()
            menu=menus.return_value
            menu.exec.assert_called_once_with(card.more.mapToGlobal(QPoint(0,card.more.height())))
            hide=next(call.args[1] for call in menu.addAction.call_args_list if call.args[0]==self.app.t('Hide / restore'))
            hide(); self.assertIn(game.id,self.store.hidden_ids()); self.assertNotIn(self.games[0].id,self.store.hidden_ids())

    def test_removal_guide_close_never_executes(self):
        self.app.select_game(self.games[1].id)
        with patch('gametime.removal.execute') as execute:
            self.app.uninstall_game(); self.pump(); self.assertEqual(len(self.app._dialogs),1)
            self.app._dialogs[0].close(); self.pump(); execute.assert_not_called()

    def test_popup_is_independent_topmost_when_main_hidden_or_minimized(self):
        from gametime.tracker import Alert
        from PySide6.QtCore import Qt
        for minimized in (False,True):
            if minimized: self.app.showMinimized(); self.pump()
            else: self.app.hide()
            self.assertTrue(self.app.popup(Alert(date.today().isoformat(),(), 'limit','Fixture reminder','OK')))
            self.pump(); popup=self.app.popup_window
            self.assertTrue(popup.isVisible()); self.assertIsNone(popup.parent())
            self.assertTrue(popup.windowFlags() & Qt.WindowStaysOnTopHint)
            popup.accept(); self.pump(); self.assertIsNone(self.app.popup_window)

    def test_threshold_escape_delay_then_visible_delivery_and_failure_retry(self):
        from gametime.tracker import Alert,Sample
        alert=Alert(date.today().isoformat(),('limit:7200',),'limit','Fixture limit','OK')
        tracker=self.app.tracker; tracker.active=self.games[0]; tracker.identity='fixture:1'; tracker.alerts.append(alert)
        with patch('gametime.controller.win32.sample',return_value=Sample(datetime.now().astimezone(),1,str(self.exe),'fixture:1')), patch('gametime.controller.win32.escape_game',return_value=True) as escape:
            self.app.notify(alert); escape.assert_called_once(); self.assertIsNone(self.app.popup_window)
            self.pump(.3); self.assertTrue(self.app.popup_window.isVisible()); self.assertFalse(tracker.alerts)
        self.assertIn((alert.keys[0],),list(self.store.db.execute('SELECT key FROM alerts WHERE day=?',(alert.day,))))
        self.app.dismiss_popup(); tracker.alerts.append(alert)
        with patch('gametime.qt_ui.win32.present_notification',side_effect=OSError('fixture')):
            self.app.finish_notification(alert)
        self.assertEqual(list(tracker.alerts),[alert]); self.assertIsNone(self.app.popup_window)

    def test_shell_icon_dpi_does_not_shrink_its_display_area(self):
        from PySide6.QtGui import QPixmap,QColor
        native=QPixmap(256,256); native.fill(QColor('#00ff00')); native.setDevicePixelRatio(256/96)
        class ShellIcon:
            def isNull(me): return False
            def pixmap(me,*args): return native
        self.app.art.cache.clear()
        with patch.object(self.app.art.provider,'icon',return_value=ShellIcon()):
            _,pix=self.app.art.artwork(self.games[0],{str(self.exe):self.games[0].id})
        self.assertEqual(pix.devicePixelRatio(),1.0)
        scaled=pix.scaled(80,80)
        self.assertEqual(scaled.deviceIndependentSize().width(),80)
        self.assertEqual(scaled.deviceIndependentSize().height(),80)

    def test_corrupt_optional_artwork_does_not_break_library(self):
        from gametime.model import Game
        self.base.joinpath('.gametime-hub.json').write_text('[]')
        self.app.art.refresh_links(self.base); self.assertEqual(self.app.art.links,{})
        metadata=self.base/'broken.item'; metadata.write_text('[]')
        game=Game('epic:fixture','Broken optional artwork','Epic',str(self.base),str(metadata))
        poster,icon=self.app.art.artwork(game,{})
        self.assertIsNone(poster); self.assertIsNone(icon)
        self.app._art_queue=list(self.app.cards)
        with patch.object(self.app.art,'artwork',side_effect=OSError('unavailable artwork')):
            self.app.load_next_art()
        self.app.render(); self.assertEqual(len(self.app.cards),3)

    def test_wide_and_portrait_art_preserve_square_geometry(self):
        from PySide6.QtGui import QPixmap,QPainter,QColor
        from gametime.qt_widgets import GameCard
        for width,height in ((200,100),(100,200)):
            image=QPixmap(width,height); image.fill(QColor('#c02020'))
            painter=QPainter(image); painter.fillRect(int(width*.6),10,20,20,QColor('#00ff00')); painter.end()
            card=GameCard(self.games[0],self.app.t); card.resize(240,232); card.art=(image,None)
            rendered=card.grab().toImage(); pixels=[]
            for y in range(1,59):
                for x in range(1,239):
                    color=rendered.pixelColor(x,y)
                    if color.green()>180 and color.red()<40 and color.blue()<40: pixels.append((x,y))
            self.assertTrue(pixels)
            span_x=max(x for x,y in pixels)-min(x for x,y in pixels)
            span_y=max(y for x,y in pixels)-min(y for x,y in pixels)
            self.assertLessEqual(abs(span_x-span_y),2)
            # Padding is present above wide art and beside portrait art.
            sample=rendered.pixelColor(120,8) if width>height else rendered.pixelColor(45,30)
            self.assertLess(sample.red(),80)
            card.deleteLater()

    def test_small_window_is_responsive_and_cards_reflow(self):
        self.app.show(); self.app.resize(1000,700); self.pump()
        self.assertLessEqual(self.app.width(),1000); self.assertLessEqual(self.app.height(),700)
        self.assertGreaterEqual(self.app.grid.columns,2)
        for page in (1,2,0): self.app.switch_page(page); self.pump(); self.assertLessEqual(self.app.width(),1000)

if __name__=='__main__': unittest.main()
