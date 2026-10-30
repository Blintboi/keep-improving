"""One editor for category, individual and mixed shared time budgets."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import ntpath
import uuid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QStackedLayout,QListWidget,QListWidgetItem,QFileDialog,QSizePolicy,QLayout
from .qt_translation import QLineEdit,QCheckBox
from .qt_widgets import label,button,back_button,panel,NoWheelComboBox,NoWheelDoubleSpinBox,duration,Disclosure
from .wellbeing import target,validate_rules
from .activities import known_activities
from .activity_identity import canonical_member,activity_key


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
        self.shared_enabled=app.settings.game_budget_enabled; self.shared_created=self.shared_enabled
        self.categories={key:new_rule(name,[target('category',key)],'category-'+key) for key,name in (('apps','Applications'),('sites','Websites'))}
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(10); layout.setAlignment(Qt.AlignTop)
        self.views=BudgetStack(); layout.addWidget(self.views)
        overview=QWidget(); listing=QVBoxLayout(overview); listing.setContentsMargins(0,0,0,0); listing.setSpacing(14); listing.setAlignment(Qt.AlignTop)
        header=QHBoxLayout(); note=label(app.t('Your individual and shared budgets, all in one place.'),'muted'); note.setWordWrap(True)
        header.addWidget(note,1); self.add_button=button(app.t('Add new'),self.create_new,'primary'); header.addWidget(self.add_button); listing.addLayout(header)
        self.rows_widget=QWidget(); self.rows_layout=QVBoxLayout(self.rows_widget); self.rows_layout.setContentsMargins(0,0,0,0); self.rows_layout.setSpacing(10); self.rows_layout.setAlignment(Qt.AlignTop)
        listing.addWidget(self.rows_widget); self.row_keys=[]; self._rows_signature=None
        self.empty=label(app.t('No time budgets yet. Add one for a game, application, website or a group.'),'muted'); self.empty.setWordWrap(True); listing.addWidget(self.empty)
        self.views.addWidget(overview)
        editor=QWidget(); edit_layout=QVBoxLayout(editor); edit_layout.setContentsMargins(0,0,0,0); edit_layout.setSpacing(12); edit_layout.setAlignment(Qt.AlignTop)
        navigation=QHBoxLayout(); self.back_button=back_button(app.t,self.cancel_edit); navigation.addWidget(self.back_button); navigation.addStretch()
        self.delete_button=button(app.t('Remove this budget'),self.remove_current,'quiet'); navigation.addWidget(self.delete_button); edit_layout.addLayout(navigation)
        # Stable identities for the editor; the public navigation is the list.
        self.selector=NoWheelComboBox(self); self.selector.hide()
        self.stack=BudgetStack(); edit_layout.addWidget(self.stack)
        from .qt_restriction_steps import edit_steps
        self.steps_button=button(app.t('Warnings and restrictions…'),lambda:edit_steps(self))
        edit_layout.addWidget(self.steps_button)
        self.views.addWidget(editor)
        shared=QWidget(); box=QVBoxLayout(shared); self.shared_layout=box; box.setContentsMargins(0,0,0,0); box.setAlignment(Qt.AlignTop)
        self.shared_switches=QHBoxLayout(); box.addLayout(self.shared_switches)
        self.shared=QCheckBox(app.t('Use a shared game budget')); self.shared.setChecked(self.shared_enabled); self.shared_switches.addWidget(self.shared)
        box.addWidget(schedule); self.stack.addWidget(shared)
        self.shared.toggled.connect(self.toggle_shared)
        detail=panel(); form=QVBoxLayout(detail); form.setContentsMargins(22,20,22,22); form.setSpacing(14); form.setAlignment(Qt.AlignTop)
        self.name=QLineEdit(); self.name.setMaxLength(80); self.name.setAccessibleName(app.t('Budget name')); form.addWidget(self.name)
        self.members_note=label('','muted'); self.members_note.setWordWrap(True); form.addWidget(self.members_note)
        self.members_button=button(app.t('Edit members…'),self.edit_members); form.addWidget(self.members_button,0,Qt.AlignLeft)
        self.enabled=QCheckBox(app.t('Use a daily limit')); form.addWidget(self.enabled)
        self.limit_fields=QWidget(); fields=QHBoxLayout(self.limit_fields); fields.setContentsMargins(0,0,0,0); fields.addWidget(label(app.t('Daily limit (minutes)'),'muted'))
        self.minutes=NoWheelDoubleSpinBox(); self.minutes.setRange(.01,1440); self.minutes.setDecimals(2)
        self.minutes.setAccessibleName(app.t('Daily limit (minutes)')); fields.addWidget(self.minutes,1); form.addWidget(self.limit_fields)
        self.overlay=QCheckBox(app.t('Show countdown while active')); form.addWidget(self.overlay)
        self.appearance=button(app.t('Countdown position, size and colors…'),self.edit_countdown,'quiet')
        form.addWidget(self.appearance,0,Qt.AlignLeft)
        self.details=Disclosure(app.t('More options')); form.addWidget(self.details)
        self.enforce=QCheckBox(app.t('Restrict after the budget runs out')); self.details.body.addWidget(self.enforce)
        self.enforce.setToolTip(app.t('Applications and games get 10 seconds before minimization. Website limits use the browser connection. Protected games retain their existing permissions.'))
        self.usage=label('','muted'); self.usage.setWordWrap(True); self.details.body.addWidget(self.usage)
        self.reset_note=label('','muted'); self.reset_note.setWordWrap(True); self.details.body.addWidget(self.reset_note)
        actions=QHBoxLayout()
        self.browser=button(app.t('Browser connection'),lambda:app.focus_page.browser_dialog(),'quiet'); actions.addWidget(self.browser)
        self.remove=self.delete_button; actions.addStretch()
        self.details.body.addLayout(actions)
        self.tracking=button(app.t('Enable application and website measurement'),self.enable_tracking)
        form.addWidget(self.tracking,0,Qt.AlignLeft)
        self.error=label('','danger'); self.error.setWordWrap(True); form.addWidget(self.error); self.error.hide()
        self.stack.addWidget(detail)
        empty=panel(); empty_layout=QVBoxLayout(empty); empty_layout.setContentsMargins(22,24,22,24); empty_layout.setAlignment(Qt.AlignTop)
        empty_layout.addWidget(label(app.t('Start with a time budget'),'section'))
        empty_note=label(app.t('Set a daily budget for one game, application or website, or let several share a group budget. You can add a countdown to each budget.'),'muted')
        empty_note.setWordWrap(True); empty_layout.addWidget(empty_note); self.stack.addWidget(empty)
        self.enabled.toggled.connect(self.controls)
        self.overlay.toggled.connect(self.controls)
        self.name.textChanged.connect(self.rename)
        self.selector.currentIndexChanged.connect(self.choose)
        self.refresh('shared-games')
        self.views.setCurrentIndex(0)

    def toggle_shared(self,checked):
        self.shared_enabled=checked; self.schedule.setVisible(checked)
        if hasattr(self,'shared_countdown'):
            self.shared_countdown.hide(); self.shared_appearance.hide()

    def attach_shared_countdown(self,checkbox,appearance):
        self.shared_countdown=checkbox; checkbox.setParent(self); checkbox.hide()
        self.shared_appearance=button(self.app.t('Countdown position, size and colors…'),self.show_shared_appearance,'quiet')
        self.shared_appearance.setParent(self); self.shared_appearance.hide()
        checkbox.toggled.connect(lambda:self.toggle_shared(self.shared_enabled)); self.toggle_shared(self.shared_enabled)
        appearance.setParent(self); appearance.hide()

    def show_shared_appearance(self):
        self.app.open_activities('game')

    def show_editor(self,key=None):
        self.collect()
        if key is not None: self.refresh(key)
        self.views.setCurrentIndex(1)
        if hasattr(self.app,'budget_scroll'): self.app.budget_scroll.verticalScrollBar().setValue(0)

    def show_list(self):
        self.collect()
        # An untouched creation form is not an extra empty budget.
        self.rules=[rule for rule in self.rules if rule['members'] or rule['name']!=str(self.app.t('New budget'))
                    or rule['seconds']!=3600 or not rule['enabled'] or not rule['overlay'] or rule['enforce']]
        self.current=None; self.refresh(); self.views.setCurrentIndex(0)
        if hasattr(self.app,'budget_scroll'): self.app.budget_scroll.verticalScrollBar().setValue(0)

    def cancel_edit(self):
        """Discard this budget's draft, retaining drafts for other budgets."""
        key=self.current; settings=self.app.settings
        if key in settings.restriction_plans: self.restriction_plans[key]=deepcopy(settings.restriction_plans[key])
        else: self.restriction_plans.pop(key,None)
        self.restriction_changed.discard(key)
        self.current=None  # Never collect invalid/unfinished controls while cancelling.
        if key=='shared-games':
            self.shared_enabled=settings.game_budget_enabled; self.shared_created=self.shared_enabled
            self.shared.setChecked(self.shared_enabled); self.schedule.saved(settings)
        elif key and key.startswith('game:'):
            gid=key[5:]; self.draft_games.discard(gid); self.game_overlay_changed.discard(gid)
            for destination,source in ((self.game_limits,settings.game_limits),(self.original_game_limits,settings.game_limits),
                                       (self.game_overlays,settings.game_overlays)):
                if gid in source: destination[gid]=deepcopy(source[gid])
                else: destination.pop(gid,None)
        elif key:
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
        self.app.budget_scroll.verticalScrollBar().setValue(0)
        self.app.set_status('Changes discarded.')

    def create_new(self):
        self.collect(); rule=new_rule(str(self.app.t('New budget')),[]); rule['enabled']=True; self.rules.append(rule)
        self.refresh(rule['id']); self.show_editor(); self.name.setFocus(); self.name.selectAll()

    def list_rows(self):
        rows=[]; t=self.app.t
        if self.shared_created:
            from .schedule import week_plans
            plans=week_plans(self.schedule.settings(self.app.settings))
            times={plan['limit_seconds'] for plan in plans.values()}
            amount=t('{minutes:g} min / day',minutes=next(iter(times))/60) if len(times)==1 else t('Varies by day')
            rows.append(('shared-games',t('Games · shared budget'),t('All games'),amount,self.shared_enabled,
                         self.shared_countdown.isChecked() if hasattr(self,'shared_countdown') else self.app.settings.overlay_enabled))
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
        return rows

    def refresh_rows(self):
        rows=self.list_rows(); signature=tuple(tuple(map(str,row)) for row in rows)
        if signature==self._rows_signature: return
        self._rows_signature=signature; self.row_keys=[row[0] for row in rows]
        while self.rows_layout.count():
            item=self.rows_layout.takeAt(0); item.widget().hide(); item.widget().deleteLater()
        for key,name,members,amount,enabled,shown in rows:
            card=panel(); card.setProperty('budgetKey',key); card.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
            row=QHBoxLayout(card); row.setContentsMargins(20,16,20,16); row.setSpacing(18)
            text=QVBoxLayout(); title=label(name,'section'); title.setWordWrap(True); text.addWidget(title)
            description=label(members,'muted'); description.setWordWrap(True); text.addWidget(description); row.addLayout(text,1)
            summary=QVBoxLayout(); summary.addWidget(label(amount if enabled else self.app.t('Disabled')))
            row.addLayout(summary)
            edit=button(self.app.t('Edit'),lambda checked=False,k=key:self.show_editor(k))
            edit.setAccessibleName(self.app.t('Edit {name}',name=name)); row.addWidget(edit); self.rows_layout.addWidget(card)
        self.empty.setVisible(not rows)

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
        if self.loading or not self.current or self.current=='shared-games': return
        key=self.current
        if key.startswith('game:'):
            gid=key[5:]
            if self.enabled.isChecked(): self.game_limits[gid]=self.minutes.value()*60
            else: self.game_limits.pop(gid,None)
        else:
            rule=self.rule(key)
            if rule:
                name=self.name.text().strip()
                if key.startswith('category-') and name==str(self.app.t(rule['name'])): name=rule['name']
                rule.update(name=name,seconds=self.minutes.value()*60,enabled=self.enabled.isChecked(),enforce=self.enforce.isChecked())
                if rule not in self.rules and rule['enabled']: self.rules.append(rule)

    def refresh(self,selected=None):
        chosen=selected or self.current or 'shared-games'
        self.loading=True; blocked=self.selector.blockSignals(True); self.selector.clear()
        if self.shared_created: self.selector.addItem(self.app.t('Games · shared budget'),'shared-games')
        for gid in sorted(set(self.game_limits)|self.draft_games,key=lambda value:self.game_name(value).casefold()):
            self.selector.addItem(self.game_name(gid),'game:'+gid)
        for rule in self.rules:
            self.selector.addItem(rule['name'],rule['id'])
        self.selector.setCurrentIndex(max(0,self.selector.findData(chosen)) if self.selector.count() else -1); self.selector.blockSignals(blocked)
        self.current=None; self.loading=False; self.choose(); self.refresh_rows()

    def choose(self,*args):
        self.collect(); self.current=self.selector.currentData(); self.loading=True
        if self.current is None: self.stack.setCurrentIndex(2)
        elif self.current=='shared-games': self.stack.setCurrentIndex(0); self.toggle_shared(self.shared_enabled); self.remove.show()
        else:
            self.stack.setCurrentIndex(1); game=self.current.startswith('game:')
            if game:
                gid=self.current[5:]; value=self.game_limits.get(gid)
                self.name.setText(self.game_name(gid)); self.name.setReadOnly(True)
                self.enabled.setChecked(value is not None); self.minutes.setValue((value or 1800)/60)
                from .schedule import game_settings
                self.overlay.setChecked(game_settings(replace(self.app.settings,game_overlays=self.game_overlays),gid).overlay_enabled)
                self.enforce.setChecked(True); self.enforce.setEnabled(False)
                self.members_note.hide(); self.members_button.hide()
                used=self.app.tracker.quota_totals(datetime.now().astimezone()).get(gid,0)
                self.reset_note.setText(self.app.t('Uses the game budget reset time and includes time already played.'))
                self.browser.hide()
            else:
                rule=self.rule(self.current); self.name.setText(self.app.t(rule['name']) if self.current.startswith('category-') else rule['name'])
                self.name.setReadOnly(False)
                self.enabled.setChecked(rule['enabled']); self.minutes.setValue(rule['seconds']/60)
                self.overlay.setChecked(rule['overlay']); self.enforce.setChecked(rule['enforce']); self.enforce.setEnabled(True)
                names=[str(self.member_name(member)) for member in rule['members']]
                self.members_note.setText(', '.join(names[:4])+(self.app.t(' · {count} more',count=len(names)-4) if len(names)>4 else ''))
                self.members_note.setToolTip(', '.join(names))
                self.members_note.setText(', '.join(names[:4]) if names else self.app.t('Choose what this budget applies to'))
                self.members_note.show(); self.members_button.show()
                self.app.wellbeing.configure(datetime.now().astimezone())
                from .wellbeing import applies
                used=sum(seconds for atom,seconds in self.app.wellbeing.atoms.items() if applies(rule['members'],atom))
                self.reset_note.setText(self.app.t('Renews at midnight. Each second counts once within this budget.'))
                self.reset_note.setToolTip(self.app.t('New shared activity measurement starts with this version. Existing game budgets keep already recorded play time.'))
                self.browser.setVisible(any(m['kind']=='site' or m==target('category','sites') for m in rule['members']))
            self.usage.setText(self.app.t('Used in this budget: {time}',time=duration(used)))
            self.remove.show()
        self.loading=False; self.controls(); self.error.hide()

    def controls(self,*args):
        self.minutes.setEnabled(self.enabled.isChecked()); self.overlay.setEnabled(self.enabled.isChecked())
        self.enforce.setEnabled(self.enabled.isChecked() and not (self.current or '').startswith('game:'))
        for widget in (self.limit_fields,self.enforce,self.usage,self.reset_note): widget.setVisible(self.enabled.isChecked())
        self.steps_button.setVisible(bool(self.current))
        if self.current in self.restriction_plans: self.enforce.hide()
        rule=self.rule(self.current)
        self.overlay.hide(); self.appearance.hide()
        self.tracking.setVisible(bool(rule and not self.app.focus.settings.tracking and any(
            m['kind'] in ('app','site') or m['kind']=='category' and m['value'] in ('apps','sites') for m in rule['members'])))

    def edit_countdown(self):
        self.collect()
        key=self.current[5:] if self.current.startswith('game:') else 'counter:'+self.current
        self.app.game_countdown_dialog(key)

    def enable_tracking(self):
        self.app.focus.configure(replace(self.app.focus.settings,tracking=True)); self.app.update_focus_policy()
        self.app.statistics.tracking.setChecked(True); self.controls()

    def saved(self,settings):
        self.restriction_plans=deepcopy(settings.restriction_plans); self.restriction_changed.clear()
        self.rules=deepcopy(settings.wellbeing_rules); self.original_game_limits=dict(settings.game_limits)
        self.categories={key:new_rule(name,[target('category',key)],'category-'+key) for key,name in (('apps','Applications'),('sites','Websites'))}
        self.shared_enabled=settings.game_budget_enabled; self.shared_created=self.shared_enabled
        self.shared.setChecked(self.shared_enabled)
        self.game_limits=dict(settings.game_limits); self.game_overlays=deepcopy(settings.game_overlays); self.game_overlay_changed.clear()
        self.draft_games.clear()
        self.refresh()

    def remap(self,aliases):
        from .wellbeing import remap_rules
        self.collect(); self.rules=remap_rules(self.rules,aliases)
        for old,new in aliases.items():
            before,after='game:'+old,'game:'+new
            if before in self.restriction_plans:
                self.restriction_plans.setdefault(after,self.restriction_plans.pop(before))
            if before in self.restriction_changed:
                self.restriction_changed.update((before,after))
        for name in ('game_limits','original_game_limits','game_overlays'):
            values=getattr(self,name)
            for old,new in aliases.items():
                if old in values:
                    value=values.pop(old)
                    if name=='game_overlays': values.setdefault(new,value)
                    else: values[new]=min(value,values.get(new,value))
        self.draft_games={aliases.get(g,g) for g in self.draft_games}
        self.game_overlay_changed={aliases.get(g,g) for g in self.game_overlay_changed}
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
        overlays=deepcopy(base.game_overlays)
        for gid in self.game_overlay_changed:
            overlays.setdefault(gid,{})['overlay_enabled']=self.game_overlays[gid]['overlay_enabled']
        plans=deepcopy(base.restriction_plans)
        for key in self.restriction_changed:
            if key in self.restriction_plans: plans[key]=deepcopy(self.restriction_plans[key])
            else: plans.pop(key,None)
        return replace(base,wellbeing_rules=rules,game_limits=limits,game_overlays=overlays,game_budget_enabled=self.shared_enabled,restriction_plans=plans)

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
            key='shared-games'; self.shared_created=True; self.shared.setChecked(True)
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
        rule['members']=members
        if rule['name']==str(self.app.t('New budget')):
            rule['name']=str(self.member_name(members[0])) if len(members)==1 else str(self.app.t('Shared budget'))
        self.refresh(rule['id'])

    def remove_current(self):
        key=self.current; self.current=None
        if not key: return
        self.restriction_plans.pop(key,None); self.restriction_changed.add(key)
        if key=='shared-games':
            self.shared_created=False; self.shared.setChecked(False)
        elif key.startswith('game:'):
            self.game_limits.pop(key[5:],None); self.draft_games.discard(key[5:])
        else: self.rules=[rule for rule in self.rules if rule['id']!=key]
        self.refresh('shared-games'); self.views.setCurrentIndex(0)

    def pick_members(self,initial,accept,individual=False):
        app=self.app; window=app._dialog(app.t('Choose budget members'),720); window.resize(720,650)
        layout=QVBoxLayout(window); layout.setContentsMargins(24,22,24,22); layout.setSpacing(12)
        layout.addWidget(back_button(app.t,window.reject),0,Qt.AlignLeft)
        layout.addWidget(label(app.t('Choose one game, application or website.' if individual else 'Choose games, applications or websites. Selected items share one budget.')))
        search=QLineEdit(); search.setPlaceholderText(app.t('Search…')); layout.addWidget(search)
        listing=QListWidget(); listing.setAccessibleName(app.t('Budget members')); layout.addWidget(listing,1)
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
        if not individual:
            for key in ('games','apps','sites'): add(target('category',key))
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
            if individual and len(members)!=1: error.setText(app.t('Choose one game, application or website.')); return
            if not 1<=len(members)<=200: error.setText(app.t('Choose between 1 and 200 members for a shared budget.')); return
            accept(members); window.accept()
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(app.t('Cancel'),window.reject)); actions.addWidget(button(app.t('Use selection'),finish,'primary')); layout.addLayout(actions)
        window.show()
        from .qt_ui import dark_window
        dark_window(window)
