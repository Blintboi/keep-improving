"""Native Qt Gaming Hub. All controller and UI state belongs to this GUI thread."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import ctypes
import logging
import os
import time
import uuid
import winsound
from PySide6.QtCore import Qt,QTimer,QPoint,QEventLoop
from PySide6.QtGui import QIcon,QFont,QAction
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QVBoxLayout,QHBoxLayout,
    QGridLayout,QStackedWidget,QScrollArea,QLineEdit,QComboBox,QCheckBox,QDoubleSpinBox,QDialog,
    QFileDialog,QInputDialog,QMenu,QAbstractSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QSizePolicy,QSlider)
from .controller import MonitorActions
from .model import Catalog,Game,Settings,norm,blocked
from .service import DiscoveryService
from .tracker import Tracker
from .hub import HubWorker
from .i18n import tr,LANGUAGES
from . import win32,__version__
from .qt_widgets import STYLE,ACCENT,MUTED,label,button,panel,glyph,duration,BudgetRing,LocalArtwork,CardGrid,GameCard
from .qt_statistics import StatisticsPage
from .overlay import CountdownOverlay,PositionPicker,choose_screen,foreground_screen_name

log=logging.getLogger(__name__)

def dark_window(widget):
    hwnd=int(widget.winId())
    try:
        fn=ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        fn.argtypes=[win32.W.HWND,win32.W.DWORD,ctypes.c_void_p,win32.W.DWORD]
        for attribute,value in ((20,1),(35,0x191610),(36,0xf2f4ed)):
            data=ctypes.c_int(value); fn(hwnd,attribute,ctypes.byref(data),ctypes.sizeof(data))
    except OSError: pass
    return hwnd

def setup_application():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('Gaming Hub'); app.setOrganizationName('GameTimeMonitor')
    app.setQuitOnLastWindowClosed(False); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    app.setFont(QFont('Segoe UI',10)); app.setWindowIcon(QIcon(str(Path(__file__).with_name('app.ico'))))
    return app

class AlertDialog(QDialog):
    def __init__(self,owner):
        super().__init__(None,Qt.Dialog|Qt.WindowStaysOnTopHint|Qt.WindowCloseButtonHint)
        self.owner=owner; self.setObjectName('Surface'); self.setAttribute(Qt.WA_DeleteOnClose)
    def closeEvent(self,event):
        if self.owner.popup_window is self: self.owner.popup_window=self.owner.popup_day=None
        event.accept()

class App(QMainWindow,MonitorActions):
    def __init__(self,store,data_dir,background=False,service=None,hub=None):
        super().__init__()
        self.store,self.data_dir=store,Path(data_dir)
        self.settings=store.settings(); self.catalog=Catalog(self.settings,store.games(True),store.overrides(),store.rules())
        self.tracker=Tracker(store,self.catalog); self.hub=hub or HubWorker(data_dir); self.hub_fingerprint=None
        self.service=service or DiscoveryService(self.settings)
        self.catalog.steam_libraries=self.service.discovery.libraries_from_metadata()
        self.popup_window=self.popup_day=self.notification_timer=None; self.escape_attempts=set(); self.closed=False
        self.launcher=None; self.launching=None; self.last_rows=None
        self.tick_timer=self.tray_timer=None; self._timers=set(); self._dialogs=[]
        self.hidden_ids=store.hidden_ids(); self.selected_id=None; self.show_hidden=False; self.cards={}
        self.status_key='Discovering games…'; self.status_values={}; self.status_text=self.t(self.status_key)
        self.art=LocalArtwork(data_dir,self.service.discovery.roots); self.art.refresh_links(self.settings.games_root)
        self.setWindowTitle('Gaming Hub'); self.setWindowIcon(QIcon(str(Path(__file__).with_name('app.ico'))))
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1380,screen.width()-60),min(920,screen.height()-60)); self.setMinimumSize(1000,700)
        self.overlay_failed=False; self.overlay=None; self._overlay_preview_until=0
        self._build(); dark_window(self)
        try: self.overlay=CountdownOverlay(self)
        except Exception:
            self.overlay_failed=True; log.exception('Countdown initialization failed')
            self.set_status('Countdown unavailable; early warning popups remain active.')
        QApplication.instance().screenAdded.connect(self.refresh_overlay_screens)
        QApplication.instance().screenRemoved.connect(self.refresh_overlay_screens)
        self.tray=win32.Tray(self.show,self.tray_menu,self.devices_changed)
        self.refresh_manual_availability(); self.service.start(); self.render()
        if not background or not self.tray.available: self.show()
        self.overlay_timer=QTimer(self); self.overlay_timer.setInterval(200); self.overlay_timer.timeout.connect(self.update_overlay); self.overlay_timer.start()
        self.tick_timer=self.call_later(200,self.tick); self.tray_timer=self.call_later(75,self.poll_tray)

    def t(self,text,**values): return tr(text,self.settings.language,**values)
    def source_name(self,source): return self.t('Manual') if source=='Kézi' else self.t('Games folder') if source=='Games' else source
    def call_later(self,milliseconds,callback):
        timer=QTimer(self); timer.setSingleShot(True); self._timers.add(timer)
        def fire():
            self._timers.discard(timer); timer.deleteLater()
            if not self.closed: callback()
        timer.timeout.connect(fire); timer.start(milliseconds); return timer

    def _build(self,state=None):
        state=state or {}; self.cards={}; self.last_rows=None
        surface=QWidget(); surface.setObjectName('Surface'); row=QHBoxLayout(surface); row.setContentsMargins(0,0,0,0); row.setSpacing(0)
        rail=QFrame(); rail.setObjectName('Rail'); rail.setFixedWidth(196)
        side=QVBoxLayout(rail); side.setContentsMargins(16,26,16,18); side.setSpacing(9)
        brand=QHBoxLayout(); brand.setSpacing(10); logo=QLabel(); logo.setPixmap(self.windowIcon().pixmap(34,34)); brand.addWidget(logo)
        brand_text=QVBoxLayout(); brand_text.setSpacing(3); name=label('Gaming Hub'); name.setFont(QFont('Segoe UI',13,QFont.Bold)); brand_text.addWidget(name)
        small=label(self.t('Game Time Monitor'),'muted'); small.setStyleSheet('font-size:10px;'); brand_text.addWidget(small); brand.addLayout(brand_text); side.addLayout(brand)
        side.addSpacing(32); side.addWidget(label(self.t('YOUR SPACE'),'eyebrow')); side.addSpacing(4)
        self.nav=[]
        for index,text,icon in ((0,'Library','library'),(1,'Statistics','stats'),(2,'Settings','settings')):
            item=button(self.t(text),lambda checked=False,n=index:self.switch_page(n),'nav'); item.setCheckable(True); item.setIcon(glyph(icon)); item.setMinimumHeight(45)
            self.nav.append(item); side.addWidget(item)
        side.addStretch()
        monitoring=panel(); monitoring.setStyleSheet('QFrame#Panel {background:#13211d; border:1px solid #284339; border-radius:13px;}')
        monitor_layout=QVBoxLayout(monitoring); monitor_layout.setContentsMargins(13,13,13,13); monitor_layout.setSpacing(7)
        active=label('●  '+self.t('Monitoring active')); active.setStyleSheet('color:#9ce7c5; font-size:11px; font-weight:600;'); monitor_layout.addWidget(active)
        note=label(self.t('Play time is counted automatically.'),'muted'); note.setWordWrap(True); note.setStyleSheet('font-size:11px;'); monitor_layout.addWidget(note); side.addWidget(monitoring)
        test=button(self.t('Test alert'),self.test_popup,'quiet'); test.setIcon(glyph('bell',MUTED,18)); side.addWidget(test)
        hide=button(self.t('Hide to tray'),self.hide,'quiet'); hide.setIcon(glyph('hide',MUTED,18)); side.addWidget(hide)
        side.addSpacing(12); side.addWidget(label(self.t('Language / Nyelv'),'eyebrow'))
        self.language=QComboBox()
        for name,code in LANGUAGES.items(): self.language.addItem(name,code)
        self.language.setCurrentIndex(self.language.findData(self.settings.language)); self.language.currentIndexChanged.connect(lambda index:self.set_language(self.language.itemData(index)))
        side.addWidget(self.language); version=label('v'+__version__,'muted'); version.setStyleSheet('font-size:10px; padding-top:8px;'); side.addWidget(version)
        row.addWidget(rail)
        right=QVBoxLayout(); right.setContentsMargins(0,0,0,0); right.setSpacing(0)
        self.restriction_banner=QFrame(); self.restriction_banner.setStyleSheet('QFrame {background:#45232b; border:0;}')
        banner_layout=QHBoxLayout(self.restriction_banner); banner_layout.setContentsMargins(30,12,24,12)
        self.restriction_label=label(); self.restriction_label.setWordWrap(True); self.restriction_label.setStyleSheet('color:#ffc5cc;')
        banner_layout.addWidget(self.restriction_label,1); banner_layout.addWidget(button(self.t('Settings'),self.settings_dialog))
        right.addWidget(self.restriction_banner); self.restriction_banner.hide()
        self.pages=QStackedWidget(); right.addWidget(self.pages,1)
        self.hub_page=self._build_library(state); self.pages.addWidget(self.hub_page)
        self.statistics=StatisticsPage(self); self.pages.addWidget(self.statistics)
        self.settings_page=self._build_settings(); self.pages.addWidget(self.settings_page)
        self.status_label=label(self.status_text,'muted'); self.status_label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        self.status_label.setStyleSheet('font-size:11px; padding:8px 32px 12px; color:#7d9395;'); right.addWidget(self.status_label)
        row.addLayout(right,1)
        previous=self.takeCentralWidget(); self.setCentralWidget(surface)
        if previous: previous.deleteLater()
        self.show_hidden=state.get('show_hidden',self.show_hidden); self.hidden_toggle.setChecked(self.show_hidden)
        self.search.setText(state.get('query','')); self.sort.setCurrentIndex(self.sort.findData(state.get('sort','name')))
        self.statistics.start.setText(state.get('start',self.statistics.start.text())); self.statistics.end.setText(state.get('end',self.statistics.end.text()))
        self.statistics.selected_day=state.get('day')
        self.pages.setCurrentIndex(state.get('page',0))
        for i,item in enumerate(self.nav): item.setChecked(i==self.pages.currentIndex())

    def _build_library(self,state):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(32,25,24,17); layout.setSpacing(17)
        top=QHBoxLayout(); titles=QVBoxLayout(); titles.setSpacing(6)
        titles.addWidget(label(self.t('Your library'),'title')); titles.addWidget(label(self.t('Pick a game. Make time for a good session.'),'muted')); top.addLayout(titles); top.addStretch()
        add=button(self.t('Add game'),self.add_manual); add.setIcon(glyph('plus','#cee1db',17)); top.addWidget(add); layout.addLayout(top)
        budget=panel('Budget'); budget_row=QHBoxLayout(budget); budget_row.setContentsMargins(20,14,22,14); budget_row.setSpacing(20)
        self.ring=BudgetRing(); budget_row.addWidget(self.ring)
        self.total_label=label('00:00:00','metric'); self.remaining_label=label('00:00:00','metric'); self.limit_label=label('120 min','section')
        for title,value in [('Today’s game time',self.total_label),('Time remaining',self.remaining_label),('Daily budget',self.limit_label)]:
            box=QVBoxLayout(); box.setSpacing(4); box.addWidget(label(self.t(title),'muted')); box.addWidget(value); budget_row.addLayout(box,1)
        self.active_label=label(self.t('Active game: none'),'muted'); self.active_label.setWordWrap(True); self.active_label.setMaximumWidth(220)
        budget_row.addWidget(self.active_label,1); layout.addWidget(budget)
        toolbar=QHBoxLayout(); toolbar.setSpacing(10)
        self.search=QLineEdit(); self.search.setPlaceholderText(self.t('Search your games…')); self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph('search',MUTED,18),QLineEdit.LeadingPosition); toolbar.addWidget(self.search,1)
        self.source_filter=QComboBox(); self.source_filter.setMinimumWidth(170); self.source_filter.addItem(self.t('All sources'),None); toolbar.addWidget(self.source_filter)
        self.hidden_toggle=QCheckBox(self.t('Show hidden games')); self.hidden_toggle.setToolTip(self.t('Show hidden games (hiding does not stop tracking)')); toolbar.addWidget(self.hidden_toggle)
        layout.addLayout(toolbar)
        collection=QHBoxLayout(); self.collection_count=label('','section'); collection.addWidget(self.collection_count); collection.addStretch()
        self.sort=QComboBox(); self.sort.addItem(self.t('Name: A–Z'),'name'); self.sort.addItem(self.t('Most played today'),'today'); self.sort.setFixedWidth(186); collection.addWidget(self.sort); layout.addLayout(collection)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.grid=CardGrid(); self.scroll.setWidget(self.grid); layout.addWidget(self.scroll,1)
        self.empty=label(self.t('No games match this view.'),'muted'); self.empty.setAlignment(Qt.AlignCenter); self.empty.hide(); layout.addWidget(self.empty)
        selected=panel('Selected'); bottom=QHBoxLayout(selected); bottom.setContentsMargins(18,13,15,13); bottom.setSpacing(14)
        self.selection_icon=QLabel(); self.selection_icon.setFixedSize(44,44); self.selection_icon.setPixmap(self.windowIcon().pixmap(40,40)); bottom.addWidget(self.selection_icon)
        name_box=QVBoxLayout(); name_box.setSpacing(5)
        self.selection_title=label(self.t('Choose a game'),'section'); self.selection_title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred)
        self.selection_note=label(self.t('Select a card to play or manage it.'),'muted'); name_box.addWidget(self.selection_title); name_box.addWidget(self.selection_note); bottom.addLayout(name_box,1)
        self.more=button('',self.game_menu); self.more.setIcon(glyph('dots','#cee1db')); self.more.setFixedSize(40,40); self.more.setToolTip(self.t('Game options')); bottom.addWidget(self.more)
        self.launch_button=button(self.t('▶ Play'),self.launch_selected,'primary'); self.launch_button.setMinimumWidth(156); bottom.addWidget(self.launch_button); layout.addWidget(selected)
        self.search.textChanged.connect(self.refresh_view); self.source_filter.currentIndexChanged.connect(self.refresh_view)
        self.hidden_toggle.toggled.connect(self.refresh_view); self.sort.currentIndexChanged.connect(self.refresh_view)
        self._restore_source=state.get('source')
        return page

    def _build_settings(self):
        page=QWidget(); outer=QVBoxLayout(page); outer.setContentsMargins(32,25,32,22); outer.setSpacing(16)
        outer.addWidget(label(self.t('Settings'),'title')); outer.addWidget(label(self.t('Set a comfortable pace for your play time.'),'muted'))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll,1)
        body=QWidget(); body_layout=QVBoxLayout(body); body_layout.setContentsMargins(0,0,8,0); body_layout.setSpacing(18); scroll.setWidget(body)
        limits=panel(); limits_layout=QVBoxLayout(limits); limits_layout.setContentsMargins(22,20,22,22); limits_layout.setSpacing(14)
        limits_layout.addWidget(label(self.t('Daily routine'),'section')); fields=QHBoxLayout(); fields.setSpacing(24)
        self.limit=QDoubleSpinBox(); self.warning=QDoubleSpinBox()
        for text,widget,value in [('Daily limit (minutes)',self.limit,self.settings.limit_seconds/60),('Warn after (minutes)',self.warning,self.settings.warning_seconds/60)]:
            widget.setButtonSymbols(QAbstractSpinBox.NoButtons); widget.setRange(.01,1440); widget.setDecimals(2); widget.setSingleStep(5); widget.setValue(value)
            group=QVBoxLayout(); group.addWidget(label(self.t(text),'muted')); group.addWidget(widget); fields.addLayout(group,1)
        limits_layout.addLayout(fields)
        self.chess=QCheckBox(self.t('Exclude chess games by default (optional personal preference)')); self.chess.setChecked(self.settings.exclude_chess); limits_layout.addWidget(self.chess)
        limits_layout.addWidget(label(self.t('Reminders let you decide when to finish. Games are never closed for you.'),'muted')); body_layout.addWidget(limits)
        body_layout.addWidget(self.build_restriction_settings())
        body_layout.addWidget(self.build_overlay_settings())
        locations=panel(); places=QVBoxLayout(locations); places.setContentsMargins(22,20,22,22); places.setSpacing(12)
        places.addWidget(label(self.t('Games and discovery'),'section')); places.addWidget(label(self.t('Games and optional shortcuts folder (full path)'),'muted'))
        browse=QHBoxLayout(); self.games_path=QLineEdit(self.settings.games_root); browse.addWidget(self.games_path,1); browse.addWidget(button(self.t('Browse…'),self.browse_root)); places.addLayout(browse)
        self.hub_enabled=QCheckBox(self.t('Also maintain a shortcuts folder (optional)')); self.hub_enabled.setChecked(self.settings.hub_enabled); places.addWidget(self.hub_enabled)
        self.paths={}
        for key,text,values in [('steam','Additional Steam installations (separated by semicolons)',self.settings.steam_roots),('epic','Additional Epic manifest folders (separated by semicolons)',self.settings.epic_manifest_dirs),('ubisoft','Additional Ubisoft Connect installations (separated by semicolons)',self.settings.ubisoft_roots)]:
            places.addWidget(label(self.t(text),'muted')); edit=QLineEdit(';'.join(values)); places.addWidget(edit); self.paths[key]=edit
        body_layout.addWidget(locations); body_layout.addStretch()
        footer=QHBoxLayout(); self.settings_error=label('','danger'); self.settings_error.setWordWrap(True); footer.addWidget(self.settings_error,1)
        footer.addWidget(button(self.t('Save settings'),self.save_settings,'primary')); outer.addLayout(footer)
        return page

    def build_restriction_settings(self):
        card=panel(); layout=QVBoxLayout(card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(self.t('Play restriction'),'section'))
        self.restriction_enabled=QCheckBox(self.t('Prevent further tracked gameplay after a daily threshold'))
        self.restriction_enabled.setChecked(self.settings.restriction_enabled); layout.addWidget(self.restriction_enabled)
        row=QHBoxLayout(); row.addWidget(label(self.t('Restrict after (total daily minutes)'),'muted'),1)
        self.restriction_minutes=QDoubleSpinBox(); self.restriction_minutes.setRange(.01,1440); self.restriction_minutes.setDecimals(2)
        self.restriction_minutes.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.restriction_minutes.setSingleStep(5); self.restriction_minutes.setValue(self.settings.restriction_seconds/60)
        self.restriction_minutes.setEnabled(self.restriction_enabled.isChecked()); self.restriction_enabled.toggled.connect(self.restriction_minutes.setEnabled)
        row.addWidget(self.restriction_minutes); layout.addLayout(row)
        note=label(self.t('At the threshold, tracked games receive one guarded Escape and are minimized when they return to the foreground. The Hub also blocks launching them until the next day. Games are not closed; online games may continue in the background. You can disable this here.'),'muted')
        note.setWordWrap(True); layout.addWidget(note); return card

    def build_overlay_settings(self):
        card=panel(); layout=QVBoxLayout(card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(self.t('In-game countdown'),'section'))
        self.overlay_enabled=QCheckBox(self.t('Show a click-through countdown while gaming')); self.overlay_enabled.setChecked(self.settings.overlay_enabled); layout.addWidget(self.overlay_enabled)
        self.overlay_warning=QCheckBox(self.t('Use a red countdown instead of the early warning popup')); self.overlay_warning.setChecked(self.settings.overlay_replace_warning); layout.addWidget(self.overlay_warning)
        self.limit_popup=QCheckBox(self.t('Show a popup when the daily time limit expires')); self.limit_popup.setChecked(self.settings.limit_popup_enabled); layout.addWidget(self.limit_popup)
        self.overlay_controls=QWidget(); controls=QVBoxLayout(self.overlay_controls); controls.setContentsMargins(0,4,0,0); controls.setSpacing(10)
        fields=QHBoxLayout(); fields.addWidget(label(self.t('Monitor'),'muted')); self.overlay_screen=QComboBox(); fields.addWidget(self.overlay_screen,1); controls.addLayout(fields)
        self.overlay_picker=PositionPicker(self.settings.overlay_x,self.settings.overlay_y,QApplication.primaryScreen())
        self.overlay_picker.setAccessibleName(self.t('Countdown position'))
        self.overlay_screen.currentIndexChanged.connect(self.overlay_screen_changed)
        self.refresh_overlay_screens()
        self.overlay_screen.setCurrentIndex(max(0,self.overlay_screen.findData(self.settings.overlay_screen)))
        controls.addWidget(label(self.t('Drag the timer below to set its position. Arrow keys also work.'),'muted')); controls.addWidget(self.overlay_picker)
        self.overlay_picker.positionChanged.connect(lambda x,y:self.update_overlay())
        opacity=QHBoxLayout(); opacity.addWidget(label(self.t('Background opacity'),'muted'))
        self.overlay_opacity=QSlider(Qt.Horizontal); self.overlay_opacity.setRange(25,95); self.overlay_opacity.setValue(round(self.settings.overlay_opacity*100)); opacity.addWidget(self.overlay_opacity,1)
        self.overlay_opacity_label=label(str(self.overlay_opacity.value())+'%'); self.overlay_opacity.valueChanged.connect(lambda value:self.overlay_opacity_label.setText(str(value)+'%')); self.overlay_opacity.valueChanged.connect(lambda value:self.update_overlay()); opacity.addWidget(self.overlay_opacity_label); controls.addLayout(opacity)
        actions=QHBoxLayout(); actions.addWidget(button(self.t('Preview for 10 seconds'),self.preview_overlay)); actions.addWidget(button(self.t('Reset position'),lambda:self.overlay_picker.set_position(1,0))); actions.addStretch(); controls.addLayout(actions)
        note=label(self.t('The countdown never takes focus or mouse input. Exclusive fullscreen may hide desktop overlays; windowed or borderless mode is more reliable.'),'muted'); note.setWordWrap(True); controls.addWidget(note)
        layout.addWidget(self.overlay_controls)
        self.overlay_enabled.toggled.connect(self.overlay_controls.setEnabled); self.overlay_enabled.toggled.connect(self.overlay_warning.setEnabled)
        self.overlay_controls.setEnabled(self.overlay_enabled.isChecked()); self.overlay_warning.setEnabled(self.overlay_enabled.isChecked())
        return card

    def refresh_overlay_screens(self,*args):
        if not hasattr(self,'overlay_screen'): return
        wanted=self.overlay_screen.currentData()
        if wanted is None: wanted=self.settings.overlay_screen
        self.overlay_screen.blockSignals(True); self.overlay_screen.clear(); self.overlay_screen.addItem(self.t('Automatic (active game monitor)'),'')
        for screen in QApplication.screens():
            rect=screen.geometry(); self.overlay_screen.addItem(f'{screen.name()} · {rect.width()} × {rect.height()}',screen.name())
        if wanted and self.overlay_screen.findData(wanted)<0: self.overlay_screen.addItem(self.t('{name} (not connected)',name=wanted),wanted)
        self.overlay_screen.setCurrentIndex(max(0,self.overlay_screen.findData(wanted))); self.overlay_screen.blockSignals(False); self.overlay_screen_changed()

    def overlay_screen_changed(self,*args):
        if hasattr(self,'overlay_picker'):
            self.overlay_picker.screen=choose_screen(self.overlay_screen.currentData() or '',self.screen().name() if self.screen() else '')
            self.overlay_picker.update()

    def overlay_values(self):
        return dict(overlay_enabled=self.overlay_enabled.isChecked(),overlay_replace_warning=self.overlay_warning.isChecked(),limit_popup_enabled=self.limit_popup.isChecked(),
                    overlay_opacity=self.overlay_opacity.value()/100,overlay_x=self.overlay_picker.x_ratio,overlay_y=self.overlay_picker.y_ratio,overlay_screen=self.overlay_screen.currentData() or '')

    def preview_overlay(self):
        self._overlay_preview_until=time.monotonic()+10; self.update_overlay()

    def update_overlay(self):
        if self.closed or not self.overlay: return
        preview=time.monotonic()<self._overlay_preview_until
        settings=replace(self.settings,**self.overlay_values()) if preview else self.settings
        if not settings.overlay_enabled:
            self.overlay.hide(); return
        try:
            current=win32.sample()
            if not current.interactive:
                self.overlay.hide(); return
            if preview:
                total=settings.warning_seconds; remaining=settings.limit_seconds-total
                automatic=self.screen().name() if self.screen() else ''
            else:
                active=self.tracker.active
                game=self.catalog.resolve(current.path)
                if not active or not game or game.id!=active.id or current.identity!=self.tracker.identity:
                    self.overlay.hide(); return
                total=sum(self.tracker.totals(current.wall.date()).values())
                previous=self.tracker.previous
                if previous and previous.identity==current.identity:
                    elapsed=current.awake-previous.awake
                    if 0<elapsed<=1.5 and abs((current.wall-previous.wall).total_seconds()-elapsed)<1.5 and previous.wall.date()==current.wall.date(): total+=elapsed
                remaining=settings.limit_seconds-total; automatic=foreground_screen_name()
            self.overlay.present(remaining,total,settings,choose_screen(settings.overlay_screen,automatic),preview)
            self.overlay_failed=False
        except Exception:
            if not self.overlay_failed: log.exception('Countdown presentation failed')
            self.overlay_failed=True; self.overlay.hide(); self.set_status('Countdown unavailable; early warning popups remain active.')

    def browse_root(self):
        value=QFileDialog.getExistingDirectory(self,self.t('Gaming Hub'),self.games_path.text())
        if value: self.games_path.setText(value)

    def save_settings(self):
        try:
            settings=replace(self.settings,games_root=self.games_path.text().strip(),warning_seconds=self.warning.value()*60,limit_seconds=self.limit.value()*60,
                steam_roots=[p.strip() for p in self.paths['steam'].text().split(';') if p.strip()],
                epic_manifest_dirs=[p.strip() for p in self.paths['epic'].text().split(';') if p.strip()],
                ubisoft_roots=[p.strip() for p in self.paths['ubisoft'].text().split(';') if p.strip()],
                hub_enabled=self.hub_enabled.isChecked(),exclude_chess=self.chess.isChecked(),
                restriction_enabled=self.restriction_enabled.isChecked(),restriction_seconds=self.restriction_minutes.value()*60,**self.overlay_values()).validate()
            self.tracker.flush(); self.store.save_settings(settings); self.settings=self.catalog.settings=settings
            self.tracker.unclassified.clear(); self.tracker.previous=None; self.service.configure(settings)
            self.art.roots=list(dict.fromkeys(self.art.roots+settings.steam_roots)); self.art.cache.clear(); self.art.refresh_links(settings.games_root)
            self.settings_error.setText(''); self.last_rows=None; self.set_status('Settings saved.'); self._overlay_preview_until=0; self.update_overlay(); self.render()
        except (ValueError,OSError) as exc: self.settings_error.setText(self.t(str(exc)))

    def set_status(self,text,**values):
        self.status_key=text; self.status_values=values; self.status_text=self.t(text,**values)
        if hasattr(self,'status_label'): self.status_label.setText(self.status_text); self.status_label.setToolTip(self.status_text)

    def set_language(self,language):
        if not language or language==self.settings.language: return
        state={'query':self.search.text(),'source':self.source_filter.currentData(),'sort':self.sort.currentData(),'page':self.pages.currentIndex(),
               'show_hidden':self.hidden_toggle.isChecked(),'start':self.statistics.start.text(),'end':self.statistics.end.text(),'day':self.statistics.selected_day}
        self.tracker.flush(); self.settings=replace(self.settings,language=language).validate(); self.catalog.settings=self.settings; self.store.save_settings(self.settings)
        self.status_text=self.t(self.status_key,**self.status_values); self._build(state); self.render()
        if self.pages.currentIndex()==1: self.statistics.refresh()

    def switch_page(self,index):
        self.pages.setCurrentIndex(index)
        for n,item in enumerate(self.nav): item.setChecked(n==index)
        if index==1: self.statistics.refresh()
    def settings_dialog(self): self.switch_page(2); self.show()
    def show(self):
        if self.closed: return
        self.showNormal(); hwnd=dark_window(self)
        # Windows STARTUPINFO may hide the first Qt show. Explicitly restore the
        # native window as well, including launches through hidden startup links.
        win32.u.ShowWindow(hwnd,9)
        self.raise_(); self.activateWindow(); win32.u.SetForegroundWindow(hwnd)
    def open_games(self): self.switch_page(0); self.show()
    def closeEvent(self,event):
        if self.closed: event.accept()
        else: event.ignore(); self.hide()
    def selected(self): return self.catalog.games.get(self.selected_id) or next((g for g in self.store.games() if g.id==self.selected_id),None)
    def refresh_view(self,*args):
        if not hasattr(self,'pages') or not hasattr(self,'statistics'): return
        self.show_hidden=self.hidden_toggle.isChecked(); self.last_rows=None; self.render()
    def select_game(self,gid): self.selected_id=gid; self.update_launch_button()
    def play_game(self,gid): self.select_game(gid); self.launch_selected()

    def update_launch_button(self):
        if not hasattr(self,'launch_button'): return
        game=self.selected(); restricted=bool(game and self.launch_restricted(game)); available=bool(game and game.installed and not self.launching and not restricted)
        self.launch_button.setEnabled(available); self.more.setEnabled(bool(game)); self.launch_button.setText(self.t('Restricted today' if restricted else 'Starting…' if self.launching else '▶ Play'))
        if game:
            self.selection_title.setText(game.name); self.selection_title.setToolTip(game.name)
            self.selection_note.setText(self.source_name(game.source)+'  ·  '+self.t('Tracked' if self.catalog.enabled(game) else 'Excluded'))
            art=self.art.cache.get((game.id,game.root,game.metadata,self.art.links.get(game.id)))
            self.selection_icon.setPixmap(art[1].scaled(40,40,Qt.KeepAspectRatio,Qt.SmoothTransformation) if art and art[1] else self.windowIcon().pixmap(40,40))
        else:
            self.selection_title.setText(self.t('Choose a game')); self.selection_note.setText(self.t('Select a card to play or manage it.'))
        for gid,card in self.cards.items(): card.set_state(card.seconds,gid==self.selected_id,not self.launching and not self.launch_restricted(card.game))

    def game_menu(self):
        game=self.selected()
        if not game: return
        menu=QMenu(self)
        for text,callback in [('Open game folder',self.open_game_folder),('Assign EXE',self.assign_exe),('EXE rules',self.rules_dialog),
                              ('Exclude / track',self.toggle_game),('Hide / restore',self.toggle_hidden)]: menu.addAction(self.t(text),callback)
        menu.addSeparator(); menu.addAction(self.t('Uninstall game…'),self.uninstall_game)
        menu.exec(self.more.mapToGlobal(QPoint(0,self.more.height())))

    def _dialog(self,title,width=620):
        window=QDialog(self); window.setObjectName('Surface'); window.setWindowTitle(title); window.setAttribute(Qt.WA_DeleteOnClose); window.resize(width,300)
        self._dialogs.append(window)
        window.finished.connect(lambda result:self._dialogs.remove(window) if window in self._dialogs else None)
        return window

    def message(self,text):
        window=self._dialog('Gaming Hub',570); layout=QVBoxLayout(window); layout.setContentsMargins(28,26,28,25); layout.setSpacing(20)
        layout.addWidget(label('Gaming Hub','section')); message=label(self.t(text)); message.setWordWrap(True); layout.addWidget(message,1)
        layout.addWidget(button(self.t('OK'),window.accept,'primary'),0,Qt.AlignRight); window.show(); dark_window(window)

    def add_manual(self):
        path,_=QFileDialog.getOpenFileName(self,self.t('Choose application'),' ',self.t('Windows application')+' (*.exe)')
        if not path: return
        if blocked(path): self.message('Browsers and launcher clients cannot be assigned to a game.'); return
        name,accepted=QInputDialog.getText(self,self.t('Add game'),self.t('Game name:'),text=Path(path).stem)
        if accepted and name.strip():
            game=Game('manual:'+uuid.uuid4().hex,name.strip(),'Kézi',str(Path(path).parent)); self.store.upsert([game]); self.catalog.games[game.id]=game
            self.store.set_rule(path,game.id); self.store.set_launch_executable(game.id,path); self.refresh_rules(); self.selected_id=game.id; self.refresh_view()

    def assign_exe(self):
        game=self.selected()
        if not game: self.message('Select a game in the list first.'); return
        path,_=QFileDialog.getOpenFileName(self,self.t('Choose application'),game.root,self.t('Windows application')+' (*.exe)')
        if path:
            if blocked(path): self.message('Browsers and launcher clients do not count as game time.'); return
            self.store.set_rule(path,game.id); self.store.set_launch_executable(game.id,path); self.refresh_rules(); self.art.cache.clear(); self.refresh_view()

    def rules_dialog(self):
        window=self._dialog(self.t('Executable exclusions and assignments'),920); window.resize(920,480)
        box=QVBoxLayout(window); box.setContentsMargins(24,24,24,24); box.setSpacing(16)
        note=label(self.t('Use Exclude / track in the main list to change tracking for an entire game.'),'muted'); note.setWordWrap(True); box.addWidget(note)
        table=QTableWidget(0,2); table.setHorizontalHeaderLabels([self.t('Application path'),self.t('Tracking')]); table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        table.setColumnWidth(1,210); table.verticalHeader().hide(); table.setSelectionBehavior(QAbstractItemView.SelectRows); table.setEditTriggers(QAbstractItemView.NoEditTriggers); box.addWidget(table,1)
        def fill():
            rows=list(self.store.rules().items()); table.setRowCount(len(rows))
            for i,(path,gid) in enumerate(rows):
                table.setItem(i,0,QTableWidgetItem(path)); game=self.catalog.games.get(gid)
                table.setItem(i,1,QTableWidgetItem(game.name if game else gid or self.t('Excluded')))
        def remove():
            row=table.currentRow()
            if row>=0: self.store.delete_rule(table.item(row,0).text()); self.refresh_rules(); fill()
        def exclude():
            path,_=QFileDialog.getOpenFileName(window,self.t('Exclude application'),' ',self.t('Windows application')+' (*.exe)')
            if path: self.store.set_rule(path,None); self.refresh_rules(); fill()
        actions=QHBoxLayout(); actions.addWidget(button(self.t('Exclude EXE'),exclude)); actions.addWidget(button(self.t('Remove selected rule'),remove)); actions.addStretch(); actions.addWidget(button(self.t('Close'),window.close)); box.addLayout(actions)
        fill(); window.show(); dark_window(window)

    def uninstall_game(self):
        game=self.selected()
        if not game: self.message('Select a game in the list first.'); return
        from .removal import plan_removal,localize_plan,execute,apps_plan
        plan=localize_plan(plan_removal(game),game,self.settings.language)
        window=self._dialog(self.t('Uninstall game — {name}',name=game.name),690); window.resize(690,450)
        layout=QVBoxLayout(window); layout.setContentsMargins(28,26,28,25); layout.setSpacing(18)
        heading=label(plan.title,'title'); heading.setWordWrap(True); layout.addWidget(heading)
        instructions=label(plan.instructions); instructions.setWordWrap(True); layout.addWidget(instructions)
        note=label(self.t('Your play history will be kept. Hiding a game does not uninstall it.'),'muted'); note.setWordWrap(True); layout.addWidget(note)
        status=label(); status.setWordWrap(True); layout.addWidget(status,1); buttons=QHBoxLayout()
        def proceed():
            try:
                execute(plan); launch.setEnabled(False); status.setText(self.t("Opened. Complete the steps above in the publisher's window. You can then close this guide.")); self.devices_changed()
            except (OSError,ValueError) as exc: status.setText(self.t('Could not open the removal tool. Use Installed apps below. ')+str(exc))
        def installed():
            try: execute(apps_plan(game))
            except OSError as exc: status.setText(self.t('Open Windows Settings → Apps → Installed apps manually. ')+str(exc))
        launch=button(self.t('Continue…'),proceed,'primary'); buttons.addWidget(launch); buttons.addWidget(button(self.t('Installed apps'),installed)); buttons.addStretch(); buttons.addWidget(button(self.t('Close'),window.close)); layout.addLayout(buttons)
        window.show(); dark_window(window)

    def popup(self,alert):
        if self.popup_window: return False
        window=AlertDialog(self); self.popup_window=window; self.popup_day=alert.day
        window.setWindowTitle(self.t('Game time alert')); window.setFixedSize(590,300)
        layout=QVBoxLayout(window); layout.setContentsMargins(30,26,30,25); layout.setSpacing(17)
        eyebrow=label('●  '+self.t('Game time alert'),'eyebrow'); eyebrow.setStyleSheet('color:#a5eacf;'); layout.addWidget(eyebrow)
        title=label(self.t('Time to stop playing' if alert.kind in ('limit','session') else 'Game time reminder'),'title'); title.setWordWrap(True); layout.addWidget(title)
        text=label(alert.text); text.setWordWrap(True); layout.addWidget(text,1)
        acknowledge=button(self.t(alert.button),window.accept,'primary'); acknowledge.setDefault(True); layout.addWidget(acknowledge,0,Qt.AlignRight)
        window.finished.connect(lambda result:self._popup_finished(window))
        screen=QApplication.primaryScreen().availableGeometry(); window.move(screen.center()-window.rect().center())
        try:
            window.show(); window.raise_(); hwnd=dark_window(window); foreground=win32.present_notification(hwnd)
            window.activateWindow(); QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            if not window.isVisible() or not win32.u.IsWindowVisible(hwnd): raise RuntimeError('Notification window did not become visible')
        except Exception:
            log.exception('Qt notification presentation failed; will retry'); self.dismiss_popup(); return False
        log.info('Notification presented: kind=%s day=%s main_visible=%s foreground=%s',alert.kind,alert.day,self.isVisible(),foreground)
        try: winsound.PlaySound('SystemExclamation',winsound.SND_ALIAS|winsound.SND_ASYNC)
        except RuntimeError: log.warning('Notification sound unavailable; window remains visible')
        return True

    def _popup_finished(self,window):
        if self.popup_window is window: self.popup_window=self.popup_day=None
    def dismiss_popup(self):
        if self.popup_window: self.popup_window.close(); self.popup_window=self.popup_day=None

    def render(self):
        self.sync_hub()
        day=datetime.now().date().isoformat(); totals=self.tracker.totals(day); total=sum(totals.values())
        self.total_label.setText(duration(total)); self.remaining_label.setText(duration(self.settings.limit_seconds-total)); self.limit_label.setText(f'{self.settings.limit_seconds/60:g} '+self.t('min'))
        self.ring.set_ratio(total/self.settings.limit_seconds); self.active_label.setText(self.t('Active game: {name}',name=self.tracker.active.name if self.tracker.active else self.t('none')))
        games={g.id:g for g in self.store.games()}; games.update(self.catalog.games); self.hidden_ids=self.store.hidden_ids()
        source=self.source_filter.currentData()
        if self._restore_source is not None: source=self._restore_source; self._restore_source=None
        sources=sorted({g.source for g in games.values()}); self.source_filter.blockSignals(True); self.source_filter.clear(); self.source_filter.addItem(self.t('All sources'),None)
        for value in sources: self.source_filter.addItem(self.source_name(value),value)
        self.source_filter.setCurrentIndex(max(0,self.source_filter.findData(source))); self.source_filter.blockSignals(False); source=self.source_filter.currentData()
        query=self.search.text().strip().casefold()
        filtered=[g for g in games.values() if (self.hidden_toggle.isChecked() or g.id not in self.hidden_ids) and (g.installed or g.id in totals)
                  and (not source or g.source==source) and (not query or query in (g.name+' '+g.source+' '+self.source_name(g.source)).casefold())]
        filtered.sort(key=lambda g:(-totals.get(g.id,0) if self.sort.currentData()=='today' else 0,g.name.casefold(),g.id))
        fingerprint=tuple((g.id,g.name,g.source,g.root,g.metadata,g.installed) for g in filtered)
        if self.last_rows!=fingerprint:
            self.art.refresh_links(self.settings.games_root); self.cards={g.id:GameCard(g,self.t) for g in filtered}
            for card in self.cards.values(): card.selected.connect(self.select_game); card.launched.connect(self.play_game)
            self.grid.set_cards(list(self.cards.values())); self.last_rows=fingerprint
            self.collection_count.setText(self.t('{count} games',count=len(filtered))); self.empty.setVisible(not filtered)
            if self.selected_id not in self.cards: self.selected_id=None
            self._art_queue=list(self.cards)
            self.call_later(10,self.load_next_art)
        self.restriction_banner.setVisible(self.restriction_reached())
        self.restriction_label.setText(self.t('Today’s {minutes:g}-minute play restriction is active. Tracked games are minimized; Settings remains available.',minutes=self.settings.restriction_seconds/60))
        for gid,card in self.cards.items(): card.set_state(totals.get(gid,0),gid==self.selected_id,not self.launching and not self.launch_restricted(card.game))
        self.update_launch_button()
        self.tray.update(self.t('Game Time Monitor\nToday: {total} · remaining: {remaining}\nLeft click: open · right click: menu',total=duration(total),remaining=duration(self.settings.limit_seconds-total)))
        if self.pages.currentIndex()==1 and time.monotonic()-self.statistics.last_refresh>=10: self.statistics.refresh()

    def load_next_art(self):
        if self.closed or not self._art_queue: return
        gid=self._art_queue.pop(0); card=self.cards.get(gid)
        if card:
            try: card.art=self.art.artwork(card.game,self.catalog.rules)
            except (OSError,ValueError,TypeError,AttributeError):
                log.warning('Local game artwork unavailable: %s',gid,exc_info=True)
            card.update()
        if self._art_queue: self.call_later(15,self.load_next_art)
        else: self.update_launch_button()

    def close(self):
        if self.closed: return
        self.closed=True
        for timer in list(self._timers): timer.stop(); timer.deleteLater()
        self._timers.clear(); self.dismiss_popup()
        self.overlay_timer.stop()
        if self.overlay: self.overlay.close(); self.overlay.deleteLater()
        for signal in (QApplication.instance().screenAdded,QApplication.instance().screenRemoved):
            try: signal.disconnect(self.refresh_overlay_screens)
            except (RuntimeError,TypeError): pass
        for window in list(self._dialogs): window.close()
        self.tracker.close(); self.service.close(); self.hub.close()
        if self.launcher: self.launcher.close()
        self.tray.close(); QMainWindow.close(self)

def run(store,data_dir,background=False):
    qapp=setup_application(); window=App(store,data_dir,background)
    # Closing the window hides it; only the controller's Exit/stop request ends exec.
    timer=QTimer(); timer.setInterval(100); timer.timeout.connect(lambda:qapp.quit() if window.closed else None); timer.start()
    try: return qapp.exec()
    finally: timer.stop(); window.close()
