"""Activity shares encrypted snapshots while each computer retains its own data."""
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path
import tempfile
import unittest

from gametime.focus import Focus
from gametime.model import Game
from gametime.statistics_cloud import seal, unseal
from gametime.statistics_sync import StatisticsData
from gametime.store import Store

GROUP = 'ab' * 16
DAY = date.today().isoformat()


class ActivitySyncTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.stores, self.focus, self.data = [], [], []
        for name in ('one', 'two'):
            store = Store(Path(tmp.name) / (name + '.db')); self.addCleanup(store.close)
            store.save_settings(replace(store.settings(), statistics_sync_enabled=True, statistics_sync_group=GROUP))
            store.upsert([Game('steam:42', 'Game', 'Steam', r'C:\game')])
            focus = Focus(store)
            self.stores.append(store); self.focus.append(focus); self.data.append(StatisticsData(store, focus))

    def add(self, index, kind, key, seconds):
        with self.stores[index].db:
            self.stores[index].db.execute('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)', (kind, key, key))
            self.stores[index].db.execute('INSERT INTO activity_usage VALUES (?,?,?,?)', (DAY, kind, key, seconds))

    def transfer(self, source=0, target=1):
        snapshot = self.data[source].snapshot(GROUP, 'Computer ' + str(source))
        encrypted = seal(snapshot, GROUP)
        self.assertNotIn('example.com', encrypted)
        entry = dict(device=snapshot['device'], revision=str(snapshot['revision']), payload=encrypted)
        self.data[target].ingest(unseal(entry, GROUP), GROUP)
        return snapshot

    def rows(self, index, category, scope='all', group=GROUP):
        return self.data[index].activity_history_by_computer(DAY, DAY, group, scope, category, 'Local')

    def test_sync_keeps_origins_filters_games_and_counts_browser_once_per_device(self):
        self.add(0, 'app', r'c:\game\play.exe', 50)
        self.add(0, 'app', r'c:\apps\editor.exe', 20)
        self.add(0, 'app', r'c:\brave\brave.exe', 60)
        self.add(0, 'site', 'example.com', 35)
        self.add(1, 'app', r'c:\chrome\chrome.exe', 30)
        self.add(1, 'site', 'other.example', 40)
        snapshot = self.transfer()
        self.assertEqual(sum(r[4] for r in self.rows(1, 'apps')), 110)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'websites')), 75)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'all')), 110)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'all', snapshot['device'])), 80)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'all', 'local')), 30)
        self.assertNotIn('play.exe', str(snapshot['activity']))
        self.assertFalse(self.rows(1, 'apps', snapshot['device'], 'cd' * 16))
        self.assertEqual(len(self.data[1].snapshot(GROUP, 'Other')['activity']), 2)
        self.assertEqual(self.stores[1].totals(DAY), {})

    def test_old_snapshots_keep_cache_invalid_data_cannot_replace_it(self):
        self.add(0, 'site', 'example.com', 35)
        snapshot = self.transfer()
        legacy = deepcopy(snapshot); legacy.pop('activity'); legacy.pop('activity_started'); legacy['revision'] += 1
        self.data[1].ingest(legacy, GROUP)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'websites')), 35)
        bad = deepcopy(snapshot); bad['revision'] += 2; bad['activity'][0][4] = -1
        with self.assertRaises(ValueError): self.data[1].ingest(bad, GROUP)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'websites')), 35)
        with self.assertRaises(ValueError):
            unseal(dict(device=snapshot['device'], revision=str(snapshot['revision']), payload=seal(snapshot, GROUP)), 'cd' * 16)

    def test_remote_exclusion_is_reversible_and_unchanged_snapshot_is_stable(self):
        path = r'c:\apps\editor.exe'; self.add(0, 'app', path, 20)
        snapshot = self.transfer()
        self.focus[1].configure(replace(self.focus[1].settings, excluded_apps=[path]))
        self.assertFalse(self.rows(1, 'apps'))
        self.focus[1].configure(replace(self.focus[1].settings, excluded_apps=[]))
        self.assertEqual(sum(r[4] for r in self.rows(1, 'apps')), 20)
        self.assertEqual(snapshot, self.data[0].snapshot(GROUP, 'Computer 0'))

    def test_disabled_sync_does_not_export_activity(self):
        self.add(0, 'site', 'example.com', 10)
        self.stores[0].save_settings(replace(self.stores[0].settings(), statistics_sync_enabled=False))
        self.assertNotIn('activity', self.data[0].snapshot(GROUP, 'Computer'))

    def test_existing_http_exchange_transfers_activity_without_extra_requests(self):
        from test_statistics_cloud import Relay
        from gametime.statistics_cloud import CloudSyncWorker
        relay = Relay(); self.addCleanup(relay.close)
        worker = CloudSyncWorker(allow_local_http=True); self.addCleanup(worker.close)
        self.add(0, 'site', 'example.com', 35)
        for source in (0, 1):
            snapshot = self.data[source].snapshot(GROUP, 'Computer ' + str(source))
            values, warning = worker.exchange((relay.url, GROUP, 0),
                                               (snapshot, self.data[source].revisions(GROUP)))
            self.assertFalse(warning)
            for value in values: self.data[source].ingest(value, GROUP)
        self.assertEqual(len(relay.requests), 2)
        self.assertEqual(sum(r[4] for r in self.rows(1, 'websites')), 35)
        self.assertNotIn('example.com', str(relay.requests))
        snapshot = self.data[0].snapshot(GROUP, 'Computer 0')
        worker.exchange((relay.url, GROUP, 0), (snapshot, self.data[0].revisions(GROUP)))
        self.assertIsNone(relay.requests[-1][2]['payload'])


if __name__ == '__main__': unittest.main()
