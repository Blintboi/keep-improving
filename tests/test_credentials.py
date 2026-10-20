"""Credential protection and lossless migration using isolated Windows profiles."""
from dataclasses import asdict, replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gametime.model import Settings, Game
from gametime.secrets import PREFIX, protect, unprotect
from gametime.statistics_sync import StatisticsData, local_group
from gametime.store import Store

CODE='0123456789abcdef0123456789abcdef'

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'profile.sqlite3'
        self.store=Store(self.path); self.addCleanup(self.store.close)

    def test_windows_user_roundtrip_and_tamper_rejection(self):
        protected=protect(CODE)
        self.assertTrue(protected.startswith(PREFIX)); self.assertNotIn(CODE,protected)
        self.assertEqual(unprotect(protected),CODE)
        self.assertNotEqual(protected,protect(CODE))
        for invalid in (CODE,PREFIX+'broken',protected[:-8]+'AAAAAAAA'):
            with self.subTest(invalid=invalid[:12]), self.assertRaises((ValueError,OSError)): unprotect(invalid)

    def test_settings_save_reuses_ciphertext_and_preserves_every_other_setting(self):
        settings=replace(Settings(),statistics_sync_enabled=True,statistics_sync_group=CODE,limit_seconds=9100)
        self.store.save_settings(settings)
        first=self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0]
        self.assertNotIn(CODE,first); self.assertEqual(self.store.settings(),settings)
        self.store.save_settings(settings)
        self.assertEqual(self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0],first)

    def test_foreign_windows_account_disables_sync_without_discarding_credential(self):
        settings=replace(Settings(),statistics_sync_enabled=True,statistics_sync_group=CODE)
        self.store.save_settings(settings)
        saved=json.loads(self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
        with patch('gametime.store.unprotect',side_effect=OSError('different Windows user')):
            loaded=self.store.settings()
            self.assertFalse(loaded.statistics_sync_enabled); self.assertFalse(loaded.statistics_sync_group)
            self.assertTrue(self.store.credentials_unavailable)
            self.store.save_settings(replace(loaded,limit_seconds=12300))
        current=json.loads(self.store.db.execute("SELECT value FROM settings WHERE key='config'").fetchone()[0])
        self.assertEqual(current['statistics_sync_group'],saved['statistics_sync_group'])
        self.assertEqual(current['limit_seconds'],12300)
        self.store.save_settings(replace(loaded,statistics_sync_group=CODE,statistics_sync_enabled=True))
        self.assertFalse(self.store.credentials_unavailable); self.assertEqual(self.store.settings().statistics_sync_group,CODE)

    def test_legacy_migration_removes_secret_from_active_database_without_losing_cache(self):
        settings=replace(Settings(),statistics_sync_enabled=True,statistics_sync_group=CODE)
        with self.store.db:
            self.store.db.execute("INSERT INTO settings VALUES ('config',?)",(json.dumps(asdict(settings)),))
        data=StatisticsData(self.store); day=date.today().isoformat(); identity='a'*32
        self.store.upsert([Game('steam:42','Example','Steam','C:/Example')])
        self.store.add_usage({(day,'steam:42'):37})
        snapshot=data.snapshot(CODE,'Own PC')
        # Recreate the old plain routing labels and snapshot cache key.
        with self.store.db:
            self.store.db.execute('INSERT INTO statistics_devices (group_id,device_id,name,started,revision) VALUES (?,?,?,?,?)',(CODE,identity,'Other PC',day,99))
            self.store.db.execute('INSERT INTO statistics_remote VALUES (?,?,?,?,?,?,?)',(CODE,identity,day,'steam:42','Example','Steam',120))
            self.store.db.execute('UPDATE settings SET key=? WHERE key=?',('statistics_snapshot:'+CODE,'statistics_snapshot:'+local_group(CODE)))
        self.assertEqual(self.store.settings(),settings)
        migrated=StatisticsData(self.store)
        self.assertEqual(migrated.revisions(CODE),{identity:'99'})
        self.assertEqual(migrated.devices(CODE),[(identity,'Other PC',day)])
        self.assertEqual(sum(row[4] for row in migrated.history(day,day,CODE)),157)
        self.assertEqual(self.store.totals(day),{'steam:42':37})
        self.assertEqual(migrated.snapshot(CODE,'Own PC'),snapshot)
        for suffix in ('','-wal'):
            path=Path(str(self.path)+suffix)
            if path.exists(): self.assertNotIn(CODE.encode(),path.read_bytes())

    def test_snapshot_only_legacy_profile_also_checkpoints_the_secret_key(self):
        self.store.save_settings(replace(Settings(),statistics_sync_group=CODE))
        data=StatisticsData(self.store); snapshot=data.snapshot(CODE,'Own PC')
        with self.store.db:
            self.store.db.execute('UPDATE settings SET key=? WHERE key=?',('statistics_snapshot:'+CODE,'statistics_snapshot:'+local_group(CODE)))
        data=StatisticsData(self.store)
        self.assertEqual(data.snapshot(CODE,'Own PC'),snapshot)
        for suffix in ('','-wal'):
            path=Path(str(self.path)+suffix)
            if path.exists(): self.assertNotIn(CODE.encode(),path.read_bytes())

    def test_mixed_old_and_new_cache_keeps_only_the_newest_complete_device(self):
        StatisticsData(self.store); label=local_group(CODE); day=date.today().isoformat()
        with self.store.db:
            for identity,old,new in (('a'*32,10,11),('b'*32,11,10)):
                for group,revision,seconds in ((CODE,old,10),(label,new,20)):
                    self.store.db.execute('INSERT INTO statistics_devices (group_id,device_id,name,started,revision) VALUES (?,?,?,?,?)',(group,identity,str(revision),day,revision))
                    self.store.db.execute('INSERT INTO statistics_remote VALUES (?,?,?,?,?,?,?)',(group,identity,day,'steam:42','Example','Steam',seconds))
            self.store.db.execute('INSERT INTO settings VALUES (?,?)',('statistics_snapshot:'+CODE,json.dumps({'revision':10,'digest':'old'})))
            self.store.db.execute('INSERT INTO settings VALUES (?,?)',('statistics_snapshot:'+label,json.dumps({'revision':11,'digest':'new'})))
        data=StatisticsData(self.store)
        self.assertEqual(data.revisions(CODE),{'a'*32:'11','b'*32:'11'})
        self.assertEqual(sum(row[4] for row in data.history(day,day,CODE)),30)
        state=self.store.db.execute('SELECT value FROM settings WHERE key=?',('statistics_snapshot:'+label,)).fetchone()[0]
        self.assertEqual(json.loads(state),{'revision':11,'digest':'new'})
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM statistics_remote WHERE group_id=?',(CODE,)).fetchone()[0],0)
