"""Nonactivating update notice and explicit browser download, without auto-install."""
import logging
from sqlite3 import Error as SQLiteError
import time
import webbrowser
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
        self.notice_download = button(self.app.t('Download update'), self.download)
        row.addWidget(self.notice_download); row.addWidget(button(self.app.t('Later'), self.dismiss, 'quiet'))
        self.notice.hide()
        return self.notice

    def settings_panel(self):
        self.card = panel(); layout = QVBoxLayout(self.card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(self.app.t('Application updates'),'section'))
        layout.addWidget(label(self.app.t('Installed version: {version}',version=__version__),'muted'))
        self.automatic = QCheckBox(self.app.t('Check for updates automatically (once a day)'))
        self.automatic.setChecked(self.app.settings.check_updates); layout.addWidget(self.automatic)
        note = label(self.app.t('Checks the public GitHub version list. Downloads start only when you click Download update in your browser; installation is always your choice.'),'muted')
        note.setWordWrap(True); layout.addWidget(note)
        self.status = label('','muted'); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout(); self.check = button(self.app.t('Check for updates'), lambda:self.request(manual=True))
        self.download_button = button(self.app.t('Download update'), self.download)
        row.addWidget(self.check); row.addWidget(self.download_button); row.addStretch(); layout.addLayout(row)
        self.refresh()
        return self.card

    def refresh(self):
        release = self.available
        if hasattr(self, 'notice'):
            self.notice_text.setText(self.app.t('Version {version} is available.',version=release.version) if release else '')
            self.notice.setVisible(bool(release and self.state.dismissed != release.version))
        if hasattr(self, 'status'):
            feedback = self.message in ('Could not check for updates. Try again later.', 'Checked recently. Try again in a minute.',
                                        'The installer download has opened in your browser.', 'Could not open the download. Try again later.')
            text = (self.app.t('Version {version} is available.',version=release.version) if release and not self.pending and not feedback else
                    self.app.t(self.message) if self.message else self.app.t('Automatic update checks are enabled.' if self.app.settings.check_updates else 'Automatic update checks are off.'))
            self.status.setText(text)
            self.check.setEnabled(not self.pending and self.worker is not None)
            self.download_button.setVisible(release is not None)
            self.download_button.setEnabled(not self.pending)
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
        if self.closed or self.worker is None: return
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
        if not self.available: return False
        try:
            if not webbrowser.open(DOWNLOAD_URL, new=2): raise OSError('Browser unavailable')
            self.message = 'The installer download has opened in your browser.'
            return True
        except (OSError, webbrowser.Error):
            log.warning('Could not open the official installer download',exc_info=True)
            self.message = 'Could not open the download. Try again later.'
            return False
        finally:
            self.refresh()

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
