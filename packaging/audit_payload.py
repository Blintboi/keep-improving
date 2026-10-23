"""Fail closed on private files or secrets in source and decoded Windows payloads.

Reads archives/bytecode as data; never launches the installer or its application.
Requires the build environment's PyInstaller and a verified Gitleaks executable.
Reports contain locations and rule IDs, never matched credential values.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import tempfile
import zipfile


PRIVATE_PATH = re.compile(
    r'(?i)(?:^|/)(?:\.git|\.env(?:\..*)?|data|backups?|test-reports|'
    r'usage\.sqlite3(?:-wal|-shm)?|install\.json|bundle-install\.json|'
    r'credentials?\.json|session\.json|id_rsa|id_ed25519)(?:/|$)|'
    r'\.(?:sqlite3?|db|log|dmp|pfx|p12)$')
TOKENS = {
    # No leading word boundary: a marshalled string's length byte can be an
    # ASCII letter/digit immediately before its secret constant.
    'supabase-secret': rb'sb_secret_[A-Za-z0-9_-]{16,}',
    'supabase-management': rb'sbp_[a-f0-9]{40}',
    'github-token': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'ai-secret': rb'(?:sk-(?:proj-|or-v1-|ant-)?[A-Za-z0-9_-]{32,}|gsk_[A-Za-z0-9]{40,})',
    'telegram-token': rb'[0-9]{7,15}:[A-Za-z0-9_-]{35}',
}
JWT = re.compile(rb'eyJ[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]+')
# Exact decoded-content hashes reviewed in the public-history audit. Qt embeds
# key-parser delimiters, with no key material. No path-wide or rule-wide waiver.
QT_DELIMITERS = {
    '14abc5b245c0f2e03f7bc0b474a8db2ecb441c7300a8a8b16fb865eaf2674619',
    '7a0727417b8e21e64d9a7cf0f390bc85b3e337b4eef5ac977f49659d97e6b552',
    'dd3512d1c5ed062d30c98426cd0a850f13e0cf31437afb5b0b474132b9c52922',
    # Qt 6.11/6.12, including separately decoded UTF-16 resource strings.
    '8cbc5340df25b0ff239fad30656e2e3fc9cd6339f1581e0b292fc8101f5ac51e',
    '41265f2dcee1c1a1f021e8af81d6355a350cd80dc2d0b57c662b2bd80282faff',
    'aa7cf051bda037585c4c6f4d1f633a9a6e70d1d6515d2fc8d19c2f6903ef0166',
    '00ae5e9621bac7c963308efdf5aa6b07101bf8d4924ba6d6b6fff374a38bf132',
    'de9371f970e160967208cb4a274b5fea23996ee71472df99f59f147c16d2db13',
    'f0109346296b24f2a5e86628964aa12a9c0fbb6054e20c3be1ba685fe5384169',
}
# Schannel's literal Windows CNG blob-type label "PKCS8_PRIVATEKEY" follows
# "Key Storage Provider". It is a format identifier, with no secret value.
QT_STORAGE_LABELS = {
    'aa7cf051bda037585c4c6f4d1f633a9a6e70d1d6515d2fc8d19c2f6903ef0166',
    'f0109346296b24f2a5e86628964aa12a9c0fbb6054e20c3be1ba685fe5384169',
}
# Same deliberately invalid Auth fixture recorded in .gitleaksignore. Pin both
# exact LF/CRLF checkouts and the finding location; any other change still fails.
REVIEWED_FIXTURES = {
    '3eea154832df71df67295b5927ce5e5128f817e42dd79368d5177a8cf5d619d0': ('generic-api-key', 20),
    '0844c17749a13cf763c8b3af38bea62686d56fd9608f286dcdf47cb62c8eb69d': ('generic-api-key', 20),
}
# Exact official Qt 6.12 DLL bytes, checked against the installed wheel RECORD.
# Core: translated timezone names ending in "...sk-tyd..." / "...sk-tijd...".
# Widgets: three numeric/ASCII coincidences wholly inside embedded PNG PLTE
# chunks. A changed DLL (including an appended credential) loses this exception.
REVIEWED_BINARY_CONTENT = {
    'f57ed38afd95d0306cca9d88d997f639f70c7628a4f1f064eae291d579487121': {'ai-secret'},
    '2f62cbe2869fff4e20df7369c2786e1ec7ec290d5a63d1371b7f70cf06909c3f': {'telegram-token'},
}
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024


class Audit:
    def __init__(self, corpus):
        self.corpus = Path(corpus)
        self.corpus.mkdir(parents=True, exist_ok=True)
        self.sources = {}
        self.findings = []
        self.seen = set()
        self.files = self.modules = self.bytes = 0
        self.reviewed_native = 0

    def finding(self, rule, source, **details):
        self.findings.append(dict(rule=rule, source=source, **details))

    def scan(self, source, raw):
        self.files += 1
        self.bytes += len(raw)
        if len(raw) > MAX_FILE or self.bytes > MAX_TOTAL:
            raise ValueError('Audit size limit exceeded; payload was not approved.')
        digest = hashlib.sha256(raw).hexdigest()
        if digest in self.seen:
            return
        self.seen.add(digest)
        if raw.startswith(b'SQLite format 3\0'):
            self.finding('database-content', source)
        # Preserve UTF-16 string boundaries. Removing every NUL from machine
        # code can fabricate a token by joining unrelated binary fragments.
        utf16 = re.findall(rb'(?:[\x20-\x7e]\x00){8,}', raw)
        wide_text = b'\n'.join(part[::2] for part in utf16)
        detected = set()
        for data in (raw, wide_text):
            for rule, pattern in TOKENS.items():
                if re.search(pattern, data):
                    detected.add(rule)
            for match in JWT.finditer(data):
                try:
                    claims = json.loads(base64.urlsafe_b64decode(match[1] + b'=' * (-len(match[1]) % 4)))
                except (ValueError, UnicodeError):
                    continue
                if isinstance(claims, dict) and claims.get('role') == 'service_role':
                    detected.add('supabase-service-role-jwt')
        reviewed = detected & REVIEWED_BINARY_CONTENT.get(digest, set())
        self.reviewed_native += len(reviewed)
        for rule in sorted(detected - reviewed):
            self.finding(rule, source)
        try:
            if b'\0' in raw:
                raise UnicodeError()
            readable = raw.decode('utf-8-sig')
        except UnicodeError:
            readable = '\n'.join(x.decode('ascii') for x in re.findall(rb'[\x20-\x7e]{8,}', raw))
            # Extract UTF-16 strings separately, avoiding artificial concatenation.
            readable += '\n' + wide_text.decode('ascii')
        if readable:
            encoded = readable.encode('utf-8')
            key = hashlib.sha256(encoded).hexdigest()
            self.sources[key] = source
            (self.corpus / (key + '.txt')).write_bytes(encoded)

    def file(self, name, raw, depth=0):
        normalized = name.replace('\\', '/').replace('!', '/')
        if PRIVATE_PATH.search(normalized) and not normalized.endswith('/.env.example'):
            self.finding('private-filename', name)
        self.scan(name, raw)
        if normalized.lower().endswith('.zip'):
            self.archive(name, raw, depth + 1)
        elif PurePosixPath(normalized).name.lower() == 'gametimemonitor.exe':
            self.frozen(name, raw)

    def archive(self, name, raw, depth=0):
        if depth > 5:
            raise ValueError('Archive nesting exceeds audit bound.')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                path = PurePosixPath(entry.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts or ':' in str(path) or entry.file_size > MAX_FILE:
                    raise ValueError('Unsafe or oversized archive member.')
                self.file(name + '!' + str(path), archive.read(entry), depth)

    def frozen(self, name, raw):
        from PyInstaller.archive.readers import CArchiveReader
        with tempfile.TemporaryDirectory(prefix='gtm-bytecode-') as temp:
            path = Path(temp) / 'application.exe'
            path.write_bytes(raw)
            reader = CArchiveReader(str(path))
            for item, entry in reader.toc.items():
                if entry[-1] == 'z':
                    pyz = reader.open_embedded_archive(item)
                    for module in pyz.toc:
                        content = pyz.extract(module, raw=True)
                        if content:
                            self.modules += 1
                            self.scan(name + '!' + item + '!' + module, content)
                else:
                    content = reader.extract(item)
                    if content:
                        self.scan(name + '!' + item, content)

    def bundle(self, root):
        root = Path(root).resolve(strict=True)
        for path in sorted(root.rglob('*')):
            if path.is_symlink() or path.is_junction():
                raise ValueError('Bundle contains a link; payload was not approved.')
            if path.is_file():
                self.file(path.relative_to(root).as_posix(), path.read_bytes())

    def installer(self, path):
        raw = Path(path).read_bytes()
        self.scan(Path(path).name, raw)
        offset = 0
        while True:
            offset = raw.find(b'MSCF\0\0\0\0', offset)
            if offset < 0:
                raise ValueError('Installer cabinet not found.')
            size = struct.unpack_from('<I', raw, offset + 8)[0]
            if 36 <= size <= MAX_FILE and offset + size <= len(raw):
                break
            offset += 1
        with tempfile.TemporaryDirectory(prefix='gtm-cabinet-audit-') as temp:
            cabinet = Path(temp) / 'payload.cab'
            cabinet.write_bytes(raw[offset:offset + size])
            expanded = Path(temp) / 'expanded'
            expanded.mkdir()
            subprocess.run(['expand.exe', '-F:*', str(cabinet), str(expanded)],
                           check=True, capture_output=True)
            expected = {'payload.zip', 'setup.ps1', 'setup.cmd'}
            if {p.name for p in expanded.iterdir()} != expected:
                raise ValueError('Unexpected installer cabinet contents.')
            for item in sorted(expanded.iterdir()):
                self.file(item.name, item.read_bytes())

    def source(self, root):
        root = Path(root).resolve(strict=True)
        names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
        for name in dict.fromkeys(names.decode('utf-8').split('\0')):
            if not name:
                continue
            path = root / name
            if not path.exists():  # A locally deleted tracked file is not shipped.
                continue
            if PRIVATE_PATH.search(name) and name != '.env.example':
                self.finding('private-source-file', name)
            if path.is_symlink() or path.is_junction():
                raise ValueError('Source contains a link; source was not approved.')
            if path.suffix.lower() == '.exe':
                continue  # Installers are checked separately after decompression.
            self.scan(name, path.read_bytes())

    def gitleaks(self, executable):
        report = self.corpus.parent / 'scanner.json'
        command = [str(Path(executable).resolve()), 'dir', str(self.corpus), '--redact=100',
                   '--ignore-gitleaks-allow', '--no-banner', '--no-color', '--report-format',
                   'json', '--report-path', str(report)]
        result = subprocess.run(command, capture_output=True)
        if result.returncode not in (0, 1) or not report.exists():
            raise ValueError('Secret scanner failed; payload was not approved.')
        reviewed = 0
        for row in json.loads(report.read_text(encoding='utf-8-sig')):
            digest = Path(row['File']).stem
            if (row['RuleID'] == 'private-key' and digest in QT_DELIMITERS
                    or row['RuleID'] == 'generic-api-key' and digest in QT_STORAGE_LABELS
                    or REVIEWED_FIXTURES.get(digest) == (row['RuleID'], row['StartLine'])):
                reviewed += 1
                continue
            self.finding(row['RuleID'], self.sources.get(digest, digest), line=row['StartLine'])
        return reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--installer', type=Path)
    parser.add_argument('--gitleaks', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if not any((args.source, args.bundle, args.installer)):
        parser.error('Choose source, bundle or installer to inspect.')
    with tempfile.TemporaryDirectory(prefix='gtm-secret-audit-') as temp:
        audit = Audit(Path(temp) / 'corpus')
        for kind in ('source', 'bundle', 'installer'):
            if path := getattr(args, kind):
                getattr(audit, kind)(path)
        reviewed = audit.gitleaks(args.gitleaks)
        result = dict(files=audit.files, frozen_modules=audit.modules, bytes=audit.bytes,
                      reviewed_false_positives=reviewed, findings=audit.findings,
                      reviewed_native_content=audit.reviewed_native,
                      passed=not audit.findings)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
        return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
