"""Multiple isolated profiles exchange statistics without changing local tracking."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from gametime.model import Game, Settings
from gametime.statistics import summarize
from gametime.statistics_sync import StatisticsData, SyncWorker, validate_snapshot, group_code
from gametime.store import Store

GROUP = '012345abcdef'
OTHER = 'fedcba543210'
DAY = date.today().isoformat()


class StatisticsSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.shared = self.base/'shared'; self.shared.mkdir()
        self.stores = []; self.data = []
        for name in ('A', 'B', 'C'):
            store = Store(self.base/(name+'.sqlite3')); self.addCleanup(store.close)
            store.upsert([Game('steam:42', 'Example', 'Steam', 'C:/Games/Example')])
            self.stores.append(store); self.data.append(StatisticsData(store))
        self.worker = SyncWorker(); self.addCleanup(self.worker.close)

    def snapshot(self, index, group=GROUP):
        return self.data[index].snapshot(group, 'Computer '+str(index))

    def exchange(self, index, group=GROUP):
        values, warning = self.worker.exchange((str(self.shared), group, 0), self.snapshot(index, group))
        self.assertFalse(warning)
        for value in values: self.data[index].ingest(value, group)

    def total(self, index, scope='all', group=GROUP):
        return summarize(self.data[index].history(DAY, DAY, group, scope), DAY, DAY).total

    def test_two_computers_converge_and_repeated_sync_never_adds_imports_to_exports(self):
        self.stores[0].add_usage({(DAY, 'steam:42'): 60})
        self.stores[1].add_usage({(DAY, 'steam:42'): 120})
        for _ in range(3):
            self.exchange(0); self.exchange(1)
        self.assertEqual((self.total(0), self.total(1)), (180, 180))
        self.assertEqual(self.stores[0].totals(DAY), {'steam:42': 60})
        self.assertEqual(self.stores[1].totals(DAY), {'steam:42': 120})
        self.assertEqual(sum(row[4] for row in self.snapshot(0)['rows']), 60)
        self.assertEqual(self.total(0, 'local'), 60)
        self.assertEqual(self.total(0, self.data[1].device_id()), 120)
        self.stores[1].add_usage({(DAY, 'steam:42'): 30})
        self.exchange(1); self.exchange(0)
        self.assertEqual(self.total(0), 210)

    def test_same_parent_folder_keeps_different_users_groups_separate(self):
        self.stores[0].add_usage({(DAY, 'steam:42'): 60}); self.exchange(0)
        self.stores[1].add_usage({(DAY, 'steam:42'): 120}); self.exchange(1, OTHER)
        self.assertEqual(self.total(0), 60); self.assertEqual(self.total(1, group=OTHER), 120)
        self.assertFalse(self.data[0].devices(GROUP)); self.assertFalse(self.data[1].devices(OTHER))
        with self.assertRaises(ValueError): self.data[0].ingest(self.snapshot(1, OTHER), GROUP)

    def test_history_keeps_device_origins_filters_groups_and_updates_names(self):
        self.stores[0].add_usage({(DAY,'steam:42'):60}); self.stores[1].add_usage({(DAY,'steam:42'):120})
        snapshot=self.snapshot(1); self.data[0].ingest(snapshot,GROUP)
        self.stores[2].add_usage({(DAY,'steam:42'):300}); self.data[0].ingest(self.snapshot(2,OTHER),OTHER)
        rows=self.data[0].history_by_computer(DAY,DAY,GROUP,local_name='My desktop')
        self.assertEqual({row[5]:(row[4],row[6]) for row in rows},{'local':(60,'My desktop'),snapshot['device']:(120,'Computer 1')})
        self.assertEqual(sum(row[4] for row in rows),self.total(0))
        self.assertEqual([row[5] for row in self.data[0].history_by_computer(DAY,DAY,GROUP,'local')],['local'])
        self.assertEqual([row[5] for row in self.data[0].history_by_computer(DAY,DAY,GROUP,snapshot['device'])],[snapshot['device']])
        self.assertFalse(self.data[0].history_by_computer('2000-01-01','2000-01-02',GROUP))
        renamed=self.data[1].snapshot(GROUP,'Renamed laptop'); self.data[0].ingest(renamed,GROUP)
        self.assertEqual(self.data[0].history_by_computer(DAY,DAY,GROUP,snapshot['device'])[0][6],'Renamed laptop')
        self.assertEqual(self.stores[0].totals(DAY),{'steam:42':60})

    def test_full_snapshots_replace_old_data_and_reject_out_of_order_versions(self):
        self.stores[1].add_usage({(DAY, 'steam:42'): 40}); old = self.snapshot(1)
        self.assertTrue(self.data[0].ingest(old, GROUP))
        self.stores[1].add_usage({(DAY, 'steam:42'): 20}); new = self.snapshot(1)
        self.assertTrue(self.data[0].ingest(new, GROUP))
        self.assertFalse(self.data[0].ingest(old, GROUP)); self.assertFalse(self.data[0].ingest(new, GROUP))
        self.assertEqual(self.total(0), 60)
        self.assertFalse(self.data[0].ingest(self.snapshot(0), GROUP))

    def test_manual_games_match_by_title_and_source_without_exporting_paths(self):
        for i in (0, 1):
            game = Game('manual:'+uuid.uuid4().hex, 'My  Game' if i else 'MY GAME', 'Kézi', str(self.base/str(i)))
            self.stores[i].upsert([game]); self.stores[i].add_usage({(DAY, game.id): 60})
        self.exchange(0); self.exchange(1)
        report = summarize(self.data[1].history(DAY, DAY, GROUP), DAY, DAY)
        self.assertEqual(len(report.games), 1); self.assertEqual(report.total, 120)
        text = json.dumps(self.snapshot(1))
        self.assertNotIn('C:/Games', text); self.assertNotIn(str(self.base), text)
        self.assertNotIn('rules', text); self.assertNotIn('settings', text)

    def test_game_id_migration_does_not_duplicate_remote_history(self):
        old = Game('manual:old', 'Example', 'Kézi', 'C:/Games/Example')
        self.stores[1].upsert([old]); self.stores[1].add_usage({(DAY, old.id): 60})
        self.data[0].ingest(self.snapshot(1), GROUP)
        with self.stores[1].db: self.stores[1]._merge(old.id, 'steam:42')
        self.data[0].ingest(self.snapshot(1), GROUP)
        self.assertEqual(self.total(0), 60)
        self.assertEqual(len(self.data[0].history(DAY, DAY, GROUP)), 1)

    def test_invalid_partial_files_keep_last_good_cache_and_other_files(self):
        self.stores[1].add_usage({(DAY, 'steam:42'): 60}); self.exchange(1); self.exchange(0)
        path = self.shared/'GameTimeMonitor-statistics'/GROUP/(self.data[1].device_id()+'.json')
        path.write_text('{partial', encoding='utf-8')
        sentinel = path.parent/'user-note.txt'; sentinel.write_text('preserve')
        values, warning = self.worker.exchange((str(self.shared), GROUP, 0), self.snapshot(0))
        self.assertTrue(warning); self.assertFalse(values); self.assertEqual(self.total(0), 60)
        self.assertEqual(sentinel.read_text(), 'preserve')
        with self.assertRaises(OSError): self.worker.exchange((str(self.base/'offline'), GROUP, 0), self.snapshot(0))

    def test_invalid_snapshots_are_atomic_and_bounded(self):
        self.stores[1].add_usage({(DAY, 'steam:42'): 60}); good = self.snapshot(1)
        self.data[0].ingest(good, GROUP)
        changes = [{'rows': [[DAY, 'x', 'X', 'Steam', float('nan')]]}, {'rows': [[DAY, 'x', 'X', 'Steam', -1]]},
                   {'rows': [[DAY, 'x', 'X', 'Steam', True]]}, {'rows': [['bad-date', 'x', 'X', 'Steam', 1]]},
                   {'rows': good['rows']*2}, {'device': '../escape'}, {'revision': True}, {'name': 'X'*81}]
        for fields in changes:
            with self.subTest(fields=fields), self.assertRaises(ValueError): self.data[0].ingest({**good, **fields}, GROUP)
        self.assertEqual(self.total(0), 60)

    def test_averages_use_selected_computers_start_and_cache_survives_reopen(self):
        with self.stores[1].db: self.stores[1].db.execute("UPDATE settings SET value='2026-10-01' WHERE key='tracking_started_on'")
        self.stores[1].add_usage({(DAY, 'steam:42'): 60}); self.data[0].ingest(self.snapshot(1), GROUP)
        self.assertEqual(self.data[0].started_on(GROUP), '2026-10-01')
        self.assertEqual(self.data[0].started_on(GROUP, 'local'), self.stores[0].tracking_started_on())
        reader = Store(self.stores[0].path)
        try: self.assertEqual(StatisticsData(reader).devices(GROUP), self.data[0].devices(GROUP))
        finally: reader.close()

    def test_sync_settings_are_opt_in_and_group_codes_cannot_be_paths(self):
        self.assertFalse(Settings().statistics_sync_enabled)
        self.assertEqual(group_code('0123-45AB-CDEF'), GROUP)
        for fields in ({'statistics_sync_enabled': True}, {'statistics_sync_group': '../escape'},
                       {'statistics_sync_enabled': 'yes'}, {'statistics_device_name': 'X'*81}):
            with self.subTest(fields=fields), self.assertRaises(ValueError): replace(Settings(), **fields).validate()

    def test_background_exchange_discards_a_cancelled_group_before_delivering_results(self):
        entered=threading.Event(); release=threading.Event(); threads=[]
        original=self.worker.exchange
        def exchange(token,snapshot):
            threads.append(threading.get_ident()); entered.set(); release.wait(2)
            return original(token,snapshot)
        self.worker.exchange=exchange
        self.worker.request(str(self.shared),GROUP,self.snapshot(0))
        self.assertTrue(entered.wait(2)); self.worker.cancel()
        self.worker.request(str(self.shared),OTHER,self.snapshot(0,OTHER)); release.set()
        token,values,warning=self.worker.results.get(timeout=3)
        self.assertEqual(token,(str(self.shared),OTHER,1)); self.assertFalse(warning)
        self.assertTrue(all(identity!=threading.get_ident() for identity in threads))
