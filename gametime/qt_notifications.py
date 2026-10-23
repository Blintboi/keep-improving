"""Edit local reminder messages without changing budgets or alert delivery."""
from dataclasses import replace
from datetime import date
import math
from sqlite3 import Error as SQLiteError
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout
from .qt_translation import QPlainTextEdit
from .qt_widgets import label,button,NoWheelComboBox
from .notification_text import KINDS,MAX_MESSAGE_LENGTH,notification_text,default_notification_template
from .tracker import Alert
from .schedule import day_settings


def messages_dialog(app):
    from .qt_ui import dark_window
    t=app.t; window=app._dialog(t('Custom messages'),700); window.resize(700,540)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(12)
    intro=label(t('Edit the default message or write your own. Time placeholders update automatically.'),'muted')
    intro.setWordWrap(True); layout.addWidget(intro)
    layout.addWidget(label(t('Reminder type'),'section'))
    kinds=NoWheelComboBox(); kinds.setAccessibleName(t('Reminder type'))
    for kind,title in zip(KINDS,('Before the daily limit','Daily limit reached','Playing again after the limit','Bedtime reminder')): kinds.addItem(t(title),kind)
    layout.addWidget(kinds)
    # Translate untouched defaults in place; never replace a personal draft or
    # its selection when the main window changes language.
    class MessageEditor(QPlainTextEdit):
        def _retranslate_extra(self,language): refresh_default()
    editor=MessageEditor(); editor.setAccessibleName(t('Personal message')); editor.setPlaceholderText(t('Leave blank for the default message.'))
    editor.setTabChangesFocus(True); editor.setMinimumHeight(180); layout.addWidget(editor,1)
    count=label('','muted'); layout.addWidget(count)
    hint=label(t('Optional placeholders: {remaining} = game minutes left, {minutes} = daily limit, {time} = reminder time, {bedtime} = bedtime. Other text stays as written.'),'muted')
    hint.setWordWrap(True); layout.addWidget(hint)
    error=label('','danger'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    drafts={key:value for key,value in app.settings.notification_messages.items() if value.strip()}; current=[None]
    def update_count():
        count.setText(t('{count}/1000 characters',count=len(editor.toPlainText())))
    def edited():
        text=editor.toPlainText(); kind=current[0]
        if text.strip() and text!=default_notification_template(day_settings(app.settings),kind): drafts[kind]=text
        else: drafts.pop(kind,None)
        update_count()
        error.hide()
    def choose(*args):
        current[0]=kinds.currentData(); blocked=editor.blockSignals(True)
        editor.setPlainText(drafts.get(current[0],default_notification_template(day_settings(app.settings),current[0])))
        editor.blockSignals(blocked); update_count(); error.hide()
    def refresh_default():
        if current[0] not in drafts: choose()
        else: update_count()
    def reset():
        drafts.pop(current[0],None); choose(); editor.setFocus()
    editor.textChanged.connect(edited); kinds.currentIndexChanged.connect(choose); choose()
    def settings():
        return replace(app.settings,notification_messages={key:value for key,value in drafts.items() if value.strip()}).validate()
    def preview():
        try: value=day_settings(settings())
        except ValueError as exc: error.setText(t(str(exc))); error.show(); return
        kind=current[0]; remaining=None
        if kind=='bedtime' and '{remaining}' in drafts.get(kind,''):
            remaining=max(0,math.ceil((value.limit_seconds-sum(app.tracker.totals(date.today()).values()))/60))
        text=notification_text(value,kind,remaining)
        alert=Alert(date.today().isoformat(),(),kind,text,t('OK, I’ll finish' if kind=='bedtime' else 'OK' if kind=='warning' else 'OK, I’ll stop'))
        if not app.popup(alert): error.setText(t('Close the current alert before previewing another.')); error.show()
    def save():
        try:
            value=settings(); app.store.save_settings(value); app.settings=app.catalog.settings=value
            app.set_status('Messages saved.'); window.accept()
        except (OSError,ValueError,SQLiteError) as exc:
            error.setText(t(str(exc)) if isinstance(exc,ValueError) else t('Could not save messages. Try again.')); error.show()
    actions=QHBoxLayout(); actions.addWidget(button(t('Preview message'),preview))
    actions.addWidget(button(t('Use default message'),reset)); actions.addStretch()
    actions.addWidget(button(t('Cancel'),window.reject)); actions.addWidget(button(t('Save'),save,'primary')); layout.addLayout(actions)
    window.show(); dark_window(window); editor.setFocus()
