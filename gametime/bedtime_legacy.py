"""One-time handover of the known per-user 23:55 reminder; preserve its files."""
import ctypes
from dataclasses import replace
import logging
import os
from pathlib import Path
import subprocess

log = logging.getLogger(__name__)


def documents():
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer):
        raise OSError('Documents folder unavailable')
    return Path(buffer.value)


def legacy_task(mode):
    script = Path(__file__).with_name('bedtime_legacy.ps1')
    command = Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(command), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                             '-File', str(script), '-Mode', mode], capture_output=True,
                            text=True, encoding='utf-8-sig', errors='replace', timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise OSError('Legacy reminder handover failed')
    return result.stdout.strip()


def migrate(store, data_dir):
    try:
        # Isolated tests and secondary profiles must never touch the user's task.
        if Path(data_dir).resolve() != (documents()/'GameTimeMonitor/data').resolve(): return
        if store.db.execute("SELECT 1 FROM settings WHERE key='bedtime_legacy_checked'").fetchone(): return
        xml = legacy_task('Inspect')
        if xml:
            backup = Path(data_dir)/'backups/bedtime-reminder-task.xml'
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(xml, encoding='utf-16')
            settings = store.settings()
            store.save_settings(replace(settings, bedtime_enabled=True))
            if legacy_task('Disable') != 'disabled': raise OSError('Legacy reminder changed during handover')
            log.info('Imported the 23:55 bedtime reminder; previous scheduled task disabled')
        with store.db:
            store.db.execute("INSERT INTO settings VALUES ('bedtime_legacy_checked','1')")
    except (OSError, subprocess.SubprocessError):
        log.exception('Previous bedtime reminder could not be imported; will retry on next start')
