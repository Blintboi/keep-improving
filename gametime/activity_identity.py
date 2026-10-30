"""Portable activity identity; installation paths remain local evidence."""
import ntpath
import re


def is_idle_app(value):
    """Explorer represents the desktop/file shell, not tracked active time."""
    return bool(value) and ntpath.basename(ntpath.normpath(str(value))).casefold()=='explorer.exe'


def app_identity(value):
    name=ntpath.basename(ntpath.normpath(value)).casefold() if value else ''
    # Named installers belong to their application, including versioned downloads.
    # A generic setup.exe has no known product identity and stays separate.
    installer=re.fullmatch(r'(.+?)(?:[- _]+v?\d+(?:\.\d+){1,3})?[- _]+(?:setup|installer)(?:[- _]+v?\d+(?:\.\d+){1,3})?\.exe',name)
    return installer[1]+'.exe' if installer else name


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
