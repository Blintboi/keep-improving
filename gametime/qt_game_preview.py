"""Visible-only snapshot controls shared by both countdown editors."""
from PySide6.QtCore import QObject,QEvent,QTimer,Slot
from PySide6.QtWidgets import QWidget,QHBoxLayout
from .game_preview import running_window
from .overlay import choose_screen
from .qt_widgets import button,label
from .overlay_consent import overlay_reason


class BackgroundController(QObject):
    def __init__(self,app,picker,game_id):
        super().__init__(picker); self.app=app; self.picker=picker; self.game_id=game_id; self.target=None
        self.row=QWidget(); layout=QHBoxLayout(self.row); layout.setContentsMargins(0,0,0,0)
        layout.addWidget(button(app.t('Refresh game image'),self.refresh))
        self.status=label(app.t('Open a game to show its image here.'),'muted'); self.status.setWordWrap(True); layout.addWidget(self.status,1)
        self.show_timer=QTimer(self); self.show_timer.setSingleShot(True); self.show_timer.timeout.connect(self.refresh)
        picker.installEventFilter(self); app.game_snapshots.ready.connect(self.receive)

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Show: self.show_timer.start(0)
        elif event.type()==QEvent.Hide:
            self.show_timer.stop()
            self.target=None; self.picker.game_background=None
        return False

    def refresh(self):
        self.target=None; self.picker.game_background=None; self.picker.update()
        if not self.picker.isVisible() or self.app.closed: return
        target=running_window(self.app.catalog,self.game_id())
        if not target:
            self.status.setText(self.app.t('Open a game to show its image here.')); return
        reason=overlay_reason(self.app.catalog,target.path,self.app.catalog.games.get(target.game_id))
        if reason:
            self.status.setText(self.app.t(reason)); return
        self.target=target
        self.status.setText(self.app.t('Loading game image…'))
        if not self.app.game_snapshots.request(target,self):
            self.status.setText(self.app.t('Game image unavailable. You can still preview the countdown in the game.'))

    @Slot(object,object,object)
    def receive(self,recipient,target,result):
        if recipient is not self or target!=self.target or not self.picker.isVisible() or self.app.closed: return
        game=self.app.catalog.resolve(target.path,fallback=False)
        reason=overlay_reason(self.app.catalog,target.path,game)
        if not game or game.id!=target.game_id or not target.valid() or reason: result=None
        self.picker.game_background=result; self.picker.update()
        game=self.app.catalog.games.get(target.game_id)
        self.status.setText(self.app.t(reason) if reason else self.app.t('Game image: {name}. Refresh to update it.',name=game.name if game else '') if result else
                            self.app.t('Game image unavailable. You can still preview the countdown in the game.'))
        if result:
            # Automatic monitor follows the game's display, matching live HUD placement.
            if not self.picker._screen_choice():
                self.picker.screen=choose_screen('',result[1]); self.picker.update()
                self.picker._coordinates_changed()


def background_controls(app,picker,game_id,screen_choice,coordinates_changed):
    picker._screen_choice=screen_choice; picker._coordinates_changed=coordinates_changed
    controller=BackgroundController(app,picker,game_id); picker._background_controller=controller
    return controller.row
