from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from gametime.focus import Focus, FocusSettings, domain
from gametime.store import Store
from gametime.tracker import Sample


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'usage.sqlite3'); self.addCleanup(self.store.close)
        self.focus = Focus(self.store)
        self.start = datetime(2026, 10, 26, 11, 0).astimezone()

    def tick(self, second, path=r'C:\Apps\work.exe', site='', **kwargs):
        self.focus.tick(Sample(self.start + timedelta(seconds=second), second, path, '10:123', **kwargs), site)

    def test_all_foreground_apps_without_game_catalog_or_game_budget_changes(self):
        self.tick(0); self.tick(1); self.tick(2, r'C:\Apps\other.exe'); self.tick(3, r'C:\Apps\other.exe')
        self.focus.flush()
        rows = {row[2]: row[3] for row in self.focus.usage(self.start.date())}
        self.assertEqual(rows, {'work.exe': 2, 'other.exe': 1})
        self.assertEqual(self.store.totals(self.start.date()), {})
        self.assertEqual(self.store.budget_totals(self.start.date()), {})
        self.assertEqual(self.store.games(), [])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM activity_items').fetchone()[0], 2)

    def test_websites_are_browser_breakdown_not_extra_application_time(self):
        self.tick(0, r'C:\Brave\brave.exe', 'example.com')
        self.tick(1, r'C:\Brave\brave.exe', 'docs.example.com')
        self.tick(2, r'C:\Brave\brave.exe', '')
        self.tick(3, r'C:\Brave\brave.exe', '')
        rows = self.focus.usage(self.start.date())
        self.assertEqual(sum(row[3] for row in rows if row[0] == 'app'), 3)
        self.assertEqual(sum(row[3] for row in rows if row[0] == 'site'), 2)

    def test_idle_lock_sleep_clock_jump_and_tracking_off_drop_intervals(self):
        self.tick(0); self.tick(1, idle_seconds=60); self.tick(2, interactive=False); self.tick(3)
        self.tick(30); self.tick(31)
        self.assertEqual(sum(row[3] for row in self.focus.usage(self.start.date())), 1)
        self.focus.configure(replace(self.focus.settings, tracking=False))
        self.tick(32); self.tick(33)
        self.assertEqual(sum(row[3] for row in self.focus.usage(self.start.date())), 1)
        self.focus.configure(replace(self.focus.settings, tracking=True))
        self.tick(34); self.tick(35)
        self.assertEqual(sum(row[3] for row in self.focus.usage(self.start.date())), 2)
        current = Sample(self.start + timedelta(hours=1), 36, r'C:\Apps\work.exe', '10:123')
        self.focus.tick(current)
        self.assertEqual(sum(row[3] for row in self.focus.usage(self.start.date())), 2)

    def test_midnight_conserves_activity_and_pending_survives_restart(self):
        self.start = self.start.replace(hour=23, minute=59, second=59, microsecond=500000)
        self.tick(0); self.tick(1); self.focus.close()
        restored = Focus(self.store)
        self.assertEqual(restored.usage(self.start.date())[0][3], .5)
        self.assertEqual(restored.usage((self.start + timedelta(days=1)).date())[0][3], .5)

    def test_timer_breaks_long_break_pause_resume_and_restart(self):
        f = self.focus
        f.configure(FocusSettings(work=1, short_break=1, long_break=2, rounds=2))
        f.start(0); f.advance(30); f.pause(30)
        self.assertEqual(f.remaining, 30); self.assertFalse(f.restricting)
        f.advance(100); self.assertEqual(f.remaining, 30)
        f.start(100); f.advance(130, self.start)
        self.assertEqual((f.phase, f.remaining, f.round), ('short_break', 60, 1))
        self.assertFalse(f.restricting)
        f.advance(190); self.assertFalse(f.running); self.assertEqual(f.phase, 'focus')
        f.start(190); f.advance(250, self.start)
        self.assertEqual((f.phase, f.remaining, f.round), ('long_break', 120, 2))
        restored = Focus(self.store)
        self.assertFalse(restored.running); self.assertEqual(restored.remaining, 120)
        self.assertEqual(self.store.db.execute('SELECT SUM(rounds) FROM focus_completions').fetchone()[0], 2)
        restored.stop(); self.assertEqual((restored.phase, restored.remaining, restored.round), ('focus', 60, 0))

    def test_blacklist_subdomains_and_exact_executable_identity(self):
        s = FocusSettings(block_apps=[r'C:\Work\editor.exe'], block_sites=['https://EXAMPLE.com/path?q=private']).validate()
        self.assertTrue(s.app_blocked(r'c:\WORK\editor.exe'))
        self.assertFalse(s.app_blocked(r'C:\Elsewhere\editor.exe'))
        self.assertFalse(s.app_blocked(r'C:\Windows\explorer.exe'))
        self.assertTrue(s.site_blocked('docs.example.com'))
        self.assertTrue(s.site_blocked('ads.example.com'))
        self.assertFalse(s.site_blocked('evil-example.com'))
        self.assertFalse(s.site_blocked('example.com.evil.com'))

    def test_retired_whitelist_is_ignored_without_losing_blacklist_or_preferences(self):
        config={'mode':'allowlist','allow_apps':[], 'allow_sites':['old.example.com'],
                'block_sites':['example.com'],'work':40,'tracking':False}
        with self.store.db: self.store.db.execute("INSERT OR REPLACE INTO settings VALUES ('focus_config',?)",(json.dumps(config),))
        restored=Focus(self.store)
        self.assertEqual(restored.settings.work,40)
        self.assertFalse(restored.settings.tracking)
        self.assertFalse(restored.settings.app_blocked(r'C:\Apps\work.exe'))
        self.assertTrue(restored.settings.site_blocked('example.com'))
        self.assertFalse(restored.settings.site_blocked('other.com'))
        self.assertEqual(restored.policy()['mode'],'blocklist')

    def test_domains_strip_paths_and_reject_private_or_non_web_values(self):
        self.assertEqual(domain('https://EXAMPLE.com/private?q=secret#fragment'), 'example.com')
        self.assertEqual(domain('*.példa.hu'), 'xn--plda-bpa.hu')
        for value in ('file:///secret', 'chrome://settings', 'localhost', '127.0.0.1',
                      'https://user:secret@example.com', 'app.local', 'bad host.com', 'https://[::1]'):
            with self.subTest(value=value), self.assertRaises(ValueError): domain(value)

    def test_invalid_rules_do_not_replace_saved_settings(self):
        f = self.focus
        f.configure(replace(f.settings, block_sites=['youtube.com']))
        with self.assertRaises(ValueError): f.configure(replace(f.settings, block_apps=['editor.exe']))
        self.assertEqual(Focus(self.store).settings.block_sites, ['youtube.com'])

    def test_activity_statistics_exclude_games_and_do_not_double_count_websites(self):
        from gametime.model import Game
        day=self.start.date().isoformat()
        self.store.upsert([Game('fixture:game','Game','Steam',r'C:\Game',installed=False)])
        items=[('app',r'c:\game\play.exe','play.exe',40),('app',r'c:\work\editor.exe','editor.exe',20),
               ('app',r'c:\brave\brave.exe','brave.exe',60),('site','example.com','example.com',35)]
        with self.store.db:
            for kind,key,name,seconds in items:
                self.store.db.execute('INSERT INTO activity_items VALUES (?,?,?)',(kind,key,name))
                self.store.db.execute('INSERT INTO activity_usage VALUES (?,?,?,?)',(day,kind,key,seconds))
        apps=self.focus.history(day,day,'apps'); websites=self.focus.history(day,day,'websites'); all_rows=self.focus.history(day,day,'all')
        self.assertEqual(sum(row[4] for row in apps),80)
        self.assertEqual(sum(row[4] for row in websites),35)
        self.assertEqual(sum(row[4] for row in all_rows),80)
        self.assertEqual(next(row[4] for row in all_rows if row[1]=='activity:browser:other'),25)
        self.assertFalse(any(row[2]=='play.exe' for row in apps))


