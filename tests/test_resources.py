"""Resource scheduling must not stop tracking or leave stale UI on return."""
from dataclasses import replace
from datetime import datetime,timedelta
import os
from queue import Queue
import unittest
from unittest.mock import patch

import test_qt_ui as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class ResourceInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__)
    setUp=fixtures.QtInterfaceTests.setUp
    tearDown=fixtures.QtInterfaceTests.tearDown
    pump=fixtures.QtInterfaceTests.pump

    def test_hidden_ticks_keep_accounting_without_library_queries_and_restore_immediately(self):
        from gametime.tracker import Sample
        start=datetime.now().astimezone()
        with patch.object(self.store,'games',wraps=self.store.games) as games, \
             patch.object(self.store,'hidden_ids',wraps=self.store.hidden_ids) as hidden, \
             patch.object(self.app,'render',wraps=self.app.render) as render:
            for second in range(4):
                current=Sample(start+timedelta(seconds=second),100+second,str(self.exe),'fixture:1')
                with patch('gametime.controller.win32.sample',return_value=current): self.app.tick()
            games.assert_not_called(); hidden.assert_not_called(); render.assert_not_called()
            self.assertEqual(sum(self.app.tracker.totals(start.date()).values()),3)
            self.assertIn('00:00:03',self.app.tray.data.szTip)
        self.app.show(); self.pump(.02)
        self.assertEqual(self.app.total_label.text(),'00:00:03')
        self.assertEqual(self.app.cards[self.games[0].id].seconds,3)

    def test_minimized_ticks_defer_library_and_statistics_until_restored(self):
        self.app.show(); self.app.switch_page(1); self.app.showMinimized(); self.pump(.03)
        self.assertTrue(self.app.isMinimized())
        with patch.object(self.app,'render',wraps=self.app.render) as render, \
             patch.object(self.app.statistics,'refresh',wraps=self.app.statistics.refresh) as stats:
            self.app.statistics.last_refresh=0; self.app.render_tick(); self.app.render_tick()
            render.assert_not_called(); stats.assert_not_called()
            day=datetime.now().date().isoformat(); self.store.add_usage({(day,self.games[0].id):120})
            self.app.tracker.cache.clear(); self.app.showNormal(); self.pump(.03)
            self.assertTrue(render.called); self.assertTrue(stats.called)
            self.assertEqual(self.app.statistics.report.total,120)
            self.assertEqual(self.app.total_label.text(),'00:02:00')

    def test_workers_poll_fast_only_while_pending_and_sync_still_runs_hidden(self):
        self.app.art.pending.clear(); self.app.poll_assets()
        self.assertEqual(self.app.assets_timer.interval(),1000)
        for field in ('_clients_busy','_sync_busy'):
            setattr(self.app,field,True); self.app.update_assets_interval()
            self.assertEqual(self.app.assets_timer.interval(),100)
            setattr(self.app,field,False)
        self.app.art.pending['fixture']=1; self.app.update_assets_interval()
        self.assertEqual(self.app.assets_timer.interval(),100)
        self.app.art.pending.clear()
        self.app.settings=replace(self.app.settings,statistics_sync_enabled=True)
        self.app._sync_attempted=0
        with patch.object(self.app,'request_statistics_sync') as sync:
            self.app.poll_assets(); sync.assert_called_once()
        self.assertEqual(self.app.assets_timer.interval(),1000)

    def test_hidden_launcher_page_does_not_rescan_and_rescans_on_return(self):
        self.app.pages.setCurrentIndex(3); self.app._clients_refreshed=0
        self.app.client_worker=type('Worker',(),{'results':Queue(),'close':lambda me:None})()
        with patch.object(self.app,'refresh_clients') as refresh:
            self.app.poll_assets(); refresh.assert_not_called()
            self.app.show(); self.app.poll_assets(); refresh.assert_called_once()

    def test_overlay_has_no_fast_idle_polling_but_keeps_live_guard(self):
        from gametime.tracker import Sample
        with patch('gametime.qt_ui.win32.sample') as sample:
            self.app.update_overlay(); sample.assert_not_called()
            self.assertFalse(self.app.overlay_timer.isActive())
            self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_enabled=True)
            self.app.update_overlay(); sample.assert_not_called()
            self.assertFalse(self.app.overlay_timer.isActive())
        current=Sample(datetime.now().astimezone(),100,str(self.exe),'fixture:1')
        self.app.tracker.tick(current)
        with patch('gametime.qt_ui.win32.sample',return_value=current), \
             patch('gametime.qt_ui.foreground_screen_name',return_value=''):
            self.app.update_overlay()
        self.assertTrue(self.app.overlay_timer.isActive()); self.assertEqual(self.app.overlay_timer.interval(),200)
        self.app.tracker.tick(replace(current,path='',identity='',awake=101))
        with patch('gametime.qt_ui.win32.sample') as sample:
            self.app.update_overlay(); sample.assert_not_called()
        self.assertFalse(self.app.overlay_timer.isActive()); self.assertFalse(self.app.overlay.isVisible())

    def test_unchanged_tray_tooltip_does_not_write_to_windows(self):
        from gametime import win32
        with patch.object(win32.s,'Shell_NotifyIconW',return_value=True) as native:
            self.app.tray.update('Fixture tip'); self.app.tray.update('Fixture tip')
            self.assertEqual(native.call_count,1)
            self.app.tray.update('Fixture changed'); self.assertEqual(native.call_count,2)

    def test_explicit_shutdown_signals_once_while_window_close_only_hides(self):
        from PySide6.QtTest import QSignalSpy
        from PySide6.QtWidgets import QMainWindow
        signal=QSignalSpy(self.app.shutdown)
        self.app.show(); QMainWindow.close(self.app); self.assertEqual(signal.count(),0)
        self.app.close(); self.app.close(); self.assertEqual(signal.count(),1)

    def test_failed_tray_update_retries_before_caching_the_tip(self):
        from gametime import win32
        with patch.object(win32.s,'Shell_NotifyIconW',side_effect=[False,True]) as native:
            self.app.tray.update('Fixture transient failure'); self.app.tray.update('Fixture transient failure')
            self.app.tray.update('Fixture transient failure'); self.assertEqual(native.call_count,2)
