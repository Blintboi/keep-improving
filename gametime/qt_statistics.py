"""Historical statistics, using the same recorded-time model as the monitor."""
from datetime import date,timedelta
from collections import Counter
from dataclasses import replace
from sqlite3 import Error as SQLiteError
import hashlib
import time
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QColor,QIcon,QPainter,QPixmap,QFontMetrics
from PySide6.QtWidgets import QWidget,QScrollArea,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QListView,QHeaderView,QAbstractItemView,QStyledItemDelegate
from .statistics import date_range,summarize
from .qt_widgets import label,button,panel,duration,DailyChart
from .qt_widgets import NoWheelComboBox as QComboBox
from .statistics_sync import computer_name
from .qt_translation import UiText,QLineEdit,QTableWidget,QTableWidgetItem

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

class StatisticsLegendDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        name,values=index.data(Qt.UserRole+1)
        painter.save(); painter.setClipRect(option.rect)
        rect=option.rect.adjusted(5,0,-10,0)
        index.data(Qt.DecorationRole).paint(painter,rect.left(),rect.center().y()-8,16,16)
        font=option.font; font.setPixelSize(11); painter.setFont(font)
        metrics=QFontMetrics(font); width=metrics.horizontalAdvance(values)+8
        value_rect=rect.adjusted(rect.width()-width,0,0,0)
        painter.setPen(QColor('#93a3a7')); painter.drawText(value_rect,Qt.AlignRight|Qt.AlignVCenter,values)
        font.setPixelSize(12); painter.setFont(font); painter.setPen(QColor('#edf4f2'))
        name_rect=rect.adjusted(23,0,-width-5,0)
        painter.drawText(name_rect,Qt.AlignLeft|Qt.AlignVCenter,QFontMetrics(font).elidedText(name,Qt.ElideRight,name_rect.width()))
        painter.restore()
    def sizeHint(self,option,index): return QSize(265,32)

class StatisticsColors:
    """Reuse series colors across refreshes, filters and translated page rebuilds."""
    palette=('#73c7ff','#f0ba68','#b9a1ff','#7de5bf','#f58fa7','#74d8db',
             '#d7dc7a','#f4a67c','#9faef4','#e4a1e0','#a1d99b','#dcc6a1')
    def __init__(self): self.colors={'game':{},'computer':{}}; self.icons={}
    def color(self,key,kind):
        colors=self.colors[kind]
        if key not in colors:
            number=int.from_bytes(hashlib.sha256((kind+':'+key).encode()).digest()[:4],'big')
            candidates=self.palette[number%len(self.palette):]+self.palette[:number%len(self.palette)]
            colors[key]=next((color for color in candidates if color not in colors.values()),
                             QColor.fromHslF((number%3600)/3600,.66,.72).name())
        return colors[key]
    def icon(self,key,kind):
        color=self.color(key,kind); cache=(color,kind)
        if cache not in self.icons:
            pixmap=QPixmap(16,16); pixmap.fill(Qt.transparent)
            painter=QPainter(pixmap); painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(color))
            if kind=='game': painter.drawEllipse(2,2,12,12)
            else: painter.drawRoundedRect(2,2,12,12,2,2)
            painter.end(); self.icons[cache]=QIcon(pixmap)
        return self.icons[cache]

