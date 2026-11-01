"""Inline action blocks ordered by accumulated use, preserving legacy timing."""
from PySide6.QtCore import Qt,QSize,QTimer,QTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSizePolicy
from .qt_translation import QCheckBox,QLineEdit
from .qt_widgets import label,button,glyph,NoWheelComboBox,NoWheelDoubleSpinBox,NoWheelTimeEdit
from .restriction_policy import new_plan,step,KINDS,legacy_active,legacy_warning_active,legacy_restriction_active

NAMES={'notify':'Warning','minimize':'Minimize application / block website','cover':'Cover and mute / block website',
       'close':'Close application / browser tab','break':'Take a break','redirect':'Cover and mute / redirect website','restrict':'Restriction'}


class StepCard(QWidget):
    def __init__(self,owner,value):
        super().__init__(); self.owner=owner; self.value=value; self.setObjectName('StepCard'); self.setAttribute(Qt.WA_StyledBackground)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        t=owner.app.t; self.application_budget=owner.is_application_budget(); self.legacy_kind=None; self._defaulted_allowance=False
        box=QVBoxLayout(self); box.setContentsMargins(16,14,16,14); box.setSpacing(10)
        heading=QHBoxLayout(); self.number=label('','section'); heading.addWidget(self.number)
        self.kind=NoWheelComboBox(); self.kind.setAccessibleName(t('Step action'))
        for kind in ('notify','restrict','break'): self.kind.addItem(t(NAMES[kind]),kind)
        current=value['kind']
        if current=='cover': current='restrict'
        elif self.kind.findData(current)<0:
            scopes=owner.target_types()
            names={'app':{'close':'Close application','minimize':'Minimize application'},'site':{'close':'Close browser tab','minimize':'Blocking overlay'}}
            name=names[scopes[0]].get(current,NAMES[current]) if len(scopes)==1 else NAMES[current]
            self.legacy_kind=current; self.kind.addItem(t('Previous: {action}',action=t(name)),current)
            self.kind.view().setRowHidden(self.kind.count()-1,True)
        self.kind.setCurrentIndex(self.kind.findData(current)); heading.addWidget(self.kind,1)
        self.remove=button('',lambda:owner.remove_step(self),'quiet'); self.remove.setIcon(glyph('trash')); self.remove.setIconSize(QSize(20,20)); self.remove.setFixedSize(40,40)
        self.remove.setAccessibleName(t('Remove step')); self.remove.setToolTip(t('Remove step')); heading.addWidget(self.remove); box.addLayout(heading)
        choice=QHBoxLayout(); choice.addWidget(label(t('When should it happen?'),'muted'),1)
        self.time_mode=NoWheelComboBox(); self.time_mode.setAccessibleName(t('Action timing'))
        self.time_mode.addItem(t('After accumulated use'),'usage'); self.time_mode.addItem(t('At a daily time'),'clock')
        self.time_mode.setCurrentIndex(self.time_mode.findData(value.get('time_mode','usage'))); choice.addWidget(self.time_mode,2); box.addLayout(choice)
        timing=QHBoxLayout(); self.time_label=label(t('After use (minutes)'),'muted'); timing.addWidget(self.time_label,1)
        self.minutes=NoWheelDoubleSpinBox(); self.minutes.setDecimals(2); self.minutes.setRange(.01,1440); self.minutes.setKeyboardTracking(False)
        self.minutes.setAccessibleName(t('After use (minutes)')); self.minutes.setValue(max(.01,owner.step_time(value)/60)); timing.addWidget(self.minutes); box.addLayout(timing)
        self.clock_time=NoWheelTimeEdit(); self.clock_time.setDisplayFormat('HH:mm'); self.clock_time.setAccessibleName(t('Daily action time'))
        minute=value.get('clock_minute',22*60); self.clock_time.setTime(QTime(minute//60,minute%60)); timing.addWidget(self.clock_time)
        self.clock_note=label('','muted'); self.clock_note.setWordWrap(True); box.addWidget(self.clock_note)
        self.old_time=label(t('Previous timing is preserved. Change the minutes to use active-use timing.'),'muted'); self.old_time.setWordWrap(True); box.addWidget(self.old_time)
        self.convert_time=button(t('Use active-use timing'),lambda:self.time_changed(self.minutes.value()),'quiet'); box.addWidget(self.convert_time,0,Qt.AlignLeft)
        from .qt_step_targets import TargetFields
        self.targets={}
        for scope in owner.target_types():
            fields=TargetFields(self,scope); self.targets[scope]=fields; box.addWidget(fields)
        primary=next(iter(self.targets.values()))
        for name in ('sound','popup','extra','allowance','break_controls','break_mode','break_minutes','redirect_controls','redirect_url'):
            setattr(self,name,getattr(primary,name))
        self.hint=label(t('Breaks repeat after the same amount of use, only while time remains in the budget. The break ends after this time even in another application.'),'muted')
        self.hint.setWordWrap(True); box.addWidget(self.hint)
        self.consent=QCheckBox(t('I understand that closing can lose unsaved work.')); box.addWidget(self.consent)
        self.minutes.valueChanged.connect(self.time_changed); self.kind.currentIndexChanged.connect(self.kind_changed); self.kind.activated.connect(self.kind_changed)
        self.time_mode.currentIndexChanged.connect(self.timing_changed); self.time_mode.activated.connect(self.timing_changed); self.clock_time.timeChanged.connect(self.clock_changed)
        self.consent.toggled.connect(owner.consent_changed)
        self.sync_plan()

    def sync_plan(self):
        plan=self.owner.editor.restriction_plans[self.owner.key]
        blocked=self.consent.blockSignals(True); self.consent.setChecked(plan['close_confirmed']); self.consent.blockSignals(blocked)
        for fields in self.targets.values(): fields.sync()
        self.update_controls()

    def update_controls(self):
        clock=self.value.get('time_mode')=='clock'; legacy=self.value.get('time_mode') not in ('usage','clock'); t=self.owner.app.t
        self.old_time.setVisible(legacy); self.convert_time.setVisible(legacy)
        self.minutes.setVisible(not clock); self.clock_time.setVisible(clock); self.clock_note.setVisible(clock)
        self.time_label.setText(t('Daily action time' if clock else 'After use (minutes)'))
        if clock:
            renewal=self.owner.editor.reset_overrides.get(self.owner.key,self.owner.app.settings.budget_reset_minute)
            minute=self.value['clock_minute']; start=f'{renewal//60:02d}:{renewal%60:02d}'; end=f'{minute//60:02d}:{minute%60:02d}'
            text='Usable from {start} to {end}; restricted afterwards until the next renewal.' if self.value['kind'] not in ('notify','break') else 'The budget renews at {start}. This action happens at {end}.'
            self.clock_note.setText(t(text,start=start,end=end))
        for fields in self.targets.values(): fields.update_controls()
        self.hint.setVisible(self.value['kind']=='break')
        self.hint.setText(t('This break starts once on each selected day, at the chosen time.' if clock else
                           'Breaks repeat after the same amount of use, only while time remains in the budget. The break ends after this time even in another application.'))
        self.consent.setVisible(any(fields.needs_consent() for fields in self.targets.values()))

    def time_changed(self,value):
        self.value['offset']=value*60; self.value['time_mode']='usage'
        self.value.pop('clock_minute',None)
        blocked=self.time_mode.blockSignals(True); self.time_mode.setCurrentIndex(self.time_mode.findData('usage')); self.time_mode.blockSignals(blocked)
        self.update_controls(); self.owner.changed(); self.owner.queue_sort()

    def timing_changed(self,*args):
        if self.time_mode.currentData()=='clock': self.clock_changed(self.clock_time.time())
        else: self.time_changed(self.minutes.value())

    def clock_changed(self,value):
        self.value.update(time_mode='clock',clock_minute=value.hour()*60+value.minute(),offset=0)
        self.update_controls(); self.owner.changed(); self.owner.queue_sort()

    def kind_changed(self,*args):
        kind=self.kind.currentData()
        if kind is None: return
        old=self.value['kind']
        if kind=='restrict' and not self.application_budget: kind='cover'
        self.value['kind']=kind
        if kind!=old: self.value.pop('targets',None)
        if kind=='restrict' and old!='cover' and not self._defaulted_allowance:
            self._defaulted_allowance=True
            plan=self.owner.editor.restriction_plans[self.owner.key]
            if not plan['extension_minutes'] and not any(item is not self.value and item['kind'] in ('cover','minimize','restrict') for item in plan['steps']):
                self.owner.extra_changed(5)
        if self.legacy_kind and kind!=self.legacy_kind:
            index=self.kind.findData(self.legacy_kind)
            if index>=0:
                blocked=self.kind.blockSignals(True); self.kind.removeItem(index); self.kind.blockSignals(blocked)
            self.legacy_kind=None
        if kind=='break':
            if self.value.get('time_mode') not in ('usage','clock'): self.value.update(offset=self.minutes.value()*60,time_mode='usage')
            self.value.setdefault('break_mode','minimize'); self.value.setdefault('break_minutes',5)
        else:
            for key in ('break_mode','break_minutes','redirect_url'): self.value.pop(key,None)
        if kind!='notify' and self.value.get('time_mode')!='usage' and self.value['offset']<0:
            self.value.update(offset=self.minutes.value()*60,time_mode='usage')
        if kind=='notify' and not (self.value['sound'] or self.value['popup']): self.value['popup']=True
        self.sync_plan(); self.owner.changed(); self.owner.queue_sort()


class RestrictionBlocks(QWidget):
    def __init__(self,editor):
        super().__init__(); self.editor=editor; self.app=editor.app; self.key=None; self.cards=[]; self.loading=False
        self.sort_timer=QTimer(self); self.sort_timer.setSingleShot(True); self.sort_timer.timeout.connect(self.sort_cards)
        t=self.app.t; outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(12)
        outer.addWidget(label(t('Warnings and restrictions'),'section'))
        self.body=QWidget(); body=QVBoxLayout(self.body); body.setContentsMargins(0,0,0,0); body.setSpacing(10)
        self.rows=QVBoxLayout(); self.rows.setContentsMargins(0,0,0,0); self.rows.setSpacing(8); body.addLayout(self.rows)
        self.legacy_warning_card=self.legacy_card('Warning','warning_seconds',self.remove_legacy_warning)
        self.legacy_restrict_card=self.legacy_card('Minimize game','restriction_seconds',self.remove_legacy_restriction)
        self.legacy_single_card=self.single_legacy_card()
        self.empty=label('','muted'); self.empty.setWordWrap(True); body.addWidget(self.empty)
        actions=QHBoxLayout(); self.add_step=button(t('Add action'),lambda:self.add('notify'))
        self.add_step.setIcon(glyph('plus')); actions.addWidget(self.add_step)
        self.restore=button(t('Restore previous settings'),self.restore_legacy,'quiet'); actions.addWidget(self.restore)
        actions.addStretch(); body.addLayout(actions)
        outer.addWidget(self.body)
        self.editor.schedule.selection_changed.connect(self.schedule_changed)
        self.set_budget(None)

    def legacy_card(self,title,field,remove):
        card=QWidget(); card.setObjectName('StepCard'); card.setAttribute(Qt.WA_StyledBackground)
        box=QVBoxLayout(card); box.setContentsMargins(16,14,16,14); box.setSpacing(10)
        heading=QHBoxLayout(); card.number=label('','section'); heading.addWidget(card.number)
        heading.addWidget(label(self.app.t(title),'section'),1)
        trash=button('',remove,'quiet'); trash.setIcon(glyph('trash')); trash.setIconSize(QSize(20,20)); trash.setFixedSize(40,40)
        trash.setAccessibleName(self.app.t('Remove step')); trash.setToolTip(self.app.t('Remove step')); heading.addWidget(trash)
        box.addLayout(heading); box.addWidget(self.editor.schedule._groups[field]); self.rows.addWidget(card)
        card.hide(); return card

    def single_legacy_card(self):
        card=QWidget(); card.setObjectName('StepCard'); card.setAttribute(Qt.WA_StyledBackground)
        box=QVBoxLayout(card); box.setContentsMargins(16,14,16,14); box.setSpacing(10)
        heading=QHBoxLayout(); card.number=label('','section'); heading.addWidget(card.number)
        heading.addWidget(label(self.app.t('Restrict when the budget runs out'),'section'),1)
        trash=button('',self.remove_single_legacy,'quiet'); trash.setIcon(glyph('trash')); trash.setIconSize(QSize(20,20)); trash.setFixedSize(40,40)
        trash.setAccessibleName(self.app.t('Remove step')); trash.setToolTip(self.app.t('Remove step')); heading.addWidget(trash)
        box.addLayout(heading)
        card.note=label('','muted'); card.note.setWordWrap(True); box.addWidget(card.note); self.rows.addWidget(card); card.hide(); return card

    def remove_single_legacy(self):
        if not self.key: return
        if self.key.startswith('game:'):
            plan=self.editor.restriction_plans.get(self.key)
            if plan is None:
                plan=new_plan(legacy=True); self.editor.restriction_plans[self.key]=plan
            plan['legacy_enforce']=False; self.changed()
        else:
            rule=self.editor.rule(self.key)
            if rule: rule['enforce']=False
        self.refresh_state(); self.sort_cards()

    def schedule_changed(self):
        if self.key=='shared-games' and not self.loading:
            schedule=self.editor.schedule
            if not legacy_warning_active(self.editor.restriction_plans,self.key):
                adjusted=False
                for day in schedule._selected:
                    plan=schedule._plans[day]
                    if plan['limit_seconds']>0 and not 0<plan['warning_seconds']<plan['limit_seconds']:
                        plan['warning_seconds']=plan['limit_seconds']*.8
                        schedule._edits.setdefault(day,{})['warning_seconds']=plan['warning_seconds']; adjusted=True
                if adjusted: schedule.load_selection()
            for card in self.cards:
                if card.value.get('time_mode') not in ('usage','clock'):
                    blocked=card.minutes.blockSignals(True)
                    card.minutes.setValue(max(.01,self.step_time(card.value)/60))
                    card.minutes.blockSignals(blocked)
            self.refresh_state(); self.queue_sort()

    def remove_legacy_warning(self):
        if self.key!='shared-games': return
        plan=self.editor.restriction_plans.get(self.key)
        if plan is None:
            plan=new_plan(legacy=True); self.editor.restriction_plans[self.key]=plan
        plan['legacy_warning']=False; self.changed(); self.set_budget(self.key); self.editor.controls()

    def remove_legacy_restriction(self):
        if self.key=='shared-games': self.editor.schedule.change('restriction_enabled',False)

    def set_budget(self,key):
        self.loading=True; self.key=key
        plan=self.editor.restriction_plans.get(key)
        self.body.setVisible(bool(key)); self.setVisible(bool(key))
        for card in self.cards: self.rows.removeWidget(card); card.hide(); card.deleteLater()
        self.cards=[]
        if plan is not None:
            for value in plan['steps']: self._card(value)
        self.loading=False; self.refresh_state(); self.sort_cards()

    def restore_legacy(self):
        if self.loading or self.key not in self.editor.restriction_plans: return
        self.editor.restriction_plans.pop(self.key)
        self.editor.restriction_changed.add(self.key); self.set_budget(self.key); self.editor.controls()

    def changed(self):
        if not self.loading and self.key: self.editor.restriction_changed.add(self.key)

    def extra_changed(self,value):
        if not self.loading and self.key in self.editor.restriction_plans:
            self.editor.restriction_plans[self.key]['extension_minutes']=int(value); self.changed()
            for card in self.cards: card.sync_plan()

    def consent_changed(self,checked):
        if not self.loading and self.key in self.editor.restriction_plans:
            self.editor.restriction_plans[self.key]['close_confirmed']=checked; self.changed()
            for card in self.cards: card.sync_plan()

    def _card(self,value):
        card=StepCard(self,value); self.cards.append(card); self.rows.addWidget(card)

    def is_application_budget(self):
        if self.key=='shared-games' or self.key and self.key.startswith('game:'): return True
        rule=self.editor.rule(self.key)
        if not rule or not rule['members']: return True
        return any(m['kind'] in ('game','app') or m['kind']=='category' and m['value'] in ('games','apps') for m in rule['members'])

    def target_types(self):
        result=['app'] if self.is_application_budget() else []
        rule=self.editor.rule(self.key)
        if rule and any(m['kind']=='site' or m=={'kind':'category','value':'sites'} for m in rule['members']): result.append('site')
        return result or ['app']

    def add(self,kind):
        if not self.key: return
        plan=self.editor.restriction_plans.get(self.key)
        if plan is None:
            plan=new_plan(legacy=True); self.editor.restriction_plans[self.key]=plan; self.set_budget(self.key); self.editor.controls()
        if len(plan['steps'])>=20: return
        value=step(kind,self.base_limit(),sound=kind=='notify',popup=kind=='notify',usage=True)
        plan['steps'].append(value); self._card(value); self.changed(); self.sort_cards(); self.refresh_state()

    def remove_step(self,card):
        plan=self.editor.restriction_plans.get(self.key)
        if plan is None or card not in self.cards: return
        plan['steps'].remove(card.value); self.cards.remove(card); self.rows.removeWidget(card); card.hide(); card.deleteLater()
        self.changed(); self.sort_cards(); self.refresh_state()

    def base_limit(self):
        if self.key=='shared-games' and self.editor.schedule._selected:
            return self.editor.schedule._plans[min(self.editor.schedule._selected)]['limit_seconds']
        return self.editor.minutes.value()*60

    def step_time(self,value):
        if value.get('time_mode')=='clock':
            renewal=self.editor.reset_overrides.get(self.key,self.app.settings.budget_reset_minute)
            return ((value['clock_minute']-renewal)%1440)*60
        return value['offset'] if value.get('time_mode')=='usage' else max(0,self.base_limit()+value['offset'])

    def queue_sort(self):
        plan=self.editor.restriction_plans.get(self.key)
        if plan is not None: plan['steps'].sort(key=self.step_time)
        self.sort_timer.start(0)

    def sort_cards(self):
        plan=self.editor.restriction_plans.get(self.key)
        # Stable sorting preserves the order of simultaneous steps.
        if plan is not None:
            plan['steps'].sort(key=self.step_time)
            order={id(value):index for index,value in enumerate(plan['steps'])}
            self.cards.sort(key=lambda card:order[id(card.value)])
        ordered=[(self.step_time(card.value),card) for card in self.cards]
        if not self.legacy_single_card.isHidden(): ordered.append((self.base_limit(),self.legacy_single_card))
        schedule=self.editor.schedule
        if self.key=='shared-games' and schedule._selected:
            days=sorted(schedule._selected); first=schedule._plans[days[0]]
            if not self.legacy_warning_card.isHidden():
                ordered.append((first['warning_seconds'],self.legacy_warning_card))
            if not self.legacy_restrict_card.isHidden():
                active=next((schedule._plans[d] for d in days if schedule._plans[d]['restriction_enabled']),first)
                ordered.append((active['restriction_seconds'],self.legacy_restrict_card))
        for index,(_,card) in enumerate(sorted(ordered,key=lambda item:item[0])):
            self.rows.removeWidget(card); self.rows.addWidget(card); card.number.setText(str(index+1)+'.')

    def refresh_state(self):
        active=self.key in self.editor.restriction_plans
        shared=self.key=='shared-games'; schedule=self.editor.schedule
        warning=shared and legacy_warning_active(self.editor.restriction_plans,self.key) and bool(schedule._selected)
        restriction=shared and legacy_active(self.editor.restriction_plans,self.key) and any(schedule._plans[d]['restriction_enabled'] for d in schedule._selected)
        rule=self.editor.rule(self.key)
        single=(bool(self.key and self.key.startswith('game:') and legacy_restriction_active(self.editor.restriction_plans,self.key))
                or bool(rule and rule['enforce'] and legacy_active(self.editor.restriction_plans,self.key)))
        if hasattr(self.editor,'access') and not self.editor.access.usage_limits.get(self.key,True):
            warning=restriction=single=False
        self.legacy_warning_card.setVisible(bool(warning)); self.legacy_restrict_card.setVisible(bool(restriction)); self.legacy_single_card.setVisible(single)
        notes=[]; types=self.target_types()
        if 'app' in types: notes.append(self.app.t('At the budget limit, applications and games are minimized after 10 seconds.'))
        if 'site' in types: notes.append(self.app.t('At the budget limit, websites are blocked.'))
        self.legacy_single_card.note.setText('\n'.join(notes))
        self.body.setVisible(bool(self.key)); self.empty.setVisible(not self.cards and not warning and not restriction and not single)
        self.empty.setText(self.app.t('No actions yet.'))
        self.restore.setVisible(active)
        self.add_step.setEnabled(len(self.cards)<20)
        self.editor.schedule.set_custom_steps(bool(active and self.key=='shared-games'))
