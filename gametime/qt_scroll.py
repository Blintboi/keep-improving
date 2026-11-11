"""Retain scroll offsets through Qt list rebuilds and their deferred layouts."""
from functools import wraps
from PySide6.QtCore import QTimer
from shiboken6 import isValid


def position(area):
    pending=getattr(area,'_pending_scroll',None)
    return pending[1] if pending else area.verticalScrollBar().value()


def restore(area,value):
    token=object();area._pending_scroll=(token,value)
    area.verticalScrollBar().setValue(value)
    def settled():
        if isValid(area) and getattr(area,'_pending_scroll',None)==(token,value):
            area.verticalScrollBar().setValue(value);area._pending_scroll=None
    QTimer.singleShot(0,settled)


def preserving(select):
    def decorate(function):
        @wraps(function)
        def run(self,*args,**kwargs):
            areas=select(self);areas=areas if isinstance(areas,(tuple,list)) else (areas,)
            saved=[(area,position(area)) for area in areas if area is not None]
            try:return function(self,*args,**kwargs)
            finally:
                for area,value in saved:
                    if isValid(area):restore(area,value)
        return run
    return decorate
