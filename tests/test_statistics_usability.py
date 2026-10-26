from datetime import date, timedelta
from dataclasses import replace
import os
import unittest
import test_qt_ui as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class StatisticsUsabilityTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
    setUp=fixtures.QtInterfaceTests.setUp
    tearDown=fixtures.QtInterfaceTests.tearDown
    pump=fixtures.QtInterfaceTests.pump

    def test_overview_starts_with_daily_totals_and_compact_filters(self):
        page=self.app.statistics; today=date.today().isoformat()
        self.store.add_usage({(today,self.games[0].id):120})
        self.app.switch_page(1)
        self.assertEqual(page.chart_mode.currentData(),'total')
        self.assertEqual(len(page.report.days),7)
        self.assertEqual(page.report.total,120)
        self.assertEqual(page.chart.series,{})
        self.assertTrue(page.legend.isHidden())
        self.assertTrue(page.computer_panel.isHidden())
        self.assertTrue(page.custom_range.isHidden())
        self.assertTrue(page.games_table.isColumnHidden(1))
        self.assertTrue(page.games_table.isColumnHidden(2))

    def test_ranking_search_keeps_period_total_and_other_filters(self):
        page=self.app.statistics; today=date.today().isoformat()
        self.store.add_usage({(today,self.games[0].id):120,(today,self.games[1].id):60})
        self.app.switch_page(1); page.search.setText('beta')
        self.assertEqual(page.games_table.rowCount(),1)
        self.assertEqual(page.games_table.item(0,0).text(),'Fixture Beta')
        self.assertEqual(page.report.total,180)
        page.search.setText('missing'); self.assertEqual(page.games_table.rowCount(),0)
        self.assertFalse(page.empty_details.isHidden())
        page.search.clear(); self.assertEqual(page.games_table.rowCount(),2)

    def test_calendar_draft_waits_for_apply_and_day_selection_can_be_cleared(self):
        page=self.app.statistics; today=date.today(); yesterday=(today-timedelta(days=1)).isoformat()
        self.store.add_usage({(today.isoformat(),self.games[0].id):120,(yesterday,self.games[0].id):60})
        self.app.switch_page(1)
        page.period.setCurrentIndex(page.period.findData('custom'))
        page.start.setText(today.isoformat()); page.end.setText(today.isoformat())
        page.refresh(live=True); self.assertEqual(page.report.total,180)
        self.app.switch_page(0); self.app.switch_page(1); self.assertEqual(page.report.total,180)
        page.apply_dates(); self.assertEqual(page.report.total,120)
        page.choose_day(today.isoformat()); self.assertEqual(page.day_selector.currentData(),today.isoformat())
        page.show_period(); self.assertIsNone(page.selected_day); self.assertIsNone(page.day_selector.currentData())
        page.period.setCurrentIndex(page.period.findData('yesterday'))
        self.assertEqual(page.report.total,60); self.assertEqual(len(page.report.days),1)

    def test_chart_groups_small_series_without_losing_ranking_or_total(self):
        from gametime.model import Game
        page=self.app.statistics; day=date.today().isoformat()
        games=[Game('extra:'+str(i),'Extra '+str(i),'Steam',str(self.base/('extra'+str(i)))) for i in range(9)]
        self.store.upsert(games); self.store.add_usage({(day,game.id):60*(i+1) for i,game in enumerate(games)})
        self.app.switch_page(1); page.chart_mode.setCurrentIndex(page.chart_mode.findData('game'))
        self.assertEqual(len(page.chart.series),6)
        self.assertEqual(sum(page.chart.segments[day].values()),page.report.total)
        self.assertEqual(len(page.report.games),9); self.assertEqual(page.games_table.rowCount(),9)
        page.chart_mode.setCurrentIndex(page.chart_mode.findData('total'))
        self.assertEqual(page.chart.days[day],page.report.total); self.assertEqual(page.chart.series,{})

    def test_local_activity_filter_and_language_preserve_dates_and_view(self):
        page=self.app.statistics; self.app.switch_page(1)
        page.preset(30); page.category.setCurrentIndex(page.category.findData('apps'))
        self.assertEqual(page.scope,'local'); self.assertFalse(page.devices.isEnabled())
        page.choose_day(date.today().isoformat())
        state=(page.start.text(),page.end.text(),page.selected_day,page.period.currentData())
        self.app.set_language('en')
        self.assertEqual((page.start.text(),page.end.text(),page.selected_day,page.period.currentData()),state)
        self.assertEqual(page.chart_mode.currentData(),'total')
        page.category.setCurrentIndex(page.category.findData('games'))
        self.assertEqual(page.scope,'all')

    def test_focus_view_does_not_rebuild_hidden_activity_history(self):
        from unittest.mock import patch
        page=self.app.focus_page
        self.assertEqual(page.sections.currentIndex(),0)
        with patch.object(self.app.focus,'usage') as usage,patch.object(self.app.focus,'history') as history:
            page.refresh(force=True)
            for _ in range(4): page.refresh()
            usage.assert_not_called(); history.assert_not_called()

    def test_library_keeps_games_open_and_launchers_collapsed_by_default(self):
        self.assertNotIn(3,self.app.nav)
        self.assertFalse(self.app.clients_toggle.isChecked())
        self.assertTrue(self.app.clients_page.isHidden())
        self.store.save_client_cache([])
        self.app.clients_toggle.click()
        self.assertFalse(self.app.clients_page.isHidden())
        self.assertEqual(self.app.pages.currentIndex(),0)
        self.assertTrue(self.app.nav[0].isChecked())
        self.app.clients_toggle.click()
        self.assertTrue(self.app.clients_page.isHidden())
        self.assertEqual(self.app.pages.currentIndex(),0)

    def test_visible_blacklist_add_remove_keeps_the_running_timer(self):
        from unittest.mock import patch
        page=self.app.focus_page
        self.app.focus.start(100); remaining=self.app.focus.remaining
        page.url_input.setText('https://example.com/private/path'); page.add_url()
        self.assertEqual(page.block_lists['site'].count(),1)
        self.assertTrue(self.app.focus.restricting)
        self.assertEqual(self.app.focus.remaining,remaining)
        page.block_lists['site'].setCurrentRow(0); page.remove_rule_button.click()
        self.assertEqual(self.app.focus.settings.block_sites,[])
        self.assertEqual(page.block_lists['site'].count(),0)

    def test_activity_opens_the_same_day_and_category_in_statistics(self):
        from datetime import datetime
        from gametime.tracker import Sample
        now=datetime.now().astimezone(); focus=self.app.focus
        for second in range(3): focus.tick(Sample(now+timedelta(seconds=second),second,r'C:\Brave\brave.exe','2:1'),'example.com')
        page=self.app.focus_page; page.sections.setCurrentIndex(1); page.tabs.setCurrentIndex(1)
        page.open_statistics()
        self.assertEqual(self.app.pages.currentIndex(),1)
        self.assertEqual(self.app.statistics.category.currentData(),'websites')
        self.assertEqual(self.app.statistics.report.total,2)
        self.assertEqual(len(self.app.statistics.report.days),1)
