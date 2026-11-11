"""Portable activity identity; installation paths remain local evidence."""
import ntpath
import re


def is_idle_app(value):
    """Explorer represents the desktop/file shell, not tracked active time."""
    return bool(value) and ntpath.basename(ntpath.normpath(str(value))).casefold()=='explorer.exe'


def app_identity(value):
    name=ntpath.basename(ntpath.normpath(value)).casefold() if value else ''
    # A setup program must remain independently restorable from its application.
    return name


def automatic_exclusion(value):
    """Conservative defaults: installers and explicit maintenance executables."""
    name=ntpath.basename(ntpath.normpath(str(value))).casefold()
    if name in {'msiexec.exe','trustedinstaller.exe','tiworker.exe','werfault.exe',
                'wermgr.exe','consent.exe','dllhost.exe','runtimebroker.exe',
                'applicationframehost.exe','shellexperiencehost.exe','startmenuexperiencehost.exe',
                'searchhost.exe','lockapp.exe','dxsetup.exe','vcredist_x86.exe','vcredist_x64.exe'}:return True
    return bool(re.fullmatch(r'(?:setup|install|installer|uninstall|unins\d*)\.exe',name)
                or re.search(r'(?:^|[-_ .])(?:setup|installer|uninstall)(?:[-_ .](?:v?\d[\w.-]*|x64|x86|arm64|win64|win32))*\.exe$',name))


def site_identity(value):
    return value.lower().removeprefix('www.')


def canonical_member(member):
    kind,value=member['kind'],member['value']
    if kind=='app': value=app_identity(value)
    elif kind=='site': value=site_identity(value)
    return dict(kind=kind,value=value)


def activity_key(member):
    member=canonical_member(member)
    return member['kind']+':'+member['value']
