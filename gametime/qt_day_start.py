"""One local-time boundary for history, quotas and daily reminders."""
from dataclasses import replace
from datetime import datetime
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QAbstractSpinBox
from .qt_widgets import label,button,NoWheelTimeEdit
from .quota import current_day
from .schedule import bedtime_occurrence


def apply_day_start(app,previous,wall=None):
    if previous.budget_reset_minute==app.settings.budget_reset_minute: return
    wall=wall or datetime.now().astimezone()
    old_day=current_day(previous,wall).isoformat(); new_day=current_day(app.settings,wall).isoformat()
    if hasattr(app,'restrictions'): app.restrictions.state.move_day(old_day,new_day)
    keys=[key for key in app.store.alert_keys(old_day) if key.startswith('scheduled:')]
    if keys: app.store.mark_alert(new_day,keys)
    old_state,old_night,_=bedtime_occurrence(previous,wall)
    new_state,new_night,_=bedtime_occurrence(app.settings,wall)
    if old_state!='off' and new_state!='off':
        keys=[key for key in app.store.alert_keys(old_night) if key.startswith('bedtime:')]
        if keys: app.store.mark_alert(new_night,keys)
        if hasattr(app,'bedtime'): app.bedtime.ledger=None
    app.focus.configure_day_start(app.settings.budget_reset_minute)
    app.tracker.configure_budget(wall); app.tracker.previous=None
    app.wellbeing.configure(wall)
    app._scheduled_day=None; app._wellbeing_alert_day=None
    app._wellbeing_grace=None; app._restriction_grace=None


def day_start_dialog(app):
    from .qt_ui import dark_window
    t=app.t; window=app._dialog(t('Day starts at'),500)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(14)
    note=label(t('Statistics and all daily budgets start a new day at this time.'))
    note.setWordWrap(True); layout.addWidget(note)
    edit=NoWheelTimeEdit(); edit.setObjectName('DayStartTime'); edit.setDisplayFormat('HH:mm')
    edit.setAccessibleName(t('Day starts at')); edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
    minute=app.settings.budget_reset_minute; edit.setTime(QTime(minute//60,minute%60)); layout.addWidget(edit)
    note=label(t('Earlier statistics stay unchanged.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
    error=label('','error'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    def save():
        try:
            previous=app.settings
            minute=edit.time().hour()*60+edit.time().minute()
            settings=replace(previous,budget_reset_minute=minute).validate()
            app.tracker.flush(); app.focus.flush(); app.wellbeing.flush()
            app.store.save_settings(settings); app.settings=app.catalog.settings=settings
            apply_day_start(app,previous)
            app.update_focus_policy(); app.tracker.evaluate(datetime.now().astimezone())
            app.last_rows=None; app.render(); app.statistics.refresh(live=True)
            app.notifications_page.refresh(); app.set_status('Settings saved.')
            window.accept()
        except (ValueError,OSError,SQLiteError) as exc:
            error.setText(t(str(exc))); error.show()
    row=QHBoxLayout(); row.addStretch()
    row.addWidget(button(t('Save'),save,'primary')); row.addWidget(button(t('Cancel'),window.reject))
    layout.addLayout(row); window.show(); dark_window(window)
    return window
