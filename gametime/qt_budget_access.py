"""Active weekdays and optional minute caps, drafted with the budget editor."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout
from .qt_widgets import label,button,panel
from .schedule import DAY_NAMES
from .qt_schedule import DAY_SHORT


class BudgetAccess:
    def __init__(self,editor):
        self.editor=editor; self.t=editor.app.t; self.loading=False
        self.saved(editor.app.settings)
        self.widget=panel(); box=QVBoxLayout(self.widget); box.setContentsMargins(22,16,22,18); box.setSpacing(10)
        heading=QHBoxLayout(); heading.addWidget(label(self.t('Active days for this budget'),'section')); heading.addStretch()
        heading.addWidget(button(self.t('Every day'),lambda:self.select(range(7)),'quiet')); box.addLayout(heading)
        row=QHBoxLayout(); row.setSpacing(8); self.days=[]
        for day in range(7):
            item=button(self.t(DAY_SHORT[day]),lambda checked=False:self.changed(),'day'); item.setCheckable(True); item.setFixedSize(56,44)
            item.setAccessibleName(self.t(DAY_NAMES[day])); self.days.append(item); row.addWidget(item)
        row.addStretch(); box.addLayout(row)
        self.widget.setToolTip(self.t('A selected day starts at this budget’s daily renewal time.'))
        self.none=label(self.t('This budget is inactive until you select a day.'),'muted'); self.none.setWordWrap(True); box.addWidget(self.none)

    def saved(self,settings):
        self.active_days=deepcopy(settings.budget_active_days); self.usage_limits=dict(settings.budget_usage_limits)
        self.changed_days=set(); self.changed_limits=set()

    def choose(self,key):
        self.loading=True
        values=self.active_days.get(key,list(range(7)))
        for day,item in enumerate(self.days): item.setChecked(day in values)
        enabled=self.usage_limits.get(key,True)
        self.editor.usage_limit.setChecked(enabled); self.editor.shared_usage_limit.setChecked(enabled)
        self.none.setVisible(not values); self.widget.setVisible(bool(key))
        self.loading=False

    def select(self,days):
        for day,item in enumerate(self.days): item.setChecked(day in days)
        self.changed()

    def changed(self):
        key=self.editor.current
        if self.loading or self.editor.loading or not key: return
        values=[day for day,item in enumerate(self.days) if item.isChecked()]
        if len(values)==7: self.active_days.pop(key,None)
        else: self.active_days[key]=values
        self.changed_days.add(key); self.none.setVisible(not values)

    def usage_changed(self,enabled):
        key=self.editor.current
        if self.loading or self.editor.loading or not key or key=='computer-window': return
        if enabled: self.usage_limits.pop(key,None)
        else: self.usage_limits[key]=False
        self.changed_limits.add(key); self.editor.controls(); self.editor.steps.refresh_state()

    def discard(self,key,settings):
        for destination,source,changed in ((self.active_days,settings.budget_active_days,self.changed_days),
                                           (self.usage_limits,settings.budget_usage_limits,self.changed_limits)):
            if key in source: destination[key]=deepcopy(source[key])
            else: destination.pop(key,None)
            changed.discard(key)

    def remove(self,key):
        self.active_days.pop(key,None); self.usage_limits.pop(key,None)
        self.changed_days.add(key); self.changed_limits.add(key)

    def values(self,base):
        result={}
        for field,draft,changed in (('budget_active_days',self.active_days,self.changed_days),('budget_usage_limits',self.usage_limits,self.changed_limits)):
            values=deepcopy(getattr(base,field))
            for key in changed:
                if key in draft: values[key]=deepcopy(draft[key])
                else: values.pop(key,None)
            result[field]=values
        return result
