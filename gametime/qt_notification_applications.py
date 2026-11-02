"""Searchable application selection; choosing an item never launches it."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QFileDialog
from .qt_translation import QLineEdit
from .qt_widgets import label,button
from .notification_applications import choices
from .notification_rules import executable
from pathlib import Path


def choose(app,current,accept):
    t=app.t; dialog=app._dialog(t('Choose application'),760); dialog.resize(760,560)
    dialog.setWindowModality(Qt.WindowModal)
    box=QVBoxLayout(dialog); box.setContentsMargins(24,22,24,22); box.setSpacing(12)
    note=label(t('Choose a detected or registered application. Search by name or path.'),'muted'); note.setWordWrap(True); box.addWidget(note)
    search=QLineEdit(); search.setPlaceholderText(t('Search applications…')); search.setAccessibleName(t('Search applications…')); box.addWidget(search)
    listing=QListWidget(); listing.setAccessibleName(t('Applications')); listing.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); box.addWidget(listing,1)
    chosen=None
    for path,name in choices(app,current):
        item=QListWidgetItem(name); item.setData(Qt.UserRole,path); item.setToolTip(path); listing.addItem(item)
        if path.casefold()==current.casefold(): chosen=item
    empty=label(t('No applications found. Open an application once so it can be detected, or choose its executable.'),'muted'); empty.setWordWrap(True); box.addWidget(empty)
    path_label=QLineEdit(); path_label.setReadOnly(True); path_label.setAccessibleName(t('Selected application')); box.addWidget(path_label)
    error=label('','danger'); error.setWordWrap(True); box.addWidget(error)
    def confirm(path):
        try:
            executable(path)
            if not Path(path).is_file(): raise ValueError('Application file was not found.')
        except (ValueError,OSError) as exc:
            error.setText(t(str(exc)) if isinstance(exc,ValueError) else t('Application file was not found.')); return
        accept(path); dialog.accept()
    def pick():
        item=listing.currentItem()
        if item and not item.isHidden(): confirm(item.data(Qt.UserRole))
    def browse():
        path,_=QFileDialog.getOpenFileName(dialog,t('Choose application'),' ',t('Windows applications (*.exe)'))
        if path: confirm(path)
    actions=QHBoxLayout(); actions.addWidget(button(t('Choose executable…'),browse,'quiet')); actions.addStretch()
    actions.addWidget(button(t('Cancel'),dialog.reject)); select=button(t('Select application'),pick,'primary'); select.setDefault(True); select.setEnabled(False); actions.addWidget(select); box.addLayout(actions)
    def selection():
        item=listing.currentItem(); valid=item is not None and not item.isHidden()
        select.setEnabled(valid); path_label.setText(item.data(Qt.UserRole) if valid else ''); error.clear()
    def filter_rows(text):
        query=text.strip().casefold()
        for index in range(listing.count()):
            item=listing.item(index); item.setHidden(query not in (item.text()+' '+item.data(Qt.UserRole)).casefold())
        empty.setVisible(not any(not listing.item(i).isHidden() for i in range(listing.count())))
        selection()
    listing.currentItemChanged.connect(selection); listing.itemDoubleClicked.connect(lambda *_:pick()); search.textChanged.connect(filter_rows)
    if chosen: listing.setCurrentItem(chosen)
    filter_rows(''); dialog.show()
    from .qt_ui import dark_window
    dark_window(dialog); search.setFocus()
    return dialog
