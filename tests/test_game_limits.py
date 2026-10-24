"""Per-game caps share accounting, never add time, and keep Hub/overlay distinct."""
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from gametime.model import Settings, Catalog, Game
from gametime.store import Store
from gametime.tracker import Tracker, Sample
from gametime.budget import gameplay_budget, remaining_budget, game_remaining


class GameLimitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=Store(Path(self.tmp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.game=Game('fixture','Fixture','Games',self.tmp.name)
        self.settings=replace(Settings(),game_limits={'fixture':1800})
        self.catalog=Catalog(self.settings,[self.game]); self.tracker=Tracker(self.store,self.catalog)
        self.now=datetime(2026,10,24,12)

    def test_strict_validation_and_compatible_default(self):
        self.assertEqual(Settings().game_limits,{})
        for value in ([],None,{'':60},{'x':True},{'x':0},{'x':-1},{'x':86401},{'x':float('nan')},{'x':float('inf')},{'x':'30'},{'x':{}}):
            with self.subTest(value=value),self.assertRaises(ValueError): replace(Settings(),game_limits=value).validate()
        replace(Settings(),game_limits={'x':.6,'y':86400}).validate()

    def test_overlay_uses_smaller_and_hub_keeps_shared_budget(self):
        totals={'fixture':600,'other':1800}
        self.assertEqual(remaining_budget(self.settings,self.now,sum(totals.values())).remaining,4800)
        self.assertEqual(gameplay_budget(self.settings,self.now,totals,'fixture').remaining,1200)
        self.assertEqual(gameplay_budget(self.settings,self.now,{'fixture':600,'other':6000},'fixture').remaining,600)
        self.assertEqual(gameplay_budget(self.settings,self.now,totals,'other').remaining,4800)
        self.assertEqual(gameplay_budget(self.settings,self.now,totals,'fixture',.75).remaining,1199.25)

    def test_exhausted_shared_budget_cannot_be_extended_by_game_cap(self):
        self.assertEqual(gameplay_budget(self.settings,self.now,{'other':7200},'fixture').remaining,0)
        self.assertEqual(gameplay_budget(self.settings,self.now,{'fixture':1800},'fixture').remaining,0)
        self.assertIsNone(game_remaining(self.settings,'other',0))

    def test_bedtime_still_caps_overlay_and_game_warning_color(self):
        settings=replace(self.settings,bedtime_enabled=True,bedtime_caps_budget=True)
        self.assertEqual(gameplay_budget(settings,self.now.replace(hour=23,minute=59),{},'fixture').remaining,60)
        self.assertTrue(gameplay_budget(self.settings,self.now,{'fixture':1500},'fixture').warning)
        self.assertFalse(gameplay_budget(self.settings,self.now,{'fixture':600},'fixture').warning)

    def test_both_caps_consume_the_same_foreground_seconds_and_survive_restart(self):
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=2),2); self.tracker.close()
        tracker=Tracker(self.store,self.catalog); totals=tracker.quota_totals(self.now)
        self.assertEqual(totals,{'fixture':2})
        self.assertEqual(gameplay_budget(self.settings,self.now,totals,'fixture').remaining,1798)
        self.assertEqual(remaining_budget(self.settings,self.now,2).remaining,7198)

    def test_new_cap_counts_preexisting_usage_without_touching_history(self):
        self.store.add_usage({('2026-10-24','fixture'):2000})
        self.assertEqual(gameplay_budget(self.settings,self.now,self.tracker.quota_totals(self.now),'fixture').remaining,0)
        self.store.save_settings(self.settings)
        self.assertEqual(self.store.settings().game_limits,{'fixture':1800})
        self.assertEqual(self.store.totals('2026-10-24'),{'fixture':2000})

    def test_custom_reset_midnight_and_next_period_apply_to_game_cap(self):
        self.catalog.settings=replace(self.settings,budget_reset_minute=360)
        start=self.now.replace(hour=23,minute=59,second=59)
        self.tracker._credit(self.game,start,start+timedelta(seconds=2),2)
        self.assertEqual(self.tracker.quota_totals(start+timedelta(seconds=2)),{'fixture':2})
        self.assertEqual(self.tracker.quota_totals(start+timedelta(hours=6,seconds=2)),{})

    def test_alert_is_scoped_durable_and_removed_when_switching_or_limit_removed(self):
        self.tracker.cache['2026-10-24']={'fixture':1800}
        self.tracker.active=self.game; self.tracker.identity='fixture:creation'
        self.tracker.evaluate(self.now); alert=self.tracker.alerts[0]
        self.assertEqual(alert.game_id,self.game.id); self.assertIn('30',alert.text)
        self.tracker.delivered(self.tracker.alerts.popleft()); self.tracker.evaluate(self.now)
        self.assertFalse(self.tracker.alerts)
        self.tracker.identity='new:creation'; self.tracker.evaluate(self.now); self.assertEqual(len(self.tracker.alerts),1)
        self.tracker.active=None; self.tracker.evaluate(self.now); self.assertFalse(self.tracker.alerts)
        self.tracker.active=self.game; self.tracker.evaluate(self.now); self.assertEqual(len(self.tracker.alerts),1)
        self.catalog.settings=replace(self.settings,game_limits={}); self.tracker.evaluate(self.now); self.assertFalse(self.tracker.alerts)

    def test_excluded_game_does_not_emit_cap_alert(self):
        self.tracker.cache['2026-10-24']={'fixture':1800}
        self.tracker.active=self.game; self.catalog.overrides[self.game.id]=False
        self.tracker.evaluate(self.now); self.assertFalse(self.tracker.alerts)

    def test_discovery_merge_preserves_stricter_cap_and_usage(self):
        self.store.save_settings(replace(self.settings,game_limits={'fixture':1800,'renamed':900}))
        self.store.add_usage({('2026-10-24','fixture'):300})
        with self.store.db: self.store._merge('fixture','renamed')
        self.assertEqual(self.store.settings().game_limits,{'renamed':900})
        self.assertEqual(self.store.totals('2026-10-24'),{'renamed':300})

    def test_tracker_reconciliation_migrates_local_cap_and_foreground_usage(self):
        self.store.save_settings(self.settings); self.store.upsert([self.game])
        self.tracker._credit(self.game,self.now,self.now+timedelta(seconds=2),2)
        renamed=replace(self.game,id='steam:fixture',source='Steam')
        self.tracker.reconcile([renamed],lambda game: game.source=='Games')
        self.assertEqual(self.catalog.settings.game_limits,{'steam:fixture':1800})
        self.assertEqual(self.store.settings().game_limits,self.catalog.settings.game_limits)
        self.assertEqual(self.tracker.quota_totals(self.now),{'steam:fixture':2})

    def test_statistics_snapshot_keeps_caps_local(self):
        from gametime.statistics_sync import StatisticsData
        self.store.save_settings(self.settings); self.store.upsert([self.game])
        self.store.add_usage({('2026-10-24','fixture'):300})
        snapshot=StatisticsData(self.store).snapshot('b'*32,'Fixture')
        self.assertNotIn('game_limits',str(snapshot)); self.assertEqual(snapshot['rows'][0][-1],300)


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class GameLimitInterfaceTests(unittest.TestCase):
    if os.name=='nt':
        import test_qt_ui as fixtures
        setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
        setUp=fixtures.QtInterfaceTests.setUp; tearDown=fixtures.QtInterfaceTests.tearDown; pump=fixtures.QtInterfaceTests.pump

    def configure(self):
        self.game=self.games[0]; self.now=datetime.now().astimezone()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_limits={self.game.id:1800})
        self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:600,self.games[1].id:1800}

    def test_hub_large_counter_shared_card_own_and_both_overlay_renderers_smaller(self):
        self.configure(); self.app.render()
        self.assertEqual(self.app.remaining_label.text(),'01:20:00')
        self.assertEqual(self.app.cards[self.game.id].game_remaining,1200)
        self.assertIsNone(self.app.cards[self.games[1].id].game_remaining)
        self.assertIn('00:20:00',self.app.cards[self.game.id].toolTip())
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True)
        self.app.tracker.active=self.game; self.app.tracker.identity='fixture:1'
        sample=Sample(self.now,100,str(self.exe),'fixture:1')
        with patch('gametime.qt_ui.win32.sample',return_value=sample),patch('gametime.qt_ui.foreground_screen_name',return_value=''):
            self.app.update_overlay(); self.assertEqual(self.app.overlay.seconds,1200)
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=True)
            with patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True) as present:
                self.app.update_overlay(); self.app._overlay_desktop_until=0; self.app.update_overlay()
                self.assertIn('20:00',present.call_args[0][2])

    def test_only_capped_game_blocks_and_existing_grace_rechecks_before_minimizing(self):
        self.configure(); self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:1800}
        self.assertTrue(self.app.launch_restricted(self.game)); self.assertFalse(self.app.launch_restricted(self.games[1]))
        self.app.tracker.active=self.game; self.app.tracker.identity='fixture:1'
        current=Sample(self.now,100,str(self.exe),'fixture:1')
        with patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_game') as minimize,patch('gametime.controller.win32.sample',return_value=current):
            self.assertTrue(self.app.enforce_gameplay(current)); escape.assert_not_called()
            for offset in range(1,11): self.app.enforce_gameplay(replace(current,wall=self.now+timedelta(seconds=offset),awake=100+offset))
            escape.assert_called_once(); minimize.assert_not_called()
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_limits={})
            self.pump(.3); minimize.assert_not_called()

    def test_dialog_save_cancel_failed_save_language_and_main_drafts(self):
        from PySide6.QtWidgets import QCheckBox, QPushButton
        from gametime.qt_widgets import NoWheelDoubleSpinBox
        self.app.limit.setValue(150)
        self.app.game_limits_dialog(self.games[0].id); window=self.app._dialogs[-1]
        enabled=window.findChild(QCheckBox,'game_limit_enabled'); minutes=window.findChild(NoWheelDoubleSpinBox,'game_limit_minutes')
        enabled.setChecked(True); minutes.setValue(30); self.app.set_language('en')
        self.assertEqual(minutes.value(),30); self.assertEqual(enabled.text(),'Limit this game')
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')):
            window.findChild(QPushButton,'save_game_limits').click()
        self.assertEqual(self.store.settings().game_limits,{}); self.assertTrue(window.isVisible())
        window.findChild(QPushButton,'save_game_limits').click(); self.pump(.03)
        self.assertEqual(self.store.settings().game_limits,{self.games[0].id:1800})
        self.assertEqual(self.app.limit.value(),150)
        self.app.save_settings(); self.assertEqual(self.store.settings().game_limits,{self.games[0].id:1800})
        self.app.game_limits_dialog(self.games[0].id); window=self.app._dialogs[-1]
        window.findChild(QCheckBox,'game_limit_enabled').setChecked(False); window.reject(); self.pump(.03)
        self.assertEqual(self.store.settings().game_limits,{self.games[0].id:1800})

    def test_excluded_game_keeps_saved_cap_but_can_launch(self):
        self.configure(); self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:1800}
        self.app.catalog.overrides[self.game.id]=False
        self.app.render(); self.assertFalse(self.app.launch_restricted(self.game))
        self.assertIsNone(self.app.cards[self.game.id].game_remaining)

    def test_protected_game_keeps_existing_minimization_permission_gate(self):
        self.configure(); self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:1800}
        self.app.tracker.active=self.game; self.app.tracker.identity='fixture:1'
        current=Sample(self.now,100,str(self.exe),'fixture:1')
        with patch.object(self.app,'minimization_allowed',return_value=False),patch('gametime.controller.win32.escape_game') as escape,patch('gametime.controller.win32.minimize_game') as minimize:
            self.assertFalse(self.app.enforce_gameplay(current)); self.assertTrue(self.app._restriction_reminder_only)
            self.app.tracker.evaluate(self.now)
            self.assertFalse(self.app.consume_silent_alert(self.app.tracker.alerts[0]))
            escape.assert_not_called(); minimize.assert_not_called()

    def test_game_switch_and_focus_change_cancel_delayed_cap_action(self):
        self.configure(); self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:1800}
        self.app.tracker.active=self.game; self.app.tracker.identity='fixture:1'
        current=Sample(self.now,100,str(self.exe),'fixture:1')
        with patch('gametime.controller.win32.escape_game'),patch('gametime.controller.win32.minimize_game') as minimize,patch('gametime.controller.win32.sample',return_value=replace(current,path='C:/Windows/notepad.exe',identity='other')):
            self.app.enforce_gameplay(current)
            for offset in range(1,11): self.app.enforce_gameplay(replace(current,wall=self.now+timedelta(seconds=offset),awake=100+offset))
            self.pump(.3); minimize.assert_not_called()

    def test_game_cap_alone_minimizes_after_full_foreground_grace(self):
        self.configure(); self.app.tracker.cache[self.now.date().isoformat()]={self.game.id:1800}
        self.assertFalse(self.app.settings.restriction_enabled)
        self.app.tracker.active=self.game; self.app.tracker.identity='fixture:1'
        current=Sample(self.now,100,str(self.exe),'fixture:1')
        with patch('gametime.controller.win32.escape_game'),patch('gametime.controller.win32.minimize_game',return_value=True) as minimize,patch('gametime.controller.win32.sample',return_value=current),patch.object(self.app,'restriction_notice') as notice:
            self.app.enforce_gameplay(current)
            for offset in range(1,10): self.app.enforce_gameplay(replace(current,wall=self.now+timedelta(seconds=offset),awake=100+offset))
            self.pump(.22); minimize.assert_not_called()
            self.app.enforce_gameplay(replace(current,wall=self.now+timedelta(seconds=10),awake=110))
            self.pump(.3); minimize.assert_called_once_with(str(self.exe),'fixture:1'); notice.assert_called_once()

    def test_multiple_game_drafts_save_and_inventory_refresh_preserve_unedited_caps(self):
        from PySide6.QtWidgets import QCheckBox,QPushButton
        from gametime.qt_widgets import NoWheelDoubleSpinBox,NoWheelComboBox
        self.configure(); self.app.game_limits_dialog(self.game.id); window=self.app._dialogs[-1]
        selector=window.findChild(NoWheelComboBox,'limit_game'); minutes=window.findChild(NoWheelDoubleSpinBox,'game_limit_minutes')
        minutes.setValue(15); selector.setCurrentIndex(selector.findData(self.games[1].id))
        window.findChild(QCheckBox,'game_limit_enabled').setChecked(True); minutes.setValue(45)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_limits={self.game.id:1800,self.games[2].id:3600})
        self.app.refresh_game_dialogs(); window.findChild(QPushButton,'save_game_limits').click(); self.pump(.03)
        self.assertEqual(self.store.settings().game_limits,{self.game.id:900,self.games[1].id:2700,self.games[2].id:3600})

    def test_empty_inventory_disables_editor_without_losing_saved_limits(self):
        from PySide6.QtWidgets import QPushButton
        self.configure(); self.app.catalog.games={}
        self.app.game_limits_dialog(); window=self.app._dialogs[-1]
        self.assertFalse(window.findChild(QPushButton,'save_game_limits').isEnabled())
        self.assertEqual(self.app.settings.game_limits,{self.game.id:1800})


if __name__=='__main__': unittest.main()
