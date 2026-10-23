"""Generate the public release record from the finished, audited installer."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gametime.updates import DOWNLOAD_URL, Release


def write_manifest(installer, version, output):
    installer, output = Path(installer), Path(output)
    with installer.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    record = Release.parse({'schema':1, 'version':version, 'installer_url':DOWNLOAD_URL,
                            'sha256':digest, 'size':installer.stat().st_size})
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(asdict(record), indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--installer', required=True); parser.add_argument('--version', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args(); write_manifest(args.installer, args.version, args.output)
