"""Opt-in parallel audio accounting: conserve budgets, keep foreground sessions."""
from dataclasses import replace
from datetime import datetime,timedelta,date
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
import ctypes as C
import json
import tempfile

from gametime.store import Store
from gametime.model import Settings,Catalog,Game
from gametime.focus import Focus,app_key
from gametime.tracker import Sample
from gametime.wellbeing import Wellbeing,target
from gametime.background_media import BackgroundMedia
from gametime.activity_sessions import local_snapshot
from gametime.media_audio import AudioSampler
from gametime.statistics_sync import StatisticsData,validate_snapshot


class BackgroundMediaTests(TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.store=Store(Path(temp.name)/'usage.sqlite3');self.addCleanup(self.store.close)
        self.settings=Settings(games_root=str(Path(temp.name)/'Games'))
        self.focus=Focus(self.store);self.catalog=Catalog(self.settings)
        self.engine=Wellbeing(self.store,self.catalog,self.focus)
        self.audio=Mock();self.audio.sample.return_value=[]
        self.bridge=Mock();self.bridge.media.return_value=[]
        self.app=SimpleNamespace(store=self.store,focus=self.focus,wellbeing=self.engine,
            browser_bridge=self.bridge,browser_continuity=SimpleNamespace(browser_path=lambda browser:'C:/Apps/'+browser+'.exe'),update_focus_policy=Mock())
        self.media=BackgroundMedia(self.app,self.audio)
        self.start=datetime.combine(date.today(),datetime.min.time()).replace(hour=12).astimezone()
        self.editor=r'C:\Apps\editor.exe';self.player=r'C:\Apps\player.exe';self.browser=r'C:\Apps\brave.exe'
        with self.store.db:self.store.db.execute("UPDATE settings SET value=? WHERE key='sessions_since'",(str(self.start.timestamp()-86400),))

    def rules(self,**groups):
        rules=[dict(id=key,name=key,members=members,seconds=600,enabled=True,enforce=False,overlay=False) for key,members in groups.items()]
        self.settings=replace(self.settings,wellbeing_rules=rules).validate();self.catalog.settings=self.settings
        self.store.save_settings(self.settings)

    def enable(self,kind,value):self.media.set_enabled(target(kind,value),True)

    def tick(self,second,path=None,host='',interactive=True,redirect='',wall=None):
        sample=Sample(wall or self.start+timedelta(seconds=second),second,path or self.editor,'100:1',interactive)
        self.focus.tick(sample,host);self.engine.tick(sample,host,redirect)
        self.media.tick(sample,self.engine.current[1],redirect)
        return sample

    def totals(self,wall=None):return {s.rule['id']:s.used for s in self.engine.states(wall or self.start)}

    def usage(self):
        self.focus.flush();self.engine.flush()
        return {(kind,key):seconds for day,kind,key,seconds in self.store.db.execute('SELECT * FROM activity_usage')}

    def test_default_off_and_selected_app_only(self):
        self.audio.sample.return_value=[(self.player,'101:1')]
        self.tick(0);self.tick(1)
        self.assertNotIn(('app',app_key(self.player)),self.usage());self.audio.sample.assert_called_with(False)
        self.enable('app',self.player);self.tick(2);self.tick(3)
        self.assertEqual(self.usage()['app',app_key(self.player)],1)
        restored=BackgroundMedia(self.app,self.audio);self.assertTrue(restored.enabled(target('app',r'D:\New\PLAYER.exe')))
        self.media.set_enabled(target('app',self.player),False);self.tick(4);self.tick(5)
        self.assertEqual(self.usage()['app',app_key(self.player)],1)

    def test_parallel_groups_are_union_and_rule_edit_recomputes(self):
        self.enable('app',self.player)
        self.audio.sample.return_value=[(self.player,'101:1'),(self.player,'102:1')]
        self.rules(player=[target('app',self.player)],editor=[target('app',self.editor)],both=[target('category','apps')])
        for second in range(4):self.tick(second)
        self.assertEqual(self.totals(),dict(player=3,editor=3,both=3))
        self.rules(player=[target('app',self.player)],both=[target('app',self.player),target('app',self.editor)])
        self.assertEqual(self.totals(),dict(player=3,both=3));self.usage()
        restored=Wellbeing(self.store,self.catalog,self.focus)
        self.assertEqual({s.rule['id']:s.used for s in restored.states(self.start)},dict(player=3,both=3))

    def test_focus_switch_has_no_duplicate_time_or_extra_sessions(self):
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(player=[target('app',self.player)])
        for second,path in enumerate([self.player,self.player,self.editor,self.player,self.player,self.editor,self.editor]):self.tick(second,path)
        self.assertEqual(self.totals()['player'],6)
        self.assertEqual(self.usage()['app',app_key(self.player)],6)
        counts={(r[1],r[2]):r[3] for r in local_snapshot(self.store)['rows']}
        self.assertEqual(counts['app',app_key(self.player)],2)

    def test_paused_excluded_tracking_off_and_sleep(self):
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(player=[target('app',self.player)])
        self.tick(0);self.tick(1);self.audio.sample.return_value=[];self.tick(2);self.tick(3)
        self.assertEqual(self.totals()['player'],2)
        self.audio.sample.return_value=[(self.player,'101:1')];self.tick(4)
        self.focus.settings.excluded_apps=[app_key(self.player)];self.tick(5)
        self.assertEqual(self.totals()['player'],2)
        self.focus.settings.excluded_apps=[];self.tick(6);self.tick(100)
        self.assertEqual(self.totals()['player'],2)
        self.focus.settings.tracking=False;self.tick(101);self.tick(102)
        self.assertEqual(self.totals()['player'],2)

    def test_locked_audio_counts_without_foreground_deduction(self):
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(player=[target('app',self.player)])
        self.tick(0,self.player);self.tick(1,self.player,interactive=False);self.tick(2,self.player,interactive=False)
        self.assertEqual(self.totals()['player'],2);self.assertEqual(self.usage()['app',app_key(self.player)],2)
        self.assertEqual(local_snapshot(self.store)['rows'],[])

    def test_two_sites_keep_full_history_without_double_browser_budget(self):
        for site in ('music.example.com','video.example.com'):self.enable('site',site)
        self.audio.sample.return_value=[(self.browser,'102:1')]
        self.bridge.media.return_value=[('brave',[('music.example.com',''),('video.example.com',''),('other.example.com','')])]
        self.rules(music=[target('site','music.example.com')],video=[target('site','video.example.com')],both=[target('category','sites')],browser=[target('app',self.browser)])
        self.tick(0);self.tick(1);self.tick(2,self.browser,'music.example.com');self.tick(3,self.browser,'music.example.com')
        self.assertEqual(self.totals(),dict(music=3,video=3,both=3,browser=3))
        usage=self.usage();self.assertEqual(usage['app',app_key(self.browser)],3)
        self.assertNotIn(('site','other.example.com'),usage)
        all_rows=self.focus.history(str(self.start.date()),str(self.start.date()),'all')
        self.assertEqual({row[1]:row[4] for row in all_rows},{'activity:app:'+app_key(self.editor):2,'activity:site:music.example.com':3,'activity:site:video.example.com':3})
        self.assertEqual([r for r in local_snapshot(self.store)['rows'] if r[1]=='site'],[[str(self.start.date()),'site','music.example.com',1]])

    def test_sites_need_audible_browser_and_exact_selection(self):
        self.enable('site','music.example.com');self.bridge.media.return_value=[('brave',[('music.example.com',''),('sub.music.example.com','')])]
        self.tick(0);self.tick(1);self.assertNotIn(('site','music.example.com'),self.usage())
        self.audio.sample.return_value=[(self.browser,'102:1')];self.tick(2);self.tick(3)
        self.assertEqual(self.usage()['site','music.example.com'],1);self.assertNotIn(('site','sub.music.example.com'),self.usage())

    def test_day_boundary_and_custom_renewal_split_once(self):
        self.start=self.start.replace(hour=23,minute=59,second=59)
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(player=[target('app',self.player)],both=[target('category','apps')])
        self.settings=replace(self.settings,budget_reset_overrides={'player':720});self.catalog.settings=self.settings
        self.tick(0);sample=self.tick(2)
        self.assertEqual(self.totals(sample.wall),dict(player=2,both=1));self.usage()
        self.assertEqual([r[0] for r in self.store.db.execute('SELECT SUM(seconds) FROM media_budget_usage GROUP BY day')],[1,1])
        self.tick(43201);self.tick(43202)
        self.assertEqual(self.totals(self.start+timedelta(seconds=43202))['player'],1)

    def test_redirect_exemption_is_preserved_for_parallel_time(self):
        self.enable('site','music.example.com');self.audio.sample.return_value=[(self.browser,'102:1')]
        self.bridge.media.return_value=[('brave',[('music.example.com','one')])]
        self.rules(one=[target('site','music.example.com')],two=[target('site','music.example.com')])
        self.tick(0);self.tick(1);self.assertEqual(self.totals(),dict(one=0,two=1))

    def test_shared_device_budget_exports_the_union_once(self):
        from gametime.device_sharing import local_usage
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(player=[target('app',self.player)],both=[target('category','apps')])
        self.tick(0);self.tick(1);self.tick(2);self.usage()
        for key in ('player','both'):
            self.assertEqual(local_usage(self.store,self.settings,key,{'reset_minute':0}),{str(self.start.date()):2})

    def test_game_identity_migration_keeps_union_deduction(self):
        old=Game('pending:old','Example','Games',r'C:\Game');new=Game('steam:123','Example','Steam',r'C:\Game')
        self.store.upsert([old]);self.catalog.games={old.id:old}
        self.enable('app',self.player);self.audio.sample.return_value=[(self.player,'101:1')]
        self.rules(both=[target('game',old.id),target('app',self.player)])
        self.tick(0,r'C:\Game\play.exe');self.tick(1,r'C:\Game\play.exe');self.usage()
        self.assertEqual(self.totals()['both'],1)
        self.store.reconcile([new],lambda g:True);self.engine.remap({old.id:new.id});self.catalog.games={new.id:new}
        self.rules(both=[target('game',new.id),target('app',self.player)])
        self.assertEqual(self.totals()['both'],1)

    def test_sync_preserves_background_split_and_does_not_republish(self):
        self.enable('site','music.example.com');self.audio.sample.return_value=[(self.browser,'102:1')]
        self.bridge.media.return_value=[('brave',[('music.example.com','')])]
        self.tick(0);self.tick(1);self.tick(2,self.browser,'other.example.com');self.tick(3,self.browser,'other.example.com');self.usage()
        group='a'*32;self.store.save_settings(replace(self.settings,statistics_sync_enabled=True,statistics_sync_group=group))
        data=StatisticsData(self.store,self.focus);snap=data.snapshot(group,'One')
        self.assertTrue(snap['background_activity'])
        other=Store(Path(self.store.path).with_name('other.sqlite3')) if hasattr(self.store,'path') else Store(':memory:')
        self.addCleanup(other.close);other_focus=Focus(other);remote=StatisticsData(other,other_focus)
        remote.ingest(snap,group)
        local=self.focus.history(str(self.start.date()),str(self.start.date()),'all')
        imported=remote.activity_history_by_computer(str(self.start.date()),str(self.start.date()),group,snap['device'],'all')
        self.assertCountEqual(local,[row[:5] for row in imported]);self.assertNotIn('background_activity',remote.snapshot(group,'Two'))
        bad=json.loads(json.dumps(snap));bad['background_activity'][0][3]=999
        with self.assertRaises(ValueError):validate_snapshot(bad,group)
        snap.pop('background_activity');snap['revision']+=1;remote.ingest(snap,group)
        self.assertFalse(other.db.execute("SELECT 1 FROM settings WHERE key LIKE 'statistics_background:%'").fetchone())


class AudioDetectionTests(TestCase):
    def test_opt_out_starts_no_thread(self):
        sampler=AudioSampler();self.assertEqual(sampler.sample(False),());self.assertIsNone(sampler.thread);sampler.close()

    def test_only_active_non_muted_nonzero_signal_is_counted(self):
        sampler=AudioSampler();reader=Mock();reader.sessions.return_value=[('s',123,'control')]
        values={'state':1,'mute':0,'volume':.5,'peak':.1}
        def call(obj,slot,args,ptr):
            key={('control',3):'state',('volume',6):'mute',('volume',4):'volume',('meter',3):'peak'}[obj,slot]
            C.cast(ptr,args[0]).contents.value=values[key]
        with patch('gametime.restriction_audio.query',side_effect=lambda obj,iid:'volume' if iid.startswith('87CE') else 'meter'),patch('gametime.restriction_audio.call',side_effect=call),patch('gametime.restriction_audio.release'),patch('gametime.win32.process_image',return_value=('player.exe','123:1')):
            self.assertEqual(sampler.scan(reader,100),(('player.exe','123:1'),));reader.sessions.assert_called_with(audible_only=True)
            for field,value in (('mute',1),('state',0),('volume',0),('peak',0)):
                original=values[field];values[field]=value
                self.assertEqual(sampler.scan(reader,103),(),field);values[field]=original
            values['peak']=.1;sampler.scan(reader,104);values['peak']=0
            self.assertTrue(sampler.scan(reader,105));self.assertEqual(sampler.scan(reader,106),())

    def test_read_only_windows_audio_scan(self):
        from gametime.restriction_audio import Mutes
        reader=Mutes()
        try:
            rows=AudioSampler().scan(reader,10000)
            self.assertIsInstance(rows,tuple);self.assertEqual(reader.owned,{})
        finally:reader.close()
