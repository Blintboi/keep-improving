from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock,patch
import hashlib
import io
import tempfile
import threading
from gametime.update_install import download,location,verify,launch,installed_directory
from gametime.updates import Release,DOWNLOAD_URL

class Response(io.BytesIO):
    def __init__(self,raw,url=DOWNLOAD_URL,length=None):super().__init__(raw);self.url=url;self.headers={} if length is None else {'Content-Length':str(length)}
    def geturl(self):return self.url
    def read1(self,size):return self.read(size)

class UpdateInstallationTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.content=b'MZ synthetic executable fixture';self.release=Release('9.0.0',DOWNLOAD_URL,hashlib.sha256(self.content).hexdigest(),len(self.content))
    def test_verified_download_is_cached_and_partial_is_never_executable(self):
        opener=Mock();opener.open.return_value=Response(self.content);progress=Mock()
        path=download(self.release,self.root,threading.Event(),progress,opener)
        self.assertEqual(path.read_bytes(),self.content);self.assertEqual(list(self.root.glob('*.part')),[]);progress.assert_called_with(len(self.content),len(self.content))
        self.assertEqual(download(self.release,self.root,threading.Event(),progress,opener),path);self.assertEqual(opener.open.call_count,1)
    def test_truncation_wrong_hash_extra_bytes_or_html_do_not_produce_installer(self):
        for raw in (self.content[:-1],self.content+b'x',b'x'*len(self.content),b'MZ'+b'x'*(len(self.content)-2)):
            with self.subTest(raw=raw):
                opener=Mock();opener.open.return_value=Response(raw)
                with self.assertRaises(ValueError):download(self.release,self.root,threading.Event(),Mock(),opener)
                self.assertEqual(list(self.root.iterdir()),[])
    def test_cancel_and_untrusted_redirect_keep_application_and_disk_untouched(self):
        for url in ('http://github.com/a','https://github.com.evil.test/a','file:///C:/a','https://127.0.0.1/a','https://user@github.com/a'):
            with self.subTest(url=url),self.assertRaises(ValueError):location(url)
        stop=threading.Event();stop.set();opener=Mock();opener.open.return_value=Response(self.content)
        with self.assertRaises(InterruptedError):download(self.release,self.root,stop,Mock(),opener)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_installer_handoff_uses_literal_paths_and_an_external_hidden_process(self):
        setup=self.root/'setup.ps1';install=self.root/'Program $name';data=self.root/'Data with spaces'
        with patch('gametime.update_install.subprocess.Popen') as process:launch(setup,install,data)
        args=process.call_args.args[0];self.assertIn('-File',args);self.assertEqual(args[args.index('-InstallDir')+1],str(install));self.assertEqual(args[args.index('-DataDir')+1],str(data.resolve()));self.assertNotIn('-Command',args)
    def test_source_launcher_cannot_accidentally_update_real_installation(self):
        with patch('gametime.update_install.sys.frozen',False,create=True),self.assertRaises(ValueError):installed_directory()
