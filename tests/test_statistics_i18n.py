from dataclasses import replace
from datetime import datetime
from pathlib import Path
from string import Formatter
import tempfile
import unittest
from gametime.i18n import HU, tr
from gametime.model import Game, Settings, Catalog
from gametime.removal import plan_removal, localize_plan
from gametime.statistics import date_range, summarize
from gametime.store import Store
from gametime.tracker import Tracker, Sample


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'history.sqlite3'
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.close())
        self.a = Game('a','Hidden','Steam',r'C:\GameA')
        self.b = Game('b','Removed','Kézi',r'C:\GameB',installed=False)
        self.store.upsert([self.a,self.b])
        self.store.set_hidden('a',True)
        self.store.set_enabled('a',False)
        self.store.add_usage({('2026-10-16','a'): 60, ('2026-10-16','b'): 30,
                              ('2026-10-18','a'): 10.5, ('2026-10-18','orphan'): 19.5,
                              ('2026-09-01','a'): 999})

    def test_inclusive_dates_zero_days_hidden_removed_and_unknown_games(self):
        report = summarize(self.store.history('2026-10-16','2026-10-18'),'2026-10-16','2026-10-18')
        self.assertEqual(report.days,{'2026-10-16':90,'2026-10-17':0,'2026-10-18':30})
        self.assertEqual(report.total,120)
        self.assertEqual(report.average,40)
        self.assertEqual([(g[0],g[3]) for g in report.games],[('a',70.5),('b',30),('orphan',19.5)])
        self.assertEqual(report.by_day['2026-10-18'][0][0],'orphan')
        self.assertEqual(report.by_day['2026-10-18'][0][1],'orphan')
        self.assertEqual(self.store.hidden_ids(),{'a'})
        self.assertFalse(self.store.overrides()['a'])

    def test_different_installations_of_same_name_stay_separate(self):
        rows = [('2026-10-18','x','Same','Steam',10),('2026-10-18','y','Same','Epic',20)]
        report = summarize(rows,'2026-10-18','2026-10-18')
        self.assertEqual(len(report.games),2)
        self.assertEqual(report.total,30)

    def test_live_pending_time_is_counted_once_after_flush_and_reopen(self):
        tracker = Tracker(self.store,Catalog(Settings(),[self.a],rules={r'c:\gamea\play.exe':'a'}))
        from datetime import timedelta
        now=datetime(2026,10,18,12)
        tracker.tick(Sample(now,100,r'C:\GameA\play.exe','id'))
        tracker.tick(Sample(now+timedelta(seconds=1),101,r'C:\GameA\play.exe','id'))
        tracker.flush(); tracker.flush()
        self.store.close(); self.store=Store(self.path)
        report=summarize(self.store.history('2026-10-18','2026-10-18'),'2026-10-18','2026-10-18')
        self.assertEqual(report.total,31)

    def test_empty_period_and_bad_rows_do_not_invent_time(self):
        report=summarize([('2026-01-01','x','X','Steam',12),('2026-10-18','x','X','Steam',-1)],'2026-10-18','2026-10-18')
        self.assertEqual(report.total,0)
        self.assertFalse(report.games)

    def test_date_validation_and_leap_year(self):
        self.assertEqual(len(date_range('2024-01-01','2024-12-31')),366)
        for start,end in [('2026-10-19','2026-10-18'),('2026-02-30','2026-03-01'),
                          ('20261001','2026-10-18'),('2024-01-01','2025-01-01'),('bad','2026-10-18')]:
            with self.subTest(start=start),self.assertRaises(ValueError): date_range(start,end)


class LanguageTests(unittest.TestCase):
    def test_translation_placeholders_preserve_keys_and_format_specs(self):
        formatter=Formatter()
        fields=lambda text: {(name,spec) for _,name,spec,_ in formatter.parse(text) if name is not None}
        for english,hungarian in HU.items():
            with self.subTest(text=english): self.assertEqual(fields(english),fields(hungarian))

    def test_fresh_default_english_hungarian_selection_persists(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'db.sqlite3'
            store=Store(path)
            self.assertEqual(store.settings().language,'en')
            store.save_settings(replace(store.settings(),language='hu'))
            store.close(); store=Store(path)
            self.assertEqual(store.settings().language,'hu')
            store.close()

    def test_hungarian_alerts_and_formatted_strings(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'db.sqlite3')
            tracker=Tracker(store,Catalog(Settings(language='hu')))
            store.add_usage({('2026-10-18','x'):6000})
            tracker.evaluate(datetime(2026,10,18,12))
            self.assertEqual(tracker.alerts[0].text,'Már csak 20 perc játékidőd maradt mára.')
            store.close()
        self.assertEqual(tr('Active game: {name}','hu',name='Minecraft'),'Aktív játék: Minecraft')
        self.assertEqual(tr('Game discovery failed: problem','hu'),'Játékfelismerési hiba: problem')

    def test_removal_localization_cannot_change_action_or_target(self):
        game=Game('steam:42','Example','Steam',r'C:\Example')
        plan=plan_removal(game)
        translated=localize_plan(plan,game,'hu')
        self.assertEqual((plan.kind,plan.target,plan.arguments),(translated.kind,translated.target,translated.arguments))
        self.assertIn('Example',translated.instructions)
        self.assertIn('eltávolítás',translated.title)
        self.assertEqual(localize_plan(plan,game,'en'),plan)


if __name__=='__main__': unittest.main()
