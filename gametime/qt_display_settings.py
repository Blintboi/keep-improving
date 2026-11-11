"""Global display controls, kept in Settings and shared by all countdowns and notices."""
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtWidgets import QFrame,QVBoxLayout
from .qt_widgets import label,separator
from .qt_translation import QCheckBox


class DisplaySettings(QFrame):
    def __init__(self,app):
        super().__init__(); self.app=app
        self.setObjectName("Panel"); display_layout=QVBoxLayout(self); display_layout.setContentsMargins(18,14,18,14); display_layout.setSpacing(10)
        self.fullscreen=QCheckBox(app.t('Show over fullscreen games')); self.fullscreen.setAccessibleName(app.t('Show over fullscreen games'))
        display_layout.addWidget(self.fullscreen)
        self.protected=QCheckBox(app.t('Also show in anti-cheat games')); self.protected.setAccessibleName(app.t('Also show in anti-cheat games'))
        display_layout.addWidget(self.protected)
        self.display_note=label(app.t('Applies to countdowns and notifications.'),'muted'); self.display_note.setWordWrap(True); display_layout.addWidget(self.display_note)
        display_layout.addWidget(separator())
        self.details=QCheckBox(app.t('Detailed RTSS countdown')); self.details.setAccessibleName(app.t('Detailed RTSS countdown'))
        display_layout.addWidget(self.details)
        detail_note=label(app.t('Show the event name and daily budget remaining. Turn off to show only the countdown.'),'muted')
        detail_note.setWordWrap(True); display_layout.addWidget(detail_note)
        self.display_status=label('','muted'); self.display_status.setWordWrap(True); self.display_status.hide(); display_layout.addWidget(self.display_status)
        self.fullscreen.clicked.connect(self.toggle_fullscreen); self.protected.clicked.connect(self.toggle_protected)
        self.details.clicked.connect(self.toggle_details)
        self.refresh()

    def refresh(self):
        for widget,checked in ((self.fullscreen,self.app.settings.overlay_rtss_auto),(self.protected,self.app.overlay_consents.display_enabled),
                               (self.details,self.app.settings.overlay_rtss_details)):
            blocked=widget.blockSignals(True); widget.setChecked(checked); widget.blockSignals(blocked)

    def display_saved(self,enabled):
        self.app.apply_display_settings()
        message='If a game is already running, save and restart it after enabling this.' if enabled else ''
        if enabled and not self.app.rtss_available(): message='Install RTSS 7.3.7 or newer first.'
        self.display_status.setText(self.app.t(message) if message else ''); self.display_status.setVisible(bool(message))

    def toggle_fullscreen(self,enabled):
        try:
            settings=replace(self.app.settings,overlay_rtss_auto=enabled).validate()
            self.app.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
            self.display_saved(enabled)
        except (ValueError,OSError,SQLiteError): self.display_error()

    def toggle_protected(self,enabled):
        # Keep the switch off until the user has explicitly accepted and saved.
        self.refresh()
        if enabled:
            from .qt_overlay_consent import request_display_consent
            if not request_display_consent(self.app,self): return
        try:
            self.app.overlay_consents.set_display_enabled(enabled)
            self.display_saved(enabled)
        except (ValueError,OSError,SQLiteError): self.display_error()

    def toggle_details(self,enabled):
        try:
            settings=replace(self.app.settings,overlay_rtss_details=enabled).validate()
            self.app.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
            self.app.update_overlay(); self.refresh()
            self.display_status.clear(); self.display_status.hide()
        except (ValueError,OSError,SQLiteError): self.display_error()

    def display_error(self):
        self.refresh(); self.display_status.setText(self.app.t('Could not save settings. Try again.')); self.display_status.show()
