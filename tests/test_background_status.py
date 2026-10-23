"""Temporary background failures are logged; only persistent problems reach UI."""
import os
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gametime.background import BackgroundFailures, DISCOVERY_PROBLEM, HUB_PROBLEM
from gametime.hub import HubWorker
from gametime.model import Settings
from gametime.service import DiscoveryService

if os.name == 'nt':
    import test_qt_ui as fixtures


class BackgroundStatusTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.clock = patch('gametime.background.time.monotonic', side_effect=lambda: self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.discovery = SimpleNamespace(settings=Settings(), libraries=[], hints=[], errors=[],
            ubisoft_game_roots=[], riot_hints=[], scan_launchers=Mock(return_value=[]),
            scan_games=Mock(return_value=[]), watch_specs=Mock(return_value={}),
            registry_watch_specs=Mock(return_value=[]))
        self.service = DiscoveryService(Settings(), discovery=self.discovery, watcher_factory=Mock())

    def results(self):
        rows = []
        while not self.service.results.empty(): rows.append(self.service.results.get_nowait())
        return rows

    def test_partial_manifest_is_logged_and_retried_without_visible_status(self):
        self.discovery.errors = ['C:/fixture/private/appmanifest_123.acf']
        with self.assertLogs('gametime.service', level='WARNING') as logs:
            self.service._scan('launchers')
        self.assertIn(self.discovery.errors[0], '\n'.join(logs.output))
        self.assertEqual([r[0] for r in self.results()], ['launchers'])
        self.assertEqual(self.service.debounce.jobs[('launchers', '')][1], 2)
        self.now = 2; self.discovery.errors = []; self.service._scan('launchers')
        self.assertEqual([r[0] for r in self.results()], ['launchers'])
        self.assertFalse(self.service.problems.failures)
        self.assertFalse(self.service.debounce.jobs)

    def test_persistent_metadata_notifies_once_and_recovery_clears_it(self):
        self.discovery.errors = ['C:/fixture/private/metadata']
        with self.assertLogs('gametime.service'):
            for self.now in (0, 2, 6, 14, 30, 60, 90):
                self.service.debounce.ready(self.now); self.service._scan('launchers')
        notices = [r for r in self.results() if r[0] == 'discovery_problem']
        self.assertEqual(notices, [('discovery_problem', True)])
        self.assertEqual(self.service.debounce.jobs, {})
        self.discovery.errors = []; self.service._scan('launchers')
        self.assertIn(('discovery_problem', False), self.results())

    def test_independent_operations_cannot_reset_each_others_failures(self):
        with self.assertLogs('gametime.service'):
            for self.now in (0, 30, 60):
                self.service._problem('watchers', ['access denied'])
                self.service._scan('launchers')
            self.service._problem(('games', ''), ['another failure'])
            self.now = 90; self.service._problem(('games', ''), ['another failure'])
            self.now = 120; self.service._problem(('games', ''), ['another failure'])
        self.service._problem('watchers', None)
        self.assertEqual([r for r in self.results() if r[0] == 'discovery_problem'], [('discovery_problem', True)])
        self.service._problem(('games', ''), None)
        self.assertEqual(self.results(), [('discovery_problem', False)])

    def test_failed_scan_retries_and_never_exposes_exception_details(self):
        self.discovery.scan_games.side_effect = OSError('C:/private/game: device not ready')
        with self.assertLogs('gametime.service'):
            for self.now in (0, 30, 60): self.service._scan('games')
        self.assertEqual(self.results(), [('discovery_problem', True)])
        self.assertIn(('games', ''), self.service.debounce.jobs)
        self.discovery.scan_games.side_effect = None; self.service._scan('games')
        self.assertIn(('discovery_problem', False), self.results())

    def test_event_storm_still_gets_a_persistence_confirmation(self):
        self.discovery.errors = ['partial metadata']
        with self.assertLogs('gametime.service'):
            for self.now in range(10):
                self.service.debounce.jobs.clear(); self.service._scan('launchers')
            self.assertFalse(self.service.problems.reported)
            self.assertEqual(self.service.debounce.jobs[('launchers', '')][1], 60)
            self.now = 60; self.service.debounce.ready(self.now); self.service._scan('launchers')
        self.assertIn(('discovery_problem', True), self.results())
        self.assertFalse(self.service.debounce.jobs)

    def test_successful_attempt_resets_persistence_clock(self):
        gate = BackgroundFailures()
        for self.now in (0, 30): gate.update('scan', True)
        self.now = 59; gate.update('scan', False)
        for self.now in (60, 90, 119): gate.update('scan', True)
        self.assertFalse(gate.reported)
        self.now = 120; gate.update('scan', True)
        self.assertEqual(gate.reported, {'scan'})

    def test_dead_and_registry_watchers_repair_without_resetting_failure_clock(self):
        key = ('C:/fixture', False, 'launchers'); spec = (1, 'fixture')
        self.discovery.watch_specs.return_value = {key: 'C:/fixture'}
        self.discovery.registry_watch_specs.return_value = [spec]
        def broken(*args): return SimpleNamespace(error='access denied', thread=Mock(is_alive=Mock(return_value=False)), close=Mock())
        self.service.factory = broken; self.service.registry_factory = broken
        with self.assertLogs('gametime.service'):
            for self.now in (0, 30, 60): self.service._watches()
        self.assertTrue(self.service._watch_retry)
        self.assertEqual(self.results(), [('discovery_problem', True)])
        for watcher in [self.service.watchers[key][0], self.service.registry_watchers[spec]]:
            watcher.error = None; watcher.thread.is_alive.return_value = True
        self.service._watches()
        self.assertEqual(self.results(), [('discovery_problem', False)])
        self.assertFalse(self.service._watch_retry)

    def test_watcher_constructor_exception_keeps_repair_pending(self):
        self.discovery.watch_specs.return_value = {('C:/fixture', False, 'launchers'): 'C:/fixture'}
        self.service.factory.side_effect = PermissionError('C:/private/access denied')
        with self.assertLogs('gametime.service'):
            for self.now in (0, 30, 60): self.service._watches()
        self.assertTrue(self.service._watch_retry)
        self.assertEqual(self.results(), [('discovery_problem', True)])
        self.discovery.watch_specs.return_value = {}; self.service._watches()
        self.assertEqual(self.results(), [('discovery_problem', False)])

    def test_full_games_refresh_recovers_a_previously_failed_single_group(self):
        self.discovery.scan_games.side_effect = OSError('offline fixture')
        with self.assertLogs('gametime.service'):
            for self.now in (0, 30, 60): self.service._scan('games', 'C:/fixture/group')
        self.assertEqual(self.results(), [('discovery_problem', True)])
        self.discovery.scan_games.side_effect = None; self.service._scan('games')
        self.assertIn(('discovery_problem', False), self.results())
        self.assertFalse(self.service.problems.failures); self.assertFalse(self.service.debounce.jobs)

    def run_hub(self, fail_count):
        worker = HubWorker.__new__(HubWorker)
        worker.condition = Mock(); worker.condition.__enter__ = Mock(); worker.condition.__exit__ = Mock()
        worker.pending = (Settings(), (), {}, {}); worker.first_request = 0; worker.due = 0
        worker.failures = 0; worker.problems = BackgroundFailures(); worker.closed = False; worker.results = Queue()
        calls = []
        def sync(*job):
            calls.append(self.now)
            if len(calls) <= fail_count:
                if len(calls) == 7: worker.closed = True
                raise OSError('C:/private/shortcut: sharing violation')
            worker.closed = True
            return {'enabled': False}
        worker.hub = SimpleNamespace(sync=sync)
        worker.condition.wait.side_effect = lambda seconds: setattr(self, 'now', self.now + seconds)
        with self.assertLogs('gametime.hub'): worker._run()
        return calls, list(worker.results.queue)

    def test_hub_transient_shortcut_error_stays_in_logs_and_recovers(self):
        calls, results = self.run_hub(1)
        self.assertEqual(calls, [0, 2]); self.assertFalse(results[0]['persistent'])
        self.assertEqual(results[1], {'enabled': False})

    def test_hub_persistent_problem_uses_bounded_backoff(self):
        calls, results = self.run_hub(7)
        self.assertEqual(calls, [0, 2, 6, 14, 30, 60, 90])
        self.assertEqual([r['persistent'] for r in results], [False] * 5 + [True, True])


@unittest.skipUnless(os.name == 'nt', 'Windows Qt required')
class BackgroundStatusQtTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name == 'nt' else classmethod(lambda cls: None)
    if os.name == 'nt':
        setUp = fixtures.QtInterfaceTests.setUp; tearDown = fixtures.QtInterfaceTests.tearDown; pump = fixtures.QtInterfaceTests.pump

    def test_friendly_notice_is_persistent_translatable_and_disappears_on_recovery(self):
        self.app.service.results.put(('discovery_problem', True)); self.app.drain_discovery()
        self.assertEqual(self.app.status_key, DISCOVERY_PROBLEM)
        self.assertIn('Néhány játék', self.app.status_label.text()); self.assertEqual(self.app._status_until, float('inf'))
        self.app.set_language('en'); self.assertEqual(self.app.status_label.text(), DISCOVERY_PROBLEM)
        self.app.service.results.put(('discovery_problem', False)); self.app.drain_discovery()
        self.assertEqual(self.app.status_key, ''); self.assertTrue(self.app.status_label.isHidden())

    def test_recovery_and_normal_discovery_preserve_a_user_action_message(self):
        self.app.background_problem('discovery', DISCOVERY_PROBLEM, True)
        self.app.set_status('Settings saved.')
        self.app.service.results.put(('launchers', [], [], [], [], [], []))
        self.app.service.results.put(('discovery_problem', False)); self.app.drain_discovery()
        self.assertEqual(self.app.status_key, 'Settings saved.')

    def test_one_recovered_operation_cannot_hide_another_persistent_problem(self):
        self.app.background_problem('discovery', DISCOVERY_PROBLEM, True)
        self.app.background_problem('hub', HUB_PROBLEM, True)
        self.app.background_problem('hub', HUB_PROBLEM, False)
        self.assertEqual(self.app.status_key, DISCOVERY_PROBLEM)
        self.app.background_problem('discovery', DISCOVERY_PROBLEM, False)
        self.assertTrue(self.app.status_label.isHidden())

    def test_hub_raw_error_never_reaches_label_and_success_clears_friendly_notice(self):
        self.app.set_status('Settings saved.')
        self.app.hub.results.put({'error': 'C:/private/shortcut: sharing violation', 'persistent': False})
        with self.assertLogs('gametime.controller'): self.app.sync_hub()
        self.assertEqual(self.app.status_key, 'Settings saved.')
        self.app.hub.results.put({'error': 'C:/private/shortcut: sharing violation', 'persistent': True})
        with self.assertLogs('gametime.controller'): self.app.sync_hub()
        self.assertEqual(self.app.status_key, HUB_PROBLEM)
        self.assertNotIn('private', self.app.status_label.text())
        self.app.hub.results.put({'enabled': True}); self.app.sync_hub()
        self.assertTrue(self.app.status_label.isHidden())

    def test_repeated_hub_failure_does_not_overwrite_newer_user_message(self):
        self.app.background_problem('hub', HUB_PROBLEM, True)
        self.app.set_status('Settings saved.')
        self.app.hub.results.put({'error': 'still unavailable', 'persistent': True})
        with self.assertLogs('gametime.controller'): self.app.sync_hub()
        self.assertEqual(self.app.status_key, 'Settings saved.')


if __name__ == '__main__': unittest.main()
