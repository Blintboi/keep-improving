"""One fixed schedule per computer period; weekdays belong to the budget."""
from copy import deepcopy
from dataclasses import replace
import uuid
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout
from .qt_translation import QLineEdit
from .qt_widgets import label
from .qt_schedule import WeeklyScheduleEditor
from .computer_periods import FIELDS,project,split_weekly


def fixed_form(schedule):
    schedule.day_details.hide(); schedule.selection_label.hide(); schedule.difference.hide()
    schedule.bedtime_enabled.hide()
    schedule._fixed_budget=True
    schedule.select_days(range(7))


class PeriodEditor:
    def __init__(self,editor):
        self.editor=editor; self.items=deepcopy(editor.app.settings.computer_periods); self.key=None
        self.page=QWidget(); box=QVBoxLayout(self.page); box.setContentsMargins(0,0,0,0)
        self.name=QLineEdit(); self.name.setMaxLength(80); self.name.setAccessibleName(editor.app.t('Budget name')); box.addWidget(self.name)
        self.schedule=WeeklyScheduleEditor(editor.app.settings,editor.app.t); self.schedule.set_mode('computer'); fixed_form(self.schedule)
        box.addWidget(self.schedule)
        row=QHBoxLayout(); row.addWidget(label(editor.app.t('Renews daily at'),'muted'))
        self.reset=editor.reset_field(); row.addWidget(self.reset,1); box.addLayout(row)
        fixed_form(editor.schedule)
        source=editor.app.settings; normalized=split_weekly(source)
        self.migrated=normalized!=source
        if normalized!=source:
            editor.schedule.saved(normalized); editor.schedule._edits=deepcopy(editor.schedule._plans)
            editor.rules=deepcopy(normalized.wellbeing_rules); self.items=deepcopy(normalized.computer_periods)
            editor.computer_created=normalized.bedtime_enabled
            editor.restriction_plans=deepcopy(normalized.restriction_plans)
            editor.restriction_changed.update(set(source.restriction_plans)|set(normalized.restriction_plans))
            editor.reset_overrides=dict(normalized.budget_reset_overrides); editor.reset_changed.update(normalized.budget_reset_overrides)
            editor.access.active_days=deepcopy(normalized.budget_active_days); editor.access.changed_days.update(normalized.budget_active_days)
            editor.access.usage_limits=dict(normalized.budget_usage_limits); editor.access.changed_limits.update(normalized.budget_usage_limits)
        self.schedule.selection_changed.connect(self.collect)
        self.name.textEdited.connect(self.collect)

    def is_extra(self,key): return any(p['id']==key for p in self.items)
    def is_computer(self,key): return key=='computer-window' or self.is_extra(key)

    def create(self):
        key='computer-'+uuid.uuid4().hex
        values={field:getattr(self.editor.app.settings,field) for field in FIELDS}; values['bedtime_enabled']=True
        self.items.append(dict(id=key,name=str(self.editor.app.t('Computer use')),values=values))
        self.editor.refresh(key); self.editor.show_editor()

    def choose(self,key):
        self.key=None
        item=next(p for p in self.items if p['id']==key)
        self.name.setText(item['name']); self.schedule.saved(project(self.editor.app.settings,item)); self.schedule.select_days(range(7))
        minute=self.editor.reset_overrides.get(key,self.editor.app.settings.budget_reset_minute)
        self.reset.setTime(QTime(minute//60,minute%60)); self.key=key

    def collect(self):
        if self.editor.loading or self.editor.current!=self.key: return
        item=next((p for p in self.items if p['id']==self.key),None)
        if item:
            item['name']=self.name.text().strip()
            item['values']={k:self.schedule._plans[0][k] for k in FIELDS}

    def rows(self):
        t=self.editor.app.t; rows=[]
        for item in self.items:
            plan=item['values']; start=plan['bedtime_minute']; end=plan['bedtime_resume_minute']
            rows.append((item['id'],item['name'],t('Scheduled period'),f'{start//60:02d}:{start%60:02d}–{end//60:02d}:{end%60:02d}',plan['bedtime_enabled'],False))
        return rows

    def place_days(self):
        editor=self.editor; key=editor.current
        if self.is_extra(key): self.schedule.layout().insertWidget(1,editor.access.widget)
        elif key in ('shared-games','computer-window'): editor.schedule.layout().insertWidget(1,editor.access.widget)
        else: editor.detail_form.insertWidget(3,editor.access.widget)

    def saved(self,settings): self.items=deepcopy(settings.computer_periods); self.key=None

    def discard(self,key,settings):
        self.items=[p for p in self.items if p['id']!=key]
        saved=next((p for p in settings.computer_periods if p['id']==key),None)
        if saved: self.items.append(deepcopy(saved))
        self.editor.access.discard(key,settings)
        if key in settings.budget_reset_overrides: self.editor.reset_overrides[key]=settings.budget_reset_overrides[key]
        else: self.editor.reset_overrides.pop(key,None)
        self.editor.reset_changed.discard(key)
