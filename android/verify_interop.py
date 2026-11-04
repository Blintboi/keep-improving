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

if __name__ == '__main__':
    main()
