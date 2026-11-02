"""One inline editor for every reminder, with recoverable unapplied changes."""
from PySide6.QtCore import Qt,QTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFileDialog
from .qt_translation import QLineEdit,QPlainTextEdit,QCheckBox
from .qt_widgets import label,button,panel,NoWheelComboBox,NoWheelTimeEdit,NoWheelDoubleSpinBox
from .notification_drafts import original
from .notification_rules import normalized,TRIGGERS,title,message,validate_item,validate_files
from .qt_notification_options import IconPicker,PomodoroFields
from .notification_text import default_notification_template
from .budget import quota_plan
from .quota import current_day
from .tracker import Alert


class NotificationEditor(QWidget):
    def __init__(self,page):
        super().__init__(); self.page=page; self.app=page.app; self.loading=True; self.key=None; self.new=False; self.template=''
        t=self.app.t; layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setAlignment(Qt.AlignTop)
        card=panel(); form=QVBoxLayout(card); form.setContentsMargins(22,20,22,22); form.setSpacing(12); layout.addWidget(card)
        heading=QHBoxLayout(); heading.addWidget(label(t('Title')),1)
        self.enabled=QCheckBox(t('Enabled')); heading.addWidget(self.enabled); form.addLayout(heading)
        self.title=QLineEdit(); self.title.setMaxLength(80); self.title.setAccessibleName(t('Title')); form.addWidget(self.title)
        form.addWidget(label(t('Message')))
        self.message=QPlainTextEdit(); self.message.setAccessibleName(t('Message')); self.message.setFixedHeight(110); form.addWidget(self.message)
        form.addWidget(label(t('Show notification'))); self.trigger=NoWheelComboBox(); self.trigger.setAccessibleName(t('Show notification'))
        for key,name in TRIGGERS.items(): self.trigger.addItem(t(name),key)
        form.addWidget(self.trigger)
        self.schedule=QWidget(); row=QHBoxLayout(self.schedule); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('Time'))); self.time=NoWheelTimeEdit(); self.time.setDisplayFormat('HH:mm'); self.time.setAccessibleName(t('Time')); row.addWidget(self.time); row.addStretch(); form.addWidget(self.schedule)
        self.count_box=QWidget(); row=QHBoxLayout(self.count_box); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('Completed focus rounds today'))); self.count=NoWheelDoubleSpinBox(); self.count.setDecimals(0); self.count.setRange(1,1000); self.count.setAccessibleName(t('Completed focus rounds today')); row.addWidget(self.count); row.addStretch(); form.addWidget(self.count_box)
        self.note=label('','muted'); self.note.setWordWrap(True); form.addWidget(self.note)
        form.addWidget(label(t('Icon'))); self.icons=IconPicker(t); self.icon=self.icons.path; form.addWidget(self.icons)
        form.addWidget(label(t('Notification button'))); self.action=NoWheelComboBox(); self.action.setAccessibleName(t('Notification button'))
        for key,name in (('none','No button'),('app','Open an application'),('pomodoro','Start Pomodoro')): self.action.addItem(t(name),key)
        form.addWidget(self.action)
        self.application=QWidget(); row=QHBoxLayout(self.application); row.setContentsMargins(0,0,0,0)
        self.application_path=QLineEdit(); self.application_path.setAccessibleName(t('Application path')); row.addWidget(self.application_path,1)
        row.addWidget(button(t('Choose application…'),self.browse_application)); form.addWidget(self.application)
        self.pomodoro=PomodoroFields(t); form.addWidget(self.pomodoro)
        self.action_note=label(t('You can adjust these times in the notification before starting. Uses your current focus blacklist.'),'muted'); self.action_note.setWordWrap(True); form.addWidget(self.action_note)
        self.auto_close=QCheckBox(t('Close automatically')); form.addWidget(self.auto_close)
        self.duration_box=QWidget(); row=QHBoxLayout(self.duration_box); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('Seconds until closing'))); self.duration=NoWheelDoubleSpinBox(); self.duration.setDecimals(0); self.duration.setRange(1,3600); self.duration.setAccessibleName(t('Seconds until closing')); row.addWidget(self.duration); row.addStretch(); form.addWidget(self.duration_box)
        self.duration_note=label(t('When turned off, the notification stays open until you close it.'),'muted'); self.duration_note.setWordWrap(True); form.addWidget(self.duration_note)
        self.hint=label(t('Optional placeholders: {remaining} = game minutes left, {minutes} = daily limit, {time} = reminder time, {bedtime} = bedtime. Other text stays as written.'),'muted'); self.hint.setWordWrap(True); form.addWidget(self.hint)
        actions=QHBoxLayout(); actions.addWidget(button(t('Preview message'),self.preview)); self.reset=button(t('Use default message'),self.reset_message)
        actions.addWidget(self.reset); actions.addStretch(); actions.addWidget(button(t('Cancel'),page.cancel_edit)); form.addLayout(actions)
        for signal in (self.title.textChanged,self.message.textChanged,self.trigger.currentIndexChanged,self.time.timeChanged,self.count.valueChanged,self.enabled.toggled,
                       self.icons.changed,self.action.currentIndexChanged,self.application_path.textChanged,self.pomodoro.changed,self.auto_close.toggled,self.duration.valueChanged): signal.connect(self.changed)

    def open(self,key,new=False):
        self.loading=True; self.key=key; self.new=new
        settings=self.page.draft_settings()
        item=normalized(original(settings,key) or dict(id=key.split(':',1)[1],title='',text='',minute=720,enabled=True,icon='preset:bell',timeout=20))
        self.template=item['template']; self.default_title=title(dict(item,title=''),self.app.t)
        self.default=default_notification_template(quota_plan(settings),self.template) if self.template else ''
        self.title.setText(item['title'] or (self.default_title if self.template else '')); self.message.setPlainText(item['text'] or self.default)
        self.trigger.setCurrentIndex(self.trigger.findData(item['trigger'])); self.time.setTime(QTime(item['minute']//60,item['minute']%60)); self.count.setValue(item['count'])
        self.enabled.setChecked(item['enabled']); self.icons.set_value(item['icon'])
        self.action.setCurrentIndex(self.action.findData(item['action']['kind'])); self.application_path.setText(item['action'].get('path','')); self.pomodoro.set_value(item['action'])
        self.auto_close.setChecked(item['timeout']!=0); self.duration.setValue(item['timeout'] or max(12,min(90,len(self.message.toPlainText())*75//1000)))
        self.loading=False; self.update_controls(); self.title.setFocus()
        if new: self.changed()

    def value(self):
        text=self.message.toPlainText(); heading=self.title.text(); kind=self.action.currentData()
        action={'kind':kind}
        if kind=='app': action['path']=self.application_path.text()
        elif kind=='pomodoro': action.update(self.pomodoro.value())
        from .notification_rules import BUILTIN_IDS
        ident=BUILTIN_IDS[self.key.split(':',1)[1]] if self.key.startswith('builtin:') else self.key.split(':',1)[1]
        return dict(id=ident,title='' if self.template and heading==self.default_title else heading,text='' if self.template and text==self.default else text,
                    icon=self.icons.value(),minute=self.time.time().hour()*60+self.time.time().minute(),enabled=self.enabled.isChecked(),trigger=self.trigger.currentData(),
                    count=int(self.count.value()),action=action,timeout=int(self.duration.value()) if self.auto_close.isChecked() else 0,template=self.template)

    def update_controls(self):
        trigger=self.trigger.currentData(); action=self.action.currentData(); t=self.app.t
        self.schedule.setVisible(trigger=='time'); self.count_box.setVisible(trigger=='pomodoros')
        notes={'time':'Appears once a day at the selected time while Keep Improving is running.',
               'startup':'Appears once each time Keep Improving starts. Saving a notification does not trigger it.',
               'pomodoros':'Counts completed focus rounds, not breaks. Uses the global day start and appears once per day.',
               'bedtime':'Follows the bedtime reminder time in your time budget.'}
        self.note.setText(t(notes.get(trigger,'Follows the shared game time budget.')))
        self.application.setVisible(action=='app'); self.pomodoro.setVisible(action=='pomodoro'); self.action_note.setVisible(action=='pomodoro')
        self.duration_box.setVisible(self.auto_close.isChecked()); self.duration_note.setVisible(not self.auto_close.isChecked())
        self.hint.setVisible(bool(self.template)); self.reset.setVisible(bool(self.template))

    def changed(self,*_):
        if not self.loading and self.key: self.update_controls(); self.page.record(self.key,self.value())

    def restore_previous(self):
        if self.key in self.before: self.page.changes[self.key]=self.before[self.key]
        else: self.page.changes.pop(self.key,None)

    def reset_message(self): self.message.setPlainText(self.default)

    def browse_application(self):
        from .qt_notification_applications import choose
        choose(self.app,self.application_path.text(),self.application_path.setText)

    def preview(self):
        try:
            item=self.value(); validate_item(item); validate_files(item)
            alert=Alert(current_day(self.app.settings).isoformat(),(),'scheduled',message(item,quota_plan(self.app.settings)),'',
                        title=title(item,self.app.t),icon=item['icon'],action=item['action'],timeout=item['timeout'])
            if not self.app.popup(alert): raise ValueError('Close the current alert before previewing another.')
        except ValueError as exc: self.page.show_error(str(exc))