@unittest.skipUnless(os.name == 'nt', 'Windows credential protection required')
class BrowserBridgeTests(unittest.TestCase):
    def setUp(self):
        FocusTests.setUp(self)
        from gametime.browser_activity import BrowserBridge
        self.bridge = BrowserBridge(self.store, port=0); self.addCleanup(self.bridge.close)

    def post(self, value=None, token=None, origin='chrome-extension://abcdefghijklmnop'):
        data = value or {'browser': 'brave', 'domain': 'example.com', 'focused': True, 'private': False}
        request = Request(f'http://127.0.0.1:{self.bridge.port}/activity', data=json.dumps(data).encode(),
                          headers={'Authorization': 'Bearer ' + (token if token is not None else self.bridge.token),
                                   'Content-Type': 'application/json', 'Origin': origin})
        return json.loads(urlopen(request, timeout=2).read())

    def test_bridge_requires_pairing_and_rejects_webpage_origins_and_full_urls(self):
        for token, origin in (('wrong', 'chrome-extension://abcdefghijklmnop'), (self.bridge.token, 'https://evil.example')):
            with self.assertRaises(HTTPError) as error: self.post(token=token, origin=origin)
            self.assertIn(error.exception.code, (401, 403))
        with self.assertRaises(HTTPError):
            self.post({'browser': 'brave', 'url': 'https://example.com/secret', 'focused': True, 'private': False})
        self.assertFalse(self.post()['active'])
        self.assertEqual(self.bridge.website(r'C:\Brave\brave.exe'), 'example.com')
        self.assertEqual(self.bridge.website(r'C:\Chrome\chrome.exe'), '')
        self.assertTrue(self.bridge.connected)
        saved = self.store.db.execute("SELECT value FROM settings WHERE key='browser_pairing'").fetchone()[0]
        self.assertNotIn(self.bridge.token, saved)

    def test_bridge_policy_expiry_background_browser_and_private_observations(self):
        self.post()
        self.post({'browser': 'edge', 'domain': '', 'focused': False, 'private': False})
        self.assertEqual(self.bridge.website(r'C:\Brave\brave.exe'), 'example.com')
        self.post({'browser': 'brave', 'domain': 'secret.example.com', 'focused': True, 'private': True})
        self.assertEqual(self.bridge.website(r'C:\Brave\brave.exe'), '')
        self.post()
        with patch('gametime.browser_activity.time.monotonic', return_value=self.bridge.observation['at'] + 21):
            self.assertEqual(self.bridge.website(r'C:\Brave\brave.exe'), '')
            self.assertFalse(self.bridge.connected)
        self.focus.start(0); self.bridge.update(self.focus.policy())
        self.assertTrue(self.post()['active'])
        self.focus.pause(1); self.bridge.update(self.focus.policy())
        self.assertFalse(self.post()['active'])
