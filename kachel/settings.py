'''Reading the settings files, distrustfully.

Three TOML files in ~/.config/kachel/, written by hand:

    kachel.toml   general things: the window
    tiles.toml    the wall: groups and tiles
    rail.toml     folders and actions (read from phase 5 on)

Hand-written files have typos. A wrong value never stops the program: it is
reported and replaced by its default, and everything else in the file still
counts. Only a file that is not TOML at all is refused as a whole -- then the
caller keeps what it had before.

The messages are German, like everything else on screen.
'''

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import config, layout


@dataclass
class General:
    columns: int = config.COLUMNS
    height: int = config.HEIGHT


@dataclass
class Tile:
    group: str
    app: str = None        # .desktop ID, as written; resolved by assemble()
    name: str = None
    icon: str = None
    command: str = None
    size: str = 'medium'
    pos: tuple = None      # (col, row) or None
    shortcuts: list = field(default_factory=list)   # of dicts, phase 4
    line: int = None       # where its [[tile]] header is in the file

    @property
    def label(self):
        '''How messages and --grid name this tile.'''
        if self.app:
            return self.app.removesuffix('.desktop')
        return self.name or '?'


# The keys each table may have. Anything else is reported as a typo.
GENERAL_KEYS = {'window'}
WINDOW_KEYS = {'columns', 'height'}
TILES_KEYS = {'groups', 'tile'}
TILE_KEYS = {'group', 'app', 'name', 'icon', 'command', 'size', 'pos',
             'shortcut'}


@dataclass
class Wall:
    groups: list = field(default_factory=list)   # of str, in order
    tiles: list = field(default_factory=list)    # of Tile


GENERAL_SKELETON = '''\
# Kachel -- general settings. Saved changes apply at once.

[window]
columns = 2     # tile columns, 1-4; the width follows (1: 426, 2: 772 px)
height  = 680   # 300-2000 px
'''

TILES_SKELETON = '''\
# Kachel -- the tile wall. Saved changes apply at once.
#
# `groups` is required: it names the groups and puts them in order. Every
# tile then says which group it belongs to.
#
#   /usr/bin/python3 -m kachel --list-apps   the app IDs to pin
#   /usr/bin/python3 -m kachel --grid        where every tile ended up
#
# groups = ["Work", "Games"]
#
# [[tile]]
# group = "Work"
# app   = "org.gnome.Terminal"   # .desktop ID; the .desktop may be left off
# size  = "large"                # small | medium | wide | large
# pos   = [0, 0]                 # [column 0-5, row], optional
#
# [[tile]]
# group   = "Work"
# name    = "Notes"              # a tile without an app needs name + command
# icon    = "theme:accessories-text-editor"
# command = "xed ~/notes.txt"

groups = []
'''


# -- small helpers ---------------------------------------------------------

def _is_int(value):
    # bool is a subclass of int; `columns = true` is not a number.
    return isinstance(value, int) and not isinstance(value, bool)


def _where(filename, line=None):
    return f'{filename}, Zeile {line}' if line else filename


def _unknown_keys(table, known, where, messages):
    '''Report keys nobody reads. A misspelt key is the commonest typo, and
    without a word it would just look as if the setting did nothing.'''
    for key in table:
        if key not in known:
            messages.append(f'{where}: unbekannter Schlüssel {key}, '
                            'wird übergangen')


def tile_header_lines(text):
    '''Line numbers (1-based) of every [[tile]] header, in order.

    tomllib reports no positions for values, but the n-th [[tile]] header in
    the text is the n-th entry in the parsed list, so this is enough to say
    where a bad tile is. [[tile.shortcut]] headers do not count.
    '''
    pattern = re.compile(r'^\s*\[\[\s*tile\s*\]\]')
    return [number for number, line in enumerate(text.splitlines(), 1)
            if pattern.match(line)]


def syntax_message(filename, error):
    '''tomllib's complaint, with its position put up front in German.'''
    text = str(error)
    match = re.search(r'\s*\(at line (\d+), column (\d+)\)$', text)
    if match:
        text = text[:match.start()]
        return f'{filename}, Zeile {match[1]}, Spalte {match[2]}: {text}'
    match = re.search(r'\s*\(at end of document\)$', text)
    if match:
        # An unclosed [ or quote: tomllib only notices at the very end.
        return f'{filename}, am Dateiende: {text[:match.start()]}'
    return f'{filename}: {text}'


