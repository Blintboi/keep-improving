from datetime import datetime, timedelta
import gc
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == "nt", "Windows required")
class NotificationTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from gametime import win32
        from gametime.discovery import Discovery
        from gametime.model import Game, Settings
        from gametime.service import DiscoveryService
        from gametime.store import Store
        from gametime.ui import App
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.store = Store(base / "usage.sqlite3")
        self.addCleanup(self.store.close)
        settings = Settings(games_root=str(base / "Games"))
        self.store.save_settings(settings)
        self.game = Game("fixture:notification", "Notification fixture", "Kézi", str(base))
        self.exe = str(base / "fixture.exe")
        Path(self.exe).write_bytes(b"MZ fixture")
        self.store.upsert([self.game])
        self.store.set_rule(self.exe, self.game.id)
        service = DiscoveryService(settings, discovery=Discovery(
            settings, [], [], base / "none.dat", platforms=False, ubisoft=False, riot=False))
        self.root = tk.Tk()
        self.app = App(self.root, self.store, base, service=service)
        self.addCleanup(self.close_app)
        sound = patch("gametime.ui.winsound.PlaySound")
        sound.start()
        self.addCleanup(sound.stop)
        self.root.update()
        self.root.after_cancel(self.app.tick_timer)
        self.app.tick_timer = None
        self.native = win32

    def close_app(self):
        self.app.close()
        self.app = self.root = None
        # Tcl objects must be finalized on the UI thread before another
        # discovery worker can trigger cyclic GC in the next test.
        gc.collect()

    def pump(self, duration=.25):
        until = time.monotonic() + duration
        while time.monotonic() < until:
            self.root.update()
            time.sleep(.01)

    def cross_threshold(self, seconds, kind, delivered=True, foreground=True):
        from gametime.tracker import Sample
        now = datetime.now().astimezone()
        day = now.date().isoformat()
        self.store.add_usage({(day, self.game.id): seconds - 1})
        if kind == "limit":
            self.store.mark_alert(day, ("warning:6000",))
        self.app.tracker.tick(Sample(now, 100, self.exe, "fixture:1"))
        with patch("gametime.ui.win32.sample", return_value=Sample(
                now + timedelta(seconds=1), 101, self.exe if foreground else "browser.exe",
                "fixture:1" if foreground else "browser:1")):
            self.app.tick()
        self.pump()
        if delivered:
            self.assertIsNotNone(self.app.popup_window)
            self.assertEqual(len(self.app.tracker.alerts), 0)
            self.assertIn(f"{kind}:{seconds}", self.store.alert_keys(day))
        else:
            self.assertIsNone(self.app.popup_window)
            self.assertEqual(len(self.app.tracker.alerts), 1)
            self.assertNotIn(f"{kind}:{seconds}", self.store.alert_keys(day))

    def assert_popup_visible(self):
        from gametime.ui import dark_title
        popup = self.app.popup_window
        visible = self.native.api(self.native.u, "IsWindowVisible", [self.native.W.HWND], self.native.W.BOOL)
        self.assertTrue(popup.winfo_viewable(), f"Popup state: {popup.state()}")
        self.assertTrue(visible(dark_title(popup)))
        self.assertTrue(popup.attributes("-topmost"))
        self.assertFalse(popup.transient(), "Alerts must not inherit the main window's minimized/hidden state")

    def test_warning_threshold_while_main_window_minimized(self):
        self.root.iconify()
        self.pump(.1)
        self.assertEqual(self.root.state(), "iconic")
        self.cross_threshold(6000, "warning")
        self.assert_popup_visible()
        self.assertEqual(self.root.state(), "iconic")

    def test_limit_threshold_while_main_window_withdrawn(self):
        self.root.withdraw()
        self.cross_threshold(7200, "limit")
        self.assert_popup_visible()
        self.assertEqual(self.root.state(), "withdrawn")

    def test_existing_popup_stays_visible_when_main_window_is_hidden(self):
        self.cross_threshold(6000, "warning")
        self.root.iconify()
        self.pump(.1)
        self.assert_popup_visible()
        self.root.withdraw()
        self.pump(.1)
        self.assert_popup_visible()

    def test_failed_presentation_keeps_alert_pending_and_retries(self):
        self.root.iconify()
        from gametime.tracker import Sample
        with patch("gametime.ui.win32.escape_game", return_value=True) as escape:
            with patch("gametime.ui.win32.present_notification", side_effect=OSError("fixture presentation failure")), \
                    self.assertLogs("gametime.ui", level="ERROR"):
                self.cross_threshold(6000, "warning", delivered=False)
            now = datetime.now().astimezone()
            with patch("gametime.ui.win32.sample", return_value=Sample(now, 102, self.exe, "fixture:1")):
                self.app.tick()
            escape.assert_called_once_with(self.exe, "fixture:1")
        self.pump()
        self.assert_popup_visible()
        self.assertEqual(len(self.app.tracker.alerts), 0)
        self.assertIn("warning:6000", self.store.alert_keys(datetime.now().date().isoformat()))

    def test_escape_precedes_popup_by_200ms_for_the_active_game(self):
        events = []
        original = self.native.present_notification
        def escape(*args):
            self.assertIsNone(self.app.popup_window)
            events.append(("escape", time.monotonic()))
            return True
        def present(hwnd):
            events.append(("popup", time.monotonic()))
            return original(hwnd)
        self.root.iconify()
        with patch("gametime.ui.win32.escape_game", side_effect=escape) as sent, \
                patch("gametime.ui.win32.present_notification", side_effect=present):
            self.cross_threshold(6000, "warning")
        sent.assert_called_once_with(self.exe, "fixture:1")
        self.assertEqual([event[0] for event in events], ["escape", "popup"])
        self.assertGreaterEqual(events[1][1] - events[0][1], .19)
        self.assert_popup_visible()

    def test_background_alert_does_not_send_escape_to_an_unrelated_app(self):
        with patch("gametime.ui.win32.escape_game") as escape:
            self.cross_threshold(6000, "warning", foreground=False)
        escape.assert_not_called()
        self.assert_popup_visible()

    def test_topmost_popup_remains_visible_when_foreground_request_is_denied(self):
        self.root.iconify()
        with patch.object(self.native.u, "SetForegroundWindow", return_value=False):
            self.cross_threshold(6000, "warning")
        self.assert_popup_visible()

    def test_popup_is_above_synthetic_borderless_topmost_fullscreen_window(self):
        import tkinter as tk
        from gametime.ui import dark_title
        game = tk.Toplevel(self.root)
        game.title("Synthetic fullscreen fixture")
        game.attributes("-fullscreen", True)
        game.attributes("-topmost", True)
        game.configure(bg="#304030")
        self.pump(.1)
        self.assertTrue(game.winfo_viewable())
        self.root.iconify()
        self.cross_threshold(6000, "warning")
        self.assert_popup_visible()
        hwnd = dark_title(self.app.popup_window)
        rectangle = self.native.W.RECT()
        get_rect = self.native.api(self.native.u, "GetWindowRect",
                                   [self.native.W.HWND, self.native.C.POINTER(self.native.W.RECT)], self.native.W.BOOL)
        self.assertTrue(get_rect(hwnd, self.native.C.byref(rectangle)))
        hit_test = self.native.api(self.native.u, "WindowFromPoint", [self.native.W.POINT], self.native.W.HWND)
        ancestor = self.native.api(self.native.u, "GetAncestor", [self.native.W.HWND, self.native.W.UINT], self.native.W.HWND)
        point = self.native.W.POINT((rectangle.left + rectangle.right) // 2,
                                   (rectangle.top + rectangle.bottom) // 2)
        self.assertEqual(ancestor(hit_test(point), 2), hwnd, "Another window covers the popup")


@unittest.skipUnless(os.name == "nt", "Windows required")
class EscapeSafetyTests(unittest.TestCase):
    def setUp(self):
        from gametime import win32
        self.native = win32
        self.path, self.identity = r"C:\Games\Fixture\game.exe", "123:456"
        replacements = [patch.object(win32, "interactive_desktop", return_value=True),
                        patch.object(win32.u, "GetForegroundWindow", return_value=444),
                        patch.object(win32.u, "GetWindowThreadProcessId", return_value=1),
                        patch.object(win32, "process_image", return_value=(self.path, self.identity)),
                        patch.object(win32.u, "GetAsyncKeyState", return_value=0),
                        patch.object(win32.u, "SendInput", return_value=2)]
        self.mocks = [replacement.start() for replacement in replacements]
        for replacement in replacements:
            self.addCleanup(replacement.stop)

    def test_sends_one_escape_down_up_pair_with_native_input_size(self):
        def send(count, keys, size):
            self.assertEqual(count, 2)
            self.assertEqual([(key.type, key.ki.wVk, key.ki.dwFlags) for key in keys],
                             [(1, 0x1B, 0), (1, 0x1B, 2)])
            self.assertEqual(size, {8: 40, 4: 28}[self.native.C.sizeof(self.native.C.c_void_p)])
            return 2
        self.mocks[-1].side_effect = send
        self.assertTrue(self.native.escape_game(self.path, self.identity))
        self.mocks[-1].assert_called_once()

    def test_skips_different_game_focus_change_modifiers_and_locked_desktop(self):
        scenarios = [(0, False), (1, None), (1, [444, 555]),
                     (3, (self.path, "different:process")), (3, ("browser.exe", self.identity)), (4, 0x8000)]
        for index, value in scenarios:
            with self.subTest(index=index, value=value):
                target = self.mocks[index]
                old_value = target.return_value
                target.side_effect = value if isinstance(value, list) else None
                if not isinstance(value, list):
                    target.return_value = value
                try:
                    self.assertFalse(self.native.escape_game(self.path, self.identity))
                    self.mocks[-1].assert_not_called()
                finally:
                    target.return_value, target.side_effect = old_value, None

    def test_blocked_injection_does_not_repeat(self):
        self.mocks[-1].return_value = 0
        with self.assertLogs("gametime.win32", level="WARNING"):
            self.assertFalse(self.native.escape_game(self.path, self.identity))
        self.mocks[-1].assert_called_once()

    def test_partial_injection_releases_escape_without_pressing_again(self):
        self.mocks[-1].side_effect = [1, 1]
        with self.assertLogs("gametime.win32", level="WARNING"):
            self.assertFalse(self.native.escape_game(self.path, self.identity))
        self.assertEqual(self.mocks[-1].call_count, 2)
        count, pointer, size = self.mocks[-1].call_args.args
        self.assertEqual(count, 1)
        key = self.native.C.cast(pointer, self.native.C.POINTER(self.native.INPUT)).contents
        self.assertEqual((key.ki.wVk, key.ki.dwFlags), (0x1B, 2))


if __name__ == "__main__":
    unittest.main()
