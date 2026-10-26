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

    def test_focus_page_tracks_apps_and_sites_and_selects_rules(self):
        from gametime.tracker import Sample
        from PySide6.QtCore import Qt
        now = datetime.now().astimezone()
        for second in range(3):
            self.app.focus.tick(Sample(now + timedelta(seconds=second), second, r'C:\Brave\brave.exe', '12:1'), 'example.com')
        page = self.app.focus_page
        self.app.switch_page(4)
        page.sections.setCurrentIndex(1)
        self.assertEqual(page.tables['app'].rowCount(), 1)
        self.assertEqual(page.tables['site'].rowCount(), 1)
        self.assertEqual(page.tables['app'].item(0, 0).data(Qt.UserRole), r'c:\brave\brave.exe')
        page.tables['app'].selectRow(0); page.add_selected('block')
        self.assertTrue(self.app.focus.settings.app_blocked(r'C:\Brave\brave.exe'))
        page.add_selected('remove')
        self.assertFalse(self.app.focus.settings.app_blocked(r'C:\Brave\brave.exe'))
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
        self.assertEqual(page.tables['app'].horizontalHeaderItem(0).text(), 'Applications')
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
