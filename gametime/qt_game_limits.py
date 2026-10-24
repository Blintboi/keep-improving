"""Local per-game caps, sharing the existing quota period and foreground ledger."""
from dataclasses import replace
from datetime import datetime
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout
from .qt_translation import QCheckBox
from .qt_widgets import label, button, NoWheelComboBox, duration
from .qt_personalization import number


def game_limits_dialog(app, gid=None):
    window=app._dialog(app.t('Per-game limits'),620)
    layout=QVBoxLayout(window); layout.setContentsMargins(26,24,26,24); layout.setSpacing(16)
    note=label(app.t('Each game limit is part of the shared daily budget. The overlay shows whichever runs out first.'),'muted')
    note.setWordWrap(True); layout.addWidget(note)
    selector=NoWheelComboBox(); selector.setObjectName('limit_game'); selector.setAccessibleName(app.t('Game')); layout.addWidget(selector)
    enabled=QCheckBox(app.t('Limit this game')); enabled.setObjectName('game_limit_enabled'); layout.addWidget(enabled)
    row=QHBoxLayout(); row.addWidget(label(app.t('Game limit (minutes)')))
    minutes=number(30); minutes.setObjectName('game_limit_minutes'); minutes.setAccessibleName(app.t('Game limit (minutes)')); row.addWidget(minutes,1); layout.addLayout(row)
    usage=label('','muted'); usage.setWordWrap(True); layout.addWidget(usage)
    note=label(app.t('Uses the same daily reset as the shared budget, including time already played. At the limit, this game cannot be started from the Hub and is minimized after 10 seconds in the foreground. Protected games require the existing minimization permission; otherwise a reminder is shown.'),'muted')
    note.setWordWrap(True); layout.addWidget(note)
    excluded=label(app.t('This game is excluded from tracking. Its limit takes effect when tracking is enabled again.'),'muted'); excluded.setWordWrap(True); layout.addWidget(excluded)
    error=label('','danger'); error.setWordWrap(True); layout.addWidget(error)
    drafts={}; changed=set(); current=[None]; loading=[False]

    def collect():
        if current[0] is not None:
            value=minutes.value()*60 if enabled.isChecked() else None
            if value!=drafts.get(current[0]): changed.add(current[0])
            drafts[current[0]]=value

    def controls(*args):
        minutes.setEnabled(current[0] is not None and enabled.isChecked())
        if not loading[0]: error.clear()

    def load(*args):
        collect(); current[0]=selector.currentData(); loading[0]=True
        game=app.catalog.games.get(current[0])
        value=drafts.setdefault(current[0],app.settings.game_limits.get(current[0])) if game else None
        enabled.setChecked(value is not None); enabled.setEnabled(game is not None)
        minutes.setValue(value/60 if value is not None else 30)
        excluded.setVisible(bool(game and not app.catalog.enabled(game)))
        used=app.tracker.quota_totals(datetime.now().astimezone()).get(current[0],0) if game else 0
        usage.setText(app.t('Played in this budget period: {used}',used=duration(used)) if game else app.t('No installed games available.'))
        loading[0]=False; controls(); save.setEnabled(game is not None)

    def refresh():
        games=sorted((g for g in app.catalog.games.values() if g.installed),key=lambda g:(g.name.casefold(),g.id))
        rows=[(g.name+' · '+app.source_name(g.source),g.id) for g in games]
        if current[0] is not None and rows==[(selector.itemText(i),selector.itemData(i)) for i in range(selector.count())]: return
        collect(); chosen=current[0] or gid
        selector.blockSignals(True); selector.clear()
        for name,key in rows: selector.addItem(name,key)
        selector.setCurrentIndex(max(0,selector.findData(chosen))); selector.blockSignals(False)
        current[0]=None; load()

    def persist():
        collect()
        try:
            values=dict(app.settings.game_limits)
            for key in changed:
                if drafts[key] is None: values.pop(key,None)
                else: values[key]=drafts[key]
            settings=replace(app.settings,game_limits=values).validate()
            app.tracker.flush(); app.store.save_settings(settings)
            app.settings=app.catalog.settings=settings
            app._restriction_grace=None
            app.tracker.evaluate(datetime.now().astimezone())
            app.update_overlay(); app.render(); app.set_status('Settings saved.'); window.accept()
        except (ValueError,OSError,SQLiteError) as exc: error.setText(app.t(str(exc)))

    actions=QHBoxLayout(); actions.addStretch(); actions.addWidget(button(app.t('Cancel'),window.reject))
    save=button(app.t('Save'),persist,'primary'); save.setObjectName('save_game_limits'); actions.addWidget(save); layout.addLayout(actions)
    selector.currentIndexChanged.connect(load); enabled.toggled.connect(controls)
    window._refresh_games=refresh; refresh(); window.show()
    from .qt_ui import dark_window
    dark_window(window)
    return window
