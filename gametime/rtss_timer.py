"""Cached Unicode labels and digit sprites for the RTSS countdown.

Only the small ASCII image-tag sequence changes on a countdown tick. The atlas
is written once per appearance/label combination, never once per second.
"""
import atexit
from collections import OrderedDict
import math
from pathlib import Path
import re
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QFontMetrics,QImage,QPainter
from .overlay import countdown_font,countdown_size
from .qt_fullscreen_notifications import ansi_path

_cache=OrderedDict()


class Atlas:
    def __init__(self,font_size,color,opacity,caption,prefix):
        self.directory=tempfile.TemporaryDirectory(prefix='gtm-timer-')
        self.parts={}; drawings=[]; y=0; width=1
        for key,text,size in [('caption',caption,max(8,font_size*.55)),('prefix',prefix,max(8,font_size*.55)),
                              ('large','0123456789:',font_size),('small','0123456789:',max(8,font_size*.55))]:
            font=countdown_font(size); metrics=QFontMetrics(font); height=metrics.height()
            x=0
            parts=[(key,text)] if key in ('caption','prefix') else [(key+c,c) for c in text]
            for name,value in parts if text else []:
                w=metrics.horizontalAdvance(value)
                self.parts[name]=(x,y,w,height); drawings.append((x,y+metrics.ascent(),value,font))
                x+=w+2
            width=max(width,x); y+=height+2
        side=2**math.ceil(math.log2(max(width,y)))
        image=QImage(side,side,QImage.Format_ARGB32_Premultiplied); image.fill(Qt.transparent)
        painter=QPainter(image); painter.setRenderHint(QPainter.TextAntialiasing)
        pen=QColor(color); pen.setAlphaF(max(.25,min(1,opacity))); painter.setPen(pen)
        for x,y,text,font in drawings:
            painter.setFont(font); painter.drawText(x,y,text)
        painter.end()
        path=Path(self.directory.name)/'timer.png'
        if not image.save(str(path),'PNG'): raise OSError('Could not create countdown image.')
        self.path=ansi_path(path)
        self.height=QFontMetrics(countdown_font(font_size)).height()
        self.small=QFontMetrics(countdown_font(max(8,font_size*.55))).height()
        self.canvas_width=countdown_size(font_size,caption=caption,detail=prefix+'00:00:00' if prefix else '').width()

    def width(self,parts): return sum(self.parts[key][2] for key in parts)

    def line(self,parts,x,y):
        tags=[]
        for key in parts:
            sx,sy,width,height=self.parts[key]
            tags.append(f'<P={x},{y}><I={width},{height},{sx},{sy},{width},{height}>'); x+=width
        return ''.join(tags)

    def close(self):
        try: self.directory.cleanup()
        except OSError: pass


def countdown(remaining,font_size,color,opacity,caption,detail):
    match=re.search(r'\d{2,}:\d{2}(?::\d{2})?$',detail)
    duration=match.group() if match else ''
    prefix=detail[:match.start()] if match else detail
    key=(font_size,color,opacity,caption,prefix)
    atlas=_cache.get(key)
    if atlas is None:
        atlas=Atlas(*key); _cache[key]=atlas
        if len(_cache)>16: _cache.popitem(last=False)[1].close()
    _cache.move_to_end(key)
    seconds=max(0,math.ceil(remaining)); text=f'{seconds//3600:02d}:{seconds%3600//60:02d}:{seconds%60:02d}'
    width=atlas.canvas_width; y=4
    result=f'<C=FFFFFFFF><LI="{atlas.path}">'
    for parts,height in ((['caption'] if caption else [],atlas.small+2),
                         (['large'+c for c in text],atlas.height),
                         ((['prefix'] if prefix else [])+['small'+c for c in duration],atlas.small+2)):
        if not parts: continue
        result+=atlas.line(parts,max(4,(width-atlas.width(parts))//2),y); y+=height
    return result+'<C>'


def clear():
    for atlas in _cache.values(): atlas.close()
    _cache.clear()


atexit.register(clear)
