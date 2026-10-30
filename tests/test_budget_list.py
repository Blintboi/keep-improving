"""A separate budgets page lists all budgets and uses one creation form."""
from dataclasses import replace
from unittest.mock import patch
import unittest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QPushButton,QLabel
import test_qt_ui as fixture
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target


class BudgetListTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_navigation_has_one_budget_page_and_one_add_action(self):
        self.app.show(); self.app.nav[5].click(); self.pump(.03)
        editor=self.app.budget_editor
        self.assertEqual(self.app.pages.currentWidget(),self.app.budget_page)
        self.assertNotIn('schedule',self.app.settings_sections); self.assertFalse(editor.selector.isVisible())
        self.assertEqual(editor.views.currentIndex(),0); self.assertEqual(editor.row_keys,['shared-games'])
        buttons=[button.text() for button in editor.findChildren(QPushButton) if button.isVisible()]
        self.assertEqual(buttons.count(self.app.t('Add new')),1)
        self.assertIn(self.app.t('Edit'),buttons); self.assertNotIn(self.app.t('Individual budget…'),buttons)
        self.assertFalse(self.app.limit.isVisible())
        next(b for b in editor.findChildren(QPushButton) if b.isVisible() and b.text()==self.app.t('Edit')).click()
        self.assertTrue(self.app.limit.isVisible())

    def test_list_shows_all_types_and_saves_edits_to_multiple_budgets_together(self):
        editor=self.app.budget_editor
        self.app.open_budget(member=target('app',r'C:\Apps\editor.exe')); editor.minutes.setValue(20)
        app_id=editor.current
        self.app.open_budget(member=target('site','example.com')); editor.minutes.setValue(30)
        site_id=editor.current
        self.app.open_budget(member=target('game',self.games[0].id)); editor.minutes.setValue(40)
        editor.show_list()
        self.assertEqual(set(editor.row_keys),{'shared-games',app_id,site_id,'game:'+self.games[0].id})
        rows={row[0]:row for row in editor.list_rows()}
        self.assertIn('20',rows[app_id][3]); self.assertIn('30',rows[site_id][3])
        self.assertEqual(self.store.settings().wellbeing_rules,[])
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        self.assertEqual([r['seconds'] for r in self.store.settings().wellbeing_rules],[1200,1800])
        self.assertEqual(self.store.settings().game_limits[self.games[0].id],2400)
        self.assertEqual(editor.views.currentIndex(),0)

    def test_one_new_form_accepts_single_or_mixed_members_and_requires_selection(self):
        self.app.open_budget(); editor=self.app.budget_editor; before=self.store.settings()
        editor.add_button.click(); identity=editor.current
        self.assertTrue(editor.name.isVisible()); self.assertTrue(editor.minutes.isVisible()); self.assertTrue(editor.members_button.isVisible())
        self.assertFalse(editor.appearance.isVisible())
        self.app.save_budgets(); self.assertTrue(self.app.budget_error.text()); self.assertEqual(self.store.settings(),before)
        editor.replace_members(editor.rule(identity),[target('site','example.com')]); editor.minutes.setValue(15)
        self.app.save_budgets(); self.assertFalse(self.app.budget_error.text())
        editor.show_editor(identity); editor.name.setText('Leisure'); editor.collect()
        members=[target('site','example.com'),target('app',r'C:\Apps\editor.exe'),target('game',self.games[0].id)]
        editor.replace_members(editor.rule(identity),members); self.app.save_budgets()
        rules=self.store.settings().wellbeing_rules; self.assertEqual(len(rules),1); self.assertEqual(rules[0]['members'],members)
        self.assertEqual(rules[0]['name'],'Leisure'); self.assertEqual(rules[0]['seconds'],900)

    def test_abandoned_empty_form_and_deletion_do_not_restore_a_budget(self):
        editor=self.app.budget_editor; editor.create_new(); editor.show_list()
        self.assertEqual(editor.row_keys,['shared-games']); self.assertEqual(editor.rules,[])
        editor.show_editor('shared-games'); editor.remove_current(); self.app.save_budgets()
        self.assertEqual(editor.row_keys,[]); self.assertFalse(self.store.settings().game_budget_enabled)

    def test_disabled_and_long_named_rules_remain_readable_and_editable(self):
        name='A long budget name '+('abcde '*10)
        rule=new_rule(name,[target('site','example.com')],'long')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule])
        editor=self.app.budget_editor; editor.saved(self.app.settings)
        self.app.resize(1020,740); self.app.open_budget(); self.pump(.04)
        self.assertEqual(set(editor.row_keys),{'shared-games','long'})
        self.assertEqual(self.app.budget_scroll.horizontalScrollBar().maximum(),0)
        editor.show_editor('long'); self.assertFalse(editor.enabled.isChecked()); editor.enabled.setChecked(True)
        self.app.save_budgets(); self.assertTrue(self.store.settings().wellbeing_rules[0]['enabled'])

    def test_hidden_refresh_is_cached_and_language_switch_preserves_unsaved_budget(self):
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor
        identity=editor.current; editor.minutes.setValue(35); editor.show_list()
        self.app.switch_page(0)
        with patch.object(editor.rows_layout,'addWidget') as rebuild:
            editor.refresh_rows(); editor.refresh_rows(); rebuild.assert_not_called()
        self.app.set_language('en'); self.app.open_budget(); editor.show_editor(identity)
        self.assertEqual(editor.minutes.value(),35)
        self.assertEqual(editor.add_button.text(),'Add new')

    def test_saving_one_page_keeps_the_other_pages_unsaved_values(self):
        original=self.store.settings()
        self.app.games_path.setText(str(self.base/'Another games folder'))
        self.app.open_budget(member=target('site','example.com')); editor=self.app.budget_editor; editor.minutes.setValue(25)
        self.app.save_budgets()
        self.assertEqual(self.store.settings().games_root,original.games_root)
        self.assertEqual(self.app.games_path.text(),str(self.base/'Another games folder'))
        editor.show_editor(editor.rules[0]['id']); editor.minutes.setValue(40)
        self.app.save_settings(scope='general')
        self.assertEqual(self.store.settings().games_root,str(self.base/'Another games folder'))
        self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],1500)
        self.assertEqual(editor.minutes.value(),40)
        self.app.save_budgets(); self.assertEqual(self.store.settings().wellbeing_rules[0]['seconds'],2400)

    def test_short_lists_stay_below_header_after_resize_and_returning_from_tall_editor(self):
        app=self.app; editor=app.budget_editor; app.show(); app.open_budget()
        editor.show_editor('shared-games'); app.schedule_editor.day_details.setExpanded(True)
        for section in app.schedule_editor.details.values(): section.setExpanded(True)
        self.pump(.03); editor.show_list()
        for width,height in ((1020,740),(1382,952),(1100,1100)):
            app.resize(width,height)
            for count in (1,3,0):
                with self.subTest(size=(width,height),count=count):
                    editor.shared_created=count>0
                    editor.rules=[new_rule('Site '+str(i),[target('site',f'example{i}.com')],f'site-{i}') for i in range(max(0,count-1))]
                    editor.refresh(); self.pump(.03)
                    self.assertEqual(app.budget_scroll.verticalScrollBar().maximum(),0)
                    self.assertEqual(app.budget_scroll.horizontalScrollBar().maximum(),0)
                    header_bottom=editor.add_button.mapTo(editor,QPoint(0,editor.add_button.height())).y()
                    rows_top=editor.rows_widget.mapTo(editor,QPoint()).y()
                    self.assertLessEqual(rows_top-header_bottom,16)
                    previous_bottom=None
                    for index in range(count):
                        card=editor.rows_layout.itemAt(index).widget()
                        self.assertEqual(card.y(),0 if previous_bottom is None else previous_bottom+10)
                        previous_bottom=card.y()+card.height()
                    if not count:
                        self.assertTrue(editor.empty.isVisible())
                        self.assertLessEqual(editor.empty.mapTo(editor,QPoint()).y()-header_bottom,32)

    def test_long_budget_list_scrolls_all_the_way_to_last_row(self):
        app=self.app; editor=app.budget_editor; app.resize(1020,740)
        editor.rules=[new_rule('Budget '+str(i),[target('site',f'example{i}.com')],f'site-{i}') for i in range(15)]
        app.open_budget(); self.pump(.03)
        scroll=app.budget_scroll; self.assertGreater(scroll.verticalScrollBar().maximum(),0)
        self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()); self.pump(.02)
        last=editor.rows_layout.itemAt(editor.rows_layout.count()-1).widget()
        bottom=last.mapTo(scroll.viewport(),QPoint(0,last.height())).y()
        self.assertLessEqual(bottom,scroll.viewport().height())
        self.assertGreater(bottom,0)

    def test_library_empty_result_and_focus_controls_stay_at_top(self):
        app=self.app; app.resize(1382,952); app.show(); app.switch_page(0)
        app.search.setText('no matching game'); self.pump(.03)
        self.assertTrue(app.empty.isVisible())
        search_bottom=app.search.mapTo(app.scroll.widget(),QPoint(0,app.search.height())).y()
        self.assertLess(app.empty.y()-search_bottom,60)
        focus=app.focus_page; app.switch_page(4)
        for index in (0,1):
            focus.rule_tabs.setCurrentIndex(index); self.pump(.03)
            page=focus.rule_tabs.currentWidget(); first=page.layout().itemAt(0)
            self.assertEqual(first.geometry().top(),page.layout().contentsMargins().top())


if __name__=='__main__': unittest.main()
