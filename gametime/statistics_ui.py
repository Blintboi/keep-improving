"""Dark daily chart and historical game breakdown, owned by the Tk thread."""
from datetime import date, timedelta
import time
import tkinter as tk
from tkinter import ttk
from .statistics import date_range, summarize


def duration(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}"


class StatisticsView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=18)
        self.app = app
        self.report = None
        self.selected_day = None
        self.last_refresh = 0
        self.bars = []
        t = app.t
        self.start = tk.StringVar(value=(date.today()-timedelta(days=29)).isoformat())
        self.end = tk.StringVar(value=date.today().isoformat())
        self.summary = tk.StringVar()
        self.top_game = tk.StringVar()
        self.error = tk.StringVar()
        self.breakdown_title = tk.StringVar()
        controls = ttk.Frame(self)
        controls.pack(fill="x")
        for label, count in (("Last 7 days", 7), ("Last 30 days", 30), ("This month", 0)):
            ttk.Button(controls, text=t(label), command=lambda n=count: self.preset(n)).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text=t("Refresh"), command=self.refresh).pack(side="right")
        dates = ttk.Frame(self)
        dates.pack(fill="x", pady=10)
        for label, variable in (("From", self.start), ("To", self.end)):
            ttk.Label(dates, text=t(label)).pack(side="left", padx=(0, 6))
            entry = ttk.Entry(dates, textvariable=variable, width=12)
            entry.pack(side="left", padx=(0, 14))
            entry.bind("<Return>", lambda e: self.refresh())
        ttk.Label(dates, text="YYYY-MM-DD", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        ttk.Button(dates, text=t("Apply"), command=self.refresh).pack(side="left")
        ttk.Label(self, textvariable=self.error, foreground="#ffb3b3").pack(anchor="w")
        ttk.Label(self, textvariable=self.summary, style="Title.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(self, textvariable=self.top_game, style="Muted.TLabel").pack(anchor="w")
        ttk.Label(self, text=t("Daily play time — click a bar to see its games")).pack(anchor="w", pady=(10, 2))
        self.chart = tk.Canvas(self, height=160, background="#23262d", highlightthickness=0, cursor="hand2")
        self.chart.pack(fill="x")
        self.chart.bind("<Configure>", lambda e: self.draw_chart())
        self.chart.bind("<Button-1>", self.select_bar)
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(12, 6))
        daily, details = ttk.Frame(body), ttk.Frame(body)
        body.add(daily, weight=1)
        body.add(details, weight=3)
        self.days_tree = ttk.Treeview(daily, columns=("date", "time"), show="headings", selectmode="browse", height=5)
        self.days_tree.heading("date", text=t("Date"))
        self.days_tree.heading("time", text=t("Time"))
        self.days_tree.column("date", width=110, minwidth=95)
        self.days_tree.column("time", width=95, minwidth=80)
        scroll = ttk.Scrollbar(daily, orient="vertical", command=self.days_tree.yview)
        self.days_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.days_tree.pack(fill="both", expand=True)
        self.days_tree.bind("<<TreeviewSelect>>", self.select_day)
        heading = ttk.Frame(details)
        heading.pack(fill="x", padx=(12, 0))
        ttk.Label(heading, textvariable=self.breakdown_title).pack(side="left")
        ttk.Button(heading, text=t("Whole period"), command=self.show_period).pack(side="right")
        self.games_tree = ttk.Treeview(details, columns=("name", "source", "time", "share"), show="headings", height=4)
        for key, label, width in (("name", "Game", 230), ("source", "Source", 100), ("time", "Time", 100), ("share", "Share", 70)):
            self.games_tree.heading(key, text=t(label))
            self.games_tree.column(key, width=width, minwidth=60, stretch=key == "name")
        scroll_games = ttk.Scrollbar(details, orient="vertical", command=self.games_tree.yview)
        self.games_tree.configure(yscrollcommand=scroll_games.set)
        scroll_games.pack(side="right", fill="y")
        self.games_tree.pack(fill="both", expand=True, padx=(12, 0), pady=(6, 0))
        ttk.Label(self, text=t("Only recorded play time is available. Hidden and removed games are included."),
                  style="Muted.TLabel", wraplength=950).pack(anchor="w")
        ttk.Label(self, text=t("Daily average includes every calendar day in the selected period."),
                  style="Muted.TLabel", wraplength=950).pack(anchor="w")

    def preset(self, count):
        today = date.today()
        self.start.set((today-timedelta(days=count-1) if count else today.replace(day=1)).isoformat())
        self.end.set(today.isoformat())
        self.selected_day = None
        self.refresh()

    def refresh(self):
        self.last_refresh = time.monotonic()
        try:
            date_range(self.start.get(), self.end.get())
        except ValueError as exc:
            self.error.set(self.app.t(str(exc)))
            return
        self.error.set("")
        self.app.tracker.flush()
        self.report = summarize(self.app.store.history(self.start.get(), self.end.get()), self.start.get(), self.end.get())
        self.last_refresh = time.monotonic()
        self.summary.set(self.app.t("Total: {total}  ·  Daily average: {average}",
                                    total=duration(self.report.total), average=duration(self.report.average)))
        self.top_game.set(self.app.t("Most played: {name}", name=self.report.games[0][1]) if self.report.games
                          else self.app.t("No recorded play time"))
        self.days_tree.delete(*self.days_tree.get_children())
        for day, seconds in reversed(list(self.report.days.items())):
            self.days_tree.insert("", "end", iid=day, values=(day, duration(seconds)))
        if self.selected_day not in self.report.days:
            self.selected_day = None
        if self.selected_day:
            self.days_tree.selection_set(self.selected_day)
        self.show_breakdown()
        self.draw_chart()

    def select_day(self, event=None):
        selection = self.days_tree.selection()
        if selection:
            self.selected_day = selection[0]
            self.show_breakdown()
            self.draw_chart()

    def show_period(self):
        self.selected_day = None
        self.days_tree.selection_remove(*self.days_tree.selection())
        self.show_breakdown()
        self.draw_chart()

    def show_breakdown(self):
        if not self.report:
            return
        period = self.selected_day or self.app.t("Whole period")
        self.breakdown_title.set(self.app.t("Breakdown — {period}", period=period))
        rows = self.report.by_day.get(self.selected_day, []) if self.selected_day else self.report.games
        total = sum(row[3] for row in rows)
        self.games_tree.delete(*self.games_tree.get_children())
        for gid, name, source, seconds in rows:
            share = f"{seconds/total:.1%}" if total else "0%"
            if self.app.settings.language == "hu":
                share = share.replace(".", ",")
            source_name = self.app.t("Manual") if source == "Kézi" else self.app.t("Games folder") if source == "Games" else source
            self.games_tree.insert("", "end", iid=gid, values=(name, source_name, duration(seconds), share))
        if not rows:
            self.games_tree.insert("", "end", values=(self.app.t("No recorded play time"), "", "", ""))

    def draw_chart(self):
        self.chart.delete("all")
        self.bars = []
        if not self.report:
            return
        width, height = max(300, self.chart.winfo_width()), 160
        items = list(self.report.days.items())
        maximum = max(1, max(self.report.days.values(), default=0))
        left, right, top, bottom = 72, width-12, 16, height-26
        self.chart.create_text(8, top, text=duration(maximum) if maximum > 1 else "00:00:00", anchor="w", fill="#aeb5c2")
        self.chart.create_text(8, bottom, text="00:00:00", anchor="w", fill="#aeb5c2")
        self.chart.create_line(left, bottom, right, bottom, fill="#414752")
        step = (right-left)/len(items)
        for index, (day, seconds) in enumerate(items):
            x1 = left+index*step
            x2 = x1+step
            y = bottom-max(2, (bottom-top)*seconds/maximum)
            fill = "#63e2ca" if day == self.selected_day else ("#86b9ff" if seconds else "#414752")
            self.chart.create_rectangle(x1+min(2, step/5), y, x2-min(2, step/5), bottom, fill=fill, outline="")
            self.bars.append((x1, x2, day))
            every = max(1, (len(items)+6)//7)
            if index % every == 0 or index == len(items)-1:
                self.chart.create_text((x1+x2)/2, bottom+14, text=day[5:], fill="#aeb5c2", font=("Segoe UI", 9))

    def select_bar(self, event):
        for left, right, day in self.bars:
            if left <= event.x < right:
                self.days_tree.selection_set(day)
                self.days_tree.see(day)
                self.select_day()
                break
