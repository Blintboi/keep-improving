"""Historical statistics, using the same recorded-time model as the monitor."""
from datetime import date,timedelta
from collections import Counter
from dataclasses import replace
from pathlib import Path
from sqlite3 import Error as SQLiteError
import hashlib
import time
from PySide6.QtCore import Qt,QDate,QLocale,QEvent,QTimer,QPoint,QRect,QSize
from PySide6.QtGui import QColor,QIcon,QPainter,QPixmap,QTextCharFormat,QPalette
from PySide6.QtWidgets import QWidget,QScrollArea,QVBoxLayout,QHBoxLayout,QGridLayout,QHeaderView,QAbstractItemView,QDateEdit,QCalendarWidget,QToolButton,QListWidget,QListWidgetItem,QListView
from .statistics import date_range,summarize
from .qt_widgets import label,button,panel,duration,DailyChart
from .qt_widgets import NoWheelComboBox as QComboBox
from .statistics_sync import computer_name
from .qt_translation import UiText,QCheckBox,QLineEdit,QTableWidget,QTableWidgetItem

def rename_computer_dialog(app):
    from .qt_ui import dark_window
    t=app.t; window=app._dialog(t('Rename computer'),520)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(14)
    group=app.settings.statistics_sync_group
    names={'local':app.settings.statistics_device_name or computer_name()}
    aliases=app.statistics_data.device_aliases(group)
    names.update({identity:aliases.get(identity,value) for identity,value,started in app.statistics_data.devices(group)})
    layout.addWidget(label(t('Computer'),'muted'))
    devices=QComboBox(); devices.setAccessibleName(t('Computer'))
    for identity,value in names.items():
        devices.addItem(app.statistics.colors.icon(identity,'computer'),app.statistics.computer_names.get(identity,value),identity)
    devices.setCurrentIndex(max(0,devices.findData(app.statistics.scope))); layout.addWidget(devices)
    layout.addWidget(label(t('Computer name'),'muted'))
    name=QLineEdit(); name.setMaxLength(80)
    name.setAccessibleName(t('Computer name')); layout.addWidget(name)
    note=label('','muted')
    note.setWordWrap(True); layout.addWidget(note)
    error=label('','danger'); error.setWordWrap(True); error.hide(); layout.addWidget(error)
    def choose_device():
        name.setText(names[devices.currentData()]); name.selectAll(); error.hide()
        note.setText(t('This name appears in statistics. Linked computers receive it at the next sync.' if devices.currentData()=='local' else
                       'This name is saved on this computer for your statistics and stays after synchronization.'))
    devices.currentIndexChanged.connect(choose_device); choose_device()
    def save():
        value=name.text().strip()
        if not value:
            error.setText(t('Enter a computer name.')); error.show(); name.setFocus(); return
        try:
            identity=devices.currentData(); changed=False
            if identity=='local':
                settings=replace(app.settings,statistics_device_name=value).validate()
                if settings!=app.settings:
                    app.store.save_settings(settings); app.settings=app.catalog.settings=settings
                    changed=True; app.schedule_statistics_event()
            else:
                if group!=app.settings.statistics_sync_group: raise ValueError('Connection changed.')
                changed=app.statistics_data.set_device_alias(group,identity,value)
            if changed:
                app.statistics.refresh_devices(); app.statistics.update_chart(); app.statistics.show_breakdown()
            window.accept()
        except (OSError,ValueError,SQLiteError):
            error.setText(t('Could not save computer name. Try again.')); error.show()
    actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(t('Cancel'),window.reject))
    save_button=button(t('Save'),save,'primary'); save_button.setDefault(True); actions.addWidget(save_button)
    layout.addLayout(actions); window.show(); dark_window(window); name.setFocus(); name.selectAll()

