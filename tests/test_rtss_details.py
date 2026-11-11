"""The optional RTSS labels never change timer selection or desktop/tray detail."""
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_timer_views as timer_fixture
from gametime.model import Settings
from gametime.store import Store
from gametime.wellbeing import target
from gametime.overlay import countdown_size


class DetailsSettingsTests(unittest.TestCase):
    def test_default_and_old_profile_stay_detailed_and_false_survives_restart(self):
        self.assertTrue(Settings().overlay_rtss_details)
        for invalid in (0,1,'false',None):
            with self.subTest(value=invalid),self.assertRaises(ValueError): replace(Settings(),overlay_rtss_details=invalid).validate()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'usage.sqlite3'
            with closing(Store(path)) as store:
                with store.db: store.db.execute("INSERT OR REPLACE INTO settings VALUES ('config','{}')")
                self.assertTrue(store.settings().overlay_rtss_details)
                store.save_settings(replace(store.settings(),overlay_rtss_details=False))
            with closing(Store(path)) as store: self.assertFalse(store.settings().overlay_rtss_details)


class DetailsInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(timer_fixture.TimerInterfaceTests.setUpClass.__func__)
    setUp=timer_fixture.TimerInterfaceTests.setUp; tearDown=timer_fixture.TimerInterfaceTests.tearDown
    pump=timer_fixture.TimerInterfaceTests.pump; setup_budget=timer_fixture.TimerInterfaceTests.setup_budget

    def test_rtss_omits_duplicate_budget_line_and_keeps_different_budget_value(self):
        from gametime.restriction_policy import step
        current=self.configure_game()
        self.app.settings.restriction_plans['youtube']['steps']=[step('cover',3600,usage=True)]
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=True),patch.object(self.app.rtss,'present',return_value=True):
            self.app._overlay_desktop_until=0; self.app.update_overlay()
            self.assertEqual(self.rtss_renderer.call_args.args[4],self.app.t('Restriction in'))
            self.assertEqual(self.rtss_renderer.call_args.args[5],'')
            self.app.settings.restriction_plans['youtube']['steps']=[step('cover',1200,usage=True)]
            self.app.update_overlay()
            self.assertIn('01:00:00',self.rtss_renderer.call_args.args[5])

    def configure_game(self):
        self.setup_budget(target('game',self.games[0].id))
        self.app.settings.restriction_plans['youtube']['steps'][0]['redirect_url']=''
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_auto=False,
            counter_overlays={'youtube':{'overlay_rtss_auto':True}})
        current=replace(self.sample,path=str(self.exe),identity='fixture:game')
        self.app.tracker.active=self.games[0]; self.app.tracker.identity=current.identity
        self.app.wellbeing.tick(current); self.app.restrictions.prepare(self.now)
        return current

    def test_switch_updates_game_rtss_immediately_and_preserves_next_event_and_tray(self):
        current=self.configure_game(); page=self.app.display_settings
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=True), \
             patch.object(self.app.rtss,'present',return_value=True) as present,patch.object(self.app,'apply_display_settings') as restart:
            page.details.click(); self.app._overlay_desktop_until=0; self.app.update_overlay()
            self.assertFalse(self.store.settings().overlay_rtss_details); self.assertFalse(self.app.catalog.settings.overlay_rtss_details)
            self.assertFalse(self.app.settings.overlay_rtss_auto)  # A per-budget RTSS selection still uses this switch.
            text=present.call_args.args[2]; size=present.call_args.args[3][5]
            self.assertIn('00:30:00',text); self.assertNotIn('<LI=',text); self.assertNotIn('\n',text)
            compact=countdown_size(25); self.assertEqual(size,(compact.width(),compact.height()))
            self.rtss_renderer.assert_not_called(); restart.assert_not_called()
            event=self.app.timer_views(current)[0]; self.assertEqual((event.event,event.seconds,event.total),('break',1800,3600))
            self.assertIn('01:00:00',event.secondary(self.app.t))
            page.details.click()
            self.assertTrue(self.store.settings().overlay_rtss_details); self.assertIn('<LI=',present.call_args.args[2])
            self.assertGreater(present.call_args.args[3][5][1],size[1])
            self.assertEqual(self.rtss_renderer.call_args.args[0],1800)

    def test_desktop_fallback_and_website_counter_keep_their_details(self):
        self.setup_budget()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,overlay_rtss_details=False)
        with patch('gametime.qt_ui.win32.sample',return_value=self.sample): self.app.update_overlay()
        self.assertEqual(self.app.overlay.caption,'Szünetig'); self.assertIn('01:00:00',self.app.overlay.detail)
        current=self.configure_game()
        with patch('gametime.qt_ui.win32.sample',return_value=current),patch.object(self.app,'rtss_available',return_value=False): self.app.update_overlay()
        self.assertFalse(self.app.settings.overlay_rtss_details)
        self.assertTrue(self.app.overlay.isVisible()); self.assertEqual(self.app.overlay.caption,'Szünetig')

    def test_failed_save_restores_switch_and_language_changes_keep_saved_choice(self):
        page=self.app.display_settings
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')),patch.object(self.app,'update_overlay') as update:
            page.details.click(); update.assert_not_called()
        self.assertTrue(page.details.isChecked()); self.assertTrue(self.app.settings.overlay_rtss_details)
        self.assertFalse(page.display_status.isHidden())
        page.details.click(); self.assertFalse(page.details.isChecked())
        for language,caption in (('en','Detailed RTSS countdown'),('hu','Részletes RTSS-számláló')):
            self.app.set_language(language); page.refresh()
            self.assertEqual(page.details.text(),caption); self.assertFalse(page.details.isChecked())
        self.assertFalse(self.store.settings().overlay_rtss_details)


if __name__=='__main__': unittest.main()
