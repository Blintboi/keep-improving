"""Central budgets, statistics handoff and foreground-safe runtime integration."""
from dataclasses import replace
from datetime import datetime,timedelta
import math
import unittest
from unittest.mock import patch,Mock
from PySide6.QtCore import QItemSelectionModel
import test_qt_ui as fixture
from gametime.tracker import Sample
from gametime.wellbeing import target
from gametime.qt_budgets import new_rule


class WellbeingInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def configure(self,members,seconds=1,enforce=False):
        rule=new_rule('Fixture budget',members); rule.update(enabled=True,seconds=seconds,enforce=enforce)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule])
        return rule

    def exhaust(self,path=r'C:\Apps\editor.exe',website=''):
        start=datetime.now().astimezone(); sample=Sample(start,100,path,'fixture:1')
        self.app.wellbeing.tick(sample,website)
        sample=replace(sample,wall=start+timedelta(seconds=1),awake=101)
        self.app.wellbeing.tick(sample,website); return sample

    def test_independent_category_and_mixed_group_drafts_save_in_one_place(self):
        editor=self.app.budget_editor; self.app.open_budget(member=target('category','apps'))
        editor.enabled.setChecked(True); editor.minutes.setValue(90)
        self.app.open_budget(member=target('category','sites')); editor.enabled.setChecked(True); editor.minutes.setValue(40)
        members=[target('game',self.games[0].id),target('app',r'C:\Apps\editor.exe'),target('site','youtube.com')]
        self.app.open_budget(members=members); editor.name.setText('Szabadidő'); editor.minutes.setValue(25)
        editor.enforce.setChecked(True)
        self.app.set_language('en'); self.app.save_settings()
        self.assertFalse(self.app.settings_error.text())
        saved=self.store.settings(); self.assertEqual([r['seconds'] for r in saved.wellbeing_rules],[5400,2400,1500])
        self.assertEqual(saved.wellbeing_rules[-1]['members'],members)
        self.assertEqual(saved.wellbeing_rules[-1]['name'],'Szabadidő'); self.assertTrue(saved.wellbeing_rules[-1]['enforce'])
        editor.remove_current(); self.app.save_settings(); self.assertEqual(len(self.store.settings().wellbeing_rules),2)

    def test_statistics_opens_exact_local_member_and_groups_selected_rows(self):
        now=datetime.now().astimezone(); day=now.date().isoformat()
        self.store.add_usage({(day,self.games[0].id):60})
        self.app.focus._credit('app',r'c:\apps\editor.exe','editor.exe',now,now+timedelta(seconds=30),30)
        self.app.switch_page(1); page=self.app.statistics
        page.games_table.selectRow(0); page.budget_button.click()
        self.assertEqual(self.app.pages.currentIndex(),5); self.assertEqual(self.app.budget_editor.current,'game:'+self.games[0].id)
        self.app.switch_page(1); selection=page.games_table.selectionModel()
        for row in range(2): selection.select(page.games_table.model().index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
        self.assertFalse(page.budget_button.isEnabled()); self.assertTrue(page.group_budget_button.isEnabled())
        page.group_budget_button.click(); editor=self.app.budget_editor
        self.assertEqual(editor.rule(editor.current)['members'],[target('game',self.games[0].id),target('app','editor.exe')])

    def test_disabling_shared_games_keeps_own_cap_and_does_not_crash_render_or_custom_reminder(self):
        from gametime.budget import remaining_budget,gameplay_budget
        self.app.budget_editor.shared.setChecked(False); self.app.game_limits_dialog(self.games[0].id)
        self.app.budget_editor.enabled.setChecked(True); self.app.budget_editor.minutes.setValue(30); self.app.save_settings()
        self.assertFalse(self.app.settings_error.text()); now=datetime.now().astimezone()
        self.assertTrue(math.isinf(remaining_budget(self.app.settings,now,8000).remaining))
        self.assertEqual(gameplay_budget(self.app.settings,now,{self.games[0].id:1800},self.games[0].id).remaining,0)
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,notification_messages={'bedtime':'{remaining}'})
        self.assertEqual(self.app.bedtime_message(now.date(),now),self.app.t('No shared limit'))
        self.app.update_tray(); self.app.render()

    def test_only_opted_in_rule_minimizes_after_continuous_ten_seconds(self):
        self.configure([target('category','apps')],enforce=True); sample=self.exhaust()
        with patch.object(self.app,'popup',return_value=True),patch('gametime.qt_wellbeing_runtime.win32.minimize_game',return_value=True) as minimize:
            for second in range(10):
                self.app.wellbeing_tick(replace(sample,wall=sample.wall+timedelta(seconds=second),awake=sample.awake+second))
            minimize.assert_not_called()
            self.app.wellbeing_tick(replace(sample,wall=sample.wall+timedelta(seconds=10),awake=sample.awake+10))
            minimize.assert_called_once_with(sample.path,sample.identity,consented=True)
            self.app.wellbeing_tick(replace(sample,interactive=False)); self.assertIsNone(self.app._wellbeing_grace)

    def test_notifications_are_durable_and_site_rules_do_not_minimize_browser(self):
        self.configure([target('site','example.com')],enforce=True); sample=self.exhaust(r'C:\Apps\brave.exe','example.com')
        self.app.browser_bridge=Mock(); self.app.browser_bridge.website.return_value='example.com'
        with patch.object(self.app,'popup',return_value=True) as popup,patch('gametime.qt_wellbeing_runtime.win32.minimize_game') as minimize:
            for second in range(12): self.app.wellbeing_tick(replace(sample,wall=sample.wall+timedelta(seconds=second),awake=sample.awake+second))
            popup.assert_called_once(); minimize.assert_not_called()
            del self.app._wellbeing_alert_day
            self.app.wellbeing_tick(sample); popup.assert_called_once()
        self.assertTrue(self.app.wellbeing.policy(self.app.focus.policy(),sample.wall)['active'])

    def test_application_countdown_uses_own_budget_without_rtss_or_foreground_transfer(self):
        self.configure([target('category','apps')],seconds=60); sample=self.exhaust()
        with patch('gametime.qt_ui.win32.sample',return_value=sample),patch.object(self.app.rtss,'present') as rtss:
            self.app.update_overlay(); self.assertEqual(self.app.overlay.seconds,59); self.assertEqual(self.app._overlay_backend,'desktop')
            rtss.assert_not_called()
        with patch('gametime.qt_ui.win32.sample',return_value=replace(sample,identity='different')):
            self.app.update_overlay(); self.assertFalse(self.app.overlay.isVisible())

    def test_protected_game_and_clock_jump_keep_minimization_guard(self):
        self.configure([target('game',self.games[0].id)],enforce=True); sample=self.exhaust(str(self.exe))
        with patch.object(self.app,'popup',return_value=True),patch.object(self.app,'minimization_allowed',return_value=False),patch('gametime.qt_wellbeing_runtime.win32.minimize_game') as minimize:
            self.assertFalse(self.app.wellbeing_tick(sample)); minimize.assert_not_called()
        with patch.object(self.app,'popup',return_value=True),patch('gametime.qt_wellbeing_runtime.win32.minimize_game') as minimize:
            self.app.wellbeing_tick(sample)
            self.app.wellbeing_tick(replace(sample,wall=sample.wall+timedelta(seconds=100),awake=sample.awake+10))
            minimize.assert_not_called()
        self.assertTrue(self.app.launch_restricted(self.games[0])); self.assertFalse(self.app.launch_restricted(self.games[1]))

    def test_game_alias_remaps_pending_time_saved_rules_and_unsaved_editor(self):
        member=target('game',self.games[0].id); self.configure([member]); self.store.save_settings(self.app.settings)
        self.app.budget_editor.saved(self.app.settings); self.app.open_budget(member=member)
        self.app.budget_editor.enabled.setChecked(True); self.app.budget_editor.minutes.setValue(25)
        sample=self.exhaust(str(self.exe)); renamed=replace(self.games[0],id='steam:renamed',source='Steam')
        self.app.tracker.reconcile([renamed],lambda g:g.source=='Games')
        expected=[target('game',renamed.id)]
        self.assertEqual(self.app.settings.wellbeing_rules[0]['members'],expected)
        self.assertEqual(self.app.wellbeing.states(sample.wall)[0].used,1)
        self.app.save_settings(); saved=self.store.settings()
        self.assertEqual(saved.game_limits,{}); self.assertEqual(saved.wellbeing_rules[0]['members'],expected)
        self.assertEqual(saved.wellbeing_rules[0]['seconds'],1500)


if __name__=='__main__': unittest.main()
