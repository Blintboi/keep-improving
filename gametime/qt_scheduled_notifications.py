"""Editor for locally scheduled daily notifications."""
from dataclasses import replace
from pathlib import Path
import uuid
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt,QTime
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QFileDialog
from .qt_translation import QLineEdit,QPlainTextEdit,QCheckBox
from .qt_widgets import label,button,back_button,NoWheelComboBox,NoWheelTimeEdit
from .scheduled_notifications import validate_notifications
from .tracker import Alert
from .quota import current_day


def dialog(app,initial_id=None,*,single=False):
    from .qt_ui import dark_window
    t=app.t; window=app._dialog(t('Scheduled notifications'),700); window.resize(700,650)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(10)
    layout.addWidget(back_button(t,window.reject),0,Qt.AlignLeft)
    note=label(t('Notifications appear every day at the selected time while the app is running.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
    fullscreen_note=label(t('In exclusive fullscreen, notifications use the enabled RTSS overlay when the game permits it. Otherwise they wait until they can be shown.'),'muted'); fullscreen_note.setWordWrap(True); layout.addWidget(fullscreen_note)
    layout.addWidget(button(t('In-game notifications (RTSS)…'),app.rtss_dialog,'quiet'),0,Qt.AlignLeft)
    chooser=NoWheelComboBox(); chooser.setAccessibleName(t('Scheduled notifications')); layout.addWidget(chooser)
    chooser.setVisible(not single)
    layout.addWidget(label(t('Title'))); title=QLineEdit(); title.setMaxLength(80); title.setAccessibleName(t('Title')); layout.addWidget(title)
    layout.addWidget(label(t('Message'))); message=QPlainTextEdit(); message.setAccessibleName(t('Message')); message.setMaximumHeight(130); layout.addWidget(message)
    row=QHBoxLayout(); row.addWidget(label(t('Time'))); time=NoWheelTimeEdit(); time.setDisplayFormat('HH:mm'); time.setAccessibleName(t('Time')); row.addWidget(time)
    enabled=QCheckBox(t('Enabled')); row.addWidget(enabled); row.addStretch(); layout.addLayout(row)
    layout.addWidget(label(t('Icon (optional)'))); iconrow=QHBoxLayout(); icon=QLineEdit(); icon.setAccessibleName(t('Icon (optional)')); iconrow.addWidget(icon,1)
    def browse():
        path,_=QFileDialog.getOpenFileName(window,t('Choose icon'),'',t('Images (*.png *.ico *.jpg *.jpeg *.bmp)'))
        if path: icon.setText(path)
    iconrow.addWidget(button(t('Browse…'),browse)); layout.addLayout(iconrow)
    error=label('','danger'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    items=[dict(item) for item in app.settings.scheduled_notifications]; current=[None]
    def refresh(select=None):
        chooser.blockSignals(True); chooser.clear()
        for item in items: chooser.addItem(item['title'],item['id'])
        chooser.setCurrentIndex(next((i for i,x in enumerate(items) if x['id']==select),-1))
        chooser.blockSignals(False); load()
    def load(*args):
        current[0]=chooser.currentData(); item=next((x for x in items if x['id']==current[0]),None)
        title.setText(item['title'] if item else ''); message.setPlainText(item['text'] if item else '')
        icon.setText(item['icon'] if item else ''); time.setTime(QTime(item['minute']//60,item['minute']%60) if item else QTime(12,0))
        enabled.setChecked(item['enabled'] if item else True); error.hide()
    chooser.currentIndexChanged.connect(load)
    def value():
        item={'id':current[0] or uuid.uuid4().hex,'title':title.text().strip(),'text':message.toPlainText(),
              'icon':icon.text().strip(),'minute':time.time().hour()*60+time.time().minute(),'enabled':enabled.isChecked()}
        validate_notifications([item]); return item
    def save():
        try:
            item=value()
            if item['icon'] and not Path(item['icon']).is_file(): raise ValueError(t('Icon file was not found.'))
            updated=[dict(x) for x in app.settings.scheduled_notifications if x['id']!=item['id']]+[item]
            settings=replace(app.settings,scheduled_notifications=updated).validate(); app.store.save_settings(settings)
            app.settings=app.catalog.settings=settings; items[:]=updated; refresh(item['id']); app.set_status('Scheduled notification saved.')
            if single: window.accept()
        except (ValueError,OSError,SQLiteError) as exc: error.setText(t(str(exc))); error.show()
    def remove():
        if not current[0]: return
        try:
            updated=[dict(x) for x in app.settings.scheduled_notifications if x['id']!=current[0]]
            settings=replace(app.settings,scheduled_notifications=updated).validate(); app.store.save_settings(settings)
            app.settings=app.catalog.settings=settings; items[:]=updated; refresh(); app.set_status('Scheduled notification deleted.')
            if single: window.accept()
        except (ValueError,OSError,SQLiteError) as exc: error.setText(t(str(exc))); error.show()
    def preview():
        try:
            item=value()
            if not app.popup(Alert(current_day(app.settings).isoformat(),(),'scheduled',item['text'],'',title=item['title'],icon=item['icon'])):
                raise ValueError(t('Close the current alert before previewing another.'))
        except ValueError as exc: error.setText(str(exc)); error.show()
    actions=QHBoxLayout()
    if not single: actions.addWidget(button(t('New'),lambda:refresh()))
    if not single or initial_id: actions.addWidget(button(t('Delete'),remove))
    actions.addWidget(button(t('Preview message'),preview)); actions.addStretch(); actions.addWidget(button(t('Save'),save,'primary')); layout.addLayout(actions)
    refresh(initial_id); window.show(); dark_window(window)
    return window
