"""Built-in and user-scheduled reminders in one local, cached list."""
from .quota import current_day
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt,QSize,QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QScrollArea
from .qt_widgets import label,button,back_button,panel,glyph,ACCENT,separator
from .qt_translation import QCheckBox,QDialog
from . import notification_drafts
from .notification_text import KINDS,notification_text
from .schedule import day_settings,week_plans
from .budget import quota_plan
from .restriction_policy import legacy_warning_active

TITLES=dict(zip(KINDS,('Before the daily limit','Daily limit reached',
                       'Playing again after the limit','Bedtime reminder')))


class NotificationsPage(QWidget):
    def __init__(self,app):
        super().__init__(); self.app=app; self.closed=False; self._settings=None; self._day=None; self._revision=0; self._rows_revision=-1
        self.changes={key:value for key,value in notification_drafts.read(app.store).items() if value!=notification_drafts.original(app.settings,key)}
        self.draft_timer=QTimer(self); self.draft_timer.setSingleShot(True); self.draft_timer.timeout.connect(self.flush_draft)
        outer=QVBoxLayout(self); outer.setContentsMargins(32,25,32,22); outer.setSpacing(16)
        header=QHBoxLayout(); self.back=back_button(app.t,self.show_list); self.back.hide(); header.addWidget(self.back)
        header.addWidget(label(app.t('Notifications'),'title'),1)
        self.add_button=button(app.t('Add new'),self.create,'primary'); header.addWidget(self.add_button)
        header.addWidget(app.page_settings_button('notifications')); outer.addLayout(header)
        note=label(app.t('Create reminders with your own triggers and actions.'),'muted')
        note.setWordWrap(True); outer.addWidget(note)
        display=panel(); self.display=display; display_layout=QVBoxLayout(display); display_layout.setContentsMargins(18,14,18,14); display_layout.setSpacing(10)
        self.fullscreen=QCheckBox(app.t('Show over fullscreen games')); self.fullscreen.setAccessibleName(app.t('Show over fullscreen games'))
        display_layout.addWidget(self.fullscreen)
        self.protected=QCheckBox(app.t('Also show in anti-cheat games')); self.protected.setAccessibleName(app.t('Also show in anti-cheat games'))
        display_layout.addWidget(self.protected)
        self.display_note=label(app.t('Applies to countdowns and notifications.'),'muted'); self.display_note.setWordWrap(True); display_layout.addWidget(self.display_note)
        display_layout.addWidget(separator())
        self.details=QCheckBox(app.t('Detailed RTSS countdown')); self.details.setAccessibleName(app.t('Detailed RTSS countdown'))
        display_layout.addWidget(self.details)
        detail_note=label(app.t('Show the event name and daily budget remaining. Turn off to show only the countdown.'),'muted')
        detail_note.setWordWrap(True); display_layout.addWidget(detail_note)
        self.display_status=label('','muted'); self.display_status.setWordWrap(True); self.display_status.hide(); display_layout.addWidget(self.display_status)
        outer.addWidget(display)
        self.fullscreen.clicked.connect(self.toggle_fullscreen); self.protected.clicked.connect(self.toggle_protected)
        self.details.clicked.connect(self.toggle_details)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); outer.addWidget(self.scroll,1)
        body=QWidget(); body_layout=QVBoxLayout(body); body_layout.setContentsMargins(0,0,8,0); body_layout.setAlignment(Qt.AlignTop)
        self.list_widget=QWidget(); self.rows=QVBoxLayout(self.list_widget); self.rows.setContentsMargins(0,0,0,0)
        self.rows.setSpacing(10); self.rows.setAlignment(Qt.AlignTop); body_layout.addWidget(self.list_widget); self.scroll.setWidget(body)
        self.empty=label(app.t('No notifications yet. Add one to get started.'),'muted'); self.empty.setWordWrap(True); body_layout.addWidget(self.empty)
        from .qt_notification_editor import NotificationEditor
        self.editor=NotificationEditor(self); body_layout.addWidget(self.editor); self.editor.hide()
        footer=QHBoxLayout(); self.error=label('','danger'); self.error.setWordWrap(True); footer.addWidget(self.error,1)
        self.discard=button(app.t('Discard draft'),self.discard_draft,'quiet'); footer.addWidget(self.discard)
        self.save_button=button(app.t('Save changes'),self.save,'primary'); footer.addWidget(self.save_button); outer.addLayout(footer)
        self.draft_note=label('','muted'); self.draft_note.setWordWrap(True); outer.addWidget(self.draft_note)
        self.row_keys=[]; self.refresh()

    def entries(self):
        app=self.app; t=app.t; settings=self.draft_settings(); plan=quota_plan(settings); night=plan
        week=week_plans(settings); entries=[]
        for kind in KINDS:
            if kind in settings.notification_overrides or kind in settings.removed_notifications: continue
            if kind=='bedtime':
                enabled=any(p['bedtime_enabled'] and p['bedtime_warning_enabled'] for p in week.values())
                times={(p['bedtime_enabled'],p['bedtime_warning_minute'],p['bedtime_minute']) for p in week.values()}
                timing=t('Varies by day') if len(times)>1 else t('Daily at {time}',time=f'{night.bedtime_warning_minute//60:02d}:{night.bedtime_warning_minute%60:02d}')
                text=notification_text(night,kind)
            else:
                enabled=settings.game_budget_enabled and (kind=='warning' or settings.limit_popup_enabled)
                enabled=enabled and (legacy_warning_active(settings.restriction_plans,'shared-games') if kind=='warning'
                                     else 'shared-games' not in settings.restriction_plans)
                if kind=='session': timing=t('When playing again after reaching the daily limit')
                else:
                    field='warning_seconds' if kind=='warning' else 'limit_seconds'
                    timing=t('Varies by day') if len({p[field] for p in week.values()})>1 else t('After {minutes:g} minutes of gaming',minutes=getattr(plan,field)/60)
                text=notification_text(plan,kind)
            state=t('Countdown or popup') if kind=='warning' and enabled and settings.overlay_enabled and settings.overlay_replace_warning else t('Enabled' if enabled else 'Disabled')
            entries.append(('builtin:'+kind,t(TITLES[kind]),timing+' · '+state,text,'preset:moon' if kind=='bedtime' else 'preset:bell'))
        from .notification_rules import normalized,TRIGGERS,title,message
        records=[('builtin:'+kind,item) for kind,item in settings.notification_overrides.items()]
        records += [('scheduled:'+item['id'],item) for item in settings.scheduled_notifications]
        for key,item in records:
            item=normalized(item); trigger=item['trigger']; timing=t(TRIGGERS[trigger])
            if trigger=='time': timing=t('Daily at {time}',time=f'{item["minute"]//60:02d}:{item["minute"]%60:02d}')
            elif trigger=='pomodoros': timing=t('After {count} focus rounds today',count=item['count'])
            entries.append((key,title(item,t),timing+' · '+t('Enabled' if item['enabled'] else 'Disabled'),message(item,plan),item['icon']))
        return entries

    def refresh(self):
        for widget,checked in ((self.fullscreen,self.app.settings.overlay_rtss_auto),(self.protected,self.app.overlay_consents.display_enabled),
                               (self.details,self.app.settings.overlay_rtss_details)):
            blocked=widget.blockSignals(True); widget.setChecked(checked); widget.blockSignals(blocked)
        self.discard.setVisible(bool(self.changes))
        self.draft_note.setText(self.app.t('Draft saved on this computer. Save changes to apply.') if self.changes else '')
        if self._settings is self.app.settings and self._day==current_day(self.app.settings) and self._rows_revision==self._revision: return
        self._rows_revision=self._revision
        self._settings=self.app.settings; self._day=current_day(self.app.settings)
        while self.rows.count():
            item=self.rows.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.row_keys=[]
        for key,title,subtitle,text,icon_path in self.entries():
            card=panel(); card.setProperty('notificationKey',key)
            row=QHBoxLayout(card); row.setContentsMargins(18,15,18,15); row.setSpacing(16)
            from .qt_notification_options import notification_icon
            icon=notification_icon(icon_path,28)
            badge=label(); badge.setFixedSize(36,36); badge.setPixmap(icon.pixmap(28,28)); row.addWidget(badge,0,Qt.AlignTop)
            content=QVBoxLayout(); content.setSpacing(5)
            for value,role in ((title,'section'),(subtitle,'muted'),(text[:180]+('…' if len(text)>180 else ''),'muted')):
                line=label(value,role); line.setTextFormat(Qt.PlainText); line.setWordWrap(True); content.addWidget(line)
            row.addLayout(content,1)
            edit=button(self.app.t('Edit'),lambda checked=False,k=key:self.edit(k),'quiet')
            edit.setAccessibleName(self.app.t('Edit {name}',name=title)); row.addWidget(edit)
            delete=button('',lambda checked=False,k=key,n=str(title):self.confirm_remove(k,n),'quiet')
            delete.setIcon(glyph('trash')); delete.setIconSize(QSize(20,20)); delete.setFixedSize(40,40)
            delete.setAccessibleName(self.app.t('Delete {name}',name=title)); delete.setToolTip(self.app.t('Delete {name}',name=title)); row.addWidget(delete)
            self.rows.addWidget(card); self.row_keys.append(key)
        self.empty.setVisible(not self.row_keys and self.editor.isHidden())

    def display_saved(self,enabled):
        self.app.apply_display_settings()
        message='If a game is already running, save and restart it after enabling this.' if enabled else ''
        if enabled and not self.app.rtss_available(): message='Install RTSS 7.3.7 or newer first.'
        self.display_status.setText(self.app.t(message) if message else ''); self.display_status.setVisible(bool(message))

    def toggle_fullscreen(self,enabled):
        try:
            settings=replace(self.app.settings,overlay_rtss_auto=enabled).validate()
            self.app.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
            self.display_saved(enabled)
        except (ValueError,OSError,SQLiteError): self.display_error()

    def toggle_protected(self,enabled):
        # Keep the switch off until the user has explicitly accepted and saved.
        self.refresh()
        if enabled:
            from .qt_overlay_consent import request_display_consent
            if not request_display_consent(self.app,self): return
        try:
            self.app.overlay_consents.set_display_enabled(enabled)
            self.display_saved(enabled)
        except (ValueError,OSError,SQLiteError): self.display_error()

    def toggle_details(self,enabled):
        try:
            settings=replace(self.app.settings,overlay_rtss_details=enabled).validate()
            self.app.store.save_settings(settings); self.app.settings=self.app.catalog.settings=settings
            self.app.update_overlay(); self.refresh()
            self.display_status.clear(); self.display_status.hide()
        except (ValueError,OSError,SQLiteError): self.display_error()

    def display_error(self):
        self.refresh(); self.display_status.setText(self.app.t('Could not save settings. Try again.')); self.display_status.show()

    def draft_settings(self): return notification_drafts.apply(self.app.settings,self.changes)

    def record(self,key,item):
        notification_drafts.update(self.changes,self.app.settings,key,item); self._revision+=1
        self.draft_timer.start(350); self.error.clear(); self.discard.setVisible(bool(self.changes))
        self.draft_note.setText(self.app.t('Unapplied changes. Save changes to apply.') if self.changes else '')

    def flush_draft(self):
        if self.closed: return
        self.draft_timer.stop()
        try:
            notification_drafts.write(self.app.store,self.changes)
            self.draft_note.setText(self.app.t('Draft saved on this computer. Save changes to apply.') if self.changes else '')
        except (OSError,SQLiteError): self.show_error('Could not save the draft. Keep this window open and try again.')

    def hideEvent(self,event):
        self.flush_draft(); super().hideEvent(event)

    def close_draft(self):
        self.flush_draft(); self.closed=True; self.draft_timer.stop()

    def create(self):
        import uuid
        self.edit('scheduled:'+uuid.uuid4().hex,new=True)

    def edit(self,key,new=False):
        from copy import deepcopy
        self.editor.before=deepcopy(self.changes)
        self.editor.open(key,new); self.editor.show(); self.list_widget.hide(); self.empty.hide(); self.display.hide()
        self.back.show(); self.add_button.hide(); self.scroll.verticalScrollBar().setValue(0)

    def show_list(self):
        self.editor.hide(); self.list_widget.show(); self.display.show(); self.back.hide(); self.add_button.show()
        self.flush_draft(); self.refresh(); self.scroll.verticalScrollBar().setValue(0)

    def cancel_edit(self):
        self.editor.restore_previous(); self._revision+=1; self.error.clear(); self.show_list()

    def ask_delete(self,name,*,discard=False):
        t=self.app.t; dialog=QDialog(self); dialog.setObjectName('Surface'); dialog.resize(540,200)
        dialog.setWindowTitle(t('Discard draft' if discard else 'Delete notification'))
        layout=QVBoxLayout(dialog); layout.setContentsMargins(26,24,26,24); layout.setSpacing(14)
        title=label(t('Discard all unfinished notification changes?' if discard else 'Delete “{name}”?',**({} if discard else {'name':name})),'section')
        title.setWordWrap(True); layout.addWidget(title)
        note=label(t('Saved notifications will be kept.' if discard else 'Time budgets and recorded activity history will be kept. Save changes to apply.'),'muted')
        note.setWordWrap(True); layout.addWidget(note); actions=QHBoxLayout(); actions.addStretch()
        cancel=button(t('Cancel'),dialog.reject); cancel.setDefault(True); actions.addWidget(cancel)
        delete=button(t('Discard draft' if discard else 'Delete'),dialog.accept,'danger-action'); delete.setAutoDefault(False); actions.addWidget(delete)
        layout.addLayout(actions)
        from .qt_ui import dark_window
        dark_window(dialog); cancel.setFocus(); return dialog.exec()==QDialog.Accepted

    def confirm_remove(self,key,name):
        if self.ask_delete(name): self.record(key,None); self.flush_draft(); self.refresh()

    def discard_draft(self):
        if self.ask_delete('',discard=True):
            self.changes.clear(); self._revision+=1; self.error.clear(); self.show_list()

    def show_error(self,text): self.error.setText(self.app.t(text))

    def save(self):
        from .notification_rules import validate_files
        try:
            settings=self.draft_settings().validate()
            for key,item in self.changes.items():
                if item and 'id' in item: validate_files(item)
            self.app.store.save_settings(settings)
            self.app.settings=self.app.catalog.settings=settings
            self.changes.clear(); self._revision+=1; self.error.clear(); self.show_list()
            self.app.set_status('Notifications saved.')
        except (ValueError,OSError,SQLiteError) as exc:
            self.show_error(str(exc) if isinstance(exc,ValueError) else 'Could not save notifications. Try again.')
            self.flush_draft()