# -- the pure part ---------------------------------------------------------

def parse_general(data, filename=config.GENERAL_FILE):
    '''A parsed kachel.toml -> (General, messages).'''
    general = General()
    messages = []
    _unknown_keys(data, GENERAL_KEYS, filename, messages)
    window = data.get('window', {})
    if not isinstance(window, dict):
        messages.append(f'{filename}: [window] ist kein Abschnitt')
        return general, messages
    _unknown_keys(window, WINDOW_KEYS, f'{filename}, [window]', messages)

    columns = window.get('columns', config.COLUMNS)
    if _is_int(columns) and config.COLUMNS_MIN <= columns <= config.COLUMNS_MAX:
        general.columns = columns
    else:
        messages.append(f'{filename}: columns = {columns!r} geht nicht, '
                        f'erlaubt ist {config.COLUMNS_MIN} bis '
                        f'{config.COLUMNS_MAX} -- es gilt {config.COLUMNS}')

    height = window.get('height', config.HEIGHT)
    if _is_int(height) and config.HEIGHT_MIN <= height <= config.HEIGHT_MAX:
        general.height = height
    else:
        messages.append(f'{filename}: height = {height!r} geht nicht, '
                        f'erlaubt ist {config.HEIGHT_MIN} bis '
                        f'{config.HEIGHT_MAX} -- es gilt {config.HEIGHT}')
    return general, messages


def _optional_str(raw, key, where, messages):
    value = raw.get(key)
    if value is None or isinstance(value, str):
        return value or None
    messages.append(f'{where}: {key} muss Text sein, wird übergangen')
    return None


def parse_tiles(data, text='', filename=config.TILES_FILE):
    '''A parsed tiles.toml -> (Wall, messages).

    `text` is the file as written, only used to put line numbers into the
    messages.
    '''
    messages = []
    wall = Wall()
    _unknown_keys(data, TILES_KEYS, filename, messages)

    groups = data.get('groups')
    if not isinstance(groups, list) \
            or not all(isinstance(g, str) for g in groups):
        messages.append(f'{filename}: groups fehlt oder ist keine Liste von '
                        'Namen -- ohne groups bleibt die Wand leer')
        return wall, messages
    for name in groups:
        if name in wall.groups:
            messages.append(f'{filename}: Gruppe „{name}“ steht doppelt in '
                            'groups, es gilt die erste')
        else:
            wall.groups.append(name)

    raw_tiles = data.get('tile', [])
    if not isinstance(raw_tiles, list):
        messages.append(f'{filename}: tile muss als [[tile]] stehen')
        raw_tiles = []
    lines = tile_header_lines(text)

    for index, raw in enumerate(raw_tiles):
        line = lines[index] if index < len(lines) else None
        where = _where(filename, line)
        if not isinstance(raw, dict):
            continue

        group = raw.get('group')
        if not isinstance(group, str):
            messages.append(f'{where}: Kachel ohne group, wird weggelassen')
            continue
        if group not in wall.groups:
            messages.append(f'{where}: Gruppe „{group}“ steht nicht in '
                            'groups, Kachel wird weggelassen')
            continue

        tile = Tile(group=group, line=line)
        _unknown_keys(raw, TILE_KEYS, where, messages)
        tile.app = _optional_str(raw, 'app', where, messages)
        tile.name = _optional_str(raw, 'name', where, messages)
        tile.icon = _optional_str(raw, 'icon', where, messages)
        tile.command = _optional_str(raw, 'command', where, messages)
        if tile.app is None and (tile.name is None or tile.command is None):
            messages.append(f'{where}: Kachel braucht app oder name und '
                            'command, wird weggelassen')
            continue

        size = raw.get('size', 'medium')
        # A list or table here would not even be hashable; it is a typo
        # like any other, not a reason to fall over.
        if isinstance(size, str) and size in layout.SIZES:
            tile.size = size
        else:
            messages.append(f'{where}: {tile.label}: size = {size!r} gibt es '
                            'nicht (small, medium, wide, large), es gilt '
                            'medium')

        pos = raw.get('pos')
        if pos is not None:
            if isinstance(pos, list) and len(pos) == 2 \
                    and all(_is_int(v) for v in pos) \
                    and pos[1] <= layout.MAX_ROW:
                tile.pos = (pos[0], pos[1])
            elif isinstance(pos, list) and len(pos) == 2 \
                    and all(_is_int(v) for v in pos):
                messages.append(f'{where}: {tile.label}: Zeile {pos[1]} ist '
                                f'zu weit unten (höchstens {layout.MAX_ROW}), '
                                'wird eingepasst')
            else:
                messages.append(f'{where}: {tile.label}: pos = {pos!r} muss '
                                '[spalte, zeile] sein, wird eingepasst')

        shortcuts = raw.get('shortcut', [])
        if isinstance(shortcuts, list):
            tile.shortcuts = [s for s in shortcuts if isinstance(s, dict)]

        wall.tiles.append(tile)
    return wall, messages


