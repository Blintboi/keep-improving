"""Seven selectable days, safe group edits and one save with all settings."""
from dataclasses import replace
from PySide6.QtCore import Qt,QTime,Signal,QSize
from PySide6.QtWidgets import QFrame,QWidget,QVBoxLayout,QHBoxLayout,QAbstractSpinBox,QMenu
from .qt_translation import QLabel,QCheckBox
from .qt_widgets import label,button,glyph,NoWheelDoubleSpinBox,NoWheelTimeEdit,Disclosure
from .schedule import week_plans,DAY_NAMES
from .quota import current_day

DAY_SHORT=('Mon','Tue','Wed','Thu','Fri','Sat','Sun')
GAME_FIELDS=('limit_seconds','warning_seconds','restriction_enabled','restriction_seconds')
COMPUTER_FIELDS=('bedtime_enabled','bedtime_warning_enabled','bedtime_warning_minute','bedtime_minute','bedtime_resume_minute','bedtime_minimize','bedtime_caps_budget')


class DayCheckBox(QCheckBox):
    def nextCheckState(self):
        self.setCheckState(Qt.Unchecked if self.checkState()==Qt.Checked else Qt.Checked)


class WeeklyScheduleEditor(QFrame):
    selection_changed=Signal()
    def __init__(self,settings,t):
        super().__init__(); self.setObjectName('Panel'); self.t=t
        self.mode='games'; self._mode_selection={}
        self._plans=week_plans(settings); self._edits={}; self._loading=False; self._selected=set(); self._fields={}; self._mixed={}; self._groups={}
        layout=QVBoxLayout(self); layout.setContentsMargins(22,18,22,18); layout.setSpacing(12)
        self.title=label(t('Daily game time'),'section'); layout.addWidget(self.title)
        owner=self
        class SelectionLabel(QLabel):
            def _retranslate_extra(self,language): owner.update_summary()
        self.selection_label=SelectionLabel(); self.selection_label.setWordWrap(True); layout.addWidget(self.selection_label)
        self.difference=label('','muted'); self.difference.setWordWrap(True); layout.addWidget(self.difference)
        self.controls=QWidget(); form=QVBoxLayout(self.controls); form.setContentsMargins(0,0,0,0); form.setSpacing(12)
        row=QHBoxLayout(); row.setSpacing(18)
        self.limit=self.number_field(row,'limit_seconds','Daily limit (minutes)')
        self.warning=self.number_field(row,'warning_seconds','Warn after (minutes)'); form.addLayout(row)
        self.zero_limit_note=label(t('0 minutes: access is blocked.'),'muted'); self.zero_limit_note.setWordWrap(True); form.addWidget(self.zero_limit_note)
        self.day_details=Disclosure(t('Change days'))
        days=QHBoxLayout(); days.setSpacing(9); self.day_buttons=[]
        for day in range(7):
            item=button(t(DAY_SHORT[day]),lambda checked=False:self.select_checked(),'day'); item.setCheckable(True); item.setFixedSize(56,44)
            item.setAccessibleName(t(DAY_NAMES[day])); self.day_buttons.append(item); days.addWidget(item)
        days.addStretch(); self.day_details.body.addLayout(days)
        presets=QHBoxLayout()
        for title,indices in (('Every day',range(7)),('Weekdays',range(5)),('Weekend',(5,6))):
            presets.addWidget(button(t(title),lambda checked=False,values=tuple(indices):self.select_days(values),'quiet'))
        presets.addStretch(); self.day_details.body.addLayout(presets)
        self.unify=button(t('Use these values for all selected days'),self.unify_selected); self.day_details.body.addWidget(self.unify,0,Qt.AlignLeft)
        # Day selection stays enabled even when all days have been deselected.
        self.day_details.toggle.setText(t('Different settings by weekday')); self.day_details.setExpanded(False)
        layout.addWidget(self.day_details); layout.addWidget(self.controls)
        self.options=QWidget(); form=QVBoxLayout(self.options); form.setContentsMargins(0,0,0,0); form.setSpacing(12)
        layout.addWidget(self.options)
        self.details={}
        def detail(key,title):
            item=Disclosure(t(title)); self.details[key]=item; form.addWidget(item); return item.body
        restriction=detail('restriction','Play restriction')
        self.restriction_enabled=self.check_field(restriction,'restriction_enabled','Enable play restriction')
        self.restriction_controls=QWidget(); restriction_body=QVBoxLayout(self.restriction_controls); restriction_body.setContentsMargins(0,0,0,0)
        row=QHBoxLayout(); self.restriction_minutes=self.number_field(row,'restriction_seconds','Daily threshold (minutes)'); restriction_body.addLayout(row)
        note=label(t('10 seconds to save and quit before each minimization.'),'muted'); note.setWordWrap(True); restriction_body.addWidget(note)
        note.setToolTip(t('Protected games require separate minimization consent under Per-game countdowns. Without it, reminders remain available without interrupting the match.'))
        restriction.addWidget(self.restriction_controls)
        bedtime_section=detail('bedtime','Bedtime reminder')
        self.bedtime_enabled=self.check_field(bedtime_section,'bedtime_enabled','Active on selected days')
        self.bedtime_controls=QWidget(); bedtime=QVBoxLayout(self.bedtime_controls); bedtime.setContentsMargins(0,0,0,0); bedtime.setSpacing(10)
        row=QHBoxLayout(); self.bedtime_times={}
        for key,title in (('bedtime_minute','Period starts'),('bedtime_resume_minute','Period ends')):
            edit=NoWheelTimeEdit(); edit.setDisplayFormat('HH:mm'); edit.setButtonSymbols(QAbstractSpinBox.NoButtons); edit.setMinimumHeight(44); edit.setAccessibleName(t(title))
            self._fields[key]=edit; self.bedtime_times[key]=edit; self.field_group(row,key,title,edit)
            edit.timeChanged.connect(lambda value,k=key:self.change(k,value.hour()*60+value.minute()))
            self.track_typing(edit,key,lambda value:value.time().hour()*60+value.time().minute())
        bedtime.addLayout(row)
        bedtime.addWidget(label(t('Warnings and restrictions'),'section'))
        reminder=QFrame(); self.computer_warning_card=reminder; reminder.setObjectName('StepCard'); reminder.setAttribute(Qt.WA_StyledBackground)
        reminder_layout=QVBoxLayout(reminder); reminder_layout.setContentsMargins(16,14,16,14)
        heading=QHBoxLayout(); heading.addWidget(label(t('Warning'),'section'),1)
        remove_warning=button('',lambda:self.change('bedtime_warning_enabled',False),'quiet'); remove_warning.setIcon(glyph('trash')); remove_warning.setIconSize(QSize(20,20)); remove_warning.setFixedSize(40,40)
        remove_warning.setAccessibleName(t('Remove warning')); remove_warning.setToolTip(t('Remove warning')); heading.addWidget(remove_warning); reminder_layout.addLayout(heading)
        warning_row=QHBoxLayout()
        edit=NoWheelTimeEdit(); edit.setDisplayFormat('HH:mm'); edit.setButtonSymbols(QAbstractSpinBox.NoButtons); edit.setMinimumHeight(44); edit.setAccessibleName(t('Remind at'))
        self._fields['bedtime_warning_minute']=edit; self.bedtime_times['bedtime_warning_minute']=edit; self.field_group(warning_row,'bedtime_warning_minute','Remind at',edit)
        edit.timeChanged.connect(lambda value:self.change('bedtime_warning_minute',value.hour()*60+value.minute()))
        self.track_typing(edit,'bedtime_warning_minute',lambda value:value.time().hour()*60+value.time().minute())
        reminder_layout.addLayout(warning_row); bedtime.addWidget(reminder)
        restrict=QFrame(); self.computer_restriction_card=restrict; restrict.setObjectName('StepCard'); restrict.setAttribute(Qt.WA_StyledBackground)
        restrict_layout=QVBoxLayout(restrict); restrict_layout.setContentsMargins(16,14,16,14)
        heading=QHBoxLayout(); heading.addWidget(label(t('Restriction'),'section'),1)
        remove_restriction=button('',lambda:self.change('bedtime_minimize',False),'quiet'); remove_restriction.setIcon(glyph('trash')); remove_restriction.setIconSize(QSize(20,20)); remove_restriction.setFixedSize(40,40)
        remove_restriction.setAccessibleName(t('Remove restriction')); remove_restriction.setToolTip(t('Remove restriction')); heading.addWidget(remove_restriction); restrict_layout.addLayout(heading)
        self.bedtime_minimize=self.check_field(restrict_layout,'bedtime_minimize','Minimize the active window during this period')
        bedtime.addWidget(restrict)
        action_row=QHBoxLayout()
        self.add_computer_step=button(t('Add action'),self.choose_computer_step); self.add_computer_step.setIcon(glyph('plus')); action_row.addWidget(self.add_computer_step); action_row.addStretch(); bedtime.addLayout(action_row)
        advanced=Disclosure(t('More options')); bedtime.addWidget(advanced)
        self.bedtime_caps_budget=self.check_field(advanced.body,'bedtime_caps_budget','Cap remaining game time at bedtime')
        self.bedtime_caps_budget.setToolTip(t('Show the smaller of the unused daily budget and the time until bedtime. During the bedtime window, remaining time stays at zero until Resume at.'))
        note=label(t('Bedtime minimization also applies to browsers and other apps until the resume time.'),'muted'); note.setWordWrap(True)
        advanced.body.addWidget(note); self.bedtime_minimize_note=note
        bedtime_section.addWidget(self.bedtime_controls)
        self.details['bedtime'].toggle.hide(); self.details['bedtime'].setExpanded(True)
        identical=all(value==self._plans[0] for value in self._plans.values())
        self.select_days(range(7) if identical else (current_day(settings).weekday(),))
        self.set_mode('games')

    def choose_computer_step(self):
        menu=QMenu(self.add_computer_step)
        warning=menu.addAction(self.t('Warning'))
        restriction=menu.addAction(self.t('Minimize the active window during this period'))
        warning.setEnabled(bool(self._selected) and not all(self._plans[d]['bedtime_warning_enabled'] for d in self._selected))
        restriction.setEnabled(bool(self._selected) and not all(self._plans[d]['bedtime_minimize'] for d in self._selected))
        warning.triggered.connect(lambda:self.change('bedtime_warning_enabled',True))
        restriction.triggered.connect(lambda:self.change('bedtime_minimize',True))
        menu.setAttribute(Qt.WA_DeleteOnClose); menu.popup(self.add_computer_step.mapToGlobal(self.add_computer_step.rect().bottomLeft()))

    def field_group(self,row,key,title,edit):
        container=QWidget(); group=QVBoxLayout(container); group.setContentsMargins(0,0,0,0)
        self._groups[key]=container; heading=QHBoxLayout(); heading.addWidget(label(self.t(title),'muted'))
        mixed=label(self.t('Varies'),'muted'); mixed.setStyleSheet('color:#e8c583;'); self._mixed[key]=mixed; heading.addWidget(mixed); heading.addStretch()
        group.addLayout(heading); group.addWidget(edit); row.addWidget(container,1)

    def set_custom_steps(self,enabled):
        pass  # Legacy controls are presented as separate action blocks.

    def set_mode(self,mode):
        if mode not in ('games','computer'): raise ValueError('Invalid schedule mode.')
        if self.mode!=mode:
            self._mode_selection[self.mode]=set(self._selected); self.mode=mode
            self.select_days(self._mode_selection.get(mode,set(range(7))))
        self.title.setText(self.t('Daily game time' if mode=='games' else 'Computer use'))
        self.controls.setVisible(mode=='games'); self.options.setVisible(mode=='computer')
        self.details['restriction'].hide(); self.details['bedtime'].setVisible(mode=='computer'); self.update_summary(); self.update_enabled()

    def set_computer_enabled(self,enabled):
        for day in range(7):
            self._plans[day]['bedtime_enabled']=enabled
            self._edits.setdefault(day,{})['bedtime_enabled']=enabled
        self.load_selection(); self.selection_changed.emit()

    def restore_fields(self,settings,fields):
        source=week_plans(settings)
        for day in range(7):
            for key in fields:
                self._plans[day][key]=source[day][key]
                if day in self._edits: self._edits[day].pop(key,None)
            if day in self._edits and not self._edits[day]: self._edits.pop(day)
        self.load_selection(); self.selection_changed.emit()

    def number_field(self,row,key,title):
        edit=NoWheelDoubleSpinBox(); edit.setRange(0 if key=='limit_seconds' else .01,1440); edit.setDecimals(2); edit.setSingleStep(5); edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
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
        self.load_selection(); self.selection_changed.emit()

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
        self.selection_label.setText(self.t('Editing all days.') if self._selected==set(range(7)) else self.t('Editing: {days}',days=names) if names else self.t('Select at least one day to edit its schedule.'))
        fields=GAME_FIELDS if self.mode=='games' else COMPUTER_FIELDS
        mixed=self._selected and any(len({self._plans[day][key] for day in self._selected})>1 for key in fields)
        self.difference.setText(self.t('The selected days differ. Values shown are from {day}; only edited fields change on all selected days.',day=self.t(DAY_NAMES[min(self._selected)])) if mixed else self.t('The selected days use the same schedule.') if names else '')
        self.difference.setVisible(bool(mixed))
        self.unify.setVisible(bool(mixed))
        if self._selected: self.unify.setText(self.t("Use {day}'s schedule for selected days",day=self.t(DAY_NAMES[min(self._selected)])))

    def update_enabled(self):
        self.controls.setEnabled(bool(self._selected))
        usage=not hasattr(self,'usage_limit') or self.usage_limit.isChecked()
        self.limit.setEnabled(usage)
        self.zero_limit_note.setVisible(usage and any(self._plans[d]['limit_seconds']==0 for d in self._selected))
        self.warning.setEnabled(any(self._plans[d]['limit_seconds']>0 for d in self._selected))
        self.options.setEnabled(bool(self._selected))
        self.restriction_minutes.setEnabled(self.restriction_enabled.checkState()!=Qt.Unchecked)
        self.restriction_controls.setVisible(self.restriction_enabled.checkState()!=Qt.Unchecked)
        self.bedtime_controls.setEnabled(self.bedtime_enabled.checkState()!=Qt.Unchecked)
        self.bedtime_controls.setVisible(self.bedtime_enabled.checkState()!=Qt.Unchecked)
        self.bedtime_minimize_note.setVisible(self.bedtime_minimize.checkState()!=Qt.Unchecked)
        if self._selected:
            warning=any(self._plans[d]['bedtime_warning_enabled'] for d in self._selected)
            restriction=any(self._plans[d]['bedtime_minimize'] for d in self._selected)
            self.computer_warning_card.setVisible(warning); self.computer_restriction_card.setVisible(restriction)
            self.add_computer_step.setEnabled(not all(self._plans[d]['bedtime_warning_enabled'] and self._plans[d]['bedtime_minimize'] for d in self._selected))
        for key,title,field in (('restriction','Play restriction',self.restriction_enabled),('bedtime','Bedtime reminder',self.bedtime_enabled)):
            state=self.t('On') if field.checkState()==Qt.Checked else self.t('Off') if field.checkState()==Qt.Unchecked else self.t('Varies')
            self.details[key].toggle.setText(self.t('{setting} · {state}',setting=self.t(title),state=state))

    def change(self,key,value):
        if self._loading or not self._selected: return
        restored_warning=False
        for day in self._selected:
            was_zero=self._plans[day]['limit_seconds']==0
            self._plans[day][key]=value; self._edits.setdefault(day,{})[key]=value
            if key=='limit_seconds' and was_zero and value>0 and not 0<self._plans[day]['warning_seconds']<value:
                self._plans[day]['warning_seconds']=value*.8
                self._edits[day]['warning_seconds']=value*.8; restored_warning=True
            if key in ('bedtime_minute','bedtime_resume_minute'):
                plan=self._plans[day]
                warning=(plan['bedtime_minute']-plan['bedtime_warning_minute'])%1440
                duration=(plan['bedtime_resume_minute']-plan['bedtime_minute'])%1440
                if duration and (not warning or warning+duration>=1440) and duration<1435:
                    plan['bedtime_warning_minute']=(plan['bedtime_minute']-5)%1440
                    self._edits[day]['bedtime_warning_minute']=plan['bedtime_warning_minute']
        if restored_warning or key in ('bedtime_minute','bedtime_resume_minute','bedtime_warning_enabled','bedtime_minimize'): self.load_selection()
        if key in self._mixed: self._mixed[key].hide()
        self.update_summary(); self.update_enabled()
        self.selection_changed.emit()

    def unify_selected(self):
        if not self._selected: return
        values=dict(self._plans[min(self._selected)])
        for key in (GAME_FIELDS if self.mode=='games' else COMPUTER_FIELDS): self.change(key,values[key])
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
