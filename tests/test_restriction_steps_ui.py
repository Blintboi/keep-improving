"""Action editor integration with temp profiles; native effects are mocked."""
from dataclasses import replace
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QPushButton
import test_qt_ui as fixture
from gametime.qt_restriction_steps import edit_steps
from gametime.restriction_policy import new_plan, step
from gametime.tracker import Sample


class StepsInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_dialog_cancel_leaves_original_and_save_waits_for_budget_save(self):
        editor=self.app.budget_editor; self.app.open_budget(); editor.show_editor('shared-games')
        window=edit_steps(editor); self.pump()
        window.reject(); self.assertEqual(editor.restriction_plans,{})
        window=edit_steps(editor)
        from gametime.qt_translation import QCheckBox
        checks=window.findChildren(QCheckBox)
        next(c for c in checks if c.text()==self.app.t('Use these steps')).setChecked(True)
        next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Save')).click()
        self.assertIn('shared-games',editor.restriction_plans)
        self.assertEqual(self.store.settings().restriction_plans,{})
        self.app.save_settings('budgets')
        self.assertIn('shared-games',self.store.settings().restriction_plans)

    def test_custom_warning_only_replaces_legacy_game_minimization(self):
        plan=new_plan(); plan['steps']=[step('notify',popup=True)]
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True,
            restriction_seconds=1,restriction_plans={'shared-games':plan})
        now=datetime.now().astimezone()
        with patch.object(self.app.tracker,'quota_day_totals',return_value={self.games[0].id:10000}):
            self.assertFalse(self.app.restriction_reached(now,self.games[0]))

    def test_popup_only_step_does_not_play_sound(self):
        from gametime.tracker import Alert
        self.app.dismiss_popup()
        with patch.object(self.app,'notification_mode',return_value='normal'),patch('gametime.qt_ui.play_notification') as sound:
            self.assertTrue(self.app.popup(Alert(datetime.now().date().isoformat(),(),'wellbeing','Fixture','OK',sound=False)))
            sound.assert_not_called()

    def test_extension_deadline_close_is_cancelled_when_plan_removed(self):
        from concurrent.futures import Future
        import threading
        runtime=self.app.restrictions; cancelled=threading.Event(); future=Future()
        target=Sample(datetime.now().astimezone(),100,str(self.exe),'123:456')
        runtime.jobs[target.identity]=(future,cancelled,target,('shared-games',))
        with patch.object(runtime,'process_browser_requests'),patch.object(runtime.audio,'update'):
            runtime.tick(replace(target,interactive=False))
        self.assertTrue(cancelled.is_set()); future.set_result(False)

    def test_clock_change_moves_one_time_allowance(self):
        from gametime.qt_day_start import apply_day_start
        from gametime.quota import current_day
        from gametime.restriction_policy import Budget
        now=datetime.now().astimezone().replace(hour=0,minute=30)
        plan=new_plan(); plan.update(extension_minutes=2,close_confirmed=True,steps=[step('cover')])
        state=self.app.restrictions.state
        day=current_day(self.app.settings,now).isoformat()
        state.update(day,100,[Budget('shared-games','x',1,1,())],{'shared-games':plan})
        state.extend(['shared-games'],'app:fixture.exe')
        previous=self.app.settings; self.app.settings=self.app.catalog.settings=replace(previous,budget_reset_minute=60)
        apply_day_start(self.app,previous,now)
        newday=current_day(self.app.settings,now).isoformat()
        state.update(newday,101,[Budget('shared-games','x',1,1,())],{'shared-games':plan})
        self.assertTrue(state.rows['shared-games']['used_extension'])
