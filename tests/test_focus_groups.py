"""Live budget membership, whole categories, and lifetime focus rounds."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch,Mock
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget,QPushButton
import test_qt_ui as fixture
from gametime.focus import Focus,FocusSettings
from gametime.store import Store
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target
from gametime.tracker import Sample


class FocusGroupTests(TestCase):
    def test_validation_categories_native_and_web_members(self):
        group=new_rule('Mixed',[target('app','editor.exe'),target('site','example.com'),target('game','fixture')],'mixed')
        settings=FocusSettings(block_groups=['budget:mixed','budget:mixed']).validate()
        self.assertEqual(settings.block_groups,['budget:mixed'])
        self.assertTrue(settings.app_blocked(r'C:\New\editor.exe','',[group]))
        self.assertTrue(settings.app_blocked(r'C:\Games\future.exe','fixture',[group]))
        self.assertFalse(settings.app_blocked(r'C:\Browsers\brave.exe','',[group]))
        self.assertTrue(settings.site_blocked('sub.example.com',[group]))
        self.assertFalse(settings.site_blocked('example.com.evil.org',[group]))
        self.assertFalse(settings.app_blocked(r'C:\New\editor.exe','',[]))
        self.assertFalse(settings.site_blocked('example.com',[]))
        self.assertTrue(FocusSettings(block_groups=['games']).app_blocked('new.exe','new-game'))
        self.assertFalse(FocusSettings(block_groups=['apps']).app_blocked('new.exe','new-game'))
        self.assertTrue(FocusSettings(block_groups=['apps']).app_blocked('editor.exe',''))
        self.assertFalse(FocusSettings(block_groups=['apps']).app_blocked('explorer.exe',''))
        self.assertFalse(FocusSettings(block_groups=['apps'],excluded_apps=[r'c:\new\editor.exe']).app_blocked(r'C:\New\editor.exe',''))
        for invalid in (None,'games',['unknown'],['budget:'],[{}]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError): FocusSettings(block_groups=invalid).validate()

    def test_group_policy_follows_changes_and_pause_break_stop_release(self):
        with TemporaryDirectory() as directory:
            store=Store(Path(directory)/'usage.sqlite3')
            try:
                focus=Focus(store); focus.configure(FocusSettings(block_groups=['budget:web']))
                group=new_rule('Web',[target('site','example.com')],'web')
                focus.start(0); self.assertEqual(focus.policy([group])['block'],['example.com'])
                group['members']=[target('site','other.com')]; self.assertEqual(focus.policy([group])['block'],['other.com'])
                focus.pause(1); self.assertFalse(focus.policy([group])['active'])
                focus.start(2); focus.remaining=1; focus.advance(3)
                self.assertFalse(focus.policy([group])['active']); focus.stop()
                self.assertFalse(focus.policy([group])['active'])
                restored=Focus(store); self.assertEqual(restored.settings.block_groups,['budget:web'])
                group['members']=[target('category','sites')]
                restored.start(0); self.assertEqual(restored.policy([group])['mode'],'allowlist')
                self.assertEqual(restored.policy([group])['allow'],[])
            finally: store.close()

    def test_lifetime_rounds_use_existing_history_and_survive_stop_day_change_restart(self):
        with TemporaryDirectory() as directory:
            store=Store(Path(directory)/'usage.sqlite3')
            try:
                focus=Focus(store)
                with store.db: store.db.executemany('INSERT INTO focus_completions VALUES (?,?)',[('2026-10-01',2),('2026-10-02',3)])
                focus=Focus(store); self.assertEqual(focus.completed_rounds,5)
                focus.start(0); focus.remaining=1; focus.advance(1,datetime(2026,11,2,23,59))
                self.assertEqual(focus.completed_rounds,6); focus.stop(); focus.configure_day_start(240)
                self.assertEqual(focus.completed_rounds,6); self.assertEqual(focus.round,0)
                focus=Focus(store); focus.start(5); focus.remaining=1; focus.advance(6,datetime(2026,11,3,12))
                self.assertEqual(focus.completed_rounds,7); self.assertEqual(Focus(store).completed_rounds,7)
            finally: store.close()


class FocusGroupInterfaceTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def test_group_picker_contains_saved_mixed_budgets_and_removal_is_independent(self):
        group=new_rule('Mixed group',[target('site','example.com'),target('app','editor.exe')],'mixed')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[group])
        page=self.app.focus_page; self.app.switch_page(4); page.rule_tabs.setCurrentIndex(2); page.add_group_button.click()
        dialog=self.app._dialogs[-1]; listing=dialog.findChild(QListWidget)
        choice=next(listing.item(i) for i in range(listing.count()) if listing.item(i).data(Qt.UserRole)=='budget:mixed')
        choice.setCheckState(Qt.Checked)
        next(button for button in dialog.findChildren(QPushButton) if button.text()==self.app.t('Add selected')).click()
        self.assertEqual(self.app.focus.settings.block_groups,['budget:mixed'])
        self.assertEqual(page.block_lists['group'].item(0).text(),'Mixed group')
        self.app.focus.start(0); self.app.browser_bridge=Mock(); self.app.update_focus_policy()
        policy=self.app.browser_bridge.update.call_args.args[0]; self.assertTrue(policy['active']); self.assertIn('example.com',policy['block'])
        self.assertTrue(self.app.restrictions.legacy_block(('',r'C:\Work\editor.exe','')))
        self.assertTrue(self.app.restrictions.legacy_block(('','','sub.example.com')))
        self.app.focus.pause(1); self.assertFalse(self.app.restrictions.legacy_block(('','','sub.example.com')))
        page.block_lists['group'].setCurrentRow(0); page.remove_rule_button.click()
        self.assertEqual(self.app.focus.settings.block_groups,[]); self.assertEqual(self.app.settings.wellbeing_rules,[group])

    def test_games_category_uses_new_catalog_entries_and_existing_minimization_consent(self):
        self.app.focus.configure(FocusSettings(block_groups=['games'])); self.app.focus.start(0)
        sample=Sample(datetime.now().astimezone(),1,str(self.exe),'fixture:game')
        with patch.object(self.app,'minimization_allowed',return_value=False) as consent,patch('gametime.qt_ui.win32.minimize_game') as minimize:
            self.app.focus_tick(sample); consent.assert_called_once(); minimize.assert_not_called()
        with patch.object(self.app,'minimization_allowed',return_value=True),patch('gametime.qt_ui.win32.minimize_game') as minimize:
            self.app.focus_tick(replace(sample,awake=2,wall=sample.wall+timedelta(seconds=1))); minimize.assert_called_once()
        self.app.focus.pause(2)
        with patch('gametime.qt_ui.win32.minimize_game') as minimize:
            self.app.focus_tick(replace(sample,awake=3,wall=sample.wall+timedelta(seconds=2))); minimize.assert_not_called()

    def test_all_sites_group_keeps_blocking_when_another_budget_adds_a_domain(self):
        group=new_rule('Sites',[target('site','example.com')],'sites'); group.update(seconds=0,enabled=True,enforce=True)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[group])
        self.app.focus.configure(FocusSettings(block_groups=['sites'])); self.app.focus.start(0)
        self.app.browser_bridge=Mock(); self.app.update_focus_policy(); policy=self.app.browser_bridge.update.call_args.args[0]
        self.assertTrue(policy['active']); self.assertEqual(policy['mode'],'allowlist'); self.assertEqual(policy['allow'],[])

    def test_sidebar_focus_header_lifetime_count_and_language_are_consistent(self):
        self.assertEqual(list(self.app.nav),[1,0,5,6,4,2])
        self.app.focus.completed_rounds=12
        for language in ('hu','en'):
            self.app.set_language(language); page=self.app.focus_page; page.refresh()
            self.assertEqual(page.rule_tabs.tabText(2),self.app.t('Groups'))
            self.assertIn('12',page.round_label.text())
            self.assertFalse(any(button.accessibleName()==self.app.t('Page settings') for button in page.findChildren(QPushButton)))
            with patch.object(self.store,'games',side_effect=AssertionError('No catalog reads while refreshing')):
                page.refresh(); page.refresh()
