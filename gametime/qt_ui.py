"""Native Qt Gaming Hub. All controller and UI state belongs to this GUI thread."""
from dataclasses import replace
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
import ctypes
import logging
import os
import time
import uuid
import winsound
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt,QTimer,QPoint,QEventLoop,QObject,QEvent,Signal,QTime,QSize
from PySide6.QtGui import QIcon,QFont,QAction,QColor,QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QVBoxLayout,QHBoxLayout,
    QGridLayout,QStackedWidget,QScrollArea,QFileDialog,QInputDialog,QMenu,QAbstractSpinBox,
    QHeaderView,QAbstractItemView,QSizePolicy,QAbstractScrollArea,QColorDialog)
from .qt_translation import ui_text,retranslate_widgets,QLabel,QLineEdit,QCheckBox,QDialog,QToolButton,QTableWidget,QTableWidgetItem
from .controller import MonitorActions
from .model import Catalog,Game,Settings,norm,blocked,helper
from .service import DiscoveryService
from .tracker import Tracker
from .hub import HubWorker
from .i18n import tr,LANGUAGES
from . import win32,__version__
from .qt_widgets import STYLE,ACCENT,MUTED,label,button,panel,separator,glyph,duration,BudgetRing,LocalArtwork,CardGrid,GameCard,normalize_icon
from .qt_widgets import (NoWheelComboBox as QComboBox,NoWheelDoubleSpinBox as QDoubleSpinBox,
    NoWheelTimeEdit as QTimeEdit,NoWheelSlider as QSlider)
from .qt_statistics import StatisticsPage
from .focus import Focus, BROWSERS, app_key, SHELLS
from .qt_focus import FocusPage
from .overlay import CountdownOverlay,PositionPicker,choose_screen,foreground_screen_name
from .rtss import Backend as RTSSBackend, countdown as rtss_countdown, installation as rtss_installation
from .statistics_sync import StatisticsData
from .statistics_cloud import CloudSyncWorker,SERVICE_URL,SYNC_COOLDOWN
from .statistics_auth import AuthWorker
from .schedule import day_settings,game_settings,any_countdown,bedtime_occurrence,DayScheduleError,DAY_NAMES
from .budget import remaining_budget,quota_plan,game_remaining,gameplay_budget
from .quota import reset_clock,period_day,reset_at
from .sound import play_notification
from .game_preview import SnapshotWorker,running_window
from .qt_game_preview import background_controls
from .game_safety import policy as safety
from .overlay_consent import Consents,MinimizeConsents,overlay_reason

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
    app.setApplicationName('Keep Improving'); app.setOrganizationName('GameTimeMonitor')
    app.setQuitOnLastWindowClosed(False); app.setStyle('Fusion'); app.setStyleSheet(STYLE)
    app.setFont(QFont('Segoe UI',10)); app.setWindowIcon(QIcon(str(Path(__file__).with_name('app.ico'))))
    return app

class CodeVisibilityGuard(QObject):
    """A revealed connection secret must not remain visible in a retired window."""
    def __init__(self,window,hide_code):
        super().__init__(window)
        self.hide_code=hide_code
        window.installEventFilter(self)

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.WindowDeactivate,QEvent.Hide): self.hide_code()
        return False


class AlertDialog(QDialog):
    def __init__(self,owner,passive=False):
        flags=Qt.Dialog|Qt.WindowStaysOnTopHint|Qt.WindowCloseButtonHint
        if passive: flags|=Qt.WindowDoesNotAcceptFocus
        super().__init__(None,flags)
        if passive: self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.owner=owner; self.setObjectName('Surface'); self.setAttribute(Qt.WA_DeleteOnClose)
    def closeEvent(self,event):
        if self.owner.popup_window is self: self.owner.popup_window=self.owner.popup_day=None
        event.accept()

