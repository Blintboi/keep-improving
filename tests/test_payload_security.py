"""Poisoned release inputs must fail without printing or executing their secrets."""
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import zipfile

spec = importlib.util.spec_from_file_location('audit_payload', Path(__file__).resolve().parents[1] / 'packaging/audit_payload.py')
audit_payload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_payload)


class PayloadSecurityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.audit = audit_payload.Audit(Path(temp.name) / 'corpus')

    def test_public_key_is_allowed_and_admin_jwt_is_blocked(self):
        self.audit.scan('client', b'sb_publishable_' + b'x' * 40)
        self.assertFalse(self.audit.findings)
        claims = base64.urlsafe_b64encode(json.dumps({'role': 'service_role'}).encode()).rstrip(b'=')
        self.audit.scan('compiled', b'eyJhbGciOiJIUzI1NiJ9.' + claims + b'.signature')
        self.assertEqual(self.audit.findings[0]['rule'], 'supabase-service-role-jwt')

    def test_reviewed_auth_fixture_is_exact_for_lf_and_crlf_checkouts(self):
        raw=(Path(__file__).resolve().parent/'test_statistics_auth.py').read_bytes().replace(b'\r\n',b'\n')
        windows=raw.replace(b'\n',b'\r\n')
        cases=((raw,'generic-api-key',20,True),(windows,'generic-api-key',20,True),
               (raw+b'\n# changed\n','generic-api-key',20,False),
               (windows+b'\r\n# changed\r\n','generic-api-key',20,False),
               (raw,'generic-api-key',21,False),(raw,'private-key',20,False))
        for number,(content,rule,line,accepted) in enumerate(cases):
            with self.subTest(number=number):
                audit=audit_payload.Audit(self.audit.corpus.parent/str(number))
                audit.scan('tests/test_statistics_auth.py',content)
                digest=hashlib.sha256(content).hexdigest()
                row={'File':str(audit.corpus/(digest+'.txt')),'RuleID':rule,'StartLine':line}
                (audit.corpus.parent/'scanner.json').write_text(json.dumps([row]))
                with patch.object(audit_payload.subprocess,'run',return_value=Mock(returncode=1)):
                    self.assertEqual(audit.gitleaks('isolated-scanner.exe'),int(accepted))
                self.assertEqual(len(audit.findings),0 if accepted else 1)

    def test_binary_and_utf16_injected_secrets_are_blocked_and_redacted(self):
        for prefix in (b'sb_' + b'secret_', b'gh' + b'p_', b'g' + b'sk_'):
            secret = prefix + b'X' * 44
            for raw in (b'\0\1' + secret + b'\0', secret.decode().encode('utf-16le')):
                self.audit.scan('frozen-module', raw)
            self.assertNotIn(secret.decode(), json.dumps(self.audit.findings))
        self.assertEqual(len(self.audit.findings), 6)

    def test_nested_profile_and_environment_files_are_blocked(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, 'w') as archive:
            archive.writestr('.env.production', 'SOME_CREDENTIAL=private')
            archive.writestr('usage.sqlite3', b'SQLite format 3\0' + b'private')
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, 'w') as archive:
            archive.writestr('payload.zip', inner.getvalue())
        self.audit.archive('installer', outer.getvalue())
        self.assertEqual(sum(f['rule'] == 'private-filename' for f in self.audit.findings), 2)
        self.assertTrue(any(f['rule'] == 'database-content' for f in self.audit.findings))

    def test_archive_traversal_and_invalid_frozen_executable_fail_closed(self):
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, 'w') as archive:
            archive.writestr('../outside', 'blocked')
        with self.assertRaises(ValueError):
            self.audit.archive('archive', archive_bytes.getvalue())
        with self.assertRaises(Exception):
            self.audit.frozen('GameTimeMonitor.exe', b'not-an-archive')

    def test_build_injected_constant_inside_compressed_pyz_is_detected(self):
        from PyInstaller.archive.writers import CArchiveWriter, ZlibArchiveWriter
        root = self.audit.corpus.parent
        secret = 'sb_' + 'secret_' + 'X' * 44
        # Compile a literal exactly as a build-time environment substitution would.
        code = compile('provider = ' + repr(secret), 'fixture.py', 'exec')
        pyz = root / 'PYZ.pyz'
        ZlibArchiveWriter(str(pyz), [('fixture', 'fixture.py', 'PYMODULE')], {'fixture': code})
        exe = root / 'GameTimeMonitor.exe'
        CArchiveWriter(str(exe), [('PYZ.pyz', str(pyz), False, 'z')], 'python313.dll')
        self.audit.file(exe.name, exe.read_bytes())
        self.assertEqual(self.audit.modules, 1)
        self.assertTrue(any(f['rule'] == 'supabase-secret' and '!fixture' in f['source']
                            for f in self.audit.findings))
        self.assertNotIn(secret, json.dumps(self.audit.findings))
