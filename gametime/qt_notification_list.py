"""Built-in and user-scheduled reminders in one local, cached list."""
from .quota import current_day
from dataclasses import replace
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QScrollArea
from .qt_widgets import label,button,panel,glyph,ACCENT
from .qt_translation import QCheckBox
from .notification_text import KINDS,notification_text
from .schedule import day_settings,week_plans
from .budget import quota_plan

TITLES=dict(zip(KINDS,('Before the daily limit','Daily limit reached',
                       'Playing again after the limit','Bedtime reminder')))


class NotificationsPage(QWidget):
    def __init__(self,app):
        super().__init__(); self.app=app; self._settings=None; self._day=None; self.editor=None
        outer=QVBoxLayout(self); outer.setContentsMargins(32,25,32,22); outer.setSpacing(16)
        header=QHBoxLayout(); header.addWidget(label(app.t('Notifications'),'title'),1)
        self.add_button=button(app.t('Add notification'),self.create,'primary'); header.addWidget(self.add_button)
        header.addWidget(app.page_settings_button('notifications')); outer.addLayout(header)
        note=label(app.t('Built-in reminders and your own scheduled messages, all in one place.'),'muted')
        note.setWordWrap(True); outer.addWidget(note)
        display=panel(); display_layout=QVBoxLayout(display); display_layout.setContentsMargins(18,14,18,14); display_layout.setSpacing(10)
        self.fullscreen=QCheckBox(app.t('Show over fullscreen games')); self.fullscreen.setAccessibleName(app.t('Show over fullscreen games'))
        display_layout.addWidget(self.fullscreen)
        self.protected=QCheckBox(app.t('Also show in anti-cheat games')); self.protected.setAccessibleName(app.t('Also show in anti-cheat games'))
        display_layout.addWidget(self.protected)
        self.display_note=label(app.t('Applies to countdowns and notifications.'),'muted'); self.display_note.setWordWrap(True); display_layout.addWidget(self.display_note)
        self.display_status=label('','muted'); self.display_status.setWordWrap(True); self.display_status.hide(); display_layout.addWidget(self.display_status)
        outer.addWidget(display)
        self.fullscreen.clicked.connect(self.toggle_fullscreen); self.protected.clicked.connect(self.toggle_protected)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); outer.addWidget(self.scroll,1)
        body=QWidget(); self.rows=QVBoxLayout(body); self.rows.setContentsMargins(0,0,8,0)
        self.rows.setSpacing(10); self.rows.setAlignment(Qt.AlignTop); self.scroll.setWidget(body)
        self.row_keys=[]; self.refresh()

    def entries(self):
        app=self.app; t=app.t; settings=app.settings; plan=quota_plan(settings); night=plan
        week=week_plans(settings); entries=[]
        for kind in KINDS:
            if kind=='bedtime':
                enabled=any(p['bedtime_enabled'] for p in week.values())
                times={(p['bedtime_enabled'],p['bedtime_warning_minute'],p['bedtime_minute']) for p in week.values()}
                timing=t('Varies by day') if len(times)>1 else t('Daily at {time}',time=f'{night.bedtime_warning_minute//60:02d}:{night.bedtime_warning_minute%60:02d}')
                text=notification_text(night,kind)
            else:
                enabled=settings.game_budget_enabled and (kind=='warning' or settings.limit_popup_enabled)
                if kind=='session': timing=t('When playing again after reaching the daily limit')
                else:
                    field='warning_seconds' if kind=='warning' else 'limit_seconds'
                    timing=t('Varies by day') if len({p[field] for p in week.values()})>1 else t('After {minutes:g} minutes of gaming',minutes=getattr(plan,field)/60)
                text=notification_text(plan,kind)
            state=t('Countdown or popup') if kind=='warning' and enabled and settings.overlay_enabled and settings.overlay_replace_warning else t('Enabled' if enabled else 'Disabled')
            entries.append(('builtin:'+kind,t(TITLES[kind]),t('Built-in reminder')+' · '+timing+' · '+state,text,''))
        for item in sorted(settings.scheduled_notifications,key=lambda x:(x['minute'],x['title'].casefold(),x['id'])):
            timing=t('Daily at {time}',time=f'{item["minute"]//60:02d}:{item["minute"]%60:02d}')
            entries.append(('scheduled:'+item['id'],item['title'],t('Custom notification')+' · '+timing+' · '+t('Enabled' if item['enabled'] else 'Disabled'),item['text'],item['icon']))
        return entries

    def refresh(self):
        for widget,checked in ((self.fullscreen,self.app.settings.overlay_rtss_auto),(self.protected,self.app.overlay_consents.display_enabled)):
            blocked=widget.blockSignals(True); widget.setChecked(checked); widget.blockSignals(blocked)
        if self._settings is self.app.settings and self._day==current_day(self.app.settings): return
        self._settings=self.app.settings; self._day=current_day(self.app.settings)
        while self.rows.count():
            item=self.rows.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.row_keys=[]
        for key,title,subtitle,text,icon_path in self.entries():
            card=panel(); card.setProperty('notificationKey',key)
            row=QHBoxLayout(card); row.setContentsMargins(18,15,18,15); row.setSpacing(16)
            icon=QIcon(icon_path) if icon_path else QIcon()
            if icon.isNull(): icon=glyph('bell',ACCENT,28)
            badge=label(); badge.setFixedSize(36,36); badge.setPixmap(icon.pixmap(28,28)); row.addWidget(badge,0,Qt.AlignTop)
            content=QVBoxLayout(); content.setSpacing(5)
            for value,role in ((title,'section'),(subtitle,'muted'),(text[:180]+('…' if len(text)>180 else ''),'muted')):
                line=label(value,role); line.setTextFormat(Qt.PlainText); line.setWordWrap(True); content.addWidget(line)
            row.addLayout(content,1)
            edit=button(self.app.t('Edit'),lambda checked=False,k=key:self.edit(k),'quiet')
            edit.setAccessibleName(self.app.t('Edit {name}',name=title)); row.addWidget(edit)
            self.rows.addWidget(card); self.row_keys.append(key)

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

    def display_error(self):
        self.refresh(); self.display_status.setText(self.app.t('Could not save settings. Try again.')); self.display_status.show()

    def create(self): self.edit(None)

    def edit(self,key):
        if self.editor and self.editor.isVisible():
            self.editor.raise_(); self.editor.activateWindow(); return
        if key and key.startswith('builtin:'):
            from .qt_notifications import messages_dialog
            self.editor=messages_dialog(self.app,initial_kind=key.split(':',1)[1])
        else:
            from .qt_scheduled_notifications import dialog
            self.editor=dialog(self.app,initial_id=key.split(':',1)[1] if key else None,single=True)
        self.editor.finished.connect(self.editor_finished)

    def editor_finished(self,*args):
        self.editor=None; self.refresh()
