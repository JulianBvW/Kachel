'''Reading the settings files, distrustfully.

Three TOML files in ~/.config/kachel/, written by hand:

    kachel.toml   general things: the window
    tiles.toml    the wall: groups and tiles
    rail.toml     the rail: folders and actions

Hand-written files have typos. A wrong value never stops the program: it is
reported and replaced by its default, and everything else in the file still
counts. Only a file that is not TOML at all is refused as a whole -- then the
caller keeps what it had before.

The messages are German, like everything else on screen.
'''

import os
import re
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import config, files, layout


@dataclass
class General:
    columns: int = config.COLUMNS
    height: int = config.HEIGHT
    exclude: tuple = files.DEFAULT_EXCLUDE            # left out of @f
    exclude_names: tuple = files.DEFAULT_EXCLUDE_NAMES


@dataclass
class Shortcut:
    '''A button on a large or wide tile: runs `command`, not the app.'''
    name: str
    command: str
    icon: str = None       # None: the default symbol
    terminal: bool = False
    line: int = None       # where its [[tile.shortcut]] header is


@dataclass
class Tile:
    group: str
    app: str = None        # .desktop ID, as written; resolved by assemble()
    name: str = None
    icon: str = None
    command: str = None
    size: str = 'medium'
    pos: tuple = None      # (col, row) or None
    shortcuts: list = field(default_factory=list)   # of Shortcut
    line: int = None       # where its [[tile]] header is in the file

    @property
    def label(self):
        '''How messages and --grid name this tile.'''
        if self.app:
            return self.app.removesuffix('.desktop')
        return self.name or '?'


@dataclass
class Folder:
    '''A folder on the rail, as written. railmodel resolves the path.'''
    path: str
    name: str = None       # None: the folder's own name
    icon: str = None       # None: ms:folder
    line: int = None


# Design §5: red for switching off, amber for restarting.
CONFIRM_RED = (0xef / 255, 0x66 / 255, 0x61 / 255, 0.5)
CONFIRM_LABEL = 'Sicher?'
CONFIRM_DURATION = 4000
CONFIRM_DURATION_MIN, CONFIRM_DURATION_MAX = 500, 60000


@dataclass
class Confirm:
    '''How an action asks before it runs: the first click arms it, the
    second runs it, and a coloured fill rises for `duration` ms.'''
    label: str = CONFIRM_LABEL
    color: tuple = CONFIRM_RED    # (r, g, b, a), 0-1
    duration: int = CONFIRM_DURATION


@dataclass
class Action:
    '''An action on the rail: runs `command`.'''
    name: str
    command: str
    icon: str = None       # None: ms:bolt
    terminal: bool = False
    confirm: Confirm = None    # None: runs on the first click
    line: int = None


# Two pages: three actions each, the fourth place turns the page.
MAX_ACTIONS = 6


@dataclass
class Rail:
    folders: list = field(default_factory=list)   # of Folder
    actions: list = field(default_factory=list)   # of Action


# The keys each table may have. Anything else is reported as a typo.
GENERAL_KEYS = {'window', 'files'}
WINDOW_KEYS = {'columns', 'height'}
FILES_KEYS = {'exclude', 'exclude_names'}
TILES_KEYS = {'groups', 'tile'}
TILE_KEYS = {'group', 'app', 'name', 'icon', 'command', 'size', 'pos',
             'shortcut'}
SHORTCUT_KEYS = {'name', 'icon', 'command', 'terminal'}
RAIL_KEYS = {'folder', 'action'}
FOLDER_KEYS = {'path', 'name', 'icon'}
ACTION_KEYS = {'name', 'icon', 'command', 'terminal', 'confirm'}
CONFIRM_KEYS = {'label', 'color', 'duration'}


@dataclass
class Wall:
    groups: list = field(default_factory=list)   # of str, in order
    tiles: list = field(default_factory=list)    # of Tile


