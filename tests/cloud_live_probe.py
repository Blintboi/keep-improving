"""Opt-in end-to-end probe using synthetic profiles against a supplied service.

No real user profile is opened. The report contains only test-group hashes and
device identifiers, so an administrator can remove exactly these probe records.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from datetime import date
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gametime.model import Game
from gametime.statistics_cloud import CloudSyncWorker, keys, new_code
from gametime.statistics_sync import StatisticsData
from gametime.store import Store


def run(service):
    code, other = new_code(), new_code()
    report = dict(groups=[hashlib.sha256(keys(value)[1].encode()).hexdigest() for value in (code, other)],
                  devices=[], checks={})
    with tempfile.TemporaryDirectory() as root:
        stores, data = [], []
        worker = CloudSyncWorker()
        try:
            day = date.today().isoformat()
            for index, seconds in enumerate((60, 120, 900)):
                store = Store(Path(root)/(str(index)+'.sqlite3')); stores.append(store)
                store.upsert([Game('steam:42', 'Synthetic sync fixture', 'Steam', 'C:/Synthetic')])
                store.add_usage({(day, 'steam:42'): seconds})
                data.append(StatisticsData(store)); report['devices'].append(data[-1].device_id())
            def exchange(index, group=code):
                values, warning = worker.exchange((service, group, 0),
                    (data[index].snapshot(group, 'Synthetic computer '+str(index)), data[index].revisions(group)))
                assert not warning
                for value in values: data[index].ingest(value, group)
            def total(index, group=code):
                return sum(row[4] for row in data[index].history(day, day, group))
            exchange(0); exchange(1); exchange(0); exchange(2, other)
            assert total(0) == total(1) == 180
            assert total(2, other) == 900 and not data[2].devices(other)
            report['checks']['same_code_combines_and_other_code_isolated'] = True
            assert stores[0].totals(day) == {'steam:42': 60} and stores[1].totals(day) == {'steam:42': 120}
            assert sum(row[4] for row in data[0].snapshot(code, 'Synthetic computer 0')['rows']) == 60
            report['checks']['budgets_and_exports_stay_local'] = True
            old = data[1].snapshot(code, 'Synthetic computer 1')
            stores[1].add_usage({(day, 'steam:42'): 30}); exchange(1); exchange(0)
            assert total(0) == 210
            worker.exchange((service, code, 0), (old, {})); exchange(0)
            assert total(0) == 210
            report['checks']['new_data_replaces_and_stale_data_cannot_overwrite'] = True
            for _ in range(2): exchange(0); exchange(1)
            assert total(0) == total(1) == 210
            report['checks']['repeated_exchange_is_idempotent'] = True
            reader = Store(stores[0].path)
            try:
                assert sum(row[4] for row in StatisticsData(reader).history(day, day, code)) == 210
            finally: reader.close()
            report['checks']['downloaded_cache_survives_reopen'] = True
            try:
                with urlopen(Request(service, data=b'{}', headers={'Content-Type':'application/json',
                                      'Authorization':'Bearer 1234'}), timeout=15):
                    raise AssertionError('Weak credential accepted')
            except HTTPError as exc: assert exc.code == 401
            report['checks']['unauthenticated_requests_rejected'] = True
            report['success'] = True
        finally:
            worker.close()
            for store in stores: store.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--service', required=True); parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = run(args.service)
    destination = Path(args.report); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
