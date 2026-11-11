"""Selections, saved list edits and background refresh retain the user's place."""
from dataclasses import replace
from unittest import TestCase
from gametime.qt_budgets import new_rule
from gametime.wellbeing import target
import test_qt_ui as fixture


class ScrollPositionTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp;tearDown=fixture.QtInterfaceTests.tearDown;pump=fixture.QtInterfaceTests.pump

    def test_statistics_day_selection_keeps_chart_in_view(self):
        from datetime import date
        today=date.today().isoformat();self.store.add_usage({(today,self.games[0].id):120})
        self.app.resize(1000,700);self.app.switch_page(1);self.app.show();self.pump(.1)
        page=self.app.statistics;bar=page.scroll.verticalScrollBar();bar.setValue(180);before=bar.value();self.assertGreater(before,0)
        page.choose_day(today);self.pump(.05);self.assertEqual(bar.value(),before)

    def test_budget_toggle_and_return_from_editor_keep_list_position(self):
        rules=[new_rule(f'Budget {i}',[target('site',f'site{i}.example.com')]) for i in range(20)]
        settings=replace(self.app.settings,wellbeing_rules=rules,budget_setup_completed=True)
        self.store.save_settings(settings);self.app.settings=self.app.catalog.settings=settings;editor=self.app.budget_editor;editor.saved(settings)
        self.app.resize(1000,700);self.app.open_budget();self.pump(.1);bar=self.app.budget_scroll.verticalScrollBar();bar.setValue(700);before=bar.value();self.assertGreater(before,0)
        editor.enable_rule(rules[12]['id']);self.pump(.05);self.assertEqual(bar.value(),before)
        editor.show_editor(rules[12]['id']);self.pump(.05);self.assertEqual(bar.value(),0)
        editor.show_list();self.pump(.05);self.assertEqual(bar.value(),before)

    def test_notification_refresh_and_return_keep_list_position(self):
        notifications=[dict(id=f'{i+1:032x}',title=f'Reminder {i}',text='A reminder message',icon='preset:bell',minute=720,enabled=True) for i in range(18)]
        settings=replace(self.app.settings,scheduled_notifications=notifications,budget_setup_completed=True)
        self.store.save_settings(settings);self.app.settings=self.app.catalog.settings=settings;page=self.app.notifications_page
        self.app.pages.setCurrentWidget(page);self.app.resize(1000,700);self.app.show();page.refresh();self.pump(.1)
        bar=page.scroll.verticalScrollBar();bar.setValue(900);before=bar.value();self.assertGreater(before,0,(len(page.row_keys),page.scroll.size(),page.scroll.widget().size(),page.scroll.widget().minimumSizeHint(),page.list_widget.minimumSizeHint()))
        page._revision+=1;page.refresh();self.pump(.05);self.assertEqual(bar.value(),before)
        page.edit('scheduled:'+notifications[10]['id']);self.pump(.05);self.assertEqual(bar.value(),0)
        page.cancel_edit();self.pump(.05);self.assertEqual(bar.value(),before)

    def test_activity_refresh_keeps_scrolled_list_even_if_selection_is_above_it(self):
        from gametime.qt_activities import ActivityList
        listing=ActivityList(self.app,'site');self.addCleanup(listing.close);listing.resize(800,500);listing.show()
        listing.entries=[(target('site',f'site{i}.example.com'),f'Activity {i:02d}') for i in range(80)];listing.filter();self.pump(.1)
        bar=listing.list.verticalScrollBar();bar.setValue(35);before=bar.value();self.assertGreater(before,0)
        listing.entries=[(member,name+' updated') for member,name in listing.entries];listing.filter();self.pump(.05)
        self.assertEqual(bar.value(),before);listing.close()
