"""Explorer is idle everywhere, including old and linked-computer history."""
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from gametime.activity_identity import is_idle_app
from gametime.activities import known_activities
from gametime.focus import Focus
from gametime.model import Catalog,Game,Settings,blocked
from gametime.statistics_sync import FORMAT,StatisticsData
from gametime.store import Store
from gametime.tracker import Sample,Tracker
from gametime.wellbeing import Wellbeing

EXPLORER=r'C:\Windows\EXPLORER.EXE'
EDITOR=r'C:\Apps\editor.exe'
DAY='2026-10-25'
GROUP='a'*32

class ExplorerIdleTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'usage.sqlite3'); self.addCleanup(self.store.close)
        self.focus=Focus(self.store); self.time=datetime(2026,10,25,12).astimezone()

    def test_default_tracking_and_game_classifier_ignore_explorer_only(self):
        for value in (EXPLORER,r'c:\WINDOWS\explorer.exe','explorer.exe'):
            self.assertTrue(is_idle_app(value)); self.assertTrue(blocked(value))
        for value in (r'C:\Apps\explorer++.exe',r'C:\Apps\fileexplorer.exe',EDITOR,''):
            self.assertFalse(is_idle_app(value))
        def tick(seconds,path):
            sample=Sample(self.time+timedelta(seconds=seconds),seconds,path,'12:34')
            self.focus.tick(sample); return sample
        tick(0,EXPLORER); tick(1,EXPLORER); tick(2,EDITOR); tick(3,EDITOR); tick(4,EXPLORER)
        tick(5,r'C:\Apps\explorer++.exe'); tick(6,r'C:\Apps\explorer++.exe'); tick(7,EXPLORER)
        self.focus.flush()
        self.assertEqual({x[2]:x[3] for x in self.focus.usage(DAY)},{'editor.exe':2,'explorer++.exe':2})
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM activity_items WHERE key LIKE '%explorer.exe'").fetchone()[0],0)
        game=Game('manual:fixture','Fixture game','Kézi',r'C:\Windows'); self.store.upsert([game]); self.store.set_rule(EXPLORER,game.id)
        catalog=Catalog(Settings(),self.store.games(True),self.store.overrides(),self.store.rules()); tracker=Tracker(self.store,catalog)
        for second in range(2): tracker.tick(Sample(self.time+timedelta(seconds=second),second,EXPLORER,'12:34'))
        self.assertIsNone(tracker.active); self.assertFalse(tracker.pending); self.assertFalse(tracker.unclassified)
        self.assertEqual(self.store.rules().get(EXPLORER.casefold()),game.id)

    def seed_history(self):
        records=[('app',EXPLORER,'explorer.exe',900),('app',EDITOR,'editor.exe',60),('site','explorer.exe','explorer.exe',20)]
        with self.store.db:
            for kind,key,name,seconds in records:
                self.store.db.execute('INSERT INTO activity_items VALUES (?,?,?)',(kind,key,name))
                self.store.db.execute('INSERT INTO activity_usage VALUES (?,?,?,?)',(DAY,kind,key,seconds))
        return records

    def test_old_local_history_and_library_hidden_without_deleting_data(self):
        self.seed_history()
        self.assertEqual(sum(row[4] for row in self.focus.history(DAY,DAY,'apps')),60)
        self.assertEqual(sum(row[4] for row in self.focus.history(DAY,DAY,'all')),60)
        self.assertEqual(self.focus.history(DAY,DAY,'websites')[0][4],20)
        self.assertEqual(sum(row[3] for row in self.focus.usage(DAY) if row[0]=='app'),60)
        activities=known_activities(self.store,Settings())
        self.assertFalse(any(member['kind']=='app' and is_idle_app(member['value']) for member,_ in activities))
        self.assertTrue(any(member['kind']=='site' and member['value']=='explorer.exe' for member,_ in activities))
        self.assertEqual(self.store.db.execute("SELECT seconds FROM activity_usage WHERE kind='app' AND key=?",(EXPLORER,)).fetchone()[0],900)

    def test_stored_budgets_and_appearance_cannot_reintroduce_explorer(self):
        rule={'id':'explorer-old','name':'Old budget','members':[{'kind':'app','value':r'c:\windows\explorer.exe'}],
              'seconds':1200,'enabled':True,'enforce':False,'overlay':True}
        settings=replace(Settings(),wellbeing_rules=[rule],activity_overlays={'app:explorer.exe':{'overlay_enabled':False}}).validate()
        activities=known_activities(self.store,settings)
        self.assertFalse(any(member['kind']=='app' and is_idle_app(member['value']) for member,_ in activities))
        self.assertEqual(settings.wellbeing_rules,[rule])
        self.assertIn('app:explorer.exe',settings.activity_overlays)

    def test_old_explorer_time_never_spends_budget(self):
        rule={'id':'all-apps','name':'Applications','members':[{'kind':'category','value':'apps'}],
              'seconds':1200,'enabled':True,'enforce':False,'overlay':False}
        settings=replace(Settings(),wellbeing_rules=[rule]); catalog=Catalog(settings,[],{},{}); engine=Wellbeing(self.store,catalog,self.focus)
        with self.store.db:
            self.store.db.executemany('INSERT INTO wellbeing_usage VALUES (?,?,?,?,?)',[(DAY,'',EXPLORER,'',900),(DAY,'',EDITOR,'',60)])
        self.assertEqual(engine.states(self.time)[0].used,60)
        self.assertEqual(engine.states(self.time)[0].remaining,1140)
        self.assertEqual(self.store.db.execute('SELECT SUM(seconds) FROM wellbeing_usage').fetchone()[0],960)

    def test_snapshot_and_imported_history_filter_old_explorer_without_mutating_storage(self):
        self.seed_history(); settings=replace(Settings(),statistics_sync_enabled=True,statistics_sync_group=GROUP)
        self.store.save_settings(settings); data=StatisticsData(self.store,self.focus)
        snap=data.snapshot(GROUP,'Local'); apps=[row for row in snap['activity'] if row[1]=='app']
        self.assertEqual([row[3] for row in apps],['editor.exe'])
        incoming={'format':FORMAT,'group':GROUP,'device':'b'*32,'name':'Other','revision':1,'started':DAY,'rows':[],
                  'activity_started':DAY,'activity':[[DAY,'app','explorer.exe','explorer.exe',700],
                      [DAY,'app',r'D:\Tools\editor.exe','editor.exe',30],[DAY,'site','example.com','example.com',10]]}
        self.assertTrue(data.ingest(incoming,GROUP))
        for category in ('apps','all'):
            for scope in ('all','local','b'*32):
                rows=data.activity_history_by_computer(DAY,DAY,GROUP,scope,category)
                self.assertFalse(any(row[2].casefold()=='explorer.exe' and row[3]=='Application' for row in rows))
        remote=data.activity_history_by_computer(DAY,DAY,GROUP,'b'*32,'apps')
        self.assertEqual(sum(row[4] for row in remote),30)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM statistics_activity WHERE item_key='explorer.exe'").fetchone()[0],1)
        bare=StatisticsData(self.store,None)
        self.assertEqual(sum(row[4] for row in bare.activity_history_by_computer(DAY,DAY,GROUP,'b'*32,'apps')),30)

if __name__=='__main__': unittest.main()
