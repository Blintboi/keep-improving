from dataclasses import replace
from datetime import datetime, timedelta
import os
import unittest
from unittest.mock import patch

import test_qt_ui as fixtures


@unittest.skipUnless(os.name == 'nt', 'Windows Qt required')
class FocusInterfaceTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
    setUp = fixtures.QtInterfaceTests.setUp
    tearDown = fixtures.QtInterfaceTests.tearDown
    pump = fixtures.QtInterfaceTests.pump

    def test_navigation_shows_literal_ampersand_after_language_switch(self):
        from PySide6.QtGui import QKeySequence
        self.assertEqual(self.app.nav[4].text(), 'Fókusz mód')
        self.app.set_language('en')
        self.assertEqual(self.app.nav[4].text(), 'Focus mode')
        self.assertTrue(QKeySequence.mnemonic(self.app.nav[4].text()).isEmpty())
        self.app.set_language('hu')
        self.assertEqual(self.app.nav[4].text(), 'Fókusz mód')

    def test_language_popup_fits_both_rows_and_matches_control_width(self):
        from PySide6.QtCore import QPoint,QRect
        combo=self.app.language
        self.app.show(); self.pump(.05)
        for language in ('en','hu'):
            self.app.set_language(language); combo.showPopup(); self.pump(.05)
            view=combo.view(); row_heights=[view.sizeHintForRow(i) for i in range(combo.count())]
            self.assertEqual(len(row_heights),2)
            self.assertGreaterEqual(min(row_heights),32)
            self.assertEqual(view.verticalScrollBar().maximum(),0)
            self.assertGreaterEqual(view.viewport().height(),sum(row_heights))
            self.assertGreaterEqual(view.window().width(),combo.width())
            bounds=QRect(self.app.mapToGlobal(QPoint(0,0)),self.app.size())
            self.assertTrue(bounds.contains(view.window().geometry()))
            self.assertLessEqual(view.window().geometry().bottom(),combo.mapToGlobal(QPoint(0,0)).y())
            combo.hidePopup()

    def test_long_popup_stays_inside_window_and_scrolls(self):
        from PySide6.QtCore import QPoint,QRect,Qt
        from PySide6.QtTest import QTest
        self.app.resize(1000,700); self.app.show(); self.app.switch_page(2); self.app.overlay_enabled.setChecked(True)
        combo=self.app.overlay_screen
        for i in range(50): combo.addItem('Example display '+str(i),str(i))
        self.app.settings_scroll.ensureWidgetVisible(combo); self.pump(.1)
        combo.showPopup(); self.pump(.3)
        view=combo.view(); popup=view.window(); bounds=QRect(self.app.mapToGlobal(QPoint()),self.app.size())
        self.assertTrue(bounds.contains(popup.geometry()))
        bar=view.verticalScrollBar(); self.assertGreater(bar.maximum(),0)
        point=view.viewport().mapTo(popup,view.viewport().rect().center()); before=bar.value()
        QTest.wheelEvent(popup.windowHandle(),point,QPoint(0,-120)); self.pump(.05)
        self.assertGreater(bar.value(),before)
        combo.hidePopup()

    def test_library_source_popup_opens_down_consistently_when_there_is_room(self):
        from PySide6.QtCore import QPoint,QRect
        self.app.resize(1100,800); self.app.show(); self.app.switch_page(0); self.pump(.1)
        combo=self.app.source_filter
        bounds=QRect(self.app.mapToGlobal(QPoint()),self.app.size())
        anchor=combo.mapToGlobal(QPoint()); below=anchor.y()+combo.height()
        for index in (0,1,0):
            combo.setCurrentIndex(index); combo.showPopup(); self.pump(.1)
            popup=combo.view().window(); self.assertTrue(bounds.contains(popup.geometry()))
            self.assertGreaterEqual(popup.geometry().top(),below)
            combo.hidePopup()

    def test_focus_list_fits_up_to_three_rows_without_scrollbar(self):
        self.app.show(); self.app.switch_page(4)
        listing=self.app.focus_page.block_lists['site']
        for count in (1,2,3,4):
            sites=[f'example{i}.com' for i in range(count)]
            self.app.focus.configure(replace(self.app.focus.settings,block_sites=sites))
            self.app.focus_page.refresh(force=True); self.pump(.05)
            self.assertEqual(listing.verticalScrollBar().maximum()>0,count>3)
            self.assertGreaterEqual(listing.viewport().height(),sum(listing.sizeHintForRow(i) for i in range(min(3,count))))

    def test_linked_activity_supports_computer_filter_and_colored_chart(self):
        from PySide6.QtCore import Qt
        from gametime.focus import Focus
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        group='ab'*16; day=datetime.now().date().isoformat()
        other=Store(self.base/'remote-activity.sqlite')
        other.save_settings(replace(other.settings(),statistics_sync_enabled=True,statistics_sync_group=group))
        focus=Focus(other); remote=StatisticsData(other,focus)
        with other.db:
            for kind,key,seconds in [('app',r'c:\brave\brave.exe',60),('site','example.com',40)]:
                other.db.execute('INSERT INTO activity_items VALUES (?,?,?)',(kind,key,key))
                other.db.execute('INSERT INTO activity_usage VALUES (?,?,?,?)',(day,kind,key,seconds))
        snapshot=remote.snapshot(group,'Laptop'); other.close()
        now=datetime.now().astimezone()
        self.app.focus._credit('app',r'c:\brave\brave.exe','brave.exe',now,now+timedelta(seconds=30),30)
        self.app.focus._credit('site','example.com','example.com',now,now+timedelta(seconds=20),20)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_group=group)
        self.app.statistics_data.ingest(snapshot,group); self.app.switch_page(1)
        stats=self.app.statistics
        for category, total,local_total,remote_total in [('apps',90,30,60),('websites',60,20,40),('all',90,30,60)]:
            stats.category.setCurrentIndex(stats.category.findData(category)); stats.refresh()
            self.assertEqual(stats.report.total,total)
            self.assertTrue(stats.devices.isEnabled())
            self.assertIn(snapshot['device'],stats.chart.computer_segments[day])
            self.assertEqual({key:sum(values.values()) for key,values in stats.chart.computer_segments[day].items()},
                             {'local':local_total,snapshot['device']:remote_total})
            self.assertNotEqual(stats.chart.device_colors['local'],stats.chart.device_colors[snapshot['device']])
            stats.chart.resize(700,220); stats.chart.grab()
            remote_region=next(rect for rect,d,identity in stats.chart.computer_regions if d==day and identity==snapshot['device'])
            local_region=next(rect for rect,d,identity in stats.chart.computer_regions if d==day and identity=='local')
            self.assertFalse(remote_region.intersects(local_region))
            self.assertIn('Laptop',stats.chart.tooltip_at(remote_region.center()))
            for row,(key,identity) in enumerate(stats._breakdown_keys):
                self.assertEqual(stats.games_table.item(row,0).foreground().color().name(),stats.chart.series[key][1])
                self.assertEqual(stats.games_table.item(row,1).foreground().color().name(),stats.chart.device_colors[identity])
            stats.devices.setCurrentIndex(stats.devices.findData(snapshot['device']))
            self.assertEqual(stats.report.total,remote_total)
            stats.devices.setCurrentIndex(stats.devices.findData('local'))
            self.assertEqual(stats.report.total,local_total)
            stats.devices.setCurrentIndex(stats.devices.findData('all'))

    def test_linked_computers_are_identified_when_only_one_has_data(self):
        from PySide6.QtCore import Qt
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        group='cd'*16; day=datetime.now().date().isoformat()
        other=Store(self.base/'empty-computer.sqlite')
        snapshot=StatisticsData(other).snapshot(group,'Laptop'); other.close()
        self.store.add_usage({(day,self.games[0].id):120})
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_group=group)
        self.app.statistics_data.ingest(snapshot,group); self.app.show(); self.app.switch_page(1)
        stats=self.app.statistics; stats.refresh(); self.pump(.1)
        self.assertTrue(stats.chart.show_computer_markers)
        self.assertFalse(stats.computer_legend.isHidden())
        self.assertEqual({stats.computer_legend.item(i).data(Qt.UserRole) for i in range(stats.computer_legend.count())},
                         {'local',snapshot['device']})
        self.assertIn('Laptop',[stats.computer_legend.item(i).text() for i in range(stats.computer_legend.count())])
        stats.chart.resize(700,220); pixmap=stats.chart.grab()
        group_rect=next(rect for rect,d,identity in stats.chart.computer_regions if d==day and identity=='local')
        segment=next(rect for rect,d,key in stats.chart.segment_regions if d==day)
        self.assertGreater(segment.left()-group_rect.left(),4)
        image=pixmap.toImage(); ratio=pixmap.devicePixelRatio()
        pixel=image.pixelColor(int((group_rect.left()+2)*ratio),int(group_rect.center().y()*ratio))
        self.assertEqual(pixel.name(),stats.chart.device_colors['local'])
        stats.devices.setCurrentIndex(stats.devices.findData('local'))
        self.assertTrue(stats.chart.show_computer_markers)
        self.assertEqual(stats.computer_legend.count(),1)
        self.assertEqual(stats.computer_legend.item(0).data(Qt.UserRole),'local')
        stats.devices.setCurrentIndex(stats.devices.findData(snapshot['device']))
        self.assertTrue(stats.chart.show_computer_markers)
        self.assertEqual(stats.computer_legend.item(0).data(Qt.UserRole),snapshot['device'])
        stats.devices.setCurrentIndex(stats.devices.findData('local'))
        self.app.set_language('en')
        self.assertIn('this computer',stats.computer_legend.item(0).text())
        self.assertEqual(stats.computer_legend.accessibleName(),'Computer colors')

    def test_computer_legend_wraps_inside_the_chart(self):
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        group='ef'*16; other=Store(self.base/'legend-computers.sqlite')
        snapshot=StatisticsData(other).snapshot(group,'Laptop'); other.close()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,statistics_sync_group=group)
        for index in range(8):
            self.app.statistics_data.ingest(dict(snapshot,device=f'{index+1:032x}',name=f'Example computer {index+1}'),group)
        self.app.resize(1000,700); self.app.show(); self.app.switch_page(1)
        stats=self.app.statistics; stats.refresh(); self.pump(.2)
        legend=stats.computer_legend; self.assertEqual(legend.count(),9)
        self.assertEqual(legend.verticalScrollBar().maximum(),0)
        bounds=legend.viewport().rect()
        for index in range(legend.count()):
            self.assertTrue(bounds.contains(legend.visualItemRect(legend.item(index))),index)

    def test_exclude_from_statistics_and_restore_from_dialog(self):
        from PySide6.QtWidgets import QListWidget
        now=datetime.now().astimezone(); day=now.date().isoformat()
        path=str(self.base/'other-app.exe').lower()
        self.app.focus._credit('app',path,'other-app.exe',now,now+timedelta(seconds=30),30)
        self.app.switch_page(1); stats=self.app.statistics
        stats.category.setCurrentIndex(stats.category.findData('apps')); stats.refresh()
        self.assertEqual(stats.games_table.rowCount(),1)
        stats.games_table.selectRow(0); self.assertTrue(stats.exclude_app_button.isEnabled())
        stats.exclude_app_button.click(); self.assertEqual(stats.games_table.rowCount(),0)
        self.assertTrue(self.app.focus.settings.app_excluded(path))
        self.app.focus_page.excluded_apps_dialog(); dialog=self.app._dialogs[-1]
        listing=dialog.findChild(QListWidget); self.assertEqual(listing.count(),1)
        listing.setCurrentRow(0)
        from PySide6.QtWidgets import QPushButton
        restore=next(b for b in dialog.findChildren(QPushButton) if b.text()==self.app.t('Restore selected'))
        restore.click(); self.assertFalse(self.app.focus.settings.app_excluded(path))
        self.assertEqual(stats.games_table.rowCount(),1); dialog.accept()

    def test_detected_applications_can_be_selected_for_focus_blacklist(self):
        from PySide6.QtWidgets import QListWidget,QPushButton
        now=datetime.now().astimezone()
        for name in ('browser.exe','editor.exe'):
            path=str(self.base/name).lower()
            self.app.focus._credit('app',path,name,now,now+timedelta(seconds=10),10)
        self.app.focus.flush(); self.app.switch_page(4)
        self.app.focus_page.choose_detected_applications(); dialog=self.app._dialogs[-1]
        listing=dialog.findChild(QListWidget); self.assertEqual(listing.count(),2)
        listing.item(0).setSelected(True); listing.item(1).setSelected(True)
        add=next(b for b in dialog.findChildren(QPushButton) if b.text()==self.app.t('Add selected'))
        add.click()
        self.assertTrue(self.app.focus.settings.app_blocked(str(self.base/'browser.exe')))
        self.assertTrue(self.app.focus.settings.app_blocked(str(self.base/'editor.exe')))

    def test_nested_scroll_stops_at_child_edges(self):
        from PySide6.QtCore import QPoint, QPointF, Qt
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtWidgets import QListWidget, QScrollArea, QWidget
        outer=QScrollArea(self.app); content=QWidget(); outer.setWidget(content)
        inner=QListWidget(content); inner.resize(200,100)
        inner.addItems([str(i) for i in range(30)]); inner.show(); outer.resize(240,140); outer.show(); self.pump(.1)
        bar=inner.verticalScrollBar(); bar.setRange(0,20)
        def wheel(delta):
            return QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(),QPoint(0,delta),
                               Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        bar.setValue(0)
        self.assertTrue(self.app.scroll_guard.eventFilter(inner.viewport(),wheel(120)))
        self.assertFalse(self.app.scroll_guard.eventFilter(inner.viewport(),wheel(-120)))
        bar.setValue(bar.maximum())
        self.assertTrue(self.app.scroll_guard.eventFilter(inner.viewport(),wheel(-120)))
        self.assertFalse(self.app.scroll_guard.eventFilter(inner.viewport(),wheel(120)))
        bar.setRange(0,0)
        self.assertFalse(self.app.scroll_guard.eventFilter(inner.viewport(),wheel(-120)))
        outer.close()

    def test_scrollbar_handles_are_wide_enough_and_draggable(self):
        from PySide6.QtCore import QPoint,Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QScrollArea,QWidget,QStyle,QStyleOptionSlider
        area=QScrollArea(self.app); area.resize(260,180)
        content=QWidget(); content.resize(1000,1000); area.setWidget(content); area.show(); self.pump(.1)
        for bar,direction in ((area.verticalScrollBar(),QPoint(0,55)),(area.horizontalScrollBar(),QPoint(55,0))):
            self.assertGreater(bar.maximum(),0)
            self.assertGreaterEqual(bar.width() if bar.orientation()==Qt.Vertical else bar.height(),12)
            option=QStyleOptionSlider(); bar.initStyleOption(option)
            handle=bar.style().subControlRect(QStyle.CC_ScrollBar,option,QStyle.SC_ScrollBarSlider,bar)
            self.assertGreaterEqual(handle.width() if bar.orientation()==Qt.Vertical else handle.height(),8)
            QTest.mousePress(bar,Qt.LeftButton,pos=handle.center())
            QTest.mouseMove(bar,handle.center()+direction,delay=20)
            QTest.mouseRelease(bar,Qt.LeftButton,pos=handle.center()+direction)
            self.assertGreater(bar.value(),0)
        area.close()

    def test_statistics_scroll_reveals_list_before_scrolling_inside(self):
        from PySide6.QtCore import QPoint,QPointF,Qt
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtWidgets import QAbstractItemView
        now=datetime.now().astimezone()
        for i in range(20):
            path=str(self.base/f'example-{i}.exe').lower()
            self.app.focus._credit('app',path,f'example-{i}.exe',now,now+timedelta(seconds=5),5)
        self.app.resize(1100,800); self.app.show(); self.app.switch_page(1)
        stats=self.app.statistics; stats.category.setCurrentIndex(stats.category.findData('apps')); stats.refresh(); self.pump(.1)
        table=stats.games_table; page=stats.scroll; outer=page.verticalScrollBar(); inner=table.verticalScrollBar()
        self.assertIs(table.parentWidget(),stats.details_panel)
        self.assertEqual(table.verticalScrollMode(),QAbstractItemView.ScrollPerPixel)
        self.assertEqual(inner.singleStep(),12); self.assertGreater(inner.maximum(),0)
        def wheel(delta):
            return QWheelEvent(QPointF(5,5),QPointF(5,5),QPoint(),QPoint(0,delta),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        target=table.mapTo(page.widget(),QPoint(0,0)).y()
        from PySide6.QtWidgets import QApplication
        outer.setValue(target-page.viewport().height()+100); inner.setValue(inner.maximum()//2)
        before=outer.value(); QApplication.sendEvent(table.viewport(),wheel(-120))
        self.assertGreater(outer.value(),before); self.assertEqual(inner.value(),inner.maximum()//2)
        # The table can already be visible while the buttons and bottom of its card are not.
        outer.setValue(target+table.height()-page.viewport().height()+2); inner.setValue(inner.maximum()//2)
        table_bottom=table.mapTo(page.viewport(),QPoint()).y()+table.height()
        card_bottom=lambda:stats.details_panel.mapTo(page.viewport(),QPoint()).y()+stats.details_panel.height()
        self.assertLessEqual(table_bottom,page.viewport().height())
        self.assertGreater(card_bottom(),page.viewport().height())
        before=outer.value(); QApplication.sendEvent(table.viewport(),wheel(-120))
        self.assertGreater(outer.value(),before); self.assertEqual(inner.value(),inner.maximum()//2)
        for _ in range(12):
            if card_bottom()<=page.viewport().height(): break
            QApplication.sendEvent(table.viewport(),wheel(-120))
        self.assertLessEqual(card_bottom(),page.viewport().height())
        before_outer,before_inner=outer.value(),inner.value()
        QApplication.sendEvent(table.viewport(),wheel(-120))
        self.assertEqual(outer.value(),before_outer); self.assertGreater(inner.value(),before_inner)
        outer.setValue(target); before=inner.value(); QApplication.sendEvent(table.viewport(),wheel(-120))
        self.assertGreater(inner.value(),before); self.assertLessEqual(inner.value()-before,48)
        # Add content below the list so the top edge can scroll out of view.
        from PySide6.QtWidgets import QWidget
        extra=QWidget(); extra.setFixedHeight(1500); page.widget().layout().addWidget(extra)
        page.widget().layout().activate(); self.pump(.3)
        target=table.mapTo(page.widget(),QPoint(0,0)).y()
        outer.setValue(target+100); before=outer.value()
        self.assertGreater(before,target)
        self.assertTrue(self.app.scroll_guard.eventFilter(table.viewport(),wheel(120))); self.assertLess(outer.value(),before)

    def test_settings_shortcuts_keep_unsaved_changes_and_follow_language(self):
        from PySide6.QtCore import QPoint
        self.app.resize(1000,700); self.app.show(); self.app.switch_page(2); self.pump(.1)
        self.app.limit.setValue(180)
        scroll=self.app.settings_scroll
        self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
        for key,control in self.app.settings_shortcuts.items():
            control.click(); self.pump(.03)
            target=self.app.settings_sections[key]
            expected=min(scroll.verticalScrollBar().maximum(),target.mapTo(self.app.settings_body,QPoint(0,0)).y())
            self.assertEqual(scroll.verticalScrollBar().value(),expected)
            self.assertEqual(self.app.limit.value(),180)
        self.app.set_language('en')
        self.assertEqual(self.app.settings_shortcuts['reminders'].text(),'Reminders')
        self.assertEqual(self.app.limit.value(),180)
        self.app.save_settings()
        from gametime.schedule import week_plans
        self.assertEqual(week_plans(self.store.settings())[0]['limit_seconds'],180*60)

    def test_synced_settings_wait_for_unsaved_edits_and_then_apply(self):
        from gametime.focus import Focus
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        group='ab'*16
        local=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=group,language='en')
        self.store.save_settings(local); self.app.settings=self.app.catalog.settings=local
        other=Store(self.base/'other-profile.sqlite3')
        other.save_settings(replace(other.settings(),statistics_sync_enabled=True,statistics_sync_group=group,language='hu'))
        other_focus=Focus(other); other_focus.configure(replace(other_focus.settings,work=40))
        snapshot=StatisticsData(other).snapshot(group,'Other computer'); other.close()
        self.app.statistics_data.ingest(snapshot,group); self.app._preferences_pending=True
        self.app.show(); self.app.switch_page(2); self.app.limit.setValue(180)
        self.app.apply_synchronized_preferences(); self.assertTrue(self.app._preferences_pending)
        self.app.switch_page(0); self.assertTrue(self.app._preferences_pending)
        self.app.save_settings(); self.app.apply_synchronized_preferences()
        self.assertFalse(self.app._preferences_pending)
        self.assertEqual(self.app.focus.settings.work,40)
        self.assertEqual(self.app.settings.language,'hu')
        from gametime.schedule import week_plans
        self.assertEqual(week_plans(self.app.settings)[0]['limit_seconds'],180*60)

    def test_synced_game_preferences_apply_when_game_is_discovered_later(self):
        from gametime.focus import Focus
        from gametime.model import Game
        from gametime.statistics_sync import StatisticsData
        from gametime.store import Store
        group='cd'*16
        local=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group=group)
        self.store.save_settings(local); self.app.settings=self.app.catalog.settings=local
        other=Store(self.base/'other-late.sqlite3')
        game=Game('steam:987','Example Game','Steam',str(self.base/'other-game'))
        other.upsert([game]); other.save_settings(replace(other.settings(),statistics_sync_enabled=True,statistics_sync_group=group,
                                                          game_limits={'steam:987':900}))
        other.set_enabled(game.id,False); Focus(other)
        snapshot=StatisticsData(other).snapshot(group,'Other computer'); other.close()
        self.app.statistics_data.ingest(snapshot,group); self.app._preferences_pending=True
        self.app.apply_synchronized_preferences(); self.assertFalse(self.app._preferences_pending)
        discovered=replace(game,root=str(self.base/'local-game'))
        self.store.upsert([discovered]); self.app.catalog.games[game.id]=discovered; self.app.catalog_changed()
        self.assertTrue(self.app._preferences_pending); self.app.apply_synchronized_preferences()
        self.assertFalse(self.app.catalog.enabled(discovered))
        self.assertEqual(self.app.settings.game_limits[game.id],900)

    def test_activity_changes_schedule_rate_limited_sync_without_periodic_requests(self):
        from gametime.tracker import Sample
        now=datetime.now().astimezone()
        path=r'C:\Brave\brave.exe'
        bridge=unittest.mock.Mock(); self.app.browser_bridge=bridge
        with patch.object(self.app,'schedule_statistics_event') as schedule, patch.object(self.app,'update_focus_policy'):
            bridge.website.return_value='example.com'
            self.app.focus_tick(Sample(now,0,path,'12:1'))
            self.app.focus_tick(Sample(now+timedelta(seconds=1),1,path,'12:1'))
            schedule.assert_not_called()
            bridge.website.return_value='other.example'
            self.app.focus_tick(Sample(now+timedelta(seconds=2),2,path,'12:1'))
            schedule.assert_called_once_with(60)
            schedule.reset_mock(); bridge.website.return_value=''
            self.app.focus_tick(Sample(now+timedelta(seconds=3),3,r'C:\Apps\editor.exe','13:1'))
            schedule.assert_called_once_with(60)
        self.app.browser_bridge=None

    def test_activity_is_available_in_statistics(self):
        from gametime.tracker import Sample
        now = datetime.now().astimezone()
        for second in range(3):
            self.app.focus.tick(Sample(now + timedelta(seconds=second), second, r'C:\Brave\brave.exe', '12:1'), 'example.com')
        self.app.switch_page(1); page=self.app.statistics
        page.category.setCurrentIndex(page.category.findData('apps')); self.assertEqual(page.report.total,2)
        page.category.setCurrentIndex(page.category.findData('websites')); self.assertEqual(page.report.total,2)
        page.tracking.setChecked(False); self.assertFalse(self.app.focus.settings.tracking)
        self.assertEqual(self.store.totals(now.date()), {})

    def test_timer_pause_reset_and_immediate_policy_updates(self):
        page = self.app.focus_page
        with patch.object(self.app, 'focus_awake', return_value=100), patch.object(self.app, 'update_focus_policy') as update:
            page.toggle(); self.assertTrue(self.app.focus.restricting)
            page.toggle(); self.assertFalse(self.app.focus.restricting)
            page.toggle(); self.assertTrue(self.app.focus.restricting)
            page.reset(); self.assertFalse(self.app.focus.restricting)
            self.assertEqual(update.call_count, 4)

    def test_only_blocked_current_app_is_minimized_and_protected_game_gate_is_preserved(self):
        from gametime.tracker import Sample
        self.app.focus.configure(replace(self.app.focus.settings, block_apps=[str(self.exe)]))
        self.app.focus.start(100)
        current = Sample(datetime.now().astimezone(), 100, str(self.exe), '12:345')
        with patch('gametime.qt_ui.win32.minimize_game') as minimize, patch.object(self.app, 'minimization_allowed', return_value=True):
            self.app.focus_tick(current)
            minimize.assert_called_once_with(str(self.exe), '12:345', consented=True)
            self.app.focus.pause(100); minimize.reset_mock(); self.app.focus_tick(current)
            minimize.assert_not_called()
        self.app.focus.start(100)
        with patch('gametime.qt_ui.win32.minimize_game') as minimize, patch.object(self.app, 'minimization_allowed', return_value=False):
            self.app.focus_tick(current); minimize.assert_not_called()

    def test_blacklist_keeps_unlisted_browser_and_monitor_accessible(self):
        from gametime.tracker import Sample
        from types import SimpleNamespace
        self.app.focus.configure(replace(self.app.focus.settings, block_sites=['example.com']))
        self.app.focus.start(100)
        current = Sample(datetime.now().astimezone(), 100, r'C:\Brave\brave.exe', '12:345')
        with patch('gametime.qt_ui.win32.minimize_game') as minimize, patch.object(self.app, 'minimization_allowed', return_value=True):
            self.app.focus_tick(current); minimize.assert_not_called()
            fake = SimpleNamespace(website=lambda path: 'docs.example.com', update=lambda _: None)
            self.app.browser_bridge = fake
            self.app.focus_tick(current); minimize.assert_not_called()
            self.app.browser_bridge = None
            self.app.focus_tick(replace(current, identity=f'{os.getpid()}:345'))
            minimize.assert_not_called()

    def test_hidden_focus_page_does_not_query_or_rebuild_activity(self):
        from gametime.tracker import Sample
        current = Sample(datetime.now().astimezone(), 100, str(self.exe), '12:345')
        self.app.hide()
        with patch.object(self.app.focus, 'usage') as usage, patch.object(self.app.focus_page, 'refresh') as refresh:
            self.app.focus_tick(current); self.app.focus_tick(replace(current, awake=101, wall=current.wall + timedelta(seconds=1)))
            usage.assert_not_called(); refresh.assert_not_called()

    def test_focus_dialogs_preserve_input_and_language_switch(self):
        from PySide6.QtWidgets import QPlainTextEdit
        page = self.app.focus_page
        self.app.switch_page(4); page.rules_dialog()
        dialog = self.app._dialogs[-1]
        editors = dialog.findChildren(QPlainTextEdit)
        self.assertEqual(len(editors), 2)
        editors[-1].setPlainText('youtube.com')
        self.app.set_language('en'); page.refresh(force=True)
        self.assertEqual(editors[-1].toPlainText(), 'youtube.com')
        self.assertEqual(page.rule_tabs.tabText(1), 'Applications')
        dialog.reject()

    def test_url_can_be_blacklisted_before_it_has_been_visited(self):
        page=self.app.focus_page
        page.url_input.setText('https://example.com/some/path?secret=value')
        page.add_url_button.click()
        self.assertEqual(self.app.focus.settings.block_sites,['example.com'])
        self.assertEqual(page.url_input.text(),'')
        page.url_input.setText('https://example.com/other'); page.add_url_button.click()
        self.assertEqual(self.app.focus.settings.block_sites,['example.com'])
        page.url_input.setText('file:///private'); page.add_url_button.click()
        self.assertEqual(self.app.focus.settings.block_sites,['example.com'])

    def test_statistics_categories_refresh_chart_totals_and_exclude_games(self):
        from gametime.tracker import Sample
        now=datetime.now().astimezone(); day=now.date().isoformat()
        self.store.add_usage({(day,self.games[0].id):40})
        focus=self.app.focus
        focus._credit('app',str(self.exe),'fixture.exe',now,now+timedelta(seconds=40),40)
        focus._credit('app',r'C:\Work\editor.exe','editor.exe',now,now+timedelta(seconds=20),20)
        focus._credit('app',r'C:\Brave\brave.exe','brave.exe',now,now+timedelta(seconds=60),60)
        focus._credit('site','example.com','example.com',now,now+timedelta(seconds=35),35)
        stats=self.app.statistics; stats.start.setText(day); stats.end.setText(day)
        for category,expected in (('games',40),('apps',80),('websites',35),('all',120)):
            stats.category.setCurrentIndex(stats.category.findData(category)); stats.refresh()
            self.assertEqual(stats.report.total,expected,category)
            self.assertEqual(sum(stats.report.days.values()),expected)
            self.assertEqual(sum(row[4] for row in stats.computer_history),expected)
        stats.choose_day(day); self.app.set_language('en')
        self.assertEqual(stats.category.currentData(),'all')
        self.assertEqual(stats.selected_day,day)

    def test_branding_and_cursors_match_clickable_controls(self):
        from PySide6.QtCore import Qt
        from gametime.qt_widgets import glyph
        self.assertEqual(self.app.windowTitle(),'Keep Improving')
        self.assertEqual(self.app.cursor().shape(),Qt.ArrowCursor)
        self.assertEqual(self.app.focus_page.clock.cursor().shape(),Qt.ArrowCursor)
        self.assertEqual(self.app.focus_page.url_input.cursor().shape(),Qt.IBeamCursor)
        self.assertEqual(self.app.focus_page.add_url_button.cursor().shape(),Qt.PointingHandCursor)
        self.assertNotEqual(glyph('focus').pixmap(20,20).toImage(),glyph('stats').pixmap(20,20).toImage())
