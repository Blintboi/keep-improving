"""Visible feedback for explicit UI operations, without another window."""
import logging
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QProgressBar
from .qt_widgets import label

log=logging.getLogger(__name__)


class OperationFeedback(QFrame):
    def __init__(self,app):
        super().__init__(app); self.app=app; self.busy=False; self.origin=None
        self.setFixedHeight(42)
        box=QVBoxLayout(self); box.setContentsMargins(32,2,32,6); box.setSpacing(3)
        self.text=label('','muted'); self.text.setAccessibleName(app.t('Operation status')); box.addWidget(self.text)
        self.progress=QProgressBar(); self.progress.setRange(0,0); self.progress.setTextVisible(False); self.progress.setFixedHeight(3)
        self.progress.setStyleSheet('QProgressBar{border:0;background:#20322d;}QProgressBar::chunk{background:#7de5bf;}'); box.addWidget(self.progress)
        self.progress.hide(); self.text.hide()
        self.clear_timer=QTimer(self); self.clear_timer.setSingleShot(True); self.clear_timer.timeout.connect(self.text.hide)
        self.work_timer=QTimer(self); self.work_timer.setSingleShot(True); self.work_timer.timeout.connect(self.execute)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self,watched,event):
        # Keep the form unchanged while its save is queued, without dimming or
        # rebuilding it. Do not pump events from inside a database transaction.
        return bool(self.busy and event.type() in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease,QEvent.MouseButtonDblClick,QEvent.KeyPress,QEvent.KeyRelease,QEvent.Wheel)
                    and hasattr(watched,'window') and watched.window() is self.app)

    def run(self,title,work,*,origin=None,error=None,success='Saved.'):
        if self.busy or self.app.closed:return False
        self.clear_timer.stop(); self.busy=True; self.work=work; self.error=error; self.success=success
        self.origin=origin; self.origin_text=getattr(origin,'_ui_strings',{}).get('setText',origin.text()) if origin else None
        if origin:origin.setText(self.app.t(title));origin.setEnabled(False)
        self.text.setText(self.app.t(title));self.text.show();self.progress.show();self.repaint()
        # Paint the acknowledgement before beginning work on GUI-owned state.
        self.work_timer.start(0)
        return True

    def execute(self):
        failed=False
        try:
            if self.app.closed:return
            result=self.work();failed=result is False or bool(self.error and self.error())
        except Exception:
            failed=True;log.exception('User operation failed')
        finally:
            self.busy=False;self.progress.hide()
            if self.origin:
                self.origin.setText(self.origin_text);self.origin.setEnabled(True)
            self.origin=None;self.work=None
            if failed:self.text.setText(self.app.t('Could not complete the action. Check the message and try again.'))
            elif self.success:
                self.text.setText(self.app.t(self.success));self.clear_timer.start(4000)
                if self.app.status_key in ('Settings saved.','Notifications saved.'):self.app.status_label.hide()
            else:self.text.hide()

    def close_operation(self):
        self.work_timer.stop();self.clear_timer.stop();self.busy=False;self.work=None
        QApplication.instance().removeEventFilter(self)
