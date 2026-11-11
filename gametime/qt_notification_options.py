"""Styled notification icons, Pomodoro controls and explicit button actions."""
from dataclasses import replace
import ntpath
from pathlib import Path
import subprocess
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt,QSize,Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFileDialog,QSizePolicy
from .qt_translation import QToolButton,QLineEdit
from .qt_widgets import label,button,glyph,ACCENT,NoWheelComboBox,NoWheelDoubleSpinBox
from .notification_rules import ICONS,POMODORO,executable


def notification_icon(value,size=30,fallback='bell'):
    if value.startswith('preset:') and value[7:] in ICONS: return glyph(value[7:],ACCENT,size)
    icon=QIcon(value) if value else QIcon()
    return glyph(fallback,ACCENT,size) if icon.isNull() else icon


class IconPicker(QWidget):
    changed=Signal()
    def __init__(self,t):
        super().__init__(); self.t=t; self._value=''; self.loading=False
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); grid=QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(10); self.buttons={}
        for column in range(5): grid.setColumnStretch(column,1)
        for index,(name,text) in enumerate(ICONS.items()):
            item=QToolButton(); item.setText(t(text)); item.setIcon(glyph(name,ACCENT,28)); item.setIconSize(QSize(28,28))
            item.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); item.setMinimumHeight(76)
            item.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); item.setCheckable(True); item.setProperty('role','preset')
            item.setAccessibleName(t(text)); item.clicked.connect(lambda checked=False,n=name:self.select('preset:'+n))
            grid.addWidget(item,index//5,index%5); self.buttons[name]=item
        box.addLayout(grid); row=QHBoxLayout()
        self.path=QLineEdit(); self.path.setAccessibleName(t('Custom icon path')); row.addWidget(self.path,1)
        row.addWidget(button(t('Choose image…'),self.browse),0,Qt.AlignLeft); box.addLayout(row)
        self.path.textChanged.connect(self.path_changed)
    def value(self): return self._value
    def set_value(self,value):
        self.loading=True; self._value=value
        custom=bool(value and not value.startswith('preset:')); self.path.setText(value if custom else '')
        self.path.setVisible(custom)
        for name,item in self.buttons.items(): item.setChecked(value=='preset:'+name or not value and name=='bell')
        self.loading=False
    def select(self,value): self.set_value(value); self.changed.emit()
    def path_changed(self,value):
        if not self.loading:
            self._value=value
            for item in self.buttons.values(): item.setChecked(False)
            self.changed.emit()
    def browse(self):
        value,_=QFileDialog.getOpenFileName(self,self.t('Choose icon'),'',self.t('Images (*.png *.ico *.jpg *.jpeg *.bmp)'))
        if value: self.select(value)


class PomodoroFields(QWidget):
    changed=Signal()
    def __init__(self,t):
        super().__init__(); self.loading=False; self.inputs={}
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); box.setSpacing(8)
        self.presets=NoWheelComboBox(); self.presets.setAccessibleName(t('Pomodoro timing'))
        for title,value in (('25 / 5 / 15',dict(POMODORO)),('50 / 10 / 30',dict(work=50,short_break=10,long_break=30,rounds=4)),(t('Custom'),None)):
            self.presets.addItem(title,value)
        box.addWidget(self.presets); grid=QGridLayout(); grid.setHorizontalSpacing(16)
        for index,(key,name,maximum) in enumerate((('work','Focus (minutes)',240),('short_break','Short break (minutes)',60),('long_break','Long break (minutes)',120),('rounds','Rounds before a long break',12))):
            field=NoWheelDoubleSpinBox(); field.setDecimals(0); field.setRange(0,maximum); field.setValue(POMODORO[key]); field.setAccessibleName(t(name))
            grid.addWidget(label(t(name)),index//2*2,index%2); grid.addWidget(field,index//2*2+1,index%2)
            self.inputs[key]=field; field.valueChanged.connect(self.edited)
        box.addLayout(grid); self.presets.currentIndexChanged.connect(self.choose)
        hint=label(t('0-minute breaks are skipped. Set rounds to 0 for a single focus session, with no break or repetition.'),'muted')
        hint.setWordWrap(True); box.addWidget(hint)
    def value(self): return {key:int(field.value()) for key,field in self.inputs.items()}
    def set_value(self,value):
        self.loading=True
        for key,field in self.inputs.items(): field.setValue(value.get(key,POMODORO[key]))
        index=next((i for i in range(2) if self.presets.itemData(i)==self.value()),2); self.presets.setCurrentIndex(index)
        self.loading=False
    def choose(self):
        if self.loading: return
        value=self.presets.currentData()
        if value: self.set_value(value); self.changed.emit()
    def edited(self):
        if self.loading: return
        blocked=self.presets.blockSignals(True); self.presets.setCurrentIndex(2); self.presets.blockSignals(blocked); self.changed.emit()


def launch_application(path):
    path=executable(path)
    if not Path(path).is_file(): raise ValueError('Application file was not found.')
    # A local selected executable, no shell, command string, URL or arguments.
    return subprocess.Popen([path],cwd=str(Path(path).parent),shell=False)


def popup_action(app,window,layout,alert):
    action=alert.action or {}; kind=action.get('kind','none')
    if kind=='none': return 0
    t=app.t; fields=None
    if kind=='pomodoro':
        fields=PomodoroFields(t); fields.set_value(action); fields.ensurePolished()
        fields.setMinimumHeight(fields.sizeHint().height()); layout.addWidget(fields); window.pomodoro_fields=fields
        note=label(t('Uses your current focus blacklist. Starting replaces any paused timer.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
        fields.changed.connect(lambda:window.close_timer.stop())
    status=label('','muted'); status.setWordWrap(True); status.hide(); layout.addWidget(status); window.action_status=status
    def perform():
        window.close_timer.stop(); start.setEnabled(False)
        try:
            if kind=='app': launch_application(action['path']); result='Application opened.'
            else:
                if app.focus.running:
                    raise ValueError('A focus timer is already running. Stop it in Focus mode before starting a new one.')
                settings=replace(app.focus.settings,**fields.value()).validate()
                app.focus.configure(settings); app.focus.stop(); app.focus.start(app.focus_awake())
                app.update_focus_policy(); app.focus_page.refresh(force=True)
                window.close(); return
            status.setText(t(result)); status.show()
        except (ValueError,OSError,SQLiteError) as exc:
            status.setText(t(str(exc)) if isinstance(exc,ValueError) else t('Could not start the action. Try again.')); status.show(); start.setEnabled(True)
    row=QHBoxLayout(); row.addStretch()
    start=button(t('Start Pomodoro') if kind=='pomodoro' else t('Open {name}',name=ntpath.basename(action['path'])),perform,'primary')
    window.action_button=start; row.addWidget(start); row.addWidget(button(t('Close'),window.close)); layout.addLayout(row)
    return fields.sizeHint().height()+130 if fields else 75
