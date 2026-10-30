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

    def test_overview_starts_with_everything_and_compact_filters(self):
        page=self.app.statistics; today=date.today().isoformat()
        self.store.add_usage({(today,self.games[0].id):120})
        self.app.switch_page(1)
        self.assertEqual(page.category.currentData(),'all')
        self.assertFalse(hasattr(page,'chart_mode'))
        self.assertEqual(len(page.report.days),7)
        self.assertEqual(page.report.total,120)
        self.assertTrue(page.chart.series)
        key=page._breakdown_keys[0][0]
        self.assertEqual(page.games_table.item(0,0).foreground().color().name(),page.chart.series[key][1])
        self.assertTrue(page.computer_panel.isHidden())
        self.assertTrue(page.computer_legend.isHidden())
        self.assertTrue(page.custom_range.isHidden())
        self.assertTrue(page.games_table.isColumnHidden(1))
        self.assertFalse(page.games_table.isColumnHidden(2))

    def test_daily_chart_stacks_three_computers_with_small_gaps(self):
        from PySide6.QtCore import QPointF,Qt
        from PySide6.QtTest import QTest
        from gametime.qt_widgets import DailyChart
        today=date.today(); days=[(today-timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
        data={day:{'local':{'game':1200,'app':600,'web':300},
                   'laptop':{'game':600,'app':900,'web':300},
                   'other':{'game':900,'app':300,'web':600}} for day in days}
        totals={day:sum(sum(values.values()) for values in groups.values()) for day,groups in data.items()}
        segments={day:{key:sum(group[key] for group in groups.values()) for key in ('game','app','web')}
                  for day,groups in data.items()}
        series={'game':('Game','#73c7ff'),'app':('Application','#f0ba68'),'web':('Website','#7de5bf')}
        names={'local':'Local','laptop':'Laptop','other':'Other'}
        colors={'local':'#f58fa7','laptop':'#b9a1ff','other':'#74d8db'}
        chart=DailyChart(self.app.t); chart.resize(900,300)
        chart.set_days(totals,None,segments,series,data,names,colors); chart.grab()
        self.assertEqual(len(chart.regions),7); self.assertEqual(len(chart.computer_regions),21)
        for day in days:
            blocks=[(rect,identity) for rect,d,identity in chart.computer_regions if d==day]
            self.assertEqual([identity for rect,identity in blocks],['local','laptop','other'])
            self.assertAlmostEqual(blocks[0][0].left(),blocks[1][0].left())
            self.assertAlmostEqual(blocks[0][0].top()-blocks[1][0].bottom(),3,places=4)
            self.assertAlmostEqual(blocks[1][0].top()-blocks[2][0].bottom(),3,places=4)
            self.assertIn('Laptop',chart.tooltip_at(blocks[1][0].center()))
            visible_height=sum(rect.height() for rect,identity in blocks)
            self.assertAlmostEqual(blocks[0][0].bottom()-blocks[-1][0].top(),visible_height+6,places=4)
            self.assertAlmostEqual(blocks[0][0].bottom()-blocks[-1][0].top(),
                                   (chart.height()-30-24)*totals[day]/7200,places=4)
        chosen=[]; chart.day_clicked.connect(chosen.append)
        QTest.mouseClick(chart,Qt.LeftButton,pos=chart.computer_regions[1][0].center().toPoint())
        self.assertEqual(chosen,[days[0]])

    def test_default_everything_includes_games_apps_and_sites_once(self):
        from datetime import datetime
        now=datetime.now().astimezone(); day=now.date().isoformat()
        self.store.add_usage({(day,self.games[0].id):60})
        focus=self.app.focus
        focus._credit('app',r'c:\apps\editor.exe','editor.exe',now,now+timedelta(seconds=30),30)
        focus._credit('app',r'c:\brave\brave.exe','brave.exe',now,now+timedelta(seconds=60),60)
        focus._credit('site','example.com','example.com',now,now+timedelta(seconds=40),40)
        self.app.switch_page(1); page=self.app.statistics
        self.assertEqual(page.category.currentData(),'all')
        self.assertEqual(page.report.total,150)
        self.assertEqual({row[2] for row in page.report.games},{self.games[0].source,'Application','Website','Browser'})

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

    def test_list_combines_names_and_filters_computers_independently(self):
        from gametime.statistics_sync import FORMAT
        today=date.today().isoformat(); group='ab'*16; laptop='12'*16
        self.app.settings=replace(self.app.settings,statistics_sync_group=group)
        self.store.add_usage({(today,self.games[0].id):120})
        snapshot=dict(format=FORMAT,group=group,device=laptop,name='Laptop',revision=1,started=today,
                      rows=[[today,'other-game','  fixture alpha  ','Steam',60],
                            [today,'third-game','Another game','Steam',30]])
        self.app.statistics_data.ingest(snapshot,group); self.app.switch_page(1)
        page=self.app.statistics; page.category.setCurrentIndex(page.category.findData('games'))
        self.assertEqual(page.report.total,210); self.assertEqual(page.games_table.rowCount(),3)
        page.merge_duplicates.setChecked(True)
        self.assertEqual(page.games_table.rowCount(),2)
        self.assertEqual(page.games_table.item(0,3).text(),'00:03:00')
        self.assertEqual(page.games_table.item(0,1).text(),'Több gép')
        self.assertEqual(page.games_table.item(0,4).text(),'85,7%')
        page.detail_devices.setCurrentIndex(page.detail_devices.findData(laptop))
        self.assertEqual(page.scope,'all'); self.assertEqual(page.report.total,210)
        self.assertEqual(page.games_table.rowCount(),2)
        self.assertEqual(page.games_table.item(0,3).text(),'00:01:00')
        self.assertEqual(page.games_table.item(0,4).text(),'66,7%')
        page.search.setText('alpha'); self.assertEqual(page.games_table.rowCount(),1)
        self.assertEqual(page.games_table.item(0,4).text(),'66,7%')
        page.search.clear(); page.detail_devices.setCurrentIndex(page.detail_devices.findData('all'))
        page.merge_duplicates.setChecked(False); self.assertEqual(page.games_table.rowCount(),3)
        page.choose_day(today); self.assertEqual(page.games_table.rowCount(),3)
        self.app.set_language('en')
        self.assertEqual(page.detail_devices.currentData(),'all'); self.assertFalse(page.merge_duplicates.isChecked())
        self.assertEqual(page.merge_duplicates.text(),'Combine matching names')

    def test_each_activity_category_defaults_to_colored_breakdown(self):
        from datetime import datetime,timedelta
        now=datetime.now().astimezone(); focus=self.app.focus
        for kind,key in (('app',r'c:\apps\one.exe'),('app',r'c:\apps\two.exe'),
                         ('site','one.example.com'),('site','two.example.com')):
            focus._credit(kind,key,key,now,now+timedelta(seconds=30),30)
        page=self.app.statistics; self.app.switch_page(1)
        for category in ('apps','websites'):
            page.category.setCurrentIndex(page.category.findData(category))
            self.assertEqual(len(page.chart.series),2)
            self.assertTrue(page.chart.series)
            for row in range(page.games_table.rowCount()):
                key=page._breakdown_keys[row][0]
                self.assertEqual(page.games_table.item(row,0).foreground().color().name(),page.chart.series[key][1])
        self.assertFalse(hasattr(page,'chart_mode'))

    def test_series_colors_are_distinct_and_stable(self):
        from gametime.qt_statistics import StatisticsColors
        for kind in ('computer','game'):
            colors=StatisticsColors(); keys=[f'fixture-{i}' for i in range(64)]
            first=[colors.color(key,kind) for key in keys]
            self.assertEqual(len(set(first)),len(first))
            self.assertGreater(min(colors.difference(a,b)**.5 for i,a in enumerate(first[:5]) for b in first[:i]),25)
            self.assertEqual(first,[colors.color(key,kind) for key in keys])

    def test_removed_chart_mode_falls_back_to_activity_breakdown(self):
        self.app._build({'statistics_chart_mode':'total'})
        self.assertFalse(hasattr(self.app.statistics,'chart_mode'))

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

    def test_custom_dates_use_themed_calendars_inside_the_window(self):
        from PySide6.QtCore import QPoint,QRect,Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QTableView,QToolButton
        self.app.resize(1000,700); self.app.show(); self.app.switch_page(1)
        page=self.app.statistics; page.period.setCurrentIndex(page.period.findData('custom'))
        page.scroll.ensureWidgetVisible(page.start); self.pump(.1)
        original=page._range
        for field,number in ((page.start,10),(page.end,19)):
            QTest.mouseClick(field,Qt.LeftButton,pos=QPoint(field.width()-12,field.height()//2)); self.pump(.15)
            calendar=field.calendarWidget(); self.assertTrue(calendar.isVisible())
            popup=calendar.window(); bounds=QRect(self.app.mapToGlobal(QPoint()),self.app.size())
            self.assertTrue(bounds.contains(popup.geometry()))
            self.assertIn('#192126',calendar.styleSheet())
            self.assertEqual(calendar.findChild(QToolButton,'qt_calendar_prevmonth').text(),'‹')
            view=calendar.findChild(QTableView); model=view.model()
            candidates=[model.index(row,col) for row in range(model.rowCount()) for col in range(model.columnCount())
                        if str(model.data(model.index(row,col)))==str(number)]
            self.assertEqual(len(candidates),1)
            QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualRect(candidates[0]).center()); self.pump(.1)
            self.assertEqual(field.date().day(),number)
            self.assertEqual(page._range,original)
        page.apply_dates(); self.assertEqual(page._range,(page.start.text(),page.end.text()))
        self.app.set_language('en')
        self.assertEqual(page.start.calendarWidget().locale().name(),'en_GB')

    def test_chart_includes_all_series_without_losing_ranking_or_total(self):
        from gametime.model import Game
        page=self.app.statistics; day=date.today().isoformat()
        games=[Game('extra:'+str(i),'Extra '+str(i),'Steam',str(self.base/('extra'+str(i)))) for i in range(9)]
        self.store.upsert(games); self.store.add_usage({(day,game.id):60*(i+1) for i,game in enumerate(games)})
        self.app.switch_page(1)
        self.assertEqual(len(page.chart.series),9)
        self.assertEqual(sum(page.chart.segments[day].values()),page.report.total)
        self.assertEqual(len(page.report.games),9); self.assertEqual(page.games_table.rowCount(),9)
        self.assertEqual(page.chart.days[day],page.report.total)
        page.chart.resize(800,240); page.chart.grab()
        self.assertEqual(len([region for region,d,key in page.chart.segment_regions if d==day]),9)
        region=next(region for region,d,identity in page.chart.computer_regions if d==day and identity=='local')
        tooltip=page.chart.tooltip_at(region.center())
        for game in games: self.assertIn(game.name,tooltip)
        for row in range(page.games_table.rowCount()):
            key=page._breakdown_keys[row][0]
            self.assertEqual(page.games_table.item(row,0).foreground().color().name(),page.chart.series[key][1])

    def test_local_activity_filter_and_language_preserve_dates_and_view(self):
        page=self.app.statistics; self.app.switch_page(1)
        page.preset(30); page.category.setCurrentIndex(page.category.findData('apps'))
        self.assertEqual(page.scope,'all'); self.assertFalse(page.devices.isEnabled())
        page.choose_day(date.today().isoformat())
        state=(page.start.text(),page.end.text(),page.selected_day,page.period.currentData())
        self.app.set_language('en')
        self.assertEqual((page.start.text(),page.end.text(),page.selected_day,page.period.currentData()),state)
        self.assertFalse(hasattr(page,'chart_mode'))
        page.category.setCurrentIndex(page.category.findData('games'))
        self.assertEqual(page.scope,'all')

    def test_focus_view_does_not_rebuild_hidden_activity_history(self):
        from unittest.mock import patch
        page=self.app.focus_page
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

    def test_websites_are_available_in_statistics(self):
        from datetime import datetime
        from gametime.tracker import Sample
        now=datetime.now().astimezone(); focus=self.app.focus
        for second in range(3): focus.tick(Sample(now+timedelta(seconds=second),second,r'C:\Brave\brave.exe','2:1'),'example.com')
        self.app.switch_page(1); self.app.statistics.category.setCurrentIndex(self.app.statistics.category.findData('websites'))
        self.assertEqual(self.app.statistics.report.total,2)
