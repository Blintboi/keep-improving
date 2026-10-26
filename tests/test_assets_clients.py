"""Local artwork and launcher UI regressions; no real client/game execution."""
from dataclasses import asdict,replace
import json
from pathlib import Path
from queue import Queue
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
import zipfile
from gametime.clients import Client,ClientWorker,find_clients,start_client
from gametime.model import Game,Settings
from gametime.store import Store
from gametime.artwork import Asset,candidates,decode
import test_overlay as fixtures

class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.base=Path(self.tmp.name)
    def exe(self,name):
        path=self.base/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'MZ synthetic'); return str(path)
    def test_discovery_deduplicates_clients_and_rejects_game_arguments(self):
        steam=self.exe('Steam/steam.exe'); riot=self.exe('Riot/RiotClientServices.exe'); epic=self.exe('Epic/EpicGamesLauncher.exe')
        inventory=[{'target':steam,'arguments':''},{'target':steam,'arguments':''},{'target':riot,'arguments':'--launch-product=valorant --launch-patchline=live'},{'target':epic,'arguments':''}]
        result=find_clients(Settings(),inventory,candidates=[])
        self.assertEqual({c.id for c in result},{'steam','epic'})
        result=find_clients(Settings(),inventory,candidates=[riot]); self.assertEqual({c.id for c in result},{'steam','riot','epic'})
    def test_explicit_client_open_passes_only_executable_and_revalidates(self):
        path=self.exe('RiotClientServices.exe'); client=Client('riot','Riot Client',path)
        with patch('gametime.clients.subprocess.Popen') as execute:
            start_client(client); execute.assert_called_once_with([path],cwd=str(Path(path).parent),shell=False)
            for wrong in (Client('steam','Steam',path),Client('unknown','Other',path),Client('riot','Riot Client',r'\\server\RiotClientServices.exe')):
                with self.assertRaises(ValueError): start_client(wrong)
        Path(path).unlink()
        with self.assertRaises(ValueError): start_client(client)
    def test_worker_falls_back_without_shortcuts_and_uses_settings_snapshot(self):
        bridge=Mock(); bridge.inventory.side_effect=OSError('fixture'); threads=[]
        def find(settings,inventory): threads.append(threading.get_ident()); return []
        with patch('gametime.clients.find_clients',side_effect=find):
            worker=ClientWorker(self.base,bridge); worker.request(Settings())
            clients,warning=worker.results.get(timeout=5); worker.close()
        self.assertEqual(clients,[]); self.assertTrue(warning); self.assertNotEqual(threads[0],threading.get_ident()); self.assertFalse(worker.thread.is_alive())
    def test_client_cache_survives_restart_without_disk_or_registry_discovery(self):
        path=self.exe('Steam/steam.exe'); db=self.base/'usage.sqlite3'
        clients=[Client('steam','Steam',path),Client('xbox','Xbox','Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App','app')]
        store=Store(db); self.assertIsNone(store.client_cache()); store.save_client_cache(clients); store.close()
        Path(path).unlink()  # A remembered path is checked when opened, not by another scan.
        store=Store(db)
        try:
            with patch('gametime.clients.find_clients',side_effect=AssertionError('Unexpected discovery')),patch('pathlib.Path.is_file',side_effect=AssertionError('Unexpected disk check')):
                self.assertEqual(store.client_cache(),clients)
            store.save_client_cache([])
        finally: store.close()
        store=Store(db)
        try: self.assertEqual(store.client_cache(),[])
        finally: store.close()
    def test_invalid_cache_is_discarded(self):
        store=Store(self.base/'usage.sqlite3'); self.addCleanup(store.close)
        valid=asdict(Client('steam','Steam',str(self.base/'steam.exe')))
        bad_rows=[None,{},[valid,valid],[dict(valid,id='unknown')],[dict(valid,target=r'\\server\steam.exe')],
                  [dict(valid,target='steam.exe')],[dict(valid,target=str(self.base/'game.exe'))],
                  [dict(valid,kind='app')],[dict(valid,icon='https://example.invalid/icon.exe')],[dict(valid,name=[])]]
        values=['broken',json.dumps({'version':2,'clients':[]})]+[json.dumps({'version':1,'clients':rows}) for rows in bad_rows]
        for value in values:
            with self.subTest(value=value):
                with store.db: store.db.execute("INSERT OR REPLACE INTO settings VALUES ('launcher_clients',?)",(value,))
                self.assertIsNone(store.client_cache())

