"""Qt presentation primitives. Artwork comes only from local installed-game assets."""
import configparser
import hashlib
import json
from html import escape
from math import ceil
from pathlib import Path
from queue import Empty
from .model import within, helper
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer, QFileInfo
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QLinearGradient, QRegion
from PySide6.QtWidgets import QWidget,QFrame,QGridLayout,QFileIconProvider,QToolTip,QAbstractSpinBox,QDateEdit
from .qt_translation import QLabel,QPushButton,QComboBox,QDoubleSpinBox,QTimeEdit,QSlider

BG, PANEL, TEXT, MUTED, ACCENT = '#101619', '#192126', '#edf4f2', '#93a3a7', '#7de5bf'
STYLE = '''
* { font-family: "Segoe UI"; font-size: 13px; color: #edf4f2; }
QMainWindow, QDialog, QWidget#Surface { background: #101619; }
QFrame#Rail { background: #0b1114; border-right: 1px solid #202b30; }
QLabel { background: transparent; border: none; }
QLabel[role="muted"] { color: #93a3a7; }
QLabel[role="eyebrow"] { color: #8b9c9d; font-size: 10px; font-weight: 600; letter-spacing: 1px; }
QLabel[role="title"] { font-size: 27px; font-weight: 700; letter-spacing: -0.7px; }
QLabel[role="metric"] { font-size: 30px; font-weight: 650; letter-spacing: -0.7px; }
QLabel[role="section"] { font-size: 16px; font-weight: 600; }
QLabel[role="danger"] { color: #f3a7a7; }
QFrame#Panel { background: #192126; border: 1px solid #273238; border-radius: 16px; }
QFrame#Budget { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1a332e,stop:0.7 #19282a,stop:1 #192126); border: 1px solid #2b4840; border-radius: 18px; }
QPushButton, QToolButton { background: #202c31; border: 1px solid #304047; border-radius: 10px; padding: 9px 14px; font-weight: 550; }
QPushButton:hover, QToolButton:hover { background: #2b3b40; border-color: #506562; }
QPushButton:pressed, QToolButton:pressed { background: #334c45; }
QPushButton:disabled, QToolButton:disabled { color: #657779; background: #1a2429; border-color: #27343a; }
QPushButton[role="primary"] { background: #7de5bf; border: none; color: #10291f; font-weight: 700; padding: 11px 22px; }
QPushButton[role="primary"]:hover { background: #a1f3d5; }
QPushButton[role="primary"]:disabled { background: #293c35; color: #78958a; }
QPushButton[role="nav"] { background: transparent; border: none; text-align: left; padding: 12px 14px; color: #9eafb2; }
QPushButton[role="nav"]:hover { background: #152125; color: #edf4f2; }
QPushButton[role="nav"]:checked { background: #1d352d; color: #a0f0d1; }
QPushButton[role="quiet"] { background: transparent; border: none; color: #a1b4b5; }
QPushButton[role="quiet"]:hover { background: #1f2d31; color: #edf4f2; }
QPushButton[role="section-link"] { background: #19262a; border: 1px solid #304047; padding: 8px 5px; font-size: 12px; color: #c0d6d2; }
QPushButton[role="section-link"]:hover { background: #254039; border-color: #527b68; color: #edf4f2; }
QPushButton[role="preset"]:checked { background: #24483b; color: #a1f0d2; border-color: #396451; }
QPushButton[role="day"] { border-radius:22px; padding:0; color:#b9c9c9; font-weight:600; }
QPushButton[role="day"]:checked { background:#7de5bf; color:#10291f; border-color:#7de5bf; }
QPushButton[role="day"]:focus { border:2px solid #d1ffee; }
QFrame#SectionRule { background:#33434a; border:none; }
QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QTimeEdit { background: #182126; border: 1px solid #2e3b42; border-radius: 10px; padding: 10px 12px; selection-background-color: #315e4e; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus { border-color: #7de5bf; }
QLineEdit { color: #e5eeec; }
QAbstractSpinBox[hideStepButtons="true"]::up-button, QAbstractSpinBox[hideStepButtons="true"]::down-button { width:0; height:0; border:none; }
QComboBox { padding-right: 28px; combobox-popup: 0; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #1c282d; border: 1px solid #3c504e; selection-background-color: #315343; padding: 5px; outline: none; }
QComboBox QAbstractItemView::item { min-height: 32px; padding: 2px 8px; }
QScrollArea, QStackedWidget { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 13px; margin: 2px; }
QScrollBar::handle:vertical { background: #435b60; border-radius: 4px; min-height: 40px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #66827d; }
QScrollBar::handle:vertical:pressed, QScrollBar::handle:horizontal:pressed { background: #7da79a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 13px; margin: 2px; }
QScrollBar::handle:horizontal { background: #435b60; border-radius: 4px; min-width: 40px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QTableWidget, QListWidget { background: #192126; border: none; gridline-color: transparent; outline: none; }
QTableWidget::item { padding: 10px; border-bottom: 1px solid #263339; }
QTableWidget::item:selected, QListWidget::item:selected { background: #26453b; color: #c4f7e3; }
QListWidget::item { padding: 11px 12px; border-radius: 8px; margin: 2px 3px; }
QListWidget::item:hover { background: #223138; }
QHeaderView::section { background: #192126; color: #93a3a7; border: none; border-bottom: 1px solid #304047; padding: 11px 10px; text-align: left; font-size: 11px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1px solid #4c6460; border-radius: 5px; background: #172227; }
QCheckBox::indicator:checked { background: #7de5bf; border-color: #7de5bf; }
QMenu { background: #1b282c; border: 1px solid #3c514d; padding: 6px; border-radius: 10px; }
QMenu::item { padding: 10px 24px 10px 14px; border-radius: 6px; }
QMenu::item:selected { background: #315143; }
QMenu::separator { height: 1px; background: #33443f; margin: 4px 6px; }
QToolTip { background: #253c34; color: #edf4f2; border: 1px solid #527b68; padding: 7px; }
'''
STYLE += f"""
QComboBox::down-arrow {{ image: url({Path(__file__).with_name('icons').as_posix()}/chevron.svg); width:16px; height:16px; }}
QCheckBox::indicator:checked {{ image: url({Path(__file__).with_name('icons').as_posix()}/check.svg); }}
"""


