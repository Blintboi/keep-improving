"""One editor for category, individual and mixed shared budgets."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import ntpath
import uuid
from PySide6.QtCore import Qt,QSize,QTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QStackedLayout,QListWidget,QListWidgetItem,QFileDialog,QSizePolicy,QLayout,QAbstractSpinBox
from .qt_translation import QDialog,QLineEdit,QCheckBox
from .qt_widgets import label,button,back_button,panel,glyph,NoWheelComboBox,NoWheelDoubleSpinBox,NoWheelTimeEdit,duration
from .wellbeing import target,validate_rules
from .activities import known_activities
from .activity_identity import canonical_member,activity_key
from .qt_scroll import preserving,position,restore


def new_rule(name,members,identity=None):
    return dict(id=identity or uuid.uuid4().hex,name=name,members=deepcopy(members),seconds=3600,
                enabled=False,enforce=False,overlay=True)


class BudgetLayout(QStackedLayout):
    """Hidden editors must not reserve space in the current list or form."""
    def sizeHint(self): return self.currentWidget().sizeHint() if self.currentWidget() else super().sizeHint()
    def minimumSize(self): return self.currentWidget().minimumSizeHint() if self.currentWidget() else super().minimumSize()
    def hasHeightForWidth(self): return bool(self.currentWidget() and self.currentWidget().hasHeightForWidth())
    def heightForWidth(self,width): return self.currentWidget().heightForWidth(width) if self.currentWidget() else -1


class BudgetStack(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); pages=BudgetLayout(self); pages.setSizeConstraint(QLayout.SetNoConstraint)
        pages.currentChanged.connect(self.updateGeometry)
    def addWidget(self,widget): return self.layout().addWidget(widget)
    def currentWidget(self): return self.layout().currentWidget()
    def currentIndex(self): return self.layout().currentIndex()
    def setCurrentIndex(self,index): self.layout().setCurrentIndex(index)


class TimeBudgets(QWidget):
    def __init__(self,app,schedule):
        super().__init__(); self.app=app; self.schedule=schedule; self.loading=False; self.current=None
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        self.rules=deepcopy(app.settings.wellbeing_rules); self.game_limits=dict(app.settings.game_limits); self.original_game_limits=dict(self.game_limits)
        self.restriction_plans=deepcopy(app.settings.restriction_plans); self.restriction_changed=set()
        self.game_overlays=deepcopy(app.settings.game_overlays); self.draft_games=set(); self.game_overlay_changed=set()
        self.counter_overlays=deepcopy(app.settings.counter_overlays); self.counter_overlay_changed=set(); self.shared_overlay={}
        self.member_overlay_drafts={}
        self.reset_overrides=dict(app.settings.budget_reset_overrides); self.reset_changed=set()
        self.shared_enabled=app.settings.game_budget_enabled; self.shared_created=self.shared_enabled
        self.computer_created=any(plan['bedtime_enabled'] for plan in schedule._plans.values())
        self.categories={key:new_rule(name,[target('category',key)],'category-'+key) for key,name in (('apps','Applications'),('sites','Websites'))}
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(10); layout.setAlignment(Qt.AlignTop)
        self.views=BudgetStack(); layout.addWidget(self.views)
        overview=QWidget(); listing=QVBoxLayout(overview); listing.setContentsMargins(0,0,0,0); listing.setSpacing(14); listing.setAlignment(Qt.AlignTop)
        header=QHBoxLayout(); note=label(app.t('Your individual and shared budgets, all in one place.'),'muted'); note.setWordWrap(True)
        header.addWidget(note,1)
        self.add_computer=button(app.t('Add computer-use period'),self.create_computer); header.addWidget(self.add_computer)
        self.add_button=button(app.t('Add new'),self.create_new,'primary'); header.addWidget(self.add_button); listing.addLayout(header)
        self.rows_widget=QWidget(); self.rows_layout=QVBoxLayout(self.rows_widget); self.rows_layout.setContentsMargins(0,0,0,0); self.rows_layout.setSpacing(10); self.rows_layout.setAlignment(Qt.AlignTop)
        listing.addWidget(self.rows_widget); self.row_keys=[]; self._rows_signature=None
        self.empty=label(app.t('No budgets yet. Add one for a game, application, website or a group.'),'muted'); self.empty.setWordWrap(True); listing.addWidget(self.empty)
        self.views.addWidget(overview)
        editor=QWidget(); edit_layout=QVBoxLayout(editor); edit_layout.setContentsMargins(0,0,0,0); edit_layout.setSpacing(12); edit_layout.setAlignment(Qt.AlignTop)
        # Stable identities for the editor; the public navigation is the list.
        self.selector=NoWheelComboBox(self); self.selector.hide()
        self.stack=BudgetStack(); edit_layout.addWidget(self.stack)
        from .qt_restriction_steps import RestrictionBlocks
        self.steps=RestrictionBlocks(self); edit_layout.addWidget(self.steps)
        self.views.addWidget(editor)
        shared=QWidget(); box=QVBoxLayout(shared); self.shared_layout=box; box.setContentsMargins(0,0,0,0); box.setAlignment(Qt.AlignTop)
        box.addWidget(schedule)
        self.shared_reset_panel=panel(); shared_reset_layout=QHBoxLayout(self.shared_reset_panel)
        shared_reset_layout.addWidget(label(app.t('Renews daily at'),'muted'))
        self.shared_reset=self.reset_field(); shared_reset_layout.addWidget(self.shared_reset,1)
        self.shared_reset_panel.hide(); self.stack.addWidget(shared)
        detail=panel(); form=QVBoxLayout(detail); form.setContentsMargins(22,20,22,22); form.setSpacing(14); form.setAlignment(Qt.AlignTop)
        self.name=QLineEdit(); self.name.setMaxLength(80); self.name.setAccessibleName(app.t('Budget name')); form.addWidget(self.name)
        self.members_note=label('','muted'); self.members_note.setWordWrap(True); form.addWidget(self.members_note)
        self.members_button=button(app.t('Edit members…'),self.edit_members); form.addWidget(self.members_button,0,Qt.AlignLeft)
        self.limit_fields=QWidget(); fields=QHBoxLayout(self.limit_fields); fields.setContentsMargins(0,0,0,0)
        self.usage_limit=QCheckBox(app.t('Daily limit (minutes)')); self.usage_limit.setAccessibleName(app.t('Use a daily minute limit')); fields.addWidget(self.usage_limit)
        self.minutes=NoWheelDoubleSpinBox(); self.minutes.setRange(0,1440); self.minutes.setDecimals(2)
        self.minutes.setAccessibleName(app.t('Daily limit (minutes)')); fields.addWidget(self.minutes,1); form.addWidget(self.limit_fields)
        self.minutes.valueChanged.connect(lambda *_:self.steps.queue_sort() if not self.loading and self.steps.key and self.steps.key not in ('shared-games','computer-window') else None)
        self.zero_limit_note=label(app.t('0 minutes: access is blocked.'),'muted'); self.zero_limit_note.setWordWrap(True); form.addWidget(self.zero_limit_note)
        self.minutes.valueChanged.connect(self.controls)
        self.overlay=QCheckBox(app.t('Show countdown while active')); form.addWidget(self.overlay)
        self.appearance=button(app.t('Countdown settings…'),self.edit_countdown,'quiet')
        form.addWidget(self.appearance,0,Qt.AlignLeft)
        self.usage=label('','muted'); self.usage.setWordWrap(True); form.addWidget(self.usage)
        self.reset_time=self.reset_field(); self.reset_time.setParent(self); self.reset_time.hide()
        self.tracking=button(app.t('Enable application and website measurement'),self.enable_tracking)
        form.addWidget(self.tracking,0,Qt.AlignLeft)
        self.error=label('','danger'); self.error.setWordWrap(True); form.addWidget(self.error); self.error.hide()
        self.stack.addWidget(detail)
        self.shared_usage_limit=QCheckBox(app.t('Use a daily minute limit'))
        self.schedule.usage_limit=self.shared_usage_limit
        self.schedule.controls.layout().insertWidget(0,self.shared_usage_limit)
        from .qt_budget_access import BudgetAccess
        self.access=BudgetAccess(self); edit_layout.insertWidget(1,self.access.widget)
        self.detail_form=form
        from .qt_budget_periods import PeriodEditor
        self.periods=PeriodEditor(self)
        self.conflicts=label('','muted'); self.conflicts.setStyleSheet('color:#e8c583;'); self.conflicts.setWordWrap(True)
        edit_layout.insertWidget(0,self.conflicts); self.conflicts.hide()
        self.usage_limit.toggled.connect(self.access.usage_changed); self.shared_usage_limit.toggled.connect(self.access.usage_changed)
        empty=panel(); empty_layout=QVBoxLayout(empty); empty_layout.setContentsMargins(22,24,22,24); empty_layout.setAlignment(Qt.AlignTop)
        empty_layout.addWidget(label(app.t('Start with a budget'),'section'))
        empty_note=label(app.t('Set a daily budget for one game, application or website, or let several share a group budget. You can add a countdown to each budget.'),'muted')
        empty_note.setWordWrap(True); empty_layout.addWidget(empty_note); self.stack.addWidget(empty)
        self.stack.addWidget(self.periods.page)
        self.overlay.toggled.connect(self.controls)
        self.name.textChanged.connect(self.rename)
        self.selector.currentIndexChanged.connect(self.choose)
        self.refresh('shared-games')
        self.views.setCurrentIndex(0)
        from .qt_budget_drafts import BudgetDrafts
        self.drafts=BudgetDrafts(self)

    def reset_field(self):
        edit=NoWheelTimeEdit(); edit.setDisplayFormat('HH:mm'); edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
        edit.setAccessibleName(self.app.t('Renews daily at'))
        edit.timeChanged.connect(self.changed_reset)
        return edit

    def changed_reset(self,value):
        pass  # Renewal is configured once in global Settings.

    def toggle_shared(self):
        self.schedule.show()
        if hasattr(self,'shared_countdown'):
            self.shared_countdown.hide(); self.shared_appearance.setVisible(self.current=='shared-games')

    def attach_shared_countdown(self,checkbox,appearance):
        self.shared_countdown=checkbox; checkbox.setParent(self); checkbox.hide()
        self.shared_appearance=button(self.app.t('Countdown settings…'),self.show_shared_appearance,'quiet')
        self.shared_layout.addWidget(self.shared_appearance,0,Qt.AlignLeft)
        checkbox.toggled.connect(lambda *_:self.toggle_shared()); self.toggle_shared()
        appearance.setParent(self); appearance.hide()

    def show_shared_appearance(self):
        self.edit_countdown()

    def show_editor(self,key=None):
        if self.views.currentIndex()==0 and hasattr(self.app,'budget_scroll'):self._list_scroll=position(self.app.budget_scroll)
        self.collect()
        if key is not None: self.refresh(key)
        self.views.setCurrentIndex(1)
        if hasattr(self.app,'budget_scroll'): restore(self.app.budget_scroll,0)

    def show_list(self):
        if self.views.currentIndex()==0 and hasattr(self.app,'budget_scroll'):self._list_scroll=position(self.app.budget_scroll)
        if hasattr(self,'drafts'): self.drafts.remember()
        self.collect()
        self.current=None; self.refresh(); self.views.setCurrentIndex(0)
        if hasattr(self,'drafts'): self.drafts.flush()
        if hasattr(self.app,'budget_scroll'): restore(self.app.budget_scroll,getattr(self,'_list_scroll',0))

    def cancel_edit(self):
        """Discard this budget's draft, retaining drafts for other budgets."""
        key=self.current; settings=self.app.settings
        if hasattr(self,'drafts'): self.drafts.raw.pop(key,None)
        if self.periods.is_extra(key):
            self.periods.discard(key,settings); self.current=None; self.refresh(); self.views.setCurrentIndex(0)
            self.drafts.flush(); return
        self.access.discard(key,settings)
        self.member_overlay_drafts.pop(key,None)
        if key in settings.restriction_plans: self.restriction_plans[key]=deepcopy(settings.restriction_plans[key])
        else: self.restriction_plans.pop(key,None)
        self.restriction_changed.discard(key)
        if key in settings.budget_reset_overrides: self.reset_overrides[key]=settings.budget_reset_overrides[key]
        else: self.reset_overrides.pop(key,None)
        self.reset_changed.discard(key)
        self.current=None  # Never collect invalid/unfinished controls while cancelling.
        if key=='shared-games':
            self.shared_overlay.clear()
            self.shared_enabled=settings.game_budget_enabled; self.shared_created=self.shared_enabled
            from .qt_schedule import GAME_FIELDS
            self.schedule.restore_fields(settings,GAME_FIELDS)
        elif key=='computer-window':
            from .qt_schedule import COMPUTER_FIELDS
            self.schedule.restore_fields(settings,COMPUTER_FIELDS)
            from .schedule import week_plans
            self.computer_created=any(p['bedtime_enabled'] for p in week_plans(settings).values())
        elif key and key.startswith('game:'):
            gid=key[5:]; self.draft_games.discard(gid); self.game_overlay_changed.discard(gid)
            for destination,source in ((self.game_limits,settings.game_limits),(self.original_game_limits,settings.game_limits),
                                       (self.game_overlays,settings.game_overlays)):
                if gid in source: destination[gid]=deepcopy(source[gid])
                else: destination.pop(gid,None)
        elif key:
            self.counter_overlay_changed.discard(key)
            if key in settings.counter_overlays: self.counter_overlays[key]=deepcopy(settings.counter_overlays[key])
            else: self.counter_overlays.pop(key,None)
            saved=next((rule for rule in settings.wellbeing_rules if rule['id']==key),None)
            index=next((i for i,rule in enumerate(self.rules) if rule['id']==key),len(self.rules))
            self.rules=[rule for rule in self.rules if rule['id']!=key]
            if saved: self.rules.insert(index,deepcopy(saved))
            for kind,category in list(self.categories.items()):
                if category['id']==key:
                    self.categories[kind]=new_rule('Applications' if kind=='apps' else 'Websites',[target('category',kind)],key)
        self.error.clear(); self.error.hide()
        if self.app.settings_error.text()==self.app.budget_error.text(): self.app.settings_error.clear()
        self.app.budget_error.clear()
        self.refresh(); self.views.setCurrentIndex(0)
        restore(self.app.budget_scroll,getattr(self,'_list_scroll',0))
        self.app.set_status('Changes discarded.')
        if hasattr(self,'drafts'): self.drafts.flush()

    def create_new(self):
        self.collect(); rule=new_rule(str(self.app.t('New budget')),[]); rule['enabled']=True; self.rules.append(rule)
        self.refresh(rule['id']); self.show_editor(); self.name.setFocus(); self.name.selectAll()

    def create_computer(self):
        self.collect()
        if self.computer_created: self.periods.create(); return
        self.computer_created=True; self.schedule.set_computer_enabled(True)
        self.refresh('computer-window'); self.show_editor()

    def list_rows(self):
        rows=[]; t=self.app.t
        if self.shared_created:
            from .schedule import week_plans
            plans=week_plans(self.schedule.settings(self.app.settings))
            times={plan['limit_seconds'] for plan in plans.values()}
            amount=t('{minutes:g} min / day',minutes=next(iter(times))/60) if len(times)==1 else t('Varies by day')
            rows.append(('shared-games',t('Games · shared budget'),t('All games'),amount,self.shared_enabled,
                         self.shared_countdown.isChecked() if hasattr(self,'shared_countdown') else self.app.settings.overlay_enabled))
        if self.computer_created:
            plans=[p for p in self.schedule._plans.values() if p['bedtime_enabled']]
            periods={(p['bedtime_minute'],p['bedtime_resume_minute']) for p in plans}
            if len(periods)==1:
                start,end=next(iter(periods)); amount=f'{start//60:02d}:{start%60:02d}–{end//60:02d}:{end%60:02d}'
            else: amount=t('Varies by day')
            rows.append(('computer-window',t('Computer use'),t('Scheduled period'),amount,bool(plans),False))
        for gid in sorted(set(self.game_limits)|self.draft_games,key=lambda value:self.game_name(value).casefold()):
            from .schedule import game_settings
            shown=game_settings(replace(self.app.settings,game_overlays=self.game_overlays),gid).overlay_enabled
            rows.append(('game:'+gid,self.game_name(gid),t('Game'),t('{minutes:g} min / day',minutes=self.game_limits.get(gid,1800)/60),gid in self.game_limits,shown))
        for rule in self.rules:
            names=[str(self.member_name(member)) for member in rule['members']]
            members=', '.join(names[:3])+(str(t(' · {count} more',count=len(names)-3)) if len(names)>3 else '')
            if not names: members=t('Choose what this budget applies to')
            elif len(rule['members'])==1:
                kind={'app':'Application','site':'Website','game':'Game','category':'Shared budget'}[rule['members'][0]['kind']]
                members=t('{kind} · {name}',kind=t(kind),name=members)
            rows.append((rule['id'],t(rule['name']) if rule['id'].startswith('category-') else rule['name'],members,
                         t('{minutes:g} min / day',minutes=rule['seconds']/60),rule['enabled'],rule['overlay']))
        adjusted=[]
        rows.extend(self.periods.rows())
        for key,name,members,amount,enabled,overlay in rows:
            if not self.access.usage_limits.get(key,True): amount=t('No daily minute limit')
            days=self.access.active_days.get(key,list(range(7)))
            from .qt_schedule import DAY_SHORT
            day_summary=t('Every day') if len(days)==7 else ', '.join(str(t(DAY_SHORT[day])) for day in days) if days else t('No active days')
            amount=str(amount)+' · '+str(day_summary)
            adjusted.append((key,name,members,amount,enabled,overlay))
        return adjusted

    @preserving(lambda self:getattr(self.app,'budget_scroll',None))
    def refresh_rows(self):
        if hasattr(self,'drafts'): self.drafts.queue()
        self.add_computer.show()
        rows=self.list_rows(); signature=tuple(tuple(map(str,row)) for row in rows)
        if signature==self._rows_signature:
            self.refresh_breaks();return
        self._rows_signature=signature; self.row_keys=[row[0] for row in rows]
        self.break_buttons={}
        while self.rows_layout.count():
            item=self.rows_layout.takeAt(0); item.widget().hide(); item.widget().deleteLater()
        for key,name,members,amount,enabled,shown in rows:
            card=panel(); card.setProperty('budgetKey',key); card.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
            row=QHBoxLayout(card); row.setContentsMargins(20,16,20,16); row.setSpacing(18)
            text=QVBoxLayout(); title=label(name,'section'); title.setWordWrap(True); text.addWidget(title)
            description=label(members,'muted'); description.setWordWrap(True); text.addWidget(description); row.addLayout(text,1)
            summary=QVBoxLayout(); summary.addWidget(label(amount if enabled else self.app.t('Disabled')))
            row.addLayout(summary)
            pause=button(self.app.t('Break now'),lambda checked=False,k=key:self.start_break(k),'primary')
            pause.setAccessibleName(self.app.t('Break now')+' · '+str(name));row.addWidget(pause)
            self.break_buttons[key]=pause;pause.hide()
            if not enabled and key not in ('shared-games','computer-window') and not key.startswith('game:'):
                activate=button(self.app.t('Enable'),lambda checked=False,k=key:self.enable_rule(k))
                activate.setAccessibleName(self.app.t('Enable {name}',name=name)); row.addWidget(activate)
            edit=button(self.app.t('Edit'),lambda checked=False,k=key:self.show_editor(k))
            edit.setAccessibleName(self.app.t('Edit {name}',name=name)); row.addWidget(edit)
            delete=button('',lambda checked=False,k=key,n=str(name):self.confirm_remove(k,n),'quiet')
            delete.setIcon(glyph('trash')); delete.setIconSize(QSize(20,20)); delete.setFixedSize(40,40)
            delete.setAccessibleName(self.app.t('Delete {name}',name=name)); delete.setToolTip(self.app.t('Delete {name}',name=name))
            row.addWidget(delete); self.rows_layout.addWidget(card)
        self.empty.setVisible(not rows)
        self.refresh_breaks()

    def refresh_breaks(self):
        runtime=getattr(self.app,'restrictions',None)
        actions=runtime.early_break_actions() if runtime else {}
        from .timer_view import clock
        for key,pause in getattr(self,'break_buttons',{}).items():
            action=actions.get(key,{})
            pause.setVisible(bool(action));pause.setEnabled(bool(action.get('step')))
            text=self.app.t('Break remaining: {time}',time=clock(action['remaining'])) if action.get('remaining') else self.app.t(
                'Start the full break now. A fresh usage interval begins when it ends.' if action.get('step') else 'This break is no longer available.')
            if pause.toolTip()!=text:pause.setToolTip(text)

    def start_break(self,key):
        action=self.app.restrictions.early_break_actions().get(key,{})
        if not action.get('step') or not self.app.restrictions.start_early_break(key,action['step']):
            self.app.set_status('This break is no longer available.')
        self.refresh_breaks()

    def enable_rule(self,key):
        if self.periods.is_extra(key):
            next(p for p in self.periods.items if p['id']==key)['values']['bedtime_enabled']=True
            self.refresh(key); return
        rule=self.rule(key)
        if rule:
            rule['enabled']=True; self.refresh(key)

    def rename(self,text):
        if not self.loading and self.current and not self.current.startswith(('game:','category-')):
            self.selector.setItemText(self.selector.currentIndex(),text.strip() or self.app.t('Shared budget'))

    def game_name(self,gid):
        game=self.app.catalog.games.get(gid) or next((g for g in self.app.store.games() if g.id==gid),None)
        return game.name if game else gid

    def member_name(self,member):
        kind,value=member['kind'],member['value']
        if kind=='category': return self.app.t({'games':'All games','apps':'All applications','sites':'All websites'}[value])
        if kind=='game': return self.game_name(value)
        return ntpath.basename(value) if kind=='app' else value

    def rule(self,key):
        return next((rule for rule in self.rules if rule['id']==key),None) or next((rule for rule in self.categories.values() if rule['id']==key),None)

    def collect(self):
        if hasattr(self,'periods'): self.periods.collect()
        if self.loading or not self.current or self.current in ('shared-games','computer-window'): return
        key=self.current
        if key.startswith('game:'):
            gid=key[5:]
            self.game_limits[gid]=self.minutes.value()*60
        else:
            rule=self.rule(key)
            if rule:
                name=self.name.text().strip()
                if key.startswith('category-') and name==str(self.app.t(rule['name'])): name=rule['name']
                rule.update(name=name,seconds=self.minutes.value()*60)
                if rule not in self.rules and rule['enabled']: self.rules.append(rule)

    def refresh(self,selected=None):
        if hasattr(self,'drafts'): self.drafts.remember()
        chosen=selected or self.current or 'shared-games'
        self.loading=True; blocked=self.selector.blockSignals(True); self.selector.clear()
        if self.shared_created: self.selector.addItem(self.app.t('Games · shared budget'),'shared-games')
        if self.computer_created: self.selector.addItem(self.app.t('Computer use'),'computer-window')
        for item in self.periods.items: self.selector.addItem(item['name'],item['id'])
        for gid in sorted(set(self.game_limits)|self.draft_games,key=lambda value:self.game_name(value).casefold()):
            self.selector.addItem(self.game_name(gid),'game:'+gid)
        for rule in self.rules:
            self.selector.addItem(rule['name'],rule['id'])
        self.selector.setCurrentIndex(max(0,self.selector.findData(chosen)) if self.selector.count() else -1); self.selector.blockSignals(blocked)
        self.current=None; self.loading=False; self.choose(); self.refresh_rows()

    def choose(self,*args):
        if hasattr(self,'drafts'): self.drafts.remember()
        self.collect(); self.current=self.selector.currentData(); self.loading=True
        if self.current is None: self.stack.setCurrentIndex(2)
        elif self.periods.is_extra(self.current):
            self.periods.choose(self.current); self.stack.setCurrentIndex(3)
        elif self.current in ('shared-games','computer-window'):
            self.schedule.set_mode('games' if self.current=='shared-games' else 'computer')
            self.shared_reset_panel.hide()
            minute=self.reset_overrides.get(self.current,self.app.settings.budget_reset_minute)
            self.shared_reset.setTime(QTime(minute//60,minute%60))
            self.stack.setCurrentIndex(0); self.toggle_shared()
        else:
            self.schedule.set_mode('games')
            self.stack.setCurrentIndex(1); game=self.current.startswith('game:')
            minute=self.reset_overrides.get(self.current,self.app.settings.budget_reset_minute)
            self.reset_time.setTime(QTime(minute//60,minute%60))
            if game:
                gid=self.current[5:]; value=self.game_limits.get(gid)
                self.name.setText(self.game_name(gid)); self.name.setReadOnly(True)
                self.minutes.setValue((1800 if value is None else value)/60)
                from .schedule import game_settings
                self.overlay.setChecked(game_settings(replace(self.app.settings,game_overlays=self.game_overlays),gid).overlay_enabled)
                self.members_note.hide(); self.members_button.hide()
                used=self.app.tracker.game_quota_total(datetime.now().astimezone(),gid)
            else:
                rule=self.rule(self.current); self.name.setText(self.app.t(rule['name']) if self.current.startswith('category-') else rule['name'])
                self.name.setReadOnly(False)
                self.minutes.setValue(rule['seconds']/60)
                self.overlay.setChecked(rule['overlay'])
                names=[str(self.member_name(member)) for member in rule['members']]
                self.members_note.setToolTip(', '.join(names))
                self.members_note.setText(', '.join(names) if names else self.app.t('Choose what this budget applies to'))
                self.members_note.show(); self.members_button.show()
                self.app.wellbeing.configure(datetime.now().astimezone())
                from .wellbeing import applies
                used=self.app.wellbeing.totals.get(rule['id'],sum(seconds for atom,seconds in self.app.wellbeing.atoms.items() if applies(rule['members'],atom)))
                if rule['id'].startswith('games-') and rule['members']==[target('category','games')]:
                    used=sum(self.app.tracker.quota_totals(datetime.now().astimezone(),rule['id']).values())
            self.usage.setText(self.app.t('Used in this budget: {time}',time=duration(used)))
        self.access.choose(self.current)
        self.periods.place_days()
        self.loading=False; self.steps.set_budget(None if self.periods.is_computer(self.current) else self.current); self.controls(); self.error.hide()
        if hasattr(self,'drafts'): self.drafts.apply_raw()

    def controls(self,*args):
        usage=self.access.usage_limits.get(self.current,True) if hasattr(self,'access') else True
        self.minutes.setEnabled(usage); self.overlay.setEnabled(True)
        self.zero_limit_note.setVisible(usage and self.minutes.value()==0)
        self.schedule.limit.setEnabled(usage)
        self.schedule.zero_limit_note.setVisible(usage and any(self.schedule._plans[d]['limit_seconds']==0 for d in self.schedule._selected))
        for widget in (self.limit_fields,self.usage): widget.show()
        rule=self.rule(self.current)
        self.overlay.hide(); self.appearance.setVisible(bool(self.current and (self.current.startswith('game:') or rule and rule['members'])))
        self.tracking.setVisible(bool(rule and not self.app.focus.settings.tracking and any(
            m['kind'] in ('app','site') or m['kind']=='category' and m['value'] in ('apps','sites') for m in rule['members'])))

    def edit_countdown(self):
        self.collect()
        from .qt_personalization import game_overlay_dialog
        from .qt_countdown_targets import BudgetCountdownTargets
        game_overlay_dialog(self.app,self.current,targets=BudgetCountdownTargets(self,self.current))

    def enable_tracking(self):
        self.app.focus.configure(replace(self.app.focus.settings,tracking=True)); self.app.update_focus_policy()
        self.app.activity_tracking.setChecked(True); self.controls()

    def saved(self,settings):
        from .computer_periods import split_weekly
        source=settings; settings=split_weekly(settings)
        self.schedule.saved(settings)
        self.periods.saved(settings)
        self.access.saved(settings)
        self.member_overlay_drafts.clear()
        self.counter_overlays=deepcopy(settings.counter_overlays); self.counter_overlay_changed.clear(); self.shared_overlay.clear()
        self.restriction_plans=deepcopy(settings.restriction_plans); self.restriction_changed.clear()
        self.rules=deepcopy(settings.wellbeing_rules); self.original_game_limits=dict(settings.game_limits)
        self.categories={key:new_rule(name,[target('category',key)],'category-'+key) for key,name in (('apps','Applications'),('sites','Websites'))}
        self.shared_enabled=settings.game_budget_enabled; self.shared_created=self.shared_enabled
        from .schedule import week_plans
        self.computer_created=any(p['bedtime_enabled'] for p in week_plans(settings).values())
        self.game_limits=dict(settings.game_limits); self.game_overlays=deepcopy(settings.game_overlays); self.game_overlay_changed.clear()
        self.reset_overrides=dict(settings.budget_reset_overrides); self.reset_changed.clear()
        self.draft_games.clear()
        if settings!=source:
            self.schedule._edits=deepcopy(self.schedule._plans)
            self.restriction_changed.update(set(source.restriction_plans)|set(settings.restriction_plans))
            self.reset_changed.update(settings.budget_reset_overrides)
            self.access.changed_days.update(settings.budget_active_days); self.access.changed_limits.update(settings.budget_usage_limits)
        self.refresh()
        if hasattr(self,'drafts'): self.drafts.saved()
        self.periods.migrated=settings!=source

    def remap(self,aliases):
        for values,changed in ((self.access.active_days,self.access.changed_days),(self.access.usage_limits,self.access.changed_limits)):
            for old,new in aliases.items():
                if 'game:'+old in values: values.setdefault('game:'+new,values.pop('game:'+old))
                if 'game:'+old in changed: changed.discard('game:'+old); changed.add('game:'+new)
        from .wellbeing import remap_rules
        self.collect(); self.rules=remap_rules(self.rules,aliases)
        for old,new in aliases.items():
            before,after='game:'+old,'game:'+new
            if before in self.restriction_plans:
                self.restriction_plans.setdefault(after,self.restriction_plans.pop(before))
            if before in self.restriction_changed:
                self.restriction_changed.update((before,after))
            if before in self.reset_overrides:
                self.reset_overrides.setdefault(after,self.reset_overrides.pop(before)); self.reset_changed.update((before,after))
        for name in ('game_limits','original_game_limits','game_overlays'):
            values=getattr(self,name)
            for old,new in aliases.items():
                if old in values:
                    value=values.pop(old)
                    if name=='game_overlays': values.setdefault(new,value)
                    else: values[new]=min(value,values.get(new,value))
        self.draft_games={aliases.get(g,g) for g in self.draft_games}
        self.game_overlay_changed={aliases.get(g,g) for g in self.game_overlay_changed}
        remapped={}
        for key,profiles in self.member_overlay_drafts.items():
            key='game:'+aliases.get(key[5:],key[5:]) if key.startswith('game:') else key
            remapped.setdefault(key,{}).update({('game:'+aliases.get(member[5:],member[5:]) if member.startswith('game:') else member):value
                                              for member,value in profiles.items()})
        self.member_overlay_drafts=remapped
        selected=self.current
        if selected and selected.startswith('game:'): selected='game:'+aliases.get(selected[5:],selected[5:])
        self.refresh(selected)

    def settings(self,base):
        self.collect()
        # Empty disabled category drafts do not become saved configuration.
        rules=deepcopy(self.rules); validate_rules(rules)
        limits=dict(base.game_limits)
        for gid in set(self.original_game_limits)|set(self.game_limits):
            if self.original_game_limits.get(gid)!=self.game_limits.get(gid):
                if gid in self.game_limits: limits[gid]=self.game_limits[gid]
                else: limits.pop(gid,None)
        plans=deepcopy(base.restriction_plans)
        for key in self.restriction_changed:
            if key in self.restriction_plans: plans[key]=deepcopy(self.restriction_plans[key])
            else: plans.pop(key,None)
        resets={key:base.budget_reset_minute for key in base.budget_reset_overrides if key not in self.reset_changed or key in self.reset_overrides}
        return self.countdown_settings(replace(base,wellbeing_rules=rules,game_limits=limits,
                       computer_periods=deepcopy(self.periods.items),game_budget_enabled=self.shared_enabled,restriction_plans=plans,budget_reset_overrides=resets,**self.access.values(base)))

    def countdown_settings(self,base):
        overlays=deepcopy(base.game_overlays); activities=deepcopy(base.activity_overlays)
        for gid in self.game_overlay_changed:
            overlays[gid]={**overlays.get(gid,{}),**self.game_overlays[gid]}
        for profiles in self.member_overlay_drafts.values():
            for key,value in profiles.items():
                destination=overlays if key.startswith('game:') else activities
                identity=key[5:] if key.startswith('game:') else key
                destination[identity]={**destination.get(identity,{}),**value}
        counters=deepcopy(base.counter_overlays)
        for key in self.counter_overlay_changed:
            if key in self.counter_overlays: counters[key]=deepcopy(self.counter_overlays[key])
            else: counters.pop(key,None)
        return replace(base,game_overlays=overlays,activity_overlays=activities,counter_overlays=counters,**self.shared_overlay)

    def open_member(self,member):
        member=canonical_member(member)
        self.collect()
        existing=next((rule for rule in self.rules if {activity_key(m) for m in rule['members']}=={activity_key(member)}),None)
        if existing: key=existing['id']
        elif member['kind']=='game':
            gid=member['value']; self.draft_games.add(gid); key='game:'+gid
            if gid not in self.game_limits:
                self.game_limits[gid]=1800
        elif member['kind']=='category' and member['value']=='games':
            key='shared-games'; self.shared_created=True; self.shared_enabled=True
        elif member['kind']=='category':
            key='category-'+member['value']
            if not any(rule['id']==key for rule in self.rules):
                rule=deepcopy(self.categories[member['value']]); rule['enabled']=True; self.rules.append(rule)
        else:
            rule=next((r for r in self.rules if r['members']==[member]),None)
            if rule is None:
                rule=new_rule(str(self.member_name(member)),[member]); rule['enabled']=True; self.rules.append(rule)
            key=rule['id']
        self.refresh(key); self.show_editor()

    def add_individual(self):
        self.pick_members([],lambda members:self.open_member(members[0]),individual=True)

    def add_group(self): self.pick_members([],self.create_group)

    def create_group(self,members):
        if len(members)==1 and members[0]['kind']=='category': self.open_member(members[0]); return
        self.collect(); rule=new_rule(str(self.app.t('Shared budget')),members); rule['enabled']=True; self.rules.append(rule)
        self.refresh(rule['id']); self.show_editor(); self.name.setFocus(); self.name.selectAll()

    def edit_members(self):
        self.collect(); rule=self.rule(self.current)
        if rule: self.pick_members(rule['members'],lambda members:self.replace_members(rule,members))

    def replace_members(self,rule,members):
        # An all-games selection recreates the original weekly game budget,
        # including its historical/synchronized play-time accounting.
        if (not self.shared_created and not rule['members'] and
                members==[target('category','games')]):
            self.collect(); identity=rule['id']; minutes=rule['seconds']/60
            self.rules.remove(rule); self.shared_created=self.shared_enabled=True
            self.schedule.select_days(range(7)); self.schedule.change('limit_seconds',minutes*60)
            for day in range(7):
                plan=self.schedule._plans[day]
                if plan['warning_seconds']>=plan['limit_seconds']:
                    plan['warning_seconds']=plan['limit_seconds']*.8
                    self.schedule._edits.setdefault(day,{})['warning_seconds']=plan['warning_seconds']
            self.schedule.load_selection()
            if identity in self.restriction_plans:
                self.restriction_plans['shared-games']=self.restriction_plans.pop(identity)
                self.restriction_changed.update((identity,'shared-games'))
            if identity in self.reset_overrides:
                self.reset_overrides['shared-games']=self.reset_overrides.pop(identity)
                self.reset_changed.update((identity,'shared-games'))
            self.refresh('shared-games'); self.show_editor(); return
        if members==[{'kind':'computer','value':'period'}]:
            self.rules.remove(rule); self.current=None
            self.create_computer(); return
        rule['members']=members
        if rule['name']==str(self.app.t('New budget')):
            rule['name']=str(self.member_name(members[0])) if len(members)==1 else str(self.app.t('Shared budget'))
        self.refresh(rule['id'])

    def remove_current(self):
        self.remove_budget(self.current)

    def confirm_remove(self,key,name):
        if self.ask_delete(name): self.remove_budget(key)

    def ask_delete(self,name):
        t=self.app.t; dialog=QDialog(self); dialog.setObjectName('Surface')
        dialog.setWindowTitle(t('Delete budget')); dialog.resize(540,200)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(26,24,26,24); layout.setSpacing(14)
        title=label(t('Delete “{name}”?',name=name),'section'); title.setWordWrap(True); layout.addWidget(title)
        note=label(t('Recorded activity history will be kept. Save changes to apply.'),'muted')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        actions=QHBoxLayout(); actions.addStretch()
        cancel=button(t('Cancel'),dialog.reject); cancel.setDefault(True); actions.addWidget(cancel)
        delete=button(t('Delete'),dialog.accept,'danger-action'); delete.setAutoDefault(False); actions.addWidget(delete)
        layout.addLayout(actions)
        from .qt_ui import dark_window
        dark_window(dialog); cancel.setFocus()
        return dialog.exec()==QDialog.Accepted

    def remove_budget(self,key):
        if not key: return
        if hasattr(self,'drafts'): self.drafts.raw.pop(key,None)
        self.access.remove(key)
        self.member_overlay_drafts.pop(key,None)
        self.collect(); self.current=None
        self.restriction_plans.pop(key,None); self.restriction_changed.add(key)
        self.reset_overrides.pop(key,None); self.reset_changed.add(key)
        if key=='shared-games':
            self.shared_created=False; self.shared_enabled=False
        elif key=='computer-window':
            self.computer_created=False; self.schedule.set_computer_enabled(False)
        elif self.periods.is_extra(key): self.periods.items=[p for p in self.periods.items if p['id']!=key]
        elif key.startswith('game:'):
            self.game_limits.pop(key[5:],None); self.draft_games.discard(key[5:])
        else: self.rules=[rule for rule in self.rules if rule['id']!=key]
        self.refresh('shared-games'); self.views.setCurrentIndex(0)

    def pick_members(self,initial,accept,individual=False):
        app=self.app; window=app._dialog(app.t('Choose budget members'),820); window.resize(820,650)
        layout=QVBoxLayout(window); layout.setContentsMargins(24,22,24,22); layout.setSpacing(12)
        layout.addWidget(back_button(app.t,window.reject),0,Qt.AlignLeft)
        prompt=('Choose one game, application or website.' if individual else
                'Choose activities to share a budget, or choose a scheduled computer-use period.')
        note=label(app.t(prompt)); note.setWordWrap(True); layout.addWidget(note)
        columns=QHBoxLayout(); columns.setSpacing(18); layout.addLayout(columns,1)
        available=QVBoxLayout(); available.setSpacing(10); columns.addLayout(available,1)
        available.addWidget(label(app.t('Available activities'),'section'))
        search=QLineEdit(); search.setPlaceholderText(app.t('Search…')); available.addWidget(search)
        listing=QListWidget(); listing.setAccessibleName(app.t('Budget members')); available.addWidget(listing,1)
        listing.setStyleSheet('QListWidget::indicator {width:17px;height:17px;border:1px solid #607c77;border-radius:4px;background:#172227;} '
                             'QListWidget::indicator:checked {background:#7de5bf;border-color:#7de5bf;}')
        choices={}
        def add(member,title=None):
            member=canonical_member(member)
            pair=(member['kind'],member['value'])
            if pair in choices: return choices[pair]
            item=QListWidgetItem(str(title or self.member_name(member)))
            item.setData(Qt.UserRole,member); item.setToolTip(member['value'])
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked if any(activity_key(member)==activity_key(old) for old in initial) else Qt.Unchecked)
            listing.addItem(item); choices[pair]=item; return item
        computer_choice=None
        rule=self.rule(self.current)
        if not individual:
            for key in ('games','apps','sites'): add(target('category',key))
            if rule and not rule['members']:
                computer_choice=add({'kind':'computer','value':'period'},app.t('Computer use · scheduled period'))
                def exclusive_period(changed):
                    if changed.checkState()!=Qt.Checked: return
                    if changed is computer_choice:
                        for item in choices.values():
                            if item is not changed: item.setCheckState(Qt.Unchecked)
                    else: computer_choice.setCheckState(Qt.Unchecked)
                listing.itemChanged.connect(exclusive_period)
        for game in sorted(app.store.games(),key=lambda value:value.name.casefold()): add(target('game',game.id),game.name+' · '+str(app.t('Game')))
        for member,name in known_activities(app.store,app.settings,app.catalog):
            add(member,name+' · '+str(app.t('Application' if member['kind']=='app' else 'Website')))
        for member in initial: add(member)
        if individual:
            def select_one(changed):
                if changed.checkState()!=Qt.Checked: return
                for item in choices.values():
                    if item is not changed: item.setCheckState(Qt.Unchecked)
            listing.itemChanged.connect(select_one)
        from .qt_member_selection import SelectedMembers
        selected=SelectedMembers(listing,app.t,window); columns.addWidget(selected,1)
        search.textChanged.connect(lambda text:[item.setHidden(text.casefold() not in (item.text()+' '+item.toolTip()).casefold()) for item in choices.values()])
        error=label('','danger'); error.setWordWrap(True)
        row=QHBoxLayout(); site=QLineEdit(); site.setPlaceholderText(app.t('Website domain, e.g. youtube.com')); row.addWidget(site,1)
        def add_site():
            try:
                item=add(target('site',site.text())); item.setCheckState(Qt.Checked); item.setHidden(False); site.clear(); error.clear()
            except ValueError as exc: error.setText(app.t(str(exc)))
        row.addWidget(button(app.t('Add website'),add_site)); layout.addLayout(row)
        def add_app():
            path,_=QFileDialog.getOpenFileName(window,app.t('Choose application'),'','Windows application (*.exe)')
            if path:
                item=add(target('app',path)); item.setCheckState(Qt.Checked); item.setHidden(False)
        layout.addWidget(button(app.t('Choose executable…'),add_app),0,Qt.AlignLeft); layout.addWidget(error)
        def finish():
            members=[item.data(Qt.UserRole) for item in choices.values() if item.checkState()==Qt.Checked]
            if computer_choice and computer_choice.checkState()==Qt.Checked:
                if self.current in self.restriction_plans:
                    error.setText(app.t('Choose the scheduled period before adding budget actions.')); return
                accept(members); window.accept(); return
            if individual and len(members)!=1: error.setText(app.t('Choose one game, application or website.')); return
            if not 1<=len(members)<=200: error.setText(app.t('Choose between 1 and 200 members for a shared budget.')); return
            accept(members); window.accept()
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(app.t('Cancel'),window.reject)); actions.addWidget(button(app.t('Use selection'),finish,'primary')); layout.addLayout(actions)
        window.show()
        from .qt_ui import dark_window
        dark_window(window)
