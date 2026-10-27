"""Retain translation keys on UI text; update existing widgets in place.

User-entered names and paths remain ordinary strings and are never translated.
"""
from PySide6 import QtWidgets as W
from PySide6.QtCore import QPoint,QRect
from .i18n import tr


class UiText(str):
    def __new__(cls,key,language,values=None,parts=None):
        values=values or {}
        if parts is None:
            text=tr(key,language,**{k:v.in_language(language) if isinstance(v,UiText) else v for k,v in values.items()})
        else:
            text=''.join(str(p.in_language(language)) if isinstance(p,UiText) else p for p in parts)
        result=super().__new__(cls,text)
        result.key,result.language,result.values,result.parts=key,language,values,parts
        return result

    def in_language(self,language): return UiText(self.key,language,self.values,self.parts)
    def __add__(self,other):
        if not isinstance(other,str): return NotImplemented
        return UiText(None,self.language,parts=(self,other))
    def __radd__(self,other):
        if not isinstance(other,str): return NotImplemented
        return UiText(None,self.language,parts=(other,self))


def ui_text(key,language,**values):
    if isinstance(key,UiText) and not values: return key.in_language(language)
    return UiText(key,language,values)


class _Translated:
    def __init__(self,*args,**kwargs):
        self._ui_strings={}
        super().__init__(*args,**kwargs)
        text=args[0] if args else kwargs.get('text')
        if isinstance(text,UiText): self._ui_strings['setText']=text

    def _remember(self,setter,value):
        if isinstance(value,UiText): self._ui_strings[setter]=value
        else: self._ui_strings.pop(setter,None)

    def setText(self,value):
        self._remember('setText',value); super().setText(value)
    def setToolTip(self,value):
        self._remember('setToolTip',value); super().setToolTip(value)
    def setAccessibleName(self,value):
        self._remember('setAccessibleName',value); super().setAccessibleName(value)
    def setPlaceholderText(self,value):
        self._remember('setPlaceholderText',value); super().setPlaceholderText(value)
    def setWindowTitle(self,value):
        self._remember('setWindowTitle',value); super().setWindowTitle(value)

    def retranslate(self,language):
        blocked=self.blockSignals(True)
        try:
            for setter,value in list(self._ui_strings.items()): getattr(self,setter)(value.in_language(language))
            self._retranslate_extra(language)
        finally: self.blockSignals(blocked)

    def _retranslate_extra(self,language): pass


class QLabel(_Translated,W.QLabel): pass
class QPushButton(_Translated,W.QPushButton): pass
class QCheckBox(_Translated,W.QCheckBox): pass
class QToolButton(_Translated,W.QToolButton): pass
class QDialog(_Translated,W.QDialog): pass
class QDoubleSpinBox(_Translated,W.QDoubleSpinBox): pass
class QTimeEdit(_Translated,W.QTimeEdit): pass
class QSlider(_Translated,W.QSlider): pass
class QPlainTextEdit(_Translated,W.QPlainTextEdit): pass


class QLineEdit(_Translated,W.QLineEdit):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.textEdited.connect(lambda:self._ui_strings.pop('setText',None))


class QComboBox(_Translated,W.QComboBox):
    def __init__(self,*args,**kwargs):
        self._ui_items={}; super().__init__(*args,**kwargs)
        # The popup container is outside the item view and keeps a native white background on Windows.
        self.view().window().setStyleSheet('QComboBoxPrivateContainer { background: #1c282d; }')
        self.setSizeAdjustPolicy(W.QComboBox.AdjustToContents)
    def showPopup(self):
        super().showPopup()
        popup=self.view().window(); owner=self.window()
        bounds=QRect(owner.mapToGlobal(QPoint(0,0)),owner.size())
        screen=self.screen()
        if screen: bounds=bounds.intersected(screen.availableGeometry())
        if bounds.isEmpty(): return
        anchor=self.mapToGlobal(QPoint(0,0))
        below=max(0,bounds.bottom()-(anchor.y()+self.height())+1)
        above=max(0,anchor.y()-bounds.top())
        height=popup.height()
        if height<=below:
            y=anchor.y()+self.height()
        elif height<=above:
            y=anchor.y()-height
        elif above>below:
            height=min(height,above); y=anchor.y()-height
        else:
            height=min(height,below); y=anchor.y()+self.height()
        width=min(popup.width(),bounds.width())
        if height<=0 or width<=0: return
        popup.resize(width,height)
        x=max(bounds.left(),min(anchor.x(),bounds.right()-width+1))
        popup.move(x,max(bounds.top(),min(y,bounds.bottom()-height+1)))
    def addItem(self,*args,**kwargs):
        index=self.count(); super().addItem(*args,**kwargs)
        value=next((value for value in args if isinstance(value,UiText)),kwargs.get('text'))
        if isinstance(value,UiText): self._ui_items[index]=value
    def addItems(self,values):
        for value in values: self.addItem(value)
    def setItemText(self,index,value):
        if isinstance(value,UiText): self._ui_items[index]=value
        else: self._ui_items.pop(index,None)
        super().setItemText(index,value)
    def clear(self): self._ui_items.clear(); super().clear()
    def removeItem(self,index):
        self._ui_items={i-(i>index):v for i,v in self._ui_items.items() if i!=index}
        super().removeItem(index)
    def _retranslate_extra(self,language):
        for index,value in list(self._ui_items.items()):
            if index<self.count(): self.setItemText(index,value.in_language(language))


class QTableWidgetItem(W.QTableWidgetItem):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._ui_text=args[0] if args and isinstance(args[0],UiText) else None
    def setText(self,value):
        self._ui_text=value if isinstance(value,UiText) else None; super().setText(value)


class QTableWidget(_Translated,W.QTableWidget):
    def setHorizontalHeaderLabels(self,values):
        self._ui_headers=list(values); super().setHorizontalHeaderLabels(values)
    def _retranslate_extra(self,language):
        if hasattr(self,'_ui_headers'):
            self.setHorizontalHeaderLabels([v.in_language(language) if isinstance(v,UiText) else v for v in self._ui_headers])
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                item=self.item(row,col)
                value=getattr(item,'_ui_text',None)
                if value is not None: item.setText(value.in_language(language))


def retranslate_widgets(root,language):
    for widget in (root,*root.findChildren(W.QWidget)):
        if isinstance(widget,_Translated): widget.retranslate(language)
