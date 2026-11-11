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
        editor=self.app.budget_editor; editor.create_new(); draft=editor.current; editor.show_list()
        self.assertIn(draft,editor.row_keys); self.assertEqual(len(editor.rules),1)
        editor.remove_budget(draft)
        editor.remove_budget('shared-games'); self.app.save_budgets()
        self.assertEqual(editor.row_keys,[]); self.assertFalse(self.store.settings().game_budget_enabled)

    def test_rebuild_both_original_budgets_from_new_and_member_selection(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidget,QDialog
        from gametime.schedule import week_plans
        editor=self.app.budget_editor; self.app.open_budget()
        editor.remove_budget('shared-games'); self.app.save_budgets()
        editor.add_button.click(); draft=editor.current
        editor.minutes.setValue(75); editor.steps.add_step.click()
        editor.replace_members(editor.rule(draft),[target('category','games')])
        self.assertEqual(editor.current,'shared-games')
        self.assertEqual(len(editor.steps.cards),1)
        self.app.save_budgets(); saved=self.store.settings()
        self.assertTrue(saved.game_budget_enabled); self.assertEqual(saved.limit_seconds,4500)
        self.assertIn('shared-games',saved.restriction_plans)
        editor.add_button.click()
        editor.pick_members([],lambda members:editor.replace_members(editor.rule(editor.current),members))
        window=next(w for w in self.app.findChildren(QDialog) if w.isVisible())
        listing=window.findChild(QListWidget)
        computer=next(listing.item(i) for i in range(listing.count()) if listing.item(i).data(Qt.UserRole)=={'kind':'computer','value':'period'})
        computer.setCheckState(Qt.Checked)
        next(b for b in window.findChildren(QPushButton) if b.text()==self.app.t('Use selection')).click()
        self.assertEqual(editor.current,'computer-window'); self.app.save_budgets()
        self.assertTrue(all(p['bedtime_enabled'] for p in week_plans(self.store.settings()).values()))
        self.assertEqual(self.store.settings().wellbeing_rules,[])

    def test_computer_warning_and_minimization_blocks_can_be_removed_and_added(self):
        from gametime.schedule import week_plans
        editor=self.app.budget_editor; self.app.open_budget(); editor.create_computer()
        schedule=self.app.schedule_editor
        self.assertFalse(schedule.computer_warning_card.isHidden())
        remove=next(b for b in schedule.computer_warning_card.findChildren(QPushButton) if b.accessibleName()==self.app.t('Remove warning'))
        remove.click(); self.assertTrue(schedule.computer_warning_card.isHidden())
        from PySide6.QtWidgets import QMenu
        schedule.add_computer_step.click(); menu=schedule.add_computer_step.findChild(QMenu)
        menu.actions()[1].trigger(); menu.close(); self.assertFalse(schedule.computer_restriction_card.isHidden())
        self.app.save_budgets(); plans=week_plans(self.store.settings())
        self.assertTrue(all(not p['bedtime_warning_enabled'] and p['bedtime_minimize'] for p in plans.values()))
        editor.show_editor('computer-window'); schedule.add_computer_step.click()
        menu=schedule.add_computer_step.findChild(QMenu); menu.actions()[0].trigger(); menu.close()
        remove=next(b for b in schedule.computer_restriction_card.findChildren(QPushButton) if b.accessibleName()==self.app.t('Remove restriction'))
        remove.click(); self.app.save_budgets(); plans=week_plans(self.store.settings())
        self.assertTrue(all(p['bedtime_warning_enabled'] and not p['bedtime_minimize'] for p in plans.values()))

    def test_disabled_and_long_named_rules_remain_readable_and_editable(self):
        name='A long budget name '+('abcde '*10)
        rule=new_rule(name,[target('site','example.com')],'long')
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,wellbeing_rules=[rule])
        editor=self.app.budget_editor; editor.saved(self.app.settings)
        self.app.resize(1020,740); self.app.open_budget(); self.pump(.04)
        self.assertEqual(set(editor.row_keys),{'shared-games','long'})
        self.assertEqual(self.app.budget_scroll.horizontalScrollBar().maximum(),0)
        editor.show_editor('long'); editor.minutes.setValue(22); self.app.save_budgets()
        self.assertFalse(self.store.settings().wellbeing_rules[0]['enabled'])
        row=next(editor.rows_layout.itemAt(i).widget() for i in range(editor.rows_layout.count()) if editor.rows_layout.itemAt(i).widget().property('budgetKey')=='long')
        next(b for b in row.findChildren(QPushButton) if b.text()==self.app.t('Enable')).click()
        self.app.save_budgets(); self.assertTrue(self.store.settings().wellbeing_rules[0]['enabled'])

    def test_each_row_deletes_only_its_budget_and_preserves_history_until_saved(self):
        from datetime import date
        from PySide6.QtWidgets import QCheckBox
        editor=self.app.budget_editor; self.app.open_budget(member=target('site','example.com'))
        site=editor.current; self.app.open_budget(member=target('game',self.games[0].id))
        game='game:'+self.games[0].id; self.app.save_budgets()
        day=date.today().isoformat(); self.store.add_usage({(day,self.games[0].id):123})
        self.app.open_budget(); self.pump(.03)
        self.assertEqual(set(editor.row_keys),{'shared-games',site,game})
        for key in list(editor.row_keys):
            row=next(editor.rows_layout.itemAt(i).widget() for i in range(editor.rows_layout.count()) if editor.rows_layout.itemAt(i).widget().property('budgetKey')==key)
            controls=row.findChildren(QPushButton)
            self.assertEqual(len([b for b in controls if not b.icon().isNull()]),1)
            self.assertTrue(any(b.text()==self.app.t('Edit') for b in controls))
        editor.show_editor('shared-games')
        self.assertFalse(any(c.isVisible() and c.text()==self.app.t('Use a shared game budget') for c in editor.findChildren(QCheckBox)))
        editor.show_editor(site)
        self.assertFalse(any(c.isVisible() and c.text()==self.app.t('Use a daily limit') for c in editor.findChildren(QCheckBox)))
        editor.show_list()
        row=next(editor.rows_layout.itemAt(i).widget() for i in range(editor.rows_layout.count()) if editor.rows_layout.itemAt(i).widget().property('budgetKey')=='shared-games')
        trash=next(b for b in row.findChildren(QPushButton) if not b.icon().isNull())
        with patch.object(editor,'ask_delete',return_value=False) as prompt:
            trash.click()
        self.assertIn('shared-games',editor.row_keys)
        prompt.assert_called_once_with(str(self.app.t('Games · shared budget')))
        with patch.object(editor,'ask_delete',return_value=True): trash.click()
        self.assertNotIn('shared-games',editor.row_keys)
        self.assertTrue(self.store.settings().game_budget_enabled)
        self.app.cancel_budget_settings(); self.app.open_budget()
        self.assertNotIn('shared-games',editor.row_keys)
        self.assertTrue(self.store.settings().game_budget_enabled)
        self.app.save_budgets()
        self.assertFalse(self.store.settings().game_budget_enabled)
        self.assertIn(self.games[0].id,self.store.settings().game_limits)
        self.assertEqual(len(self.store.settings().wellbeing_rules),1)
        self.assertEqual(self.store.totals(day),{self.games[0].id:123})
        for key in (site,game):
            row=next(editor.rows_layout.itemAt(i).widget() for i in range(editor.rows_layout.count()) if editor.rows_layout.itemAt(i).widget().property('budgetKey')==key)
            with patch.object(editor,'ask_delete',return_value=True):
                next(b for b in row.findChildren(QPushButton) if not b.icon().isNull()).click()
        self.app.save_budgets()
        self.assertEqual(self.store.settings().wellbeing_rules,[])
        self.assertEqual(self.store.settings().game_limits,{})
        self.assertEqual(self.store.totals(day),{self.games[0].id:123})

    def test_delete_confirmation_is_localized_and_cancel_is_default(self):
        from PySide6.QtCore import QTimer,Qt
        from PySide6.QtWidgets import QApplication,QDialog
        from PySide6.QtTest import QTest
        editor=self.app.budget_editor; self.app.open_budget(); observed=[]
        def respond(answer):
            dialog=QApplication.activeModalWidget()
            self.assertIsInstance(dialog,QDialog)
            labels=dialog.findChildren(QLabel); buttons=dialog.findChildren(QPushButton)
            observed.append((dialog.windowTitle(),[(item.text(),item.textFormat()) for item in labels],
                             [b.text() for b in buttons if b.isDefault()],[(b.text(),b.property('role')) for b in buttons],dialog.objectName()))
            if answer=='Escape': QTest.keyClick(dialog,Qt.Key_Escape)
            else: next(b for b in buttons if b.text()==answer).click()
        QTimer.singleShot(0,lambda:respond('Mégse'))
        self.assertFalse(editor.ask_delete('Játék <teszt>'))
        self.assertEqual(observed[0][0],'Keret törlése')
        self.assertTrue(any('Játék <teszt>' in text and fmt==Qt.PlainText for text,fmt in observed[0][1]))
        self.assertEqual(observed[0][2],['Mégse']); self.assertIn(('Törlés','danger-action'),observed[0][3]); self.assertEqual(observed[0][4],'Surface')
        QTimer.singleShot(0,lambda:respond('Escape'))
        self.assertFalse(editor.ask_delete('Játék <teszt>'))
        QTimer.singleShot(0,lambda:respond('Törlés'))
        self.assertTrue(editor.ask_delete('Játék <teszt>'))
        self.app.set_language('en'); editor=self.app.budget_editor
        QTimer.singleShot(0,lambda:respond('Cancel'))
        self.assertFalse(editor.ask_delete('Game <test>'))
        self.assertEqual(observed[-1][0],'Delete budget'); self.assertEqual(observed[-1][2],['Cancel'])

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