GENERAL_SKELETON = '''\
# Kachel -- general settings. Saved changes apply at once.

[window]
columns = 2     # tile columns, 1-4; the width follows (1: 426, 2: 772 px)
height  = 680   # 300-2000 px

# What @f leaves out. Without this section, these defaults apply; to
# change them, take out the # and edit -- each list replaces its default.
#
# [files]
# exclude = [         # these folders and everything below them
#   "/usr", "/var", "/etc", "/opt", "/boot", "/root", "/srv", "/snap",
#   "/proc", "/sys", "/run", "/dev", "/timeshift", "/lost+found", "/cdrom",
#   "~/.cache", "~/.local/share/Trash", "~/.local/share/Steam",
#   "~/.local/share/flatpak", "~/.var/app", "~/.steam", "~/.wine",
#   "~/.npm", "~/.cargo", "~/.rustup", "~/.gradle", "~/.m2", "~/.conda",
#   "~/miniforge3", "~/.vscode", "~/.mozilla", "~/Games",
#   "~/VirtualBox VMs",
# ]
# exclude_names = [   # folder names, wherever they turn up
#   "node_modules", ".git", "__pycache__", ".venv", "venv", ".tox",
#   ".mypy_cache", ".pytest_cache", "steamapps", "compatdata",
# ]
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
# [[tile.shortcut]]             # belongs to the tile right above it;
# name     = "home-server"       # large tiles carry up to 4, wide up to 2
# icon     = "ms:dns"            # any Material Symbol (default ms:bolt)
# command  = "ssh home-server"
# terminal = true                # in the default terminal; default false
#
# [[tile]]
# group   = "Work"
# name    = "Notes"              # a tile without an app needs name + command
# icon    = "theme:accessories-text-editor"
# command = "xed ~/notes.txt"
#
# Icons: "ms:<symbol>" (fonts.google.com/icons), "theme:<icon name>",
# or a path to a file (relative to this folder).

groups = []
'''

RAIL_SKELETON = '''\
# Kachel -- the rail on the left. Saved changes apply at once.
#
# Folders at the top, one click opens them in the file manager. A path is
# "~/...", an absolute path, or one of the system's own folders:
#   @XDG_DOCUMENTS_DIR  @XDG_DOWNLOAD_DIR  @XDG_PICTURES_DIR  @XDG_MUSIC_DIR
#   @XDG_VIDEOS_DIR  @XDG_DESKTOP_DIR  @XDG_TEMPLATES_DIR  @XDG_PUBLICSHARE_DIR
# Those resolve to whatever they are called on this system, and so does the
# name, unless you give one:
#
#   [[folder]]
#   name = "Kachel"            # optional; default: the folder's own name
#   path = "~/Projekte/Kachel"
#   icon = "ms:code"           # optional; default ms:folder
#
# Actions at the bottom, at most 6, in the order written here: up to 4 fit on
# one page, with 5 or 6 the fourth place turns to a second page.
#
#   [[action]]
#   name     = "htop"
#   icon     = "ms:monitoring"   # optional; default ms:bolt
#   command  = "htop"
#   terminal = true              # optional; in the default terminal
#   confirm  = true              # optional; ask first (click twice)
#
# `confirm` is true, false, or a table:
#   confirm = { label = "Sure?", color = "#4caf5080", duration = 10000 }
# label: shown while armed (default "Sicher?"); color: #rgb, #rrggbb,
# #rrggbbaa or rgba(r, g, b, a) (default red); duration: 500-60000 ms
# until it disarms by itself (default 4000).
#
# Leave out all [[folder]] (or all [[action]]) entries and the defaults
# below come back. For none at all, write `folder = []` (or `action = []`).
#
# Icons: "ms:<symbol>" (fonts.google.com/icons), "theme:<icon name>",
# or a path to a file (relative to this folder).


# -- folders ------------------------------------------------------------

[[folder]]
path = "~"
icon = "ms:home"

[[folder]]
path = "@XDG_DOCUMENTS_DIR"
icon = "ms:description"

[[folder]]
path = "@XDG_DOWNLOAD_DIR"
icon = "ms:download"

[[folder]]
path = "@XDG_PICTURES_DIR"
icon = "ms:image"

[[folder]]
path = "@XDG_MUSIC_DIR"
icon = "ms:music_note"

[[folder]]
path = "@XDG_VIDEOS_DIR"
icon = "ms:movie"

[[folder]]
path = "@XDG_DESKTOP_DIR"
icon = "ms:desktop_windows"


# -- actions ------------------------------------------------------------

[[action]]
name    = "Einstellungen"
icon    = "ms:settings"
command = "cinnamon-settings"

[[action]]
name    = "Bereitschaft"
icon    = "ms:bedtime"
command = "systemctl suspend"

[[action]]
name    = "Ausschalten"
icon    = "ms:power_settings_new"
command = "systemctl poweroff"
confirm = { label = "Wirklich ausschalten?", color = "#ef666180" }

[[action]]
name    = "Neustart"
icon    = "ms:restart_alt"
command = "systemctl reboot"
confirm = { label = "Wirklich neu starten?", color = "#e8aa4e73" }

[[action]]
name    = "Abmelden"
icon    = "ms:logout"
command = "cinnamon-session-quit --logout --no-prompt"

[[action]]
name    = "Sperren"
icon    = "ms:lock"
command = "cinnamon-screensaver-command --lock"
'''


