"""Encrypted HTTP exchange between isolated profiles; no real cloud/user data."""
import base64
from dataclasses import asdict, replace
from copy import deepcopy
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

from gametime.model import Game, Settings
from gametime.statistics_cloud import (CLOUD_FORMAT, CloudSyncWorker, keys, new_code,
                                       seal, unseal, associated_data)
from gametime.statistics_sync import StatisticsData
from gametime.store import Store

CODE = '0123456789abcdef0123456789abcdef'
OTHER = 'fedcba9876543210fedcba9876543210'
DAY = date.today().isoformat()


class Relay:
    """Protocol fixture, not a replacement for testing the Supabase SQL/RLS."""
    def __init__(self):
        self.rows = {}; self.requests = []; self.policies=[]; self.status = 200; self.corrupt = False; self.retry_after=None
        relay = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                authorization = self.headers['Authorization']
                relay.requests.append((self.path, authorization, body))
                relay.policies.append(self.headers.get('X-GameTime-Sync'))
                if self.path == '/redirect':
                    self.send_response(302); self.send_header('Location', relay.url+'/target'); self.end_headers(); return
                rows = relay.rows.setdefault(authorization, {})
                device = body['device']; current = rows.get(device)
                if body['payload'] is not None and (current is None or int(body['revision']) > int(current['revision'])):
                    rows[device] = {k: body[k] for k in ('device', 'revision', 'payload')}
                result = dict(format=CLOUD_FORMAT, need_upload=device not in rows,
                              snapshots=[deepcopy(value) for key, value in rows.items()
                                         if key != device and body['known'].get(key) != value['revision']])
                if relay.corrupt and result['snapshots']:
                    result['snapshots'][0]['payload'] = 'broken'
                raw = json.dumps(result).encode()
                self.send_response(relay.status); self.send_header('Content-Type', 'application/json')
                if relay.retry_after is not None: self.send_header('Retry-After',relay.retry_after)
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)


class StatisticsCloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.stores = []; self.data = []
        for name in ('A', 'B', 'C'):
            store = Store(Path(self.tmp.name)/(name+'.sqlite3')); self.addCleanup(store.close)
            store.upsert([Game('steam:42', 'Example', 'Steam', 'C:/Games/Example')])
            self.stores.append(store); self.data.append(StatisticsData(store))
        self.relay = Relay(); self.addCleanup(self.relay.close)
        self.worker = CloudSyncWorker(allow_local_http=True); self.addCleanup(self.worker.close)

    def snapshot(self, index=0, code=CODE):
        return self.data[index].snapshot(code, 'Computer '+str(index))

    def exchange(self, index, code=CODE):
        values, warning = self.worker.exchange((self.relay.url, code, 0),
            (self.snapshot(index, code), self.data[index].revisions(code)))
        self.assertFalse(warning)
        for value in values: self.data[index].ingest(value, code)

    def total(self, index, code=CODE):
        return sum(row[4] for row in self.data[index].history(DAY, DAY, code))

    def test_generated_codes_and_key_separation(self):
        generated = {new_code() for _ in range(100)}
        self.assertEqual(len(generated), 100)
        self.assertTrue(all(len(value) == 32 for value in generated))
        encryption, authorization = keys(CODE)
        self.assertNotEqual(encryption.hex(), authorization)
        self.assertNotIn(CODE, authorization)
        for bad in ('1234', 'x'*32, '../escape', None):
            with self.assertRaises(ValueError): keys(bad)

    def test_protocol_upgrade_keeps_encryption_and_sends_event_policy(self):
        self.exchange(0)
        self.assertEqual(self.relay.policies,['event-driven-v2'])
        self.assertEqual(self.relay.requests[0][2]['format'],'GameTimeMonitor.sync.v2')
        self.relay.status=426; self.relay.retry_after='86400'
        self.worker.request(self.relay.url,CODE,self.snapshot(),{})
        token,values,warning=self.worker.results.get(timeout=3)
        self.assertFalse(values)
        self.assertIn('Update Game Time Monitor',warning)
        self.assertGreater(self.worker.retry_delay(self.relay.url,CODE),86399)

    def test_folder_upgrade_preserves_local_and_cached_history_without_exposing_short_code(self):
        store=self.stores[0]; old='012345abcdef'
        self.stores[1].add_usage({(DAY,'steam:42'):120})
        self.data[0].ingest(self.data[1].snapshot(old,'Old computer'),old)
        config={**asdict(Settings()),'statistics_sync_enabled':True,
                'statistics_sync_folder':'C:/OldSharedFolder','statistics_sync_group':old}
        with store.db: store.db.execute("INSERT OR REPLACE INTO settings VALUES ('config',?)",(json.dumps(config),))
        settings=store.settings(); self.assertFalse(settings.statistics_sync_enabled)
        self.assertEqual(settings.statistics_sync_group,old); self.assertEqual(self.total(0,old),120)
        store.save_settings(settings)
        self.assertNotIn('statistics_sync_folder',asdict(store.settings()))
        with self.assertRaises(ValueError): replace(settings,statistics_sync_enabled=True).validate()
        self.assertTrue(replace(settings,statistics_sync_enabled=True,statistics_sync_group=CODE).validate())

    def test_encryption_hides_fields_and_authenticates_payload_identity_revision_and_code(self):
        self.stores[0].add_usage({(DAY, 'steam:42'): 60})
        snapshot = self.snapshot(); payload = seal(snapshot, CODE)
        entry = dict(device=snapshot['device'], revision=str(snapshot['revision']), payload=payload)
        self.assertEqual(unseal(entry, CODE), snapshot)
        self.assertNotEqual(payload, seal(snapshot, CODE))
        for text in (b'Example', b'Computer 0', CODE.encode(), b'C:/Games'):
            self.assertNotIn(text, base64.b64decode(payload))
        for changes, code in (({}, OTHER), ({'device': 'a'*32}, CODE),
                              ({'revision': str(snapshot['revision']+1)}, CODE),
                              ({'payload': payload[:-4]+'AAAA'}, CODE)):
            with self.subTest(changes=changes), self.assertRaises(ValueError): unseal({**entry, **changes}, code)

    def test_decompression_is_bounded_before_json_parsing(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = b'0'*12; device = 'a'*32; version = '1'
        encrypted = b'GTM1'+nonce+AESGCM(keys(CODE)[0]).encrypt(nonce, zlib.compress(b'x'*2048), associated_data(device, version))
        with patch('gametime.statistics_cloud.MAX_BYTES', 1024), self.assertRaises(ValueError):
            unseal(dict(device=device, revision=version, payload=base64.b64encode(encrypted).decode()), CODE)

    def test_two_profiles_converge_without_merging_budgets_or_other_groups(self):
        self.stores[0].add_usage({(DAY, 'steam:42'): 60}); self.stores[1].add_usage({(DAY, 'steam:42'): 120})
        self.stores[2].add_usage({(DAY, 'steam:42'): 900})
        for _ in range(3):
            self.exchange(0); self.exchange(1); self.exchange(2, OTHER)
        self.assertEqual((self.total(0), self.total(1), self.total(2, OTHER)), (180, 180, 900))
        self.assertEqual(self.stores[0].totals(DAY), {'steam:42': 60})
        self.assertEqual(sum(row[4] for row in self.snapshot()['rows']), 60)
        self.assertFalse(self.data[2].devices(OTHER))
        for path, credential, body in self.relay.requests:
            self.assertNotIn(CODE, credential); self.assertNotIn(OTHER, credential)
            self.assertNotIn('Example', json.dumps(body)); self.assertNotIn('Computer', json.dumps(body))

    def test_unchanged_snapshots_are_not_reuploaded_and_missing_server_copy_is_repaired(self):
        self.exchange(0); first = len(self.relay.requests)
        self.exchange(0)
        self.assertIsNone(self.relay.requests[-1][2]['payload'])
        self.assertEqual(len(self.relay.requests), first+1)
        self.relay.rows.clear(); self.exchange(0)
        self.assertIsNone(self.relay.requests[-2][2]['payload'])
        self.assertIsNotNone(self.relay.requests[-1][2]['payload'])

    def test_offline_and_corrupt_responses_preserve_last_good_cache(self):
        self.stores[1].add_usage({(DAY, 'steam:42'): 120}); self.exchange(1); self.exchange(0)
        self.stores[1].add_usage({(DAY, 'steam:42'): 60}); self.exchange(1)
        self.relay.corrupt = True
        with self.assertRaises(ValueError): self.exchange(0)
        self.assertEqual(self.total(0), 120)
        self.relay.corrupt = False; self.relay.status = 503
        with self.assertRaises(OSError): self.exchange(0)
        self.assertEqual(self.total(0), 120)
        self.relay.status = 200; self.exchange(0); self.assertEqual(self.total(0), 180)

    def test_no_redirected_credential_and_no_cleartext_service_in_production(self):
        with self.assertRaises(OSError):
            self.worker.post(self.relay.url+'/redirect', keys(CODE)[1], dict(device='a'*32))
        self.assertEqual(len(self.relay.requests), 1)
        worker = CloudSyncWorker(); self.addCleanup(worker.close)
        for url in (self.relay.url, 'https://user:pass@example.com', 'https://example.com/?token=x', 'https://example.com/#x'):
            with self.assertRaises(ValueError): worker.post(url, keys(CODE)[1], {})

    def test_background_job_uses_cloud_failure_message_and_recovers(self):
        self.relay.status = 503
        self.worker.request(self.relay.url, CODE, self.snapshot(), {})
        token, values, warning = self.worker.results.get(timeout=3)
        self.assertEqual(warning, self.worker.failure_message); self.assertFalse(values)
        self.relay.status = 200
        self.worker.retries.clear()
        self.worker.request(self.relay.url, CODE, self.snapshot(), {})
        token, values, warning = self.worker.results.get(timeout=3)
        self.assertFalse(warning)

    def test_failed_background_requests_wait_and_success_resets_backoff(self):
        self.relay.status=429
        self.relay.retry_after='3600'
        self.worker.request(self.relay.url,CODE,self.snapshot(),{})
        self.worker.results.get(timeout=3)
        self.assertGreaterEqual(self.worker.retry_delay(self.relay.url,CODE),3599)
        count=len(self.relay.requests)
        self.assertFalse(self.worker.request(self.relay.url,CODE,self.snapshot(),{}))
        self.assertEqual(len(self.relay.requests),count)
        self.relay.status=200
        self.worker.exchange((self.relay.url,CODE,0),(self.snapshot(),{}))
        self.assertEqual(self.worker.retry_delay(self.relay.url,CODE),0)

    def test_unadmitted_code_is_explained_without_leaking_server_errors(self):
        self.relay.status=403
        self.worker.request(self.relay.url,CODE,self.snapshot(),{})
        token,values,warning=self.worker.results.get(timeout=3)
        self.assertFalse(values)
        self.assertEqual(warning,'Cloud sync is not enabled for this connection code. Local statistics are kept.')
        self.assertGreaterEqual(self.worker.retry_delay(self.relay.url,CODE),3599)
