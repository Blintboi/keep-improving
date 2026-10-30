"""A new profile starts without budgets unless its owner creates one."""
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QWidget
from .qt_translation import QCheckBox
from .qt_widgets import label,button,NoWheelDoubleSpinBox


def budget_setup(app):
    if app.settings.budget_setup_completed: app._budget_setup_pending=False; return
    window=app._dialog(app.t('Your first time budget'),580); window._personalization_kind='budget-setup'
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(18)
    layout.addWidget(label(app.t('Start with what matters to you'),'section'))
    note=label(app.t('Create individual budgets or shared groups for games, applications and websites on the Time budgets page.'),'muted')
    note.setWordWrap(True); layout.addWidget(note)
    games=QCheckBox(app.t('Create a shared budget for all games')); games.setAccessibleName(app.t('Create a shared budget for all games')); layout.addWidget(games)
    fields=QWidget(); row=QHBoxLayout(fields); row.setContentsMargins(0,0,0,0)
    row.addWidget(label(app.t('Daily limit (minutes)')))
    minutes=NoWheelDoubleSpinBox(); minutes.setRange(1,1440); minutes.setDecimals(0); minutes.setValue(120)
    minutes.setAccessibleName(app.t('Daily limit (minutes)')); row.addWidget(minutes,1); layout.addWidget(fields)
    fields.hide(); games.toggled.connect(fields.setVisible)
    hint=label(app.t('Without this group, games have no automatic limit. You can create a budget for anything later.'),'muted'); hint.setWordWrap(True); layout.addWidget(hint)
    error=label('','danger'); error.setWordWrap(True); layout.addWidget(error)
    def finish():
        try:
            value=replace(app.settings,budget_setup_completed=True,game_budget_enabled=games.isChecked())
            if games.isChecked():
                value=replace(value,limit_seconds=minutes.value()*60,warning_seconds=minutes.value()*48,overlay_enabled=True)
            app.store.save_settings(value); app.settings=app.catalog.settings=value
            app.schedule_editor.saved(value); app.budget_editor.saved(value)
            app.overlay_enabled.setChecked(value.overlay_enabled)
            window.accept(); app.open_budget()
        except (ValueError,OSError,SQLiteError): error.setText(app.t('Could not save settings. Try again.'))
    layout.addWidget(button(app.t('Get started'),finish,'primary'),0,Qt.AlignRight)
    window.finished.connect(lambda *_:setattr(app,'_budget_setup_pending',False))
    window.show(); window.raise_(); window.activateWindow()
