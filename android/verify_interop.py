"""Synthetic cross-runtime fixtures; never reads or contacts a user's profile/service."""
from pathlib import Path
import argparse
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gametime.statistics_cloud import keys, seal, unseal
from gametime.statistics_sync import validate_snapshot
from gametime.statistics_sync import StatisticsData
from gametime.store import Store

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--build-dir', type=Path, default=ROOT / 'android/app/build')
    args = parser.parse_args()
    if args.generate:
        code = '1' * 32
        snapshot = dict(format='GameTimeMonitor.statistics.v1', group=code,
                        device='a' * 32, name='Kísérleti számítógép', started='2026-11-01',
                        revision=1793700000000000001,
                        rows=[['2026-11-03', 'steam:fixture', 'Próbajáték', 'Steam', 600]],
                        activity_started='2026-11-01',
                        activity=[['2026-11-03', 'app', r'c:\apps\brave.exe', 'Brave', 1200],
                                  ['2026-11-03', 'site', 'example.test', 'example.test', 1500]])
        entry = dict(device=snapshot['device'], revision=str(snapshot['revision']), payload=seal(snapshot, code))
        target = ROOT / 'android/app/src/test/resources/interop.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(code=code, authorization=keys(code)[1], entry=entry)), encoding='utf-8')
        print('Generated synthetic desktop fixture')
    else:
        value=json.loads((args.build_dir/'sessions-phone-export.json').read_text(encoding='utf-8'))
        snapshot=unseal(value['entry'],value['code']);validate_snapshot(snapshot,value['code'])
        assert sum(row[3] for row in snapshot['sessions']['rows'])==2
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'sessions.sqlite3')
            try:
                data=StatisticsData(store);assert data.ingest(snapshot,value['code'])
                assert data.session_data(value['code'])[snapshot['device']]==snapshot['sessions']
                assert data.snapshot(value['code'],'Desktop')['sessions']['rows']==[]
            finally:store.close()
        print('Encrypted Android session counts imported without echoing remote counts')
        value = json.loads((args.build_dir / 'interop-export.json').read_text(encoding='utf-8'))
        snapshot = unseal(value['entry'], value['code'])
        validate_snapshot(snapshot, value['code'])
        assert snapshot['name'] == 'Android próba'
        print('Desktop accepted the Android-encrypted snapshot; exact 64-bit revision and Unicode preserved')
        value = json.loads((args.build_dir / 'phone-export.json').read_text(encoding='utf-8'))
        phone = unseal(value['entry'], value['code'])
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'desktop.sqlite3')
            try:
                statistics = StatisticsData(store)
                assert statistics.ingest(phone, value['code'])
                assert not statistics.ingest(phone, value['code'])
                rows = statistics.activity_history_by_computer('0001-01-01', '9999-12-31', value['code'], 'all', 'all')
                assert sum(row[4] for row in rows) == 3600
                assert statistics.snapshot(value['code'], 'PC')['rows'] == []
            finally:
                store.close()
        print('Desktop imported the real Android phone store exactly once; imported history was not re-exported')
        value=json.loads((args.build_dir/'shared-phone-export.json').read_text(encoding='utf-8'))
        phone=unseal(value['entry'],value['code'])
        from dataclasses import replace
        from gametime import device_sharing
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'shared.sqlite3')
            try:
                store.save_settings(replace(store.settings(),statistics_sync_enabled=True,statistics_sync_group=value['code']))
                data=StatisticsData(store);assert data.ingest(phone,value['code']);assert not data.ingest(phone,value['code'])
                device_sharing.apply(store)
                assert len(store.settings().wellbeing_rules)==1
                assert len(store.settings().device_groups)==1
                assert phone['scoped_rules']['usage'][0][3]==300
                assert data.snapshot(value['code'],'PC')['scoped_rules']['usage']==[]
            finally:store.close()
        print('Desktop accepted Android shared rules and groups; remote usage was not echoed or duplicated')

if __name__ == '__main__':
    main()
