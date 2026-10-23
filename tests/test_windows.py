"""Real Win32 API/filesystem tests. Metadata fixtures are NOT real game installs."""
import json
import os
from pathlib import Path
from queue import Empty, Queue
import tempfile
import time
import unittest

from gametime.discovery import Discovery
from gametime.model import Settings
from gametime.service import DiscoveryService


@unittest.skipUnless(os.name == "nt", "Windows required")
class WindowsTests(unittest.TestCase):
    def setUp(self):
        from gametime import win32
        self.native = win32
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def await_result(self, service, predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = service.results.get(timeout=.2)
            except Empty:
                continue
            if predicate(result):
                return result
        self.fail("Expected filesystem discovery event did not arrive")

    def make_service(self):
        games = self.base / "Games"
        games.mkdir()
        steamapps = self.base / "Steam" / "steamapps"
        steamapps.mkdir(parents=True)
        epic = self.base / "Manifests"
        epic.mkdir()
        settings = Settings(games_root=str(games))
        discovery = Discovery(settings, [str(steamapps.parent)], [str(epic)], self.base / "LauncherInstalled.dat", platforms=False, ubisoft=False, riot=False)
        service = DiscoveryService(settings, discovery=discovery)
        self.addCleanup(service.close)
        service.start()
        self.await_result(service, lambda r: r[0] == "games")
        return service, games, steamapps, epic

    def test_native_process_path_creation_time_and_awake_clock(self):
        path, identity = self.native.process_image(os.getpid())
        self.assertTrue(Path(path).is_file())
        self.assertTrue(identity.startswith(str(os.getpid()) + ":"))
        before = self.native.awake_seconds()
        time.sleep(.03)
        self.assertGreaterEqual(self.native.awake_seconds(), before)

    def test_single_instance_mutex_and_release(self):
        first = self.native.Instance(self.base)
        second = self.native.Instance(self.base)
        self.assertTrue(first.acquired)
        self.assertFalse(second.acquired)
        first.close()
        second.close()
        third = self.native.Instance(self.base)
        self.assertTrue(third.acquired)
        third.close()

    def test_native_process_lookup_recognizes_own_full_path_and_missing_executable(self):
        executable,_=self.native.process_image(os.getpid())
        self.assertIs(self.native.process_running(executable),True)
        self.assertIs(self.native.process_running(str(self.base/'NonexistentUniqueFixture.exe')),False)

    def test_process_lookup_closes_snapshot_and_ignores_another_session(self):
        from unittest.mock import patch
        native=self.native
        def entry(handle,pointer): pointer._obj.pid=123; pointer._obj.executable='RTSS.exe'; return True
        def session(pid,pointer): pointer._obj.value=2 if pid==123 else 1; return True
        with patch.object(native.k,'CreateToolhelp32Snapshot',return_value=44),patch.object(native.k,'Process32FirstW',side_effect=entry),patch.object(native.k,'Process32NextW',return_value=False),patch.object(native.k,'ProcessIdToSessionId',side_effect=session),patch.object(native.C,'get_last_error',return_value=18),patch.object(native.k,'CloseHandle') as close,patch.object(native,'process_image') as inspect:
            self.assertIs(native.process_running('C:/fixture/RTSS.exe'),False)
            inspect.assert_not_called(); close.assert_called_once_with(44)

    def test_process_lookup_defers_on_denied_image_and_does_not_match_other_installation(self):
        from unittest.mock import patch
        native=self.native
        def entry(handle,pointer): pointer._obj.pid=123; pointer._obj.executable='RTSS.exe'; return True
        def session(pid,pointer): pointer._obj.value=1; return True
        for image,expected in ((('', ''),None),(('C:/other/RTSS.exe','123:1'),False)):
            with self.subTest(image=image),patch.object(native.k,'CreateToolhelp32Snapshot',return_value=44),patch.object(native.k,'Process32FirstW',side_effect=entry),patch.object(native.k,'Process32NextW',return_value=False),patch.object(native.k,'ProcessIdToSessionId',side_effect=session),patch.object(native.C,'get_last_error',return_value=18),patch.object(native.k,'CloseHandle') as close,patch.object(native,'process_image',return_value=image):
                self.assertIs(native.process_running('C:/fixture/RTSS.exe'),expected); close.assert_called_once_with(44)

    def test_native_directory_watch_reports_create_rename_remove(self):
        changes = Queue()
        watcher = self.native.DirectoryWatcher(self.base, True, changes.put)
        self.addCleanup(watcher.close)
        self.assertTrue(watcher.ready.wait(3))
        self.assertIsNone(watcher.error)
        path = self.base / "a.exe"
        path.write_text("fixture")
        received = changes.get(timeout=3)
        self.assertEqual(received, path)
        renamed = self.base / "b.exe"
        path.rename(renamed)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if changes.get(timeout=3) == renamed:
                break
        else:
            self.fail("Rename not reported")
        renamed.unlink()
        watcher.close()
        self.assertFalse(watcher.thread.is_alive())

    def test_running_service_discovers_new_nested_games_and_removal(self):
        service, games, _, _ = self.make_service()
        child = games / "New" / "bin"
        child.mkdir(parents=True)
        exe = child / "game.exe"
        exe.write_text("simulated executable")
        found = self.await_result(service, lambda r: r[0] == "games" and any(g.name == "New" for g in r[1]))
        self.assertEqual(len(found[1]), 1)
        exe.unlink()
        removed = self.await_result(service, lambda r: r[0] == "games" and not r[1])
        self.assertEqual(Path(removed[2]), games / "New")

    def test_running_service_steam_item_creation_and_partial_manifest(self):
        service, _, apps, _ = self.make_service()
        (apps / "common" / "New").mkdir(parents=True)
        file = apps / "appmanifest_987.acf"
        file.write_text('"AppState" {', encoding="utf-8")
        time.sleep(.15)
        file.write_text('"AppState" { "appid" "987" "name" "New" "installdir" "New" }', encoding="utf-8")
        result = self.await_result(service, lambda r: r[0] == "launchers" and any(g.id == "steam:987" for g in r[1]))
        self.assertTrue(result[1])
        file.unlink()
        self.await_result(service, lambda r: r[0] == "launchers" and not r[1])

    def test_running_service_epic_install_location(self):
        service, _, _, epic = self.make_service()
        root = self.base / "AnotherDrive" / "EpicGame"
        root.mkdir(parents=True)
        (epic / "new.item").write_text(json.dumps({"AppName": "fixture", "DisplayName": "Epic Fixture", "InstallLocation": str(root)}))
        result = self.await_result(service, lambda r: r[0] == "launchers" and any(g.id == "epic:fixture" for g in r[1]))
        self.assertEqual(Path(result[1][0].root), root)

    def test_missing_games_folder_is_detected_when_created(self):
        settings = Settings(games_root=str(self.base / "Missing" / "Games"))
        discovery = Discovery(settings, [], [], self.base / "none.dat", platforms=False, ubisoft=False, riot=False)
        service = DiscoveryService(settings, discovery=discovery)
        self.addCleanup(service.close)
        service.start()
        self.await_result(service, lambda r: r[0] == "games")
        game = Path(settings.games_root) / "First" / "bin"
        game.mkdir(parents=True)
        (game / "first.exe").write_text("fixture")
        self.await_result(service, lambda r: r[0] == "games" and any(g.name == "First" for g in r[1]))


if __name__ == "__main__":
    unittest.main()
