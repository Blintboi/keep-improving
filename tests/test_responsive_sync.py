from dataclasses import replace
from datetime import datetime,timedelta
from unittest.mock import patch
import unittest
import test_qt_ui as fixture
from gametime.activity_identity import automatic_exclusion,app_identity
from gametime.tracker import Sample
from gametime.companion_sync import snapshot

class ResponsiveCompanionTests(unittest.TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp
    tearDown=fixture.QtInterfaceTests.tearDown
    pump=fixture.QtInterfaceTests.pump

    def test_paired_browser_can_schedule_policy_during_initialization(self):
        from gametime.store import Store
        from gametime.qt_ui import App
        store=Store(self.base/'paired.sqlite3')
        try:
            store.save_settings(self.settings)
            with store.db:store.db.execute("INSERT INTO settings VALUES ('browser_pairing','fixture-token')")
            with patch('gametime.browser_activity.BrowserBridge') as bridge:
                paired=App(store,self.base/'paired',background=True,service=self.app.service,hub=self.app.hub)
                try:
                    paired.tick_timer.stop()
                    self.assertFalse(paired.closed);bridge.return_value.update.assert_called()
                finally:
                    paired.close();paired.deleteLater();self.pump(.03)
        finally:store.close()

    def test_automatic_exclusions_are_discoverable_restorable_and_durable(self):
        path=r'C:\Downloads\Editor-Setup.exe';now=datetime.now().astimezone()
        for second in range(3):self.app.focus.tick(Sample(now+timedelta(seconds=second),second,path,'fixture:1'))
        self.app.focus.flush()
        self.assertTrue(automatic_exclusion(path));self.assertNotEqual(app_identity(path),app_identity('Editor.exe'))
        self.assertEqual(self.app.focus.usage(now.date()),[])
        self.app.open_activities('app');listing=self.app.activity_lists['app'];self.assertEqual(listing.list.count(),0)
        listing.show_excluded.setChecked(True);self.assertEqual(listing.list.count(),1)
        listing.toggle_tracking();self.assertFalse(self.app.focus.settings.app_excluded(path))
        for second in range(3,5):self.app.focus.tick(Sample(now+timedelta(seconds=second),second,path,'fixture:1'))
        self.app.focus.flush();before=self.store.db.execute('SELECT sum(seconds) FROM activity_usage').fetchone()[0]
        self.assertGreater(before,0)
        self.app.focus.set_app_tracking(path,False);self.assertEqual(self.app.focus.history('0001-01-01','9999-12-31','apps'),[])
        self.app.focus.set_app_tracking(path,True);self.assertEqual(sum(r[4] for r in self.app.focus.history('0001-01-01','9999-12-31','apps')),before)
        self.assertTrue(all(not automatic_exclusion(name) for name in ('editor.exe','Steam.exe','SetupDesigner.exe','GameLauncher.exe','UpdaterStudio.exe','cmd.exe')))

    def test_lightweight_poll_reuses_published_snapshot_but_manual_sync_refreshes(self):
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True,statistics_sync_group='e'*32)
        with patch.object(self.app.statistics_sync,'request',return_value=True),patch.object(self.app.statistics_data,'snapshot',wraps=self.app.statistics_data.snapshot) as create:
            self.app.request_statistics_sync();self.assertEqual(create.call_count,1)
            self.app._sync_busy=False;self.app.statistics_data._sync_not_before=0
            self.app.request_statistics_sync(refresh=False);self.assertEqual(create.call_count,1)
            self.app._sync_busy=False;self.app.statistics_data._sync_not_before=0
            self.app.request_statistics_sync();self.assertEqual(create.call_count,2)

    def test_remote_focus_state_tracks_start_pause_and_stop_without_remote_local_credit(self):
        self.app.focus.start(100)
        running=snapshot(self.store,self.app.focus)['focus_state'];self.assertTrue(running['running']);self.assertTrue(running['active'])
        self.app.focus.pause(110)
        paused=snapshot(self.store,self.app.focus)['focus_state'];self.assertFalse(paused['running']);self.assertTrue(paused['active']);self.assertLess(paused['remaining'],running['remaining'])
        self.app.focus.stop();self.assertFalse(snapshot(self.store,self.app.focus)['focus_state']['active'])
        self.app.focus.remaining=0
        self.assertFalse(snapshot(self.store,self.app.focus)['focus_state']['active'])
        self.assertEqual(self.store.totals(datetime.now().date()),{})
