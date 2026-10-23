"""Public release checks stay bounded and never install or download automatically."""
from contextlib import closing
from dataclasses import asdict, replace
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from queue import Queue
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from gametime import __version__
from gametime.model import Settings
from gametime.store import Store
from gametime.updates import (Release, version_tuple, fetch_release, UpdateWorker, UpdateState,
    DOWNLOAD_URL, MANIFEST_URL, MAX_MANIFEST, STATE_KEY, NoRedirect, CHECK_INTERVAL)
if os.name=='nt': import test_qt_ui as fixtures


def release(version='999.1.0'):
    return Release.parse({'schema':1,'version':version,'installer_url':DOWNLOAD_URL,'sha256':'a'*64,'size':1000})


class Response(io.BytesIO):
    def __init__(self, raw, url=MANIFEST_URL, headers=None):
        super().__init__(raw); self.url=url; self.headers=headers or {}
    def geturl(self): return self.url
    def read1(self, size): return self.read(size)


class UpdateTests(unittest.TestCase):
    def test_numeric_stable_versions_and_no_downgrade_offers(self):
        self.assertGreater(version_tuple('2.10.0'), version_tuple('2.9.9'))
        self.assertFalse(release(__version__).newer_than(__version__))
        self.assertFalse(release('1.0.0').newer_than(__version__))
        for value in ('v2.26.0','02.26.0','2.26','2.26.0-beta','2.26.0\n','1.2.9999999',None):
            with self.subTest(value=value), self.assertRaises(ValueError): version_tuple(value)

    def test_metadata_cannot_redirect_downloads_or_smuggle_invalid_fields(self):
        for key,values in {'schema':[True,2,'1'], 'size':[True,-1,0,300*1024*1024],
                           'sha256':['A'*64,'a'*63,None], 'installer_url':['http://example.com','file:///C:/file.exe',DOWNLOAD_URL+'?redirect=evil',DOWNLOAD_URL+'#x','https://github.com.evil.example/file']}.items():
            for value in values:
                data=asdict(release()); data[key]=value
                with self.subTest(key=key,value=value), self.assertRaises(ValueError): Release.parse(data)
        data=asdict(release()); data['command']='execute'
        with self.assertRaises(ValueError): Release.parse(data)

    def test_request_is_fixed_https_and_contains_no_account_device_or_profile_data(self):
        response=Response(json.dumps(asdict(release())).encode()); opener=Mock(); opener.open.return_value=response
        self.assertEqual(fetch_release(opener), release())
        request=opener.open.call_args[0][0]
        self.assertEqual(request.full_url, MANIFEST_URL); self.assertIsNone(request.data)
        self.assertEqual(set(dict(request.header_items())), {'Accept','User-agent'})
        self.assertEqual(request.get_header('User-agent'),'GameTimeMonitor/updates-v1')
        self.assertTrue(response.closed)

    def test_large_content_length_or_chunked_response_is_rejected(self):
        for response in (Response(b'{}',headers={'Content-Length':str(MAX_MANIFEST+1)}),Response(b' '* (MAX_MANIFEST+1))):
            opener=Mock(); opener.open.return_value=response
            with self.assertRaises(ValueError): fetch_release(opener)
            self.assertTrue(response.closed)

    def test_deadline_redirect_and_bad_json_fail_closed(self):
        opener=Mock(); opener.open.return_value=Response(b'{}')
        with patch('gametime.updates.time.monotonic',side_effect=[0,16]), self.assertRaises(TimeoutError): fetch_release(opener)
        for response in (Response(b'{}',url='https://evil.example/'),Response(b'not json'),Response(b'\xff')):
            opener.open.return_value=response
            with self.assertRaises((ValueError,UnicodeError)): fetch_release(opener)
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://evil.example'))

    def test_missing_first_manifest_is_distinct_from_service_failure(self):
        for code in (404,500):
            opener=Mock(); stream=io.BytesIO(b'body'); opener.open.side_effect=HTTPError(MANIFEST_URL,code,'fixture',{},stream)
            if code==404: self.assertIsNone(fetch_release(opener))
            else:
                with self.assertRaises(OSError): fetch_release(opener)
            self.assertTrue(stream.closed)

    def test_worker_is_lazy_has_one_request_and_discards_closed_results(self):
        started=threading.Event(); finish=threading.Event(); ended=threading.Event()
        def fetch():
            started.set(); finish.wait(2); ended.set(); return release()
        with patch('gametime.updates.threading.Thread') as thread:
            worker=UpdateWorker(fetch); thread.assert_not_called()
        worker.request(); self.assertTrue(started.wait(2)); self.assertFalse(worker.request())
        worker.close(); finish.set(); self.assertTrue(ended.wait(2)); self.assertTrue(worker.results.empty())

    def test_worker_turns_unexpected_failure_into_quiet_error_result(self):
        worker=UpdateWorker(Mock(side_effect=RuntimeError('fixture')))
        with self.assertLogs('gametime.updates'): worker._run()
        self.assertEqual(worker.results.get_nowait(),(None,True))

    def test_cache_roundtrip_and_invalid_metadata_cannot_change_download_target(self):
        with tempfile.TemporaryDirectory() as tmp, closing(Store(Path(tmp)/'usage.sqlite3')) as store:
            state=UpdateState(store); state.release=release(); state.dismissed=release().version; state.attempted=1000; state.save()
            loaded=UpdateState(store); self.assertEqual((loaded.release,loaded.dismissed,loaded.attempted),(release(),release().version,1000))
            data=asdict(release()); data['installer_url']='https://evil.example/'
            with store.db: store.db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps({'release':data}),STATE_KEY))
            with self.assertLogs('gametime.updates'): self.assertIsNone(UpdateState(store).release)
            from gametime.statistics_sync import StatisticsData
            self.assertNotIn(STATE_KEY,json.dumps(StatisticsData(store).snapshot('b'*32,'Fixture')))

    def test_update_switch_is_optional_and_validated(self):
        self.assertTrue(Settings().check_updates)
        replace(Settings(),check_updates=False).validate()
        for value in (None,1,'yes'):
            with self.subTest(value=value), self.assertRaises(ValueError): replace(Settings(),check_updates=value).validate()

    def test_build_manifest_matches_the_finished_installer(self):
        path=Path(__file__).resolve().parents[1]/'packaging/release_manifest.py'
        spec=importlib.util.spec_from_file_location('update_release_builder',path); builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'setup.exe'; exe.write_bytes(b'MZ synthetic installer fixture')
            output=Path(tmp)/'latest.json'; builder.write_manifest(exe,__version__,output)
            record=Release.parse(json.loads(output.read_text('utf-8')))
            self.assertEqual(record.version,__version__); self.assertEqual(record.size,exe.stat().st_size)
            self.assertEqual(record.sha256,hashlib.sha256(exe.read_bytes()).hexdigest())


