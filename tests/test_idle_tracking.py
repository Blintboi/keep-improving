"""Synthetic idle input, isolated history and preserved clock-based behavior."""
import ctypes as C
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from gametime.model import Settings,Catalog,Game
from gametime.store import Store
from gametime.tracker import Tracker,Sample
from gametime.focus import Focus
from gametime.wellbeing import Wellbeing
from gametime.background_media import BackgroundMedia
from gametime.idle_tracking import timeout


class IdleTrackingTests(TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'usage.sqlite3');self.addCleanup(self.store.close)
        self.settings=replace(Settings(),pause_when_idle=True,idle_timeout_seconds=60,
            wellbeing_rules=[dict(id='all',name='All activities',members=[dict(kind='category',value=v) for v in ('apps','games','sites')],seconds=600,enabled=True,enforce=False,overlay=True)])
        self.game=Game('fixture','Game','Steam',r'C:\Games\Fixture')
        self.catalog=Catalog(self.settings,[self.game]);self.tracker=Tracker(self.store,self.catalog)
        self.focus=Focus(self.store);self.wellbeing=Wellbeing(self.store,self.catalog,self.focus)
        self.audio=Mock();self.audio.sample.return_value=[]
        bridge=Mock();bridge.media.return_value=[]
        self.app=SimpleNamespace(store=self.store,focus=self.focus,wellbeing=self.wellbeing,browser_bridge=bridge,update_focus_policy=Mock())
        self.media=BackgroundMedia(self.app,self.audio)
        self.start=datetime.now().astimezone().replace(hour=12,minute=0,second=0,microsecond=0)

    def tick(self,t,idle,path=r'C:\Games\Fixture\game.exe',host='',**changes):
        sample=Sample(self.start+timedelta(seconds=t),t,path,'100:1',idle_seconds=idle,**changes)
        sample=self.media.tracking_sample(sample)
        self.tracker.tick(sample);self.focus.tick(sample,host,idle_timeout=timeout(self.catalog.settings));self.wellbeing.tick(sample,host)
        self.media.tick(sample,self.wellbeing.current[1]);return sample

    def test_games_pause_at_threshold_resume_without_backfill_and_keep_restriction_target(self):
        for t,idle in enumerate((58,59,60,61,900,0,1)):self.tick(t,idle)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),3)
        self.assertEqual(self.wellbeing.states(self.start)[0].used,3)
        self.assertEqual(self.tracker.active.id,'fixture')
        self.tick(7,900);self.assertIsNotNone(self.wellbeing.current[1])
        self.tracker.flush();self.focus.flush();self.wellbeing.flush()
        self.assertEqual(self.store.db.execute('SELECT SUM(seconds) FROM usage').fetchone()[0],3)

    def test_apps_sites_and_background_media_share_the_policy_without_stopping_focus(self):
        self.media.set_enabled(dict(kind='app',value=r'C:\Apps\player.exe'),True)
        self.audio.sample.return_value=[(r'C:\Apps\player.exe','101:1')]
        self.focus.start(0)
        for t,idle in enumerate((58,59,60,61,0,1)):
            self.tick(t,idle,r'C:\Apps\brave.exe','example.com')
        self.focus.flush();self.wellbeing.flush()
        rows=list(self.store.db.execute('SELECT kind,key,seconds FROM activity_usage'))
        self.assertEqual(len(rows),3);self.assertTrue(all(r[2]==3 for r in rows),rows)
        self.assertEqual(self.wellbeing.states(self.start)[0].used,3)
        self.assertEqual(self.focus.remaining,self.focus.settings.work*60-5)
        self.assertTrue(self.focus.running)
        # Native coverage must include skipped intervals so browser replay cannot refill them.
        from gametime.continuity_ledger import uncovered
        for kind in ('activity','wellbeing'):
            self.assertEqual(uncovered(self.store.db,kind,self.start.timestamp(),self.start.timestamp()+5),[])

    def test_disabled_or_longer_timeout_keeps_counting_without_input(self):
        self.catalog.settings=replace(self.settings,pause_when_idle=False)
        self.tick(0,900);self.tick(1,901)
        self.catalog.settings=replace(self.settings,idle_timeout_seconds=120)
        self.tick(2,65);self.tick(3,66)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),2)
        self.assertEqual(self.wellbeing.states(self.start)[0].used,2)

    def test_sleep_clock_jumps_and_locked_desktop_still_do_not_count(self):
        self.catalog.settings=replace(self.settings,pause_when_idle=False)
        self.tick(0,0);self.tick(1,0,interactive=False);self.tick(2,0);self.tick(20,0)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),0)
        self.assertEqual(self.wellbeing.states(self.start)[0].used,0)

    def test_defaults_validation_persistence_and_device_local_preferences(self):
        self.assertFalse(Settings().pause_when_idle);self.assertEqual(Settings().idle_timeout_seconds,300)
        self.assertFalse(Settings().media_prevents_idle)
        with self.assertRaises(ValueError):replace(self.settings,media_prevents_idle=1).validate()
        for changes in ({'pause_when_idle':1},{'idle_timeout_seconds':True},{'idle_timeout_seconds':0},{'idle_timeout_seconds':61},{'idle_timeout_seconds':86460},{'idle_timeout_seconds':float('nan')}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):replace(self.settings,**changes).validate()
        self.store.save_settings(self.settings)
        self.assertTrue(self.store.settings().pause_when_idle);self.assertEqual(self.store.settings().idle_timeout_seconds,60)
        from gametime.preferences_sync import values
        saved=values(self.store);self.assertNotIn('settings.pause_when_idle',saved);self.assertNotIn('settings.idle_timeout_seconds',saved)
        self.assertNotIn('settings.media_prevents_idle',saved)

    def test_media_activity_keeps_games_running_without_enabling_background_measurement(self):
        self.catalog.settings=replace(self.settings,media_prevents_idle=True)
        self.audio.sample.return_value=[(r'C:\Apps\podcast.exe','101:1')]
        for t in range(4):self.tick(t,900+t)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),3)
        self.assertEqual(self.wellbeing.states(self.start)[0].used,3)
        self.assertEqual(self.media.atoms,());self.assertEqual(self.media.members,[])
        self.audio.sample.assert_called_with(True)
        self.focus.flush()
        self.assertFalse(any('podcast' in row[0] for row in self.store.db.execute('SELECT key FROM activity_usage')))

    def test_playback_stop_starts_idle_timeout_and_resume_does_not_backfill(self):
        self.catalog.settings=replace(self.settings,media_prevents_idle=True)
        self.tick(0,900)
        self.audio.sample.return_value=[(r'C:\Apps\podcast.exe','101:1')]
        self.tick(1,901);self.tick(2,902)
        self.audio.sample.return_value=[]
        for t in range(3,65):self.tick(t,900+t)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),61)
        self.audio.sample.return_value=[(r'C:\Apps\podcast.exe','101:1')]
        self.tick(65,965);self.tick(66,966)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),62)
        self.catalog.settings=replace(self.settings,media_prevents_idle=False)
        self.tick(67,967);self.tick(68,968)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),62)
        self.audio.sample.assert_called_with(False)

    def test_media_does_not_count_locked_foreground_or_sleep_gaps(self):
        self.catalog.settings=replace(self.settings,media_prevents_idle=True)
        self.audio.sample.return_value=[(r'C:\Apps\podcast.exe','101:1')]
        self.tick(0,900);self.tick(1,901,interactive=False);self.tick(2,902);self.tick(20,920)
        self.assertEqual(sum(self.tracker.totals(self.start.date()).values()),0)

    def test_sleep_expires_media_activity_even_when_awake_clock_stops(self):
        from gametime.idle_tracking import MediaActivity
        activity=MediaActivity();before=Sample(self.start,100,idle_seconds=900)
        self.assertEqual(activity.sample(before,True,True).idle_seconds,0)
        after=replace(before,wall=self.start+timedelta(hours=1),awake=101,idle_seconds=4500)
        self.assertEqual(activity.sample(after,True,False).idle_seconds,3600)

    def test_windows_input_sampling_handles_rollover_failure_and_future_timestamps(self):
        from gametime import win32
        def run(last,now):
            def fill(ptr):C.cast(ptr,C.POINTER(win32.LASTINPUTINFO)).contents.dwTime=last;return True
            with patch.object(win32.u,'GetLastInputInfo',side_effect=fill),patch.object(win32.k,'GetTickCount',return_value=now):return win32.idle_seconds()
        self.assertEqual(run(1000,61000),60);self.assertEqual(run(0xfffffff0,984),1)
        self.assertEqual(run(1010,1000),0)
        with patch.object(win32.u,'GetLastInputInfo',return_value=False):self.assertEqual(win32.idle_seconds(),0)
