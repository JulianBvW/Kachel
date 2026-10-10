'''Finding files: what matches, what is left out, what comes first. Pure.

The searching itself (plocate, the recent files, a thread) is in
filesearch.py; everything here works on plain paths and numbers, so it can
be tested.
'''

import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .text import normalize

# Left out of @f unless kachel.toml says otherwise (Design §11.4). Measured
# on 10.10.2026: /timeshift alone holds 3.5 million entries, /usr 690,000.
DEFAULT_EXCLUDE = (
    '/usr', '/var', '/etc', '/opt', '/boot', '/root', '/srv', '/snap',
    '/proc', '/sys', '/run', '/dev', '/timeshift', '/lost+found', '/cdrom',
    '~/.cache', '~/.local/share/Trash', '~/.local/share/Steam',
    '~/.local/share/flatpak', '~/.var/app', '~/.steam', '~/.wine',
    '~/.npm', '~/.cargo', '~/.rustup', '~/.gradle', '~/.m2', '~/.conda',
    '~/miniforge3', '~/.vscode', '~/.mozilla', '~/Games',
    '~/VirtualBox VMs',
)
DEFAULT_EXCLUDE_NAMES = (
    'node_modules', '.git', '__pycache__', '.venv', 'venv', '.tox',
    '.mypy_cache', '.pytest_cache', 'steamapps', 'compatdata',
)

WORD_SPLIT = re.compile(r'[\s\-_.()\[\]{},+]+')


@dataclass
class FileHit:
    path: str
    folder: bool = False
    mtime: float = None      # None until looked up


# -- dates -----------------------------------------------------------------

def parse_date(text):
    '''A period from JJJJ, MM.JJJJ, TT.MM.JJJJ or MM/TT/JJJJ ->
    (start, end) as local timestamps, end exclusive. None if it is none
    of those, or no real date.'''
    text = text.strip()
    try:
        if re.fullmatch(r'\d{4}', text):
            start = datetime(int(text), 1, 1)
            end = datetime(int(text) + 1, 1, 1)
        elif m := re.fullmatch(r'(\d{1,2})\.(\d{4})', text):
            month, year = int(m[1]), int(m[2])
            start = datetime(year, month, 1)
            end = datetime(year + month // 12, month % 12 + 1, 1)
        elif m := re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', text):
            start = datetime(int(m[3]), int(m[2]), int(m[1]))
            end = start + timedelta(days=1)
        elif m := re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', text):
            start = datetime(int(m[3]), int(m[1]), int(m[2]))
            end = start + timedelta(days=1)
        else:
            return None
    except ValueError:      # 13.2025, 31.02.2025
        return None
    return start.timestamp(), end.timestamp()


def date_ok(mtime, before=None, after=None):
    '''`before`/`after` are periods from parse_date. The period itself
    never counts: before 2026 ends on 31.12.2025, after 2025 starts on
    1.1.2026.'''
    if mtime is None:
        return before is None and after is None
    if before is not None and mtime >= before[0]:
        return False
    if after is not None and mtime < after[1]:
        return False
    return True


def when(mtime, today=None):
    '''heute, gestern or 14.01.2025.'''
    day = datetime.fromtimestamp(mtime).date()
    today = today or date.today()
    if day == today:
        return 'heute'
    if day == today - timedelta(days=1):
        return 'gestern'
    return day.strftime('%d.%m.%Y')


# -- what is left out ------------------------------------------------------

class Excluder:
    '''Paths (with everything below them) and folder names that do not
    count. '/usr' leaves out /usr/lib, not /usrlocal.'''

    def __init__(self, paths=DEFAULT_EXCLUDE, names=DEFAULT_EXCLUDE_NAMES,
                 home=None):
        home = str(home or os.path.expanduser('~'))
        prefixes = ((home + p[1:] if p.startswith('~') else p).rstrip('/')
                    for p in paths)
        # '/' would leave out everything; an empty entry means nothing.
        self.prefixes = tuple(p for p in prefixes if p)
        self.names = frozenset(names)

    def excluded(self, path):
        for prefix in self.prefixes:
            if path == prefix or path.startswith(prefix + '/'):
                return True
        if self.names:
            folders = path.split('/')[:-1]
            return any(part in self.names for part in folders)
        return False


# -- matching and order ----------------------------------------------------

def words_of(query):
    return normalize(query).split()


def matches(path, words):
    '''Every word somewhere in the path.'''
    haystack = normalize(path)
    return all(word in haystack for word in words)


def name_matches(path, words):
    '''Every word in the file's own name.'''
    return matches(os.path.basename(path.rstrip('/')), words)


def has_type(path, types):
    '''No types: anything. Otherwise one of the endings (or).'''
    if not types:
        return True
    lower = path.lower()
    return any(lower.endswith('.' + t.lower().lstrip('.')) for t in types)


def strong(name, words):
    '''Does every word begin a word in `name`? 'notiz' is strong for
    Kachel-Notizen.md, 'chel' is not.'''
    if not words:
        return False
    parts = [p for p in WORD_SPLIT.split(normalize(name)) if p]
    return all(any(p.startswith(word) for p in parts) for word in words)


def tier(path, words, home):
    '''The first three steps of the order: word in the name before word
    only in the folders; home before /mnt and /media before the rest;
    hidden folders last. Lower is better.'''
    name = normalize(os.path.basename(path))
    in_name = 0 if all(word in name for word in words) else 1
    home = str(home)
    if path == home or path.startswith(home + '/'):
        place = 0
        inner = path[len(home):]
    elif path.startswith(('/mnt/', '/media/')):
        place, inner = 1, path
    else:
        place, inner = 2, path
    hidden = 1 if any(part.startswith('.') for part in
                      inner.split('/')[:-1] if part) else 0
    return (in_name, place, hidden)


def rank(hits, words, home):
    '''Order by tier, then newer first. Hits without a time keep their
    place behind the timed ones of their tier.'''
    def key(hit):
        return tier(hit.path, words, home) + (
            0 if hit.mtime is not None else 1, -(hit.mtime or 0))
    return sorted(hits, key=key)


def shown_dir(path, home):
    '''The folder a file is in, with ~ for home.'''
    folder = os.path.dirname(path) or '/'
    home = str(home)
    if folder == home:
        return '~'
    if folder.startswith(home + '/'):
        return '~' + folder[len(home):]
    return folder


def escape_pattern(word):
    '''plocate takes *, ? and [ as a glob; a typed one is meant literally.'''
    return re.sub(r'([*?\[\]\\])', r'\\\1', word)
