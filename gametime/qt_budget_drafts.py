"""Local, unapplied budget drafts. Event-driven writes; no credentials or polling."""
from copy import deepcopy
import json
import logging
from sqlite3 import Error as SQLiteError
from PySide6.QtCore import QObject,QTimer,QEvent
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout
from .qt_translation import QDialog
from .qt_widgets import label,button

KEY='budget_editor_draft_v1'
FIELDS=('rules','game_limits','original_game_limits','restriction_plans','game_overlays','counter_overlays',
        'shared_overlay','member_overlay_drafts','reset_overrides','shared_enabled','shared_created','computer_created','categories')
SETS=('restriction_changed','draft_games','game_overlay_changed','counter_overlay_changed','reset_changed')


class BudgetDrafts(QObject):
    def __init__(self,editor):
        super().__init__(editor); self.editor=editor; self.loading=True; self.closed=False; self.last=None; self.raw={}
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.flush)
        self.baseline=self.snapshot()
        row=editor.app.store.db.execute('SELECT value FROM settings WHERE key=?',(KEY,)).fetchone()
        if row:
            try:
                data=json.loads(row[0]); self.restore(data); self.last=row[0]
            except (ValueError,TypeError,KeyError,IndexError,AttributeError):
                logging.getLogger(__name__).exception('Could not restore budget draft')
                self.restore({'state':deepcopy(self.baseline),'view':0})
        self.loading=False; self.wire(); QApplication.instance().installEventFilter(self)
        self.queue()

    def wire(self):
        for widget in self.editor.findChildren(QWidget):
            if widget.property('draftConnected'): continue
            connected=False
            for name in ('textEdited','valueChanged','timeChanged','toggled','activated','clicked'):
                signal=getattr(widget,name,None)
                if signal is not None:
                    signal.connect(self.queue); connected=True
            if connected: widget.setProperty('draftConnected',True)
        self.editor.schedule.selection_changed.connect(self.queue) if not getattr(self,'_schedule_connected',False) else None
        self._schedule_connected=True

    def eventFilter(self,watched,event):
        if not self.closed and isinstance(watched,QWidget) and (watched is self.editor or self.editor.isAncestorOf(watched)):
            if event.type()==QEvent.ChildAdded: self.queue()
            elif event.type() in (QEvent.FocusOut,QEvent.KeyRelease,QEvent.MouseButtonRelease): self.queue()
        return False

    def queue(self,*args):
        if not self.loading and not self.closed: self.timer.start(350)

    def snapshot(self):
        e=self.editor; e.collect()
        data={name:deepcopy(getattr(e,name)) for name in FIELDS}
        data.update({name:sorted(getattr(e,name)) for name in SETS})
        data['periods']=deepcopy(e.periods.items)
        data['schedule']={'plans':deepcopy(e.schedule._plans),'edits':deepcopy(e.schedule._edits)}
        data['access']={name:deepcopy(getattr(e.access,name)) for name in ('active_days','usage_limits')}
        data['access'].update({name:sorted(getattr(e.access,name)) for name in ('changed_days','changed_limits')})
        return data

    def restore(self,data):
        e=self.editor; state=data['state']
        if set(state)!=set(self.baseline): raise ValueError('Invalid budget draft.')
        e.current=None
        for name in FIELDS: setattr(e,name,deepcopy(state[name]))
        for name in SETS: setattr(e,name,set(state[name]))
        e.periods.items=deepcopy(state['periods'])
        e.schedule._plans={int(k):v for k,v in state['schedule']['plans'].items()}
        e.schedule._edits={int(k):v for k,v in state['schedule']['edits'].items()}; e.schedule.load_selection()
        for name in ('active_days','usage_limits'): setattr(e.access,name,deepcopy(state['access'][name]))
        for name in ('changed_days','changed_limits'): setattr(e.access,name,set(state['access'][name]))
        self.raw=data.get('raw',{})
        e.refresh(data.get('key')); e.views.setCurrentIndex(data.get('view',0)); self.apply_raw()

    def apply_raw(self):
        # Preserve an incomplete numeric entry as text as well as its last value.
        for address,text in self.raw.get(self.editor.current,{}).items():
            widget=self.raw_fields().get(address)
            if widget:
                blocked=widget.blockSignals(True); widget.setText(text); widget.blockSignals(blocked)
                if widget.hasAcceptableInput(): widget.parent().interpretText()

    def remember(self):
        key=self.editor.current
        if self.loading or not key: return
        raw={address:widget.text() for address,widget in self.raw_fields().items()
             if not widget.hasAcceptableInput() or widget.isModified()}
        if raw: self.raw[key]=raw
        else: self.raw.pop(key,None)

    def raw_fields(self):
        e=self.editor; result={}
        if e.current and e.stack.currentIndex()==1: result['minutes']=e.minutes.lineEdit()
        schedule=e.periods.schedule if e.periods.is_extra(e.current) else e.schedule
        if e.periods.is_computer(e.current) or e.current=='shared-games':
            result.update({'schedule:'+key:w.lineEdit() for key,w in schedule._fields.items() if hasattr(w,'lineEdit')})
        for card in e.steps.cards:
            result['step:'+card.value['id']]=card.minutes.lineEdit()
        return result

    def flush(self):
        if self.loading or self.closed: return
        self.timer.stop(); self.remember(); self.loading=True
        try:
            self.wire(); state=self.snapshot(); e=self.editor
            raw=deepcopy(self.raw)
            clean=state==self.baseline and not raw
            value=None if clean else json.dumps(dict(state=state,key=e.current,view=e.views.currentIndex(),raw=raw),ensure_ascii=False,allow_nan=False)
            if value!=self.last:
                with e.app.store.db:
                    if value is None: e.app.store.db.execute('DELETE FROM settings WHERE key=?',(KEY,))
                    else: e.app.store.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(KEY,value))
                self.last=value
            if hasattr(e.app,'budget_draft_note'):
                e.app.budget_draft_note.setText(e.app.t('Draft saved on this computer. Save changes to apply.') if value else '')
                e.app.budget_discard.setVisible(bool(value))
            from .budget_conflicts import warning
            e.conflicts.setText(warning(e)); e.conflicts.setVisible(bool(e.conflicts.text()))
        except (ValueError,OSError,SQLiteError):
            logging.getLogger(__name__).exception('Could not save budget draft')
            if hasattr(self.editor.app,'budget_draft_note'):
                self.editor.app.budget_draft_note.setText(self.editor.app.t('Could not save the draft. Keep this window open and try again.'))
        finally: self.loading=False

    def saved(self):
        self.timer.stop(); self.baseline=self.snapshot(); self.last=None; self.raw={}; self.editor.periods.migrated=False
        with self.editor.app.store.db: self.editor.app.store.db.execute('DELETE FROM settings WHERE key=?',(KEY,))
        if hasattr(self.editor.app,'budget_draft_note'):
            self.editor.app.budget_draft_note.clear(); self.editor.app.budget_discard.hide()

    def prepare_save(self):
        self.remember()
        for key in list(self.raw):
            self.editor.show_editor(key)
            for address in list(self.raw.get(key,{})):
                field=self.raw_fields().get(address)
                if field is None: continue
                if not field.hasAcceptableInput():
                    self.editor.app.budget_error.setText(self.editor.app.t('Finish the incomplete value before saving.'))
                    field.setFocus(); return False
                field.parent().interpretText(); field.setModified(False)
            self.raw.pop(key,None)
        return True

    def discard(self):
        e=self.editor; t=e.app.t; dialog=QDialog(e); dialog.setObjectName('Surface'); dialog.setWindowTitle(t('Discard draft'))
        box=QVBoxLayout(dialog); box.setContentsMargins(24,22,24,22); note=label(t('Discard all unfinished budget changes?'),'section'); note.setWordWrap(True); box.addWidget(note)
        box.addWidget(label(t('Your saved budgets and activity history will be kept.'),'muted'))
        row=QHBoxLayout(); row.addStretch(); cancel=button(t('Cancel'),dialog.reject); cancel.setDefault(True); row.addWidget(cancel)
        row.addWidget(button(t('Discard draft'),dialog.accept,'danger-action')); box.addLayout(row)
        from .qt_ui import dark_window
        dark_window(dialog)
        if dialog.exec()!=QDialog.Accepted: return
        self.loading=True
        try:
            e.current=None; e.schedule.saved(e.app.settings); e.saved(e.app.settings); e.show_list()
        finally: self.loading=False

    def close(self):
        self.flush(); self.closed=True; self.timer.stop(); QApplication.instance().removeEventFilter(self)
