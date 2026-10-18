"""Qt presentation primitives. Artwork comes only from local installed-game assets."""
import configparser
import hashlib
import json
from pathlib import Path
from .model import within, helper
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer, QFileInfo
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QLinearGradient, QRegion
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QGridLayout, QFileIconProvider, QToolTip

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
QFrame#Selected { background: #1a2529; border: 1px solid #30423f; border-radius: 15px; }
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
QPushButton[role="preset"]:checked { background: #24483b; color: #a1f0d2; border-color: #396451; }
QLineEdit, QComboBox, QDoubleSpinBox { background: #182126; border: 1px solid #2e3b42; border-radius: 10px; padding: 10px 12px; selection-background-color: #315e4e; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #7de5bf; }
QLineEdit { color: #e5eeec; }
QComboBox { padding-right: 28px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #1c282d; border: 1px solid #3c504e; selection-background-color: #315343; padding: 5px; outline: none; }
QScrollArea, QStackedWidget { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 2px; }
QScrollBar::handle:vertical { background: #35474c; border-radius: 3px; min-height: 35px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
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

def duration(seconds):
    seconds=max(0,int(seconds))
    return f'{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}'

def glyph(name, color=ACCENT, size=20):
    pix=QPixmap(size,size); pix.fill(Qt.transparent)
    p=QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    p.scale(size/24,size/24); p.setPen(QPen(QColor(color),1.8,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    if name=='library':
        for x,y in ((3,3),(14,3),(3,14),(14,14)): p.drawRoundedRect(QRectF(x,y,7,7),2,2)
    elif name=='stats':
        p.drawLine(4,20,21,20)
        for x,y in ((7,11),(13,6),(19,3)): p.drawLine(x,16,x,y)
    elif name=='search':
        p.drawEllipse(QRectF(4,3,12,12)); p.drawLine(15,15,21,21)
    elif name=='settings':
        p.drawEllipse(QRectF(5,5,14,14)); p.drawEllipse(QRectF(9,9,6,6))
        for x1,y1,x2,y2 in ((12,2,12,5),(12,19,12,22),(2,12,5,12),(19,12,22,12),(5,5,7,7),(17,17,19,19),(5,19,7,17),(17,7,19,5)): p.drawLine(x1,y1,x2,y2)
    elif name=='plus': p.drawLine(12,5,12,19); p.drawLine(5,12,19,12)
    elif name=='hide': p.drawRoundedRect(QRectF(4,4,16,16),3,3); p.drawLine(8,15,16,15)
    elif name=='bell':
        p.drawArc(QRectF(6,4,12,14),0,180*16); p.drawLine(6,11,5,18); p.drawLine(18,11,19,18); p.drawLine(5,18,19,18); p.drawArc(QRectF(9,17,6,5),180*16,180*16)
    elif name=='dots':
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        for x in (5,12,19): p.drawEllipse(QRectF(x-1.5,10.5,3,3))
    elif name=='play':
        p.setBrush(QColor(color)); p.setPen(Qt.NoPen)
        path=QPainterPath(); path.moveTo(8,5); path.lineTo(20,12); path.lineTo(8,19); path.closeSubpath(); p.drawPath(path)
    p.end()
    return QIcon(pix)

class BudgetRing(QWidget):
    def __init__(self):
        super().__init__(); self.ratio=0; self.setFixedSize(66,66)
    def set_ratio(self,value): self.ratio=max(0,min(1,value)); self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#2e4941'),5)); p.drawEllipse(QRectF(7,7,52,52))
        p.setPen(QPen(QColor(ACCENT if self.ratio<.84 else '#f1c581' if self.ratio<1 else '#f09f9f'),5,Qt.SolidLine,Qt.RoundCap))
        p.drawArc(QRectF(7,7,52,52),90*16,-int(self.ratio*360*16))
        p.setPen(QPen(QColor('#bdf2db'),1.7,Qt.SolidLine,Qt.RoundCap)); p.drawLine(33,20,33,33); p.drawLine(33,33,42,38)

class LocalArtwork:
    def __init__(self, data_dir, roots):
        self.data_dir=Path(data_dir); self.roots=list(roots); self.cache={}; self.links={}
        self.provider=QFileIconProvider()
    def refresh_links(self, root):
        try:
            state=json.loads((Path(root)/'.gametime-hub.json').read_text(encoding='utf-8'))
            self.links={row['gid']:row['path'] for row in state.get('links',[]) if row.get('role')=='launch'}
        except (OSError,ValueError,KeyError,TypeError,AttributeError): self.links={}
    def artwork(self,game,rules):
        key=(game.id,game.root,game.metadata,self.links.get(game.id))
        if key in self.cache: return self.cache[key]
        poster=None
        if game.source=='Steam':
            appid=game.id.partition(':')[2]
            if appid.isascii() and appid.isdigit():
                for root in self.roots:
                    folder=Path(root)/'appcache/librarycache'
                    candidates=[folder/(appid+'_header.jpg'),folder/(appid+'_library_hero.jpg'),folder/(appid+'_library_600x900.jpg')]
                    nested=folder/appid
                    if nested.is_dir():
                        candidates+=list(nested.glob('*header*'))[:8]+list(nested.glob('*library_600x900*'))[:8]
                    for path in candidates:
                        if path.is_file():
                            image=QPixmap(str(path))
                            if not image.isNull(): poster=image.scaled(640,420,Qt.KeepAspectRatio,Qt.SmoothTransformation); break
                    if poster: break
        icon=QIcon()
        # Prefer real game artwork to a generic Windows internet-shortcut icon.
        executable=next((p for p,gid in rules.items() if gid==game.id and Path(p).is_file()),None)
        if not executable and game.source=='Epic' and game.metadata.endswith('.item'):
            try:
                manifest=json.loads(Path(game.metadata).read_text(encoding='utf-8-sig'))
                candidate=Path(game.root)/manifest.get('LaunchExecutable','')
                if within(candidate.resolve(),Path(game.root).resolve()) and candidate.suffix.lower()=='.exe' and not helper(candidate) and candidate.is_file(): executable=str(candidate)
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
        pix=icon.pixmap(96,96) if not icon.isNull() else None
        if pix and not pix.isNull():
            bounds=QRegion(pix.mask()).boundingRect()
            if not bounds.isEmpty(): pix=pix.copy(bounds)
        result=(poster,pix)
        self.cache[key]=result
        return result

class GameCard(QFrame):
    selected=Signal(str)
    launched=Signal(str)
    def __init__(self,game,t):
        super().__init__(); self.game=game; self.t=t; self.chosen=False; self.hovered=False; self.seconds=0; self.art=(None,None)
        self.setFixedHeight(232); self.setMinimumWidth(190); self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus); self.setAccessibleName(game.name)
        self.play=button('',lambda:self.launched.emit(self.game.id)); self.play.setIcon(glyph('play','#b8f4db',17)); self.play.setFixedSize(34,34)
        self.play.setParent(self); self.play.setToolTip(t('▶ Play')); self.play.setAccessibleName(t('▶ Play')+' '+game.name)
        self.play.setStyleSheet('QPushButton {background:#28463c; border:1px solid #3b6352; border-radius:17px; padding:0;} QPushButton:hover {background:#3b6854;}')
        self.setToolTip(game.name)
    def resizeEvent(self,event): self.play.move(self.width()-49,183)
    def set_state(self,seconds,chosen,enabled=True):
        if self.seconds!=seconds or self.chosen!=chosen: self.seconds=seconds; self.chosen=chosen; self.update()
        self.play.setEnabled(enabled and self.game.installed)
    def enterEvent(self,event): self.hovered=True; self.update()
    def leaveEvent(self,event): self.hovered=False; self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton: self.selected.emit(self.game.id); self.setFocus()
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton: self.launched.emit(self.game.id)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter): self.launched.emit(self.game.id)
        elif event.key()==Qt.Key_Space: self.selected.emit(self.game.id)
        else: super().keyPressEvent(event)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(1,1,self.width()-2,self.height()-2); clip=QPainterPath(); clip.addRoundedRect(rect,15,15)
        p.setClipPath(clip); p.fillRect(rect,QColor('#202d33' if self.hovered else PANEL))
        poster,icon=self.art
        if poster:
            # Fit the complete image into the shared art area without stretching
            # or cropping portrait/landscape artwork. The panel fills spare space.
            art_area=QRectF(0,0,self.width(),156)
            fitted=poster.scaled(int(art_area.width()),int(art_area.height()),Qt.KeepAspectRatio,Qt.SmoothTransformation)
            p.fillRect(art_area,QColor('#152329'))
            p.drawPixmap(int((self.width()-fitted.width())/2),int((156-fitted.height())/2),fitted)
        else:
            seed=hashlib.sha256(self.game.name.encode()).digest(); color=QColor.fromHsv(seed[0]*359//255,105,77)
            grad=QLinearGradient(0,0,self.width(),160); grad.setColorAt(0,color); grad.setColorAt(1,QColor('#14262c'))
            p.fillRect(QRectF(0,0,self.width(),160),grad)
            p.setPen(Qt.NoPen); p.setBrush(QColor(255,255,255,9)); p.drawEllipse(QRectF(self.width()-160,-76,240,240))
            p.setBrush(QColor(255,255,255,6)); p.drawEllipse(QRectF(-60,45,180,180))
            if icon and not icon.isNull():
                scaled=icon.scaled(80,80,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                p.drawPixmap(int((self.width()-scaled.width())/2),int(82-scaled.height()/2),scaled)
            else:
                p.setPen(QColor('#c1d9d7')); p.setFont(QFont('Segoe UI',30,QFont.Bold))
                initials=''.join(part[0] for part in self.game.name.split()[:2]).upper()
                p.drawText(QRectF(0,38,self.width(),88),Qt.AlignCenter,initials)
        fade=QLinearGradient(0,68,0,166); fade.setColorAt(0,QColor(25,33,38,0)); fade.setColorAt(1,QColor(PANEL)); p.fillRect(QRectF(0,60,self.width(),108),fade)
        source=self.t('Manual') if self.game.source=='Kézi' else self.t('Games folder') if self.game.source=='Games' else self.game.source
        p.setFont(QFont('Segoe UI',8,QFont.DemiBold)); badge_width=p.fontMetrics().horizontalAdvance(source)+18
        p.setPen(Qt.NoPen); p.setBrush(QColor(12,22,25,205)); p.drawRoundedRect(QRectF(12,12,badge_width,23),7,7)
        p.setPen(QColor('#c5d9d5')); p.drawText(QRectF(21,12,badge_width-12,23),Qt.AlignVCenter,source)
        p.setFont(QFont('Segoe UI',11,QFont.DemiBold)); p.setPen(QColor(TEXT))
        p.drawText(QRectF(15,148,self.width()-30,39),Qt.TextWordWrap|Qt.AlignTop,self.game.name)
        p.setFont(QFont('Segoe UI',9)); p.setPen(QColor(MUTED))
        caption=self.t('Today')+'  '+duration(self.seconds) if self.game.installed else self.t('Removed')
        p.drawText(QRectF(15,194,self.width()-72,20),Qt.AlignVCenter,caption)
        p.setClipping(False); p.setBrush(Qt.NoBrush); p.setPen(QPen(QColor(ACCENT if self.chosen else '#3b514e' if self.hovered else '#2b393f'),1.6 if self.chosen else 1))
        p.drawRoundedRect(rect,15,15)

class CardGrid(QWidget):
    def __init__(self):
        super().__init__(); self.cards=[]; self.columns=0
        self.grid=QGridLayout(self); self.grid.setContentsMargins(0,0,8,0); self.grid.setSpacing(16); self.grid.setAlignment(Qt.AlignTop)
    def set_cards(self,cards):
        for old in self.cards: self.grid.removeWidget(old); old.deleteLater()
        self.cards=cards; self.columns=0; self.reflow()
    def resizeEvent(self,event): self.reflow()
    def reflow(self):
        if not hasattr(self,'grid'): return
        columns=max(1,(self.width()+16)//238)
        if columns==self.columns: return
        for card in self.cards: self.grid.removeWidget(card)
        for i,card in enumerate(self.cards): self.grid.addWidget(card,i//columns,i%columns)
        for col in range(max(columns,self.columns)): self.grid.setColumnStretch(col,1 if col<columns else 0)
        self.columns=columns

class DailyChart(QWidget):
    day_clicked=Signal(str)
    def __init__(self):
        super().__init__(); self.days={}; self.selected=None; self.regions=[]; self.setMinimumHeight(175); self.setMouseTracking(True)
    def set_days(self,days,selected=None): self.days=days; self.selected=selected; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing); self.regions=[]
        if not self.days: return
        maximum=max(1,max(self.days.values())); left,right,top,bottom=64,self.width()-12,18,self.height()-27
        p.setFont(QFont('Segoe UI',8)); p.setPen(QColor('#73898b'))
        p.drawText(QRectF(0,top-9,60,20),Qt.AlignLeft,duration(maximum) if maximum>1 else '00:00:00')
        p.drawText(QRectF(0,bottom-10,60,20),Qt.AlignLeft,'00:00:00')
        p.setPen(QPen(QColor('#2b3a40'),1,Qt.DotLine)); p.drawLine(left,top,right,top); p.drawLine(left,bottom,right,bottom)
        step=(right-left)/len(self.days); every=max(1,(len(self.days)+6)//7)
        for i,(day,seconds) in enumerate(self.days.items()):
            x=left+i*step; height=max(3,(bottom-top)*seconds/maximum); gap=min(6,step/5)
            bar=QRectF(x+gap,bottom-height,max(.5,step-gap*2),height)
            p.setPen(Qt.NoPen); p.setBrush(QColor(ACCENT if day==self.selected else '#68b4ab' if seconds else '#304249'))
            p.drawRoundedRect(bar,min(4,bar.width()/3),min(4,bar.width()/3))
            self.regions.append((QRectF(x,top,step,bottom-top),day,seconds))
            if i%every==0 or i==len(self.days)-1:
                p.setPen(QColor(MUTED)); p.drawText(QRectF(x-10,bottom+7,step+20,20),Qt.AlignCenter,day[5:])
    def mousePressEvent(self,event):
        for rect,day,seconds in self.regions:
            if rect.contains(event.position()): self.day_clicked.emit(day); break
    def mouseMoveEvent(self,event):
        for rect,day,seconds in self.regions:
            if rect.contains(event.position()): self.setToolTip(day+'  ·  '+duration(seconds)); return
        self.setToolTip('')