class App(QMainWindow,MonitorActions):
    shutdown=Signal()

    def __init__(self,store,data_dir,background=False,service=None,hub=None,updates=False):
        super().__init__()
        self.setCursor(Qt.ArrowCursor)
        self.store,self.data_dir=store,Path(data_dir)
        from .bedtime_legacy import migrate
        migrate(store,self.data_dir)
        self.settings=store.settings(); self.catalog=Catalog(self.settings,store.games(True),store.overrides(),store.rules())
        self.overlay_consents=Consents(store); self.catalog.overlay_consents=self.overlay_consents
        self.minimize_consents=MinimizeConsents(store)
        self.statistics_data=StatisticsData(store); self.statistics_sync=CloudSyncWorker()
        self.account_auth=AuthWorker(); self.account_session=store.account_session()
        self._auth_busy=False; self._auth_callback=None
        self._sync_busy=False; self._sync_status='Sync enabled.'; self._sync_success_at=''
        self._sync_startup_pending=self.settings.statistics_sync_enabled
        self._sync_event_pending=False
        self.statistics_event_timer=QTimer(self); self.statistics_event_timer.setSingleShot(True)
        self.statistics_event_timer.timeout.connect(self.sync_statistics_event)
        self.tracker=Tracker(store,self.catalog); self.hub=hub or HubWorker(data_dir); self.hub_fingerprint=None
        self.focus=Focus(store); self.browser_bridge=None; self._focus_notice=''
        if store.db.execute("SELECT 1 FROM settings WHERE key='browser_pairing'").fetchone(): self.enable_browser_bridge()
        self.service=service or DiscoveryService(self.settings)
        self.catalog.steam_libraries=self.service.discovery.libraries_from_metadata()
        self.popup_window=self.popup_day=self.notification_timer=None; self.escape_attempts=set(); self.closed=False
        self.launcher=None; self.launching=None; self.last_rows=None
        self.clients=[]; self.client_worker=None; self._clients_busy=False; self._clients_loaded=False
        self.tick_timer=self.tray_timer=None; self._timers=set(); self._dialogs=[]
        self.hidden_ids=store.hidden_ids(); self.selected_id=None; self.show_hidden=False; self.cards={}
        self.status_key='Discovering games…'; self.status_values={}; self.status_text=self.t(self.status_key)
        from .qt_updates import Updates
        self.updates=Updates(self,updates)
        self.art=LocalArtwork(data_dir,self.service.discovery.roots); self.art.refresh_links(self.settings.games_root)
        self.setWindowTitle('Keep Improving'); self.setWindowIcon(QIcon(str(Path(__file__).with_name('app.ico'))))
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1380,screen.width()-60),min(920,screen.height()-60)); self.setMinimumSize(1000,700)
        self.overlay_failed=False; self.overlay=None; self._overlay_preview_until=0
        self._overlay_desktop_until=0
        self._overlay_preview_target=None; self.game_snapshots=SnapshotWorker(self)
        self.rtss=RTSSBackend(self.data_dir); self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
        self._rtss_publishing=False; self._rtss_checked=0; self._rtss_available=False
        self._rtss_consent_paths=frozenset(); self._rtss_consent_attempt=None
        if self.settings.overlay_rtss_auto: self.rtss.protect()
        self.overlay_timer=QTimer(self); self.overlay_timer.setInterval(200); self.overlay_timer.timeout.connect(self.update_overlay)
        self.assets_timer=QTimer(self); self.assets_timer.setInterval(1000); self.assets_timer.timeout.connect(self.poll_assets)
        self._build(); dark_window(self)
        try: self.overlay=CountdownOverlay(self)
        except Exception:
            self.overlay_failed=True; log.exception('Countdown initialization failed')
            self.set_status('Countdown unavailable; early warning popups remain active.')
        QApplication.instance().screenAdded.connect(self.refresh_overlay_screens)
        QApplication.instance().screenRemoved.connect(self.refresh_overlay_screens)
        self.tray=win32.Tray(self.show,self.tray_menu,self.devices_changed,identity=self.data_dir)
        self.refresh_manual_availability(); self.service.start(); self.render()
        self.updates.reschedule()
        if not background or not self.tray.available: self.show()
        self.assets_timer.start()
        self.tick_timer=self.call_later(200,self.tick); self.tray_timer=self.call_later(75,self.poll_tray)
        self.call_later(20,self.prepare_rtss_profiles)

    def t(self,text,**values): return ui_text(text,self.settings.language,**values)
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
        name=label('Keep Improving'); name.setFont(QFont('Segoe UI',11,QFont.Bold)); brand.addWidget(name,1); side.addLayout(brand)
        side.addSpacing(32)
        self.nav={}
        for index,text,icon in ((0,'Library','library'),(4,'Focus & activity','focus'),(1,'Statistics','stats'),(2,'Settings','settings')):
            item=button(self.t(text),lambda checked=False,n=index:self.switch_page(n),'nav'); item.setCheckable(True); item.setIcon(glyph(icon)); item.setMinimumHeight(45)
            self.nav[index]=item; side.addWidget(item)
        side.addStretch()
        self.language=QComboBox()
        self.language.setAccessibleName(self.t('Language / Nyelv')); self.language.setToolTip(self.t('Language / Nyelv'))
        self.language.setIconSize(QSize(24,16))
        for name,code in LANGUAGES.items(): self.language.addItem(QIcon(str(Path(__file__).with_name('icons')/f'flag-{code}.svg')),name,code)
        self.language.setCurrentIndex(self.language.findData(self.settings.language)); self.language.currentIndexChanged.connect(lambda index:self.set_language(self.language.itemData(index)))
        side.addWidget(self.language)
        row.addWidget(rail)
        right=QVBoxLayout(); right.setContentsMargins(0,0,0,0); right.setSpacing(0)
        self.restriction_banner=QFrame(); self.restriction_banner.setStyleSheet('QFrame {background:#45232b; border:0;}')
        banner_layout=QHBoxLayout(self.restriction_banner); banner_layout.setContentsMargins(30,12,24,12)
        self.restriction_label=label(); self.restriction_label.setWordWrap(True); self.restriction_label.setStyleSheet('color:#ffc5cc;')
        banner_layout.addWidget(self.restriction_label,1); banner_layout.addWidget(button(self.t('Settings'),self.settings_dialog))
        right.addWidget(self.restriction_banner); self.restriction_banner.hide()
        self.bedtime_banner=QFrame(); self.bedtime_banner.setStyleSheet('QFrame {background:#382b45; border:0;}')
        bedtime_row=QHBoxLayout(self.bedtime_banner); bedtime_row.setContentsMargins(30,12,24,12)
        bedtime_note=label(self.t('Bedtime: eligible foreground windows are minimized every 10 seconds. Protected games require separate minimization consent. Change this in Settings.'))
        bedtime_note.setWordWrap(True); bedtime_row.addWidget(bedtime_note,1)
        bedtime_row.addWidget(button(self.t('Settings'),self.settings_dialog)); right.addWidget(self.bedtime_banner); self.bedtime_banner.hide()
        right.addWidget(self.updates.banner())
        self.pages=QStackedWidget(); right.addWidget(self.pages,1)
        self.hub_page=self._build_library(state); self.pages.addWidget(self.hub_page)
        self.statistics=StatisticsPage(self); self.pages.addWidget(self.statistics)
        self.settings_page=self._build_settings(); self.pages.addWidget(self.settings_page)
        # Keep the previous internal index stable; client navigation now expands the library panel.
        self.pages.addWidget(QWidget())
        self.focus_page=FocusPage(self); self.pages.addWidget(self.focus_page)
        self.status_label=label(self.status_text,'muted'); self.status_label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        self.status_label.setStyleSheet('font-size:11px; padding:8px 32px 12px; color:#7d9395;'); right.addWidget(self.status_label)
        self.status_label.setVisible(time.monotonic()<getattr(self,'_status_until',0))
        row.addLayout(right,1)
        previous=self.takeCentralWidget(); self.setCentralWidget(surface)
        if previous: previous.deleteLater()
        self.show_hidden=state.get('show_hidden',self.show_hidden); self.hidden_toggle.setChecked(self.show_hidden)
        self.search.setText(state.get('query','')); self.sort.setCurrentIndex(self.sort.findData(state.get('sort','name')))
        self.statistics.start.setText(state.get('start',self.statistics.start.text())); self.statistics.end.setText(state.get('end',self.statistics.end.text()))
        self.statistics._range=(self.statistics.start.text(),self.statistics.end.text())
        self.statistics.selected_day=state.get('day')
        self.statistics.scope=state.get('statistics_scope','all')
        self.statistics.chart_mode.setCurrentIndex(self.statistics.chart_mode.findData(state.get('statistics_chart_mode','total')))
        self.pages.setCurrentIndex(0 if state.get('page')==3 else state.get('page',0))
        for i,item in self.nav.items(): item.setChecked(i==self.pages.currentIndex())

    def _build_clients(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(8)
        row=QHBoxLayout(); row.addWidget(label(self.t('Open an installed launcher.'),'muted'),1)
        self.clients_refresh=button(self.t('Refresh'),self.refresh_clients); row.addWidget(self.clients_refresh); layout.addLayout(row)
        self.clients_status=label('','muted'); self.clients_status.setWordWrap(True); layout.addWidget(self.clients_status)
        content=QWidget(); self.clients_layout=QGridLayout(content)
        self.clients_layout.setContentsMargins(0,0,0,0); self.clients_layout.setSpacing(16); self.clients_layout.setAlignment(Qt.AlignTop)
        self.client_cards={}; self.client_buttons={}
        layout.addWidget(content); page.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.render_clients(); return page

    def refresh_clients(self):
        if self.closed or self._clients_busy: return
        if self.client_worker is None:
            from .clients import ClientWorker
            self.client_worker=ClientWorker(self.data_dir)
        self._clients_busy=True; self.clients_refresh.setEnabled(False); self.clients_status.setText(self.t('Finding installed launchers…')); self.clients_status.show()
        self.client_worker.request(self.settings)
        self.update_assets_interval()

    def render_clients(self):
        if not hasattr(self,'clients_layout'): return
        previous=self.client_cards; cards={}; buttons={}
        for index,client in enumerate(self.clients):
            if client.id in previous and previous[client.id][0]==client:
                cards[client.id]=previous[client.id]; buttons[client.id]=self.client_buttons[client.id]; continue
            card=panel(); body=QHBoxLayout(card); body.setContentsMargins(12,10,12,10); body.setSpacing(10)
            icon=QLabel(); icon.setFixedSize(32,32)
            from PySide6.QtCore import QFileInfo
            pix=normalize_icon(self.art.provider.icon(QFileInfo(client.icon or client.target)).pixmap(48,48))
            if pix is not None and not pix.isNull(): icon.setPixmap(pix.scaled(32,32,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            body.addWidget(icon); body.addWidget(label(client.name),1)
            launch=button(self.t('Open'),lambda checked=False,c=client:self.open_client(c)); launch.setAccessibleName(self.t('Open')+' '+client.name); body.addWidget(launch)
            cards[client.id]=(client,card); buttons[client.id]=launch
        if list(cards.values())!=list(previous.values()):
            content=self.clients_layout.parentWidget(); content.setUpdatesEnabled(False)
            try:
                for identity,(client,card) in previous.items():
                    if cards.get(identity)!=(client,card):
                        self.clients_layout.removeWidget(card); card.hide(); card.deleteLater()
                for index,(client,card) in enumerate(cards.values()): self.clients_layout.addWidget(card,index//2,index%2)
            finally: content.setUpdatesEnabled(True)
        self.client_cards=cards; self.client_buttons=buttons
        for column in range(2): self.clients_layout.setColumnStretch(column,1)
        self.clients_status.setText(self.t('Finding installed launchers…') if self._clients_busy else self.t('No supported launcher found. Install a client, then refresh.') if not self.clients else '')
        self.clients_status.setVisible(bool(self.clients_status.text()))
        self.clients_refresh.setEnabled(not self._clients_busy)

    def open_client(self,client):
        try:
            from .clients import start_client
            start_client(client); self.set_status('Opened {name}.',name=client.name)
        except (OSError,ValueError) as exc:
            self.set_status('Could not open {name}. Refresh the launcher list.',name=client.name); self.message(self.t(str(exc)))

    def poll_assets(self):
        if self.closed: return
        try:
            changed=self.art.poll()
            for key in changed:
                card=self.cards.get(key[0])
                if card and self.art.key(card.game)==key: card.art=self.art.cache[key]; card.update()
            if changed: self.update_launch_button(); self.prepare_rtss_profiles(changed)
            if self.client_worker:
                while not self.client_worker.results.empty():
                    clients,warning=self.client_worker.results.get_nowait(); self._clients_busy=False
                    if clients is not None:
                        self.clients=clients; self._clients_loaded=True
                        try: self.store.save_client_cache(clients)
                        except SQLiteError: log.warning('Could not remember launchers',exc_info=True)
                    self.render_clients()
                    if warning: self.clients_status.setText(self.t(warning)); self.clients_status.show()
        except (OSError,ValueError,RuntimeError): log.warning('Optional assets/launchers unavailable',exc_info=True)
        self.poll_account()
        self.poll_statistics_sync()
        self.updates.poll()
        self.update_assets_interval()

    def update_assets_interval(self):
        # Workers still return promptly; an empty queue needs no 100 ms wakeups.
        interval=100 if self.art.pending or self._clients_busy or self._sync_busy else 1000
        if self.assets_timer.interval()!=interval: self.assets_timer.setInterval(interval)

    def request_account(self,action,code,callback):
        if self.closed or self._auth_busy: return False
        self._auth_busy=self.account_auth.request(action,self.account_session,code)
        if self._auth_busy:
            self._auth_callback=callback
            for window in self._dialogs:
                update=getattr(window,'_account_update',None)
                if update: update()
        return self._auth_busy

    def poll_account(self):
        while not self.account_auth.results.empty():
            token,values,warning=self.account_auth.results.get_nowait()
            if token[2]!=self.account_auth.generation: continue
            self._auth_busy=False; value=values[0] if values else {}
            if 'session' in value:
                self.account_session=value['session']
                try: self.store.save_account_session(value['session'])
                except (OSError,SQLiteError):
                    warning='Could not save account sign-in. Try again.'
                    value={**value,'ok':False,'error':'storage'}
            callback,self._auth_callback=self._auth_callback,None
            for window in self._dialogs:
                update=getattr(window,'_account_update',None)
                if update: update()
            if callback: callback(value,warning)

    def statistics_sync_status(self):
        if self.store.credentials_unavailable: return self.t('Enter your connection code again on this Windows account to reconnect.')
        if not self.settings.statistics_sync_enabled: return self.t('Statistics sync is off.')
        if self._sync_status=='Statistics synchronized.':
            return self.t('Last sync: {time}',time=self._sync_success_at)
        return self.t(self._sync_status)

    def update_statistics_sync_status(self):
        for widget in (getattr(self,'sync_summary',None),getattr(self.statistics,'sync_label',None)):
            if widget: widget.setText(self.statistics_sync_status())
        self.update_statistics_sync_controls()

    def update_statistics_sync_controls(self):
        page=getattr(self,'statistics',None)
        if not page: return
        delay=max(self.statistics_sync.retry_delay(SERVICE_URL,self.settings.statistics_sync_group),
                  self.statistics_data.sync_delay())
        allowed=self.settings.statistics_sync_enabled and not self._sync_busy and not delay
        if page.sync_now.isEnabled()!=bool(allowed): page.sync_now.setEnabled(bool(allowed))
        # Reuse the existing GUI timer only while a visible countdown is useful.
        if not self.isVisible() or self.isMinimized() or self.pages.currentIndex()!=1: return
        text=(self.t('Syncing…') if self._sync_busy else self.t('Sync now') if not self.settings.statistics_sync_enabled else
              self.t('Wait {seconds}s',seconds=int(delay)+1) if 0<delay<=60 else
              self.t('Wait {minutes} min',minutes=int(delay/60)+1) if delay else self.t('Sync now'))
        if page.sync_now.text()!=text: page.sync_now.setText(text)

    def request_statistics_sync(self):
        if self.closed or self._sync_busy or not self.settings.statistics_sync_enabled: return
        if self.statistics_sync.retry_delay(SERVICE_URL,self.settings.statistics_sync_group): return
        if self.statistics_data.sync_delay(): return
        self._sync_startup_pending=False
        try:
            if not SERVICE_URL: raise ValueError('The synchronization service is not configured yet.')
            self.statistics_data.defer_sync(SYNC_COOLDOWN)
            self._sync_event_pending=False; self.statistics_event_timer.stop()
            self.tracker.flush()
            snapshot=self.statistics_data.snapshot(self.settings.statistics_sync_group,self.settings.statistics_device_name)
            self._sync_busy=self.statistics_sync.request(SERVICE_URL,self.settings.statistics_sync_group,snapshot,
                                                       self.statistics_data.revisions(self.settings.statistics_sync_group))
            self._sync_status='Synchronizing statistics…'
        except (ValueError,OSError):
            self._sync_status='Could not prepare statistics for synchronization.'
            log.warning('Could not prepare statistics snapshot',exc_info=True)
        self.update_statistics_sync_status()
        self.update_assets_interval()

    def statistics_activity_changed(self, playing):
        # Foreground transitions already observed for accounting; no process scans.
        # One quiet minute coalesces Alt-Tab/game-ending events into a single upload.
        self.schedule_statistics_event(0 if playing else 60)

    def schedule_statistics_event(self, quiet_seconds=0):
        if self.closed or not self.settings.statistics_sync_enabled: return
        self._sync_event_pending=True
        delay=max(quiet_seconds,self.statistics_data.sync_delay(),
                  self.statistics_sync.retry_delay(SERVICE_URL,self.settings.statistics_sync_group))
        self.statistics_event_timer.start(max(1,int(delay*1000)+1))

    def sync_statistics_event(self):
        if self.closed or not self.settings.statistics_sync_enabled:
            self._sync_event_pending=False; return
        if self._sync_busy: return  # Completion arms the one pending event.
        if (self.statistics_data.sync_delay() or
            self.statistics_sync.retry_delay(SERVICE_URL,self.settings.statistics_sync_group)):
            self.schedule_statistics_event(); return
        self._sync_event_pending=False
        self.request_statistics_sync()

    def poll_statistics_sync(self):
        while not self.statistics_sync.results.empty():
            token,values,warning=self.statistics_sync.results.get_nowait()
            if token!=(SERVICE_URL,self.settings.statistics_sync_group,self.statistics_sync.generation): continue
            self._sync_busy=False; changed=False
            for value in values:
                try: changed=self.statistics_data.ingest(value,token[1]) or changed
                except ValueError: warning='Some computer data could not be read. Try syncing manually later.'
            delay=self.statistics_sync.retry_delay(SERVICE_URL,self.settings.statistics_sync_group)
            if delay: self.statistics_data.defer_sync(delay)
            self._sync_status=warning or 'Statistics synchronized.'
            if not warning: self._sync_success_at=datetime.now().strftime('%Y-%m-%d %H:%M')
            if self._sync_event_pending and not self.statistics_event_timer.isActive():
                self.schedule_statistics_event()
            if changed and self.isVisible() and not self.isMinimized() and self.pages.currentIndex()==1: self.statistics.refresh(live=True)
            self.update_statistics_sync_status()
        self.update_statistics_sync_controls()
        if self._sync_startup_pending:
            self._sync_startup_pending=False
            self.request_statistics_sync()

    def statistics_sync_dialog(self):
        from .qt_account import statistics_dialog
        statistics_dialog(self)

    def refresh_sources(self):
        self.art.invalidate(); self._art_queue=list(self.cards); self.call_later(10,self.load_next_art)
        if self._clients_loaded or self.client_worker: self.refresh_clients()
        MonitorActions.refresh_sources(self)

    def _build_library(self,state):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(32,25,24,17); layout.setSpacing(17)
        top=QHBoxLayout(); top.addWidget(label(self.t('Library'),'title'),1)
        add=button(self.t('Add'),self.add_manual); add.setToolTip(self.t('Add game')); add.setIcon(glyph('plus','#cee1db',17)); top.addWidget(add); layout.addLayout(top)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget(); body=QVBoxLayout(content); body.setContentsMargins(0,0,8,0); body.setSpacing(17)
        self.scroll.setWidget(content); layout.addWidget(self.scroll,1); layout=body
        budget=panel('Budget'); budget_row=QHBoxLayout(budget); budget_row.setContentsMargins(20,14,22,14); budget_row.setSpacing(20)
        self.ring=BudgetRing(); budget_row.addWidget(self.ring)
        self.total_label=label('00:00:00','metric'); self.remaining_label=label('00:00:00','metric')
        for title,value in [('Today',self.total_label),('Remaining',self.remaining_label)]:
            box=QVBoxLayout(); box.setSpacing(4); box.addWidget(label(self.t(title),'muted')); box.addWidget(value)
            if title=='Remaining':
                self.remaining_reason=label('','muted'); self.remaining_reason.hide(); box.addWidget(self.remaining_reason)
            budget_row.addLayout(box,1)
        self.active_label=label('','muted'); self.active_label.setWordWrap(True); self.active_label.setMaximumWidth(220)
        budget_row.addWidget(self.active_label,1); layout.addWidget(budget)
        self.clients_toggle=QToolButton(); self.clients_toggle.setText(self.t('Launchers')); self.clients_toggle.setCheckable(True)
        self.clients_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); self.clients_toggle.setArrowType(Qt.RightArrow)
        self.clients_toggle.setCursor(Qt.PointingHandCursor); self.clients_toggle.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.clients_toggle.setStyleSheet('text-align:left; padding:8px 12px;'); self.clients_toggle.clicked.connect(self.set_clients_expanded)
        layout.addWidget(self.clients_toggle)
        self.clients_page=self._build_clients(); self.clients_page.hide(); layout.addWidget(self.clients_page)
        toolbar=QHBoxLayout(); toolbar.setSpacing(10)
        self.search=QLineEdit(); self.search.setPlaceholderText(self.t('Search your games…')); self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph('search',MUTED,18),QLineEdit.LeadingPosition); toolbar.addWidget(self.search,1)
        self.source_filter=QComboBox(); self.source_filter.setMinimumWidth(170); self.source_filter.addItem(self.t('All sources'),None); toolbar.addWidget(self.source_filter)
        self.hidden_toggle=QCheckBox(self.t('Show hidden games')); self.hidden_toggle.setToolTip(self.t('Show hidden games (hiding does not stop tracking)')); toolbar.addWidget(self.hidden_toggle)
        self.sort=QComboBox(); self.sort.addItem(self.t('Name: A–Z'),'name'); self.sort.addItem(self.t('Most played today'),'today'); self.sort.setFixedWidth(186); toolbar.addWidget(self.sort); layout.addLayout(toolbar)
        self.grid=CardGrid(); layout.addWidget(self.grid,1)
        self.empty=label(self.t('No games match this view.'),'muted'); self.empty.setAlignment(Qt.AlignCenter); self.empty.hide(); layout.addWidget(self.empty)
        self.search.textChanged.connect(self.refresh_view); self.source_filter.currentIndexChanged.connect(self.refresh_view)
        self.hidden_toggle.toggled.connect(self.refresh_view); self.sort.currentIndexChanged.connect(self.refresh_view)
        self._restore_source=state.get('source')
        return page

    def _build_settings(self):
        page=QWidget(); outer=QVBoxLayout(page); outer.setContentsMargins(32,25,32,22); outer.setSpacing(16)
        heading=label(self.t('Settings'),'title'); heading.setToolTip('Keep Improving '+__version__); outer.addWidget(heading)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll,1)
        body=QWidget(); body_layout=QVBoxLayout(body); body_layout.setContentsMargins(0,0,8,0); body_layout.setSpacing(18); scroll.setWidget(body)
        body_layout.addWidget(self.updates.settings_panel())
        from .qt_schedule import WeeklyScheduleEditor
        self.schedule_editor=WeeklyScheduleEditor(self.settings,self.t)
        for name in ('limit','warning','restriction_enabled','restriction_minutes','bedtime_enabled','bedtime_times','bedtime_minimize','bedtime_controls','bedtime_caps_budget'):
            setattr(self,name,getattr(self.schedule_editor,name))
        body_layout.addWidget(self.schedule_editor)
        limits=panel(); limits_layout=QVBoxLayout(limits); limits_layout.setContentsMargins(22,20,22,22); limits_layout.setSpacing(12)
        limits_layout.addWidget(label(self.t('Per-game limits'),'section'))
        note=label(self.t('Each game limit is part of the shared daily budget. The overlay shows whichever runs out first.'),'muted'); note.setWordWrap(True); limits_layout.addWidget(note)
        limits_layout.addWidget(button(self.t('Per-game limits…'),self.game_limits_dialog),0,Qt.AlignLeft); body_layout.addWidget(limits)
        messages=panel(); message_layout=QVBoxLayout(messages); message_layout.setContentsMargins(22,20,22,22); message_layout.setSpacing(12)
        message_layout.addWidget(label(self.t('Reminder messages'),'section'))
        note=label(self.t('These messages are shared by all days. The test uses today’s saved bedtime schedule.'),'muted'); note.setWordWrap(True); message_layout.addWidget(note)
        actions=QHBoxLayout(); actions.addWidget(button(self.t('Custom messages…'),self.custom_messages_dialog))
        actions.addWidget(button(self.t('Test bedtime reminder'),self.test_bedtime_popup,'quiet')); actions.addStretch(); message_layout.addLayout(actions); body_layout.addWidget(messages)
        from .qt_personalization import sound_panel
        body_layout.addWidget(sound_panel(self))
        sync=panel(); sync_layout=QVBoxLayout(sync); sync_layout.setContentsMargins(22,20,22,22); sync_layout.setSpacing(12)
        sync_layout.addWidget(label(self.t('Linked statistics'),'section'))
        self.sync_summary=label(self.statistics_sync_status(),'muted'); self.sync_summary.setWordWrap(True); sync_layout.addWidget(self.sync_summary)
        sync_layout.addWidget(button(self.t('Link computers'),self.statistics_sync_dialog),0,Qt.AlignLeft); body_layout.addWidget(sync)
        body_layout.addWidget(self.build_overlay_settings())
        locations=panel(); places=QVBoxLayout(locations); places.setContentsMargins(22,20,22,22); places.setSpacing(12)
        places.addWidget(label(self.t('Games folder'),'section'))
        browse=QHBoxLayout(); self.games_path=QLineEdit(self.settings.games_root); browse.addWidget(self.games_path,1); browse.addWidget(button(self.t('Browse…'),self.browse_root)); places.addLayout(browse)
        self.hub_enabled=QCheckBox(self.t('Maintain game shortcuts')); self.hub_enabled.setToolTip(self.t('Also maintain a shortcuts folder (optional)')); self.hub_enabled.setChecked(self.settings.hub_enabled); places.addWidget(self.hub_enabled)
        advanced=QToolButton(); advanced.setText(self.t('Advanced')); advanced.setCheckable(True); advanced.setArrowType(Qt.RightArrow); advanced.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        places.addWidget(advanced); extra=QWidget(); extra_layout=QVBoxLayout(extra); extra_layout.setContentsMargins(0,6,0,0); extra_layout.setSpacing(12)
        extra.hide(); places.addWidget(extra)
        def expand(checked): extra.setVisible(checked); advanced.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        advanced.toggled.connect(expand)
        self.paths={}
        for key,text,values in [('steam','Additional Steam installations (separated by semicolons)',self.settings.steam_roots),('epic','Additional Epic manifest folders (separated by semicolons)',self.settings.epic_manifest_dirs),('ubisoft','Additional Ubisoft Connect installations (separated by semicolons)',self.settings.ubisoft_roots)]:
            extra_layout.addWidget(label(self.t(text),'muted')); edit=QLineEdit(';'.join(values)); extra_layout.addWidget(edit); self.paths[key]=edit
        body_layout.addWidget(locations); body_layout.addStretch()
        footer=QHBoxLayout(); self.settings_error=label('','danger'); self.settings_error.setWordWrap(True); footer.addWidget(self.settings_error,1)
        footer.addWidget(button(self.t('Save'),self.save_settings,'primary')); outer.addLayout(footer)
        return page

    def update_bedtime_banner(self,active):
        if self.bedtime_banner.isHidden()==bool(active): self.bedtime_banner.setVisible(active)

    def build_overlay_settings(self):
        card=panel(); layout=QVBoxLayout(card); layout.setContentsMargins(22,20,22,22); layout.setSpacing(12)
        layout.addWidget(label(self.t('Countdown'),'section'))
        self.overlay_enabled=QCheckBox(self.t('Show while gaming')); self.overlay_enabled.setToolTip(self.t('Show a click-through countdown while gaming')); self.overlay_enabled.setChecked(self.settings.overlay_enabled); layout.addWidget(self.overlay_enabled)
        layout.addWidget(separator()); layout.addWidget(label(self.t('Countdown notifications'),'section'))
        self.overlay_warning=QCheckBox(self.t('Warning color instead of early popup')); self.overlay_warning.setChecked(self.settings.overlay_replace_warning); layout.addWidget(self.overlay_warning)
        self.limit_popup=QCheckBox(self.t('Popup when time expires')); self.limit_popup.setChecked(self.settings.limit_popup_enabled); layout.addWidget(self.limit_popup)
        test=button(self.t('Test alert'),self.test_popup,'quiet'); test.setIcon(glyph('bell',MUTED,18)); layout.addWidget(test,0,Qt.AlignLeft)
        self.overlay_controls=QWidget(); controls=QVBoxLayout(self.overlay_controls); controls.setContentsMargins(0,4,0,0); controls.setSpacing(10)
        controls.addWidget(separator()); controls.addWidget(label(self.t('Position and text size'),'section'))
        fields=QHBoxLayout(); fields.addWidget(label(self.t('Monitor'),'muted')); self.overlay_screen=QComboBox(); fields.addWidget(self.overlay_screen,1); controls.addLayout(fields)
        self.overlay_picker=PositionPicker(self.settings.overlay_x,self.settings.overlay_y,QApplication.primaryScreen(),self.settings.overlay_font_size)
        self.overlay_picker.setAccessibleName(self.t('Countdown position'))
        self.overlay_screen.currentIndexChanged.connect(self.overlay_screen_changed)
        self.refresh_overlay_screens()
        self.overlay_screen.setCurrentIndex(max(0,self.overlay_screen.findData(self.settings.overlay_screen)))
        controls.addWidget(self.overlay_picker)
        controls.addWidget(background_controls(self,self.overlay_picker,lambda:None,lambda:self.overlay_screen.currentData(),self.update_overlay_coordinates))
        hint=label(self.t('Drag the timer or enter its position from the display’s top-left corner. Arrow keys move 1 px; Shift + arrow moves 10 px. Preview shows changes before saving.'),'muted')
        hint.setWordWrap(True); controls.addWidget(hint)
        precise=QHBoxLayout(); precise.setSpacing(14); self.overlay_coordinates=[]
        for axis,text in enumerate(('Horizontal (px)','Vertical (px)')):
            group=QVBoxLayout(); group.addWidget(label(self.t(text),'muted'))
            edit=QDoubleSpinBox(); edit.setDecimals(0); edit.setSingleStep(1); edit.setKeyboardTracking(False); edit.setButtonSymbols(QAbstractSpinBox.NoButtons)
            edit.setAccessibleName(self.t(text))
            self.overlay_coordinates.append(edit); edit.valueChanged.connect(lambda value,n=axis:self.overlay_coordinate_changed(n,value))
            group.addWidget(edit); precise.addLayout(group,1)
        group=QVBoxLayout(); group.addWidget(label(self.t('Text size'),'muted'))
        self.overlay_font_size=QDoubleSpinBox(); self.overlay_font_size.setDecimals(0); self.overlay_font_size.setRange(8,72)
        self.overlay_font_size.setKeyboardTracking(False)
        self.overlay_font_size.setButtonSymbols(QAbstractSpinBox.NoButtons); self.overlay_font_size.setSuffix(' pt')
        self.overlay_font_size.setAccessibleName(self.t('Text size')); self.overlay_font_size.setValue(self.settings.overlay_font_size)
        self.overlay_font_size.valueChanged.connect(self.overlay_size_changed); group.addWidget(self.overlay_font_size); precise.addLayout(group,1)
        controls.addLayout(precise)
        controls.addWidget(separator()); controls.addWidget(label(self.t('Colors and opacity'),'section'))
        self.overlay_picker.positionChanged.connect(self.overlay_position_changed); self.update_overlay_coordinates()
        colors=QHBoxLayout(); self.overlay_colors={'normal':self.settings.overlay_color_normal,'warning':self.settings.overlay_color_warning}; self.overlay_color_buttons={}
        for kind,text in (('normal','Normal color'),('warning','Warning color')):
            colors.addWidget(label(self.t(text),'muted'))
            item=button('',lambda checked=False,k=kind:self.choose_overlay_color(k)); item.setAccessibleName(self.t(text))
            self.overlay_color_buttons[kind]=item; colors.addWidget(item)
        colors.addWidget(button(self.t('Reset colors'),self.reset_overlay_colors)); colors.addStretch(); controls.addLayout(colors)
        self.overlay_preview_state=QComboBox(); self.overlay_preview_state.setAccessibleName(self.t('Preview state'))
        self.overlay_preview_state.addItem(self.t('Normal color'),'normal'); self.overlay_preview_state.addItem(self.t('Warning color'),'warning'); self.overlay_preview_state.setCurrentIndex(1)
        self.overlay_preview_state.currentIndexChanged.connect(self.update_overlay_colors); self.update_overlay_colors(refresh=False)
        opacity=QHBoxLayout(); opacity.addWidget(label(self.t('Text opacity'),'muted'))
        self.overlay_opacity=QSlider(Qt.Horizontal); self.overlay_opacity.setAccessibleName(self.t('Text opacity'))
        self.overlay_opacity.setRange(25,100); self.overlay_opacity.setValue(round(self.settings.overlay_opacity*100)); opacity.addWidget(self.overlay_opacity,1)
        self.overlay_opacity_label=label(str(self.overlay_opacity.value())+'%'); self.overlay_opacity.valueChanged.connect(lambda value:self.overlay_opacity_label.setText(str(value)+'%'))
        self.overlay_opacity.valueChanged.connect(lambda value:self.update_overlay()); opacity.addWidget(self.overlay_opacity_label); controls.addLayout(opacity)
        controls.addWidget(separator()); controls.addWidget(label(self.t('Countdown preview'),'section'))
        actions=QHBoxLayout(); actions.addWidget(button(self.t('Preview (10s)'),self.preview_overlay))
        actions.addWidget(label(self.t('Preview state'),'muted')); actions.addWidget(self.overlay_preview_state)
        actions.addStretch(); actions.addWidget(button(self.t('Reset position'),lambda:self.overlay_picker.set_position(1,0))); controls.addLayout(actions)
        self.overlay_preview_status=label(self.t('Preview brings a running game to the foreground. Alt+Tab ends the preview.'),'muted'); self.overlay_preview_status.setWordWrap(True); controls.addWidget(self.overlay_preview_status)
        note=label(self.t('Exclusive fullscreen may require RTSS.'),'muted'); note.setToolTip(self.t('The countdown never takes focus or mouse input. Exclusive fullscreen may hide desktop overlays; windowed or borderless mode is more reliable.')); note.setWordWrap(True); controls.addWidget(note)
        controls.addWidget(button(self.t('In-game countdown (RTSS)…'),self.rtss_dialog,'quiet'),0,Qt.AlignLeft)
        protection=label(self.t('Protected games need separate risk consent under Per-game countdowns. Without consent, overlays and game images stay off. Automatic Escape stays disabled.'),'muted'); protection.setWordWrap(True); controls.addWidget(protection)
        self.rtss_status=label('','muted'); self.rtss_status.setWordWrap(True); self.rtss_status.hide(); controls.addWidget(self.rtss_status)
        layout.addWidget(self.overlay_controls)
        layout.addWidget(button(self.t('Per-game countdowns…'),self.game_countdown_dialog),0,Qt.AlignLeft)
        self.overlay_enabled.toggled.connect(self.overlay_controls.setEnabled); self.overlay_enabled.toggled.connect(self.overlay_warning.setEnabled)
        self.overlay_controls.setEnabled(self.overlay_enabled.isChecked()); self.overlay_warning.setEnabled(self.overlay_enabled.isChecked())
        return card

    def refresh_overlay_screens(self,*args):
        if not hasattr(self,'overlay_screen'): return
        wanted=self.overlay_screen.currentData()
        if wanted is None: wanted=self.settings.overlay_screen
        self.overlay_screen.blockSignals(True); self.overlay_screen.clear(); self.overlay_screen.addItem(self.t('Automatic'),''); self.overlay_screen.setToolTip(self.t('Automatic (active game monitor)'))
        for screen in QApplication.screens():
            rect=screen.geometry(); self.overlay_screen.addItem(f'{screen.name()} · {rect.width()} × {rect.height()}',screen.name())
        if wanted and self.overlay_screen.findData(wanted)<0: self.overlay_screen.addItem(self.t('{name} (not connected)',name=wanted),wanted)
        self.overlay_screen.setCurrentIndex(max(0,self.overlay_screen.findData(wanted))); self.overlay_screen.blockSignals(False); self.overlay_screen_changed()

    def overlay_screen_changed(self,*args):
        if hasattr(self,'overlay_picker'):
            background=self.overlay_picker.game_background
            self.overlay_picker.screen=choose_screen(self.overlay_screen.currentData() or '',background[1] if background else self.screen().name() if self.screen() else '')
            self.overlay_picker.update()
            self.update_overlay_coordinates()

    def update_overlay_coordinates(self):
        if not hasattr(self,'overlay_coordinates'): return
        limits=self.overlay_picker.pixel_limits(); position=self.overlay_picker.pixel_position()
        for edit,bounds,value in zip(self.overlay_coordinates,limits,position):
            blocked=edit.blockSignals(True)
            edit.setRange(*bounds); edit.setValue(value); edit.blockSignals(blocked)

    def overlay_coordinate_changed(self,axis,value):
        position=list(self.overlay_picker.pixel_position()); position[axis]=int(value)
        self.overlay_picker.set_pixel_position(*position)

    def overlay_position_changed(self,*args):
        self.update_overlay_coordinates(); self.update_overlay()

    def overlay_size_changed(self,value):
        picker=self.overlay_picker; position=list(picker.pixel_position()); anchors=(picker.x_ratio,picker.y_ratio)
        picker.set_font_size(int(value)); limits=picker.pixel_limits()
        for axis,ratio in enumerate(anchors):
            if ratio in (0,1): position[axis]=limits[axis][int(ratio)]
        blocked=picker.blockSignals(True)
        picker.set_pixel_position(*position); picker.blockSignals(blocked)
        self.update_overlay_coordinates(); self.update_overlay()

    def choose_overlay_color(self,kind):
        color=QColorDialog.getColor(QColor(self.overlay_colors[kind]),self,self.t('Choose countdown color'),QColorDialog.DontUseNativeDialog)
        if color.isValid(): self.overlay_colors[kind]=color.name(); self.update_overlay_colors()

    def reset_overlay_colors(self):
        self.overlay_colors={'normal':'#ffffff','warning':'#ff5c65'}; self.update_overlay_colors()

    def update_overlay_colors(self,*args,refresh=True):
        for kind,item in self.overlay_color_buttons.items():
            color=self.overlay_colors[kind]; pix=QPixmap(18,18); pix.fill(QColor(color))
            item.setIcon(QIcon(pix)); item.setText(color.upper())
        self.overlay_picker.text_color=self.overlay_colors[self.overlay_preview_state.currentData() or 'warning']; self.overlay_picker.update()
        if refresh: self.update_overlay()

    def custom_messages_dialog(self):
        from .qt_notifications import messages_dialog
        messages_dialog(self)

    def game_countdown_dialog(self,gid=None):
        from .qt_personalization import game_overlay_dialog
        game_overlay_dialog(self,gid if isinstance(gid,str) else None)

    def overlay_values(self):
        return dict(overlay_enabled=self.overlay_enabled.isChecked(),overlay_replace_warning=self.overlay_warning.isChecked(),limit_popup_enabled=self.limit_popup.isChecked(),
                    overlay_opacity=self.overlay_opacity.value()/100,overlay_font_size=int(self.overlay_font_size.value()),overlay_color_normal=self.overlay_colors['normal'],overlay_color_warning=self.overlay_colors['warning'],overlay_x=self.overlay_picker.x_ratio,overlay_y=self.overlay_picker.y_ratio,overlay_screen=self.overlay_screen.currentData() or '')

    def preview_overlay(self):
        self._overlay_preview_settings=None; self._overlay_preview_game_id=None
        self.start_overlay_preview()

    def preview_game_overlay(self,settings):
        self._overlay_preview_settings=replace(quota_plan(settings),overlay_enabled=True)
        return self.start_overlay_preview(getattr(self,'_overlay_preview_game_id',None))

    def start_overlay_preview(self,gid=None):
        target=running_window(self.catalog,gid)
        self._overlay_preview_target=None
        self._overlay_preview_source_window=win32.u.GetForegroundWindow()
        self._overlay_preview_focus_until=0
        self._overlay_preview_delay_until=0
        if target:
            reason=overlay_reason(self.catalog,target.path,self.catalog.games.get(target.game_id))
            if reason:
                self._overlay_preview_until=0; self.hide_countdown()
                self.overlay_preview_status.setText(self.t(reason)); return self.t(reason)
            restoring=bool(win32.u.IsIconic(target.hwnd))
            if not target.activate():
                message=self.t('Could not activate the game. Switch to it and try Preview again.')
                self.overlay_preview_status.setText(message)
                self.set_status('Could not activate the game. Switch to it and try Preview again.')
                self._overlay_preview_until=0; self.hide_countdown(); return message
            self._overlay_preview_target=target
            self._overlay_preview_focus_until=time.monotonic()+1.5
            if restoring: self._overlay_preview_delay_until=time.monotonic()+.25
            message=self.t('Preview in game: {name}. Alt+Tab ends the preview.',name=self.catalog.games[target.game_id].name)
        else:
            message=self.t('No running game found. Showing the desktop preview.')
        self.overlay_preview_status.setText(message)
        self._overlay_preview_until=time.monotonic()+10; self.update_overlay()
        return message

    def rtss_dialog(self):
        window=QDialog(self); window.setWindowTitle(self.t('In-game countdown (RTSS)')); window.resize(660,360)
        layout=QVBoxLayout(window)
        automatic=QCheckBox(self.t('Use RTSS for games allowed by anti-cheat protection')); automatic.setChecked(self.settings.overlay_rtss_auto); layout.addWidget(automatic)
        guard=label(self.t('RTSS is off by default. Protected games also require separate per-game risk consent.')); guard.setWordWrap(True); layout.addWidget(guard)
        note=label(self.t('Use RTSS to show the countdown in supported fullscreen games. If it is unavailable, the app tries the desktop countdown.')); note.setWordWrap(True); layout.addWidget(note)
        restart=label(self.t('If a game was already running, save it and restart it once after enabling RTSS.'),'muted'); restart.setWordWrap(True); layout.addWidget(restart)
        status=label('' if rtss_installation() else self.t('Install RTSS 7.3.7 or newer first.'),'muted'); status.setWordWrap(True); layout.addWidget(status)
        def save():
            self.settings=replace(self.settings,overlay_rtss_auto=automatic.isChecked()).validate(); self.catalog.settings=self.settings
            self.store.save_settings(self.settings); self.rtss.hide(); self.rtss.failed_paths.clear()
            if not self.settings.overlay_rtss_auto: self.rtss.cancel_preparation()
            self._rtss_checked=0; self.prepare_rtss_profiles(); self.update_overlay()
            self.set_status('Settings saved.'); window.accept()
        layout.addStretch(); actions=QHBoxLayout(); actions.addStretch()
        actions.addWidget(button(self.t('Save'),save,'primary')); actions.addWidget(button(self.t('Cancel'),window.reject)); layout.addLayout(actions)
        window.exec()

    def rtss_available(self):
        now=time.monotonic()
        if not self._rtss_checked or now-self._rtss_checked>=30:
            self._rtss_available=bool(rtss_installation()); self._rtss_checked=now
        return self._rtss_available

    def refresh_rtss_consent(self,extra=()):
        if not self.overlay_consents.accepted and not self._rtss_consent_paths: return
        paths=list(self.catalog.rules)+list(extra)
        for values in self.art.executables.values(): paths.extend(values)
        groups={}; approved=set()
        catalog=Catalog(self.settings,tuple(self.catalog.games.values()),rules=self.catalog.rules)
        for path in dict.fromkeys(paths):
            if helper(path) or not (game:=catalog.resolve(path,fallback=False)): continue
            name=Path(path).name.casefold()
            groups.setdefault(name,[]).append((path,game))
        for group in groups.values():
            # RTSS profiles are shared by executable basename. Never let one
            # consent silently authorize another known game with the same name.
            if any(safety.reason(path,game) and not self.overlay_consents.allows(game) for path,game in group): continue
            approved.update(path for path,game in group if self.overlay_consents.allows(game) and not overlay_reason(self.catalog,path,game))
        self._rtss_consent_paths=frozenset(norm(path) for path in approved); self._rtss_consent_attempt=None
        self.rtss.authorize(approved)

    def prepare_rtss_profiles(self,keys=None):
        self.refresh_rtss_consent()
        if self.closed or not any_countdown(self.settings) or not self.settings.overlay_rtss_auto or not self.rtss_available(): return
        paths=list(self.catalog.rules)
        for key in self.art.executables if keys is None else keys: paths.extend(self.art.executables.get(key,()))
        allowed=[]; protected=[]
        for path in dict.fromkeys(paths):
            if helper(path) or not (game:=self.catalog.resolve(path,fallback=False)): continue
            if overlay_reason(self.catalog,path,game): protected.append(path)
            elif game_settings(self.settings,game.id).overlay_enabled: allowed.append(path)
        self.rtss.protect(protected); self.rtss.prepare(allowed)

    def hide_countdown(self):
        if self.overlay:
            if self.overlay.isVisible(): self._overlay_desktop_until=time.monotonic()+.2
            self.overlay.hide()
        if self._rtss_publishing or self._overlay_backend=='rtss' or self.rtss.identity: self.rtss.hide()
        self._rtss_publishing=False
        self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
        self.rtss_status.hide()

    def overlay_warning_visible(self):
        if (self.overlay_failed or self._overlay_backend=='none' or not self._overlay_identity
                or time.monotonic()-self._overlay_updated>1.5): return False
        current=win32.sample()
        if overlay_reason(self.catalog,current.path,self.catalog.resolve(current.path)): return False
        if (not current.interactive or current.identity!=self._overlay_identity
                or current.identity!=self.tracker.identity or not self.catalog.resolve(current.path)): return False
        if self._overlay_backend=='rtss': return True
        return bool(self.overlay and self.overlay.isVisible() and win32.desktop_overlay_available())

    def update_overlay(self):
        if self.closed: return
        preview=time.monotonic()<self._overlay_preview_until
        if not preview: self._overlay_preview_target=None
        settings=quota_plan(self.settings)
        if preview: settings=getattr(self,'_overlay_preview_settings',None) or replace(settings,**self.overlay_values())
        elif self.tracker.active: settings=game_settings(settings,self.tracker.active.id)
        # The one-second tracker starts this timer when gameplay begins. Keep
        # the 200 ms foreground/lock guard while a countdown can be visible.
        if not settings.overlay_enabled or (not preview and self.tracker.active is None):
            self.overlay_timer.stop()
            self.hide_countdown(); return
        if not self.overlay_timer.isActive(): self.overlay_timer.start()
        try:
            current=win32.sample()
            if not current.interactive:
                self._overlay_preview_until=0; self._overlay_preview_target=None
                self.hide_countdown(); return
            game=self.catalog.resolve(current.path)
            reason=overlay_reason(self.catalog,current.path,game)
            if reason:
                if norm(current.path) in self._rtss_consent_paths: self.refresh_rtss_consent((current.path,))
                self._overlay_preview_until=0; self._overlay_preview_target=None
                self.overlay_timer.stop(); self.hide_countdown()
                self.rtss_status.setText(self.t(reason)); self.rtss_status.show(); return
            if preview:
                target=self._overlay_preview_target
                if target:
                    if time.monotonic()<self._overlay_preview_delay_until:
                        self.hide_countdown(); return
                    game=self.catalog.resolve(target.path,fallback=False)
                    matches=target.matches(current)
                    if not game or game.id!=target.game_id or not matches:
                        # SW_RESTORE/activation can complete asynchronously.
                        # Wait only while the original settings window still
                        # owns focus; never refocus after the user switches away.
                        if (game and game.id==target.game_id and time.monotonic()<self._overlay_preview_focus_until
                                and win32.u.GetForegroundWindow()==self._overlay_preview_source_window and target.valid()):
                            self.hide_countdown(); return
                        self._overlay_preview_until=0; self._overlay_preview_target=None; self.hide_countdown(); return
                    self._overlay_preview_focus_until=0
                state=getattr(self,'_overlay_game_preview_state',None) if getattr(self,'_overlay_preview_settings',None) else None
                total=settings.warning_seconds if (state or self.overlay_preview_state.currentData())=='warning' else 0; remaining=settings.limit_seconds-total
                warning=total>=settings.warning_seconds
                automatic=foreground_screen_name() if target else self.screen().name() if self.screen() else ''
            else:
                settings=game_settings(quota_plan(self.settings,current.wall),self.tracker.active.id)
                active=self.tracker.active
                game=self.catalog.resolve(current.path)
                if not active or not game or game.id!=active.id or current.identity!=self.tracker.identity:
                    self.hide_countdown(); return
                totals=self.tracker.quota_totals(current.wall)
                elapsed=0
                previous=self.tracker.previous
                if previous and previous.identity==current.identity:
                    elapsed=current.awake-previous.awake
                    if not (0<elapsed<=1.5 and abs((current.wall-previous.wall).total_seconds()-elapsed)<1.5
                            and period_day(previous.wall,reset_clock(self.settings))==period_day(current.wall,reset_clock(self.settings))): elapsed=0
                budget=gameplay_budget(self.settings,current.wall,totals,active.id,elapsed)
                total=sum(totals.values())+elapsed
                remaining=budget.remaining; warning=budget.warning; automatic=foreground_screen_name()
            screen=choose_screen(settings.overlay_screen,automatic)
            attempted=(not preview or self._overlay_preview_target is not None) and settings.overlay_rtss_auto and self.rtss_available()
            if attempted:
                if self.overlay_consents.allows(game) and norm(current.path) not in self._rtss_consent_paths:
                    attempt=(norm(current.path),self.overlay_consents.accepted)
                    if self._rtss_consent_attempt!=attempt:
                        self.refresh_rtss_consent((current.path,)); self._rtss_consent_attempt=attempt
                geometry=screen.geometry(); ratio=screen.devicePixelRatio()
                text=rtss_countdown(remaining,warning,settings.overlay_opacity,settings.overlay_font_size,settings.overlay_color_normal,settings.overlay_color_warning)
                # IPC can publish before its acknowledgement reaches this tick.
                # Withdraw the desktop first; a failed receipt is not proof that
                # the RTSS copy has disappeared.
                fallback=self.rtss.fallback_for(current.identity)
                if self.overlay and self.overlay.isVisible() and not fallback:
                    self.overlay.hide()
                    self._overlay_desktop_until=time.monotonic()+.2
                    self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
                    # Let the compositor remove this window before starting IPC
                    # on the next existing guard tick; no extra timer or wait.
                    return
                if not fallback and time.monotonic()<self._overlay_desktop_until:
                    self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
                    return
                self._rtss_publishing=True
                healthy=self.rtss.present(current.path,current.identity,text,(settings.overlay_x,settings.overlay_y,round(geometry.width()*ratio),round(geometry.height()*ratio),settings.overlay_font_size))
                desktop_ready=self.rtss.desktop_ready
                self.rtss_status.setText(self.t('RTSS connected' if healthy else self.rtss.error or ('RTSS unavailable; using the desktop countdown.' if desktop_ready else 'RTSS connecting…'))); self.rtss_status.show()
                if healthy:
                    if self.overlay: self.overlay.hide()
                    self._overlay_backend='rtss'; self._overlay_identity='' if preview else current.identity; self._overlay_updated=time.monotonic(); self.overlay_failed=False
                    return
                if not desktop_ready:
                    if self.overlay: self.overlay.hide()
                    self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
                    return
            else:
                if self._rtss_publishing or self.rtss.identity: self.rtss.hide()
                self._rtss_publishing=False; self.rtss_status.hide()
                if not self.rtss.desktop_ready:
                    if self.overlay: self.overlay.hide()
                    self._overlay_backend='none'; self._overlay_identity=''; self._overlay_updated=0
                    return
            if not self.overlay: raise RuntimeError('Desktop countdown unavailable')
            self.overlay.present(remaining,total,settings,screen,preview,warning=warning)
            self._overlay_backend='desktop'; self._overlay_identity='' if preview else current.identity; self._overlay_updated=time.monotonic()
            self.overlay_failed=False
        except Exception:
            if not self.overlay_failed: log.exception('Countdown presentation failed')
            self.overlay_failed=True; self.hide_countdown(); self.set_status('Countdown unavailable; early warning popups remain active.')

    def browse_root(self):
        value=QFileDialog.getExistingDirectory(self,'Keep Improving',self.games_path.text())
        if value: self.games_path.setText(value)

    def save_settings(self):
        try:
            settings=replace(self.schedule_editor.settings(self.settings),games_root=self.games_path.text().strip(),
                steam_roots=[p.strip() for p in self.paths['steam'].text().split(';') if p.strip()],
                epic_manifest_dirs=[p.strip() for p in self.paths['epic'].text().split(';') if p.strip()],
                ubisoft_roots=[p.strip() for p in self.paths['ubisoft'].text().split(';') if p.strip()],
                hub_enabled=self.hub_enabled.isChecked(),
                check_updates=self.updates.automatic.isChecked(),**self.overlay_values(),**self.sound_values()).validate()
            self.tracker.flush(); self.store.save_settings(settings); self.settings=self.catalog.settings=settings
            self.schedule_editor.saved(settings)
            if not any_countdown(settings): self.rtss.cancel_preparation()
            self.tracker.unclassified.clear(); self.tracker.previous=None; self.service.configure(settings)
            self.art.roots=list(dict.fromkeys(self.art.roots+settings.steam_roots)); self.art.invalidate(); self.art.refresh_links(settings.games_root)
            self._art_queue=list(self.cards); self.call_later(10,self.load_next_art)
            self.settings_error.setText(''); self.last_rows=None; self.set_status('Settings saved.'); self._overlay_preview_until=0; self.update_overlay(); self.render()
            self.updates.saved()
            self.prepare_rtss_profiles()
            state,day,plan=bedtime_occurrence(settings,datetime.now())
            self.update_bedtime_banner(plan.bedtime_minimize and state=='bedtime')
        except (ValueError,OSError,SQLiteError) as exc:
            self.settings_error.setText(self.t('{day}: {error}',day=self.t(DAY_NAMES[exc.day]),error=self.t(str(exc.error))) if isinstance(exc,DayScheduleError) else self.t(str(exc)))

    def set_status(self,text,**values):
        from .background import DISCOVERY_PROBLEM, HUB_PROBLEM
        self.status_key=text; self.status_values=values; self.status_text=self.t(text,**values)
        if not text:
            self._status_until=0
            if hasattr(self,'status_label'): self.status_label.clear(); self.status_label.setToolTip(''); self.status_label.hide()
            return
        persistent=text in (DISCOVERY_PROBLEM,HUB_PROBLEM) or text.startswith(('Could not','An error','Countdown unavailable','Gaming Hub:'))
        self._status_until=float('inf') if persistent else time.monotonic()+6
        if hasattr(self,'status_label'):
            self.status_label.setText(self.status_text); self.status_label.setToolTip(self.status_text); self.status_label.show()
            deadline=self._status_until
            if not persistent: self.call_later(6100,lambda:self.status_label.hide() if self._status_until==deadline else None)

    def set_language(self,language):
        if not language or language==self.settings.language: return
        try:
            settings=replace(self.settings,language=language).validate(); self.store.save_settings(settings)
        except (OSError,ValueError,SQLiteError):
            blocked=self.language.blockSignals(True)
            self.language.setCurrentIndex(self.language.findData(self.settings.language)); self.language.blockSignals(blocked)
            self.set_status('Could not change language. Try again.'); return
        positions=[(area,area.horizontalScrollBar().value(),area.verticalScrollBar().value()) for area in self.findChildren(QAbstractScrollArea)]
        updates=self.updatesEnabled()
        self.setUpdatesEnabled(False)
        try:
            self.settings=self.catalog.settings=settings
            retranslate_widgets(self,language)
            blocked=self.language.blockSignals(True)
            self.language.setCurrentIndex(self.language.findData(language)); self.language.blockSignals(blocked)
            self.status_text=self.t(self.status_key,**self.status_values); self.status_label.setText(self.status_text)
            self.ring.setToolTip(self.t('Daily budget')+f': {quota_plan(self.settings).limit_seconds/60:g} '+self.t('min'))
            self.overlay_picker.setAccessibleName(self.t('Countdown position'))
            self.statistics.retranslate_report()
            self.focus_page.refresh(force=True)
            self.update_launch_button(); self.update_statistics_sync_status(); self.update_tray()
            self.updates.refresh()
            for card in self.cards.values(): card.update()
            QApplication.sendPostedEvents(None,QEvent.LayoutRequest)
            for area,x,y in positions:
                area.horizontalScrollBar().setValue(x); area.verticalScrollBar().setValue(y)
        finally: self.setUpdatesEnabled(updates)

    def switch_page(self,index):
        if index==3:
            self.pages.setCurrentIndex(0); self.clients_toggle.setChecked(True); self.set_clients_expanded(True); index=0
        self.pages.setCurrentIndex(index)
        for n,item in self.nav.items(): item.setChecked(n==index)
        if index==1: self.statistics.refresh(live=True)
        if index==4: self.focus_page.refresh(force=True)
        if index==0: self.render()

    def set_clients_expanded(self,expanded):
        self.clients_page.setVisible(bool(expanded)); self.clients_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        if expanded and not self._clients_loaded and not self._clients_busy:
            cached=self.store.client_cache()
            if cached is None: self.refresh_clients()
            else:
                self.clients=cached; self._clients_loaded=True; self.render_clients()

    def focus_awake(self): return win32.awake_seconds()

    def enable_browser_bridge(self):
        if self.browser_bridge is None:
            from .browser_activity import BrowserBridge
            self.browser_bridge=BrowserBridge(self.store)
            self.update_focus_policy()
        return self.browser_bridge

    def copy_browser_pairing(self,code):
        clipboard=QApplication.clipboard(); clipboard.setText(code)
        self.call_later(60000,lambda: clipboard.clear() if clipboard.text()==code else None)

    def update_focus_policy(self):
        if self.browser_bridge: self.browser_bridge.update(self.focus.policy())

    def focus_tick(self,current):
        import ntpath
        website=self.browser_bridge.website(current.path) if self.browser_bridge else ''
        self.focus.tick(current,website)
        self.update_focus_policy()
        focus=self.focus
        if focus.notice and self._focus_notice!=focus.notice:
            self._focus_notice=focus.notice
            if self.settings.notification_sound!='silent': play_notification(self.settings)
        if not focus.notice: self._focus_notice=''
        if focus.restricting and current.interactive and current.path and current.identity:
            key=app_key(current.path); filename=ntpath.basename(key)
            own=current.identity.startswith(str(os.getpid())+':')
            blocked=focus.settings.app_blocked(key)
            if blocked and not own and filename not in SHELLS:
                if self.minimization_allowed(current.path,current.identity):
                    win32.minimize_game(current.path,current.identity,consented=True)
                elif self.isVisible() and not self.isMinimized() and self.pages.currentIndex()==4:
                    self.focus_page.notice.setText(self.t('This protected game requires the existing minimization permission.'))
        if self.isVisible() and not self.isMinimized() and self.pages.currentIndex()==4:
            self.focus_page.refresh()
    def settings_dialog(self): self.switch_page(2); self.show()
    def show(self):
        if self.closed: return
        self.showNormal(); hwnd=dark_window(self)
        # Windows STARTUPINFO may hide the first Qt show. Explicitly restore the
        # native window as well, including launches through hidden startup links.
        win32.u.ShowWindow(hwnd,9)
        self.raise_(); self.activateWindow(); win32.u.SetForegroundWindow(hwnd)
    def open_games(self): self.switch_page(0); self.show()
    def restriction_notice(self): self.open_games()

    def game_limits_dialog(self,gid=None):
        from .qt_game_limits import game_limits_dialog
        game_limits_dialog(self,gid if isinstance(gid,str) else None)
    def closeEvent(self,event):
        if self.closed: event.accept()
        else: event.ignore(); self.hide()
    def showEvent(self,event):
        super().showEvent(event)
        if not self.closed:
            if self.pages.currentIndex()==1: self.statistics.refresh(live=True)
            self.render()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange and self.isVisible() and not self.isMinimized() and not self.closed:
            if self.pages.currentIndex()==1: self.statistics.refresh(live=True)
            self.render()
    def selected(self): return self.catalog.games.get(self.selected_id) or next((g for g in self.store.games() if g.id==self.selected_id),None)
    def refresh_view(self,*args):
        if not hasattr(self,'pages') or not hasattr(self,'statistics'): return
        self.show_hidden=self.hidden_toggle.isChecked(); self.last_rows=None; self.render()
    def refresh_game_dialogs(self):
        for window in tuple(getattr(self,'_dialogs',())):
            refresh=getattr(window,'_refresh_games',None)
            if refresh: refresh()
    def select_game(self,gid): self.selected_id=gid; self.update_launch_button()
    def play_game(self,gid): self.select_game(gid); self.launch_selected()

    def update_launch_button(self):
        for gid,card in self.cards.items():
            restricted=self.launch_restricted(card.game)
            card.set_state(card.seconds,gid==self.selected_id,not self.launching and not restricted)
            card.play.setToolTip(self.t('Restricted today' if restricted else 'Starting…' if self.launching==gid else '▶ Play'))

    def game_menu(self,gid):
        card=self.cards.get(gid)
        if not card: return
        self.select_game(gid)
        game=self.selected()
        if not game: return
        menu=QMenu(self)
        tracking='Exclude from tracking' if self.catalog.enabled(game) else 'Track game'
        visibility='Show in library' if game.id in self.hidden_ids else 'Hide from library'
        for text,callback in [('Open game folder',self.open_game_folder),('Assign EXE',self.assign_exe),('EXE rules',self.rules_dialog),
                              ('Per-game limit…',lambda:self.game_limits_dialog(game.id)),
                              ('Per-game countdown…',lambda:self.game_countdown_dialog(game.id)),(tracking,self.toggle_game),(visibility,self.toggle_hidden)]: menu.addAction(self.t(text),callback)
        menu.addSeparator(); menu.addAction(self.t('Uninstall game…'),self.uninstall_game)
        menu.exec(card.more.mapToGlobal(QPoint(0,card.more.height())))

    def _dialog(self,title,width=620):
        window=QDialog(self); window.setObjectName('Surface'); window.setWindowTitle(title); window.setAttribute(Qt.WA_DeleteOnClose); window.resize(width,300)
        self._dialogs.append(window)
        window.finished.connect(lambda result:self._dialogs.remove(window) if window in self._dialogs else None)
        window.destroyed.connect(lambda obj=None:self._dialogs.remove(window) if window in self._dialogs else None)
        return window

    def message(self,text):
        window=self._dialog('Keep Improving',570); layout=QVBoxLayout(window); layout.setContentsMargins(28,26,28,25); layout.setSpacing(20)
        layout.addWidget(label('Keep Improving','section')); message=label(self.t(text)); message.setWordWrap(True); layout.addWidget(message,1)
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
        note=label(self.t('Use the game’s menu in the library to enable or exclude its play-time tracking.'),'muted'); note.setWordWrap(True); box.addWidget(note)
        table=QTableWidget(0,2); table.setHorizontalHeaderLabels([self.t('Application path'),self.t('Assignment')]); table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
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
        mode=self.notification_mode()
        if mode=='defer': return False
        if mode=='audio': return self.audio_notification(alert)
        passive=mode=='passive'
        window=AlertDialog(self,passive); self.popup_window=window; self.popup_day=alert.day; self.popup_kind=alert.kind
        bedtime=alert.kind=='bedtime'; caption=self.t('Bedtime reminder' if bedtime else 'Game time alert')
        screen=QApplication.primaryScreen().availableGeometry()
        width=min(620,max(420,screen.width()-60))
        window.setWindowTitle(caption)
        layout=QVBoxLayout(window); layout.setContentsMargins(28,24,28,24); layout.setSpacing(20)
        header=QHBoxLayout(); header.setSpacing(16)
        badge=label(); badge.setFixedSize(48,48); badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet('background:#243c35; border-radius:14px;')
        badge.setPixmap(glyph('moon' if bedtime else 'bell',ACCENT,26).pixmap(26,26)); header.addWidget(badge)
        title=label(self.t('Get ready for bed' if bedtime else 'Time to stop playing' if alert.kind in ('limit','session') else 'Game time reminder'),'title')
        title.setStyleSheet('font-size:24px;'); title.setWordWrap(True); header.addWidget(title,1); layout.addLayout(header)
        message=panel('ReminderMessage'); message.setStyleSheet('QFrame#ReminderMessage { background:#192328; border:1px solid #2c3a40; border-radius:12px; }')
        message_layout=QVBoxLayout(message); message_layout.setContentsMargins(18,16,18,16)
        text=label(alert.text); text.setWordWrap(True); text.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        text.setStyleSheet('font-size:15px; color:#dce8e5;')
        text.setTextInteractionFlags(Qt.TextSelectableByMouse); text.ensurePolished()
        text_height=max(30,text.heightForWidth(width-106)); text.setMinimumHeight(text_height)
        body=QScrollArea(); body.setWidgetResizable(True); body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); body.setWidget(text)
        body.setStyleSheet('QScrollArea {background:transparent; border:0;} QScrollArea > QWidget {background:transparent;}')
        message_layout.addWidget(body); layout.addWidget(message,1)
        title.ensurePolished(); header_height=max(48,title.heightForWidth(width-120))
        window.setFixedSize(width,min(max(260,172+header_height+min(260,text_height)),max(260,screen.height()-60)))
        acknowledge=button(self.t(alert.button),window.accept,'primary'); acknowledge.setDefault(True); layout.addWidget(acknowledge,0,Qt.AlignRight)
        window.finished.connect(lambda result:self._popup_finished(window))
        window.move(screen.center()-window.rect().center())
        try:
            window.show(); hwnd=dark_window(window)
            foreground=win32.present_notification(hwnd,activate=False) if passive else win32.present_notification(hwnd)
            if not passive: window.raise_(); window.activateWindow()
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
            if not window.isVisible() or not win32.u.IsWindowVisible(hwnd): raise RuntimeError('Notification window did not become visible')
        except Exception:
            log.exception('Qt notification presentation failed; will retry'); self.dismiss_popup(); return False
        log.info('Notification presented: kind=%s day=%s main_visible=%s foreground=%s',alert.kind,alert.day,self.isVisible(),foreground)
        play_notification(self.settings)
        return True

    def _popup_finished(self,window):
        if self.popup_window is window: self.popup_window=self.popup_day=None
    def dismiss_popup(self):
        if self.popup_window: self.popup_window.close(); self.popup_window=self.popup_day=None

    def render_tick(self):
        # Tracking, alerts, Hub discovery and cloud sync continue in the tray.
        # Refresh widgets on return instead of reading/repainting a hidden UI.
        if self.isVisible() and not self.isMinimized(): self.render()
        else:
            self.sync_hub()
            self.update_tray()

    def update_tray(self):
        now=datetime.now().astimezone(); total=sum(self.tracker.totals(now.date().isoformat()).values())
        budget=remaining_budget(self.settings,now,sum(self.tracker.quota_totals(now).values()))
        tip=self.t('Keep Improving\nToday: {total} · remaining: {remaining}\nLeft click: open · right click: menu',total=duration(total),remaining=duration(budget.remaining))
        if self.updates.available: tip=self.t('Update {version} available',version=self.updates.available.version)+'\n'+tip
        self.tray.update(tip)

    def render(self):
        self.sync_hub()
        now=datetime.now().astimezone(); day=now.date().isoformat(); totals=self.tracker.totals(day); total=sum(totals.values())
        plan=quota_plan(self.settings,now)
        quota_totals=self.tracker.quota_totals(now)
        used=sum(quota_totals.values())
        budget=remaining_budget(self.settings,now,used)
        self.total_label.setText(duration(total)); self.remaining_label.setText(duration(budget.remaining))
        tomorrow=period_day(now,reset_clock(self.settings))+timedelta(days=1)
        renewal=reset_at(tomorrow,reset_clock(self.settings)[tomorrow.weekday()],now)
        self.remaining_label.setToolTip(self.t('Unused daily budget: {remaining}',remaining=duration(budget.quota_remaining))+'\n'+self.t('Next budget reset: {time}',time=renewal.strftime('%Y-%m-%d %H:%M')))
        self.remaining_reason.setText((self.t('Bedtime has started') if budget.bedtime.timestamp()<=now.timestamp() else self.t('Until bedtime at {time}',time=budget.bedtime.strftime('%H:%M'))) if budget.bedtime else '')
        self.remaining_reason.setVisible(budget.bedtime is not None)
        self.ring.set_ratio(used/plan.limit_seconds); self.ring.setToolTip(self.t('Daily budget')+f': {plan.limit_seconds/60:g} '+self.t('min'))
        self.active_label.setText(self.tracker.active.name if self.tracker.active else ''); self.active_label.setVisible(self.tracker.active is not None)
        self.active_label.setToolTip(self.t('Active game: {name}',name=self.tracker.active.name) if self.tracker.active else '')
        games={g.id:g for g in self.store.games()}; games.update(self.catalog.games); self.hidden_ids=self.store.hidden_ids()
        source=self.source_filter.currentData()
        if self._restore_source is not None: source=self._restore_source; self._restore_source=None
        sources=[(self.t('All sources'),None)]+[(self.source_name(value),value) for value in sorted({g.source for g in games.values()})]
        self.source_filter.blockSignals(True)
        if [(self.source_filter.itemText(i),self.source_filter.itemData(i)) for i in range(self.source_filter.count())]!=sources:
            self.source_filter.clear()
            for text,value in sources: self.source_filter.addItem(text,value)
        self.source_filter.setCurrentIndex(max(0,self.source_filter.findData(source))); self.source_filter.blockSignals(False); source=self.source_filter.currentData()
        query=self.search.text().strip().casefold()
        local_sources={source:' '.join(tr(key,language) for language in LANGUAGES.values()) for source,key in (('Kézi','Manual'),('Games','Games folder'))}
        filtered=[g for g in games.values() if (self.hidden_toggle.isChecked() or g.id not in self.hidden_ids) and (g.installed or g.id in totals)
                  and (not source or g.source==source) and (not query or query in (g.name+' '+g.source+' '+local_sources.get(g.source,'')).casefold())]
        filtered.sort(key=lambda g:(-totals.get(g.id,0) if self.sort.currentData()=='today' else 0,g.name.casefold(),g.id))
        fingerprint=tuple((g.id,g.name,g.source,g.root,g.metadata,g.installed) for g in filtered)
        if self.last_rows!=fingerprint:
            self.art.refresh_links(self.settings.games_root)
            previous=self.cards; self.cards={}; artwork=[]
            duplicates=Counter(g.name.casefold() for g in filtered)
            for game in filtered:
                card=previous.get(game.id)
                if card is None:
                    card=GameCard(game,self.t)
                    cached=self.art.cache.get(self.art.key(game))
                    if cached is not None: card.art=cached
                    else: artwork.append(game.id)
                    card.selected.connect(self.select_game); card.launched.connect(self.play_game)
                    card.options_requested.connect(self.game_menu)
                else:
                    if self.art.key(card.game)!=self.art.key(game) or self.art.key(game) not in self.art.cache: artwork.append(game.id)
                    card.set_game(game)
                show_source=duplicates[game.name.casefold()]>1
                if card.show_source!=show_source: card.show_source=show_source; card.update()
                self.cards[game.id]=card
            self.grid.set_cards(list(self.cards.values())); self.last_rows=fingerprint
            self.empty.setVisible(not filtered)
            if self.selected_id not in self.cards: self.selected_id=None
            self._art_queue=list(dict.fromkeys([gid for gid in getattr(self,'_art_queue',[]) if gid in self.cards]+artwork))
            if self._art_queue: self.call_later(10,self.load_next_art)
        shared_restricted=self.restriction_reached(now)
        active=self.tracker.active or self.selected()
        own_restricted=active and self.restriction_reached(now,active)
        self.restriction_banner.setVisible(bool(shared_restricted or own_restricted))
        self.restriction_label.setText(self.t('Play restriction active · {minutes:g} min',minutes=plan.restriction_seconds/60) if shared_restricted else
            self.t('{name}: game limit reached',name=active.name) if own_restricted else '')
        card_height=244
        for gid,card in self.cards.items():
            card.set_game_remaining(game_remaining(self.settings,gid,quota_totals.get(gid,0)) if self.catalog.enabled(card.game) else None)
            card.set_state(totals.get(gid,0),gid==self.selected_id,not self.launching and not self.launch_restricted(card.game))
            card_height=max(card_height,card.required_height())
        self.grid.set_card_height(card_height)
        self.update_launch_button()
        self.update_tray()
        if self.isVisible() and not self.isMinimized() and self.pages.currentIndex()==1 and time.monotonic()-self.statistics.last_refresh>=10: self.statistics.refresh(live=True)

    def load_next_art(self):
        if self.closed or not self._art_queue: return
        gid=self._art_queue.pop(0); card=self.cards.get(gid)
        if card:
            try:
                art=self.art.artwork(card.game,self.catalog.rules)
                if self.art.key(card.game) not in self.art.pending or not any(card.art): card.art=art
            except (OSError,ValueError,TypeError,AttributeError):
                log.warning('Local game artwork unavailable: %s',gid,exc_info=True)
            card.update()
        self.update_assets_interval()
        if self._art_queue: self.call_later(15,self.load_next_art)
        else: self.update_launch_button()

    def close(self):
        if self.closed: return
        self.closed=True
        self.statistics_event_timer.stop()
        self.focus.close()
        if self.browser_bridge: self.browser_bridge.close()
        self.statistics_sync.close(); self.account_auth.close()
        self.updates.close()
        for timer in list(self._timers): timer.stop(); timer.deleteLater()
        self._timers.clear(); self.dismiss_popup()
        self.overlay_timer.stop()
        self.game_snapshots.close()
        self.rtss.close()
        self.assets_timer.stop(); self.art.close()
        if self.client_worker: self.client_worker.close()
        if self.overlay: self.overlay.close(); self.overlay.deleteLater()
        for signal in (QApplication.instance().screenAdded,QApplication.instance().screenRemoved):
            try: signal.disconnect(self.refresh_overlay_screens)
            except (RuntimeError,TypeError): pass
        for window in list(self._dialogs): window.close()
        self.tracker.close(); self.service.close(); self.hub.close()
        if self.launcher: self.launcher.close()
        self.tray.close(); QMainWindow.close(self)
        self.shutdown.emit()

def run(store,data_dir,background=False):
    qapp=setup_application(); window=App(store,data_dir,background,updates=True)
    # Closing the window hides it; only the controller's Exit/stop request ends exec.
    window.shutdown.connect(qapp.quit)
    try: return qapp.exec()
    finally:
        window.shutdown.disconnect(qapp.quit)
        window.close()
