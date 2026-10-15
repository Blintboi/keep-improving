"""Optional interactive Windows test, isolated data and self-closing fixture games.

Run from the project directory: py -3 -B tests/gui_smoke.py --report PATH
Requires the Windows .NET Framework C# compiler (only for the test fixture).
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import traceback
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gametime.discovery import Discovery
from gametime.model import Settings
from gametime.service import DiscoveryService
from gametime.store import Store
from gametime.tracker import Alert
from gametime.ui import App, BG, PANEL, dark_title
from gametime import win32


def capture(hwnd, path):
    """Render this test application's own window, not the user's desktop."""
    g = C.WinDLL("gdi32", use_last_error=True)
    api = win32.api
    api(win32.u, "GetWindowRect", [W.HWND, C.POINTER(W.RECT)], W.BOOL)
    api(win32.u, "GetWindowDC", [W.HWND], W.HDC)
    api(win32.u, "ReleaseDC", [W.HWND, W.HDC], C.c_int)
    api(win32.u, "PrintWindow", [W.HWND, W.HDC, W.UINT], W.BOOL)
    api(g, "CreateCompatibleDC", [W.HDC], W.HDC)
    api(g, "CreateCompatibleBitmap", [W.HDC, C.c_int, C.c_int], W.HBITMAP)
    api(g, "SelectObject", [W.HDC, W.HANDLE], W.HANDLE)
    api(g, "DeleteObject", [W.HANDLE], W.BOOL)
    api(g, "DeleteDC", [W.HDC], W.BOOL)
    api(g, "GetDIBits", [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT], C.c_int)
    rect = W.RECT()
    assert win32.u.GetWindowRect(hwnd, C.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    dc = win32.u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(dc)
    bitmap = g.CreateCompatibleBitmap(dc, width, height)
    old = g.SelectObject(mem, bitmap)
    try:
        assert win32.u.PrintWindow(hwnd, mem, 2)
        g.SelectObject(mem, old)
        data = C.create_string_buffer(width * height * 4)
        header = C.create_string_buffer(struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, len(data), 0, 0, 0, 0))
        assert g.GetDIBits(mem, bitmap, 0, height, data, header, 0) == height
        raw = data.raw
        rows = []
        for y in range(height):
            row = raw[y * width * 4:(y + 1) * width * 4]
            rgb = bytearray(width * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
            rows.append(b"\0" + rgb)
        def chunk(tag, value):
            return struct.pack(">I", len(value)) + tag + value + struct.pack(">I", zlib.crc32(tag + value) & 0xFFFFFFFF)
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
               chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
        Path(path).write_bytes(png)
    finally:
        g.DeleteObject(bitmap)
        g.DeleteDC(mem)
        win32.u.ReleaseDC(hwnd, dc)


def run(report_path, ui_only=False):
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"fixture": "Synthetic games and launcher manifests; no real Steam/Epic installation performed", "checks": {}}
    if ui_only:
        report["foreground_tests"] = "Not run: require manual foreground activation; UI visibility and real Win32 widgets tested"
    with tempfile.TemporaryDirectory(prefix="game-time-gui-") as temp:
        base = Path(temp)
        csc = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
        if not csc.is_file():
            csc = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe"
        compiled = base / "FixtureGame.exe"
        subprocess.run([str(csc), "/nologo", "/target:winexe", "/reference:System.Windows.Forms.dll",
                        "/reference:System.Drawing.dll", "/out:" + str(compiled),
                        str(Path(__file__).with_name("FixtureGame.cs"))], check=True, capture_output=True)
        games = base / "Games"
        games.mkdir()
        if ui_only:
            example = games / "Bemutato jatek" / "bin" / "game.exe"
            example.parent.mkdir(parents=True)
            example.write_text("fixture")
        data = base / "data"
        data.mkdir()
        settings = Settings(games_root=str(games))
        store = Store(data / "usage.sqlite3")
        store.save_settings(settings)
        service = DiscoveryService(settings, discovery=Discovery(settings, [], [], base / "none.dat", ubisoft=False))
        root = tk.Tk()
        app = App(root, store, data, service=service)
        children = []
        started = time.monotonic()
        totals = []
        def total():
            return sum(app.tracker.totals(datetime.now().date()).values())
        def schedule(delay, function):
            def guarded():
                try:
                    function()
                except Exception:
                    report["error"] = traceback.format_exc()
                    finish()
            root.after(delay, guarded)
        def launch_first():
            app.show()
            root.focus_force()
            target = games / "Friss jatek" / "bin" / "game.exe"
            target.parent.mkdir(parents=True)
            shutil.copyfile(compiled, target)
            children.append(subprocess.Popen([str(target), str(base / "stop-game-1")]))
            schedule(4300, first_active)
        def first_active():
            current = win32.sample()
            report["foreground_debug"] = {"name": Path(current.path).name, "interactive": current.interactive,
                                           "fixture_exit": children[0].poll(), "known_games": len(app.catalog.games)}
            report["checks"]["real_foreground_executable"] = current.path.lower().endswith(r"friss jatek\bin\game.exe")
            report["checks"]["first_launch_counted_without_restart_or_registration"] = total() >= 2
            report["checks"]["no_keyboard_mouse_required"] = total() >= 2
            assert all(report["checks"].values()), report
            totals.append(total())
            app.show()
            schedule(2600, background)
        def background():
            report["checks"]["alt_tab_and_background_pause"] = total() - totals[-1] <= 1.5
            report["checks"]["background_process_still_running"] = children[0].poll() is None
            assert report["checks"]["alt_tab_and_background_pause"]
            target = games / "Masodik jatek" / "bin" / "renderer.exe"
            target.parent.mkdir(parents=True)
            shutil.copyfile(compiled, target)
            children.append(subprocess.Popen([str(target), str(base / "stop-game-2")]))
            totals.append(total())
            report["second_start"] = time.monotonic()
            schedule(3400, second_active)
        def second_active():
            elapsed = time.monotonic() - report.pop("second_start")
            report["checks"]["two_running_games_not_double_counted"] = 1 <= total() - totals[-1] <= elapsed + .3
            report["checks"]["second_foreground_game_identified"] = bool(app.tracker.active and app.tracker.active.name == "Masodik jatek")
            assert report["checks"]["two_running_games_not_double_counted"]
            assert report["checks"]["second_foreground_game_identified"]
            app.show()
            schedule(500, capture_main)
        def capture_main():
            root.update()
            report["checks"]["native_tray_icon_added"] = app.tray.available
            capture(dark_title(root), report_path.with_name("dark-main.png"))
            app.settings_dialog()
            root.update()
            settings_window = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
            capture(dark_title(settings_window), report_path.with_name("dark-settings.png"))
            settings_window.destroy()
            today = datetime.now().date().isoformat()
            assert app.popup(Alert(today, (), "warning", "Már csak 20 perc játékidőd maradt mára.", "Rendben"))
            report["checks"]["popup_topmost"] = bool(app.popup_window.attributes("-topmost"))
            schedule(400, warning_popup)
        def dismiss():
            for widget in app.popup_window.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.invoke()
                    return
            raise AssertionError("Popup acknowledgment button missing")
        def warning_popup():
            capture(dark_title(app.popup_window), report_path.with_name("dark-warning.png"))
            dismiss()
            root.withdraw()
            app.test_popup()
            schedule(400, limit_popup)
        def limit_popup():
            visible = win32.api(win32.u, "IsWindowVisible", [W.HWND], W.BOOL)
            report["checks"]["popup_visible_with_main_window_hidden"] = bool(visible(dark_title(app.popup_window)))
            capture(dark_title(app.popup_window), report_path.with_name("dark-limit.png"))
            report["checks"]["dark_main_settings_popups"] = root.cget("bg") == BG and ttk.Style(root).lookup("Treeview", "fieldbackground") == PANEL
            dismiss()
            report["checks"]["acknowledgment_button_closes_popup"] = app.popup_window is None
            app.tracker.flush()
            if not ui_only:
                report["checks"]["sqlite_saved_runtime_usage"] = sum(store.totals(datetime.now().date()).values()) >= 3
            report["measured_seconds"] = total()
            finish()
        def finish():
            if app.closed:
                return
            report["elapsed_seconds"] = round(time.monotonic() - started, 2)
            for index in range(len(children)):
                (base / f"stop-game-{index + 1}").touch()
            app.close()
        schedule(1500, capture_main if ui_only else launch_first)
        root.after(35000, lambda: (report.update(error="GUI test timed out"), finish()))
        try:
            root.mainloop()
        finally:
            if not app.closed:
                finish()
            for child in children:
                child.wait(timeout=48)
            store.close()
    report["passed"] = not report.get("error") and all(report["checks"].values())
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ui-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.report, args.ui_only))
