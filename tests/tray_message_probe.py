"""Exercise OS-dispatched tray messages inside Tcl's real native event loop.

Run in a subprocess: the old WNDPROC -> root.after path aborts CPython and
cannot be caught by unittest. Only this test's own hidden HWND is addressed.
"""
import faulthandler
from pathlib import Path
import sys
import tempfile
import threading
import tkinter as tk
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gametime import win32
from gametime.discovery import Discovery
from gametime.model import Settings
from gametime.service import DiscoveryService
from gametime.store import Store
from gametime.ui import App


def main():
    faulthandler.enable()
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        store = Store(base / "usage.sqlite3")
        settings = Settings(games_root=str(base / "Games"))
        store.save_settings(settings)
        service = DiscoveryService(settings, discovery=Discovery(
            settings, [], [], base / "none.dat", platforms=False, ubisoft=False, riot=False))
        root = tk.Tk()
        app = App(root, store, base, service=service)
        errors, menus = [], []

        def post(event):
            assert win32.u.PostMessageW(app.tray.window, 0x8001, 0, (1 << 16) | event)

        def guarded(action):
            def run():
                try:
                    action()
                except Exception:
                    errors.append(traceback.format_exc())
                    root.quit()
            return run

        def check_open():
            assert root.state() == "normal", root.state()
            assert not app.closed

        def hidden():
            check_open()
            root.tk.eval(root.protocol("WM_DELETE_WINDOW"))
            assert root.state() == "withdrawn"
            post(0x400)

        def minimized():
            check_open()
            root.iconify()
            post(0x400)

        def repeated():
            check_open()
            for _ in range(20):
                post(0x400)
                post(0x401)
            post(0x406)  # Hover notifications must not close or hide anything.
            post(0x407)

        original_menu = app.tray.popup_menu

        def cancel_menu(items):
            menus.append("cancelled")
            timer = threading.Timer(.2, lambda: win32.u.PostMessageW(app.tray.window, 0x001F, 0, 0))
            timer.start()
            try:
                return original_menu(items)
            finally:
                timer.join(timeout=2)

        app.tray.popup_menu = cancel_menu

        def menu():
            check_open()
            post(0x7B)

        def exit_via_menu():
            check_open()
            assert menus == ["cancelled"], menus
            app.tray.popup_menu = lambda items: 5
            post(0x7B)

        def timeout():
            raise AssertionError("Tray messages were not handled before timeout")

        assert app.tray.version4
        root.after(100, guarded(lambda: post(0x400)))
        root.after(350, guarded(hidden))
        root.after(600, guarded(minimized))
        root.after(850, guarded(repeated))
        root.after(1100, guarded(menu))
        root.after(1700, guarded(exit_via_menu))
        root.after(5000, guarded(timeout))
        try:
            root.mainloop()
            assert not errors, "\n".join(errors)
            assert app.closed, "Only the explicit Exit command should terminate the loop"
            print("TRAY_MAINLOOP_OK: visible, hidden, minimized, repeated, keyboard, hover, menu cancel, exit")
        finally:
            app.close()
            store.close()


if __name__ == "__main__":
    main()
