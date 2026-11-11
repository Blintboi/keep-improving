"""A live, filter-independent view of a budget member selection."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QListWidget,QListWidgetItem
from .qt_widgets import label


class SelectedMembers(QWidget):
    def __init__(self,listing,t,parent=None):
        super().__init__(parent); self.source=listing; self.t=t; self.rows={}
        box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); box.setSpacing(10)
        self.heading=label('','section'); box.addWidget(self.heading)
        hint=label(t('Uncheck an item to remove it.'),'muted'); hint.setWordWrap(True); box.addWidget(hint)
        self.listing=QListWidget(); self.listing.setAccessibleName(t('Selected budget members'))
        self.listing.setStyleSheet(listing.styleSheet()); box.addWidget(self.listing,1)
        self.empty=label(t('No members selected yet.'),'muted'); self.empty.setWordWrap(True); box.addWidget(self.empty)
        listing.itemChanged.connect(self.update_selection)
        self.listing.itemChanged.connect(self.uncheck)
        self.update_selection()

    def update_selection(self,*args):
        chosen={}
        for index in range(self.source.count()):
            item=self.source.item(index)
            if item.checkState()==Qt.Checked:
                member=item.data(Qt.UserRole); chosen[(member['kind'],member['value'])]=item
        blocked=self.listing.blockSignals(True)
        try:
            for key in list(self.rows):
                if key not in chosen:
                    self.listing.takeItem(self.listing.row(self.rows.pop(key)))
            for key,source in chosen.items():
                if key in self.rows: continue
                item=QListWidgetItem(source.text()); item.setToolTip(source.toolTip())
                item.setData(Qt.UserRole,source.data(Qt.UserRole))
                item.setFlags(item.flags()|Qt.ItemIsUserCheckable); item.setCheckState(Qt.Checked)
                self.listing.addItem(item); self.rows[key]=item
        finally: self.listing.blockSignals(blocked)
        self.heading.setText(self.t('Selected ({count})',count=len(chosen)))
        self.empty.setVisible(not chosen)

    def uncheck(self,item):
        if item.checkState()!=Qt.Unchecked: return
        member=item.data(Qt.UserRole)
        for index in range(self.source.count()):
            source=self.source.item(index)
            if source.data(Qt.UserRole)==member:
                source.setCheckState(Qt.Unchecked); return
