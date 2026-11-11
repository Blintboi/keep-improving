"""The same device selector in budget and notification forms."""
from copy import deepcopy
from dataclasses import replace
import uuid
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QScrollArea
from .qt_translation import QDialog,QLineEdit,QCheckBox
from .qt_widgets import label,button,NoWheelComboBox
from . import device_scopes


def devices(app):
    s=app.settings
    result=[(s.scope_device,(s.statistics_device_name or app.t('This device'))+' · '+app.t('This device'))]
    if s.statistics_sync_group:
        exists=app.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='statistics_devices'").fetchone()
        if exists:result.extend(app.store.db.execute('SELECT device_id,name FROM statistics_devices WHERE group_id=? ORDER BY name',(device_scopes.connection(s.statistics_sync_group),)))
    return list(dict(result).items())


class DeviceScope(QWidget):
    changed=Signal()
    def __init__(self,app,budget=False):
        super().__init__();self.app=app;self.budget=budget;self.original=None;self.loading=True
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0);box.setSpacing(8)
        box.addWidget(label(app.t('Devices'),'section'));row=QHBoxLayout();self.choice=NoWheelComboBox();self.choice.setAccessibleName(app.t('Devices'));row.addWidget(self.choice,1)
        row.addWidget(button(app.t('Device groups…'),self.groups,'quiet'));box.addLayout(row)
        self.note=label(app.t('Selected devices share one allowance. Offline totals use the last synchronization.') if budget else app.t('This notification appears on the selected devices.'),'muted');self.note.setWordWrap(True);box.addWidget(self.note)
        if budget:
            row=app.store.db.execute("SELECT value FROM settings WHERE key='device_rules_received_at'").fetchone()
            if row:
                from datetime import datetime
                box.addWidget(label(app.t('Last sync: {time}',time=datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d %H:%M')),'muted'))
        self.choice.activated.connect(self.select);self.set_value(None)

    def set_value(self,value):
        self.loading=True;self.original=deepcopy(value);self.choice.clear();s=self.app.settings
        for id,name in devices(self.app):self.choice.addItem(name,dict(mode='device',device=id))
        if s.statistics_sync_enabled and s.statistics_sync_group:
            self.choice.addItem(self.app.t('All linked devices'),dict(mode='all'))
            for id,g in s.device_groups.items():
                if g['connection']==device_scopes.connection(s.statistics_sync_group):self.choice.addItem(self.app.t('Group: {name}',name=g['name']),dict(mode='group',group=id))
        wanted=value or dict(mode='device',device=s.scope_device);index=-1
        for i in range(self.choice.count()):
            candidate=self.choice.itemData(i)
            if all(wanted.get(k)==v for k,v in candidate.items()):index=i;break
        if index<0:self.choice.addItem(self.app.t('Unavailable device or group'),wanted);index=self.choice.count()-1
        self.choice.setCurrentIndex(index);self.loading=False

    def select(self,*args):
        if self.loading:return
        self.original=device_scopes.normalize(self.choice.currentData(),self.app.settings,budget=self.budget);self.changed.emit()

    def value(self):return deepcopy(self.original)

    def groups(self):
        app=self.app;t=app.t;s=app.settings
        if not s.statistics_sync_enabled or not s.statistics_sync_group:
            self.note.setText(t('Connect your devices in Statistics before creating groups.'));return
        dialog=QDialog(self);dialog.setObjectName('Surface');dialog.setWindowTitle(t('Device groups'));dialog.resize(500,480)
        box=QVBoxLayout(dialog);box.setContentsMargins(24,20,24,20);choose=NoWheelComboBox();choose.addItem(t('New group'),None)
        for id,g in s.device_groups.items():
            if g['connection']==device_scopes.connection(s.statistics_sync_group):choose.addItem(g['name'],id)
        box.addWidget(choose);box.addWidget(label(t('Name')));name=QLineEdit();name.setMaxLength(80);box.addWidget(name)
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();members=QVBoxLayout(body);checks={}
        for id,title in devices(app):
            check=QCheckBox(title);checks[id]=check;members.addWidget(check)
        members.addStretch();scroll.setWidget(body);box.addWidget(scroll,1)
        note=label(t('Phones and computers can belong to the same group.'),'muted');note.setWordWrap(True);box.addWidget(note)
        error=label('','muted');error.setWordWrap(True);box.addWidget(error)
        def load():
            g=s.device_groups.get(choose.currentData(),{});name.setText(g.get('name',''))
            for id,check in checks.items():check.setChecked(id in g.get('devices',[]))
            remove.setEnabled(choose.currentData() is not None)
        choose.currentIndexChanged.connect(load)
        def save():
            try:
                id=choose.currentData() or uuid.uuid4().hex
                groups=deepcopy(app.settings.device_groups);groups[id]=dict(name=name.text().strip(),devices=[id for id,c in checks.items() if c.isChecked()],connection=device_scopes.connection(app.settings.statistics_sync_group))
                proposed=replace(app.settings,device_groups=groups).validate();app.store.save_settings(proposed);app.settings=app.catalog.settings=proposed
                app.schedule_statistics_event();dialog.accept();self.set_value(self.original)
            except ValueError as ex:error.setText(t(str(ex)))
        def delete():
            id=choose.currentData()
            if not id:return
            confirm=QDialog(dialog);confirm.setObjectName('Surface');confirm.setWindowTitle(t('Delete device group'));layout=QVBoxLayout(confirm)
            note=label(t('Rules using this group will become inactive. History will be kept.'));note.setWordWrap(True);layout.addWidget(note)
            actions=QHBoxLayout();actions.addWidget(button(t('Cancel'),confirm.reject));actions.addWidget(button(t('Delete'),confirm.accept,'danger-action'));layout.addLayout(actions)
            if confirm.exec()!=QDialog.Accepted:return
            groups=deepcopy(app.settings.device_groups);groups.pop(id,None);proposed=replace(app.settings,device_groups=groups).validate();app.store.save_settings(proposed);app.settings=app.catalog.settings=proposed;app.schedule_statistics_event();dialog.accept();self.set_value(self.original)
        row=QHBoxLayout();remove=button(t('Delete group'),delete,'danger-action');remove.setEnabled(False);row.addWidget(remove);row.addStretch();row.addWidget(button(t('Cancel'),dialog.reject));row.addWidget(button(t('Save'),save));box.addLayout(row)
        from .qt_ui import dark_window
        dark_window(dialog);dialog.exec()
