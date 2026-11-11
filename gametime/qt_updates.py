"""Nonactivating checks; a user click downloads, verifies and installs an update."""
import logging
from sqlite3 import Error as SQLiteError
import time
import webbrowser
import os
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QScrollArea
from . import __version__
from .qt_translation import QCheckBox
from .qt_widgets import label, button, panel
from .updates import UpdateState, UpdateWorker, CHECK_INTERVAL, DOWNLOAD_URL

log = logging.getLogger(__name__)


class Updates:
    def __init__(self, app, worker=False):
        self.app = app
        self.worker = UpdateWorker() if worker is True else worker or None
        self.state = UpdateState(app.store)
        self.pending = False
        self.manual = False
        self.closed = False
        self.message = ''
        self.download_worker=None;self.downloading=False;self.ready=None;self.install_dir=None
        self.timer = QTimer(app); self.timer.setSingleShot(True); self.timer.timeout.connect(self.automatic_check)

    @property
    def available(self):
        release = self.state.release
        return release if release and release.newer_than(__version__) else None

    def banner(self):
        self.notice = panel()
        self.notice.setStyleSheet('QFrame#Panel {background:#1c3430; border-bottom:1px solid #31544b; border-radius:0;}')
        row = QHBoxLayout(self.notice); row.setContentsMargins(30,10,24,10)
        self.notice_text = label(); self.notice_text.setWordWrap(True); row.addWidget(self.notice_text,1)
        self.notice_download = button(self.app.t('Download and install update'), self.download)
        row.addWidget(self.notice_download); row.addWidget(button(self.app.t('Later'), self.dismiss, 'quiet'))
        self.notice.hide()
        return self.notice

    def settings_panel(self):
        self.card = panel(); layout = QVBoxLayout(self.card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(self.app.t('Application updates'),'section'))
        layout.addWidget(label(self.app.t('Installed version: {version}',version=__version__),'muted'))
        self.automatic = QCheckBox(self.app.t('Check for updates automatically (once a day)'))
        self.automatic.setChecked(self.app.settings.check_updates); layout.addWidget(self.automatic)
        self.automatic.setToolTip(self.app.t('Checks the public GitHub version list. Clicking Download and install update verifies the download, closes Keep Improving and restarts it in the background with your existing data.'))
        self.status = label('','muted'); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout(); self.check = button(self.app.t('Check for updates'), lambda:self.request(manual=True))
        self.download_button = button(self.app.t('Download and install update'), self.download)
        row.addWidget(self.check); row.addWidget(self.download_button); row.addStretch(); layout.addLayout(row)
        self.refresh()
        return self.card

    def refresh(self):
        release = self.available
        if hasattr(self, 'notice'):
            self.notice_text.setText(self.app.t('Version {version} is available.',version=release.version) if release else '')
            self.notice.setVisible(bool(release and self.state.dismissed != release.version))
            self.notice_download.setEnabled(not self.downloading)
        if hasattr(self, 'status'):
            feedback = self.downloading or self.ready is not None or self.message in ('Could not check for updates. Try again later.', 'Checked recently. Try again in a minute.',
                                        'Could not download and verify the update. The application is still running. Try again.', 'Could not start the installer. The application is still running. Try again.',
                                        'Save or discard your open settings changes before installing the update.', 'Run the installed application to install an update.')
            text = (self.app.t('Version {version} is available.',version=release.version) if release and not self.pending and not feedback else
                    self.app.t(self.message) if self.message else self.app.t('Automatic update checks are enabled.' if self.app.settings.check_updates else 'Automatic update checks are off.'))
            self.status.setText(text)
            self.check.setEnabled(not self.pending and not self.downloading and self.worker is not None)
            self.download_button.setVisible(release is not None)
            self.download_button.setEnabled(not self.pending and not self.downloading)
            self.download_button.setText(self.app.t('Install verified update' if self.ready else 'Download and install update'))
        if hasattr(self.app, 'tray'): self.app.update_tray()

    def save_state(self):
        try: self.state.save()
        except SQLiteError: log.warning('Could not remember public update state',exc_info=True)

    def reschedule(self):
        self.timer.stop()
        if self.worker is not None and not self.closed and self.app.settings.check_updates:
            delay = max(2, min(CHECK_INTERVAL, self.state.attempted + CHECK_INTERVAL - time.time()))
            self.timer.start(int(delay * 1000))

    def automatic_check(self):
        if self.app.settings.check_updates and time.time() - self.state.attempted >= CHECK_INTERVAL:
            self.request()
        else: self.reschedule()

    def request(self, manual=False):
        if self.closed or self.worker is None or self.pending: return False
        now = time.time()
        if now - self.state.attempted < 60:
            if manual:
                self.message = 'Checked recently. Try again in a minute.'; self.refresh()
            self.reschedule(); return False
        if not self.worker.request(): return False
        self.state.attempted = now; self.pending = True; self.manual = manual
        self.message = 'Checking for updates…'; self.save_state(); self.reschedule(); self.refresh()
        return True

    def poll(self):
        if self.closed:return
        self.poll_download()
        if self.worker is None: return
        while not self.worker.results.empty():
            release, error = self.worker.results.get_nowait()
            self.pending = False
            if error:
                self.message = ('Could not check for updates. Try again later.' if self.manual else '')
            else:
                self.state.release = release
                self.message = ('No newer public version is available.' if release else 'Update information has not been published yet.')
                self.save_state()
            self.refresh()

    def saved(self):
        self.reschedule(); self.refresh()

    def dismiss(self):
        if self.available:
            self.state.dismissed = self.available.version; self.save_state(); self.refresh()

    def download(self):
        if not self.available or self.downloading or self.closed:return False
        if self.ready:return self.install()
        from .update_install import DownloadWorker,installed_directory
        try:
            self.install_dir=installed_directory()
            if self.app.settings_have_draft():
                self.message='Save or discard your open settings changes before installing the update.';return False
            self.download_worker=self.download_worker or DownloadWorker()
            directory=Path(os.environ['LOCALAPPDATA'])/'KeepImproving'/'updates'
            self.downloading=self.download_worker.request(self.available,directory)
            self.message='Downloading and verifying the update…' if self.downloading else 'Could not download and verify the update. The application is still running. Try again.'
            return self.downloading
        except (OSError,ValueError,KeyError):
            log.warning('Could not prepare application update',exc_info=True)
            self.message='Run the installed application to install an update.';return False
        finally:self.refresh()

    def poll_download(self):
        if not self.download_worker or not self.downloading:return
        used,total=self.download_worker.progress
        if total:
            if hasattr(self,'status'):self.status.setText(self.app.t('Downloading update: {percent}%',percent=used*100//total))
            if hasattr(self,'notice_text'):self.notice_text.setText(self.app.t('Downloading update: {percent}%',percent=used*100//total))
        if self.download_worker.results.empty():return
        setup,error=self.download_worker.results.get_nowait();self.downloading=False
        if error:
            log.warning('Update download or verification failed: %s',type(error).__name__)
            self.message='Could not download and verify the update. The application is still running. Try again.';self.refresh();return
        self.ready=setup;self.install()

    def install(self):
        if not self.ready:return False
        if self.app.settings_have_draft():
            self.message='Save or discard your open settings changes before installing the update.';self.refresh();return False
        from .update_install import launch
        try:
            launch(self.ready,self.install_dir,self.app.data_dir)
        except OSError:
            log.warning('Could not launch verified update',exc_info=True)
            self.message='Could not start the installer. The application is still running. Try again.';self.refresh();return False
        self.message='Closing Keep Improving to install the verified update…';self.refresh()
        QTimer.singleShot(0,self.app.close)
        return True

    def open(self):
        self.app.settings_dialog()
        for area in self.app.settings_page.findChildren(QScrollArea):
            area.ensureWidgetVisible(self.card, 0, 0)
        if self.available: self.refresh()
        else: self.request(manual=True)

    def close(self):
        if self.closed: return
        self.closed = True; self.timer.stop()
        if self.worker is not None: self.worker.close()
        if self.download_worker is not None:self.download_worker.close()
