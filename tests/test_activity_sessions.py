from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest
from gametime.store import Store
from gametime.focus import Focus
from gametime.tracker import Sample
from gametime.activity_sessions import Sessions,record,local_snapshot,count_rows,validate
from gametime.statistics_sync import StatisticsData,FORMAT,game_key
from gametime.model import Game


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'usage.sqlite3');self.addCleanup(self.store.close)
        self.start=datetime(2026,11,3,12).astimezone()
        with self.store.db:self.store.db.execute("UPDATE settings SET value=? WHERE key='sessions_since'",(str(self.start.timestamp()-3600),))

    def test_switches_and_flushes_count_foreground_runs_once(self):
        focus=Focus(self.store)
        for second,path in enumerate(['editor.exe','editor.exe','other.exe','editor.exe','editor.exe']):
            focus.tick(Sample(self.start+timedelta(seconds=second),second,path,'1:1'))
            focus.flush()
        counts={(r[1],r[2]):r[3] for r in local_snapshot(self.store)['rows']}
        self.assertEqual(counts,{('app','editor.exe'):2,('app','other.exe'):1})
        self.assertEqual(sum(r[3] for r in focus.usage('2026-11-03')),4)

    def test_midnight_and_browser_backfill_merge_without_duplicate_sessions(self):
        start=datetime(2026,11,3,23,59,58).astimezone().timestamp()
        with self.store.db:
            record(self.store.db,'site','example.test',start,start+2,'2026-11-03')
            record(self.store.db,'site','example.test',start+4,start+8,'2026-11-04')
            record(self.store.db,'site','example.test',start+2,start+4,'2026-11-04')
            record(self.store.db,'site','example.test',start,start+8,'2026-11-03')
        self.assertEqual(local_snapshot(self.store)['rows'],[['2026-11-03','site','example.test',1]])
        self.assertEqual(self.store.db.execute('SELECT start,finish FROM activity_sessions').fetchall(),[(start,start+8)])

    def test_sleep_excluded_intervals_and_browser_categories(self):
        focus=Focus(self.store)
        sequence=[(0,'chrome.exe','a.test'),(1,'chrome.exe','b.test'),(2,'chrome.exe',''),(3,'editor.exe',''),(100,'chrome.exe','a.test'),(101,'chrome.exe','a.test')]
        for second,path,site in sequence:focus.tick(Sample(self.start+timedelta(seconds=second),second,path,'1:1'),site)
        focus.flush();counts={(r[1],r[2]):r[3] for r in local_snapshot(self.store)['rows']}
        self.assertEqual(counts,{('app','chrome.exe'):2,('site','a.test'):2,('site','b.test'):1,('browser','other'):1})
        data=StatisticsData(self.store,focus);rows=data.activity_history_by_computer('2026-11-03','2026-11-03','','local','all')
        self.assertEqual(count_rows(rows,data.session_data('','local'),'2026-11-03'),(4,True))

    def test_transaction_retry_keeps_usage_and_sessions_together(self):
        sessions=Sessions(self.store);sessions.credit('game','steam:1',self.start.timestamp(),self.start.timestamp()+10,'2026-11-03')
        self.store.db.execute("CREATE TRIGGER reject_usage BEFORE INSERT ON usage BEGIN SELECT RAISE(ABORT,'fixture');END")
        with self.assertRaises(Exception):self.store.add_usage({('2026-11-03','steam:1'):10},sessions=sessions)
        self.assertEqual(local_snapshot(self.store)['rows'],[])
        self.store.db.execute('DROP TRIGGER reject_usage');self.store.add_usage({('2026-11-03','steam:1'):10},sessions=sessions);sessions.clear()
        self.assertEqual(local_snapshot(self.store)['rows'],[['2026-11-03','game','steam:1',1]])

    def test_sync_legacy_unknown_and_device_isolation(self):
        data=StatisticsData(self.store);group='a'*32;remote='b'*32
        value=dict(format=FORMAT,group=group,device=remote,name='Phone',revision=1,started='2026-11-01',rows=[['2026-11-03','game','Game','Steam',30]],sessions={'since':'2026-11-02','rows':[['2026-11-03','game','game',3]]})
        self.assertTrue(data.ingest(value,group));self.assertFalse(data.ingest(value,group))
        rows=data.history_by_computer('2026-11-03','2026-11-03',group)
        self.assertEqual(count_rows(rows,data.session_data(group),'2026-11-03'),(3,False))
        self.assertNotIn(remote,data.session_data('c'*32))
        self.assertEqual(data.snapshot(group,'PC')['sessions']['rows'],[])
        value.pop('sessions');value['revision']=2;data.ingest(value,group)
        self.assertEqual(count_rows(rows,data.session_data(group),'2026-11-03'),(0,True))

    def test_game_alias_and_portable_key_preserve_count(self):
        old=Game('pending:old','Example','Games','C:\\Game','',True);new=Game('steam:123','Example','Steam','C:\\Game','',True)
        self.store.upsert([old]);start=self.start.timestamp()
        with self.store.db:record(self.store.db,'game',old.id,start,start+3,'2026-11-03')
        self.store.reconcile([new],lambda g:True)
        self.assertEqual(local_snapshot(self.store,True)['rows'],[['2026-11-03','game',new.id,1]])

    def test_partial_requires_actual_usage_on_an_untracked_day(self):
        snapshots={'pc':{'since':'2026-11-02','rows':[['2026-11-03','game','new',3]]}}
        newer=[('2026-11-03','new','New','Steam',100,'pc')]
        self.assertEqual(count_rows(newer,snapshots,'2026-10-01'),(3,False))
        self.assertEqual(count_rows(newer+[('2026-11-02','old','Old','Steam',40,'pc')],snapshots,'2026-10-01'),(3,True))
        self.assertEqual(count_rows([('2026-11-01','old','Old','Steam',40,'pc')],snapshots,'2026-10-01'),(0,True))

    def test_upgrade_does_not_invent_counts_from_old_time(self):
        self.store.add_usage({('2026-11-01','steam:1'):3600})
        self.assertEqual(local_snapshot(self.store)['rows'],[])
        sessions=Sessions(self.store);sessions.credit('app','old.exe',self.start.timestamp()-7200,self.start.timestamp()-3601,'2026-11-03');self.assertFalse(sessions.pending)
        with self.assertRaises(ValueError):validate({'since':'2026-11-03','rows':[['2026-11-02','game','id',1]]})
        with self.assertRaises(ValueError):validate({'since':'2026-11-03','rows':[['2026-11-03','game','id',True]]})

    def test_game_tracker_counts_returns_across_individual_flushes(self):
        from gametime.model import Catalog,Settings
        from gametime.tracker import Tracker
        game=Game('steam:fixture','Session fixture','Steam',str(Path(self.temp.name)/'Game'))
        catalog=Catalog(Settings());catalog.apply([game],lambda g:True);tracker=Tracker(self.store,catalog)
        path=str(Path(game.root)/'play.exe')
        for second,active in enumerate([path,path,'',path,path]):
            tracker.tick(Sample(self.start+timedelta(seconds=second),second,active,'fixture' if active else ''));tracker.flush()
        self.assertEqual(local_snapshot(self.store,True)['rows'],[['2026-11-03','game',game.id,2]])

if __name__=='__main__':unittest.main()
