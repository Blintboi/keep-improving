"""Icons stay local/cached, load lazily, and never change activity settings."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,QByteArray,QBuffer,QIODevice,QUrl,QTimer
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QWidget,QFileIconProvider
from PySide6.QtNetwork import QNetworkReply
from gametime.qt_ui import setup_application
from gametime.qt_activity_icons import ActivityIcons,IconLinks,decode_icon,icon_url,MAX_ICON,package_icon,logo_background
from gametime.activities import activity_key


def png_bytes(color='#19ba8c'):
    image=QImage(48,48,QImage.Format_ARGB32); image.fill(QColor(color))
    buffer=QBuffer(); buffer.open(QIODevice.WriteOnly); image.save(buffer,'PNG'); return bytes(buffer.data())


class Reply(QObject):
    readyRead=Signal(); finished=Signal()
    def __init__(self,url,data,error=False):
        super().__init__(); self.address=url; self.data=QByteArray(data); self.failed=error; self.aborted=False
    def readAll(self): data=self.data; self.data=QByteArray(); return data
    def url(self): return QUrl(self.address)
    def error(self): return QNetworkReply.NetworkError.ContentNotFoundError if self.failed else QNetworkReply.NetworkError.NoError
    def setReadBufferSize(self,value): self.buffer_size=value
    def deliver(self):
        if not self.aborted: self.readyRead.emit(); self.finished.emit()
    def abort(self):
        if not self.aborted: self.aborted=True; self.failed=True; self.finished.emit()


class IconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=setup_application()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.app=QWidget(); self.app.data_dir=Path(self.tmp.name)
        self.owner=QWidget(self.app); self.owner.schedule_icons=lambda *args:None
        self.app.show(); self.owner.show(); self.icons=ActivityIcons(self.app,self.owner); self.requests=[]; self.replies=[]
    def tearDown(self):
        self.icons.close(); self.app.close(); self.app.deleteLater(); self.qt.processEvents(); self.tmp.cleanup()
    def pump(self):
        until=time.monotonic()+.08; turns=0
        while time.monotonic()<until or turns<10:
            self.qt.processEvents(); time.sleep(.002); turns+=1
    def network(self,responses,automatic=True):
        owner=self
        class Network(QObject):
            def get(self,request):
                url=request.url().toString(); owner.requests.append(request)
                data,error=responses.get(url,(b'',True)); reply=Reply(url,data,error); owner.replies.append(reply)
                if automatic: QTimer.singleShot(0,reply.deliver)
                return reply
        return patch('gametime.qt_activity_icons.QNetworkAccessManager',Network)
    def test_parser_and_decoder_ignore_unsafe_links_and_oversized_or_invalid_images(self):
        parser=IconLinks('https://example.com/')
        parser.feed('<link rel="icon" href="/brand.png"><link rel="apple-touch-icon" href="https://cdn.example.com/logo.png">'
                    '<link rel="icon" href="file:///secret"><link rel="icon" href="https://user:pass@example.com/a.png">'
                    '<link rel="icon" href="http://example.com/a.png"><link rel="icon" href="https://127.0.0.1/a.png">')
        self.assertEqual(parser.links,['https://example.com/brand.png','https://cdn.example.com/logo.png'])
        self.assertEqual(icon_url('https://example.com:123/icon.png'),'')
        self.assertIsNotNone(decode_icon(png_bytes())); self.assertIsNone(decode_icon(b'<html>not an image</html>'))
        self.assertIsNone(decode_icon(b'x'*(MAX_ICON+1)))
    def test_favicon_is_downloaded_once_then_read_from_disk_after_restart(self):
        member=dict(kind='site',value='example.com'); original=self.icons.icon(member,'Example').cacheKey()
        with self.network({'https://example.com/favicon.ico':(png_bytes(),False)}):
            self.icons.request_visible([(member,'Example')]); self.pump()
            self.assertEqual(len(self.requests),1); self.assertNotEqual(self.icons.cache['site:example.com'].cacheKey(),original)
            self.icons.request_visible([(member,'Example')]); self.pump(); self.assertEqual(len(self.requests),1)
        self.icons.close(); self.icons=ActivityIcons(self.app,self.owner)
        with self.network({}):
            self.icons.icon(member,'Example'); self.icons.request_visible([(member,'Example')]); self.pump()
            self.assertEqual(len(self.requests),1); self.assertIn('site:example.com',self.icons.resolved)
    def test_missing_favicon_uses_declared_site_icon_without_querying_an_icon_service(self):
        member=dict(kind='site',value='example.com')
        with self.network({'https://example.com/':(b'<link rel="icon" href="/assets/logo.png">',False),
                           'https://example.com/assets/logo.png':(png_bytes(),False)}):
            self.icons.request_visible([(member,'Example')]); self.pump()
        self.assertEqual([r.url().toString() for r in self.requests],['https://example.com/favicon.ico','https://example.com/','https://example.com/assets/logo.png'])
        png,meta=self.icons.cache_paths(member); self.assertTrue(png.exists()); self.assertTrue(json.loads(meta.read_text())['success'])
    def test_failure_is_cached_and_hidden_views_do_not_start_or_continue_requests(self):
        member=dict(kind='site',value='example.com')
        with self.network({}):
            self.icons.request_visible([(member,'Example')]); self.pump(); self.assertEqual(len(self.requests),2)
            self.icons.request_visible([(member,'Example')]); self.pump(); self.assertEqual(len(self.requests),2)
        self.icons.close(); self.icons=ActivityIcons(self.app,self.owner)
        with self.network({},automatic=False):
            self.icons.request_visible([(member,'Example')]); self.pump(); self.assertEqual(len(self.requests),2)
            self.icons.request_visible([(dict(kind='site',value='other.com'),'Other')]); self.pump()
            self.assertEqual(len(self.requests),3); reply=self.replies[-1]; self.app.hide(); self.pump()
            self.assertTrue(reply.aborted); self.assertFalse(self.icons.jobs); self.assertFalse(self.icons.timer.isActive())
            self.icons.request_visible([(dict(kind='site',value='third.com'),'Third')]); self.pump(); self.assertEqual(len(self.requests),3)
    def test_only_two_visible_sites_can_load_and_cancelled_rows_are_not_cached_as_failures(self):
        entries=[(dict(kind='site',value=f'example{i}.com'),'Example') for i in range(6)]
        with self.network({},automatic=False):
            self.icons.request_visible(entries); self.pump(); self.assertEqual(len(self.requests),2)
            self.icons.request_visible(entries[3:4]); self.pump(); self.assertEqual(len(self.requests),3)
            self.assertTrue(self.replies[0].aborted); self.assertTrue(self.replies[1].aborted)
            self.assertFalse(self.icons.cache_paths(entries[0][0])[1].exists())
    def test_existing_executable_gets_a_native_icon_once_and_missing_executable_has_fallback(self):
        import os
        executable=str(Path(os.environ['WINDIR'])/'System32'/'notepad.exe')
        member=dict(kind='app',value=executable); fallback=self.icons.icon(member,'Notepad').cacheKey()
        with patch.object(self.icons.provider,'icon',wraps=self.icons.provider.icon) as native:
            self.icons.request_visible([(member,'Notepad')]); self.pump()
            self.assertEqual(native.call_count,1); self.assertNotEqual(self.icons.cache[activity_key(member)].cacheKey(),fallback)
            self.icons.request_visible([(member,'Notepad')]); self.pump(); self.assertEqual(native.call_count,1)
        missing=dict(kind='app',value=r'C:\Missing\application.exe')
        self.icons.request_visible([(missing,'Missing')]); self.pump(); self.assertFalse(self.icons.icon(missing,'Missing').isNull())

    def test_old_and_remote_paths_use_the_installed_icon_and_keep_it_after_removal(self):
        executable=Path(self.tmp.name)/'new'/'Editor.exe'; executable.parent.mkdir(); executable.touch()
        member=dict(kind='app',value='editor.exe'); paths=[r'D:\Remote\Editor.exe',r'C:\Old\Editor.exe',str(executable)]
        self.icons.set_sources({'app:editor.exe':paths})
        fallback=self.icons.icon(member,'Editor').cacheKey()
        with patch.object(self.icons.provider,'icon',return_value=self.icons.provider.icon(QFileIconProvider.Computer)) as native:
            self.icons.request_visible([(member,'Editor')]); self.pump(); self.assertEqual(native.call_count,1)
            self.assertEqual(native.call_args.args[0].filePath(),str(executable).replace('\\','/'))
        self.assertNotEqual(self.icons.cache['app:editor.exe'].cacheKey(),fallback)
        executable.unlink(); self.icons.close(); self.icons=ActivityIcons(self.app,self.owner); self.icons.set_sources({'app:editor.exe':paths})
        with patch.object(self.icons.provider,'icon') as native:
            self.icons.request_visible([(member,'Editor')]); self.pump(); native.assert_not_called()
        self.assertIn('app:editor.exe',self.icons.resolved)

    def test_packaged_app_uses_its_manifest_logo_and_svg_favicons_are_supported(self):
        root=Path(self.tmp.name)/'Package'; (root/'App').mkdir(parents=True); (root/'Assets').mkdir()
        (root/'Assets'/'Logo.targetsize-48_altform-unplated.png').write_bytes(png_bytes())
        (root/'AppxManifest.xml').write_text('<Package><Applications><Application Executable="App/Editor.exe">'
            '<VisualElements Square44x44Logo="Assets/Logo.png"/></Application></Applications></Package>')
        self.assertIsNotNone(package_icon(root/'App'/'Editor.exe'))
        svg=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="red" d="M0 0h24v24H0z"/></svg>'
        self.assertIsNotNone(decode_icon(svg)); self.assertIsNone(decode_icon(svg.replace(b'<path',b'<image href="file:///secret"/><path')))
        member=dict(kind='site',value='example.com')
        with self.network({'https://example.com/':(b'<link rel="icon" href="/brand.svg">',False),'https://example.com/brand.svg':(svg,False)}):
            self.icons.request_visible([(member,'Example')]); self.pump()
        self.assertTrue(json.loads(self.icons.cache_paths(member)[1].read_text())['success'])

    def test_www_alias_can_supply_the_icon_for_the_merged_site(self):
        member=dict(kind='site',value='example.com'); self.icons.set_sources({'site:example.com':['www.example.com','example.com']})
        with self.network({'https://www.example.com/favicon.ico':(png_bytes(),False)}):
            self.icons.request_visible([(member,'Example')]); self.pump()
        self.assertEqual([r.url().toString() for r in self.requests],
            ['https://example.com/favicon.ico','https://example.com/','https://www.example.com/favicon.ico'])
        self.assertTrue(json.loads(self.icons.cache_paths(member)[1].read_text())['success'])

    def test_removed_named_installer_can_use_its_installed_application_icon(self):
        executable=Path(self.tmp.name)/'Editor.exe'; executable.touch()
        member=dict(kind='app',value='editor-setup.exe')
        self.icons.set_sources({'app:editor.exe':[str(executable)]})
        with patch.object(self.icons.provider,'icon',return_value=self.icons.provider.icon(QFileIconProvider.Computer)) as native:
            self.icons.request_visible([(member,'Editor Setup')]); self.pump()
            self.assertEqual(native.call_count,1)
        self.assertTrue(json.loads(self.icons.cache_paths(member)[1].read_text())['success'])

    def test_white_logos_have_contrast_and_missing_subdomain_icon_uses_known_parent(self):
        self.assertEqual(logo_background(decode_icon(png_bytes('#ffffff'))).name(),'#243c3b')
        self.assertEqual(logo_background(decode_icon(png_bytes('#000000'))).name(),'#edf3f0')
        member=dict(kind='site',value='studio.example.com')
        self.icons.set_sources({'site:studio.example.com':['studio.example.com'],'site:example.com':['example.com']})
        with self.network({'https://example.com/favicon.ico':(png_bytes(),False)}):
            self.icons.request_visible([(member,'Studio')]); self.pump()
        self.assertEqual(self.requests[-1].url().toString(),'https://example.com/favicon.ico')
        self.assertTrue(json.loads(self.icons.cache_paths(member)[1].read_text())['success'])


if __name__=='__main__': unittest.main()
