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
        service = DiscoveryService(settings, discovery=Discovery(settings, [], [], base / "none.dat", platforms=False, ubisoft=False, riot=False))
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
            if ui_only:
                game = next(g for g in app.catalog.games.values() if g.source == "Games")
                app.tree.selection_set(game.id)
                app.toggle_hidden()
                report["checks"]["hidden_row_removed_without_excluding"] = not app.tree.exists(game.id) and app.catalog.enabled(game)
                app.show_hidden.set(True)
                app.refresh_view()
                report["checks"]["hidden_row_can_be_shown"] = app.tree.exists(game.id) and "hidden" in app.tree.item(game.id, "values")[3]
                app.tree.selection_set(game.id)
                app.uninstall_game()
                root.update()
                guide = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
                capture(dark_title(guide), report_path.with_name("dark-uninstall-guide.png"))
                report["checks"]["removal_guide_opens_without_deleting_game"] = guide.winfo_viewable() and example.is_file()
                guide.destroy()  # No Continue: never start a real remover in UI tests.
                app.toggle_hidden()
                app.show_hidden.set(False)
                app.refresh_view()
                report["checks"]["hidden_row_restored"] = app.tree.exists(game.id) and game.id not in store.hidden_ids()
                from queue import Queue
                from types import SimpleNamespace
                from unittest.mock import Mock, patch
                from gametime.launch import LaunchPlan
                app.tree.selection_set(game.id)
                app.search.set("no matching fixture")
                report["checks"]["hub_search_filters_and_disables_play"] = not app.tree.get_children() and str(app.launch_button['state']) == 'disabled'
                app.search.set(game.name.lower())
                report["checks"]["hub_search_finds_game_case_insensitively"] = app.tree.exists(game.id)
                app.search.set("")
                app.source_filter.set(app.t("Games folder")); app.refresh_view()
                report["checks"]["hub_source_filter"] = all(app.catalog.games[gid].source == 'Games' for gid in app.tree.get_children()) and app.tree.exists(game.id)
                app.source_filter.set(app.t("All sources")); app.refresh_view()
                app.tree.selection_set(game.id)
                app.launcher = SimpleNamespace(results=Queue(), request=Mock(), close=Mock())
                tracker, before = app.tracker, total()
                app.launch_selected(); app.launch_selected()
                report["checks"]["hub_play_deduplicates_while_preparing"] = app.launcher.request.call_count == 1 and str(app.launch_button['state']) == 'disabled'
                with patch('gametime.launch.execute') as execute:
                    app.launcher.results.put((game,LaunchPlan('uri','steam://rungameid/42'),None))
                    app.poll_launch()
                    report["checks"]["hub_play_executes_explicit_request_once"] = execute.call_count == 1 and app.launching is None
                report["checks"]["hub_launch_preserves_tracker_and_time"] = app.tracker is tracker and total() == before and not app.closed
                app.notebook.select(app.statistics); root.withdraw()
                with patch('gametime.ui.os.startfile') as folder:
                    app.open_games()
                    report["checks"]["hub_opens_inside_monitor_instead_of_explorer"] = app.notebook.index(app.notebook.select()) == 0 and root.state() == 'normal' and not folder.called
                app.search.set(game.name)
                app.set_language('hu'); root.update()
                report["checks"]["hub_language_switch_preserves_search"] = app.search.get() == game.name and app.tree.exists(game.id)
                report["checks"]["hub_launch_status_changes_language"] = app.status.get().startswith('Indítás:')
                app.search.set(""); app.set_language('en'); root.update()
            report["checks"]["native_tray_icon_added"] = app.tray.available
            capture(dark_title(root), report_path.with_name("dark-main.png"))
            app.settings_dialog()
            root.update()
            settings_window = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][-1]
            capture(dark_title(settings_window), report_path.with_name("dark-settings.png"))
            settings_window.destroy()
            if ui_only:
                from datetime import timedelta
                from gametime.model import Game
                yesterday = (datetime.now().date()-timedelta(days=1)).isoformat()
                today_key = datetime.now().date().isoformat()
                retired = Game("fixture:retired", "Earlier game", "Epic", str(base/"Removed"), installed=False)
                store.upsert([retired])
                store.add_usage({(yesterday,game.id):900,(yesterday,retired.id):3600,(today_key,game.id):120})
                store.set_hidden(game.id,True)
                app.tracker.cache.clear()
                app.set_language("hu")
                root.update()
                report["checks"]["hungarian_switch_saved_without_restart"] = root.title() == "Játékidőfigyelő" and store.settings().language == "hu"
                app.settings_dialog(); root.update()
                settings_window = [w for w in root.winfo_children() if isinstance(w,tk.Toplevel)][-1]
                capture(dark_title(settings_window),report_path.with_name("hungarian-settings.png"))
                settings_window.destroy()
                app.notebook.select(app.statistics)
                app.statistics.refresh(); root.update()
                report["checks"]["statistics_totals_include_hidden_and_removed"] = app.statistics.report.total == 4620 and len(app.statistics.report.games) == 2
                report["checks"]["statistics_average_starts_at_installation"] = app.statistics.report.average_days == 2 and app.statistics.report.average == 2310
                capture(dark_title(root),report_path.with_name("statistics-hungarian.png"))
                app.statistics.days_tree.selection_set(yesterday)
                app.statistics.select_day(); root.update()
                report["checks"]["statistics_day_breakdown"] = len(app.statistics.games_tree.get_children()) == 2 and app.statistics.selected_day == yesterday
                app.statistics.start.set("bad"); app.statistics.refresh()
                report["checks"]["statistics_date_error_in_hungarian"] = "formátuma" in app.statistics.error.get()
                app.statistics.preset(7)
                start, end = app.statistics.start.get(), app.statistics.end.get()
                app.set_language("en"); root.update()
                report["checks"]["language_switch_preserves_statistics_period"] = app.statistics.start.get()==start and app.statistics.end.get()==end and root.title()=="Game Time Monitor"
                app.statistics.refresh()
                capture(dark_title(root),report_path.with_name("statistics-english.png"))
                app.set_language("hu"); root.update()
                app.notebook.select(0)
                store.set_hidden(game.id,False); app.refresh_view()
                app.tree.selection_set(game.id); root.update()
                capture(dark_title(root),report_path.with_name("hungarian-games.png"))
            today = datetime.now().date().isoformat()
            assert app.popup(Alert(today, (), "warning", app.t("You have {remaining} minutes of game time left today.",remaining=20), app.t("OK")))
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
