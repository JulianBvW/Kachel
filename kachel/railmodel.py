'''What the rail shows, worked out from rail.toml. Pure but for special_dir.

settings.py reads what is written; this file turns it into what the rail
draws: folders with real paths and names, as many as fit, and the actions
split into pages.
'''

from dataclasses import dataclass
from pathlib import Path

from gi.repository import GLib

from . import config, settings

# Design §8: entries 40 high, 2 apart, the rail padded 10 top and bottom.
ENTRY_HEIGHT = 40
ENTRY_GAP = 2
PAD = 10
# The least room left between the folders and the actions.
MIN_ZONE_GAP = 8
PAGE_SLOTS = 4

# The two places that turn the page instead of running something.
MORE = 'more'
BACK = 'back'

# @XDG_..._DIR -> the name of the GLib.UserDirectory constant.
XDG_NAMES = {
    'DESKTOP': 'DIRECTORY_DESKTOP',
    'DOCUMENTS': 'DIRECTORY_DOCUMENTS',
    'DOWNLOAD': 'DIRECTORY_DOWNLOAD',
    'MUSIC': 'DIRECTORY_MUSIC',
    'PICTURES': 'DIRECTORY_PICTURES',
    'PUBLICSHARE': 'DIRECTORY_PUBLIC_SHARE',
    'TEMPLATES': 'DIRECTORY_TEMPLATES',
    'VIDEOS': 'DIRECTORY_VIDEOS',
}
HOME_NAME = 'Persönlicher Ordner'
DEFAULT_FOLDER_ICON = 'ms:folder'


def special_dir(constant):
    '''A GLib.UserDirectory by its name -> the folder, or None. The one
    lookup that touches the system; everything else takes it as an
    argument, so the tests can pass their own.'''
    return GLib.get_user_special_dir(getattr(GLib.UserDirectory, constant))


@dataclass(frozen=True)
class RailFolder:
    name: str
    path: Path
    icon: str
    shown: str        # the path as the tooltip shows it, with ~


def resolve_folder(path, special_dir, home):
    '''A path from rail.toml -> (Path, None) or (None, what is wrong).

    `special_dir(constant)` looks up a GLib.UserDirectory by its name and
    returns the folder or None; `home` is the home folder.
    '''
    path = path.strip()
    if path.startswith('@'):
        key = path[1:]
        inner = key.removeprefix('XDG_').removesuffix('_DIR')
        if not (key.startswith('XDG_') and key.endswith('_DIR')) \
                or inner not in XDG_NAMES:
            return None, (f'{path} gibt es nicht (bekannt: '
                          + ', '.join(f'@XDG_{n}_DIR' for n in XDG_NAMES)
                          + ')')
        found = special_dir(XDG_NAMES[inner])
        if not found:
            return None, f'{path} ist auf diesem System nicht gesetzt'
        return Path(found), None
    if path == '~' or path.startswith('~/'):
        return Path(home) / path[2:], None
    if path.startswith('/'):
        return Path(path), None
    return None, f'{path} muss mit ~/, / oder @XDG_ beginnen'


def shown_path(path, home):
    '''/home/julian/Dokumente -> ~/Dokumente.'''
    home = Path(home)
    if path == home:
        return '~'
    if home in path.parents:
        return '~/' + str(path.relative_to(home))
    return str(path)


def folder_capacity(height, action_slots):
    '''How many folders fit above `action_slots` actions in a window
    `height` pixels high.'''
    def stack(n):
        return max(0, n * ENTRY_HEIGHT + (n - 1) * ENTRY_GAP)
    free = height - config.SEARCHBAR_HEIGHT - 2 * PAD - stack(action_slots)
    if action_slots:
        free -= MIN_ZONE_GAP
    return max(0, (free + ENTRY_GAP) // (ENTRY_HEIGHT + ENTRY_GAP))


def pages(actions):
    '''The actions in pages of four places.

    Up to four: one page. Five or six: the first three and MORE on the
    first page, the rest (two or three) and BACK on the second.
    '''
    if not actions:
        return []
    if len(actions) <= PAGE_SLOTS:
        return [list(actions)]
    first = PAGE_SLOTS - 1
    return [list(actions[:first]) + [MORE],
            list(actions[first:2 * first]) + [BACK]]


def assemble(rail, special_dir, home, height, is_dir=Path.is_dir,
             filename=config.RAIL_FILE):
    '''-> (folders, pages, messages): what the rail shows.'''
    messages = []
    folders = []
    for folder in rail.folders:
        where = settings.location(filename, folder.line)
        path, problem = resolve_folder(folder.path, special_dir, home)
        if problem is None and not is_dir(path):
            problem = f'den Ordner {path} gibt es nicht'
            if folder.path != str(path):
                problem = f'{folder.path}: {problem}'
        if problem:
            messages.append(f'{where}: {problem}, wird weggelassen')
            continue
        if folder.name:
            name = folder.name
        elif path == Path(home):
            name = HOME_NAME
        else:
            name = path.name or str(path)
        folders.append(RailFolder(name, path, folder.icon or DEFAULT_FOLDER_ICON,
                                  shown_path(path, home)))

    split = pages(rail.actions)
    slots = len(split[0]) if split else 0
    room = folder_capacity(height, slots)
    if len(folders) > room:
        messages.append(f'{filename}: {len(folders)} Ordner, bei '
                        f'{height} px Höhe passen {room} -- die letzten '
                        f'{len(folders) - room} fallen weg')
        folders = folders[:room]
    return folders, split, messages
