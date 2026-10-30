"""New users opt in to budgets; appearance editing never invents one."""
from dataclasses import replace
from pathlib import Path
import json
import math
import tempfile
import unittest
from PySide6.QtWidgets import QWidget,QPushButton
import test_qt_ui as fixture
from gametime.store import Store
from gametime.wellbeing import target
from gametime.qt_countdown_targets import CountdownTargets


class BudgetDefaultsTests(unittest.TestCase):
    def test_new_profile_has_no_limit_and_legacy_profiles_keep_their_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'usage.sqlite3')
            try:
                fresh=store.settings()
                self.assertFalse(fresh.game_budget_enabled); self.assertFalse(fresh.budget_setup_completed)
                from gametime.budget import remaining_budget
                from datetime import datetime
                self.assertTrue(math.isinf(remaining_budget(fresh,datetime.now(),0).remaining))
                with store.db: store.db.execute("INSERT INTO settings VALUES ('config',?)",(json.dumps({'limit_seconds':9000,'game_limits':{'game':600}}),))
                old=store.settings(); self.assertTrue(old.game_budget_enabled); self.assertTrue(old.budget_setup_completed)
                self.assertEqual(old.limit_seconds,9000); self.assertEqual(old.game_limits,{'game':600})
                store.save_settings(replace(old,game_budget_enabled=False))
                self.assertFalse(store.settings().game_budget_enabled)
            finally: store.close()


class BudgetFirstInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def no_budgets(self):
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_budget_enabled=False)
        self.store.save_settings(self.app.settings); self.app.budget_editor.saved(self.app.settings)

    def field(self,window,key):
        return next(w for w in window.findChildren(QWidget) if w.accessibleName()==self.app.t(key))

    def test_empty_editor_lists_only_created_budgets_and_has_no_separate_countdown_tab(self):
        self.no_budgets(); self.app.open_budget(); editor=self.app.budget_editor
        self.assertEqual(editor.selector.count(),0); self.assertEqual(editor.stack.currentIndex(),2)
        self.assertNotIn('countdown',self.app.settings_shortcuts)
        self.app.open_budget(member=target('app',r'C:\Apps\editor.exe'))
        self.assertEqual(editor.selector.count(),1); self.assertFalse(editor.appearance.isVisible())
        editor.overlay.setChecked(False); self.assertFalse(editor.appearance.isVisible())
        self.app.open_budget(member=target('category','sites'))
        self.assertEqual(editor.selector.count(),2)

    def test_recorded_activities_do_not_generate_budgets_or_appearance_targets(self):
        self.no_budgets()
        with self.store.db:
            self.store.db.execute("INSERT INTO activity_items(kind,key,name) VALUES ('site','example.com','example.com')")
        targets=CountdownTargets(self.app)
        self.assertEqual(targets.rows(),[])
        self.app.game_countdown_dialog(); self.app._dialogs[-1].reject()
        self.assertEqual(self.store.settings().wellbeing_rules,[])
        self.assertFalse(self.store.settings().game_budget_enabled)

    def test_removed_or_disabled_budgets_do_not_reappear_as_countdown_targets(self):
        self.no_budgets(); editor=self.app.budget_editor
        self.app.open_budget(member=target('site','example.com')); identity=editor.current
        self.app.save_budgets(); editor.show_editor(identity)
        targets=CountdownTargets(self.app); self.assertEqual(len(targets.rows()),1)
        editor.enabled.setChecked(False); self.app.save_budgets(); targets.refresh(); self.assertEqual(targets.rows(),[])
        editor.show_editor(identity); editor.remove_current(); self.app.save_budgets(); targets.refresh(); self.assertEqual(targets.rows(),[])
        self.assertEqual(targets.edited,set())

    def test_game_is_added_explicitly_and_group_members_share_one_budget(self):
        self.no_budgets(); editor=self.app.budget_editor
        self.app.open_budget(member=target('game',self.games[0].id)); editor.minutes.setValue(15)
        self.app.save_settings(); self.assertEqual(self.store.settings().game_limits,{self.games[0].id:900})
        self.assertFalse(self.store.settings().game_budget_enabled)
        members=[target('game',self.games[1].id),target('app',r'C:\Apps\editor.exe'),target('site','example.com')]
        self.app.open_budget(members=members); editor.name.setText('Leisure'); editor.minutes.setValue(45)
        self.app.save_settings(); rules=self.store.settings().wellbeing_rules
        self.assertEqual(len(rules),1); self.assertEqual(rules[0]['members'],members); self.assertEqual(rules[0]['seconds'],2700)

    def setup_choice(self,with_games):
        self.no_budgets(); self.app.settings=self.app.catalog.settings=replace(self.app.settings,budget_setup_completed=False)
        self.app.show(); self.pump(.16)
        window=next(w for w in self.app._dialogs if getattr(w,'_personalization_kind','')=='budget-setup')
        checkbox=self.field(window,'Create a shared budget for all games'); self.assertFalse(checkbox.isChecked())
        checkbox.setChecked(with_games); self.field(window,'Daily limit (minutes)').setValue(45)
        next(w for w in window.findChildren(QPushButton) if w.text()==self.app.t('Get started')).click(); self.pump(.03)
        self.assertTrue(self.store.settings().budget_setup_completed)
        self.assertEqual(self.store.settings().game_budget_enabled,with_games)
        self.assertEqual(self.app.budget_editor.selector.count(),int(with_games))
        self.app.show(); self.pump(.12)
        self.assertFalse(any(getattr(w,'_personalization_kind','')=='budget-setup' for w in self.app._dialogs))

    def test_first_use_can_skip_the_games_group(self): self.setup_choice(False)

    def test_first_use_can_create_a_games_group_with_chosen_time_and_countdown(self):
        self.setup_choice(True)
        self.assertEqual(self.store.settings().limit_seconds,2700)
        self.assertTrue(self.store.settings().overlay_enabled)
        self.assertEqual(self.app.limit.value(),45)


if __name__=='__main__': unittest.main()