# -- small helpers ---------------------------------------------------------

def _is_int(value):
    # bool is a subclass of int; `columns = true` is not a number.
    return isinstance(value, int) and not isinstance(value, bool)


def location(filename, line=None):
    '''"tiles.toml, Zeile 3" -- how a message says where.'''
    return f'{filename}, Zeile {line}' if line else filename


def _unknown_keys(table, known, where, messages):
    '''Report keys nobody reads. A misspelt key is the commonest typo, and
    without a word it would just look as if the setting did nothing.'''
    for key in table:
        if key not in known:
            messages.append(f'{where}: unbekannter Schlüssel {key}, '
                            'wird übergangen')


def header_lines(text):
    '''Where the headers are, from one pass over the text:
    (lines of the [[tile]] headers, for each tile the lines of the
    [[tile.shortcut]] headers below it).

    tomllib reports no positions for values, but the n-th [[tile]] header
    is the n-th entry in the parsed list, and a [[tile.shortcut]] belongs
    to the [[tile]] above it -- enough to say where a bad entry is.
    '''
    tile = re.compile(r'^\s*\[\[\s*tile\s*\]\]')
    shortcut = re.compile(r'^\s*\[\[\s*tile\s*\.\s*shortcut\s*\]\]')
    tiles, shortcuts = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if tile.match(line):
            tiles.append(number)
            shortcuts.append([])
        elif shortcut.match(line) and shortcuts:
            shortcuts[-1].append(number)
    return tiles, shortcuts


def array_header_lines(text, name):
    '''Line numbers (1-based) of every [[name]] header, in order.'''
    header = re.compile(r'^\s*\[\[\s*' + re.escape(name) + r'\s*\]\]')
    return [number for number, line in enumerate(text.splitlines(), 1)
            if header.match(line)]


def tile_header_lines(text):
    '''Line numbers (1-based) of every [[tile]] header, in order.'''
    return header_lines(text)[0]


def shortcut_header_lines(text):
    '''For each [[tile]], the lines of its [[tile.shortcut]] headers.'''
    return header_lines(text)[1]


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

    section = data.get('files', {})
    if not isinstance(section, dict):
        messages.append(f'{filename}: [files] ist kein Abschnitt')
        return general, messages
    _unknown_keys(section, FILES_KEYS, f'{filename}, [files]', messages)
    for key in ('exclude', 'exclude_names'):
        if key not in section:
            continue
        value = section[key]
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            setattr(general, key, tuple(value))
        else:
            messages.append(f'{filename}: [files] {key} muss eine Liste von '
                            'Text sein -- es gilt die Vorgabe')
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
    lines, shortcut_lines = header_lines(text)

    for index, raw in enumerate(raw_tiles):
        line = lines[index] if index < len(lines) else None
        where = location(filename, line)
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

        if 'shortcut' in raw:
            own_lines = shortcut_lines[index] \
                if index < len(shortcut_lines) else []
            tile.shortcuts, more = parse_shortcuts(
                raw['shortcut'], tile, own_lines, filename)
            messages += more

        wall.tiles.append(tile)
    return wall, messages


