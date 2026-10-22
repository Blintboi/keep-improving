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

    def test_manual_sync_cooldown_survives_restart_and_code_change(self):
        code='d'*32
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=code)
        self.app.pages.setCurrentIndex(1)
        with patch('gametime.qt_ui.time.monotonic',return_value=100000),patch.object(self.app.statistics_sync,'request',return_value=True) as request:
            self.app.request_statistics_sync()
            self.app._sync_busy=False
            self.app.request_statistics_sync()
            self.assertEqual(request.call_count,1)
            self.app.statistics.refresh()
            self.assertFalse(self.app.statistics.sync_now.isEnabled())
            from gametime.statistics_sync import StatisticsData
            restored=StatisticsData(self.store)
            self.assertGreater(restored.sync_delay(),599)
            self.app.settings=replace(self.app.settings,statistics_sync_group='f'*32)
            self.app.request_statistics_sync()
            self.assertEqual(request.call_count,1)
        with patch('gametime.qt_ui.time.monotonic',return_value=100601),patch.object(self.app.statistics_sync,'request',return_value=True) as request:
            self.app.update_statistics_sync_controls()
            self.assertTrue(self.app.statistics.sync_now.isEnabled())
            self.app.request_statistics_sync(); request.assert_called_once()

    def test_startup_once_without_periodic_sync_or_automatic_retry(self):
        code='e'*32
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=code)
        self.app._sync_startup_pending=True
        with patch.object(self.app.statistics_sync,'request',return_value=True) as request:
            self.app.poll_statistics_sync(); request.assert_called_once()
            self.app._sync_busy=False
            self.app.statistics_data._sync_not_before=0
            for visible,page in ((True,1),(True,0),(False,1)):
                self.app.pages.setCurrentIndex(page)
                with patch.object(self.app,'isVisible',return_value=visible):
                    self.app.poll_statistics_sync()
            request.assert_called_once()
        # A guarded startup is consumed once; expiration never queues a retry.
        self.app._sync_startup_pending=True
        with patch.object(self.app.statistics_sync,'retry_delay',return_value=3600),patch.object(self.app.statistics_sync,'request') as request:
            self.app.poll_statistics_sync(); self.app.request_statistics_sync(); request.assert_not_called()
            self.app.update_statistics_sync_controls()
            self.assertFalse(self.app.statistics.sync_now.isEnabled())
        with patch.object(self.app.statistics_sync,'request') as request:
            self.app.poll_statistics_sync(); request.assert_not_called()

    def test_gameplay_events_coalesce_and_share_the_durable_guard(self):
        from gametime.tracker import Sample
        code='e'*32
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=code)
        start=datetime.now().astimezone()
        with patch.object(self.app,'schedule_statistics_event') as schedule:
            with patch('gametime.controller.win32.sample',return_value=Sample(start,100,str(self.exe),'fixture:1')):
                self.app.tick()
            with patch('gametime.controller.win32.sample',return_value=Sample(start+timedelta(seconds=1),101)):
                self.app.tick()
            self.assertEqual([call.args for call in schedule.call_args_list],[(0,),(60,)])
        self.app.statistics_data.defer_sync(600)
        with patch.object(self.app.statistics_sync,'request') as request:
            for playing in (True,False,True,False): self.app.statistics_activity_changed(playing)
            request.assert_not_called()
            self.assertTrue(self.app.statistics_event_timer.isSingleShot())
            self.assertGreater(self.app.statistics_event_timer.remainingTime(),598000)
            self.app.statistics_event_timer.stop()
            self.app.statistics_data._sync_not_before=0
            request.return_value=True
            self.app.sync_statistics_event(); request.assert_called_once()
            self.app._sync_busy=False
            self.app.poll_statistics_sync(); request.assert_called_once()
            self.assertFalse(self.app._sync_event_pending)
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=False)
        self.app.statistics_activity_changed(True)
        self.assertFalse(self.app.statistics_event_timer.isActive())

    def test_server_delay_is_persisted_without_scheduling_error_retries(self):
        from gametime.qt_ui import SERVICE_URL
        from gametime.statistics_sync import StatisticsData
        code='f'*32
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=code)
        self.app._sync_busy=True
        self.app.statistics_sync.results.put(((SERVICE_URL,code,self.app.statistics_sync.generation),[],
            self.app.statistics_sync.failure_message))
        with patch.object(self.app.statistics_sync,'retry_delay',return_value=3600):
            self.app.poll_statistics_sync()
        self.assertGreater(StatisticsData(self.store).sync_delay(),3599)
        self.assertFalse(self.app.statistics_event_timer.isActive())
        self.assertFalse(self.app._sync_startup_pending)

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

    def test_background_rediscovery_keeps_cards_artwork_focus_and_scroll(self):
        from gametime.model import Game
        from PySide6.QtGui import QPixmap,QColor
        self.app.assets_timer.stop()
        extra=[Game('extra:'+str(i),'Extra '+str(i),'Games',str(self.base/str(i))) for i in range(12)]
        self.store.upsert(extra); self.app.catalog.games.update({g.id:g for g in extra}); self.app.render()
        self.app.show(); self.app.resize(1000,700); self.pump(.05); self.app._art_queue=[]
        poster=QPixmap(60,80); poster.fill(QColor('#148050'))
        before=dict(self.app.cards)
        for card in before.values(): card.art=(poster,None); self.app.art.cache[self.app.art.key(card.game)]=card.art
        focused=next(iter(before.values())); focused.setFocus(); self.app.select_game(focused.game.id)
        bar=self.app.scroll.verticalScrollBar(); bar.setValue(bar.maximum()//2); position=bar.value()
        for _ in range(3):
            self.app.service.results.put(('launchers',[g for g in self.games if g.source in ('Steam','Epic')],[],[],[],[],[]))
            self.app.service.results.put(('games',[self.games[0],*extra],''))
            self.app.drain_discovery()
            with patch.object(self.app.grid,'reflow',wraps=self.app.grid.reflow) as reflow:
                self.app.render(); reflow.assert_not_called()
            for gid,card in before.items():
                self.assertIs(self.app.cards[gid],card); self.assertEqual(card.art[0].cacheKey(),poster.cacheKey())
            self.assertEqual(self.app.selected_id,focused.game.id); self.assertIs(self.app.focusWidget(),focused)
            self.assertEqual(bar.value(),position); self.assertFalse(self.app._art_queue)

    def test_changed_catalog_updates_only_needed_cards_and_keeps_art_while_loading(self):
        from PySide6.QtGui import QPixmap,QColor
        self.app.assets_timer.stop(); self.app._art_queue=[]
        original=dict(self.app.cards); game=self.games[0]; card=original[game.id]
        poster=QPixmap(60,80); poster.fill(QColor('#148050')); card.art=(poster,None)
        changed=replace(game,name='Renamed fixture',metadata='new-artwork')
        self.app.catalog.games[game.id]=changed; self.store.upsert([changed]); self.app.render()
        self.assertIs(self.app.cards[game.id],card); self.assertEqual(card.game.name,changed.name)
        self.assertIn(changed.name,card.play.accessibleName()); self.assertEqual(card.art[0].cacheKey(),poster.cacheKey())
        for gid,other in original.items(): self.assertIs(self.app.cards[gid],other)
        self.app._art_queue=[game.id]; key=self.app.art.key(changed); self.app.art.pending[key]=999
        with patch.object(self.app.art,'artwork',return_value=(None,None)): self.app.load_next_art()
        self.assertEqual(card.art[0].cacheKey(),poster.cacheKey())
        self.app.art.cache[key]=(None,None)
        with patch.object(self.app.art,'poll',return_value=[key]): self.app.poll_assets()
        self.assertEqual(card.art,(None,None))
        self.app.select_game(self.games[1].id); self.app.toggle_hidden()
        self.assertNotIn(self.games[1].id,self.app.cards); self.assertIs(self.app.cards[game.id],card)
        self.app.sort.setCurrentIndex(1); self.assertIs(self.app.cards[game.id],card)

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

    def test_wheel_scrolls_settings_without_changing_focused_or_unfocused_values(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QScrollArea,QDateTimeEdit
        self.app.show(); self.app.switch_page(2)
        self.app.restriction_enabled.setChecked(True); self.app.bedtime_enabled.setChecked(True)
        self.app.overlay_enabled.setChecked(True); self.pump(.03)
        scroll=self.app.pages.widget(2).findChild(QScrollArea); bar=scroll.verticalScrollBar()
        controls=[self.app.limit,self.app.warning,self.app.restriction_minutes,*self.app.bedtime_times.values(),
                  self.app.overlay_screen,self.app.overlay_opacity]
        def value(widget):
            if widget in self.app.bedtime_times.values(): return widget.time()
            if widget is self.app.overlay_screen: return widget.currentIndex()
            return widget.value()
        for widget in controls:
            for focused in (False,True):
                with self.subTest(control=type(widget).__name__,focused=focused):
                    scroll.ensureWidgetVisible(widget); self.pump(.02)
                    (widget if focused else self.app.nav[2]).setFocus(); self.pump(.01)
                    position=bar.value(); original=value(widget)
                    point=widget.mapTo(self.app,widget.rect().center())
                    QTest.wheelEvent(self.app.windowHandle(),point,QPoint(0,-120)); self.pump(.02)
                    self.assertEqual(value(widget),original)
                    self.assertGreater(bar.value(),position)
                    scroll.ensureWidgetVisible(widget); self.pump(.01)
                    point=widget.mapTo(self.app,widget.rect().center()); position=bar.value()
                    QTest.wheelEvent(self.app.windowHandle(),point,QPoint(),pixelDelta=QPoint(0,-40),phase=Qt.ScrollUpdate)
                    self.pump(.02); self.assertEqual(value(widget),original)
        # The same form controls still accept deliberate keyboard input.
        scroll.ensureWidgetVisible(self.app.limit); self.app.limit.setFocus()
        original=self.app.limit.value(); QTest.keyClick(self.app.limit,Qt.Key_Up)
        self.assertGreater(self.app.limit.value(),original)
        edit=self.app.bedtime_times['bedtime_minute']; scroll.ensureWidgetVisible(edit)
        edit.setFocus(); edit.setSelectedSection(QDateTimeEdit.Section.MinuteSection); original=edit.time()
        QTest.keyClick(edit,Qt.Key_Up); self.assertNotEqual(edit.time(),original)
        combo=self.app.overlay_screen; combo.addItem('Synthetic second monitor','fixture:2')
        scroll.ensureWidgetVisible(combo); combo.setFocus(); combo.setCurrentIndex(0)
        QTest.keyClick(combo,Qt.Key_Down); self.assertEqual(combo.currentIndex(),1)

    def test_combo_popup_scroll_and_slider_drag_still_work(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QScrollArea,QStyle,QStyleOptionSlider
        self.app.show(); self.app.switch_page(2); self.app.overlay_enabled.setChecked(True)
        scroll=self.app.pages.widget(2).findChild(QScrollArea)
        combo=self.app.overlay_screen
        for i in range(50): combo.addItem('Synthetic monitor '+str(i),'fixture:'+str(i))
        scroll.ensureWidgetVisible(combo); self.pump(.03)
        combo.showPopup(); self.pump(.03)
        view=combo.view(); popup=view.window(); bar=view.verticalScrollBar()
        original=bar.value(); point=view.viewport().mapTo(popup,view.viewport().rect().center())
        QTest.wheelEvent(popup.windowHandle(),point,QPoint(0,-120)); self.pump(.03)
        self.assertGreater(bar.value(),original)
        combo.hidePopup()
        slider=self.app.overlay_opacity; scroll.ensureWidgetVisible(slider); self.pump(.03)
        option=QStyleOptionSlider(); slider.initStyleOption(option)
        handle=slider.style().subControlRect(QStyle.CC_Slider,option,QStyle.SC_SliderHandle,slider).center()
        original=slider.value(); target=QPoint(slider.width()-12,handle.y())
        QTest.mousePress(slider,Qt.LeftButton,pos=handle); QTest.mouseMove(slider,target,20)
        QTest.mouseRelease(slider,Qt.LeftButton,pos=target)
        self.assertGreater(slider.value(),original)

    def test_guarded_connection_save_keeps_sync_enabled_and_reports_last_success(self):
        from PySide6.QtWidgets import QPushButton
        from gametime.qt_ui import SERVICE_URL
        code='e'*32
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=code)
        self.app.statistics_data.defer_sync(600)
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        with patch.object(self.app.statistics_sync,'request') as request:
            next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
            request.assert_not_called()
        self.assertTrue(self.app.settings.statistics_sync_enabled)
        self.assertEqual(self.app.statistics_sync_status(),self.app.t('Sync enabled.'))
        self.app.show(); self.app.switch_page(1); self.pump(.03)
        self.assertIn(self.app.t('Wait {minutes} min',minutes=10),self.app.statistics.sync_now.text())
        self.app._sync_busy=True; self.app.update_statistics_sync_controls()
        self.assertEqual(self.app.statistics.sync_now.text(),self.app.t('Syncing…'))
        self.app.statistics_sync.results.put(((SERVICE_URL,code,self.app.statistics_sync.generation),[],''))
        with patch('gametime.qt_ui.datetime') as clock:
            clock.now.return_value=datetime(2026,10,22,12,34)
            self.app.poll_statistics_sync()
        self.assertIn('2026-10-22 12:34',self.app.statistics_sync_status())
        self.assertFalse(self.app.statistics.sync_now.isEnabled())

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

    def test_statistics_show_named_computer_times_for_each_game_and_selected_day(self):
        from PySide6.QtCore import Qt
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        day=date.today().isoformat(); yesterday=(date.today()-timedelta(days=1)).isoformat(); group='a'*32
        self.store.add_usage({(day,self.games[0].id):120,(yesterday,self.games[0].id):60})
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_group=group,statistics_device_name='Main PC')
        identities=[]
        for index,seconds in enumerate((300,90)):
            remote=Store(self.base/('origin'+str(index)+'.sqlite3'))
            try:
                remote.upsert([self.games[0]]); remote.add_usage({(day,self.games[0].id):seconds,(yesterday,self.games[0].id):30})
                snapshot=StatisticsData(remote).snapshot(group,'Laptop'); identities.append(snapshot['device'])
                self.app.statistics_data.ingest(snapshot,group)
            finally: remote.close()
        self.app.switch_page(1); stats=self.app.statistics
        def rows():
            return {stats.games_table.item(i,1).data(Qt.UserRole):(stats.games_table.item(i,1).text(),stats.games_table.item(i,3).text()) for i in range(stats.games_table.rowCount())}
        self.assertEqual(stats.report.total,630); self.assertEqual(len(stats.report.games),1)
        shown=rows(); self.assertEqual(shown['local'],('Main PC (ez a gép)','00:03:00'))
        self.assertEqual(shown[identities[0]],('Laptop · '+identities[0][:8],'00:05:30'))
        self.assertEqual(shown[identities[1]],('Laptop · '+identities[1][:8],'00:02:00'))
        stats.choose_day(day); self.assertEqual(rows()['local'][1],'00:02:00'); self.assertEqual(rows()[identities[0]][1],'00:05:00')
        stats.devices.setCurrentIndex(stats.devices.findData(identities[1])); self.assertEqual(set(rows()),{identities[1]})
        self.app.set_language('en'); stats=self.app.statistics; self.assertEqual(stats.games_table.horizontalHeaderItem(1).text(),'Computer')
        stats.devices.setCurrentIndex(stats.devices.findData('local')); self.assertEqual(rows()['local'][0],'Main PC (this computer)')
        self.assertEqual(self.store.totals(day),{self.games[0].id:120})

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

    def test_new_cloud_code_needs_account_and_retains_existing_local_profile(self):
        from PySide6.QtWidgets import QPushButton,QLabel
        from gametime.statistics_auth import MESSAGES
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
        self.assertFalse(self.store.settings().statistics_sync_enabled)
        self.assertEqual(self.store.settings().limit_seconds,7200)
        self.assertIn(self.app.t(MESSAGES['session']),[w.text() for w in window.findChildren(QLabel)])
        self.assertFalse(self.app._auth_busy)

    def test_account_result_after_closed_dialog_saves_refresh_and_recovers_pending_code(self):
        from PySide6.QtWidgets import QPushButton,QLineEdit
        from gametime.statistics_sync import group_code
        from test_statistics_auth import session
        original=session(); self.app.account_session=original; self.store.save_account_session(original)
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        code=group_code(next(w for w in window.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code')).text())
        with patch.object(self.app.account_auth,'request',return_value=True) as request:
            next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
            request.assert_called_once_with('activate',original,code)
        self.assertEqual(self.store.pending_connection(),code); self.assertFalse(self.store.settings().statistics_sync_enabled)
        window.reject(); self.pump(.02)
        rotated={**original,'refresh_token':'new-private-refresh-token'}
        self.app.account_auth.results.put((('activate',original,0),[{'ok':True,'session':rotated}],''))
        self.app.poll_account(); self.assertEqual(self.store.account_session(),rotated)
        self.assertFalse(self.store.settings().statistics_sync_enabled)
        self.app.statistics_sync_dialog(); reopened=self.app._dialogs[-1]
        field=next(w for w in reopened.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code'))
        self.assertEqual(group_code(field.text()),code); self.assertEqual(field.echoMode(),QLineEdit.Password)
        with patch.object(self.app.account_auth,'request',return_value=True),patch.object(self.app,'request_statistics_sync'):
            next(b for b in reopened.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
            changed=replace(self.app.settings,limit_seconds=9000)
            self.store.save_settings(changed); self.app.settings=self.app.catalog.settings=changed
            self.app.account_auth.results.put((('activate',rotated,0),[{'ok':True,'session':rotated}],''))
            self.app.poll_account()
        self.assertEqual(self.store.settings().statistics_sync_group,code)
        self.assertEqual(self.store.pending_connection(),'')
        self.assertEqual(self.store.settings().limit_seconds,9000)

    def test_replacing_managed_code_requires_confirmation_and_does_not_commit_on_decline(self):
        from PySide6.QtWidgets import QPushButton,QMessageBox
        from test_statistics_auth import session
        self.app.account_session=session(); self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        with patch.object(self.app.account_auth,'request',return_value=True) as request:
            next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
            with patch('gametime.qt_account.QMessageBox.question',return_value=QMessageBox.No) as confirm:
                self.app.account_auth.results.put((('activate',session(),0),[{'error':'other_group','session':session()}],'other group'))
                self.app.poll_account(); confirm.assert_called_once()
            self.assertEqual(request.call_count,1)
        self.assertFalse(self.store.settings().statistics_sync_enabled)

    def test_saved_connection_code_is_hidden_until_explicitly_revealed_and_copies_while_hidden(self):
        from PySide6.QtWidgets import QLineEdit,QPushButton
        from gametime.statistics_sync import display_code
        saved='0123456789abcdef0123456789abcdef'
        settings=replace(self.app.settings,statistics_sync_group=saved)
        self.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        code=next(w for w in window.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code'))
        buttons={b.text():b for b in window.findChildren(QPushButton)}
        expected=display_code(saved)
        self.assertEqual(code.text(),expected); self.assertNotEqual(code.displayText(),expected)
        self.assertEqual(code.echoMode(),QLineEdit.Password)
        with patch('gametime.qt_ui.QApplication.clipboard') as clipboard:
            buttons[self.app.t('Copy')].click()
            clipboard.return_value.setText.assert_called_once_with(expected)
        self.assertEqual(code.echoMode(),QLineEdit.Password)
        reveal=buttons[self.app.t('Show code')]; reveal.click()
        self.assertEqual(code.displayText(),expected); self.assertEqual(reveal.text(),self.app.t('Hide code'))
        reveal.click(); self.assertNotEqual(code.displayText(),expected)
        reveal.click(); window.close(); self.pump(.02)
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        reopened=next(w for w in window.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code'))
        self.assertEqual(reopened.echoMode(),QLineEdit.Password)
        self.assertEqual(self.store.settings().statistics_sync_group,saved)

    def test_revealed_code_is_hidden_when_window_is_left_hidden_or_code_is_regenerated(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QLineEdit,QPushButton
        self.app.statistics_sync_dialog(); window=self.app._dialogs[-1]
        code=next(w for w in window.findChildren(QLineEdit) if w.accessibleName()==self.app.t('Connection code'))
        buttons={b.text():b for b in window.findChildren(QPushButton)}; reveal=buttons[self.app.t('Show code')]
        reveal.click(); self.qt.sendEvent(window,QEvent(QEvent.WindowDeactivate))
        self.assertEqual(code.echoMode(),QLineEdit.Password); self.assertFalse(reveal.isChecked())
        reveal.click(); window.hide()
        self.assertEqual(code.echoMode(),QLineEdit.Password); self.assertFalse(reveal.isChecked())
        window.show(); self.assertEqual(code.echoMode(),QLineEdit.Password)
        original=code.text(); reveal.click(); buttons[self.app.t('New code')].click()
        self.assertNotEqual(code.text(),original); self.assertEqual(code.echoMode(),QLineEdit.Password)
        window.reject(); self.assertEqual(self.store.settings().statistics_sync_group,'')

    def test_statistics_average_since_installation_and_day_drilldown(self):
        today=date.today(); start=today-timedelta(days=3)
        with self.store.db: self.store.db.execute("UPDATE settings SET value=? WHERE key='tracking_started_on'",(start.isoformat(),))
        self.store.add_usage({(today.isoformat(),self.games[0].id):1200,(start.isoformat(),self.games[1].id):600})
        self.store.set_hidden(self.games[1].id,True); self.app.switch_page(1)
        stats=self.app.statistics; self.assertEqual(stats.report.average_days,4); self.assertEqual(stats.report.average,450)
        self.assertEqual(stats.games_table.rowCount(),2); stats.choose_day(today.isoformat()); self.assertEqual(stats.games_table.rowCount(),1)
        stats.show_period(); self.assertEqual(stats.games_table.rowCount(),2)
        recent=(today-timedelta(days=1)).isoformat()
        stats.start.setText(recent); stats.end.setText(today.isoformat()); stats.refresh()
        self.assertEqual(stats.report.average_days,2); self.assertEqual(stats.report.average,600)
        self.assertIn(recent,stats.average_note.text()); self.assertIn(recent,stats.average_label.toolTip())
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
            exclude=next(call.args[1] for call in menu.addAction.call_args_list if call.args[0]==self.app.t('Exclude from tracking'))
            exclude(); self.assertFalse(self.app.catalog.enabled(game)); self.assertTrue(self.app.catalog.enabled(self.games[0]))
            menus.reset_mock(); self.app.game_menu(game.id)
            track=next(call.args[1] for call in menu.addAction.call_args_list if call.args[0]==self.app.t('Track game'))
            track(); self.assertTrue(self.app.catalog.enabled(game))
            hide=next(call.args[1] for call in menu.addAction.call_args_list if call.args[0]==self.app.t('Hide from library'))
            hide(); self.assertIn(game.id,self.store.hidden_ids()); self.assertNotIn(self.games[0].id,self.store.hidden_ids())

    def test_artwork_is_the_launch_button_footer_only_selects_and_double_click_starts_once(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        card=self.app.cards[self.games[0].id]; card.resize(260,260); card.grab()
        self.assertGreater(card.play.width(),card.width()-5); self.assertEqual(card.play.y(),1)
        self.assertGreater(card.more.y(),card.play.geometry().bottom())
        self.assertGreater(card.more.x(),card.width()-60)
        with patch.object(self.app,'launch_selected') as launch:
            QTest.mouseClick(card,Qt.LeftButton,pos=QPoint(25,215)); launch.assert_not_called()
            self.assertEqual(self.app.selected_id,card.game.id)
            QTest.mouseClick(card.play,Qt.LeftButton)
            QTest.mouseDClick(card.play,Qt.LeftButton); QTest.mouseRelease(card.play,Qt.LeftButton)
            launch.assert_called_once()
            card.set_state(0,False,False); QTest.mouseClick(card.play,Qt.LeftButton)
            launch.assert_called_once()

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

    def test_wide_and_portrait_covers_use_the_same_large_square_without_distortion(self):
        from PySide6.QtGui import QPixmap,QPainter,QColor
        from gametime.qt_widgets import GameCard
        for width,height in ((200,100),(100,200)):
            image=QPixmap(width,height); image.fill(QColor('#c02020'))
            painter=QPainter(image); painter.fillRect(width//2-10,height//2-10,20,20,QColor('#00ff00')); painter.end()
            card=GameCard(self.games[0],self.app.t); card.resize(240,260); card.art=(image,None)
            rendered=card.grab().toImage(); pixels=[]
            for y in range(22,166):
                for x in range(1,239):
                    color=rendered.pixelColor(x,y)
                    if color.green()>180 and color.red()<40 and color.blue()<40: pixels.append((x,y))
            self.assertTrue(pixels)
            span_x=max(x for x,y in pixels)-min(x for x,y in pixels)
            span_y=max(y for x,y in pixels)-min(y for x,y in pixels)
            self.assertLessEqual(abs(span_x-span_y),2)
            self.assertGreater(span_x,25)
            self.assertGreater(rendered.pixelColor(120,25).red(),100)
            self.assertLess(rendered.pixelColor(30,80).red(),100)
            card.deleteLater()

    def test_small_and_large_icons_keep_the_same_visible_size(self):
        from PySide6.QtGui import QPixmap,QColor
        from gametime.qt_widgets import GameCard
        bounds=[]
        for size in (32,256):
            image=QPixmap(size,size); image.fill(QColor('#00ff00'))
            card=GameCard(self.games[0],self.app.t); card.resize(240,260); card.art=(None,image)
            rendered=card.grab().toImage()
            pixels=[(x,y) for y in range(15,175) for x in range(30,210) if rendered.pixelColor(x,y).green()>200 and rendered.pixelColor(x,y).red()<30]
            bounds.append((min(x for x,y in pixels),max(x for x,y in pixels),min(y for x,y in pixels),max(y for x,y in pixels)))
            card.deleteLater()
        self.assertEqual(bounds[0],bounds[1]); self.assertGreater(bounds[0][1]-bounds[0][0],140)

    def test_small_window_is_responsive_and_cards_reflow(self):
        self.app.show(); self.app.resize(1000,700); self.pump()
        self.assertLessEqual(self.app.width(),1000); self.assertLessEqual(self.app.height(),700)
        self.assertGreaterEqual(self.app.grid.columns,2)
        for page in (1,2,0): self.app.switch_page(page); self.pump(); self.assertLessEqual(self.app.width(),1000)

if __name__=='__main__': unittest.main()
