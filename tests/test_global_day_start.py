"""All renewal controls share a clock; legacy consumed time survives migration."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QLabel
import test_qt_ui as fixture
from gametime.store import Store
from gametime.model import Settings
from gametime.budget_periods import BudgetPeriods
from gametime.restriction_policy import RestrictionState,Budget,new_plan,step
from gametime.global_day_start import migrate,normalize,carry_markers
from gametime.quota import budget_day


class GlobalMigrationTests(TestCase):
    def test_migration_carries_legacy_usage_and_save_grants_to_common_day(self):
        with TemporaryDirectory() as directory:
            store=Store(Path(directory)/'usage.sqlite3')
            try:
                wall=datetime(2026,11,2,4,tzinfo=timezone.utc)
                old=replace(Settings(),budget_reset_minute=0,budget_reset_overrides={'shared-games':360,'site':420,'computer-window':480})
                store.save_settings(old); ledger=BudgetPeriods(store)
                ledger.totals('quota:shared-games',360,wall,lambda:{'game':123},marker_key='shared-games')
                ledger.totals('site',420,wall,lambda:{'site':234},marker_key='site')
                state=RestrictionState(store); plan=new_plan(); plan['steps']=[step('cover')]; plan['extension_minutes']=5
                state.update('2026-11-01',1000,[Budget('computer-window','Computer',60,60,())],{'computer-window':plan})
                self.assertIsNotNone(state.extend(['computer-window'],'app:c:\\example.exe'))
                store.mark_alert('2026-11-01',('warning:6000',)); history=list(store.db.execute('SELECT * FROM usage'))
                updated=migrate(store,wall)
                self.assertEqual(set(updated.budget_reset_overrides.values()),{0})
                self.assertEqual(replace(updated,budget_reset_overrides=old.budget_reset_overrides),old)
                restored=BudgetPeriods(store)
                self.assertEqual(restored.totals('quota:shared-games',0,wall,lambda:{},marker_key='shared-games'),{'game':123})
                self.assertEqual(restored.totals('site',0,wall,lambda:{},marker_key='site'),{'site':234})
                self.assertIn('warning:6000',store.alert_keys('2026-11-02'))
                state=RestrictionState(store); state.update('2026-11-02',1001,[Budget('computer-window','Computer',60,60,())],{'computer-window':plan})
                self.assertTrue(state.rows['computer-window']['used_extension'])
                self.assertEqual(list(store.db.execute('SELECT * FROM usage')),history)
                self.assertEqual(restored.totals('site',0,wall+timedelta(days=1),lambda:{}),{})
                self.assertEqual(migrate(store,wall),updated)
            finally: store.close()


class GlobalSettingsTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def test_one_global_control_saves_cancel_and_updates_every_existing_clock(self):
        old=replace(self.app.settings,budget_reset_overrides={'shared-games':0,'site':0,'computer-window':0})
        self.store.save_settings(old); self.app.settings=self.app.catalog.settings=old
        self.app.nav[2].click(); self.app.show(); self.pump(.02)
        self.assertTrue(self.app.global_day_start.isVisible()); self.assertTrue(self.app.nav[2].isChecked())
        self.app.global_day_start.setTime(QTime(6,30)); self.app.cancel_general_settings()
        self.assertEqual(self.store.settings(),old)
        self.app.nav[2].click(); self.app.global_day_start.setTime(QTime(6,30))
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')): self.app.save_settings(scope='general')
        self.assertTrue(self.app.settings_error.text()); self.assertEqual(self.store.settings(),old)
        self.app.save_settings(scope='general'); self.assertFalse(self.app.settings_error.text())
        saved=self.store.settings(); self.assertEqual(saved.budget_reset_minute,390)
        self.assertEqual(set(saved.budget_reset_overrides.values()),{390})
        wall=datetime(2026,11,2,6,29)
        self.assertEqual({budget_day(saved,key,wall) for key in ('shared-games','site','computer-window','new')},{datetime(2026,11,1).date()})
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games'); self.pump(.02)
        self.assertTrue(editor.shared_reset_panel.isHidden()); self.assertTrue(editor.reset_time.isHidden()); self.assertTrue(editor.periods.reset.isHidden())
        self.assertFalse(any(label.isVisible() and label.text()==self.app.t('Renews daily at') for label in editor.findChildren(QLabel)))
        self.app.set_language('en'); self.app.nav[2].click()
        self.assertEqual(self.app.global_day_start.time(),QTime(6,30))
        self.assertEqual(self.app.global_day_start.accessibleName(),'Day starts at')
