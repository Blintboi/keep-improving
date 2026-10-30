"""Application and website libraries, with appearance owned by each activity."""
import ntpath
from PySide6.QtCore import Qt,QSize,QPoint,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QFileDialog,QInputDialog
from .qt_translation import QLineEdit
from .qt_widgets import label,button,panel
from .activities import activity_key,activity_settings,has_budget,known_activities,matching_rules
from .wellbeing import target
from .activity_identity import canonical_member
from .qt_activity_icons import ActivityIcons


class ActivityList(QWidget):
    def __init__(self,app,kind):
        super().__init__(); self.app=app; self.kind=kind; self.entries=[]; self.signature=None
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); box.setSpacing(12)
        search=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText(app.t('Search activities…'))
        search.addWidget(self.search,1); search.addWidget(button(app.t('Refresh'),self.refresh)); box.addLayout(search)
        self.note=label(app.t('Measured activities appear here automatically. You can also add one with the Add button.'),'muted'); self.note.setWordWrap(True); box.addWidget(self.note)
        self.list=QListWidget(); self.list.setAccessibleName(app.t('Applications' if kind=='app' else 'Websites')); self.list.setIconSize(QSize(42,42))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QHBoxLayout(); content.setSpacing(14); content.addWidget(self.list,1); box.addLayout(content,1)
        self.empty=label(app.t('No activities match this view.'),'muted'); self.empty.setWordWrap(True); box.insertWidget(2,self.empty)
        self.detail=panel(); self.detail.setFixedWidth(290); detail=QVBoxLayout(self.detail); detail.setContentsMargins(20,16,20,16); detail.setSpacing(10)
        heading=QHBoxLayout(); heading.setSpacing(12); self.icon_label=label(''); self.icon_label.setFixedSize(56,56); heading.addWidget(self.icon_label)
        self.name=label('','section'); self.name.setWordWrap(True); heading.addWidget(self.name,1); detail.addLayout(heading)
        self.status=label('','muted'); self.status.setWordWrap(True); detail.addWidget(self.status)
        self.countdown=button(app.t('Countdown settings…'),self.edit_countdown,'primary'); detail.addWidget(self.countdown)
        self.budget=button(app.t('Set time budget…'),self.edit_budget); detail.addWidget(self.budget)
        side=QVBoxLayout(); side.addWidget(self.detail); side.addStretch(); content.addLayout(side); self.detail.hide()
        self.search.textChanged.connect(self.filter); self.list.currentItemChanged.connect(self.select)
        self.list.itemDoubleClicked.connect(lambda *_:self.edit_countdown() if self.countdown.isEnabled() else self.edit_budget())
        self._items={}; self._displayed_icons={}; self._detail_icon=None; self.icons=ActivityIcons(app,self)
        self.icon_timer=QTimer(self); self.icon_timer.setSingleShot(True); self.icon_timer.timeout.connect(self.load_visible_icons)
        self.list.verticalScrollBar().valueChanged.connect(self.schedule_icons); self.icons.changed.connect(self.icon_changed)

    def schedule_icons(self,*args):
        if hasattr(self,'icon_timer') and self.isVisible(): self.icon_timer.start(0)

    def showEvent(self,event): super().showEvent(event); self.schedule_icons()
    def hideEvent(self,event):
        super().hideEvent(event)
        if hasattr(self,'icons'): self.icon_timer.stop(); self.icons.pause()
    def resizeEvent(self,event): super().resizeEvent(event); self.schedule_icons()

    def load_visible_icons(self):
        if not self.isVisible() or self.app.isMinimized(): self.icons.pause(); return
        names={activity_key(member):name for member,name in self.entries}
        first=self.list.indexAt(QPoint(6,6)).row(); wanted=[]
        for row in range(max(0,first),min(self.list.count(),max(0,first)+40)):
            item=self.list.item(row)
            if self.list.visualItemRect(item).top()>=self.list.viewport().height(): break
            member=item.data(Qt.UserRole); name=names.get(activity_key(member),member['value'])
            self.display_icon(activity_key(member),self.icons.icon(member,name)); wanted.append((member,name))
        if selected:=self.selected():
            name=names.get(activity_key(selected),selected['value'])
            self.display_icon(activity_key(selected),self.icons.icon(selected,name)); wanted.insert(0,(selected,name))
        # Warm the whole open library once. Scrolling must not cancel/restart icons.
        self.icons.request_visible(wanted+self.entries)

    def display_icon(self,key,icon):
        identity=icon.cacheKey()
        if (item:=self._items.get(key)) is not None and self._displayed_icons.get(key)!=identity:
            item.setIcon(icon); self._displayed_icons[key]=identity
        if (member:=self.selected()) and activity_key(member)==key and self._detail_icon!=(key,identity):
            self.icon_label.setPixmap(icon.pixmap(56,56)); self._detail_icon=(key,identity)

    def icon_changed(self,key):
        icon=self.icons.cache.get(key)
        if icon is None: return
        self.display_icon(key,icon)

    def selected(self):
        item=self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def refresh(self):
        sources={}
        self.entries=[(member,name) for member,name in known_activities(self.app.store,self.app.settings,self.app.catalog,sources) if member['kind']==self.kind]
        self.icons.set_sources(sources)
        self.filter()

    def filter(self,*args):
        selected=self.selected(); key=activity_key(selected) if selected else None; query=self.search.text().strip().casefold()
        rows=[(member,name) for member,name in self.entries if query in (name+' '+member['value']).casefold()]
        signature=(self.app.settings.language,[(activity_key(m),n,self.summary(m)) for m,n in rows])
        if signature!=self.signature:
            self.signature=signature; self.list.blockSignals(True); self.list.clear(); self._items={}; self._displayed_icons={}
            chosen=0
            for index,(member,name) in enumerate(rows):
                item=QListWidgetItem(name+'\n'+self.summary(member)); item.setData(Qt.UserRole,member)
                icon=self.icons.icon(member,name)
                item.setToolTip(member['value']); item.setSizeHint(QSize(0,68)); item.setIcon(icon)
                self.list.addItem(item); self._items[activity_key(member)]=item; self._displayed_icons[activity_key(member)]=icon.cacheKey()
                if activity_key(member)==key: chosen=index
            if rows: self.list.setCurrentRow(chosen)
            self.list.blockSignals(False)
        self.empty.setVisible(not rows); self.list.setVisible(bool(rows)); self.select(); self.schedule_icons()

    def summary(self,member):
        rules=matching_rules(self.app.settings,member)
        return ', '.join(rule['name'] for rule in rules) if rules else self.app.t('No time budget')

    def select(self,*args):
        member=self.selected(); self.detail.setVisible(member is not None)
        if not member: return
        self.name.setText(next((name for item,name in self.entries if item==member),member['value']))
        available=has_budget(self.app.settings,member); self.countdown.setEnabled(available)
        self.status.setText(self.app.t('Countdown on' if activity_settings(self.app.settings,member).overlay_enabled else 'Countdown off') if available else
                            self.app.t('Set an individual or shared time budget first to use a countdown.'))
        self.display_icon(activity_key(member),self.icons.icon(member,self.name.text())); self.schedule_icons()

    def edit_countdown(self):
        member=self.selected()
        if member and has_budget(self.app.settings,member): self.app.game_countdown_dialog(activity_key(member))

    def edit_budget(self):
        member=self.selected()
        if not member: return
        rules=matching_rules(self.app.settings,member)
        if len(rules)==1:
            self.app.open_budget(); self.app.budget_editor.show_editor(rules[0]['id'])
        elif rules: self.app.open_budget()
        else: self.app.open_budget(member=member)

    def add(self):
        if self.kind=='app':
            value,_=QFileDialog.getOpenFileName(self,self.app.t('Choose application'),'','Windows application (*.exe)')
            if not value: return
        else:
            value,accepted=QInputDialog.getText(self,self.app.t('Add website'),self.app.t('Website address'))
            if not accepted or not value.strip(): return
        try:
            member=target(self.kind,value); name=ntpath.basename(member['value']) if self.kind=='app' else member['value']
            with self.app.store.db:
                self.app.store.db.execute('INSERT OR IGNORE INTO activity_items VALUES (?,?,?)',(self.kind,member['value'],name))
            self.search.clear(); self.refresh()
            for index in range(self.list.count()):
                if self.list.item(index).data(Qt.UserRole)==canonical_member(member): self.list.setCurrentRow(index); break
        except ValueError as exc: self.app.message(str(exc))