def assemble(wall, resolve, filename=config.TILES_FILE):
    '''Resolve the apps and place the tiles -> (groups, messages).

    `resolve(app_id)` returns the installed .desktop ID for what the file
    says, or None. `groups` is a list of (name, [layout.Placement]) in the
    order of `wall.groups`.
    '''
    messages = []
    by_group = {name: [] for name in wall.groups}
    for tile in wall.tiles:
        if tile.app is not None:
            found = resolve(tile.app)
            if found is None:
                messages.append(f'{_where(filename, tile.line)}: App '
                                f'{tile.label} ist nicht installiert, '
                                'Kachel wird weggelassen')
                continue
            tile.app = found
        by_group[tile.group].append(tile)

    groups = []
    for name in wall.groups:
        placements = layout.place(by_group[name])
        for p in placements:
            if p.reason:
                messages.append(
                    f'{_where(filename, p.tile.line)}: {p.tile.label} bei '
                    f'{list(p.tile.pos)}: {p.reason} -- eingepasst bei '
                    f'{[p.col, p.row]}')
        groups.append((name, placements))
    return groups, messages


# -- the part that touches the disk ---------------------------------------

def _read(path):
    '''(data, text, None) for a good file, (None, text, message) for a bad
    one, ({}, '', None) for a missing one.'''
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return {}, '', None
    except (OSError, UnicodeDecodeError) as error:
        return None, '', f'{path.name}: nicht lesbar ({error})'
    try:
        return tomllib.loads(text), text, None
    except tomllib.TOMLDecodeError as error:
        return None, text, syntax_message(path.name, error)


def load_general(folder):
    '''-> (General or None, messages). None: not TOML, keep the old one.'''
    data, _text, problem = _read(Path(folder) / config.GENERAL_FILE)
    if data is None:
        return None, [problem]
    return parse_general(data)


def load_tiles(folder):
    '''-> (Wall or None, messages). None: not TOML, keep the old one.'''
    data, text, problem = _read(Path(folder) / config.TILES_FILE)
    if data is None:
        return None, [problem]
    if not data and not text:
        return Wall(), []   # no file at all: an empty wall, nothing to say
    return parse_tiles(data, text)


def ensure_files(folder):
    '''Write the commented skeletons where a file is missing. Never more.

    An existing file is never touched, not even a broken one: it is the
    user's, and a broken file is a half-finished edit, not an invitation.
    Returns (written paths, problems). A folder that cannot be written --
    read-only, or a file where the folder should be -- is a problem to
    report, not a reason not to start.
    '''
    folder = Path(folder)
    written, problems = [], []
    for name, skeleton in ((config.GENERAL_FILE, GENERAL_SKELETON),
                           (config.TILES_FILE, TILES_SKELETON)):
        path = folder / name
        if path.exists():
            continue
        try:
            folder.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(skeleton, encoding='utf-8')
            os.replace(temporary, path)
        except OSError as error:
            problems.append(f'{name}: konnte nicht angelegt werden ({error})')
            continue
        written.append(path)
    return written, problems
