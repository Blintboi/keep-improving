"""Installed-game selectors refresh without deleting historical data or drafts."""
from dataclasses import replace
from datetime import date
import os
from pathlib import Path
import unittest
from gametime.model import Game,norm

if os.name=='nt':import test_qt_ui as fixtures


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class GameAvailabilityTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name=='nt' else classmethod(lambda cls:None)
    if os.name=='nt':
        setUp=fixtures.QtInterfaceTests.setUp;tearDown=fixtures.QtInterfaceTests.tearDown;pump=fixtures.QtInterfaceTests.pump

    def field(self,key):
        from PySide6.QtWidgets import QWidget
        return next(w for w in self.window.findChildren(QWidget) if w.accessibleName()==self.app.t(key))

    def ids(self):
        games=self.field('Countdown target');return [games.itemData(i) for i in range(games.count())]

    def manual(self):
        root=self.base/'Removed fixture';root.mkdir();exe=root/'game.exe';exe.touch()
        game=Game('manual:removed-fixture','I SAW That fixture','Kézi',str(root))
        self.store.upsert([game]);self.store.set_rule(str(exe),game.id)
        self.app.catalog.games[game.id]=game;self.app.catalog.rules[norm(exe)]=game.id
        return game,exe

    def test_removed_manual_game_is_not_selectable_but_keeps_history_rules_and_preferences(self):
        game,exe=self.manual();exe.unlink()
        self.store.add_usage({(str(date.today()),game.id):123})
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,game_overlays={game.id:{'overlay_enabled':True,'overlay_font_size':42}})
        self.store.save_settings(self.app.settings);self.app.refresh_manual_availability()
        self.assertFalse(self.app.catalog.games[game.id].installed)
        self.app.game_countdown_dialog();self.window=self.app._dialogs[-1]
        self.assertNotIn(game.id,self.ids());self.assertIsNone(self.app.catalog.resolve(str(exe)))
        self.assertTrue(self.app.catalog.explicitly_ignored(str(exe)))
        self.assertEqual(self.store.totals(date.today())[game.id],123)
        self.assertEqual(self.store.rules()[norm(exe)],game.id)
        self.assertEqual(self.store.settings().game_overlays[game.id]['overlay_font_size'],42)

    def test_open_editor_updates_on_manual_removal_and_reinstallation_without_losing_draft(self):
        game,exe=self.manual();self.app.game_countdown_dialog(game.id);self.window=self.app._dialogs[-1]
        hidden=self.field('Hide this countdown');hidden.setChecked(False);self.field('Text size').setValue(42)
        exe.unlink();self.app.refresh_manual_availability()
        self.assertNotIn(game.id,self.ids());self.assertNotEqual(self.field('Countdown target').currentData(),game.id)
        exe.touch();self.app.refresh_manual_availability();self.assertIn(game.id,self.ids())
        games=self.field('Countdown target');games.setCurrentIndex(games.findData(game.id))
        self.assertEqual(self.field('Text size').value(),42);self.assertFalse(hidden.isChecked())
        self.assertEqual(self.store.settings().game_overlays,{})

    def test_launcher_discovery_updates_open_editor_while_hub_is_hidden(self):
        game=self.games[1];self.app.game_countdown_dialog(game.id);self.window=self.app._dialogs[-1]
        self.assertFalse(self.app.isVisible());self.field('Text size').setValue(38)
        self.app.service.results.put(('launchers',[],[],[],[],[],[]));self.app.drain_discovery()
        self.assertNotIn(game.id,self.ids());self.assertTrue(self.window.isVisible())
        self.app.service.results.put(('launchers',[game],[],[],[],[],[]));self.app.drain_discovery()
        games=self.field('Countdown target');games.setCurrentIndex(games.findData(game.id))
        self.assertEqual(self.field('Text size').value(),38)

    def test_empty_game_inventory_does_not_invent_application_or_website_budgets(self):
        from PySide6.QtWidgets import QPushButton
        self.app.catalog.games={game.id:replace(game,installed=False) for game in self.games}
        self.app.game_countdown_dialog();self.window=self.app._dialogs[-1]
        self.assertEqual(self.ids(),[]);self.assertFalse(self.field('Hide this countdown').isVisible())
        save=next(w for w in self.window.findChildren(QPushButton) if w.text()==self.app.t('Save'))
        self.assertFalse(save.isVisible())
        self.app.catalog.games[self.games[0].id]=self.games[0];self.app.catalog_changed()
        self.assertEqual(self.ids(),[self.games[0].id]);self.assertTrue(save.isVisible());self.assertTrue(save.isEnabled())

    def test_opening_removed_game_does_not_silently_select_another_game(self):
        game,exe=self.manual();exe.unlink();self.app.refresh_manual_availability()
        self.app.game_countdown_dialog(game.id);self.window=self.app._dialogs[-1]
        self.assertNotIn(game.id,self.ids());self.assertIsNone(self.field('Countdown target').currentData())
        self.assertFalse(self.field('Hide this countdown').isVisible())
        games=self.field('Countdown target');games.setCurrentIndex(0)
        self.app.game_countdown_dialog(game.id)
        self.assertIsNone(games.currentData());self.assertFalse(self.field('Text size').isVisible())
