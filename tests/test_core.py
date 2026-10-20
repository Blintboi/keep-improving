from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gametime.discovery import Discovery, parse_vdf, preserve_unreadable
from gametime.model import Catalog, Game, Settings, norm, within
from gametime.service import Debouncer
from gametime.store import Store
from gametime.tracker import Sample, Tracker


def write(path, content=""):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def manifest(lib, app="10", name="Test Game", folder="TestGame"):
    root = Path(lib) / "steamapps" / "common" / folder
    root.mkdir(parents=True, exist_ok=True)
    text = f'"AppState" {{ "appid" "{app}" "name" "{name}" "installdir" "{folder}" "StateFlags" "4" }}'
    return write(Path(lib) / "steamapps" / f"appmanifest_{app}.acf", text), root


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.steam, self.epic, self.games = self.base / "Steam", self.base / "Manifests", self.base / "Games"
        self.settings = Settings(games_root=str(self.games))
        self.discovery = Discovery(self.settings, [str(self.steam)], [str(self.epic)], self.base / "LauncherInstalled.dat", ubisoft=False, riot=False)

    def test_vdf_escaping_nested_legacy_and_comments(self):
        data = parse_vdf('// hi\n"libraryfolders" {"0" {"path" "D:\\\\SteamLibrary"} "1" "E:\\\\Games"}')
        self.assertEqual(data["libraryfolders"]["0"]["path"], r"D:\SteamLibrary")
        self.assertEqual(data["libraryfolders"]["1"], r"E:\Games")

    def test_vdf_partial_rejected(self):
        for text in ['"AppState" {', '"x"', '}', '"x" { "a" }']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_vdf(text)

    def test_steam_game_detected_without_walking_game_files(self):
        _, root = manifest(self.steam)
        with patch("os.walk", side_effect=AssertionError("Do not walk Steam content")):
            games = self.discovery.scan_launchers()
        self.assertEqual([(g.id, g.name, Path(g.root)) for g in games], [("steam:10", "Test Game", root)])

    def test_multiple_steam_libraries_and_modern_config(self):
        second, third = self.base / "DriveD", self.base / "DriveE"
        manifest(self.steam, "10")
        manifest(second, "20")
        manifest(third, "30")
        path2, path3 = str(second).replace("\\", "\\\\"), str(third).replace("\\", "\\\\")
        write(self.steam / "config" / "libraryfolders.vdf",
              f'"libraryfolders" {{ "1" {{"path" "{path2}"}} "2" "{path3}" }}')
        self.assertEqual({g.id for g in self.discovery.scan_launchers()}, {"steam:10", "steam:20", "steam:30"})

    def test_move_and_uninstall(self):
        file, _ = manifest(self.steam)
        self.discovery.scan_launchers()
        manifest(self.steam, folder="Moved")
        self.assertEqual(Path(self.discovery.scan_launchers()[0].root).name, "Moved")
        file.unlink()
        self.assertEqual(self.discovery.scan_launchers(), [])

    def test_manifest_transient_write_keeps_previous_record(self):
        file, _ = manifest(self.steam)
        self.discovery.scan_launchers()
        write(file, '"AppState" {')
        self.assertEqual(self.discovery.scan_launchers()[0].id, "steam:10")
        self.assertTrue(self.discovery.errors)

    def test_epic_multiple_drives_and_item_files(self):
        for index in (1, 2):
            root = self.base / f"Drive{index}" / "Game"
            root.mkdir(parents=True)
            write(self.epic / f"{index}.item", json.dumps({"AppName": f"app{index}", "DisplayName": f"Game {index}", "InstallLocation": str(root)}))
        result = self.discovery.scan_launchers()
        self.assertEqual({g.id for g in result}, {"epic:app1", "epic:app2"})
        (self.epic / "1.item").unlink()
        self.assertEqual([g.id for g in self.discovery.scan_launchers()], ["epic:app2"])

    def test_epic_launcher_index_fallback(self):
        root = self.base / "NewEpic"
        root.mkdir()
        write(self.discovery.launcher_dat, json.dumps({"InstallationList": [{"AppName": "new", "InstallLocation": str(root)}]}))
        result = self.discovery.scan_launchers()
        self.assertEqual(result[0].id, "epic:new")
        self.assertEqual(self.discovery.hints, result)

    def test_partial_epic_item_retries_without_losing_record(self):
        root = self.base / "EpicGame"
        root.mkdir()
        file = write(self.epic / "a.item", json.dumps({"AppName": "a", "InstallLocation": str(root)}))
        self.discovery.scan_launchers()
        write(file, '{"AppName":')
        self.assertEqual(self.discovery.scan_launchers()[0].id, "epic:a")
        self.assertTrue(self.discovery.errors)

    def test_games_nested_exes_are_one_game_and_helpers_skipped(self):
        write(self.games / "A" / "bin" / "A.exe")
        write(self.games / "A" / "bin" / "Renderer.exe")
        write(self.games / "B" / "setup.exe")
        write(self.games / "B" / "unins000.exe")
        result = self.discovery.scan_games()
        self.assertEqual([g.name for g in result], ["A"])

    def test_games_targeted_update_does_not_scan_siblings(self):
        write(self.games / "A" / "A.exe")
        write(self.games / "B" / "B.exe")
        with patch.object(self.discovery, "_has_exe", wraps=self.discovery._has_exe) as walk:
            result = self.discovery.scan_games(self.games / "B")
        self.assertEqual([g.name for g in result], ["B"])
        self.assertEqual(walk.call_count, 1)
        self.assertEqual(walk.call_args.args[0], self.games / "B")

    def test_games_root_exes_grouped(self):
        write(self.games / "A.exe")
        write(self.games / "B.exe")
        self.assertEqual(len(self.discovery.scan_games()), 1)

    def test_install_while_stopped_detected_on_next_start(self):
        self.assertEqual(self.discovery.scan_launchers(), [])
        manifest(self.steam)
        replacement = Discovery(self.settings, [str(self.steam)], [], self.base / "no-launcher.dat", ubisoft=False, riot=False)
        self.assertEqual(replacement.scan_launchers()[0].id, "steam:10")

    def test_watch_specs_missing_games_ancestor_is_nonrecursive(self):
        self.settings.games_root = str(self.base / "not-created" / "Games")
        specs = self.discovery.watch_specs()
        self.assertIn((str(self.base), False, "games"), specs)

    def test_unreadable_metadata_at_restart_preserves_saved_game(self):
        file, root = manifest(self.steam)
        saved = self.discovery.scan_launchers()[0]
        write(file, '"AppState" {')
        fresh = Discovery(self.settings, [str(self.steam)], [], self.base / "none.dat", ubisoft=False, riot=False)
        games = fresh.scan_launchers()
        self.assertEqual(preserve_unreadable(games, [saved], fresh.errors), [saved])

    def test_manifest_removal_does_not_preserve_old_record(self):
        file, _ = manifest(self.steam)
        saved = self.discovery.scan_launchers()[0]
        file.unlink()
        result = self.discovery.scan_launchers()
        self.assertEqual(preserve_unreadable(result, [saved], self.discovery.errors), [])

    def test_shared_watch_ancestor_preserves_all_missing_targets(self):
        roots = [str(self.base / "SteamA"), str(self.base / "SteamB")]
        discovery = Discovery(self.settings, roots, [], self.base / "none.dat", ubisoft=False, riot=False)
        targets = discovery.watch_specs()[(str(self.base), False, "launchers")]
        self.assertTrue(any(within(t, roots[0]) for t in targets))
        self.assertTrue(any(within(t, roots[1]) for t in targets))

    def test_wrong_vdf_structure_is_safe(self):
        write(self.steam / "config" / "libraryfolders.vdf", '"libraryfolders" "incomplete"')
        write(self.steam / "steamapps" / "appmanifest_10.acf", '"AppState" "incomplete"')
        self.assertEqual(self.discovery.scan_launchers(), [])
        self.assertEqual(len(self.discovery.errors), 2)

    def test_wrong_epic_index_structure_is_safe(self):
        write(self.discovery.launcher_dat, '[1,2,3]')
        self.assertEqual(self.discovery.scan_launchers(), [])
        self.assertIn(str(self.discovery.launcher_dat), self.discovery.errors)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.game = Game("steam:1", "Some Game", "Steam", r"D:\SteamLibrary\steamapps\common\SomeGame")
        self.catalog = Catalog(Settings(), [self.game])

    def test_full_path_not_process_basename(self):
        self.assertEqual(self.catalog.resolve(self.game.root + r"\bin\game.exe"), self.game)
        self.assertIsNone(self.catalog.resolve(r"C:\Other\game.exe"))

    def test_child_game_executable_in_nested_directory(self):
        self.assertEqual(self.catalog.resolve(self.game.root + r"\engine\binaries\win64\game-child.exe"), self.game)

    def test_path_prefix_boundary(self):
        self.assertFalse(within(r"C:\GamesBackup\a.exe", r"C:\Games"))
        self.assertTrue(within(r"c:\GAMES\A\a.exe", r"C:\Games"))

    def test_browsers_and_clients_always_excluded_even_if_mapped(self):
        for exe in ("steam.exe", "SteamWebHelper.exe", "EpicGamesLauncher.exe", "chrome.exe", "msedge.exe", "firefox.exe"):
            path = self.game.root + "\\" + exe
            self.catalog.rules[norm(path)] = self.game.id
            self.assertIsNone(self.catalog.resolve(path))

    def test_helpers_excluded_and_explicit_mapping_can_correct(self):
        path = self.game.root + r"\real-game-launcher.exe"
        self.assertIsNone(self.catalog.resolve(path))
        self.catalog.rules[norm(path)] = self.game.id
        self.assertEqual(self.catalog.resolve(path), self.game)

    def test_chess_counts_unless_user_excludes_it(self):
        game = Game("games:chess", "Chess Ultra", "Games", r"C:\Games\ChessUltra")
        self.catalog.games[game.id] = game
        for executable in ('game.exe','chess.exe','stockfish.exe','lc0.exe','fritz.exe','houdini.exe','komodo.exe'):
            path = game.root + '\\' + executable
            self.assertEqual(self.catalog.resolve(path), game)
            self.assertFalse(self.catalog.explicitly_ignored(path))
        self.catalog.overrides[game.id] = False
        self.assertIsNone(self.catalog.resolve(game.root + r"\chess.exe"))
        self.assertTrue(self.catalog.explicitly_ignored(game.root + r"\chess.exe"))
        self.catalog.overrides[game.id] = True
        self.assertEqual(self.catalog.resolve(game.root + r"\chess.exe"), game)

    def test_exact_exclusion(self):
        path = self.game.root + r"\game.exe"
        self.catalog.rules[norm(path)] = None
        self.assertIsNone(self.catalog.resolve(path))

    def test_disabled_game_applies_to_mapped_executable(self):
        path = r"C:\Other\game.exe"
        self.catalog.rules[norm(path)] = self.game.id
        self.catalog.overrides[self.game.id] = False
        self.assertIsNone(self.catalog.resolve(path))

    def test_manual_game_only_matches_exact_mapped_exe(self):
        manual = Game("manual:1", "Manual", "Kézi", r"C:\Tools")
        self.catalog.games[manual.id] = manual
        self.catalog.rules[norm(r"C:\Tools\one.exe")] = manual.id
        self.assertEqual(self.catalog.resolve(r"C:\Tools\one.exe"), manual)
        self.assertIsNone(self.catalog.resolve(r"C:\Tools\other.exe"))

    def test_new_steam_first_launch_before_manifest_processed(self):
        self.catalog.steam_libraries = [r"E:\SteamLibrary"]
        game = self.catalog.resolve(r"E:\SteamLibrary\steamapps\common\BrandNew\bin\game.exe")
        self.assertEqual(game.source, "Steam")
        self.assertTrue(game.id.startswith("pending:"))

    def test_new_games_first_launch_no_catalog_entry(self):
        game = self.catalog.resolve(r"C:\Games\BrandNew\bin\game.exe")
        self.assertEqual(game.source, "Games")
        self.assertEqual(norm(game.root), norm(r"C:\Games\BrandNew"))

    def test_games_root_record_does_not_swallow_new_nested_game(self):
        root = Game("root", "Games root", "Games", r"C:\Games")
        self.catalog.games[root.id] = root
        found = self.catalog.resolve(r"C:\Games\BrandNew\bin\game.exe")
        self.assertEqual(norm(found.root), norm(r"C:\Games\BrandNew"))


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(lambda: self.store.close())
        self.a = Game("steam:1", "Game A", "Steam", r"D:\Steam\A")
        self.b = Game("epic:2", "Game B", "Epic", r"E:\Epic\B")
        self.catalog = Catalog(Settings(), [self.a, self.b])
        self.tracker = Tracker(self.store, self.catalog)
        self.start = datetime(2026, 10, 15, 14, 0, tzinfo=timezone(timedelta(hours=2)))
        self.day = self.start.date().isoformat()

    def sample(self, sec, game=None, identity="pid:created", wall=None, active=True):
        path = game.root + r"\game.exe" if isinstance(game, Game) else game or ""
        self.tracker.tick(Sample(wall or self.start + timedelta(seconds=sec), sec, path, identity, active))

    def total(self, day=None):
        return sum(self.tracker.totals(day or self.day).values())

    def acknowledge(self):
        result = list(self.tracker.alerts)
        self.tracker.alerts.clear()
        for alert in result:
            self.tracker.delivered(alert)
        return result

    def test_active_game_counts_without_any_input_events_controller(self):
        for sec in range(31):
            self.sample(sec, self.a)
        self.assertAlmostEqual(self.total(), 30)

    def test_alt_tab_stops_and_background_does_not_count(self):
        self.sample(0, self.a)
        self.sample(1, self.a)
        self.sample(2, r"C:\Windows\notepad.exe")
        for sec in range(3, 12):
            self.sample(sec, r"C:\Windows\notepad.exe")
        self.assertAlmostEqual(self.total(), 2)

    def test_two_games_use_one_shared_budget_not_double(self):
        for sec in range(41):
            self.sample(sec, self.a if sec < 20 else self.b)
        self.assertAlmostEqual(self.total(), 40)
        self.assertAlmostEqual(self.tracker.totals(self.day)[self.a.id], 20)
        self.assertAlmostEqual(self.tracker.totals(self.day)[self.b.id], 20)

    def test_sleep_gap_excluded_even_with_unbiased_counter(self):
        self.sample(0, self.a)
        self.sample(1, self.a)
        self.sample(2, self.a, wall=self.start + timedelta(hours=1))
        self.sample(3, self.a, wall=self.start + timedelta(hours=1, seconds=1))
        self.assertAlmostEqual(self.total(), 2)

    def test_long_sampling_stall_not_charged(self):
        self.sample(0, self.a)
        self.sample(20, self.a)
        self.assertEqual(self.total(), 0)

    def test_clock_moves_back_not_charged(self):
        self.sample(0, self.a)
        self.sample(1, self.a, wall=self.start - timedelta(hours=1))
        self.assertEqual(self.total(), 0)

    def test_secure_desktop_and_lock_pause(self):
        self.sample(0, self.a)
        self.sample(1, self.a, active=False)
        self.sample(2, self.a, active=False)
        self.sample(3, self.a)
        self.sample(4, self.a)
        self.assertEqual(self.total(), 1)

    def test_midnight_split_local_date_and_new_budget(self):
        before = datetime(2026, 10, 15, 23, 59, 59, 500000, tzinfo=timezone(timedelta(hours=2)))
        self.sample(0, self.a, wall=before)
        self.sample(1, self.a, wall=before + timedelta(seconds=1))
        self.assertAlmostEqual(self.total("2026-10-15"), .5)
        self.assertAlmostEqual(self.total("2026-10-16"), .5)

    def test_restart_keeps_totals_and_does_not_count_offline_gap(self):
        for sec in range(6):
            self.sample(sec, self.a)
        self.tracker.close()
        replacement = Tracker(self.store, self.catalog)
        replacement.tick(Sample(self.start + timedelta(hours=2), 7200, self.a.root + r"\game.exe", "new"))
        self.assertEqual(sum(replacement.totals(self.day).values()), 5)

    def test_checkpoints_at_ten_seconds_without_writing_each_second(self):
        for sec in range(10):
            self.sample(sec, self.a)
        self.assertEqual(self.store.totals(self.day), {})
        self.sample(10, self.a)
        self.assertEqual(self.store.totals(self.day)[self.a.id], 10)

    def test_new_game_simultaneous_install_and_first_launch(self):
        self.catalog.steam_libraries = [r"F:\SteamLibrary"]
        path = r"F:\SteamLibrary\steamapps\common\New\bin\game.exe"
        for sec in range(31):
            self.sample(sec, path)
        self.assertEqual(self.total(), 30)
        real = Game("steam:99", "New Game", "Steam", r"F:\SteamLibrary\steamapps\common\New")
        self.tracker.reconcile([real], lambda g: g.source == "Steam")
        self.assertEqual(self.tracker.totals(self.day), {real.id: 30})

    def test_late_epic_metadata_backfills_only_observed_foreground(self):
        path = r"F:\NewEpic\game.exe"
        for sec in range(11):
            self.sample(sec, path)
        self.sample(11, r"C:\Windows\notepad.exe")
        self.sample(12, r"C:\Windows\notepad.exe")
        self.assertEqual(self.total(), 0)
        game = Game("epic:new", "New Epic", "Epic", r"F:\NewEpic")
        self.tracker.reconcile([game], lambda g: g.source == "Epic")
        self.assertEqual(self.total(), 11)
        self.assertEqual(len(self.tracker.unclassified), 1)

    def test_old_unidentified_intervals_expire(self):
        for sec in range(151):
            self.sample(sec, r"F:\Unknown\game.exe")
        game = Game("epic:new", "New Epic", "Epic", r"F:\Unknown")
        self.tracker.reconcile([game], lambda g: g.source == "Epic")
        self.assertLessEqual(self.total(), 121)

    def test_manually_excluded_chess_does_not_count_or_backfill(self):
        chess = Game("chess", "Chess Ultra", "Games", r"C:\Games\Chess")
        self.catalog.games[chess.id] = chess
        self.catalog.overrides[chess.id] = False
        for sec in range(11):
            self.sample(sec, chess)
        self.assertEqual(self.total(), 0)
        self.assertFalse(self.tracker.unclassified)

    def test_threshold_warning_and_limit_exact_text(self):
        self.store.add_usage({(self.day, self.a.id): 5999})
        self.sample(0, self.a)
        self.sample(1, self.a)
        warnings = self.acknowledge()
        self.assertEqual([a.text for a in warnings], ["You have 20 minutes of game time left today."])
        self.store.add_usage({(self.day, self.a.id): 1199})
        self.tracker.cache.clear()
        self.sample(2, self.a)
        limits = self.acknowledge()
        self.assertEqual([a.text for a in limits], ["Your daily 2-hour game time limit has been reached. Time to finish playing."])
        self.sample(3, self.a)
        self.assertFalse(self.tracker.alerts)

    def test_warning_once_persists_across_restart(self):
        self.store.add_usage({(self.day, self.a.id): 6000})
        self.sample(0, self.a)
        self.assertEqual(len(self.acknowledge()), 1)
        self.tracker = Tracker(self.store, self.catalog)
        self.sample(1, self.a)
        self.assertFalse(self.tracker.alerts)

    def test_numerically_unchanged_threshold_does_not_repeat(self):
        self.store.add_usage({(self.day, self.a.id): 6000})
        self.sample(0, self.a)
        self.acknowledge()
        self.catalog.settings.warning_seconds = 6000.0
        self.catalog.settings.limit_seconds = 7200.0
        self.sample(1, self.a)
        self.assertFalse(self.tracker.alerts)

    def test_over_limit_new_process_warns_once_but_alt_tab_does_not(self):
        self.store.add_usage({(self.day, self.a.id): 7200})
        self.sample(0, self.a, "100:created")
        self.assertEqual(self.acknowledge()[0].kind, "limit")
        self.sample(1, "")
        self.sample(2, self.a, "100:created")
        self.assertFalse(self.tracker.alerts)
        self.sample(3, self.a, "101:created")
        self.assertEqual(self.acknowledge()[0].kind, "session")
        self.sample(4, self.a, "101:created")
        self.assertFalse(self.tracker.alerts)

    def test_process_id_reuse_with_new_creation_time_rearms(self):
        self.store.add_usage({(self.day, self.a.id): 7200})
        self.sample(0, self.a, "100:one")
        self.acknowledge()
        self.sample(1, self.a, "100:two")
        self.assertEqual(self.acknowledge()[0].kind, "session")

    def test_exclusion_and_mapping_persist_database_reopen(self):
        self.store.set_enabled(self.a.id, False)
        self.store.set_rule(r"C:\Chess\chess.exe", None)
        self.store.set_rule(r"C:\Other\child.exe", self.b.id)
        self.store.close()
        self.store = Store(self.path)
        self.assertFalse(self.store.overrides()[self.a.id])
        self.assertIsNone(self.store.rules()[norm(r"C:\Chess\chess.exe")])
        self.assertEqual(self.store.rules()[norm(r"C:\Other\child.exe")], self.b.id)


class UtilityTests(unittest.TestCase):
    def test_event_debounce_has_quiet_period_and_maximum(self):
        events = Debouncer()
        for t in range(5):
            events.add(("games", "A"), t)
            self.assertEqual(events.ready(t), [])
        self.assertEqual(events.ready(5), [("games", "A")])

    def test_settings_reject_invalid_thresholds_and_root(self):
        for warning, limit in [(120, 100), (0, 120), (1, float("nan")), (100, 90000)]:
            with self.assertRaises(ValueError):
                Settings(warning_seconds=warning, limit_seconds=limit).validate()
        with self.assertRaises(ValueError):
            Settings(games_root="relative").validate()


if __name__ == "__main__":
    unittest.main()