def parse_shortcuts(raw_list, tile, lines, filename=config.TILES_FILE):
    '''The [[tile.shortcut]] entries of one tile -> (shortcuts, messages).

    `lines` are the lines of their headers, for the messages. Only large
    (up to 4) and wide (up to 2) tiles carry shortcuts.
    '''
    messages = []
    tile_where = location(filename, tile.line)
    if not isinstance(raw_list, list):
        messages.append(f'{tile_where}: shortcut muss als [[tile.shortcut]] '
                        'stehen')
        return [], messages
    limit = layout.MAX_SHORTCUTS.get(tile.size, 0)
    if raw_list and limit == 0:
        messages.append(f'{tile_where}: {tile.label}: {tile.size} trägt keine '
                        'Shortcuts (nur large und wide), sie werden '
                        'übergangen')
        return [], messages

    shortcuts = []
    for index, raw in enumerate(raw_list):
        line = lines[index] if index < len(lines) else tile.line
        where = location(filename, line)
        if not isinstance(raw, dict):
            messages.append(f'{where}: Shortcut muss als [[tile.shortcut]] '
                            'mit name und command stehen, wird weggelassen')
            continue
        _unknown_keys(raw, SHORTCUT_KEYS, where, messages)
        name = _optional_str(raw, 'name', where, messages)
        command = _optional_str(raw, 'command', where, messages)
        icon = _optional_str(raw, 'icon', where, messages)
        if name is None or command is None:
            messages.append(f'{where}: Shortcut braucht name und command, '
                            'wird weggelassen')
            continue
        terminal = raw.get('terminal', False)
        if not isinstance(terminal, bool):
            messages.append(f'{where}: {name}: terminal = {terminal!r} muss '
                            'true oder false sein, es gilt false')
            terminal = False
        shortcuts.append(Shortcut(name, command, icon, terminal, line))

    if len(shortcuts) > limit:
        extra = shortcuts[limit]
        messages.append(f'{location(filename, extra.line)}: {tile.label}: '
                        f'{tile.size} trägt höchstens {limit} Shortcuts, '
                        f'{len(shortcuts) - limit} fallen weg')
        shortcuts = shortcuts[:limit]
    return shortcuts, messages


def parse_color(value):
    ''''#rgb', '#rrggbb', '#rrggbbaa', 'rgb(r, g, b)' or 'rgba(r, g, b, a)'
    -> (r, g, b, a) between 0 and 1, or None for anything else.'''
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    match = re.fullmatch(r'#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})', text)
    if match:
        digits = match[1]
        if len(digits) == 3:
            digits = ''.join(d * 2 for d in digits)
        if len(digits) == 6:
            digits += 'ff'
        return tuple(int(digits[i:i + 2], 16) / 255 for i in range(0, 8, 2))
    number = r'\s*(\d+(?:\.\d+)?)\s*'
    match = re.fullmatch(rf'rgba?\({number},{number},{number}(?:,{number})?\)',
                         text)
    if not match or (text.startswith('rgba') != (match[4] is not None)):
        return None
    r, g, b = (float(match[i]) for i in (1, 2, 3))
    a = float(match[4]) if match[4] is not None else 1.0
    if max(r, g, b) > 255 or a > 1:
        return None
    return (r / 255, g / 255, b / 255, a)


def parse_confirm(raw, where, messages):
    '''true, false or a table -> Confirm or None.'''
    if raw is False:
        return None
    if raw is True:
        return Confirm()
    if not isinstance(raw, dict):
        messages.append(f'{where}: confirm = {raw!r} muss true, false oder '
                        '{ label = …, color = …, duration = … } sein, es '
                        'gilt true')
        return Confirm()
    confirm = Confirm()
    _unknown_keys(raw, CONFIRM_KEYS, f'{where}, confirm', messages)
    label = raw.get('label', CONFIRM_LABEL)
    if isinstance(label, str) and label.strip():
        confirm.label = label
    else:
        messages.append(f'{where}: confirm.label muss Text sein, es gilt '
                        f'„{CONFIRM_LABEL}“')
    if 'color' in raw:
        color = parse_color(raw['color'])
        if color is None:
            messages.append(f'{where}: confirm.color = {raw["color"]!r} ist '
                            'keine Farbe (#rrggbb, #rrggbbaa, rgba(…)), es '
                            'gilt rot')
        else:
            confirm.color = color
    duration = raw.get('duration', CONFIRM_DURATION)
    if _is_int(duration) \
            and CONFIRM_DURATION_MIN <= duration <= CONFIRM_DURATION_MAX:
        confirm.duration = duration
    else:
        messages.append(f'{where}: confirm.duration = {duration!r} geht '
                        f'nicht, erlaubt ist {CONFIRM_DURATION_MIN} bis '
                        f'{CONFIRM_DURATION_MAX} ms -- es gilt '
                        f'{CONFIRM_DURATION}')
    return confirm


def _entries(data, key, filename, messages):
    '''The [[key]] list, or None when the file has none at all.'''
    if key not in data:
        return None
    raw = data[key]
    if not isinstance(raw, list):
        messages.append(f'{filename}: {key} muss als [[{key}]] stehen, es '
                        'gilt die Voreinstellung')
        return None
    return raw


