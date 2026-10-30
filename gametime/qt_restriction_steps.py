"""Compact per-budget action editor. Save joins the budget's existing draft."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from .qt_translation import QCheckBox
from .qt_widgets import label, button, NoWheelComboBox, NoWheelDoubleSpinBox
from .restriction_policy import new_plan, step, validate_plans, KINDS

NAMES = {'notify': 'Warning', 'minimize': 'Minimize application', 'cover': 'Cover and mute / block website',
         'close': 'Close application / browser tab'}


def edit_steps(editor):
    editor.collect()
    key = editor.current
    if not key: return
    app = editor.app; t = app.t
    window = app._dialog(t('Warnings and restrictions'), 760)
    layout = QVBoxLayout(window); layout.setContentsMargins(24, 22, 24, 22); layout.setSpacing(14)
    custom = QCheckBox(t('Use these steps')); custom.setChecked(key in editor.restriction_plans)
    layout.addWidget(custom)
    note = label(t('Each step runs before, at or after this budget expires.'), 'muted'); note.setWordWrap(True); layout.addWidget(note)
    body = QWidget(); rows = QVBoxLayout(body); rows.setContentsMargins(0, 0, 0, 0); rows.setAlignment(Qt.AlignTop)
    scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(body); scroll.setMinimumHeight(190)
    layout.addWidget(scroll); controls = []
    plan = deepcopy(editor.restriction_plans.get(key, new_plan()))
    if key not in editor.restriction_plans:
        plan['steps'] = [step('notify', -60, sound=True, popup=True)]
    def add(value=None):
        if len(controls) >= 20: return
        value = value or step('notify', popup=True)
        row = QWidget(); box = QVBoxLayout(row); box.setContentsMargins(0, 8, 0, 8)
        top = QHBoxLayout(); when = NoWheelComboBox()
        for title, number in (('Before expiry', -1), ('At expiry', 0), ('After expiry', 1)): when.addItem(t(title), number)
        when.setCurrentIndex(0 if value['offset'] < 0 else 2 if value['offset'] > 0 else 1)
        minutes = NoWheelDoubleSpinBox(); minutes.setDecimals(1); minutes.setRange(.1, 1440); minutes.setSuffix(' ' + t('min'))
        minutes.setValue(abs(value['offset']) / 60 or 1)
        kind = NoWheelComboBox()
        for name in KINDS: kind.addItem(t(NAMES[name]), name)
        kind.setCurrentIndex(KINDS.index(value['kind']))
        for widget in (when, minutes, kind): top.addWidget(widget)
        box.addLayout(top); bottom = QHBoxLayout()
        sound = QCheckBox(t('Sound')); sound.setChecked(value['sound'])
        popup = QCheckBox(t('Popup')); popup.setChecked(value['popup'])
        bottom.addWidget(sound); bottom.addWidget(popup); bottom.addStretch()
        entry = (value['id'], row, when, minutes, kind, sound, popup)
        def remove(): controls.remove(entry); row.setParent(None); row.deleteLater()
        bottom.addWidget(button(t('Remove'), remove, 'quiet')); box.addLayout(bottom)
        def changed():
            minutes.setVisible(when.currentData() != 0)
            sound.setVisible(kind.currentData() == 'notify'); popup.setVisible(kind.currentData() == 'notify')
        when.currentIndexChanged.connect(changed); kind.currentIndexChanged.connect(changed)
        controls.append(entry); rows.addWidget(row); changed()
    for value in sorted(plan['steps'], key=lambda s: s['offset']): add(value)
    layout.addWidget(button(t('Add step'), lambda: add()), 0, Qt.AlignLeft)
    extension = QHBoxLayout(); extension.addWidget(label(t('One-time save allowance (minutes)')))
    extra = NoWheelDoubleSpinBox(); extra.setDecimals(0); extra.setRange(0, 60); extra.setSpecialValueText(t('Disabled'))
    extra.setValue(plan['extension_minutes']); extension.addWidget(extra); layout.addLayout(extension)
    hint = label(t('Available once per budget per day. Applications close when the requested time ends.'), 'muted')
    hint.setWordWrap(True); layout.addWidget(hint)
    consent = QCheckBox(t('I understand that closing an application can lose unsaved work.'))
    consent.setChecked(plan['close_confirmed']); layout.addWidget(consent)
    hint = label(t('Exclusive fullscreen may require minimizing once. Protected applications are not forcibly closed.'), 'muted')
    hint.setWordWrap(True); layout.addWidget(hint)
    error = label('', 'danger'); error.setWordWrap(True); layout.addWidget(error)
    def save():
        result = new_plan(); result.update(extension_minutes=int(extra.value()), close_confirmed=consent.isChecked())
        result['steps'] = [dict(id=i, kind=k.currentData(), offset=w.currentData() * m.value() * 60,
                               sound=s.isChecked(), popup=p.isChecked()) for i, _, w, m, k, s, p in controls]
        try:
            if custom.isChecked(): validate_plans({key: result}); editor.restriction_plans[key] = result
            else: editor.restriction_plans.pop(key, None)
            editor.restriction_changed.add(key); window.accept()
            editor.controls(); app.set_status('Apply these steps with Save changes on the budget page.')
        except ValueError as exc: error.setText(t(str(exc)))
    actions = QHBoxLayout(); actions.addStretch()
    actions.addWidget(button(t('Save'), save, 'primary')); actions.addWidget(button(t('Cancel'), window.reject))
    layout.addLayout(actions); window.resize(760, 660); window.show()
    return window
