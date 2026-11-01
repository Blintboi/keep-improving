"""Type-specific controls within one usage-triggered action card."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSizePolicy
from .qt_translation import QCheckBox,QLineEdit
from .qt_widgets import label,NoWheelComboBox,NoWheelDoubleSpinBox


class TargetFields(QWidget):
    def __init__(self,card,scope):
        super().__init__(); self.card=card; self.scope=scope; self.loading=True
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        t=card.owner.app.t
        outer=QVBoxLayout(self); outer.setContentsMargins(0,4,0,4); outer.setSpacing(10)
        self.enabled=QCheckBox(); outer.addWidget(self.enabled)
        self.body=QWidget(); self.body.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        box=QVBoxLayout(self.body); box.setContentsMargins(0,0,0,0); box.setSpacing(10); outer.addWidget(self.body)
        self.warnings=QWidget(); warning_row=QHBoxLayout(self.warnings); warning_row.setContentsMargins(0,0,0,0)
        self.sound=QCheckBox(t('Sound')); self.popup=QCheckBox(t('Popup'))
        warning_row.addWidget(self.sound); warning_row.addWidget(self.popup); warning_row.addStretch(); box.addWidget(self.warnings)
        self.regular=QWidget(); row=QHBoxLayout(self.regular); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('Action'),'muted'),1); self.mode=NoWheelComboBox(); self.mode.setAccessibleName(t('Application action' if scope=='app' else 'Website action'))
        choices=(('restrict','Close application'),) if scope=='app' else (('cover','Blocking overlay'),('redirect','Open another website'),('close','Close browser tab'))
        for value,name in choices: self.mode.addItem(t(name),value)
        row.addWidget(self.mode,2); box.addWidget(self.regular)
        self.break_controls=QWidget(); breaks=QVBoxLayout(self.break_controls); breaks.setContentsMargins(0,0,0,0); breaks.setSpacing(10)
        row=QHBoxLayout(); row.addWidget(label(t('During the break'),'muted'),1)
        self.break_mode=NoWheelComboBox(); self.break_mode.setAccessibleName(t('During the break'))
        choices=(('minimize','Minimize application'),('cover','Cover and mute'),('close','Close application')) if scope=='app' else (('cover','Blocking overlay'),('redirect','Open another website'),('close','Close browser tab'))
        for value,name in choices: self.break_mode.addItem(t(name),value)
        row.addWidget(self.break_mode,2); breaks.addLayout(row)
        row=QHBoxLayout(); row.addWidget(label(t('Break length (minutes)'),'muted'),1)
        self.break_minutes=NoWheelDoubleSpinBox(); self.break_minutes.setDecimals(0); self.break_minutes.setRange(1,1440)
        self.break_minutes.setAccessibleName(t('Break length (minutes)')); row.addWidget(self.break_minutes); breaks.addLayout(row); box.addWidget(self.break_controls)
        self.redirect_controls=QWidget(); row=QHBoxLayout(self.redirect_controls); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('Website address'),'muted'),1); self.redirect_url=QLineEdit(); self.redirect_url.setAccessibleName(t('Website address'))
        self.redirect_url.setPlaceholderText(t('Leave empty to open a new tab')); row.addWidget(self.redirect_url,2); box.addWidget(self.redirect_controls)
        self.allowance=QWidget(); row=QHBoxLayout(self.allowance); row.setContentsMargins(0,0,0,0)
        row.addWidget(label(t('One-time save allowance (minutes)'),'muted'),1)
        self.extra=NoWheelDoubleSpinBox(); self.extra.setDecimals(0); self.extra.setRange(0,60)
        self.extra.setAccessibleName(t('One-time save allowance (minutes)')); row.addWidget(self.extra); box.addWidget(self.allowance)
        self.note=label('','muted'); self.note.setWordWrap(True); box.addWidget(self.note)
        for widget,key,signal in ((self.enabled,'enabled','toggled'),(self.sound,'sound','toggled'),(self.popup,'popup','toggled'),
                                  (self.break_minutes,'break_minutes','valueChanged'),(self.extra,'extension_minutes','valueChanged'),
                                  (self.redirect_url,'redirect_url','textChanged')):
            getattr(widget,signal).connect(lambda value,key=key:self.change(key,value))
        self.mode.currentIndexChanged.connect(lambda:self.change('mode',self.mode.currentData()))
        self.break_mode.currentIndexChanged.connect(lambda:self.change('break_mode',self.break_mode.currentData()))
        self.sync()

    def sync(self):
        self.loading=True; value=self.card.value; plan=self.card.owner.editor.restriction_plans[self.card.owner.key]
        options=value.get('targets',{}).get(self.scope,{})
        self.enabled.setChecked(options.get('enabled',True))
        self.sound.setChecked(options.get('sound',value['sound'])); self.popup.setChecked(options.get('popup',value['popup']))
        mode=options.get('mode',value['kind'])
        if mode in ('notify','break'): mode='restrict' if self.scope=='app' else 'cover'
        if self.scope=='site' and mode in ('minimize','restrict'): mode='cover'
        if self.mode.findData(mode)<0:
            names={'minimize':'Minimize application','cover':'Cover and mute','close':'Close application'}
            self.mode.addItem(self.card.owner.app.t('Previous: {action}',action=self.card.owner.app.t(names[mode])),mode)
            self.mode.view().setRowHidden(self.mode.count()-1,True)
        self.mode.setCurrentIndex(self.mode.findData(mode))
        mode=options.get('break_mode',value.get('break_mode','minimize'))
        if self.scope=='app' and mode=='redirect' or self.scope=='site' and mode=='minimize': mode='cover'
        self.break_mode.setCurrentIndex(self.break_mode.findData(mode))
        self.break_minutes.setValue(options.get('break_minutes',value.get('break_minutes',5)))
        self.extra.setValue(options.get('extension_minutes',plan['extension_minutes']))
        self.redirect_url.setText(options.get('redirect_url',value.get('redirect_url','')))
        self.loading=False; self.update_controls()

    def change(self,key,value):
        if self.loading or value is None: return
        if key in ('extension_minutes','break_minutes'): value=int(value)
        if key=='redirect_url': value=value.strip()
        card=self.card; item=card.value
        # Keep unchanged single-type plans compatible with their original schema.
        basic=len(card.targets)==1 and 'targets' not in item
        if basic and key=='extension_minutes': card.owner.extra_changed(value); return
        if basic and key in ('sound','popup','break_mode','break_minutes','redirect_url'):
            item[key]=value
            if key=='break_mode':
                if value=='redirect': item.setdefault('redirect_url','')
                else: item.pop('redirect_url',None)
        else:
            if 'targets' not in item:
                item['targets']={scope:{'enabled':False} for scope in ('app','site') if scope not in card.targets}
            options=item['targets'].setdefault(self.scope,{})
            options[key]=value
            if key in ('mode','break_mode'):
                if value=='redirect': options.setdefault('redirect_url','')
                else: options.pop('redirect_url',None)
        card.owner.changed(); card.update_controls()

    def update_controls(self):
        item=self.card.value; kind=item['kind']; t=self.card.owner.app.t
        active=self.enabled.isChecked(); self.body.setEnabled(active)
        is_break=kind=='break'; notice=kind=='notify'
        titles={'site': ('Warn when using websites','Pause websites','Restrict websites'),
                'app': ('Warn when using applications and games','Pause applications and games','Restrict applications and games')}
        self.enabled.setText(t(titles[self.scope][0 if notice else 1 if is_break else 2]))
        self.enabled.setToolTip(t('Apply this action to websites in this budget.' if self.scope=='site' else
                                  'Apply this action to applications and games in this budget.'))
        mode=self.break_mode.currentData() if is_break else self.mode.currentData()
        self.warnings.setVisible(notice); self.regular.setVisible(not notice and not is_break and (self.scope=='site' or self.mode.count()>1))
        self.break_controls.setVisible(is_break)
        self.redirect_controls.setVisible(not notice and self.scope=='site' and mode=='redirect')
        saving=not notice and ((self.scope=='app' and (not is_break or mode=='close')) or (self.scope=='site' and not is_break and mode=='cover'))
        self.allowance.setVisible(saving)
        if notice: note=''
        elif self.scope=='site':
            if mode=='redirect': note='Websites in this budget open the chosen address; leave it empty to open a new tab.'
            elif mode=='close': note='The affected browser tab closes.'
            elif is_break: note='A blocking overlay remains until this break ends.'
            elif self.extra.value()>0: note='Websites: a blocking overlay appears. If you request save time, the website is usable until the overlay returns.'
            else: note='Websites: a blocking overlay immediately prevents use, with no save allowance.'
        elif is_break and mode!='close':
            note='Applications and games are minimized until this break ends.' if mode=='minimize' else 'Applications and games are covered and muted until this break ends.'
        elif self.extra.value()>0: note='Applications and games: close now or request the one-time save allowance above. They close automatically when it ends.'
        elif mode=='minimize': note='Applications and games: minimized, with no save allowance.'
        elif mode=='cover': note='Applications and games: covered and muted, with no save allowance.'
        else: note='Applications and games: close immediately, with no save allowance.'
        self.note.setText(t(note)); self.note.setVisible(bool(note))

    def needs_consent(self):
        if not self.enabled.isChecked() or self.card.value['kind']=='notify': return False
        is_break=self.card.value['kind']=='break'
        mode=self.break_mode.currentData() if is_break else self.mode.currentData()
        return mode in ('close','restrict') or not self.allowance.isHidden() and self.extra.value()>0
