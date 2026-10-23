"""Seven selectable days, safe group edits and one save with all settings."""
from dataclasses import replace
from datetime import date
from PySide6.QtCore import Qt,QTime
from PySide6.QtWidgets import QFrame,QWidget,QVBoxLayout,QHBoxLayout,QAbstractSpinBox
from .qt_translation import QLabel,QCheckBox
from .qt_widgets import label,button,separator,NoWheelDoubleSpinBox,NoWheelTimeEdit
from .schedule import SCHEDULE_FIELDS,week_plans,DAY_NAMES

DAY_SHORT=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')


class DayCheckBox(QCheckBox):
    def nextCheckState(self):
        self.setCheckState(Qt.Unchecked if self.checkState()==Qt.Checked else Qt.Checked)


class WeeklyScheduleEditor(QFrame):
    def __init__(self,settings,t):
        super().__init__(); self.setObjectName('Panel'); self.t=t
        self._plans=week_plans(settings); self._edits={}; self._loading=False; self._selected=set(); self._fields={}; self._mixed={}; self._section_days=[]
        layout=QVBoxLayout(self); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(t('Weekly schedule'),'section'))
        note=label(t('Select one or more days. Changes apply to the selected days and take effect after Save.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
        days=QHBoxLayout(); days.setSpacing(9); self.day_buttons=[]
        for day in range(7):
            item=button(t(DAY_SHORT[day]),lambda checked=False:self.select_checked(),'day'); item.setCheckable(True); item.setFixedSize(56,44)
            item.setAccessibleName(t(DAY_NAMES[day])); self.day_buttons.append(item); days.addWidget(item)
        days.addStretch(); layout.addLayout(days)
        presets=QHBoxLayout()
        for title,indices in (('Every day',range(7)),('Weekdays',range(5)),('Weekend',(5,6)),('Clear selection',())):
            presets.addWidget(button(t(title),lambda checked=False,values=tuple(indices):self.select_days(values),'quiet'))
        presets.addStretch(); layout.addLayout(presets)
        owner=self
        class SelectionLabel(QLabel):
            def _retranslate_extra(self,language): owner.update_summary()
        self.selection_label=SelectionLabel(); self.selection_label.setWordWrap(True); layout.addWidget(self.selection_label)
        self.difference=label('','muted'); self.difference.setWordWrap(True); layout.addWidget(self.difference)
        self.unify=button(t('Use these values for all selected days'),self.unify_selected); layout.addWidget(self.unify,0,Qt.AlignLeft)
        self.controls=QWidget(); form=QVBoxLayout(self.controls); form.setContentsMargins(0,0,0,0); form.setSpacing(12)
        self.section(form,'Daily game time','The warning and the limit below belong to the selected days.')
        row=QHBoxLayout(); row.setSpacing(18)
        self.limit=self.number_field(row,'limit_seconds','Daily limit (minutes)')
        self.warning=self.number_field(row,'warning_seconds','Warn after (minutes)'); form.addLayout(row)
        self.section(form,'Play restriction','10 seconds to save and quit before each minimization.')
        note=label(t('Protected games require separate minimization consent under Per-game countdowns. Without it, reminders remain available without interrupting the match.'),'muted'); note.setWordWrap(True); form.addWidget(note)
        self.restriction_enabled=self.check_field(form,'restriction_enabled','Enable play restriction')
        row=QHBoxLayout(); self.restriction_minutes=self.number_field(row,'restriction_seconds','Daily threshold (minutes)'); row.addStretch(); form.addLayout(row)
        self.section(form,'Bedtime reminder','Local time. Overnight rules belong to the selected start day and continue until Resume at, including the next morning.')
        self.bedtime_enabled=self.check_field(form,'bedtime_enabled','Enable bedtime reminder')
        self.bedtime_controls=QWidget(); bedtime=QVBoxLayout(self.bedtime_controls); bedtime.setContentsMargins(0,0,0,0); bedtime.setSpacing(10)
        row=QHBoxLayout(); self.bedtime_times={}
        for key,title in (('bedtime_warning_minute','Remind at'),('bedtime_minute','Bedtime'),('bedtime_resume_minute','Resume at')):
            edit=NoWheelTimeEdit(); edit.setDisplayFormat('HH:mm'); edit.setButtonSymbols(QAbstractSpinBox.NoButtons); edit.setMinimumHeight(44); edit.setAccessibleName(t(title))
            self._fields[key]=edit; self.bedtime_times[key]=edit; self.field_group(row,key,title,edit)
            edit.timeChanged.connect(lambda value,k=key:self.change(k,value.hour()*60+value.minute()))
            self.track_typing(edit,key,lambda value:value.time().hour()*60+value.time().minute())
        bedtime.addLayout(row)
        self.bedtime_caps_budget=self.check_field(bedtime,'bedtime_caps_budget','Cap remaining game time at bedtime')
        note=label(t('Show the smaller of the unused daily budget and the time until bedtime. During the bedtime window, remaining time stays at zero until Resume at.'),'muted'); note.setWordWrap(True); bedtime.addWidget(note)
        self.bedtime_minimize=self.check_field(bedtime,'bedtime_minimize','Minimize the foreground window every 10 seconds after bedtime')
        note=label(t('Bedtime minimization also applies to browsers and other apps until the resume time.'),'muted'); note.setWordWrap(True); bedtime.addWidget(note)
        form.addWidget(self.bedtime_controls); layout.addWidget(self.controls)
        identical=all(value==self._plans[0] for value in self._plans.values())
        self.select_days(range(7) if identical else (date.today().weekday(),))

    def section(self,layout,title,note):
        layout.addWidget(separator()); heading=QHBoxLayout(); heading.addWidget(label(self.t(title),'section'),1)
        days=label('','muted'); days.setAccessibleName(self.t('Selected days')); self._section_days.append(days); heading.addWidget(days); layout.addLayout(heading)
        text=label(self.t(note),'muted'); text.setWordWrap(True); layout.addWidget(text)

    def field_group(self,row,key,title,edit):
        group=QVBoxLayout(); heading=QHBoxLayout(); heading.addWidget(label(self.t(title),'muted'))
        mixed=label(self.t('Varies'),'muted'); mixed.setStyleSheet('color:#e8c583;'); self._mixed[key]=mixed; heading.addWidget(mixed); heading.addStretch()
        group.addLayout(heading); group.addWidget(edit); row.addLayout(group,1)

    def number_field(self,row,key,title):
        edit=NoWheelDoubleSpinBox(); edit.setRange(.01,1440); edit.setDecimals(2); edit.setSingleStep(5); edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        edit.setAccessibleName(self.t(title)); self._fields[key]=edit; self.field_group(row,key,title,edit)
        edit.valueChanged.connect(lambda value:self.change(key,value*60)); self.track_typing(edit,key,lambda value:value.value()*60)
        return edit

    def check_field(self,layout,key,title):
        row=QHBoxLayout(); edit=DayCheckBox(self.t(title)); edit.setTristate(True); edit.setAccessibleName(self.t(title)); self._fields[key]=edit; row.addWidget(edit)
        mixed=label(self.t('Varies'),'muted'); mixed.setStyleSheet('color:#e8c583;'); self._mixed[key]=mixed; row.addWidget(mixed); row.addStretch(); layout.addLayout(row)
        edit.checkStateChanged.connect(lambda value:self.change(key,value==Qt.Checked))
        return edit

    def track_typing(self,edit,key,read):
        dirty=[False]
        edit.lineEdit().textEdited.connect(lambda text:dirty.__setitem__(0,True))
        def commit():
            if dirty[0]: dirty[0]=False; self.change(key,read(edit))
        edit.editingFinished.connect(commit)

    def select_checked(self): self.select_days(day for day,item in enumerate(self.day_buttons) if item.isChecked())

    def select_days(self,days):
        self._selected=set(days)
        for day,item in enumerate(self.day_buttons):
            blocked=item.blockSignals(True); item.setChecked(day in self._selected); item.blockSignals(blocked)
        self.load_selection()

    def load_selection(self):
        self._loading=True
        if self._selected:
            first=self._plans[min(self._selected)]
            for key,edit in self._fields.items():
                values={self._plans[day][key] for day in self._selected}
                if isinstance(edit,DayCheckBox): edit.setCheckState(Qt.PartiallyChecked if len(values)>1 else Qt.Checked if first[key] else Qt.Unchecked)
                elif isinstance(edit,NoWheelTimeEdit): edit.setTime(QTime(first[key]//60,first[key]%60))
                else: edit.setValue(first[key]/60)
                self._mixed[key].setVisible(len(values)>1)
        self._loading=False; self.update_summary(); self.update_enabled()

    def update_summary(self):
        if not hasattr(self,'selection_label'): return
        names=', '.join(str(self.t(DAY_NAMES[day])) for day in sorted(self._selected))
        self.selection_label.setText(self.t('Editing: {days}',days=names) if names else self.t('Select at least one day to edit its schedule.'))
        mixed=self._selected and any(len({self._plans[day][key] for day in self._selected})>1 for key in SCHEDULE_FIELDS)
        self.difference.setText(self.t('The selected days differ. Values shown are from {day}; only edited fields change on all selected days.',day=self.t(DAY_NAMES[min(self._selected)])) if mixed else self.t('The selected days use the same schedule.') if names else '')
        self.unify.setVisible(bool(mixed))
        if self._selected: self.unify.setText(self.t("Use {day}'s schedule for selected days",day=self.t(DAY_NAMES[min(self._selected)])))
        short=', '.join(str(self.t(DAY_SHORT[day])) for day in sorted(self._selected)) or '—'
        for caption in self._section_days: caption.setText(self.t('Days: {days}',days=short))

    def update_enabled(self):
        self.controls.setEnabled(bool(self._selected))
        self.restriction_minutes.setEnabled(self.restriction_enabled.checkState()!=Qt.Unchecked)
        self.bedtime_controls.setEnabled(self.bedtime_enabled.checkState()!=Qt.Unchecked)

    def change(self,key,value):
        if self._loading or not self._selected: return
        for day in self._selected:
            self._plans[day][key]=value; self._edits.setdefault(day,{})[key]=value
        self._mixed[key].hide(); self.update_summary(); self.update_enabled()

    def unify_selected(self):
        if not self._selected: return
        values=dict(self._plans[min(self._selected)])
        for key,value in values.items(): self.change(key,value)
        self.load_selection()

    def settings(self,base):
        if not self._edits: return base
        plans=week_plans(base)
        for day,edits in self._edits.items(): plans[day].update(edits)
        if all(value==plans[0] for value in plans.values()):
            return replace(base,weekend_enabled=False,weekend_schedule={},daily_schedules={},**plans[0])
        return replace(base,weekend_enabled=False,weekend_schedule={},daily_schedules={str(day):value for day,value in plans.items()})

    def saved(self,settings):
        self._plans=week_plans(settings); self._edits={}; self.load_selection()
