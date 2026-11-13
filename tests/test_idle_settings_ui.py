"""Native and browser settings share validated durable idle preferences."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
import test_qt_ui as fixture
from gametime.browser_control import BrowserControl


class IdleSettingsTests(TestCase):
    setUpClass=classmethod(fixture.QtInterfaceTests.setUpClass.__func__)
    setUp=fixture.QtInterfaceTests.setUp;tearDown=fixture.QtInterfaceTests.tearDown;pump=fixture.QtInterfaceTests.pump

    def test_native_save_cancel_failure_and_language_change(self):
        app=self.app;app.switch_page(2)
        self.assertFalse(app.idle_minutes.isEnabled())
        self.assertFalse(app.media_prevents_idle.isEnabled())
        app.pause_when_idle.setChecked(True);app.idle_minutes.setValue(7)
        app.media_prevents_idle.setChecked(True)
        self.assertTrue(app.media_prevents_idle.isEnabled())
        self.assertTrue(app.idle_minutes.isEnabled());self.assertTrue(app.settings_have_draft())
        app.cancel_general_settings();self.assertFalse(app.pause_when_idle.isChecked());self.assertEqual(app.idle_minutes.value(),5)
        self.assertFalse(app.media_prevents_idle.isChecked())
        app.pause_when_idle.setChecked(True);app.idle_minutes.setValue(7)
        app.media_prevents_idle.setChecked(True)
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')):self.assertFalse(app.save_settings(scope='general'))
        self.assertFalse(self.store.settings().pause_when_idle);self.assertTrue(app.pause_when_idle.isChecked())
        self.assertTrue(app.save_settings(scope='general'));self.assertTrue(self.store.settings().pause_when_idle)
        self.assertEqual(self.store.settings().idle_timeout_seconds,420)
        self.assertTrue(self.store.settings().media_prevents_idle)
        app.set_language('en');self.assertEqual(str(app.pause_when_idle.text()),'Pause time tracking when idle')
        self.assertEqual(app.idle_minutes.value(),7);self.assertTrue(app.pause_when_idle.isChecked())
        app.pause_when_idle.setChecked(False);self.assertTrue(app.save_settings(scope='general'))
        self.assertFalse(self.store.settings().pause_when_idle);self.assertEqual(self.store.settings().idle_timeout_seconds,420)
        self.assertTrue(self.store.settings().media_prevents_idle);self.assertFalse(app.media_prevents_idle.isEnabled())

    def test_browser_save_updates_native_controls_rejects_bad_values_and_snapshot_retains_policy(self):
        control=BrowserControl(self.app)
        self.assertTrue(control.settings_save(dict(pause_when_idle=True,idle_timeout_seconds=120,media_prevents_idle=True)))
        self.assertTrue(self.app.media_prevents_idle.isChecked())
        self.assertTrue(self.app.browser_continuity.snapshot('brave')['media_prevents_idle'])
        with self.assertRaises(ValueError):control.settings_save(dict(media_prevents_idle='yes'))
        self.assertTrue(self.app.pause_when_idle.isChecked());self.assertEqual(self.app.idle_minutes.value(),2)
        self.assertEqual(control.state({})['settings']['idle_timeout_seconds'],120)
        self.assertEqual(self.app.browser_continuity.snapshot('brave')['idle_timeout_seconds'],120)
        with self.assertRaises(ValueError):control.settings_save(dict(idle_timeout_seconds=-1))
        self.assertEqual(self.store.settings().idle_timeout_seconds,120)
        control.settings_save(dict(pause_when_idle=False))
        self.assertEqual(self.app.browser_continuity.snapshot('brave')['idle_timeout_seconds'],0)
