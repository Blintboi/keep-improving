"""Entry point. Installer/diagnostic commands never start the resident UI."""
import argparse
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time


def default_data():
    # Matches the reminder project's per-user Documents deployment convention.
    return Path(__file__).resolve().parent / "data"


def main():
    parser = argparse.ArgumentParser(description="Windows 11 játékidőfigyelő")
    parser.add_argument("--data-dir", type=Path, default=default_data())
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--games-root")
    parser.add_argument("--enable-hub", action="store_true")
    parser.add_argument("--sync-hub", action="store_true")
    parser.add_argument("--scan-once", action="store_true")
    parser.add_argument("--stop-wait", type=float)
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args()
    if args.enable_hub and not args.configure:
        parser.error("A --enable-hub a --configure kapcsolóval használható.")
    if args.diagnose and (args.configure or args.scan_once or args.sync_hub):
        parser.error("A --diagnose külön ellenőrző parancs.")
    if os.name != "nt":
        parser.error("Windows 11 szükséges.")
    args.data_dir.mkdir(parents=True, exist_ok=True)
    from gametime.win32 import Instance
    instance = Instance(args.data_dir)
    if args.stop_wait is not None:
        deadline = time.monotonic() + args.stop_wait
        while not instance.acquired:
            (args.data_dir / "stop.request").touch()
            instance.close()
            if time.monotonic() >= deadline:
                raise RuntimeError("A figyelő nem állt le időben. Zárd be a tálcamenü Kilépés parancsával.")
            time.sleep(0.2)
            instance = Instance(args.data_dir)
        instance.close()
        (args.data_dir / "stop.request").unlink(missing_ok=True)
        return
    if not instance.acquired and not args.diagnose:
        instance.close()
        if args.configure or args.scan_once or args.sync_hub:
            raise RuntimeError("Előbb állítsd le a futó figyelőt a beállítások importálásához.")
        (args.data_dir / "show.request").touch()
        return
    if instance.acquired:
        (args.data_dir / "stop.request").unlink(missing_ok=True)
    handler = RotatingFileHandler(args.data_dir / "monitor.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from gametime.store import Store
    store = Store(args.data_dir / "usage.sqlite3")
    try:
        if args.configure:
            settings = store.settings()
            if args.games_root:
                settings.games_root = str(Path(args.games_root).resolve())
            if args.enable_hub:
                settings.hub_enabled = True
            store.save_settings(settings)
        if args.scan_once:
            from gametime.model import LAUNCHER_SOURCES
            from gametime.discovery import Discovery, preserve_unreadable
            discovery = Discovery(store.settings())
            launchers = preserve_unreadable(discovery.scan_launchers(), store.games(True), discovery.errors)
            games = discovery.scan_games()
            store.reconcile(launchers, lambda g: g.source in LAUNCHER_SOURCES)
            store.reconcile(games, lambda g: g.source == "Games")
            print(json.dumps({"games": len(launchers) + len(games), "metadata_pending": discovery.errors}, ensure_ascii=False))
        if args.sync_hub:
            from gametime.hub import Hub
            hub = Hub(args.data_dir)
            try:
                print(json.dumps(hub.sync(store.settings(), store.games(True), store.rules(), store.overrides()), ensure_ascii=False))
            finally:
                hub.bridge.close()
        if args.diagnose:
            from gametime import __version__
            from gametime.win32 import sample
            current = sample()
            print(json.dumps({"version": __version__, "python": sys.version, "data": str(args.data_dir),
                              "interactive": current.interactive, "foreground_readable": bool(current.path),
                              "installed_games": len(store.games(True)),
                              "today_seconds": sum(store.totals(datetime.now().date()).values())}, ensure_ascii=False))
        if args.configure or args.scan_once or args.diagnose or args.sync_hub:
            return
        import tkinter as tk
        from gametime.ui import App
        root = tk.Tk()
        app = App(root, store, args.data_dir, args.background)
        try:
            root.mainloop()
        finally:
            app.close()
    finally:
        store.close()
        instance.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("A játékidőfigyelő nem indítható")
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "A játékidőfigyelő hibába ütközött. Részletek a data/monitor.log fájlban.",
                                            "Játékidőfigyelő", 0x10)
        raise
