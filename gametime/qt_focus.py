"""Focus timer and explicit application and website blocklists."""
from dataclasses import asdict
import math
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QAbstractItemView, QPlainTextEdit, QScrollArea,QListWidget,QListWidgetItem)
from .qt_translation import QLineEdit
from .qt_widgets import label, button, panel, NoWheelDoubleSpinBox
from .focus import FocusSettings, domain


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
        t = owner.t
        outer=QVBoxLayout(self); outer.setContentsMargins(28,24,28,20); outer.setSpacing(12)
        heading=QHBoxLayout(); heading.addWidget(label(t('Focus mode'),'title'),1)
        heading.addWidget(button(t('How does focus work?'),self.explain,'quiet')); outer.addLayout(heading)
        focus_scroll=QScrollArea(); focus_scroll.setWidgetResizable(True); outer.addWidget(focus_scroll,1)
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
            container=QWidget(); container_box=QVBoxLayout(container); container_box.setContentsMargins(12,12,12,12); container_box.setSpacing(8)
            if kind=='site':
                url_row=QHBoxLayout(); self.url_input=QLineEdit()
                self.url_input.setPlaceholderText(t('Paste a URL or domain, e.g. https://youtube.com'))
                self.url_input.setAccessibleName(t('Website URL or domain')); self.url_input.returnPressed.connect(self.add_url)
                url_row.addWidget(self.url_input,1); self.add_url_button=button(t('Add website'),self.add_url)
                url_row.addWidget(self.add_url_button); container_box.addLayout(url_row)
                hint=label(t('The whole domain and its subdomains will be blocked during work.'),'muted'); hint.setWordWrap(True); container_box.addWidget(hint)
            else:
                choices=QHBoxLayout()
                choices.addWidget(button(t('Choose from detected applications…'),self.choose_detected_applications))
                choices.addWidget(button(t('Choose executable…'),self.choose_application))
                choices.addStretch(); container_box.addLayout(choices)
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
        self.refresh(force=True)

    def explain(self):
        dialog,box=self.dialog(self.owner.t('How does focus work?'),620)
        for text in ('Start a work interval to enable your blacklist. Pausing or stopping releases the restrictions immediately.',
                     'Breaks start automatically. After a break, you choose when to start working again.',
                     'Website blocking needs the paired browser extension. Protected games retain their existing minimization permission.',
                     'Activity history works independently of the timer and is shared when computer sync is enabled.'):
            note=label(self.owner.t(text)); note.setWordWrap(True); box.addWidget(note)
        box.addWidget(button(self.owner.t('Close'),dialog.accept)); dialog.show()

    def choose_application(self):
        from PySide6.QtWidgets import QFileDialog
        path,_=QFileDialog.getOpenFileName(self,self.owner.t('Choose application'),'','Applications (*.exe)')
        if not path: return
        values=asdict(self.focus.settings); values['block_apps'].append(path)
        self.focus.configure(FocusSettings(**values)); self.owner.update_focus_policy(); self.refresh(force=True)

    def choose_detected_applications(self):
        t=self.owner.t; dialog,box=self.dialog(t('Detected applications'),720)
        note=label(t('Select one or more previously detected applications. The full executable path is shown when you hover over an entry.'),'muted')
        note.setWordWrap(True); box.addWidget(note)
        listing=QListWidget(); listing.setMinimumHeight(200); listing.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for path,name in self.focus.store.db.execute("SELECT key,name FROM activity_items WHERE kind='app' ORDER BY lower(name),key"):
            item=QListWidgetItem(name); item.setData(Qt.UserRole,path); item.setToolTip(path); listing.addItem(item)
        box.addWidget(listing)
        empty=label(t('No applications detected yet. Use the computer with activity tracking enabled, or choose an executable.'),'muted')
        empty.setWordWrap(True); empty.setVisible(not listing.count()); box.addWidget(empty)
        error=label('','danger'); error.setWordWrap(True); box.addWidget(error)
        actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(t('Cancel'),dialog.reject))
        def add_selected():
            values=asdict(self.focus.settings)
            values['block_apps'].extend(item.data(Qt.UserRole) for item in listing.selectedItems())
            try: self.focus.configure(FocusSettings(**values))
            except ValueError as exc: error.setText(t(str(exc))); return
            self.owner.update_focus_policy(); self.refresh(force=True); dialog.accept()
        add=button(t('Add selected'),add_selected,'primary'); add.setEnabled(False)
        listing.itemSelectionChanged.connect(lambda:add.setEnabled(bool(listing.selectedItems())))
        actions.addWidget(add); box.addLayout(actions); dialog.show()

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
                # Size from the actual styled rows; fixed pixel estimates clipped
                # the last row and introduced a scrollbar with only two entries.
                height=sum(listing.sizeHintForRow(i) for i in range(min(3,listing.count())))
                listing.setFixedHeight(max(1,height+2*listing.frameWidth()))
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

    def exclude_application(self, path):
        values=asdict(self.focus.settings)
        if path not in values['excluded_apps']: values['excluded_apps'].append(path)
        self.focus.configure(FocusSettings(**values))
        self.refresh(force=True)
        if self.owner.pages.currentIndex()==1: self.owner.statistics.refresh()

    def excluded_apps_dialog(self):
        t=self.owner.t
        dialog,box=self.dialog(t('Excluded applications'),720)
        note=label(t('Excluded applications are no longer measured and are hidden from application statistics. Past records are kept and return if restored. Excluding a browser also stops new website measurements in it. Game time is unaffected.'),'muted')
        note.setWordWrap(True); box.addWidget(note)
        listing=QListWidget(); listing.setMinimumHeight(150); box.addWidget(listing)
        def fill():
            listing.clear()
            for path in self.focus.settings.excluded_apps: listing.addItem(path)
        fill()
        actions=QHBoxLayout(); restore=button(t('Restore selected'),lambda: remove())
        restore.setEnabled(False); listing.itemSelectionChanged.connect(lambda: restore.setEnabled(listing.currentItem() is not None))
        actions.addWidget(restore); actions.addStretch(); actions.addWidget(button(t('Close'),dialog.accept,'primary')); box.addLayout(actions)
        def remove():
            item=listing.currentItem()
            if not item: return
            values=asdict(self.focus.settings); values['excluded_apps'].remove(item.text())
            self.focus.configure(FocusSettings(**values)); fill(); self.refresh(force=True)
            if self.owner.pages.currentIndex()==1: self.owner.statistics.refresh()
        dialog.show()

    def refresh(self, force=False):
        owner, focus, t = self.owner, self.focus, self.owner.t
        seconds = math.ceil(focus.remaining)
        paused=not focus.running and (focus.phase!='focus' or focus.remaining<focus.settings.work*60)
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
        for index,name in enumerate(('Websites','Applications')): self.rule_tabs.setTabText(index,t(name))

    def toggle(self):
        focus = self.focus
        if focus.running: focus.pause(self.owner.focus_awake())
        else: focus.start(self.owner.focus_awake())
        self.owner.update_focus_policy()
        self.refresh(force=True)

    def reset(self):
        self.focus.stop(); self.owner.update_focus_policy(); self.refresh(force=True)

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
