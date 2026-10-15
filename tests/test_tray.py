import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == "nt", "Windows required")
class TrayTests(unittest.TestCase):
    def setUp(self):
        from gametime import win32
        self.native = win32

    def test_version4_events_only_open_or_request_menu_and_ignore_hover(self):
        opened, menus = [], []
        tray = self.native.Tray(lambda: opened.append(True), lambda: menus.append(True), lambda: None)
        self.addCleanup(tray.close)
        self.assertTrue(tray.owns_icon)
        tray.version4 = True
        def event(code, uid=1, point=0):
            tray._message(tray.window, 0x8001, point, (uid << 16) | code)
        event(0x202)  # Legacy mouse-up must not duplicate a v4 activation.
        event(0x203)
        event(0x406)  # Hover popup open/close must not hide or exit the app.
        event(0x407)
        event(0x400, uid=2)
        self.assertEqual(opened, [])
        event(0x400)
        event(0x401)
        self.assertEqual(opened, [])  # Native callbacks must never call Tk.
        tray.dispatch_pending()
        self.assertEqual(len(opened), 2)
        event(0x7B, point=(200 << 16) | (0xFFFF & -100))
        event(0x7B)
        tray.dispatch_pending()
        self.assertEqual(len(menus), 1)
        self.assertEqual(tray.menu_position, (-100, 200))

    def test_legacy_shell_fallback_handles_mouse_buttons(self):
        opened, menus = [], []
        tray = self.native.Tray(lambda: opened.append(True), lambda: menus.append(True), lambda: None)
        self.addCleanup(tray.close)
        tray.version4 = False
        tray._message(tray.window, 0x8001, 1, 0x202)
        tray._message(tray.window, 0x8001, 1, 0x205)
        tray.dispatch_pending()
        self.assertEqual((len(opened), len(menus)), (1, 1))

    def test_native_context_menu_cancels_without_running_any_command(self):
        tray = self.native.Tray(lambda: None, lambda: None, lambda: None)
        self.addCleanup(tray.close)
        tray.menu_position = (10, 100)
        tray.menu_pending = True
        # Send cancellation only to this test's own window, no global key/mouse input.
        timer = threading.Timer(.2, lambda: self.native.u.PostMessageW(tray.window, 0x001F, 0, 0))
        timer.start()
        try:
            choice = tray.popup_menu([(1, "Megnyitas"), None, (5, "Kilepes")])
        finally:
            timer.join(timeout=2)
        self.assertEqual(choice, 0)
        self.assertFalse(tray.menu_pending)

    def test_app_left_click_reopens_close_button_hides_and_only_exit_quits(self):
        import tkinter as tk
        from gametime.discovery import Discovery
        from gametime.model import Settings
        from gametime.service import DiscoveryService
        from gametime.store import Store
        from gametime.ui import App
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            store = Store(base / "usage.sqlite3")
            settings = Settings(games_root=str(base / "Games"))
            store.save_settings(settings)
            service = DiscoveryService(settings, discovery=Discovery(settings, [], [], base / "none.dat", ubisoft=False, riot=False))
            root = tk.Tk()
            app = App(root, store, base, background=True, service=service)
            try:
                root.update()
                root.tk.eval(root.protocol("WM_DELETE_WINDOW"))
                root.update()
                self.assertEqual(root.state(), "withdrawn")
                self.assertFalse(app.closed)
                for _ in range(2):
                    app.tray._message(app.tray.window, 0x8001, 0, (1 << 16) | 0x400)
                    app.tray.dispatch_pending()
                    root.update()
                    self.assertEqual(root.state(), "normal")
                    self.assertFalse(app.closed)
                with patch.object(app.tray, "popup_menu", return_value=0):
                    app.tray_menu()
                self.assertEqual(root.state(), "normal")
                self.assertFalse(app.closed)
                for command, method in ((2, "open_games"), (3, "settings_dialog"), (4, "refresh_sources")):
                    with patch.object(app.tray, "popup_menu", return_value=command), patch.object(app, method) as action:
                        app.tray_menu()
                        action.assert_called_once_with()
                        self.assertFalse(app.closed)
                with patch.object(app.tray, "popup_menu", return_value=5):
                    app.tray_menu()
                self.assertTrue(app.closed)
            finally:
                app.close()
                store.close()

    def test_posted_shell_notifications_survive_real_tk_mainloop(self):
        probe = Path(__file__).with_name("tray_message_probe.py")
        result = subprocess.run([sys.executable, "-B", "-X", "faulthandler", str(probe)],
                                cwd=probe.parent.parent, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TRAY_MAINLOOP_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