def label(text='', role=None, parent=None):
    widget=QLabel(text,parent)
    widget.setCursor(Qt.ArrowCursor)
    widget.setTextFormat(Qt.PlainText)
    if role: widget.setProperty('role',role)
    return widget

def button(text, callback, role=None):
    widget=QPushButton(text)
    if role: widget.setProperty('role',role)
    widget.setCursor(Qt.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget

def panel(name='Panel'):
    widget=QFrame(); widget.setObjectName(name)
    return widget


def separator():
    widget=QFrame(); widget.setObjectName('SectionRule'); widget.setFixedHeight(1)
    return widget

def duration(seconds):
    seconds=max(0,int(seconds))
    return f'{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}'


class _IgnoreWheel:
    """Let the surrounding page scroll, even after the editor received focus."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self,event):
        event.ignore()


class NoWheelComboBox(_IgnoreWheel,QComboBox):
    pass  # The open popup's item view retains its own scrolling.


class _SpinButtons:
    def setButtonSymbols(self,symbols):
        # Qt 6.12's styled NoButtons layout collapses the text editor to one
        # pixel. Keep its normal layout and hide just the step button controls.
        hidden=symbols==QAbstractSpinBox.NoButtons
        self.setProperty('hideStepButtons',hidden)
        super().setButtonSymbols(QAbstractSpinBox.UpDownArrows if hidden else symbols)


class NoWheelDoubleSpinBox(_SpinButtons,_IgnoreWheel,QDoubleSpinBox):
    pass


class NoWheelDateEdit(_IgnoreWheel,QDateEdit):
    pass


class NoWheelTimeEdit(_SpinButtons,_IgnoreWheel,QTimeEdit):
    pass


class NoWheelSlider(_IgnoreWheel,QSlider):
    pass

def glyph(name, color=ACCENT, size=20):
    pix=QPixmap(size,size); pix.fill(Qt.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    p.scale(size/24,size/24); p.setPen(QPen(QColor(color),1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    if name=='library':
        for x,y in ((3,3),(14,3),(3,14),(14,14)): p.drawRoundedRect(QRectF(x,y,7,7),2,2)
    elif name=='stats':
        p.drawLine(4,20,21,20)
        for x,y in ((7,11),(13,6),(19,3)): p.drawLine(x,16,x,y)
    elif name=='focus':
        p.drawEllipse(QRectF(5,5,14,14)); p.drawEllipse(QRectF(9,9,6,6))
        for x1,y1,x2,y2 in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12)): p.drawLine(x1,y1,x2,y2)
    elif name=='search':
        p.drawEllipse(QRectF(4,3,12,12)); p.drawLine(15,15,21,21)
    elif name=='settings':
        p.drawEllipse(QRectF(5,5,14,14)); p.drawEllipse(QRectF(9,9,6,6))
        for x1,y1,x2,y2 in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(5,5,7,7),(17,17,19,19),(5,19,7,17),(17,7,19,5)): p.drawLine(x1,y1,x2,y2)
    elif name=='plus': p.drawLine(12,5,12,19); p.drawLine(5,12,19,12)
    elif name=='hide': p.drawRoundedRect(QRectF(4,4,16,16),3,3); p.drawLine(8,15,16,15)
    elif name=='bell':
        p.drawArc(QRectF(6,4,12,14),0,180*16); p.drawLine(6,11,5,18); p.drawLine(18,11,19,18); p.drawLine(5,18,19,18); p.drawArc(QRectF(9,17,6,5),180*16,180*16)
    elif name=='moon':
        path=QPainterPath(); path.moveTo(17,3); path.cubicTo(7,-1,0,10,6,17)
        path.cubicTo(11,24,22,19,21,12); path.cubicTo(15,17,9,8,17,3); p.drawPath(path)
    elif name=='dots':
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        for x in (5,12,19): p.drawEllipse(QRectF(x-1.5,10.5,3,3))
    elif name=='play':
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        path=QPainterPath(); path.moveTo(8,5); path.lineTo(20,12); path.lineTo(8,19); path.closeSubpath(); p.drawPath(path)
    elif name=='clients':
        p.drawRoundedRect(QRectF(3,4,18,14),3,3); p.drawLine(8,21,16,21); p.drawLine(12,18,12,21)
        p.drawLine(7,9,11,9); p.drawLine(9,7,9,11); p.drawEllipse(QRectF(15,9,1,1))
    p.end()
    return QIcon(pix)

class BudgetRing(QWidget):
    def __init__(self):
        super().__init__(); self.ratio=0; self.setFixedSize(66,66)
    def set_ratio(self,value):
        value=max(0,min(1,value))
        if self.ratio!=value: self.ratio=value; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#2e4941'),5)); p.drawEllipse(QRectF(7,7,52,52))
        p.setPen(QPen(QColor(ACCENT if self.ratio<.84 else '#f1c581' if self.ratio<1 else '#f09f9f'),5,Qt.SolidLine,Qt.RoundCap))
        p.drawArc(QRectF(7,7,52,52),90*16,-int(self.ratio*360*16))
        p.setPen(QPen(QColor('#bdf2db'),1.7,Qt.SolidLine,Qt.RoundCap)); p.drawLine(33,20,33,33); p.drawLine(33,33,42,38)

def normalize_icon(pix):
    """Shell icons can be tiny artwork inside a larger transparent native canvas."""
    if pix is not None and not pix.isNull():
        bounds=QRegion(pix.mask()).boundingRect()
        if not bounds.isEmpty(): pix=pix.copy(bounds)
        pix.setDevicePixelRatio(1.0)
    return pix

class LocalArtwork:
    def __init__(self, data_dir, roots):
        self.data_dir=Path(data_dir); self.roots=list(roots); self.cache={}; self.links={}
        self.provider=QFileIconProvider()
        self.worker=None; self.pending={}; self.tokens=0; self.fingerprints={}; self.origins={}; self.executables={}
    def key(self,game): return (game.id,game.root,game.metadata,self.links.get(game.id))
    def request(self,game,rules):
        key=self.key(game); signature=tuple(sorted((p,gid) for p,gid in rules.items() if gid==game.id))
        if self.fingerprints.get(key)==signature: return
        self.cache.pop(key,None); self.origins.pop(key,None)
        self.fingerprints[key]=signature; self.tokens+=1; self.pending[key]=self.tokens
        if self.worker is None:
            from .artwork import ArtworkWorker
            self.worker=ArtworkWorker()
        self.worker.request(self.tokens,key,game,self.roots,rules)
    def invalidate(self):
        self.cache.clear(); self.pending.clear(); self.fingerprints.clear(); self.origins.clear(); self.executables.clear()
        if self.worker: self.worker.generation+=1
    def poll(self):
        changed=[]
        if not self.worker: return changed
        for _ in range(3):
            try: token,key,poster,icon,executables,origin,icon_origin=self.worker.results.get_nowait()
            except Empty: break
            if self.pending.get(key)!=token: continue
            self.pending.pop(key,None)
            self.executables[key]=tuple(executables)
            old_poster,old_icon=self.cache.get(key,(None,None))
            pix=QPixmap.fromImage(icon) if icon is not None else old_icon
            if icon is None and executables:
                try:
                    candidate=self.provider.icon(QFileInfo(executables[0])).pixmap(256,256)
                    if not candidate.isNull(): pix=candidate
                except (OSError,RuntimeError): pass
            pix=normalize_icon(pix)
            self.cache[key]=(QPixmap.fromImage(poster) if poster is not None else old_poster,pix)
            self.origins[key]=origin or icon_origin or (executables[0] if executables and pix is not None else '')
            changed.append(key)
        return changed
    def close(self):
        if self.worker: self.worker.close()
    def refresh_links(self, root):
        try:
            state=json.loads((Path(root)/'.gametime-hub.json').read_text(encoding='utf-8'))
            self.links={row['gid']:row['path'] for row in state.get('links',[]) if row.get('role')=='launch'}
        except (OSError,ValueError,KeyError,TypeError,AttributeError): self.links={}
    def artwork(self,game,rules):
        key=self.key(game)
        self.request(game,rules)
        if key in self.cache: return self.cache[key]
        poster=None
        icon=QIcon()
        # Prefer real game artwork to a generic Windows internet-shortcut icon.
        executable=next((p for p,gid in rules.items() if gid==game.id and Path(p).is_file()),None)
        if not executable and game.source=='Epic' and game.metadata.endswith('.item'):
            try:
                manifest=json.loads(Path(game.metadata).read_text(encoding='utf-8-sig'))
                candidate=Path(game.root)/manifest.get('LaunchExecutable','')
                if within(candidate.resolve(),Path(game.root).resolve()) and candidate.suffix.lower()=='.exe' and not helper(candidate) and 'bootstrap' not in candidate.stem.lower() and candidate.is_file(): executable=str(candidate)
            except (OSError,ValueError,TypeError,AttributeError): pass
        if executable: icon=self.provider.icon(QFileInfo(executable))
        source=self.links.get(game.id)
        if icon.isNull() and source and Path(source).is_file():
            if Path(source).suffix.lower()=='.url':
                try:
                    ini=configparser.ConfigParser(interpolation=None); ini.read(source,encoding='utf-8-sig')
                    icon_file=ini.get('InternetShortcut','IconFile',fallback='')
                    candidate=Path(icon_file)
                    if len(candidate.drive)==2 and candidate.suffix.lower()=='.ico' and candidate.is_file(): icon=QIcon(str(candidate))
                except (OSError,ValueError,configparser.Error): pass
            elif Path(source).suffix.lower()=='.lnk': icon=self.provider.icon(QFileInfo(source))
        pix=icon.pixmap(256,256) if not icon.isNull() else None
        pix=normalize_icon(pix)
        result=(poster,pix)
        self.cache[key]=result
        return result

class ImageLaunchButton(QPushButton):
    """The artwork itself is an accessible button; its play cue appears on hover."""
    @staticmethod
    def _shape(rect,radius):
        shape=QPainterPath(); shape.addRoundedRect(rect,radius,radius)
        bottom=QPainterPath(); bottom.addRect(QRectF(rect.left(),rect.bottom()-radius,rect.width(),radius))
        return shape.united(bottom)
    def paintEvent(self,event):
        if not self.isEnabled() or not (self.underMouse() or self.hasFocus()): return
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillPath(self._shape(QRectF(self.rect()),14),QColor(8,17,21,42))
        center=self.rect().center(); x,y=center.x(),center.y()
        p.setPen(Qt.NoPen); p.setBrush(QColor(12,28,24,220)); p.drawEllipse(QRectF(x-25,y-25,50,50))
        triangle=QPainterPath(); triangle.moveTo(x-5,y-10); triangle.lineTo(x+11,y); triangle.lineTo(x-5,y+10); triangle.closeSubpath()
        p.fillPath(triangle,QColor(ACCENT))
        if self.hasFocus():
            p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(ACCENT),1.5)); p.drawPath(self._shape(QRectF(self.rect()).adjusted(2,2,-2,-2),12))
    def enterEvent(self,event): super().enterEvent(event); self.update()
    def leaveEvent(self,event): super().leaveEvent(event); self.update()
    def mouseDoubleClickEvent(self,event): event.accept()


class GameCard(QFrame):
    selected=Signal(str)
    launched=Signal(str)
    options_requested=Signal(str)
    def __init__(self,game,t):
        super().__init__(); self.game=game; self.t=t; self.chosen=False; self.hovered=False; self.seconds=0; self.art=(None,None); self.show_source=False
        self.game_remaining=None
        self.setFixedHeight(244); self.setMinimumWidth(190); self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus); self.setAccessibleName(game.name)
        self.play=ImageLaunchButton('',self); self.play.clicked.connect(lambda:self.launched.emit(self.game.id))
        self.play.setCursor(Qt.PointingHandCursor); self.play.setToolTip(t('▶ Play')); self.play.setAccessibleName(t('▶ Play')+' '+game.name)
        self.play.setStyleSheet('background:transparent; border:none; padding:0;')
        self.more=button('',lambda:self.options_requested.emit(self.game.id)); self.more.setIcon(glyph('dots','#cee1db',18)); self.more.setFixedSize(34,34)
        self.more.setParent(self); self.more.setToolTip(t('Game options')); self.more.setAccessibleName(t('Game options')+' '+game.name)
        self.more.setStyleSheet('QPushButton {background:#202c31; border:1px solid #40544f; border-radius:10px; padding:0;} QPushButton:hover {background:#315143;}')
        self.setToolTip(game.name+' · '+game.source)
    def resizeEvent(self,event):
        self.play.setGeometry(1,1,self.width()-2,187); self._position_options()
    def _title_top(self):
        return 195
    def required_height(self):
        details=int(bool(self.seconds) or not self.game.installed)+int(self.game_remaining is not None)
        return 244+details*21
    def _position_options(self):
        self.more.move(self.width()-49,round(self._title_top()+4))
    def set_game(self,game):
        if self.game==game: return
        self.game=game; self.setAccessibleName(game.name)
        self.play.setAccessibleName(self.t('▶ Play')+' '+game.name)
        self.more.setAccessibleName(self.t('Game options')+' '+game.name); self.update()
    def set_state(self,seconds,chosen,enabled=True):
        if self.seconds!=seconds or self.chosen!=chosen:
            self.seconds=seconds; self.chosen=chosen; self.update()
        source=self.t('Manual') if self.game.source=='Kézi' else self.t('Games folder') if self.game.source=='Games' else self.game.source
        self.setToolTip(self.game.name+' · '+source+'\n'+self.t('Today')+': '+duration(seconds))
        if self.game_remaining is not None:
            self.setToolTip(self.toolTip()+'\n'+self.t('Game: {remaining} left',remaining=duration(self.game_remaining)))
        self.play.setEnabled(enabled and self.game.installed)
    def set_game_remaining(self,value):
        if value is not None: value=max(0,int(value))
        if value!=self.game_remaining: self.game_remaining=value; self.update()
    def enterEvent(self,event): self.hovered=True; self.update()
    def leaveEvent(self,event): self.hovered=False; self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton: self.selected.emit(self.game.id); self.setFocus()
    def mouseDoubleClickEvent(self,event):
        self.mousePressEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter): self.launched.emit(self.game.id)
        elif event.key()==Qt.Key_Space: self.selected.emit(self.game.id)
        else: super().keyPressEvent(event)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(1,1,self.width()-2,self.height()-2); clip=QPainterPath(); clip.addRoundedRect(rect,15,15)
        background=QColor('#202d33' if self.hovered else PANEL)
        p.setClipPath(clip); p.fillRect(rect,background)
        # Keep artwork decoration above the title, and blend into the current
        # card background so hovering never exposes a stripe across the name.
        p.save(); p.setClipRect(QRectF(0,0,self.width(),188),Qt.IntersectClip)
        seed=hashlib.sha256(self.game.name.encode()).digest(); color=QColor.fromHsv(seed[0]*359//255,105,77)
        grad=QLinearGradient(0,0,self.width(),188); grad.setColorAt(0,color); grad.setColorAt(1,QColor('#14262c'))
        p.fillRect(QRectF(0,0,self.width(),188),grad)
        p.setPen(Qt.NoPen); p.setBrush(QColor(255,255,255,9)); p.drawEllipse(QRectF(self.width()-160,-76,240,240))
        p.setBrush(QColor(255,255,255,6)); p.drawEllipse(QRectF(-60,45,180,180))
        fade=QLinearGradient(0,130,0,188); fade.setColorAt(0,QColor(25,33,38,0)); fade.setColorAt(1,background); p.fillRect(QRectF(0,130,self.width(),58),fade)
        # Every source uses the same large tile. Icons stay complete; cover-only
        # games receive a centered square crop without stretching their artwork.
        tile=QRectF((self.width()-156)/2,16,156,156); area=tile.adjusted(6,6,-6,-6)
        p.setBrush(QColor(12,23,29,105)); p.setPen(QPen(QColor(255,255,255,23),1)); p.drawRoundedRect(tile,18,18)
        poster,icon=self.art; image=poster; cover=True
        if icon is not None and not icon.isNull() and (poster is None or poster.isNull() or max(poster.width(),poster.height())<128 or not .5<=poster.width()/poster.height()<=2.5): image=icon; cover=False
        if image is not None and not image.isNull():
            p.save(); image_clip=QPainterPath(); image_clip.addRoundedRect(area,13,13); p.setClipPath(image_clip,Qt.IntersectClip)
            ratio=image.width()/image.height()
            if cover and .5<=ratio<=2.5:
                size=min(image.width(),image.height()); source_rect=QRectF((image.width()-size)/2,(image.height()-size)/2,size,size)
                p.setRenderHint(QPainter.SmoothPixmapTransform); p.drawPixmap(area,image,source_rect)
            else:
                transform=Qt.FastTransformation if max(image.width(),image.height())<=64 else Qt.SmoothTransformation
                scaled=image.scaled(144,144,Qt.KeepAspectRatio,transform)
                p.drawPixmap(int(area.center().x()-scaled.width()/2),int(area.center().y()-scaled.height()/2),scaled)
            p.restore()
        else:
            p.setPen(QColor('#c1d9d7')); p.setFont(QFont('Segoe UI',40,QFont.Bold))
            initials=''.join(part[0] for part in self.game.name.split()[:2]).upper()
            p.drawText(tile,Qt.AlignCenter,initials)
        source=self.t('Manual') if self.game.source=='Kézi' else self.t('Games folder') if self.game.source=='Games' else self.game.source
        if self.show_source:
            p.setFont(QFont('Segoe UI',8,QFont.DemiBold)); badge_width=p.fontMetrics().horizontalAdvance(source)+18
            p.setPen(Qt.NoPen); p.setBrush(QColor(12,22,25,205)); p.drawRoundedRect(QRectF(12,12,badge_width,23),7,7)
            p.setPen(QColor('#c5d9d5')); p.drawText(QRectF(21,12,badge_width-12,23),Qt.AlignVCenter,source)
        p.restore()
        title_top=self._title_top()
        p.setFont(QFont('Segoe UI',11,QFont.DemiBold)); p.setPen(QColor(TEXT))
        p.drawText(QRectF(15,title_top,self.width()-78,42),Qt.TextWordWrap|Qt.AlignLeft|Qt.AlignVCenter,self.game.name)
        p.setFont(QFont('Segoe UI',9)); p.setPen(QColor(MUTED))
        caption=(duration(self.seconds) if self.seconds else '') if self.game.installed else self.t('Removed')
        details_top=title_top+46
        if caption:
            p.drawText(QRectF(15,details_top,self.width()-30,17),Qt.AlignLeft|Qt.AlignVCenter,caption)
            details_top+=21
        if self.game_remaining is not None:
            p.setFont(QFont('Segoe UI',9,QFont.DemiBold)); p.setPen(QColor(ACCENT if self.game_remaining else '#ff9197'))
            p.drawText(QRectF(15,details_top,self.width()-30,18),Qt.AlignLeft|Qt.AlignVCenter,self.t('Game: {remaining} left',remaining=duration(self.game_remaining)))
        p.setClipping(False); p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(ACCENT if self.chosen else '#3b514e' if self.hovered else '#2b393f'),1.6 if self.chosen else 1))
        p.drawRoundedRect(rect,15,15)

class CardGrid(QWidget):
    def __init__(self):
        super().__init__(); self.cards=[]; self.columns=0; self.card_height=244
        self.grid=QGridLayout(self); self.grid.setContentsMargins(0,0,8,0); self.grid.setSpacing(16); self.grid.setAlignment(Qt.AlignTop)
    def set_card_height(self,height):
        if height==self.card_height: return
        self.card_height=height
        for card in self.cards: card.setFixedHeight(height)
    def set_cards(self,cards):
        if self.cards==cards: return
        self.setUpdatesEnabled(False)
        for old in self.cards:
            self.grid.removeWidget(old)
            if old not in cards: old.hide(); old.deleteLater()
        self.cards=cards
        for card in cards: card.setFixedHeight(self.card_height)
        self.reflow(force=True)
        self.setUpdatesEnabled(True)
    def resizeEvent(self,event): self.reflow()
    def reflow(self,force=False):
        if not hasattr(self,'grid'): return
        columns=max(1,(self.width()+16)//238)
        if columns==self.columns and not force: return
        for card in self.cards: self.grid.removeWidget(card)
        for i,card in enumerate(self.cards): self.grid.addWidget(card,i//columns,i%columns,Qt.AlignTop)
        for col in range(max(columns,self.columns)): self.grid.setColumnStretch(col,1 if col<columns else 0)
        self.columns=columns

class DailyChart(QWidget):
    day_clicked=Signal(str)
    def __init__(self,t=lambda text,**values:text.format(**values),format_share=lambda value,total:f'{value/total:.1%}' if total else '0%'):
        super().__init__(); self.t=t; self.days={}; self.selected=None; self.regions=[]; self.segment_regions=[]
        self.format_share=format_share
        self.segments={}; self.series={}; self.computer_segments={}; self.computer_names={}; self.device_colors={}; self.computer_regions=[]
        self.show_computer_markers=False
        self.setMinimumHeight(220); self.setMouseTracking(True)
        self.setAccessibleName(t('Daily play time'))
    def set_days(self,days,selected=None,segments=None,series=None,computers=None,computer_names=None,device_colors=None,show_computer_markers=None):
        self.days=days; self.selected=selected; self.segments=segments or {}; self.series=series or {}
        self.computer_segments=computers or {}; self.computer_names=computer_names or {}; self.device_colors=device_colors or {}
        self.show_computer_markers=len(self.device_colors)>1 if show_computer_markers is None else show_computer_markers
        self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); self.regions=[]; self.segment_regions=[]; self.computer_regions=[]
        if not self.days: return
        peak=max(self.days.values())
        unit=60 if peak<=60 else 120 if peak<=600 else 600 if peak<=3600 else 1800 if peak<=14400 else 3600
        maximum=max(unit,ceil(peak/unit)*unit)
        multiple=self.show_computer_markers
        left,right,top,bottom=68,max(69,self.width()-12),24,self.height()-30
        p.setFont(QFont('Segoe UI',8))
        for fraction in (0,.5,1):
            y=bottom-(bottom-top)*fraction
            p.setPen(QColor(MUTED)); p.drawText(QRectF(0,y-10,62,20),Qt.AlignLeft|Qt.AlignVCenter,getattr(self,'axis_format',duration)(maximum*fraction))
            p.setPen(QPen(QColor('#304047'),1,Qt.DotLine)); p.drawLine(QPointF(left,y),QPointF(right,y))
        step=(right-left)/len(self.days); every=max(1,(len(self.days)+6)//7)
        for i,(day,seconds) in enumerate(self.days.items()):
            x=left+i*step; gap=min(6,step*.12)
            per_day=self.computer_segments.get(day,{})
            groups=[(identity,values) for identity,values in per_day.items() if sum(values.values())>0]
            if not groups and seconds>0: groups=[(None,self.segments.get(day,{}))]
            height=max(3,(bottom-top)*seconds/maximum)
            rail=min(5,max(.25,step*.12)) if multiple and groups else 0
            spacing=min(2,max(.1,step*.04)) if rail else 0
            width=min(46,max(.5,step-2*gap-rail-spacing))
            bar=QRectF(x+(step-width-rail-spacing)/2+rail+spacing,bottom-height,width,height)
            if not groups:
                p.fillRect(bar,QColor('#304249'))
            block_gap=min(3,height/(len(groups)*4)) if len(groups)>1 else 0
            filled=max(0,height-block_gap*max(0,len(groups)-1))
            cursor=float(bottom)
            for index,(identity,values) in enumerate(groups):
                group_bottom=cursor
                for key,value in values.items():
                    if value<=0 or seconds<=0: continue
                    segment_height=filled*value/seconds
                    rect=QRectF(bar.left(),cursor-segment_height,bar.width(),segment_height)
                    p.fillRect(rect,QColor(self.series[key][1]))
                    self.segment_regions.append((rect,day,key)); cursor-=segment_height
                group=QRectF(bar.left(),cursor,bar.width(),group_bottom-cursor)
                if day==self.selected:
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(TEXT),1.5)); p.drawRect(group)
                if identity is not None:
                    if rail: p.fillRect(QRectF(bar.left()-spacing-rail,cursor,rail,group.height()),QColor(self.device_colors[identity]))
                    self.computer_regions.append((QRectF(bar.left()-spacing-rail,cursor,bar.width()+spacing+rail,group.height()),day,identity))
                if index<len(groups)-1: cursor-=block_gap
            if seconds and step>=65:
                p.setPen(QColor(TEXT)); p.drawText(QRectF(x,bar.top()-21,step,18),Qt.AlignCenter,getattr(self,'axis_format',duration)(seconds))
            self.regions.append((QRectF(x,top,step,bottom-top),day,seconds))
            if i%every==0 or i==len(self.days)-1:
                p.setPen(QColor(TEXT if day==self.selected else MUTED)); p.drawText(QRectF(x-10,bottom+7,step+20,20),Qt.AlignCenter,day[5:])
        if not peak:
            p.fillRect(QRectF(left,top,right-left,bottom-top-4),QColor(PANEL))
            p.setPen(QColor(MUTED)); p.drawText(QRectF(left,top,right-left,bottom-top),Qt.AlignCenter,self.t(getattr(self,'empty_text','No recorded play time')))
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton: return
        for rect,day,seconds in self.regions:
            if rect.contains(event.position()): self.day_clicked.emit(day); break
    def tooltip_at(self,position):
        for rect,day,identity in self.computer_regions:
            if not rect.contains(position): continue
            values=self.computer_segments[day][identity]; seconds=sum(values.values())
            lines=['<b>'+escape(day)+' · '+escape(str(self.computer_names.get(identity,identity)))+' · '+duration(seconds)+'</b>']
            for key,value in values.items():
                if value<=0: continue
                name,color=self.series[key]; share=self.format_share(value,seconds)
                lines.append('<span style="color:'+color+'">●</span> '+escape(name)+' · '+duration(value)+' · '+share)
            return '<br>'.join(lines)
        for rect,day,seconds in self.regions:
            if not rect.contains(position): continue
            lines=['<b>'+escape(day)+' · '+duration(seconds)+'</b>']
            for key,value in self.segments.get(day,{}).items():
                if value<=0: continue
                name,color=self.series[key]; share=self.format_share(value,seconds)
                text=escape(name)+' · '+duration(value)+' · '+share
                lines.append('<span style="color:'+color+'">●</span> '+text)
            return '<br>'.join(lines)
        return ''
    def mouseMoveEvent(self,event):
        self.setToolTip(self.tooltip_at(event.position()))