class StatisticsPage(QWidget):
    def __init__(self,app):
        super().__init__(); self.app=app; self.report=None; self.selected_day=None; self.last_refresh=0; self.updating=False; self.scope='all'
        if not hasattr(app,'statistics_colors'): app.statistics_colors=StatisticsColors()
        self.colors=app.statistics_colors
        t=app.t
        shell=QVBoxLayout(self); shell.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); shell.addWidget(scroll)
        content=QWidget(); scroll.setWidget(content)
        layout=QVBoxLayout(content); layout.setContentsMargins(32,25,32,22); layout.setSpacing(16)
        header=QHBoxLayout(); header.addWidget(label(t('Statistics'),'title'),1)
        header.addWidget(button(t('Link computers'),app.statistics_sync_dialog))
        self.sync_now=button(t('Sync now'),app.request_statistics_sync); self.sync_now.setEnabled(app.settings.statistics_sync_enabled); header.addWidget(self.sync_now)
        self.sync_now.setToolTip(t('Sync runs at startup, when gameplay starts and after it stops, or manually. Requests wait at least 10 minutes; nearby game changes are combined. Server limits also apply.'))
        layout.addLayout(header)
        devices_row=QHBoxLayout(); devices_row.addWidget(label(t('Computers'),'muted'))
        self.devices=QComboBox(); self.devices.setMinimumWidth(250); self.devices.setMaximumWidth(320); devices_row.addWidget(self.devices)
        self.devices.currentIndexChanged.connect(self.choose_device)
        self.rename_computer=button(t('Rename computer'),lambda:rename_computer_dialog(app)); devices_row.addWidget(self.rename_computer)
        self.sync_label=label(app.statistics_sync_status(),'muted'); self.sync_label.setWordWrap(True); devices_row.addWidget(self.sync_label,1); layout.addLayout(devices_row)
        controls=QHBoxLayout(); controls.setSpacing(8)
        self.presets=[]
        for text,days in [('Last 7 days',7),('Last 30 days',30),('This month',0)]:
            item=button(t(text),lambda checked=False,n=days:self.preset(n),'preset'); item.setCheckable(True)
            self.presets.append(item); controls.addWidget(item)
        controls.addStretch(); layout.addLayout(controls)
        controls=QHBoxLayout(); controls.setSpacing(8)
        self.start=QLineEdit((date.today()-timedelta(days=29)).isoformat()); self.end=QLineEdit(date.today().isoformat())
        for text,widget in [('From',self.start),('To',self.end)]:
            controls.addWidget(label(t(text),'muted')); widget.setFixedWidth(112); widget.setPlaceholderText('YYYY-MM-DD')
            widget.returnPressed.connect(self.refresh); controls.addWidget(widget)
        controls.addWidget(button(t('Apply'),self.refresh)); controls.addStretch(); layout.addLayout(controls)
        self.error=label('','danger'); self.error.setWordWrap(True); self.error.hide(); layout.addWidget(self.error)
        metrics=QHBoxLayout(); metrics.setSpacing(14)
        self.total_label,self.average_label,self.top_label=label('00:00:00','metric'),label('00:00:00','metric'),label('—','section')
        for title,value in [('Total play time',self.total_label),('Daily average',self.average_label),('Most played',self.top_label)]:
            card=panel(); box=QVBoxLayout(card); box.setContentsMargins(20,16,20,18); box.setSpacing(10)
            box.addWidget(label(t(title),'muted')); value.setWordWrap(True); box.addWidget(value); metrics.addWidget(card,1)
            if title=='Most played':
                self.top_detail=label('','muted'); box.addWidget(self.top_detail)
        layout.addLayout(metrics)
        chart_box=panel(); chart_layout=QVBoxLayout(chart_box); chart_layout.setContentsMargins(20,17,20,13)
        chart_heading=QHBoxLayout(); chart_heading.addWidget(label(t('Daily play time'),'section'),1)
        chart_heading.addWidget(label(t('Color by'),'muted'))
        self.chart_mode=QComboBox(); self.chart_mode.addItem(t('Game'),'game'); self.chart_mode.addItem(t('Computer'),'computer')
        self.chart_mode.setAccessibleName(t('Color by')); self.chart_mode.currentIndexChanged.connect(self.update_chart)
        chart_heading.addWidget(self.chart_mode); chart_layout.addLayout(chart_heading)
        self.chart_summary=label('','muted'); self.chart_summary.setWordWrap(True); chart_layout.addWidget(self.chart_summary)
        self.chart=DailyChart(t,self.share); self.chart.day_clicked.connect(self.choose_day); chart_layout.addWidget(self.chart)
        self.legend=QListWidget(); self.legend.setAccessibleName(t('Chart legend'))
        self.legend.setItemDelegate(StatisticsLegendDelegate(self.legend))
        self.legend.setFlow(QListView.LeftToRight); self.legend.setWrapping(True); self.legend.setResizeMode(QListView.Adjust)
        self.legend.setMovement(QListView.Static); self.legend.setGridSize(QSize(265,32)); self.legend.setFixedHeight(72)
        self.legend.setSelectionMode(QAbstractItemView.NoSelection); self.legend.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.legend.setStyleSheet('QListWidget::item {padding:4px 5px; margin:0; border:none;}')
        chart_layout.addWidget(self.legend)
        hint=label(t('Hover for times and shares. Click a day to see its games and computers.'),'muted')
        hint.setWordWrap(True); chart_layout.addWidget(hint)
        layout.addWidget(chart_box,2)
        lower=QHBoxLayout(); lower.setSpacing(16)
        days_card=panel(); days_layout=QVBoxLayout(days_card); days_layout.setContentsMargins(10,14,10,10)
        days_layout.addWidget(label('  '+t('Date'),'muted'))
        self.days_list=QListWidget(); self.days_list.setMinimumWidth(192); self.days_list.setMaximumWidth(252)
        self.days_list.currentRowChanged.connect(self.select_row); days_layout.addWidget(self.days_list)
        lower.addWidget(days_card,1)
        games_card=panel(); games_layout=QVBoxLayout(games_card); games_layout.setContentsMargins(16,12,16,6)
        heading=QHBoxLayout(); self.breakdown_title=label(t('Whole period'),'section'); heading.addWidget(self.breakdown_title); heading.addStretch()
        self.whole_period_button=button(t('Whole period'),self.show_period,'quiet'); heading.addWidget(self.whole_period_button); games_layout.addLayout(heading)
        self.games_table=QTableWidget(0,5); self.games_table.setHorizontalHeaderLabels([t('Game'),t('Computer'),t('Source'),t('Time'),t('Share')])
        self.games_table.verticalHeader().hide(); self.games_table.setShowGrid(False)
        self.games_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.games_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.games_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for col,width in ((1,140),(2,90),(3,88),(4,64)): self.games_table.setColumnWidth(col,width)
        self.games_table.setStyleSheet('QTableWidget::item {padding:10px 6px;}')
        self.games_table.setWordWrap(False)
        self.games_table.setMinimumHeight(145); games_layout.addWidget(self.games_table); lower.addWidget(games_card,3)
        layout.addLayout(lower,2)
        self.average_note=label('','muted'); self.average_note.setWordWrap(True); layout.addWidget(self.average_note)
        self.total_label.setToolTip(t('Only recorded play time is available. Hidden and removed games are included.'))

    def preset(self,count):
        today=date.today()
        self.start.setText((today-timedelta(days=count-1) if count else today.replace(day=1)).isoformat())
        self.end.setText(today.isoformat()); self.selected_day=None
        for item,n in zip(self.presets,(7,30,0)): item.setChecked(n==count)
        self.refresh()

    def refresh(self):
        self.last_refresh=time.monotonic()
        try: date_range(self.start.text(),self.end.text())
        except ValueError as exc:
            self.error.setText(self.app.t(str(exc))); self.error.show(); return
        self.error.hide(); self.app.tracker.flush()
        self.refresh_devices()
        group=self.app.settings.statistics_sync_group
        started=self.app.statistics_data.started_on(group,self.scope)
        self.computer_history=self.app.statistics_data.history_by_computer(self.start.text(),self.end.text(),group,self.scope,self.app.settings.statistics_device_name)
        self.report=summarize((row[:5] for row in self.computer_history),self.start.text(),self.end.text(),started_on=started,as_of=date.today().isoformat())
        self.total_label.setText(duration(self.report.total)); self.average_label.setText(duration(self.report.average))
        self.top_label.setText(self.report.games[0][1] if self.report.games else self.app.t('No recorded play time'))
        self.top_detail.setText(duration(self.report.games[0][3])+' · '+self.share(self.report.games[0][3],self.report.total) if self.report.games else '')
        if self.report.games:
            self.top_label.setStyleSheet('color:'+self.colors.color(self.report.games[0][0],'game')+';')
        else: self.top_label.setStyleSheet('')
        average_started=max(started,self.start.text())
        explanation=self.app.t('Average uses {days} elapsed days in the selected period, starting at {date}.',days=self.report.average_days,date=average_started)
        self.average_note.setText(self.app.t('Average: {days} days · since {date}',date=average_started,days=self.report.average_days))
        self.average_label.setToolTip(explanation); self.average_note.setToolTip(explanation)
        if self.selected_day not in self.report.days: self.selected_day=None
        self.updating=True
        days=list(reversed(self.report.days))
        if getattr(self,'_listed_days',None)!=days:
            self.days_list.clear()
            for day in days: self.days_list.addItem(day+'   '+duration(self.report.days[day]))
            self._listed_days=days
        else:
            for index,day in enumerate(days): self.days_list.item(index).setText(day+'   '+duration(self.report.days[day]))
        if self.selected_day: self.days_list.setCurrentRow(list(reversed(self.report.days)).index(self.selected_day))
        self.updating=False; self.update_chart(); self.show_breakdown()

    def share(self,seconds,total):
        value=f'{seconds/total:.1%}' if total else '0%'
        return value.replace('.',',') if self.app.settings.language=='hu' else value

    def retranslate_report(self):
        self.chart.setAccessibleName(self.app.t('Daily play time')); self.legend.setAccessibleName(self.app.t('Chart legend'))
        if hasattr(self,'computer_names'):
            self.computer_names={identity:value.in_language(self.app.settings.language) if isinstance(value,UiText) else value for identity,value in self.computer_names.items()}
        if self.report and self.report.games:
            self.top_detail.setText(duration(self.report.games[0][3])+' · '+self.share(self.report.games[0][3],self.report.total))
        self.update_chart(); self.show_breakdown()

    def update_chart(self,*args):
        if not self.report: return
        kind=self.chart_mode.currentData(); totals=Counter(); names={}; segments={}
        # Build once when data or grouping changes; selecting a day only repaints.
        for day,gid,name,source,seconds,identity,device_name in self.computer_history:
            if seconds<=0: continue
            key=gid if kind=='game' else identity
            names[key]=name if kind=='game' else self.computer_names.get(identity,device_name)
            segments.setdefault(day,Counter())[key]+=seconds; totals[key]+=seconds
        for key in sorted(totals): self.colors.color(key,kind)
        series={key:(names[key],self.colors.color(key,kind)) for key in sorted(totals,key=lambda key:(-totals[key],names[key].casefold(),key))}
        order={key:i for i,key in enumerate(series)}
        segments={day:dict(sorted(values.items(),key=lambda item:order[item[0]])) for day,values in segments.items()}
        self.chart.set_days(self.report.days,self.selected_day,segments,series)
        keys=(kind,tuple(series))
        if getattr(self,'_legend_keys',None)!=keys:
            self.legend.clear()
            for key in series:
                item=QListWidgetItem(self.colors.icon(key,kind),''); item.setData(Qt.UserRole,key); self.legend.addItem(item)
            self._legend_keys=keys
        for index,(key,(name,color)) in enumerate(series.items()):
            values=duration(totals[key])+' · '+self.share(totals[key],self.report.total)
            text=name+' · '+values
            item=self.legend.item(index); item.setText(text); item.setToolTip(text)
            item.setData(Qt.UserRole+1,(name,values))
        self.legend.setFixedHeight(40 if len(series)<=2 else 72)
        self.legend.setVisible(bool(series))
        if self.report.total:
            peak=max(self.report.days,key=self.report.days.get)
            self.chart_summary.setText(self.app.t('{days} active days · busiest: {date} ({time})',days=sum(value>0 for value in self.report.days.values()),date=peak,time=duration(self.report.days[peak])))
        else: self.chart_summary.setText('')

    def refresh_devices(self):
        remote=self.app.statistics_data.devices(self.app.settings.statistics_sync_group)
        aliases=self.app.statistics_data.device_aliases(self.app.settings.statistics_sync_group)
        remote=[(identity,aliases.get(identity,name),started) for identity,name,started in remote]
        names=Counter(name for identity,name,started in remote)
        self.computer_names={'local':self.app.t('{name} (this computer)',name=self.app.settings.statistics_device_name or computer_name())}
        self.computer_names.update({identity:name+(' · '+identity[:8] if names[name]>1 else '') for identity,name,started in remote})
        for identity in sorted(self.computer_names): self.colors.color(identity,'computer')
        blocked=self.devices.blockSignals(True)
        choices=[('all',self.app.t('All linked computers')),('local',self.computer_names['local'])]+[(identity,self.computer_names[identity]) for identity,name,started in remote]
        if [self.devices.itemData(i) for i in range(self.devices.count())]!=[identity for identity,name in choices]:
            self.devices.clear()
            for identity,name in choices: self.devices.addItem(name,identity)
            for i in range(1,self.devices.count()): self.devices.setItemIcon(i,self.colors.icon(self.devices.itemData(i),'computer'))
        else:
            for i,(identity,name) in enumerate(choices): self.devices.setItemText(i,name)
        index=self.devices.findData(self.scope)
        if index<0: self.scope='all'; index=0
        self.devices.setCurrentIndex(index); self.devices.blockSignals(blocked)
        self.sync_label.setText(self.app.statistics_sync_status())
        self.app.update_statistics_sync_controls()

    def choose_device(self,index):
        self.scope=self.devices.itemData(index) or 'all'; self.selected_day=None; self.refresh()

    def select_row(self,row):
        if self.updating or not self.report or row<0: return
        self.selected_day=list(reversed(self.report.days))[row]; self.show_breakdown()

    def choose_day(self,day):
        if not self.report or day not in self.report.days: return
        self.selected_day=day
        self.days_list.setCurrentRow(list(reversed(self.report.days)).index(day)); self.show_breakdown()

    def show_period(self):
        self.selected_day=None; self.updating=True; self.days_list.setCurrentRow(-1); self.updating=False; self.show_breakdown()

    def show_breakdown(self):
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
        self.breakdown_title.setText(self.selected_day or self.app.t('By game and computer')); self.whole_period_button.setVisible(self.selected_day is not None)
        keys=[(row[0],row[4]) for row in rows]
        previous=getattr(self,'_breakdown_keys',[])
        selected={previous[index.row()] for index in self.games_table.selectionModel().selectedRows() if index.row()<len(previous)}
        self.games_table.setRowCount(len(rows))
        if keys!=previous: self.games_table.clearSelection()
        for i,(gid,name,source,seconds,identity,device_name) in enumerate(rows):
            share=self.share(seconds,total)
            source=self.app.source_name(source)
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
        self.chart.selected=self.selected_day; self.chart.update()