class StatisticsColors:
    """Reuse series colors across refreshes, filters and translated page rebuilds."""
    palette=('#73c7ff','#f0ba68','#b9a1ff','#7de5bf','#f58fa7','#74d8db',
             '#d7dc7a','#f4a67c','#9faef4','#e4a1e0','#a1d99b','#dcc6a1')
    def __init__(self): self.colors={'game':{},'computer':{}}; self.icons={}; self._lab_cache={}

    def lab(self,color):
        if color in self._lab_cache: return self._lab_cache[color]
        rgb=[int(color[index:index+2],16)/255 for index in (1,3,5)]
        rgb=[value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4 for value in rgb]
        x=(.4124564*rgb[0]+.3575761*rgb[1]+.1804375*rgb[2])/.95047
        y=.2126729*rgb[0]+.7151522*rgb[1]+.0721750*rgb[2]
        z=(.0193339*rgb[0]+.1191920*rgb[1]+.9503041*rgb[2])/1.08883
        def f(value): return value**(1/3) if value>.008856 else 7.787*value+16/116
        x,y,z=map(f,(x,y,z)); result=(116*y-16,500*(x-y),200*(y-z))
        self._lab_cache[color]=result; return result

    def difference(self,one,two):
        return sum((a-b)**2 for a,b in zip(self.lab(one),self.lab(two)))

    def color(self,key,kind):
        colors=self.colors[kind]
        if key not in colors:
            number=int.from_bytes(hashlib.sha256((kind+':'+key).encode()).digest()[:4],'big')
            used=set(colors.values())
            candidates=self.palette[number%len(self.palette):]+self.palette[:number%len(self.palette)]
            available=[color for color in candidates if color not in used]
            if not available and len(colors)<32:
                available=[QColor.fromHslF(((number+i*50)%3600)/3600,.72,light).name()
                           for light in (.68,.56) for i in range(72)]
                available=[color for color in available if color not in used]
            if available:
                colors[key]=max(available,key=lambda color:min((self.difference(color,other) for other in used),default=float('inf')))
            else:
                colors[key]=next((candidate for i in range(3600)
                                  if (candidate:=QColor.fromHslF(((number+i*1373)%3600)/3600,.66,.72).name()) not in used),
                                 QColor.fromHslF((number%3600)/3600,.66,.72).name())
        return colors[key]
    def icon(self,key,kind):
        color=self.color(key,kind); cache=(color,kind)
        if cache not in self.icons:
            pixmap=QPixmap(64,64); pixmap.setDevicePixelRatio(4); pixmap.fill(Qt.transparent)
            painter=QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color))
            if kind=='game': painter.drawEllipse(2,2,12,12)
            else: painter.drawRoundedRect(2,2,12,12,2,2)
            painter.end(); self.icons[cache]=QIcon(pixmap)
        return self.icons[cache]


