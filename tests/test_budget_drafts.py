"""Drafts are durable and unapplied; only budgets participate."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
import json
import unittest
from unittest.mock import patch
import test_qt_ui as fixture
from gametime.qt_budget_drafts import KEY
from gametime.wellbeing import target


class BudgetDraftTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def restart(self):
        from gametime.qt_ui import App
        old=self.app; service=old.service; hub=old.hub; old.close(); self.pump(.03)
        self.app=App(self.store,self.base,background=True,service=service,hub=hub); self.app.tick_timer.stop(); self.pump(.03)

    def test_back_restart_and_save_keep_complete_budget_but_never_general_draft(self):
        app=self.app; applied=deepcopy(app.settings); editor=app.budget_editor
        app.games_path.setText(str(self.base/'unsaved-general'))
        app.open_budget(member=target('site','never.example')); key=editor.current
        editor.name.setText('Weekend'); editor.minutes.setValue(42); editor.access.select([5,6])
        editor.member_overlay_drafts[key]={'site:never.example':{'overlay_font_size':38,'overlay_enabled':True}}
        editor.steps.add('break'); card=editor.steps.cards[0]; card.minutes.setValue(15)
        card.targets['site'].break_mode.setCurrentIndex(card.targets['site'].break_mode.findData('redirect'))
        card.targets['site'].redirect_url.setText('https://other.example/')
        app.budget_back.click(); self.assertIn(key,editor.row_keys)
        self.assertEqual(self.store.settings(),applied)
        self.restart(); app=self.app; editor=app.budget_editor
        app.open_budget(); editor.show_editor(key)
        self.assertEqual(editor.name.text(),'Weekend'); self.assertEqual(editor.minutes.value(),42)
        self.assertEqual(editor.access.active_days[key],[5,6]); self.assertEqual(editor.steps.cards[0].minutes.value(),15)
        self.assertEqual(editor.steps.cards[0].redirect_url.text(),'https://other.example/')
        self.assertEqual(editor.member_overlay_drafts[key]['site:never.example']['overlay_font_size'],38)
        self.assertEqual(app.games_path.text(),applied.games_root)
        app.save_budgets(); self.assertFalse(app.budget_error.text())
        self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],2520)
        self.assertEqual(self.store.settings().activity_overlays['site:never.example']['overlay_font_size'],38)
        self.assertIsNone(self.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone())

    def test_invalid_and_empty_drafts_survive_failed_save_restart(self):
        editor=self.app.budget_editor; editor.create_new(); key=editor.current; editor.name.setText('')
        self.app.save_budgets(); self.assertTrue(self.app.budget_error.text())
        self.restart(); editor=self.app.budget_editor
        self.assertEqual(editor.current,key); self.assertEqual(editor.name.text(),''); self.assertEqual(editor.rule(key)['members'],[])
        self.assertFalse(self.store.settings().wellbeing_rules)

    def test_typed_step_minutes_before_focus_leaves_survive_restart(self):
        self.app.open_budget(member=target('site','typed.example')); editor=self.app.budget_editor
        editor.steps.add('notify'); card=editor.steps.cards[0]
        field=card.minutes.lineEdit(); field.setFocus(); field.setText('37'); field.setModified(True)
        with patch.object(field,'hasFocus',return_value=True): editor.drafts.flush()
        self.restart(); self.app.open_budget(); editor=self.app.budget_editor; editor.show_editor(editor.rules[0]['id'])
        self.assertEqual(editor.steps.cards[0].minutes.value(),37)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        self.assertEqual(next(iter(self.store.settings().restriction_plans.values()))['steps'][0]['offset'],2220)

    def test_explicit_discard_is_cancellable_and_does_not_change_saved_profile(self):
        from gametime.qt_translation import QDialog
        saved=self.store.settings(); self.app.open_budget(member=target('site','draft.example')); editor=self.app.budget_editor
        editor.drafts.flush()
        with patch.object(QDialog,'exec',return_value=QDialog.Rejected): editor.drafts.discard()
        self.assertEqual(len(editor.rules),1)
        with patch.object(QDialog,'exec',return_value=QDialog.Accepted): editor.drafts.discard()
        self.assertFalse(editor.rules); self.assertEqual(self.store.settings(),saved)
        self.assertIsNone(self.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone())

    def test_idle_flush_does_not_rewrite_database_and_general_save_keeps_draft(self):
        editor=self.app.budget_editor; self.app.open_budget(member=target('site','pending.example'))
        editor.minutes.setValue(17); editor.drafts.flush(); count=self.store.db.total_changes
        for _ in range(4): editor.drafts.flush()
        self.assertEqual(count,self.store.db.total_changes)
        self.app.save_settings(scope='general')
        self.assertIsNotNone(self.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone())
        self.assertFalse(self.store.settings().wellbeing_rules)

    def test_restriction_has_heading_without_redundant_checkbox_and_keeps_consent(self):
        self.app.open_budget(member=target('app',r'C:\Apps\editor.exe'))
        editor=self.app.budget_editor; editor.steps.add('restrict'); card=editor.steps.cards[0]; fields=card.targets['app']
        self.assertTrue(fields.enabled.isHidden()); self.assertFalse(fields.heading.isHidden())
        self.assertFalse(card.consent.isHidden()); self.assertFalse(fields.allowance.isHidden())
        editor.drafts.flush(); self.assertEqual(self.store.settings().restriction_plans,{})

    def test_all_website_members_are_visible_without_history_or_hover(self):
        members=[target('site',f'new-{i}.example') for i in range(9)]
        self.app.open_budget(members=members); editor=self.app.budget_editor
        self.assertEqual(editor.members_note.text(),', '.join(m['value'] for m in members))
        self.assertTrue(editor.members_note.wordWrap())
        editor.name.setText('Sleep mode'); self.app.save_budgets(); self.app.open_budget(); editor.show_editor(editor.rules[0]['id'])
        self.assertIn('new-8.example',editor.members_note.text())


class FixedBudgetDaysTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp; tearDown=fixture.QtInterfaceTests.tearDown; pump=fixture.QtInterfaceTests.pump

    def test_two_computer_periods_use_separate_days_values_and_global_renewal(self):
        from PySide6.QtCore import QTime
        editor=self.app.budget_editor; self.app.open_budget(); editor.create_computer(); editor.access.select([0,1,2,3,4])
        editor.schedule.change('bedtime_minute',22*60); editor.shared_reset.setTime(QTime(6,0))
        editor.create_computer(); key=editor.current; editor.access.select([5,6])
        editor.periods.name.setText('Weekend'); editor.periods.schedule.change('bedtime_minute',23*60)
        editor.periods.reset.setTime(QTime(7,0)); editor.collect(); self.app.save_budgets()
        self.assertFalse(self.app.budget_error.text()); saved=self.store.settings()
        self.assertEqual(saved.bedtime_minute,22*60); self.assertEqual(saved.computer_periods[0]['values']['bedtime_minute'],23*60)
        self.assertEqual(saved.budget_active_days['computer-window'],[0,1,2,3,4]); self.assertEqual(saved.budget_active_days[key],[5,6])
        self.assertNotIn(key,saved.budget_reset_overrides)
        editor.show_editor(key)
        self.assertTrue(editor.periods.schedule.day_details.isHidden()); self.assertTrue(editor.periods.schedule.bedtime_enabled.isHidden())
        self.assertIs(editor.access.widget.parent(),editor.periods.schedule)
        editor.show_editor('shared-games'); self.assertIs(editor.access.widget.parent(),editor.schedule)
        self.assertTrue(editor.schedule.day_details.isHidden())

    def test_overlap_warning_disappears_for_disjoint_days_and_unrelated_members(self):
        from gametime.budget_conflicts import overlaps
        editor=self.app.budget_editor
        for name,days in (('one',[0,1]),('two',[1,2])):
            editor.create_new(); editor.replace_members(editor.rule(editor.current),[target('site','youtube.com')]); editor.name.setText(name); editor.access.select(days)
        second=editor.current; editor.drafts.flush(); self.assertTrue(editor.conflicts.text()); self.assertTrue(overlaps(editor))
        editor.access.select([3,4]); editor.drafts.flush(); self.assertFalse(editor.conflicts.text()); self.assertFalse(overlaps(editor))
        editor.replace_members(editor.rule(second),[target('site','other.example')]); editor.access.select([0,1]); editor.drafts.flush()
        self.assertFalse(overlaps(editor))

    def test_presenting_old_weekdays_alone_does_not_block_preference_sync(self):
        source=replace(self.app.settings,weekend_enabled=True,weekend_schedule={'limit_seconds':10800,'warning_seconds':9000})
        self.store.save_settings(source); self.app.settings=self.app.catalog.settings=source
        editor=self.app.budget_editor; editor.saved(source); editor.drafts.flush()
        self.assertTrue(editor.periods.migrated); self.assertFalse(self.app.settings_have_draft())
        self.assertIsNone(self.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone())
        editor.show_editor('shared-games'); editor.schedule.limit.setValue(30)
        self.assertTrue(self.app.settings_have_draft())


if __name__=='__main__': unittest.main()
