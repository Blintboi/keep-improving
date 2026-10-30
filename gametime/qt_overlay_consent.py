"""A deliberate confirmation, never preselected or implied by closing a dialog."""
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout
from .qt_translation import QDialog,QCheckBox
from .qt_widgets import label,button,separator
from .overlay_consent import NOTICE,MINIMIZE_NOTICE,DISPLAY_NOTICE


def request_display_consent(app,parent):
    window=QDialog(parent); window.setWindowTitle(app.t('Display in anti-cheat games')); window.resize(520,210)
    layout=QVBoxLayout(window); layout.setContentsMargins(22,20,22,18); layout.setSpacing(14)
    body=label(app.t(DISPLAY_NOTICE)); body.setWordWrap(True); layout.addWidget(body)
    check=QCheckBox(app.t('I understand and accept the risk.')); layout.addWidget(check)
    actions=QHBoxLayout(); actions.addStretch()
    cancel=button(app.t('Cancel'),window.reject); cancel.setDefault(True); actions.addWidget(cancel)
    accept=button(app.t('Enable at my own risk'),lambda:window.accept() if check.isChecked() else None,'primary')
    accept.setAutoDefault(False); accept.setEnabled(False); check.toggled.connect(accept.setEnabled); actions.addWidget(accept)
    layout.addLayout(actions)
    from .qt_ui import dark_window
    dark_window(window)
    return window.exec()==QDialog.Accepted and check.isChecked()


def request_consent(app,parent,game,*,minimization=False):
    window=QDialog(parent); window.setWindowTitle(app.t('Minimization risk consent' if minimization else 'Overlay risk consent')); window.resize(680,440)
    layout=QVBoxLayout(window); layout.setContentsMargins(24,24,24,24); layout.setSpacing(16)
    title=label(app.t('Allow automatic minimization for {name}?' if minimization else 'Enable overlay for {name}?',name=game.name),'section'); title.setWordWrap(True); layout.addWidget(title)
    body=label(app.t(MINIMIZE_NOTICE if minimization else NOTICE)); body.setWordWrap(True); layout.addWidget(body)
    scope=label(app.t('Applies only to this game and installation location on this computer, until revoked. Saved play-restriction and bedtime settings take effect after consent.' if minimization else 'Applies only to this game and installation location on this computer, until revoked. Saved countdown and RTSS settings take effect after consent.'),'muted'); scope.setWordWrap(True); layout.addWidget(scope)
    saved=label(app.t('Consent is saved immediately, separately from countdown settings.'),'muted'); saved.setWordWrap(True); layout.addWidget(saved)
    check=QCheckBox(app.t('I have read the notice and accept the risks.')); check.setChecked(False)
    check.setAccessibleName(app.t('I have read the notice and accept the risks.')); layout.addWidget(check)
    layout.addWidget(separator()); actions=QHBoxLayout(); actions.addStretch()
    cancel=button(app.t('Cancel'),window.reject); cancel.setDefault(True); actions.addWidget(cancel)
    accept=button(app.t('Enable at my own risk'),lambda:window.accept() if check.isChecked() else None,'primary')
    accept.setAutoDefault(False); accept.setEnabled(False); check.toggled.connect(accept.setEnabled); actions.addWidget(accept)
    layout.addLayout(actions)
    from .qt_ui import dark_window
    dark_window(window)
    return window.exec()==QDialog.Accepted and check.isChecked()