@unittest.skipUnless(os.name=='nt','Windows Qt interface required')
class AssetClientInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OverlayInterfaceTests.setUpClass.__func__)
    tearDown=fixtures.OverlayInterfaceTests.tearDown
    pump=fixtures.OverlayInterfaceTests.pump
    def setUp(self):
        fixtures.OverlayInterfaceTests.setUp(self); self.app.assets_timer.stop()
    def image(self,path,size=(400,200),color='#1aa987'):
        from PySide6.QtGui import QImage,QColor
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        image=QImage(*size,QImage.Format_ARGB32); image.fill(QColor(color)); self.assertTrue(image.save(str(path))); return path
    def settle(self):
        deadline=time.monotonic()+6
        while self.app.art.pending and time.monotonic()<deadline:
            self.app.poll_assets(); self.pump(.02)
        self.assertFalse(self.app.art.pending)
    def test_cached_clients_load_only_on_first_visit_without_a_worker(self):
        client=Client('steam','Steam',str(self.base/'steam.exe')); self.store.save_client_cache([client])
        with patch.object(self.store,'client_cache',wraps=self.store.client_cache) as load,patch('gametime.clients.ClientWorker') as worker:
            self.app.poll_assets(); load.assert_not_called()
            self.app.switch_page(3); self.assertEqual(self.app.clients,[client]); load.assert_called_once()
            self.app.switch_page(0); self.app.switch_page(3); self.app.set_language('en')
            with patch('gametime.qt_ui.time.monotonic',return_value=time.monotonic()+120): self.app.poll_assets()
            worker.assert_not_called(); self.assertEqual(load.call_count,1)
            self.assertIn('steam',self.app.client_buttons)
    def test_unchanged_clients_and_language_keep_cards_and_shell_icons(self):
        clients=[Client('steam','Steam',str(self.base/'steam.exe')),Client('riot','Riot Client',str(self.base/'RiotClientServices.exe'))]
        self.app.clients=clients; self.app.render_clients(); cards=dict(self.app.client_cards); buttons=dict(self.app.client_buttons)
        with patch.object(self.app.art.provider,'icon',wraps=self.app.art.provider.icon) as icons:
            self.app.render_clients(); self.app.set_language('en'); self.app.render_clients()
            icons.assert_not_called(); self.assertEqual(self.app.client_cards,cards); self.assertEqual(self.app.client_buttons,buttons)
            self.assertEqual(buttons['steam'].text(),'Open'); self.assertEqual(buttons['riot'].accessibleName(),'Open Riot Client')
            changed=replace(clients[1],target=str(self.base/'moved/RiotClientServices.exe'))
            self.app.clients=[clients[0],changed]; self.app.render_clients(); self.assertEqual(icons.call_count,1)
            self.assertIs(self.app.client_buttons['steam'],buttons['steam'])
        with patch('gametime.clients.start_client') as start:
            self.app.client_buttons['riot'].click(); start.assert_called_once_with(changed)
    def test_initial_search_is_remembered_and_only_explicit_refresh_searches_again(self):
        worker=Mock(); worker.results=Queue()
        with patch('gametime.clients.ClientWorker',return_value=worker):
            self.app.switch_page(3); worker.request.assert_called_once()
            self.app.switch_page(0); self.app.switch_page(3); self.assertEqual(worker.request.call_count,1)
            worker.results.put(([],'')); self.app.poll_assets(); self.assertEqual(self.store.client_cache(),[])
            self.app.switch_page(0); self.app.switch_page(3)
            with patch('gametime.qt_ui.time.monotonic',return_value=time.monotonic()+120): self.app.poll_assets()
            self.assertEqual(worker.request.call_count,1)
            self.app.clients_refresh.click(); self.assertEqual(worker.request.call_count,2)
            client=Client('steam','Steam',str(self.base/'steam.exe')); worker.results.put(([client],'')); self.app.poll_assets()
            self.assertEqual(self.store.client_cache(),[client])
            self.app.refresh_clients(); worker.results.put((None,'Could not refresh launchers. Try again.')); self.app.poll_assets()
            self.assertEqual(self.app.clients,[client]); self.assertEqual(self.store.client_cache(),[client])
            self.assertTrue(self.app.clients_status.text())
    def test_library_launcher_panel_is_translated_and_available_while_restricted(self):
        class Worker:
            def __init__(me): me.results=Queue(); me.requests=[]
            def request(me,settings): me.requests.append(settings)
            def close(me): pass
        worker=Worker(); self.app.client_worker=worker
        self.app.switch_page(3); self.assertEqual(len(worker.requests),1); self.assertEqual(self.app.clients_toggle.text(),'Játékkliensek')
        self.assertEqual(self.app.pages.currentIndex(),0); self.assertNotIn(3,self.app.nav)
        client=Client('riot','Riot Client',str(self.exe)); worker.results.put(([client],'')); self.app.poll_assets()
        self.app.settings=self.app.catalog.settings=replace(self.app.settings,restriction_enabled=True)
        self.app.tracker.cache[str(__import__('datetime').date.today())]={self.game.id:7500}; self.app.render()
        self.assertTrue(self.app.client_buttons['riot'].isEnabled())
        with patch('gametime.clients.start_client') as execute:
            self.app.client_buttons['riot'].click(); execute.assert_called_once_with(client)
        self.app.set_language('en'); self.assertEqual(self.app.pages.currentIndex(),0); self.assertEqual(self.app.clients_toggle.text(),'Launchers')
        self.assertEqual(self.app.tracker.totals(__import__('datetime').date.today())[self.game.id],7500)
    def test_missing_client_failure_is_visible_and_does_not_start_game_worker(self):
        with patch('gametime.clients.start_client',side_effect=ValueError('This launcher is no longer available. Refresh the launcher list.')):
            self.app.open_client(Client('riot','Riot Client','missing.exe'))
        self.assertIn('Could not open',self.app.status_key); self.assertIsNone(self.app.launcher); self.assertEqual(len(self.app._dialogs),1)
    def test_local_cover_wins_over_icon_without_reading_saves_or_textures(self):
        cover=self.image(self.base/'Content/Splash/Splash.bmp',(600,300))
        self.image(self.base/'icon.png',(96,96)); self.image(self.base/'saves/cover.png')
        self.image(self.base/'textures/stone.png')
        found,exes=candidates(self.game,[],{})
        self.assertEqual(found[0].path,str(cover)); self.assertFalse(any('saves' in a.path or 'stone.png' in a.path for a in found))
        self.app.art.invalidate(); self.app.art.artwork(self.game,{str(self.exe):self.game.id}); self.settle()
        poster,icon=self.app.art.cache[self.app.art.key(self.game)]
        self.assertEqual((poster.width(),poster.height()),(600,300)); self.assertIsNotNone(icon)
        self.assertEqual(self.app.art.origins[self.app.art.key(self.game)],str(cover))
    def test_standalone_steam_id_reuses_matching_cache_only(self):
        steam=self.base/'Steam'; self.image(steam/'appcache/librarycache/42_header.jpg',(460,215))
        (self.base/'steam_appid.txt').write_text('42')
        found,_=candidates(self.game,[str(steam)],{})
        self.assertTrue(found[0].path.endswith('42_header.jpg'))
        (self.base/'steam_appid.txt').write_text('../other')
        found,_=candidates(self.game,[str(steam)],{}); self.assertFalse(any('/../' in a.path for a in found))
    def test_hashed_steam_cache_is_scoped_to_product_and_bootstrap_icon_is_skipped(self):
        steam=self.base/'Steam'; hashed=self.image(steam/'appcache/librarycache/42/abcdef0123.jpg')
        self.image(steam/'appcache/librarycache/43/not-this-game.jpg')
        game=Game('steam:42','My Game','Steam',str(self.base))
        (self.base/'EOSBootstrapper.exe').write_bytes(b'fake'); real=self.base/'MyGame.exe'; real.write_bytes(b'fake')
        found,executables=candidates(game,[str(steam)],{})
        self.assertTrue(any(asset.path==str(hashed) for asset in found))
        self.assertFalse(any('43' in Path(asset.path).parts for asset in found))
        self.assertEqual(executables[0],str(real)); self.assertFalse(any('EOSBootstrapper' in path for path in executables))
    def test_corrupt_and_oversized_images_are_skipped_then_valid_art_is_used(self):
        (self.base/'cover.png').write_bytes(b'not a PNG')
        valid=self.image(self.base/'banner.png',(600,900))
        self.assertIsNone(decode(Asset(str(self.base/'cover.png'),110)))
        self.app.art.invalidate(); self.app.art.artwork(self.game,{}); self.settle()
        poster,_=self.app.art.cache[self.app.art.key(self.game)]; self.assertEqual((poster.width(),poster.height()),(280,420))
        self.assertEqual(self.app.art.origins[self.app.art.key(self.game)],str(valid))
        huge=self.base/'huge.png'; huge.write_bytes(b'X')
        with patch('PySide6.QtGui.QImageReader.size') as size:
            from PySide6.QtCore import QSize
            size.return_value=QSize(100000,100000); self.assertIsNone(decode(Asset(str(huge),1)))
    def test_minecraft_known_jar_logo_and_square_icon_are_read_without_extraction(self):
        png=self.image(self.base/'fixture.png',(256,64)); jar=self.base/'versions/fixture/fixture.jar'; jar.parent.mkdir(parents=True)
        icon=self.image(self.base/'pack.png',(128,128))
        member='assets/minecraft/textures/gui/title/minecraft.png'
        with zipfile.ZipFile(jar,'w') as archive:
            archive.writestr(member,png.read_bytes()); archive.writestr('pack.png',icon.read_bytes()); archive.writestr('../../outside.png',png.read_bytes())
        game=Game('minecraft:java','Minecraft Java Edition','Minecraft',str(self.base))
        found,_=candidates(game,[],{}); asset=next(a for a in found if a.member==member)
        image=decode(asset); self.assertIsNotNone(image); self.assertEqual(image.width()/image.height(),4)
        square=decode(next(a for a in found if a.member=='pack.png' and a.icon))
        self.assertEqual((square.width(),square.height()),(128,128))
        self.assertFalse((self.base.parent/'outside.png').exists())
    def test_depth_drive_and_reparse_guards_keep_search_bounded(self):
        self.image(self.base/'a/b/c/d/e/splash.png')
        found,_=candidates(self.game,[],{}); self.assertFalse(found)
        drive=Game('fixture:drive','Drive','Games',str(self.base.anchor)); self.assertEqual(candidates(drive,[],{}),([],[]))
        with patch('gametime.artwork.reparse',return_value=True): self.assertEqual(candidates(self.game,[],{}),([],[]))
    def test_refresh_replaces_art_and_discards_obsolete_worker_results(self):
        self.app.art.invalidate(); key=self.app.art.key(self.game)
        self.app.art.artwork(self.game,{}); self.settle()
        self.assertIsNone(self.app.art.cache[key][0]); self.image(self.base/'cover.png')
        self.app.refresh_sources(); self.pump(.1); self.settle(); self.assertIsNotNone(self.app.art.cache[key][0])
        self.app.art.invalidate()
        self.app.art.worker.results.put((-1,key,None,None,[],'obsolete',''))
        self.assertEqual(self.app.art.poll(),[]); self.assertNotIn(key,self.app.art.cache)
    def test_image_decode_and_file_search_run_off_gui_thread(self):
        seen=[]
        from gametime.artwork import candidates as real
        def collect(*args): seen.append(threading.get_ident()); return real(*args)
        self.image(self.base/'poster.png')
        self.app.art.invalidate()
        with patch('gametime.artwork.candidates',side_effect=collect):
            self.app.art.artwork(self.game,{}); self.settle()
        self.assertTrue(seen); self.assertTrue(all(t!=threading.get_ident() for t in seen))

    def test_async_shell_icon_crops_transparent_canvas_before_card_sizing(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QPixmap,QPainter,QColor
        native=QPixmap(256,256); native.fill(Qt.transparent)
        painter=QPainter(native); painter.fillRect(2,2,43,43,QColor('#00ff00')); painter.end()
        native.setDevicePixelRatio(256/96)
        class ShellIcon:
            def pixmap(me,*args): return native
        self.app.art.invalidate(); self.app.art.artwork(self.game,{}); self.settle()
        key=self.app.art.key(self.game); token=999; self.app.art.pending[key]=token
        self.app.art.worker.results.put((token,key,None,None,[str(self.exe)],'',''))
        with patch.object(self.app.art.provider,'icon',return_value=ShellIcon()): self.app.art.poll()
        _,icon=self.app.art.cache[key]
        self.assertEqual((icon.width(),icon.height()),(43,43)); self.assertEqual(icon.devicePixelRatio(),1)
        card=self.app.cards[self.game.id]; card.resize(240,232); card.art=(None,icon)
        rendered=card.grab().toImage()
        green=sum(1 for y in range(30,140) for x in range(40,200)
                  if rendered.pixelColor(x,y).green()>100 and rendered.pixelColor(x,y).red()<30)
        self.assertGreater(green,10000)  # The shared large tile, including a low-resolution shell icon.

if __name__=='__main__': unittest.main()