class ComputerLegend(QListWidget):
    """Compact, wrapping list of the computers represented by chart side colors."""
    cell_width=240
    cell_height=34
    def __init__(self):
        super().__init__()
        self.setFlow(QListView.LeftToRight); self.setWrapping(True); self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static); self.setGridSize(QSize(self.cell_width,self.cell_height))
        self.setSelectionMode(QAbstractItemView.NoSelection); self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet('QListWidget {background:transparent; border:none;} QListWidget::item {padding:4px 6px; margin:0; border:none;}')
        self._identities=()

    def resizeEvent(self,event):
        super().resizeEvent(event); self.fit_items()

    def fit_items(self):
        columns=max(1,self.viewport().width()//self.cell_width)
        height=((self.count()+columns-1)//columns)*self.cell_height+2*self.frameWidth()
        if self.height()!=height: self.setFixedHeight(height)

    def set_computers(self,identities,names,colors):
        identities=tuple(identities)
        if identities!=self._identities:
            self.clear()
            for identity in identities:
                item=QListWidgetItem(); item.setData(Qt.UserRole,identity); self.addItem(item)
            self._identities=identities
        for index,identity in enumerate(identities):
            item=self.item(index); name=names[identity]
            if item.text()!=name: item.setText(name); item.setToolTip(name)
            color=colors.color(identity,'computer')
            if item.data(Qt.UserRole+1)!=color:
                item.setIcon(colors.icon(identity,'computer')); item.setData(Qt.UserRole+1,color)
        self.fit_items(); self.setVisible(bool(identities))


class StatisticsDate(QDateEdit):
    """Themed calendar input with explicit start/end drafts and bounded popups."""
    def __init__(self,value):
        super().__init__(QDate.fromString(value,Qt.ISODate))
        self.setDisplayFormat('yyyy-MM-dd'); self.setCalendarPopup(True)
        calendar=QCalendarWidget(self)
        calendar.setMinimumSize(330,300)
        calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        calendar.setFirstDayOfWeek(Qt.Monday)
        calendar.setGridVisible(False)
        palette=calendar.palette()
        for role,color in ((QPalette.Window,'#192126'),(QPalette.Base,'#192126'),
                           (QPalette.AlternateBase,'#192126'),(QPalette.Button,'#20312e'),
                           (QPalette.Text,'#edf4f2'),(QPalette.WindowText,'#edf4f2'),
                           (QPalette.ButtonText,'#d4eee5'),(QPalette.Highlight,'#315e4e'),
                           (QPalette.HighlightedText,'#c4f7e3')):
            palette.setColor(role,QColor(color))
        calendar.setPalette(palette)
        calendar.setStyleSheet('''
            QCalendarWidget { background:#192126; color:#edf4f2; border:1px solid #3c504e; }
            QCalendarWidget QWidget#qt_calendar_navigationbar { background:#20312e; border:none; }
            QCalendarWidget QToolButton { background:transparent; color:#d4eee5; border:none; border-radius:7px; padding:5px 8px; font-weight:600; }
            QCalendarWidget QToolButton:hover { background:#315343; }
            QCalendarWidget QToolButton#qt_calendar_prevmonth, QCalendarWidget QToolButton#qt_calendar_nextmonth { min-width:30px; font-size:22px; padding:0; }
            QCalendarWidget QMenu { background:#1c282d; color:#edf4f2; border:1px solid #3c504e; selection-background-color:#315343; }
            QCalendarWidget QSpinBox { background:#182126; color:#edf4f2; border:1px solid #527b68; border-radius:5px; selection-background-color:#315e4e; }
            QCalendarWidget QAbstractItemView { background:#192126; color:#edf4f2; selection-background-color:#315e4e; selection-color:#c4f7e3; outline:none; border:none; }
            QCalendarWidget QTableView { background:#192126; alternate-background-color:#192126; gridline-color:#192126; }
            QCalendarWidget QAbstractItemView:enabled { color:#edf4f2; }
            QCalendarWidget QAbstractItemView:disabled { color:#657779; }
        ''')
        weekend=QTextCharFormat(); weekend.setForeground(QColor('#b8c9c5'))
        calendar.setWeekdayTextFormat(Qt.Saturday,weekend); calendar.setWeekdayTextFormat(Qt.Sunday,weekend)
        for name,text in (('qt_calendar_prevmonth','‹'),('qt_calendar_nextmonth','›')):
            control=calendar.findChild(QToolButton,name)
            if control:
                control.setArrowType(Qt.NoArrow); control.setIcon(QIcon()); control.setText(text)
        self.setCalendarWidget(calendar); calendar.installEventFilter(self)
        self.setFocusPolicy(Qt.StrongFocus)

    def setLocale(self,locale):
        super().setLocale(locale)
        if self.calendarPopup(): self.calendarWidget().setLocale(locale)

    def eventFilter(self,watched,event):
        if watched is self.calendarWidget() and event.type()==QEvent.Show:
            popup=watched.window()
            if popup is not self.window():
                popup.setStyleSheet('QCalendarPopup { background:#192126; border:1px solid #3c504e; }')
                QTimer.singleShot(0,self.position_calendar)
        return super().eventFilter(watched,event)

    def position_calendar(self):
        popup=self.calendarWidget().window(); owner=self.window()
        if popup is owner or not popup.isVisible(): return
        bounds=QRect(owner.mapToGlobal(QPoint()),owner.size())
        if self.screen(): bounds=bounds.intersected(self.screen().availableGeometry())
        if bounds.isEmpty(): return
        anchor=self.mapToGlobal(QPoint()); width,height=popup.width(),popup.height()
        below=bounds.bottom()-(anchor.y()+self.height())+1
        above=anchor.y()-bounds.top()
        y=anchor.y()+self.height() if height<=below or below>=above else anchor.y()-height
        x=max(bounds.left(),min(anchor.x(),bounds.right()-width+1))
        popup.move(x,max(bounds.top(),min(y,bounds.bottom()-height+1)))

    def setText(self,value):
        parsed=QDate.fromString(value,Qt.ISODate)
        if parsed.isValid(): self.setDate(parsed)
        else: self.lineEdit().setText(value)

    def wheelEvent(self,event): event.ignore()

class StatisticsPage(QWidget):
    def __init__(self,app):
        super().__init__(); self.app=app; self.report=None; self.selected_day=None
        self.last_refresh=0; self.updating=False; self.scope='all'; self._game_scope='all'; self._category='all'
        if not hasattr(app,'statistics_colors'): app.statistics_colors=StatisticsColors()
        self.colors=app.statistics_colors; t=app.t
        self.setStyleSheet("""
            QDateEdit {background:#182126; color:#edf4f2; border:1px solid #2e3b42; border-radius:10px; padding:9px 10px;}
            QDateEdit:focus {border-color:#7de5bf;}
            QDateEdit::drop-down {border:none; width:28px;}
            QDateEdit::down-arrow {image:url("%s"); width:16px; height:16px;}
        """ % (Path(__file__).with_name('icons').joinpath('chevron.svg').as_posix(),))
        shell=QVBoxLayout(self); shell.setContentsMargins(0,0,0,0)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); shell.addWidget(self.scroll)
        content=QWidget(); self.scroll.setWidget(content)
        layout=QVBoxLayout(content); layout.setContentsMargins(28,24,28,24); layout.setSpacing(16)
        header=QHBoxLayout(); heading=QVBoxLayout(); heading.setSpacing(5)
        heading.addWidget(label(t('Statistics'),'title'))
        heading.addWidget(label(t('See where your time goes.'),'muted')); header.addLayout(heading,1)
        self.computers_button=button(t('Computers & sync'),self.toggle_computers,'quiet')
        self.computers_button.setCheckable(True); header.addWidget(self.computers_button)
        header.addWidget(button(t('What is measured?'),self.explain,'quiet')); layout.addLayout(header)
        self.computer_panel=panel(); computer_box=QVBoxLayout(self.computer_panel); computer_box.setContentsMargins(18,14,18,14)
        self.sync_label=label(app.statistics_sync_status(),'muted'); self.sync_label.setWordWrap(True); computer_box.addWidget(self.sync_label)
        actions=QHBoxLayout(); actions.addWidget(button(t('Link computers'),app.statistics_sync_dialog))
        self.rename_computer=button(t('Rename computer'),lambda:rename_computer_dialog(app)); actions.addWidget(self.rename_computer)
        self.sync_now=button(t('Sync now'),app.request_statistics_sync); self.sync_now.setEnabled(app.settings.statistics_sync_enabled)
        actions.addWidget(self.sync_now); actions.addStretch(); computer_box.addLayout(actions)
        layout.addWidget(self.computer_panel); self.computer_panel.hide()
        filters=panel(); filter_box=QVBoxLayout(filters); filter_box.setContentsMargins(18,15,18,15); filter_box.setSpacing(10)
        grid=QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(6)
        self.category=QComboBox(); self.category.setAccessibleName(t('Show activity'))
        for name,key in (('Games','games'),('Applications','apps'),('Websites','websites'),('Everything','all')): self.category.addItem(t(name),key)
        self.category.setCurrentIndex(self.category.findData('all'))
        self.period=QComboBox(); self.period.setAccessibleName(t('Period'))
        for name,key in (('Today','today'),('Yesterday','yesterday'),('Last 7 days','week'),('Last 30 days','month'),('This month','calendar'),('Custom dates…','custom')):
            self.period.addItem(t(name),key)
        self.period.setCurrentIndex(self.period.findData('week'))
        self.devices=QComboBox(); self.devices.setAccessibleName(t('Computer'))
        for column,(name,widget) in enumerate((('Show activity',self.category),('Period',self.period),('Computer',self.devices))):
            grid.addWidget(label(t(name),'muted'),0,column); grid.addWidget(widget,1,column); grid.setColumnStretch(column,1)
        filter_box.addLayout(grid)
        self.custom_range=QWidget(); dates=QHBoxLayout(self.custom_range); dates.setContentsMargins(0,4,0,0); dates.setSpacing(10)
        self.start=StatisticsDate((date.today()-timedelta(days=6)).isoformat()); self.end=StatisticsDate(date.today().isoformat())
        self._range=(self.start.text(),self.end.text())
        self._relative_day=date.today()
        for name,widget in (('From',self.start),('To',self.end)):
            widget.setAccessibleName(t(name)); widget.setMinimumWidth(140)
            widget.setLocale(QLocale('hu_HU' if app.settings.language=='hu' else 'en_GB'))
            dates.addWidget(label(t(name),'muted')); dates.addWidget(widget)
            widget.lineEdit().returnPressed.connect(self.apply_dates)
        dates.addWidget(button(t('Show period'),self.apply_dates)); dates.addStretch()
        filter_box.addWidget(self.custom_range); self.custom_range.hide()
        self.activity_note=label('','muted'); self.activity_note.setWordWrap(True); filter_box.addWidget(self.activity_note); self.activity_note.hide()
        self.tracking=QCheckBox(t('Measure application and website time'))
        self.tracking.setChecked(app.focus.settings.tracking); self.tracking.toggled.connect(self.tracking_changed)
        filter_box.addWidget(self.tracking)
        layout.addWidget(filters)
        self.category.currentIndexChanged.connect(self.choose_category)
        self.period.currentIndexChanged.connect(self.choose_period)
        self.devices.currentIndexChanged.connect(self.choose_device)
        self.error=label('','danger'); self.error.setWordWrap(True); self.error.hide(); layout.addWidget(self.error)
        metrics=QHBoxLayout(); metrics.setSpacing(12)
        self.total_label,self.average_label,self.top_label=label('—','metric'),label('—','metric'),label('—','section')
        self.metric_titles={}
        for title,value in [('Total play time',self.total_label),('Daily average',self.average_label),('Most played',self.top_label)]:
            card=panel(); box=QVBoxLayout(card); box.setContentsMargins(18,14,18,14); box.setSpacing(7)
            caption=label(t(title),'muted'); self.metric_titles[title]=caption; box.addWidget(caption)
            value.setWordWrap(True); box.addWidget(value); metrics.addWidget(card,1)
            if title=='Most played': self.top_detail=label('','muted'); box.addWidget(self.top_detail)
        layout.addLayout(metrics)
        chart_box=panel(); chart_layout=QVBoxLayout(chart_box); chart_layout.setContentsMargins(18,15,18,14); chart_layout.setSpacing(8)
        self.chart_title=label(t('Time by day'),'section'); chart_layout.addWidget(self.chart_title)
        self.chart_summary=label('','muted'); self.chart_summary.setWordWrap(True); chart_layout.addWidget(self.chart_summary)
        self.chart=DailyChart(t,self.share); self.chart.axis_format=self.friendly_time
        self.chart.empty_text='No time recorded for this selection.'
        self.chart.setMinimumHeight(210); self.chart.day_clicked.connect(self.choose_day); chart_layout.addWidget(self.chart)
        self.computer_legend=ComputerLegend(); self.computer_legend.setAccessibleName(t('Computer colors'))
        chart_layout.addWidget(self.computer_legend); self.computer_legend.hide()
        self.chart_hint=label('','muted'); self.chart_hint.setWordWrap(True); chart_layout.addWidget(self.chart_hint); layout.addWidget(chart_box)
        details=panel(); details_box=QVBoxLayout(details); details_box.setContentsMargins(18,15,18,15); details_box.setSpacing(10)
        details_heading=QHBoxLayout(); self.breakdown_title=label(t('Where did the time go?'),'section'); details_heading.addWidget(self.breakdown_title,1)
        self.day_selector=QComboBox(); self.day_selector.setAccessibleName(t('Details for day')); self.day_selector.setMinimumWidth(210)
        self.day_selector.setMaximumWidth(230)
        self.day_selector.currentIndexChanged.connect(self.select_row); details_heading.addWidget(self.day_selector)
        self.search=QLineEdit(); self.search.setPlaceholderText(t('Search this list…')); self.search.setAccessibleName(t('Search this list'))
        self.search.setClearButtonEnabled(True); self.search.setMinimumWidth(130); self.search.setMaximumWidth(220)
        self.search.textChanged.connect(self.show_breakdown); details_heading.addWidget(self.search)
        self.whole_period_button=button(t('All days'),self.show_period,'quiet'); details_heading.addWidget(self.whole_period_button)
        details_box.addLayout(details_heading)
        self.breakdown_note=label('','muted'); details_box.addWidget(self.breakdown_note)
        self.details_panel=details
        self.games_table=QTableWidget(0,5); self.games_table.verticalHeader().hide(); self.games_table.setShowGrid(False)
        self.games_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.games_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.games_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.games_table.verticalScrollBar().setSingleStep(12)
        self.games_table.setProperty('revealOnWheel',True)
        self.games_table.setProperty('revealParentBottomOnWheel',True)
        self.games_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for column,width in ((1,165),(2,110),(3,94),(4,68)): self.games_table.setColumnWidth(column,width)
        self.games_table.setStyleSheet('QTableWidget::item {padding:9px 6px;}'); self.games_table.setWordWrap(False)
        details_box.addWidget(self.games_table)
        self.games_table.itemSelectionChanged.connect(self.update_exclusion_action)
        exclusion_actions=QHBoxLayout()
        self.exclude_app_button=button(t('Exclude selected application'),self.exclude_selected_application)
        self.exclude_app_button.setEnabled(False); exclusion_actions.addWidget(self.exclude_app_button)
        exclusion_actions.addWidget(button(t('Excluded applications…'),lambda:self.app.focus_page.excluded_apps_dialog(),'quiet'))
        exclusion_actions.addStretch(); details_box.addLayout(exclusion_actions)
        self.empty_details=label(t('No activity here yet. Try a different period or activity type.'),'muted'); self.empty_details.setWordWrap(True)
        details_box.addWidget(self.empty_details); layout.addWidget(details)
        self.average_note=label('','muted',parent=self); self.average_note.hide()
        self.refresh_category_text()

    def update_exclusion_action(self):
        rows=self.games_table.selectionModel().selectedRows()
        keys=getattr(self,'_breakdown_keys',[])
        self.exclude_app_button.setEnabled(len(rows)==1 and rows[0].row()<len(keys)
                                           and keys[rows[0].row()][0].startswith('activity:app:'))

    def exclude_selected_application(self):
        rows=self.games_table.selectionModel().selectedRows()
        keys=getattr(self,'_breakdown_keys',[])
        if len(rows)!=1 or rows[0].row()>=len(keys): return
        key=keys[rows[0].row()][0]
        if key.startswith('activity:app:'):
            self.app.focus_page.exclude_application(key[len('activity:app:'):])

    def friendly_time(self,seconds):
        seconds=max(0,int(seconds))
        if seconds<60: return self.app.t('{seconds} sec',seconds=seconds)
        hours,minutes=divmod(seconds//60,60)
        if not hours: return self.app.t('{minutes} min',minutes=minutes)
        return self.app.t('{hours} h {minutes} min',hours=hours,minutes=minutes) if minutes else self.app.t('{hours} h',hours=hours)

    def tracking_changed(self,enabled):
        self.app.focus.configure(replace(self.app.focus.settings,tracking=enabled))
        self.app.update_focus_policy()

    def toggle_computers(self,checked=False):
        self.computer_panel.setVisible(bool(checked)); self.app.update_statistics_sync_controls()

    def explain(self):
        from .qt_ui import dark_window
        window=self.app._dialog(self.app.t('What is measured?'),620); box=QVBoxLayout(window); box.setContentsMargins(24,22,24,22); box.setSpacing(16)
        for text in ('Only the foreground application or active website counts, including time spent reading without input. Tracking pauses when the session is locked.',
                     'Applications excludes recognized games. Websites shows the active browser tab. Everything counts website time inside browser time, so the same time is never added twice.',
                     'Linked computers share game, application and website history and supported settings.',
                     'The daily average uses all elapsed days in the selected period since tracking began, including days with no recorded time.'):
            note=label(self.app.t(text)); note.setWordWrap(True); box.addWidget(note)
        box.addWidget(button(self.app.t('Close'),window.accept)); window.show(); dark_window(window)

    def choose_period(self,*_):
        value=self.period.currentData(); self.custom_range.setVisible(value=='custom')
        if value=='custom': return
        start,end=self.period_dates(value)
        self.start.setText(start); self.end.setText(end); self.selected_day=None; self._relative_day=date.today(); self.refresh()

    def period_dates(self,value):
        today=date.today(); end=today
        start=(today if value=='today' else today-timedelta(days=1) if value=='yesterday' else
               today-timedelta(days=6) if value=='week' else today-timedelta(days=29) if value=='month' else today.replace(day=1))
        if value=='yesterday': end=start
        return start.isoformat(),end.isoformat()

    def apply_dates(self):
        self.selected_day=None; self.refresh()

    def preset(self,count):
        index=self.period.findData({7:'week',30:'month',0:'calendar'}[count])
        if self.period.currentIndex()==index: self.choose_period()
        else: self.period.setCurrentIndex(index)

    def refresh(self,live=False):
        self.last_refresh=time.monotonic()
        if live and self.period.currentData()!='custom' and self._relative_day!=date.today():
            self._relative_day=date.today(); self._range=self.period_dates(self.period.currentData())
            self.start.setText(self._range[0]); self.end.setText(self._range[1])
        selected_range=self._range if live else (self.start.text(),self.end.text())
        try: date_range(*selected_range)
        except ValueError as exc:
            self.error.setText(self.app.t(str(exc))); self.error.show(); return
        self._range=selected_range
        if not live and self.period.currentData()!='custom' and selected_range!=self.period_dates(self.period.currentData()):
            blocked=self.period.blockSignals(True); self.period.setCurrentIndex(self.period.findData('custom')); self.period.blockSignals(blocked)
            self.custom_range.show()
        if not live: self.error.hide()
        self.app.tracker.flush(); self.app.focus.flush()
        self.refresh_devices()
        group=self.app.settings.statistics_sync_group
        started=self.app.statistics_data.started_on(group,self.scope)
        category=self.category.currentData()
        self.computer_history=(self.app.statistics_data.history_by_computer(*self._range,group,self.scope,self.app.settings.statistics_device_name)
                               if category in ('games','all') else [])
        if category!='games':
            activity_started=self.app.statistics_data.activity_started_on(group,self.scope)
            started=min(started,activity_started) if category=='all' else activity_started
            self.computer_history += self.app.statistics_data.activity_history_by_computer(
                *self._range,group,self.scope,category,self.app.settings.statistics_device_name)
        self.refresh_category_text()
        self.report=summarize((row[:5] for row in self.computer_history),*self._range,started_on=started,as_of=date.today().isoformat())
        self.total_label.setText(self.friendly_time(self.report.total)); self.average_label.setText(self.friendly_time(self.report.average))
        self.top_label.setText(self.item_name(self.report.games[0][0],self.report.games[0][1]) if self.report.games else '—')
        self.top_detail.setText(self.friendly_time(self.report.games[0][3])+' · '+self.share(self.report.games[0][3],self.report.total) if self.report.games else self.app.t('No activity yet'))
        if self.report.games:
            self.top_label.setStyleSheet('color:'+self.colors.color(self.report.games[0][0],'game')+';')
        else: self.top_label.setStyleSheet('')
        average_started=max(started,self._range[0])
        explanation=self.app.t('Average uses {days} elapsed days in the selected period, starting at {date}.',days=self.report.average_days,date=average_started)
        self.average_note.setText(self.app.t('Average: {days} days · since {date}',date=average_started,days=self.report.average_days))
        self.average_label.setToolTip(explanation); self.average_note.setToolTip(explanation)
        if self.selected_day not in self.report.days: self.selected_day=None
        self.refresh_day_selector(); self.update_chart(); self.show_breakdown()

    def refresh_day_selector(self):
        if not self.report: return
        blocked=self.day_selector.blockSignals(True); days=list(reversed(self.report.days))
        if getattr(self,'_listed_days',None)!=days:
            self.day_selector.clear(); self.day_selector.addItem(self.app.t('Whole period'),None)
            for day in days: self.day_selector.addItem('',day)
            self._listed_days=days
        self.day_selector.setItemText(0,self.app.t('Whole period'))
        for index,day in enumerate(days,1): self.day_selector.setItemText(index,day+' · '+self.friendly_time(self.report.days[day]))
        self.day_selector.setCurrentIndex(max(0,self.day_selector.findData(self.selected_day)))
        self.day_selector.blockSignals(blocked)

    def share(self,seconds,total):
        value=f'{seconds/total:.1%}' if total else '0%'
        return value.replace('.',',') if self.app.settings.language=='hu' else value

    def retranslate_report(self):
        self.refresh_category_text()
        if hasattr(self,'computer_names'):
            self.computer_names={identity:value.in_language(self.app.settings.language) if isinstance(value,UiText) else value for identity,value in self.computer_names.items()}
        if self.report and self.report.games:
            self.top_label.setText(self.item_name(self.report.games[0][0],self.report.games[0][1]))
            self.top_detail.setText(self.friendly_time(self.report.games[0][3])+' · '+self.share(self.report.games[0][3],self.report.total))
        elif self.report: self.top_detail.setText(self.app.t('No activity yet'))
        if self.report:
            self.total_label.setText(self.friendly_time(self.report.total)); self.average_label.setText(self.friendly_time(self.report.average))
        for field in (self.start,self.end):
            text=field.text(); field.setLocale(QLocale('hu_HU' if self.app.settings.language=='hu' else 'en_GB')); field.setText(text)
        self.refresh_day_selector(); self.update_chart(); self.show_breakdown()

    def choose_category(self,*_):
        category=self.category.currentData()
        self._category=category
        self.selected_day=None; self.refresh(live=True)

    def item_name(self,key,name):
        return self.app.t(name) if key=='activity:browser:other' else name

    def refresh_category_text(self):
        t=self.app.t; games=self.category.currentData()=='games'
        self.metric_titles['Total play time'].setText(t('Total time in period'))
        self.metric_titles['Most played'].setText(t('Most played' if games else 'Most used'))
        self.chart_title.setText(t('Time by day')); self.chart.setAccessibleName(t('Time by day'))
        category=self.category.currentData()
        self.games_table.setHorizontalHeaderLabels([t({'games':'Game','apps':'Application','websites':'Website','all':'Activity'}[category]),t('Computer'),t('Type'),t('Time'),t('Share')])
        self.activity_note.setVisible(category in ('apps','websites','all'))
        self.activity_note.setText(t('Applications exclude recognized games. Linked computers share these records when sync is enabled.' if category=='apps' else
                                     'Website time is part of browser time; it is counted once.' if category=='all' else
                                     'Only the active website is counted. Linked computers share these records when sync is enabled.'))
        self.total_label.setToolTip(t('Only recorded play time is available. Hidden and removed games are included.' if games else 'Only recorded active time is available. Applications exclude recognized games. Website totals are part of browser time.'))

    def update_chart(self,*args):
        if not self.report: return
        kind='game'; totals=Counter(); names={}; segments={}; computers={}
        self.chart_summary.setText(self.app.t('{start} to {end}',start=self._range[0],end=self._range[1]))
        # Build once when data or grouping changes; selecting a day only repaints.
        for day,gid,name,source,seconds,identity,device_name in self.computer_history:
            if seconds<=0: continue
            key=gid
            names[key]=self.item_name(gid,name)
            segments.setdefault(day,Counter())[key]+=seconds; totals[key]+=seconds
            computers.setdefault(day,{}).setdefault(identity,Counter())[key]+=seconds
        for key in sorted(totals): self.colors.color(key,kind)
        series={key:(names[key],self.colors.color(key,kind)) for key in sorted(totals,key=lambda key:(-totals[key],names[key].casefold(),key))}
        order={key:i for i,key in enumerate(series)}
        segments={day:dict(sorted(values.items(),key=lambda item:order[item[0]])) for day,values in segments.items()}
        computers={day:{identity:dict(sorted(values.items(),key=lambda item:order[item[0]]))
                        for identity,values in sorted(per_day.items(),key=lambda item:(item[0]!='local',self.computer_names.get(item[0],item[0]).casefold(),item[0]))}
                   for day,per_day in computers.items()}
        multi=len(self.computer_names)>1
        identities=sorted(self.computer_names,key=lambda identity:(identity!='local',self.computer_names[identity].casefold(),identity)) if multi else []
        if self.scope!='all': identities=[identity for identity in identities if identity==self.scope]
        active={identity for per_day in computers.values() for identity in per_day}
        device_colors={identity:self.colors.color(identity,'computer') for identity in active.union(identities)}
        self.chart.set_days(self.report.days,self.selected_day,segments,series,computers,self.computer_names,device_colors,show_computer_markers=multi)
        self.computer_legend.setAccessibleName(self.app.t('Computer colors'))
        self.computer_legend.set_computers(identities,self.computer_names,self.colors)
        self.chart_hint.setText(self.app.t('The side color identifies the computer. Spaces separate computers; activity colors match the list below.' if multi else
                                          'Each color is one activity. Click a day to see its details.'))

    def refresh_devices(self):
        remote=self.app.statistics_data.devices(self.app.settings.statistics_sync_group)
        aliases=self.app.statistics_data.device_aliases(self.app.settings.statistics_sync_group)
        remote=[(identity,aliases.get(identity,name),started) for identity,name,started in remote]
        names=Counter(name for identity,name,started in remote)
        self.computer_names={'local':self.app.t('{name} (this computer)',name=self.app.settings.statistics_device_name or computer_name())}
        self.computer_names.update({identity:name+(' · '+identity[:8] if names[name]>1 else '') for identity,name,started in remote})
        for identity in sorted(self.computer_names): self.colors.color(identity,'computer')
        blocked=self.devices.blockSignals(True)
        choices=[('all',self.app.t('All linked computers') if remote else self.app.t('This computer')),('local',self.computer_names['local'])]+[(identity,self.computer_names[identity]) for identity,name,started in remote]
        if [self.devices.itemData(i) for i in range(self.devices.count())]!=[identity for identity,name in choices]:
            self.devices.clear()
            for identity,name in choices: self.devices.addItem(name,identity)
            for i in range(1,self.devices.count()): self.devices.setItemIcon(i,self.colors.icon(self.devices.itemData(i),'computer'))
        else:
            for i,(identity,name) in enumerate(choices): self.devices.setItemText(i,name)
        index=self.devices.findData(self.scope)
        if index<0: self.scope='all'; index=0
        self.devices.setCurrentIndex(index); self.devices.blockSignals(blocked)
        self.devices.view().setRowHidden(self.devices.findData('local'),not bool(remote))
        self.devices.setEnabled(bool(remote))
        self.devices.setToolTip(self.app.t('Choose a computer, or include all linked computers.'))
        self.sync_label.setText(self.app.statistics_sync_status())
        self.app.update_statistics_sync_controls()

    def choose_device(self,index):
        self.scope=self.devices.itemData(index) or 'all'; self.selected_day=None; self.refresh(live=True)

    def select_row(self,row):
        if self.updating or not self.report or row<0: return
        self.selected_day=self.day_selector.itemData(row); self.show_breakdown()

    def choose_day(self,day):
        if not self.report or day not in self.report.days: return
        self.selected_day=day
        self.refresh_day_selector(); self.show_breakdown()
        if self.isVisible(): self.scroll.ensureWidgetVisible(self.details_panel,0,16)

    def show_period(self):
        self.selected_day=None; self.refresh_day_selector(); self.show_breakdown()

    def show_breakdown(self,*_):
        if not self.report: return
        rows=self.report.by_day.get(self.selected_day,[]) if self.selected_day else self.report.games
        total=sum(row[3] for row in rows)
        order={row[0]:index for index,row in enumerate(rows)}
        grouped={}
        for day,gid,name,source,seconds,identity,device_name in self.computer_history:
            if self.selected_day and day!=self.selected_day: continue
            if seconds<=0: continue
            grouped.setdefault((gid,identity),[gid,name,source,0,identity,device_name])[3]+=seconds
        rows=sorted(grouped.values(),key=lambda row:(order[row[0]],-row[3],row[5].casefold(),row[4]))
        query=self.search.text().strip().casefold(); count=len(rows)
        if query:
            rows=[row for row in rows if query in (self.item_name(row[0],row[1])+' '+self.computer_names.get(row[4],row[5])).casefold()]
        self.breakdown_title.setText(self.app.t('Where did the time go?')); self.whole_period_button.setVisible(self.selected_day is not None)
        self.breakdown_note.setText(self.app.t('Matches: {count} of {total}',count=len(rows),total=count) if query else
                                    self.app.t('{period} · {time}',period=self.selected_day,time=self.friendly_time(total)) if self.selected_day else
                                    self.app.t('Items: {count} · largest first',count=count))
        self.empty_details.setText(self.app.t('No matching entries. Try another name.' if query else 'No activity here yet. Try a different period or activity type.'))
        identities={row[4] for row in rows}
        self.games_table.setColumnHidden(1,len(identities)<=1 and len(self.chart.device_colors)<=1)
        self.games_table.setColumnHidden(2,self.category.currentData()!='all')
        self.games_table.setVisible(bool(rows)); self.empty_details.setVisible(not rows)
        self.games_table.setFixedHeight(min(350,max(128,40+44*len(rows))))
        keys=[(row[0],row[4]) for row in rows]
        previous=getattr(self,'_breakdown_keys',[])
        selected={previous[index.row()] for index in self.games_table.selectionModel().selectedRows() if index.row()<len(previous)}
        self.games_table.setRowCount(len(rows))
        if keys!=previous: self.games_table.clearSelection()
        for i,(gid,name,source,seconds,identity,device_name) in enumerate(rows):
            share=self.share(seconds,total)
            source=self.app.t(source) if source in ('Application','Website','Browser') else self.app.t('Game')
            name=self.item_name(gid,name)
            computer=self.computer_names.get(identity,device_name)
            for col,value in enumerate((name,computer,source,duration(seconds),share)):
                item=self.games_table.item(i,col)
                if item is None:
                    item=QTableWidgetItem(); self.games_table.setItem(i,col,item)
                item.setText(value)
                item.setToolTip(value)
                if col in (0,1):
                    kind='game' if col==0 else 'computer'; key=gid if col==0 else identity
                    item.setIcon(self.colors.icon(key,kind)); item.setForeground(QColor(self.colors.color(key,kind)))
                if col==1: item.setData(Qt.UserRole,identity)
                if col>=3: item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            if self.games_table.rowHeight(i)!=44: self.games_table.setRowHeight(i,44)
            if keys!=previous and (gid,identity) in selected: self.games_table.selectRow(i)
        self._breakdown_keys=keys
        self.update_exclusion_action()
        self.chart.selected=self.selected_day; self.chart.update()
