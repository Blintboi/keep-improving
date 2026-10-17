from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gametime.minecraft import scan, is_runtime
from gametime.model import Catalog, Game, Settings
from gametime.store import Store
from gametime.tracker import Tracker, Sample


class MinecraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / ".minecraft"
        (self.home / "versions").mkdir(parents=True)
        self.game = scan(self.home)[0]
        self.catalog = Catalog(Settings(), [self.game])
        self.runtime = r"C:\Program Files (x86)\Minecraft Launcher\runtime\brand-new-runtime\bin\javaw.exe"

    def test_detects_installed_java_edition_and_drops_missing_installation(self):
        self.assertEqual(self.game.id, "minecraft:java")
        self.assertEqual(scan(self.base / "missing"), [])

    def test_new_runtime_versions_are_recognized_without_fixed_exe_assignments(self):
        with patch("gametime.minecraft.runtime_roots", return_value=[r"C:\Program Files (x86)\Minecraft Launcher\runtime"]):
            self.assertEqual(self.catalog.resolve(self.runtime), self.game)
            self.assertEqual(self.catalog.resolve(self.runtime.replace("javaw.exe", "java.exe")), self.game)

    def test_generic_java_and_launcher_are_excluded(self):
        for path in (r"C:\Java\bin\javaw.exe", r"C:\Program Files (x86)\Minecraft Launcher\MinecraftLauncher.exe"):
            self.assertIsNone(self.catalog.resolve(path))

    def test_manual_exclusion_and_game_exclusion_still_win(self):
        from gametime.model import norm
        self.catalog.rules[norm(self.runtime)] = None
        self.assertIsNone(self.catalog.resolve(self.runtime))
        self.catalog.rules.clear()
        self.catalog.overrides[self.game.id] = False
        self.assertIsNone(self.catalog.resolve(self.runtime))
        self.assertTrue(self.catalog.explicitly_ignored(self.runtime))

    def test_manual_catalog_migrates_time_rules_and_exclusion(self):
        store = Store(self.base / "usage.sqlite3")
        self.addCleanup(store.close)
        manual = Game("manual:minecraft", self.game.name, "Kézi", str(self.home))
        store.upsert([manual])
        store.add_usage({("2000-01-01", manual.id): 123})
        store.set_rule(self.runtime, manual.id)
        store.set_enabled(manual.id, False)
        store.reconcile([self.game], lambda g: g.source == "Minecraft")
        self.assertEqual(store.totals("2000-01-01"), {self.game.id: 123})
        self.assertEqual(set(store.rules().values()), {self.game.id})
        self.assertFalse(store.overrides()[self.game.id])

    def test_foreground_runtime_counts_and_background_browser_does_not(self):
        store = Store(self.base / "usage.sqlite3")
        self.addCleanup(store.close)
        tracker = Tracker(store, self.catalog)
        now = datetime.now().astimezone()
        for second, path in enumerate([self.runtime] * 3 + [r"C:\Apps\brave.exe"] * 3):
            tracker.tick(Sample(now + timedelta(seconds=second), second, path, "fixture:1"))
        self.assertEqual(sum(tracker.totals(now.date()).values()), 3)

    def test_discovery_includes_minecraft_without_scanning_game_contents(self):
        from gametime.discovery import Discovery
        with patch("gametime.minecraft.scan", return_value=[self.game]):
            discovery = Discovery(Settings(), [], [], self.base / "none.dat", ubisoft=False, riot=False, minecraft=True)
            self.assertEqual(discovery.scan_launchers(), [self.game])
