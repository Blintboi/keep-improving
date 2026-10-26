"""Truthful Windows file properties; these resources are not a code signature."""
import argparse
from pathlib import Path
import sys
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo, FixedFileInfo, StringFileInfo,
    StringTable, StringStruct, VarFileInfo, VarStruct, write_version_info_to_executable)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gametime.updates import version_tuple


def version_info(version, installer=False):
    numbers = version_tuple(version) + (0,)
    if any(value > 65535 for value in numbers): raise ValueError('Windows file version is out of range.')
    values = {'FileDescription': 'Keep Improving Setup' if installer else 'Keep Improving',
              'FileVersion': version, 'ProductVersion': version, 'ProductName': 'Keep Improving',
              'OriginalFilename': 'GameTimeMonitor-Setup.exe' if installer else 'GameTimeMonitor.exe'}
    return VSVersionInfo(ffi=FixedFileInfo(filevers=numbers, prodvers=numbers), kids=[
        StringFileInfo([StringTable('040904B0', [StringStruct(key,value) for key,value in values.items()])]),
        VarFileInfo([VarStruct('Translation', [1033,1200])])])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--version', required=True)
    parser.add_argument('--output'); parser.add_argument('--installer')
    args = parser.parse_args()
    if args.installer: write_version_info_to_executable(args.installer, version_info(args.version, True))
    else: Path(args.output).write_text(str(version_info(args.version)), encoding='utf-8')
