"""Opening-choice settings inside an existing daily session-limit card."""
from copy import deepcopy
import uuid
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy
from .qt_translation import QCheckBox, QLineEdit
from .qt_widgets import label, button, NoWheelDoubleSpinBox, NoWheelComboBox
from .session_choices import defaults


class ChoiceFields(QWidget):
    def __init__(self, card):
        super().__init__(); self.card = card; self.saved = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        t = card.owner.app.t
        box = QVBoxLayout(self); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(10)
        self.enabled = QCheckBox(t('Ask why when opening')); box.addWidget(self.enabled)
        self.body = QWidget(); self.body_box = QVBoxLayout(self.body); self.body_box.setContentsMargins(0, 0, 0, 0)
        self.body_box.addWidget(label(t('Session allowance'), 'muted'))
        self.allocation = NoWheelComboBox(); self.allocation.setAccessibleName(t('Session allowance'))
        self.allocation.addItem(t('Shared allowance'),'shared');self.allocation.addItem(t('Separate allowance per member'),'activity')
        self.body_box.addWidget(self.allocation)
        allocation_note=label(t('Shared: all members use the same count for each answer. Separate: each application or website gets the full count for each answer.'),'muted')
        allocation_note.setWordWrap(True);self.body_box.addWidget(allocation_note)
        self.body_box.addWidget(label(t('Question'), 'muted'))
        self.question = QLineEdit(); self.question.setMaxLength(180); self.question.setAccessibleName(t('Opening question'))
        self.body_box.addWidget(self.question)
        self.rows = QWidget(); self.rows_box = QVBoxLayout(self.rows); self.rows_box.setContentsMargins(0, 0, 0, 0)
        self.body_box.addWidget(self.rows)
        self.add = button(t('Add choice'), self.add_choice, 'quiet'); self.body_box.addWidget(self.add)
        note = label(t('Each choice has its own allowance. Exhausted choices stay visible but cannot be selected. Other budget rules still apply.'), 'muted')
        note.setWordWrap(True); self.body_box.addWidget(note)
        scope = label(t('Choice allowances are counted on this computer and reset with this budget. Keep the desktop application running to show choices over applications and websites.'), 'muted')
        scope.setWordWrap(True); self.body_box.addWidget(scope); box.addWidget(self.body)
        self.enabled.setChecked(bool(card.value.get('session_choice')))
        self.enabled.toggled.connect(self.toggle)
        self.question.textChanged.connect(self.question_changed)
        self.allocation.currentIndexChanged.connect(self.allocation_changed)
        self.option_widgets = []; self.rebuild()

    def changed(self): self.card.owner.changed()

    def allocation_changed(self):
        if self.card.value.get('session_choice'):
            self.card.value['session_choice']['allocation']=self.allocation.currentData();self.changed()

    def question_changed(self, value):
        if self.card.value.get('session_choice'):
            self.card.value['session_choice']['question'] = value; self.changed()

    def toggle(self, enabled):
        if enabled:
            self.card.value['session_choice'] = deepcopy(self.saved) if self.saved else defaults(self.card.owner.app.t)
        else:
            self.saved = self.card.value.pop('session_choice', None)
        self.rebuild(); self.card.update_controls(); self.changed()

    def suspend(self):
        if self.enabled.isChecked(): self.enabled.setChecked(False)

    def rebuild(self):
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self.option_widgets = []; value = self.card.value.get('session_choice')
        self.body.setVisible(bool(value))
        if not value: return
        t = self.card.owner.app.t
        blocked=self.allocation.blockSignals(True);self.allocation.setCurrentIndex(self.allocation.findData(value.get('allocation','shared')));self.allocation.blockSignals(blocked)
        blocked = self.question.blockSignals(True); self.question.setText(value['question']); self.question.blockSignals(blocked)
        for index, option in enumerate(value['options']):
            row = QWidget(); layout = QVBoxLayout(row); layout.setContentsMargins(0, 6, 0, 6)
            heading = QHBoxLayout()
            name = QLineEdit(option['label']); name.setMaxLength(120); name.setAccessibleName(t('Choice name {number}', number=index+1))
            heading.addWidget(name, 1)
            remove = button(t('Remove choice'), lambda checked=False, identity=option['id']: self.remove_choice(identity), 'quiet')
            remove.setEnabled(len(value['options']) > 2); heading.addWidget(remove); layout.addLayout(heading)
            allowance = QHBoxLayout(); allowance.setSpacing(12)
            unlimited = QCheckBox(t('Unlimited')); unlimited.setChecked(option['limit'] is None); allowance.addWidget(unlimited)
            caption = label(t('Daily sessions'), 'muted'); allowance.addWidget(caption)
            count = NoWheelDoubleSpinBox(); count.setDecimals(0); count.setRange(1, 10000); count.setKeyboardTracking(False)
            count.setAccessibleName(t('Daily allowance for choice {number}', number=index+1)); count.setValue(option['limit'] or 2)
            count.setEnabled(option['limit'] is not None); caption.setEnabled(option['limit'] is not None)
            allowance.addWidget(count); allowance.addStretch(); layout.addLayout(allowance)
            # Attach controls before showing them, otherwise Qt briefly creates
            # separate native windows when rebuilding the editor (also on save).
            count.setVisible(option['limit'] is not None); caption.setVisible(option['limit'] is not None)
            name.textChanged.connect(lambda text, option=option: self.rename(option, text))
            count.valueChanged.connect(lambda amount, option=option: self.limit_changed(option, amount))
            unlimited.toggled.connect(lambda checked, option=option, count=count, caption=caption: self.unlimited_changed(option, checked, count, caption))
            self.option_widgets.append((name, unlimited, count, remove)); self.rows_box.addWidget(row)
        self.add.setEnabled(len(value['options']) < 8)

    def rename(self, option, text): option['label'] = text; self.changed()

    def limit_changed(self, option, amount):
        if option['limit'] is not None: option['limit'] = int(amount); self.changed()

    def unlimited_changed(self, option, checked, count, caption):
        option['limit'] = None if checked else int(count.value())
        count.setEnabled(not checked); caption.setEnabled(not checked)
        count.setVisible(not checked); caption.setVisible(not checked); self.changed()

    def add_choice(self):
        options = self.card.value['session_choice']['options']
        if len(options) >= 8: return
        options.append(dict(id=uuid.uuid4().hex, label=str(self.card.owner.app.t('New choice')), limit=2))
        self.rebuild(); self.changed()

    def remove_choice(self, identity):
        options = self.card.value['session_choice']['options']
        if len(options) <= 2: return
        options[:] = [item for item in options if item['id'] != identity]
        self.rebuild(); self.changed()
