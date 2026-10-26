"""Focus page: Pomodoro, local application/site history and explicit focus lists."""
from dataclasses import asdict
import math
import os
from pathlib import Path
import time

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QHeaderView, QAbstractItemView, QPlainTextEdit, QScrollArea,QListWidget,QListWidgetItem)
from .qt_translation import QCheckBox, QTableWidget, QTableWidgetItem, QLineEdit
from .qt_widgets import label, button, panel, duration, NoWheelDoubleSpinBox,NoWheelDateEdit
from .focus import FocusSettings, domain, matches


class FocusPage(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.setStyleSheet('''
            QDateEdit {background:#172126; color:#edf4f2; border:1px solid #304047; border-radius:8px; padding:7px;}
            QTabWidget::pane {border:1px solid #304047; border-radius:8px;}
            QTabBar::tab {background:#192126; color:#a7b9b9; padding:9px 18px; border:1px solid #304047;}
            QTabBar::tab:selected {background:#24483b; color:#a1f0d2; border-bottom-color:#7de5bf;}
            QTableWidget {border:0;}
        ''')
        self.owner = owner
        self.focus = owner.focus
        self.fingerprint = None
        self.last_refresh = 0
        t = owner.t
        outer=QVBoxLayout(self); outer.setContentsMargins(28,24,28,20); outer.setSpacing(12)
        heading=QHBoxLayout(); heading.addWidget(label(t('Focus & activity'),'title'),1)
        heading.addWidget(button(t('How does focus work?'),self.explain,'quiet')); outer.addLayout(heading)
        self.sections=QTabWidget(); outer.addWidget(self.sections,1)
        focus_page=QWidget(); self.sections.addTab(focus_page,t('Focus mode'))
        activity_page=QWidget(); self.sections.addTab(activity_page,t('Activity history'))
        focus_outer=QVBoxLayout(focus_page); focus_outer.setContentsMargins(0,12,0,0)
        focus_scroll=QScrollArea(); focus_scroll.setWidgetResizable(True); focus_outer.addWidget(focus_scroll)
        focus_content=QWidget(); focus_scroll.setWidget(focus_content)
        focus_box=QVBoxLayout(focus_content); focus_box.setContentsMargins(0,0,5,0); focus_box.setSpacing(14)
        timer_card=panel(); box=QVBoxLayout(timer_card); box.setContentsMargins(22,16,22,16); box.setSpacing(10)
        top=QHBoxLayout(); self.phase_label=label('','section'); top.addWidget(self.phase_label)
        self.timer_state=label('','muted'); top.addWidget(self.timer_state); top.addStretch()
        top.addWidget(button(t('Timer settings'),self.timer_settings,'quiet')); box.addLayout(top)
        timer=QHBoxLayout(); self.clock=label('','metric'); self.clock.setStyleSheet('font-size:46px; font-weight:650;')
        self.clock.setMinimumWidth(175); timer.addWidget(self.clock)
        self.start_button=button(t('Start focus'),self.toggle,'primary'); timer.addWidget(self.start_button)
        self.stop_button=button(t('Stop'),self.reset,'quiet'); self.stop_button.setToolTip(t('Stop the session and reset the timer.'))
        timer.addWidget(self.stop_button); timer.addStretch()
        self.round_label=label('','muted'); timer.addWidget(self.round_label); box.addLayout(timer)
        self.plan_label=label('','muted'); box.addWidget(self.plan_label)
        self.notice=label('','muted'); self.notice.setWordWrap(True); box.addWidget(self.notice); focus_box.addWidget(timer_card)
        rules_card=panel(); rules_box=QVBoxLayout(rules_card); rules_box.setContentsMargins(18,15,18,15); rules_box.setSpacing(10)
        title=QHBoxLayout(); title.addWidget(label(t('What should stay out of your focus session?'),'section'),1)
        title.addWidget(button(t('Edit list'),self.rules_dialog,'quiet')); rules_box.addLayout(title)
        status=QHBoxLayout(); self.mode_label=label('','muted'); status.addWidget(self.mode_label,1)
        self.connection=label('','muted'); status.addWidget(self.connection)
        status.addWidget(button(t('Browser connection'),self.browser_dialog,'quiet')); rules_box.addLayout(status)
        self.rule_tabs=QTabWidget(); self.block_lists={}
        for kind,name in (('site','Websites'),('app','Applications')):
            container=QWidget(); container_box=QVBoxLayout(container); container_box.setContentsMargins(0,12,0,0); container_box.setSpacing(8)
            if kind=='site':
                url_row=QHBoxLayout(); self.url_input=QLineEdit()
                self.url_input.setPlaceholderText(t('Paste a URL or domain, e.g. https://youtube.com'))
                self.url_input.setAccessibleName(t('Website URL or domain')); self.url_input.returnPressed.connect(self.add_url)
                url_row.addWidget(self.url_input,1); self.add_url_button=button(t('Add website'),self.add_url)
                url_row.addWidget(self.add_url_button); container_box.addLayout(url_row)
                hint=label(t('The whole domain and its subdomains will be blocked during work.'),'muted'); hint.setWordWrap(True); container_box.addWidget(hint)
            else: container_box.addWidget(button(t('Add application…'),self.choose_application))
            listing=QListWidget(); listing.setMinimumHeight(76); listing.setMaximumHeight(155)
            listing.setSelectionMode(QAbstractItemView.SingleSelection)
            listing.itemSelectionChanged.connect(self.rule_selection_changed)
            container_box.addWidget(listing); self.block_lists[kind]=listing
            self.rule_tabs.addTab(container,t(name))
        rules_box.addWidget(self.rule_tabs); self.rule_tabs.currentChanged.connect(self.rule_selection_changed)
        bottom=QHBoxLayout(); self.rules_hint=label('','muted'); self.rules_hint.setWordWrap(True); bottom.addWidget(self.rules_hint,1)
        self.remove_rule_button=button(t('Remove'),self.remove_rule,'quiet'); self.remove_rule_button.setEnabled(False)
        title.addWidget(self.remove_rule_button); rules_box.addLayout(bottom)
        self.url_status=label('','muted'); self.url_status.setWordWrap(True); self.url_status.hide(); rules_box.addWidget(self.url_status)
        focus_box.addWidget(rules_card); focus_box.addStretch()
        self._rules_snapshot=None
        history=QVBoxLayout(activity_page); history.setContentsMargins(0,14,0,0); history.setSpacing(12)
        controls=QHBoxLayout(); self.tracking=QCheckBox(t('Measure active time')); self.tracking.setChecked(self.focus.settings.tracking)
        self.tracking.toggled.connect(self.tracking_changed); controls.addWidget(self.tracking,1)
        controls.addWidget(label(t('Day'),'muted')); self.day=NoWheelDateEdit(QDate.currentDate()); self.day.setCalendarPopup(True)
        self.day.setDisplayFormat('yyyy-MM-dd'); self.day.setMaximumDate(QDate.currentDate())
        self.day.dateChanged.connect(lambda *_:self.refresh(force=True)); controls.addWidget(self.day)
        controls.addWidget(button(t('Detailed statistics'),self.open_statistics,'quiet')); history.addLayout(controls)
        privacy=label(t('Only the foreground application or active website counts. Tracking pauses after 60 seconds without input.'),'muted')
        privacy.setWordWrap(True); history.addWidget(privacy)
        self.tabs=QTabWidget(); self.tables={}
        for kind,name in (('app','Applications'),('site','Websites')):
            table=QTableWidget(0,3); table.setHorizontalHeaderLabels([t(name),t('Active time'),t('Focus rule')])
            table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
            for column in (1,2): table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeToContents)
            table.verticalHeader().hide(); table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection); table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.itemSelectionChanged.connect(self.activity_selection_changed)
            self.tables[kind]=table; self.tabs.addTab(table,t(name))
        self.tabs.currentChanged.connect(lambda *_:self.refresh(force=True)); history.addWidget(self.tabs,1)
        self.empty_activity=label('','muted'); self.empty_activity.setWordWrap(True); history.addWidget(self.empty_activity)
        actions=QHBoxLayout(); self.activity_action=button(t('Add to blacklist'),self.toggle_activity_rule); self.activity_action.setEnabled(False)
        actions.addWidget(self.activity_action); actions.addStretch()
        actions.addWidget(label(t('Game history is available in Statistics → Games.'),'muted')); history.addLayout(actions)
        self.sections.currentChanged.connect(lambda *_:self.refresh(force=True))
        self.refresh(force=True)

    def explain(self):
        dialog,box=self.dialog(self.owner.t('How does focus work?'),620)
        for text in ('Start a work interval to enable your blacklist. Pausing or stopping releases the restrictions immediately.',
                     'Breaks start automatically. After a break, you choose when to start working again.',
                     'Website blocking needs the paired browser extension. Protected games retain their existing minimization permission.',
                     'Activity history works independently of the timer and is stored on this computer.'):
            note=label(self.owner.t(text)); note.setWordWrap(True); box.addWidget(note)
        box.addWidget(button(self.owner.t('Close'),dialog.accept)); dialog.show()

    def choose_application(self):
        from PySide6.QtWidgets import QFileDialog
        path,_=QFileDialog.getOpenFileName(self,self.owner.t('Choose application'),'','Applications (*.exe)')
        if not path: return
        values=asdict(self.focus.settings); values['block_apps'].append(path)
        self.focus.configure(FocusSettings(**values)); self.owner.update_focus_policy(); self.refresh(force=True)

    def refresh_rules(self):
        import ntpath
        snapshot=(tuple(self.focus.settings.block_sites),tuple(self.focus.settings.block_apps),self.owner.settings.language)
        if snapshot!=self._rules_snapshot:
            self._rules_snapshot=snapshot
            for kind,entries in (('site',snapshot[0]),('app',snapshot[1])):
                listing=self.block_lists[kind]; previous=listing.currentItem(); selected=previous.data(Qt.UserRole) if previous else None
                blocked=listing.blockSignals(True); listing.clear()
                for key in entries:
                    item=QListWidgetItem(key if kind=='site' else ntpath.basename(key)); item.setData(Qt.UserRole,key); item.setToolTip(key)
                    listing.addItem(item)
                    if key==selected: listing.setCurrentItem(item)
                listing.blockSignals(blocked)
                listing.setFixedHeight(min(155,max(44,listing.count()*39+8)))
                listing.setVisible(listing.count()>0)
        self.rule_selection_changed()

    def rule_selection_changed(self,*_):
        kind='site' if self.rule_tabs.currentIndex()==0 else 'app'
        listing=self.block_lists[kind]
        self.remove_rule_button.setEnabled(listing.currentItem() is not None)
        self.rules_hint.setText(self.owner.t('Select an entry to remove it.' if listing.count() else
                                            'Add the websites you want to avoid during work.' if kind=='site' else 'Add applications you want to avoid during work.'))

    def remove_rule(self):
        kind='site' if self.rule_tabs.currentIndex()==0 else 'app'; item=self.block_lists[kind].currentItem()
        if not item: return
        values=asdict(self.focus.settings); field='block_'+kind+'s'
        values[field]=[value for value in values[field] if value!=item.data(Qt.UserRole)]
        self.focus.configure(FocusSettings(**values)); self.owner.update_focus_policy(); self.refresh(force=True)

    def activity_selection_changed(self):
        kind='app' if self.tabs.currentIndex()==0 else 'site'; table=self.tables[kind]
        item=table.item(table.currentRow(),0); self.activity_action.setEnabled(item is not None)
        blocked=False
        if item:
            key=item.data(Qt.UserRole); blocked=self.focus.settings.app_blocked(key) if kind=='app' else self.focus.settings.site_blocked(key)
        inherited=bool(item and kind=='site' and blocked and key not in self.focus.settings.block_sites)
        self.activity_action.setText(self.owner.t('Edit blocking rule' if inherited else 'Remove from blacklist' if blocked else 'Add to blacklist'))

    def toggle_activity_rule(self):
        kind='app' if self.tabs.currentIndex()==0 else 'site'; table=self.tables[kind]; item=table.item(table.currentRow(),0)
        if not item: return
        key=item.data(Qt.UserRole); blocked=self.focus.settings.app_blocked(key) if kind=='app' else self.focus.settings.site_blocked(key)
        if kind=='site' and blocked and key not in self.focus.settings.block_sites:
            self.sections.setCurrentIndex(0); self.rule_tabs.setCurrentIndex(0)
            rules=sorted((rule for rule in self.focus.settings.block_sites if matches(key,rule)),key=len,reverse=True)
            for index in range(self.block_lists['site'].count()):
                entry=self.block_lists['site'].item(index)
                if entry.data(Qt.UserRole)==rules[0]: self.block_lists['site'].setCurrentItem(entry); break
            return
        self.add_selected('remove' if blocked else 'block')

    def open_statistics(self):
        page=self.owner.statistics; page.category.setCurrentIndex(page.category.findData('apps' if self.tabs.currentIndex()==0 else 'websites'))
        page.period.setCurrentIndex(page.period.findData('custom'))
        text=self.day.date().toString('yyyy-MM-dd'); page.start.setText(text); page.end.setText(text); page.apply_dates()
        self.owner.switch_page(1)

    def refresh(self, force=False):
        owner, focus, t = self.owner, self.focus, self.owner.t
        seconds = math.ceil(focus.remaining)
        paused=not focus.running and (focus.phase!='focus' or focus.remaining<focus.settings.work*60)
        if self.sections.currentIndex()==0 or force:
            self.clock.setText(f'{seconds // 60:02d}:{seconds % 60:02d}')
            self.phase_label.setText(t({'focus':'Focus','short_break':'Short break','long_break':'Long break'}[focus.phase]))
            self.timer_state.setText(t('Running' if focus.running else 'Paused' if paused else 'Ready'))
            self.timer_state.setStyleSheet('color:'+('#7de5bf' if focus.running else '#f0ba68' if paused else '#93a3a7')+';')
            self.start_button.setText(t('Pause focus' if focus.running else 'Continue break' if focus.phase!='focus' else 'Resume focus' if paused else 'Start focus'))
            self.stop_button.setEnabled(focus.running or paused or focus.round>0)
            self.round_label.setText(t('Completed rounds: {count}',count=focus.round))
            self.plan_label.setText(t('Work: {work} min · short break: {rest} min',work=focus.settings.work,rest=focus.settings.short_break))
            self.notice.setText(t(focus.notice or ('Blacklist active until this work interval ends.' if focus.restricting else
                                                 'Paused. Restrictions are off until you continue.' if paused else
                                                 'Take a break. Restrictions are off.' if focus.phase!='focus' else
                                                 'Start when you are ready. Your blacklist applies during work.')))
        self.mode_label.setText(t('{apps} apps · {sites} websites',apps=len(focus.settings.block_apps),sites=len(focus.settings.block_sites)))
        bridge = owner.browser_bridge
        self.connection.setText(t('Browser connected' if bridge and bridge.connected else 'Browser not connected'))
        self.connection.setStyleSheet('color:#7de5bf;' if bridge and bridge.connected else 'color:#f0ba68;' if focus.settings.block_sites else 'color:#93a3a7;')
        self.refresh_rules()
        self.sections.setTabText(0,t('Focus mode')); self.sections.setTabText(1,t('Activity history'))
        for index,name in enumerate(('Websites','Applications')): self.rule_tabs.setTabText(index,t(name))
        for kind,table in self.tables.items():
            name='Applications' if kind=='app' else 'Websites'
            self.tabs.setTabText(0 if kind=='app' else 1,t(name)); table.setHorizontalHeaderLabels([t(name),t('Active time'),t('Focus rule')])
        if self.sections.currentIndex()!=1: return
        self.day.setMaximumDate(QDate.currentDate())
        fingerprint = (focus.revision, self.day.date().toString('yyyy-MM-dd'), owner.settings.language)
        if not force and (fingerprint == self.fingerprint or time.monotonic() - self.last_refresh < 5): return
        self.fingerprint = fingerprint; self.last_refresh = time.monotonic()
        focus.flush()
        rows=[('app',key[len('activity:app:'):],name,amount) for _,key,name,_,amount in focus.history(fingerprint[1],fingerprint[1],'apps')]
        rows += [row for row in focus.usage(fingerprint[1]) if row[0]=='site']
        for kind, table in self.tables.items():
            name = 'Applications' if kind == 'app' else 'Websites'
            self.tabs.setTabText(0 if kind == 'app' else 1, t(name))
            table.setHorizontalHeaderLabels([t(name), t('Active time'), t('Focus rule')])
            selected = table.item(table.currentRow(), 0)
            selected_key = selected.data(Qt.UserRole) if selected else None
            values = sorted((row for row in rows if row[0] == kind), key=lambda row: (-row[3], row[2]))
            table.setRowCount(len(values))
            for index, (_, key, name, amount) in enumerate(values):
                first = QTableWidgetItem(name); first.setData(Qt.UserRole, key); first.setToolTip(key)
                table.setItem(index, 0, first); table.setItem(index, 1, QTableWidgetItem(duration(amount)))
                blocked = focus.settings.app_blocked(key) if kind == 'app' else focus.settings.site_blocked(key)
                table.setItem(index, 2, QTableWidgetItem(t('Blocked during focus' if blocked else 'Allowed during focus')))
                if key == selected_key: table.selectRow(index)
        kind='app' if self.tabs.currentIndex()==0 else 'site'
        self.empty_activity.setText(t('No recorded applications on this day.' if kind=='app' else 'No recorded websites on this day. Keep the browser extension connected while browsing.'))
        self.empty_activity.setVisible(self.tables[kind].rowCount()==0)
        self.activity_selection_changed()

    def toggle(self):
        focus = self.focus
        if focus.running: focus.pause(self.owner.focus_awake())
        else: focus.start(self.owner.focus_awake())
        self.owner.update_focus_policy()
        self.refresh(force=True)

    def reset(self):
        self.focus.stop(); self.owner.update_focus_policy(); self.refresh(force=True)

    def tracking_changed(self, enabled):
        values = asdict(self.focus.settings); values['tracking'] = enabled
        self.focus.configure(FocusSettings(**values))
        self.owner.update_focus_policy(); self.refresh(force=True)

    def add_selected(self, action):
        kind = 'app' if self.tabs.currentIndex() == 0 else 'site'
        table = self.tables[kind]; item = table.item(table.currentRow(), 0)
        if not item: return
        values = asdict(self.focus.settings)
        key = item.data(Qt.UserRole)
        entries = values['block_' + kind + 's']
        if action == 'block': entries.append(key)
        else: values['block_' + kind + 's'] = [value for value in entries if value != key]
        self.focus.configure(FocusSettings(**values)); self.owner.update_focus_policy(); self.refresh(force=True)

    def add_url(self):
        t = self.owner.t
        try:
            host = domain(self.url_input.text())
            values = asdict(self.focus.settings); values['block_sites'].append(host)
            self.focus.configure(FocusSettings(**values))
        except ValueError as exc:
            self.url_status.setText(t(str(exc))); self.url_status.show(); return
        self.url_input.clear(); self.owner.update_focus_policy(); self.refresh(force=True)
        self.url_status.setText(t('Added to blacklist: {domain}',domain=host))
        self.url_status.show()

    def timer_settings(self):
        owner, t = self.owner, self.owner.t
        dialog, box = self.dialog(t('Timer settings'), 510)
        fields = {}
        for key, name, maximum in (('work', 'Focus minutes', 240), ('short_break', 'Short break minutes', 60),
                                    ('long_break', 'Long break minutes', 120), ('rounds', 'Rounds before long break', 12)):
            row = QHBoxLayout(); row.addWidget(label(t(name)), 1)
            edit = NoWheelDoubleSpinBox(); edit.setDecimals(0); edit.setRange(1, maximum)
            edit.setValue(getattr(self.focus.settings, key)); edit.setAccessibleName(t(name))
            row.addWidget(edit); box.addLayout(row); fields[key] = edit
        help_label = label(t('If an interval is already in progress, new durations apply to the next interval.'), 'muted')
        help_label.setWordWrap(True); box.addWidget(help_label)
        def save():
            values = asdict(self.focus.settings); values.update({key: int(edit.value()) for key, edit in fields.items()})
            self.focus.configure(FocusSettings(**values)); self.refresh(force=True); dialog.accept()
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(t('Cancel'),dialog.reject))
        save_button=button(t('Save'),save,'primary'); save_button.setDefault(True); actions.addWidget(save_button)
        box.addLayout(actions); dialog.show()

    def rules_dialog(self):
        owner, t = self.owner, self.owner.t
        dialog, box = self.dialog(t('Blacklist'), 760)
        dialog.resize(760, 430)
        help_label = label(t('One entry per line. Paste website URLs or domains; the whole domain and its subdomains are blocked during focus. For applications, choose the .exe file. Remove a line to stop blocking it.'), 'muted')
        help_label.setWordWrap(True); box.addWidget(help_label)
        grid = QGridLayout(); editors = {}
        for index, (key, name) in enumerate((('block_apps', 'Blocked applications'), ('block_sites', 'Blocked websites'))):
            cell = QVBoxLayout(); cell.addWidget(label(t(name), 'section'))
            edit = QPlainTextEdit('\n'.join(getattr(self.focus.settings, key))); edit.setAccessibleName(t(name))
            edit.setPlaceholderText(r'C:\Program Files\App\app.exe' if key.endswith('apps') else 'example.com')
            edit.setMinimumHeight(125); cell.addWidget(edit, 1); editors[key] = edit
            if key.endswith('apps'):
                def browse(checked=False, target=edit):
                    from PySide6.QtWidgets import QFileDialog
                    path, _ = QFileDialog.getOpenFileName(dialog, t('Choose application'), '', 'Applications (*.exe)')
                    if path: target.appendPlainText(path.replace('/', '\\'))
                cell.addWidget(button(t('Choose application'), browse))
            grid.addLayout(cell, 0, index)
        box.addLayout(grid, 1)
        error = label('', 'danger'); error.setWordWrap(True); box.addWidget(error)
        def save():
            values = asdict(self.focus.settings)
            values.update({key: [line.strip() for line in edit.toPlainText().splitlines() if line.strip()] for key, edit in editors.items()})
            try: self.focus.configure(FocusSettings(**values))
            except ValueError as exc: error.setText(t(str(exc))); return
            owner.update_focus_policy(); self.refresh(force=True); dialog.accept()
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(t('Cancel'),dialog.reject))
        save_button=button(t('Save'),save,'primary'); save_button.setDefault(True); actions.addWidget(save_button)
        box.addLayout(actions); dialog.show()

    def browser_dialog(self):
        owner, t = self.owner, self.owner.t
        bridge = owner.enable_browser_bridge()
        dialog, box = self.dialog(t('Connect Brave / browser'), 720)
        instructions = label(t('1. Open brave://extensions and enable Developer mode.\n2. Choose Load unpacked and select the extension folder below.\n3. Open the extension’s settings and paste the pairing code. Choose Brave, then Save & connect.'), 'muted')
        instructions.setWordWrap(True); box.addWidget(instructions)
        from . import __file__ as package_path
        folder = Path(package_path).parent / 'browser_extension'
        path = QLineEdit(str(folder)); path.setReadOnly(True); box.addWidget(path)
        box.addWidget(button(t('Open extension folder'), lambda: os.startfile(str(folder))))
        if bridge and not bridge.error:
            code = QLineEdit(bridge.pairing()); code.setReadOnly(True); code.setEchoMode(QLineEdit.Password)
            box.addWidget(code)
            box.addWidget(button(t('Copy pairing code'), lambda: owner.copy_browser_pairing(bridge.pairing())))
            explanation = label(t('The pairing code connects only to this Windows profile on this computer. Enable the extension in each browser you want to track.'), 'muted')
            explanation.setWordWrap(True); box.addWidget(explanation)
        else:
            error = label(t('Browser connection could not start. Another monitor may be using the local port.'), 'danger')
            error.setWordWrap(True); box.addWidget(error)
        dialog.show()

    def dialog(self, title, width):
        dialog = self.owner._dialog(title, width)
        box = QVBoxLayout(dialog); box.setContentsMargins(24, 22, 24, 22); box.setSpacing(14)
        from .qt_ui import dark_window
        dark_window(dialog)
        return dialog, box