@unittest.skipUnless(os.name=='nt','Windows Qt required')
class UpdateInterfaceTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.QtInterfaceTests.setUpClass.__func__) if os.name=='nt' else classmethod(lambda cls:None)
    if os.name=='nt':
        setUp=fixtures.QtInterfaceTests.setUp; tearDown=fixtures.QtInterfaceTests.tearDown; pump=fixtures.QtInterfaceTests.pump

    def worker(self):
        self.fake=Mock(); self.fake.results=Queue(); self.fake.request.return_value=True
        self.app.updates.worker=self.fake
        return self.app.updates

    def test_check_result_never_downloads_executes_activates_or_opens_a_popup(self):
        updates=self.worker(); self.assertTrue(updates.request(manual=True))
        with patch('gametime.qt_updates.webbrowser.open') as browser,patch.object(self.app,'popup') as popup,patch('gametime.win32.u.SetForegroundWindow') as foreground:
            self.fake.results.put((release(),False)); updates.poll()
        browser.assert_not_called(); popup.assert_not_called(); foreground.assert_not_called()
        self.assertFalse(self.app.isVisible()); self.assertFalse(updates.notice.isHidden())
        self.assertIn('999.1.0',updates.notice_text.text()); self.assertIn('999.1.0',self.app.tray.data.szTip)

    def test_download_requires_click_and_uses_the_fixed_browser_url(self):
        updates=self.worker(); updates.state.release=release(); updates.refresh()
        with patch('gametime.qt_updates.webbrowser.open',return_value=True) as browser,patch('os.startfile') as execute:
            updates.notice_download.click()
        browser.assert_called_once_with(DOWNLOAD_URL,new=2); execute.assert_not_called()
        self.assertIn('böngésző',updates.status.text()); self.assertFalse(self.app.closed)

    def test_same_or_older_version_has_no_notice_or_download(self):
        updates=self.worker()
        for version in (__version__,'1.0.0'):
            updates.state.release=release(version); updates.refresh()
            self.assertTrue(updates.notice.isHidden()); self.assertTrue(updates.download_button.isHidden())
            with patch('gametime.qt_updates.webbrowser.open') as browser: self.assertFalse(updates.download())
            browser.assert_not_called()

    def test_browser_failure_is_reported_without_stopping_the_app(self):
        import webbrowser
        updates=self.worker(); updates.state.release=release(); updates.refresh()
        with patch('gametime.qt_updates.webbrowser.open',side_effect=webbrowser.Error('fixture')),self.assertLogs('gametime.qt_updates'):
            self.assertFalse(updates.download())
        self.assertIn('Nem sikerült',updates.status.text()); self.assertFalse(self.app.closed)

    def test_later_persists_for_that_version_and_newer_release_reappears(self):
        updates=self.worker(); updates.state.release=release(); updates.refresh(); updates.dismiss()
        self.assertTrue(updates.notice.isHidden()); self.assertEqual(UpdateState(self.store).dismissed,'999.1.0')
        updates.state.release=release('999.2.0'); updates.refresh(); self.assertFalse(updates.notice.isHidden())

    def test_automatic_cadence_persists_across_restart_and_manual_requests_are_throttled(self):
        updates=self.worker()
        with patch('gametime.qt_updates.time.time',return_value=100000):
            self.assertTrue(updates.request()); self.fake.results.put((release(__version__),False)); updates.poll()
            updates.automatic_check(); self.assertFalse(updates.request(manual=True))
        self.fake.request.assert_called_once(); self.assertEqual(UpdateState(self.store).attempted,100000)
        self.assertGreater(updates.timer.remainingTime(),(CHECK_INTERVAL-10)*1000)

    def test_disabling_automatic_checks_preserves_manual_check_and_other_drafts(self):
        updates=self.worker(); self.app.limit.setValue(150); updates.automatic.setChecked(False)
        self.app.set_language('en'); self.assertFalse(updates.automatic.isChecked())
        self.app.save_settings(); self.assertFalse(self.store.settings().check_updates)
        self.assertEqual(self.store.settings().limit_seconds,9000); self.assertFalse(updates.timer.isActive())
        updates.automatic_check(); self.fake.request.assert_not_called()
        self.assertTrue(updates.request(manual=True))

    def test_failed_setting_save_keeps_preference_and_draft(self):
        updates=self.worker(); updates.automatic.setChecked(False)
        with patch.object(self.store,'save_settings',side_effect=OSError('fixture')): self.app.save_settings()
        self.assertTrue(self.store.settings().check_updates); self.assertFalse(updates.automatic.isChecked())

    def test_transient_auto_error_is_quiet_but_manual_error_is_friendly(self):
        updates=self.worker(); self.app.set_status('Settings saved.')
        updates.request(); self.fake.results.put((None,True)); updates.poll()
        self.assertEqual(self.app.status_key,'Settings saved.'); self.assertTrue(updates.notice.isHidden())
        updates.state.attempted=0; updates.request(manual=True); self.fake.results.put((None,True)); updates.poll()
        self.assertIn('Nem sikerült',updates.status.text()); self.assertNotIn('Traceback',updates.status.text())

    def test_close_stops_future_checks_and_late_results(self):
        updates=self.worker(); updates.request(); updates.close(); self.fake.results.put((release(),False)); updates.poll()
        self.assertIsNone(updates.state.release); self.assertFalse(updates.timer.isActive()); self.fake.close.assert_called_once()

    def test_production_entrypoint_explicitly_enables_external_checks(self):
        from gametime.qt_ui import run
        with patch('gametime.qt_ui.setup_application') as application,patch('gametime.qt_ui.App') as app:
            application.return_value.exec.return_value=0
            self.assertEqual(run('fixture store','fixture path'),0)
        app.assert_called_once_with('fixture store','fixture path',False,updates=True)

    def test_tray_update_action_reveals_the_card_after_settings_were_scrolled(self):
        from PySide6.QtWidgets import QScrollArea
        updates=self.worker(); self.app.settings_dialog(); self.pump(.02)
        area=self.app.settings_page.findChildren(QScrollArea)[0]; area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        with patch.object(self.app.tray,'popup_menu',return_value=6): self.app.tray_menu()
        self.assertEqual(self.app.pages.currentIndex(),2); self.assertLess(area.verticalScrollBar().value(),100)
        self.fake.request.assert_called_once()


if __name__=='__main__': unittest.main()
