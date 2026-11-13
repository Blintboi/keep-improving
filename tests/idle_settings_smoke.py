"""Render only a disposable native Settings window in HU/EN."""
import os,sys
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from test_qt_ui import QtInterfaceTests
from gametime.qt_widgets import HelpText
from PySide6.QtGui import QFontDatabase

report=Path(sys.argv[1]);report.mkdir(parents=True,exist_ok=True)
QtInterfaceTests.setUpClass()
for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','segoeuii.ttf'):
    assert QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))>=0
case=QtInterfaceTests()
case.enterContext(patch('gametime.overlay.CountdownOverlay._native_styles'))
case.setUp()
try:
    app=case.app;app.switch_page(2);app.show()
    for language in ('hu','en'):
        app.set_language(language)
        for width,height in ((1280,900),(1000,700)):
            app.resize(width,height);case.pump(.05)
            assert app.pause_when_idle.isVisible() and app.idle_minutes.isVisible()
            app.pause_when_idle.setChecked(True);app.idle_minutes.setValue(5);app.media_prevents_idle.setChecked(True)
            assert app.grab().save(str(report/f'settings-{language}-{width}.png'))
        help=next(w for w in app.settings_sections['general'].findChildren(HelpText) if 'Focus timers' in w.text() or 'fókuszidőzítők' in w.text())
        help.setExpanded(True);case.pump(.05)
        assert app.grab().save(str(report/f'help-{language}.png'));help.setExpanded(False)
    from gametime.wellbeing import target
    for language in ('hu','en'):
        app.set_language(language);app.open_budget(member=target('site','example.com'))
        editor=app.budget_editor;editor.steps.add_step.click();card=editor.steps.cards[-1]
        card.time_mode.setCurrentIndex(card.time_mode.findData('sessions'));card.choices.enabled.setChecked(True)
        card.choices.remember_minutes.setValue(15)
        for width,height in ((1280,900),(1000,700)):
            app.resize(width,height);case.pump(.05);app.budget_scroll.ensureWidgetVisible(card.choices.remember_minutes);case.pump(.05)
            assert card.choices.remember_minutes.isVisible()
            assert app.grab().save(str(report/f'choices-{language}-{width}.png'))
        app.save_budgets();app.budget_editor.cancel_edit()
    print('Native HU/EN, 1280/1000 widths and contextual Help rendered.')
finally:case.tearDown();case.doCleanups()