def parse_rail(data, text='', filename=config.RAIL_FILE):
    '''A parsed rail.toml -> (Rail, messages).

    A file without any [[folder]] gets the default folders, one without
    any [[action]] the default actions -- `folder = []` is how to say
    "none". `text` is only used for line numbers.
    '''
    messages = []
    rail = Rail()
    _unknown_keys(data, RAIL_KEYS, filename, messages)

    raw_folders = _entries(data, 'folder', filename, messages)
    if raw_folders is None:
        # Without line numbers: those would point into the skeleton,
        # not into the file being read.
        rail.folders = [replace(f, line=None) for f in default_rail().folders]
    else:
        lines = array_header_lines(text, 'folder')
        for index, raw in enumerate(raw_folders):
            line = lines[index] if index < len(lines) else None
            where = location(filename, line)
            if not isinstance(raw, dict):
                messages.append(f'{where}: Ordner muss als [[folder]] mit '
                                'path stehen, wird weggelassen')
                continue
            _unknown_keys(raw, FOLDER_KEYS, where, messages)
            path = _optional_str(raw, 'path', where, messages)
            if path is None:
                messages.append(f'{where}: Ordner ohne path, wird '
                                'weggelassen')
                continue
            rail.folders.append(Folder(
                path=path, name=_optional_str(raw, 'name', where, messages),
                icon=_optional_str(raw, 'icon', where, messages),
                line=line))

    raw_actions = _entries(data, 'action', filename, messages)
    if raw_actions is None:
        rail.actions = [replace(a, line=None) for a in default_rail().actions]
    else:
        lines = array_header_lines(text, 'action')
        for index, raw in enumerate(raw_actions):
            line = lines[index] if index < len(lines) else None
            where = location(filename, line)
            if not isinstance(raw, dict):
                messages.append(f'{where}: Aktion muss als [[action]] mit '
                                'name und command stehen, wird weggelassen')
                continue
            _unknown_keys(raw, ACTION_KEYS, where, messages)
            name = _optional_str(raw, 'name', where, messages)
            command = _optional_str(raw, 'command', where, messages)
            icon = _optional_str(raw, 'icon', where, messages)
            if name is None or command is None:
                messages.append(f'{where}: Aktion braucht name und command, '
                                'wird weggelassen')
                continue
            terminal = raw.get('terminal', False)
            if not isinstance(terminal, bool):
                messages.append(f'{where}: {name}: terminal = {terminal!r} '
                                'muss true oder false sein, es gilt false')
                terminal = False
            confirm = parse_confirm(raw.get('confirm', False), where,
                                    messages)
            rail.actions.append(Action(name, command, icon, terminal,
                                       confirm, line))
        if len(rail.actions) > MAX_ACTIONS:
            extra = rail.actions[MAX_ACTIONS]
            messages.append(f'{location(filename, extra.line)}: höchstens '
                            f'{MAX_ACTIONS} Aktionen, '
                            f'{len(rail.actions) - MAX_ACTIONS} fallen weg')
            rail.actions = rail.actions[:MAX_ACTIONS]
    return rail, messages


_default_rail = None


def default_rail():
    '''The rail as the skeleton writes it. The skeleton is the one place
    the defaults are spelt out; the tests make sure it reads cleanly.'''
    global _default_rail
    if _default_rail is None:
        _default_rail, _messages = parse_rail(tomllib.loads(RAIL_SKELETON),
                                              RAIL_SKELETON)
    return _default_rail


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
                messages.append(f'{location(filename, tile.line)}: App '
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
                    f'{location(filename, p.tile.line)}: {p.tile.label} bei '
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


def load_tiles(folder, with_text=False):
    '''-> (Wall or None, messages). None: not TOML, keep the old one.
    `with_text` adds the text that was read as a third value -- the line
    numbers in the Wall belong to exactly that text.'''
    data, text, problem = _read(Path(folder) / config.TILES_FILE)
    if data is None:
        result = None, [problem]
    elif not data and not text:
        result = Wall(), []   # no file at all: an empty wall, nothing to say
    else:
        result = parse_tiles(data, text)
    return result + (text,) if with_text else result


def load_rail(folder):
    '''-> (Rail or None, messages). None: not TOML, keep the old one.'''
    data, text, problem = _read(Path(folder) / config.RAIL_FILE)
    if data is None:
        return None, [problem]
    return parse_rail(data, text)


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
                           (config.TILES_FILE, TILES_SKELETON),
                           (config.RAIL_FILE, RAIL_SKELETON)):
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
