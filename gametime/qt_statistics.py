"""Historical statistics, using the same recorded-time model as the monitor."""
from datetime import date,timedelta
from collections import Counter
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QScrollArea,QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QComboBox
from .statistics import date_range,summarize
from .qt_widgets import label,button,panel,duration,DailyChart
from .statistics_sync import computer_name

class StatisticsPage(QWidget):
    def __init__(self,app):
        super().__init__(); self.app=app; self.report=None; self.selected_day=None; self.last_refresh=0; self.updating=False; self.scope='all'
        t=app.t
        shell=QVBoxLayout(self); shell.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); shell.addWidget(scroll)
        content=QWidget(); scroll.setWidget(content)
        layout=QVBoxLayout(content); layout.setContentsMargins(32,25,32,22); layout.setSpacing(16)
        header=QHBoxLayout(); header.addWidget(label(t('Statistics'),'title'),1)
        header.addWidget(button(t('Link computers'),app.statistics_sync_dialog))
        self.sync_now=button(t('Sync now'),app.request_statistics_sync); self.sync_now.setEnabled(app.settings.statistics_sync_enabled); header.addWidget(self.sync_now)
        self.sync_now.setToolTip(t('Automatic sync runs every 5 minutes while Statistics is open, otherwise every 15 minutes. Manual sync is limited to once a minute and follows server limits.'))
        header.addWidget(button(t('Refresh'),self.refresh)); layout.addLayout(header)
        devices_row=QHBoxLayout(); devices_row.addWidget(label(t('Computers'),'muted'))
        self.devices=QComboBox(); self.devices.setMinimumWidth(250); self.devices.setMaximumWidth(320); devices_row.addWidget(self.devices)
        self.devices.currentIndexChanged.connect(self.choose_device)
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
        layout.addLayout(metrics)
        chart_box=panel(); chart_layout=QVBoxLayout(chart_box); chart_layout.setContentsMargins(20,17,20,13)
        chart_title=label(t('Daily play time'),'section'); chart_title.setToolTip(t('Daily play time — click a bar to see its games')); chart_layout.addWidget(chart_title)
        self.chart=DailyChart(); self.chart.day_clicked.connect(self.choose_day); chart_layout.addWidget(self.chart)
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
        explanation=self.app.t('Average uses {days} elapsed days in the selected period, starting at {date}.',days=self.report.average_days,date=started)
        self.average_note.setText(self.app.t('Average: {days} days · since {date}',date=started,days=self.report.average_days))
        self.average_label.setToolTip(explanation); self.average_note.setToolTip(explanation)
        if self.selected_day not in self.report.days: self.selected_day=None
        self.updating=True; self.days_list.clear()
        for day,seconds in reversed(list(self.report.days.items())): self.days_list.addItem(day+'   '+duration(seconds))
        if self.selected_day: self.days_list.setCurrentRow(list(reversed(self.report.days)).index(self.selected_day))
        self.updating=False; self.show_breakdown()

    def refresh_devices(self):
        remote=self.app.statistics_data.devices(self.app.settings.statistics_sync_group)
        names=Counter(name for identity,name,started in remote)
        self.computer_names={'local':self.app.t('{name} (this computer)',name=self.app.settings.statistics_device_name or computer_name())}
        self.computer_names.update({identity:name+(' · '+identity[:8] if names[name]>1 else '') for identity,name,started in remote})
        self.devices.blockSignals(True); self.devices.clear()
        self.devices.addItem(self.app.t('All linked computers'),'all'); self.devices.addItem(self.computer_names['local'],'local')
        for identity,name,started in remote: self.devices.addItem(self.computer_names[identity],identity)
        index=self.devices.findData(self.scope)
        if index<0: self.scope='all'; index=0
        self.devices.setCurrentIndex(index); self.devices.blockSignals(False)
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
            grouped.setdefault((gid,identity),[gid,name,source,0,identity,device_name])[3]+=seconds
        rows=sorted(grouped.values(),key=lambda row:(order[row[0]],-row[3],row[5].casefold(),row[4]))
        self.breakdown_title.setText(self.selected_day or self.app.t('By game and computer')); self.whole_period_button.setVisible(self.selected_day is not None)
        self.games_table.setRowCount(len(rows))
        for i,(gid,name,source,seconds,identity,device_name) in enumerate(rows):
            share=f'{seconds/total:.1%}' if total else '0%'
            if self.app.settings.language=='hu': share=share.replace('.',',')
            source=self.app.source_name(source)
            computer=self.computer_names.get(identity,device_name)
            for col,value in enumerate((name,computer,source,duration(seconds),share)):
                item=QTableWidgetItem(value)
                item.setToolTip(value)
                if col==1: item.setData(Qt.UserRole,identity)
                if col>=3: item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                self.games_table.setItem(i,col,item)
            self.games_table.setRowHeight(i,44)
        self.chart.set_days(self.report.days,self.selected_day)
