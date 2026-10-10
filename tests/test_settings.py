'''Reading kachel.toml and tiles.toml: what counts, what is reported.'''

import tempfile
import tomllib
from pathlib import Path

import harness
from harness import check, section

from kachel import config, settings


def tiles(text):
    return settings.parse_tiles(tomllib.loads(text), text)


def has(messages, *words):
    return any(all(w in m for w in words) for m in messages)


section('parse_general')
general, messages = settings.parse_general({})
check('empty file: defaults, no messages',
      (general.columns, general.height, messages) == (2, 680, []))
general, messages = settings.parse_general({'window': {'columns': 3, 'height': 800}})
check('good values are taken', (general.columns, general.height) == (3, 800))
for bad in ('2', 0, 5, True, 2.0):
    general, messages = settings.parse_general({'window': {'columns': bad}})
    check(f'columns = {bad!r} -> default and a message',
          general.columns == 2 and has(messages, 'columns'), messages)
for bad in (299, 2001, '680'):
    general, messages = settings.parse_general({'window': {'height': bad}})
    check(f'height = {bad!r} -> default and a message',
          general.height == 680 and has(messages, 'height'), messages)
general, messages = settings.parse_general({'window': 3})
check('[window] not a table', general.columns == 2 and messages, messages)
general, messages = settings.parse_general({'window': {'colums': 3}})
check('a misspelt key is reported', has(messages, '[window]', 'colums'), messages)
general, messages = settings.parse_general({})
check('[files] missing: the default exclude lists',
      general.exclude[0] == '/usr' and '.git' in general.exclude_names)
general, messages = settings.parse_general({'files': {'exclude': ['/data'], 'exclude_names': []}})
check('[files] given: each list replaces its default',
      (general.exclude, general.exclude_names, messages) == (('/data',), (), []))
general, messages = settings.parse_general({'files': {'exclude': '/usr', 'exclude_name': []}})
check('[files] wrong type and a typo are reported',
      general.exclude[0] == '/usr' and len(general.exclude) > 1
      and has(messages, 'exclude muss') and has(messages, 'exclude_name'), messages)
general, messages = settings.parse_general({'files': 3})
check('[files] not a table', has(messages, '[files]'), messages)
general, messages = settings.parse_general(tomllib.loads(settings.GENERAL_SKELETON))
check('the general skeleton reads without a message', messages == [], messages)
block = settings.GENERAL_SKELETON.split('# [files]')[1]
uncommented = '[files]' + '\n'.join(line[2:] for line in block.splitlines())
general, messages = settings.parse_general(tomllib.loads(uncommented))
check('the commented [files] block is exactly the default',
      (general.exclude, general.exclude_names, messages)
      == (settings.files.DEFAULT_EXCLUDE, settings.files.DEFAULT_EXCLUDE_NAMES, []), messages)
general, messages = settings.parse_general({'windwo': {}})
check('a misspelt table is reported', has(messages, 'windwo'), messages)

section('parse_tiles: groups')
wall, messages = tiles('[[tile]]\ngroup = "A"\napp = "x"\n')
check('no groups: empty wall and a message',
      wall.tiles == [] and has(messages, 'groups fehlt'), messages)
wall, messages = tiles('groups = "A"\n')
check('groups as a string', has(messages, 'groups fehlt'), messages)
wall, messages = tiles('groups = ["A", 3]\n')
check('groups with a number', has(messages, 'groups fehlt'), messages)
wall, messages = tiles('groups = ["A", "B", "A"]\n')
check('a duplicate group is reported, the first counts',
      wall.groups == ['A', 'B'] and has(messages, 'doppelt'), messages)
wall, messages = tiles('groups = []\n')
check('empty groups: fine, nothing to say', (wall.groups, messages) == ([], []))

section('parse_tiles: tiles')
TEXT = '''groups = ["A"]

[[tile]]
group = "A"
app = "code"
size = "large"
pos = [1, 2]

[[tile.shortcut]]
name = "x"
command = "y"

[[tile]]
group = "B"
app = "steam"

[[tile]]
group = "A"
name = "Notes"

[[tile]]
group = "A"
app = "foo"
size = "huge"
pos = [1, 2, 3]
colour = "red"

[[tile]]
app = "nogroup"
'''
wall, messages = tiles(TEXT)
first = wall.tiles[0]
check('a good tile keeps app, size and pos',
      (first.app, first.size, first.pos) == ('code', 'large', (1, 2)), first)
check('its shortcut comes along',
      [(sc.name, sc.command) for sc in first.shortcuts] == [('x', 'y')],
      first.shortcuts)
check('its header line is known', first.line == 3, first.line)
check('unknown group: left out, with the line',
      has(messages, 'Zeile 13', '„B“'), messages)
check('name without command: left out',
      has(messages, 'Zeile 17', 'name und command'), messages)
foo = wall.tiles[1]
check('unknown size -> medium', foo.size == 'medium'
      and has(messages, 'Zeile 21', 'huge'), messages)
check('pos of the wrong length -> fitted in', foo.pos is None
      and has(messages, 'Zeile 21', 'pos'), messages)
check('an unknown key is reported as a typo', has(messages, 'Zeile 21', 'unbekannter Schlüssel colour'), messages)
check('tile without group: left out', has(messages, 'Zeile 28', 'ohne group'),
      messages)
check('two tiles survive', [t.label for t in wall.tiles] == ['code', 'foo'])

wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\nname = "N"\ncommand = "c"\n')
check('a tile without app but with name and command counts',
      len(wall.tiles) == 1 and wall.tiles[0].label == 'N' and not messages)
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = 5\n')
check('app as a number: reported, tile left out', not wall.tiles
      and has(messages, 'app muss Text sein'), messages)
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "x"\npos = [true, 0]\n')
check('pos with a boolean is not a pos', wall.tiles[0].pos is None, wall.tiles[0].pos)

section('tile_header_lines')
check('only [[tile]] headers, not [[tile.shortcut]]',
      settings.tile_header_lines(TEXT) == [3, 13, 17, 21, 28],
      settings.tile_header_lines(TEXT))
check('indented headers count',
      settings.tile_header_lines('  [[tile]]\n[[ tile ]]\n') == [1, 2])

section('assemble')
wall, _ = tiles('''groups = ["A", "B"]
[[tile]]
group = "A"
app = "code"
[[tile]]
group = "A"
app = "gone"
[[tile]]
group = "A"
app = "x.desktop"
size = "large"
pos = [3, 0]
''')
known = {'code.desktop', 'x.desktop'}
resolve = lambda i: i if i in known else (f'{i}.desktop' if f'{i}.desktop' in known else None)
groups, messages = settings.assemble(wall, resolve)
check('groups in file order, empty ones too', [g for g, _ in groups] == ['A', 'B'])
check('the .desktop ending is filled in',
      groups[0][1][0].tile.app == 'code.desktop', groups[0][1][0].tile.app)
check('a missing app is reported and left out',
      has(messages, 'Zeile 5', 'gone', 'nicht installiert')
      and len(groups[0][1]) == 2, messages)
check('a pos that sticks out is reported with where it went instead',
      has(messages, 'Zeile 8', '[3, 0]', 'eingepasst bei'), messages)

section('syntax errors and files')
def syntax(text):
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return settings.syntax_message('tiles.toml', error)


message = syntax('groups = ["A"]\nsize = large\n')
check('syntax message puts line and column first',
      message.startswith('tiles.toml, Zeile 2, Spalte ') and '(at' not in message,
      message)
message = syntax('groups = [\n')
check('an unclosed bracket is reported at the end of the file',
      message.startswith('tiles.toml, am Dateiende: '), message)

folder = Path(tempfile.mkdtemp(prefix='kachel-test-'))
written, problems = settings.ensure_files(folder)
check('all three skeletons are written', sorted(p.name for p in written)
      == ['kachel.toml', 'rail.toml', 'tiles.toml'] and not problems, written)
rail_read, messages = settings.load_rail(folder)
check('the rail skeleton reads cleanly', rail_read == settings.default_rail()
      and not messages, messages)
general, messages = settings.load_general(folder)
check('the general skeleton reads cleanly', general.columns == 2 and not messages,
      messages)
wall, messages = settings.load_tiles(folder)
check('the tiles skeleton reads cleanly and is empty',
      wall is not None and wall.tiles == [] and not messages, messages)

(folder / 'tiles.toml').write_text('groups = [\n', encoding='utf-8')
check('an existing, even broken file is never overwritten',
      settings.ensure_files(folder) == ([], [])
      and (folder / 'tiles.toml').read_text() == 'groups = [\n')
wall, messages = settings.load_tiles(folder)
check('a broken file: None (keep the old wall) and the syntax message',
      wall is None and has(messages, 'am Dateiende'), messages)

(folder / 'tiles.toml').unlink()
wall, messages = settings.load_tiles(folder)
check('a missing file: empty wall, nothing to say',
      wall is not None and not wall.tiles and not messages, messages)
for path in folder.iterdir():
    path.unlink()
folder.rmdir()

section('review fixes')
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "x"\nsize = ["large"]\n')
check('size as a list: reported, not a crash', wall.tiles[0].size == 'medium'
      and has(messages, 'size'), messages)
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "x"\nsize = {}\n')
check('size as a table: reported, not a crash', wall.tiles[0].size == 'medium')
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "x"\npos = [0, 100000000]\n')
check('a row far down is refused, not a wall of a billion pixels',
      wall.tiles[0].pos is None and has(messages, 'zu weit unten'), messages)
wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "x"\npos = [0, 99]\n')
check('row 99 is still fine', wall.tiles[0].pos == (0, 99), messages)

blocked = Path(tempfile.mkdtemp(prefix='kachel-test-')) / 'file-not-folder'
blocked.write_text('x', encoding='utf-8')
written, problems = settings.ensure_files(blocked)
check('a folder that cannot be made is a problem, not a crash',
      written == [] and len(problems) == 3, problems)
blocked.unlink()
blocked.parent.rmdir()

section('shortcuts')
SC = """groups = ["A"]

[[tile]]
group = "A"
app = "term"
size = "large"

[[tile.shortcut]]
name = "ssh"
icon = "ms:dns"
command = "ssh home"
terminal = true

[[tile.shortcut]]
name = "quiet"
command = "touch x"

[[tile.shortcut]]
name = "no command"

[[tile.shortcut]]
name = "bad"
command = "y"
terminal = "ja"
comand = "typo"

[[tile.shortcut]]
name = "four"
command = "4"

[[tile.shortcut]]
name = "five"
command = "5"

[[tile]]
group = "A"
app = "web"
size = "wide"

[[tile.shortcut]]
name = "w1"
command = "1"

[[tile.shortcut]]
name = "w2"
command = "2"

[[tile.shortcut]]
name = "w3"
command = "3"

[[tile]]
group = "A"
app = "small"
size = "medium"

[[tile.shortcut]]
name = "m"
command = "m"
"""
wall, messages = tiles(SC)
term, web, medium = wall.tiles
first = term.shortcuts[0]
check('a shortcut keeps name, icon, command and terminal',
      (first.name, first.icon, first.command, first.terminal)
      == ('ssh', 'ms:dns', 'ssh home', True), first)
check('its header line is known', first.line == 8, first.line)
check('terminal defaults to false, icon to none',
      term.shortcuts[1].terminal is False and term.shortcuts[1].icon is None)
check('without command: left out', has(messages, 'Zeile 18', 'name und command'),
      messages)
check('terminal must be a boolean', has(messages, 'Zeile 21', 'terminal')
      and term.shortcuts[2].terminal is False, messages)
check('a misspelt shortcut key is reported', has(messages, 'Zeile 21', 'comand'),
      messages)
check('large keeps four, the fifth is reported at its line',
      [s.name for s in term.shortcuts] == ['ssh', 'quiet', 'bad', 'four']
      and has(messages, 'Zeile 31', 'höchstens 4', '1 fallen weg'), messages)
check('wide keeps two', [s.name for s in web.shortcuts] == ['w1', 'w2']
      and has(messages, 'Zeile 48', 'höchstens 2'), messages)
check('medium carries none, and says so', medium.shortcuts == []
      and has(messages, 'Zeile 52', 'medium trägt keine Shortcuts'), messages)

check('shortcut_header_lines groups them per tile',
      settings.shortcut_header_lines(SC) == [[8, 14, 18, 21, 27, 31], [40, 44, 48], [57]],
      settings.shortcut_header_lines(SC))
check('a shortcut header before any tile is ignored',
      settings.shortcut_header_lines('[[tile.shortcut]]\n[[tile]]\n') == [[]])

wall, messages = tiles('groups = ["A"]\n[[tile]]\ngroup = "A"\napp = "t"\nsize = "large"\nshortcut = ["ssh home"]\n')
check('a shortcut that is not a table is reported, not dropped silently',
      wall.tiles[0].shortcuts == [] and has(messages, 'Shortcut muss als'), messages)

section('parse_color')
check('#rgb', settings.parse_color('#f00') == (1.0, 0.0, 0.0, 1.0))
check('#rrggbb', settings.parse_color('#00ff00') == (0.0, 1.0, 0.0, 1.0))
check('#rrggbbaa', settings.parse_color('#0000ff80') == (0.0, 0.0, 1.0, 128 / 255))
check('rgba()', settings.parse_color('rgba(255, 0, 0, 0.5)') == (1.0, 0.0, 0.0, 0.5))
check('rgb()', settings.parse_color('rgb(0,0,255)') == (0.0, 0.0, 1.0, 1.0))
for bad in ('red', '#12', '#gggggg', 'rgba(1, 2, 3)', 'rgb(1, 2, 3, 0.5)',
            'rgba(300, 0, 0, 1)', 'rgba(0, 0, 0, 2)', 5, None):
    check(f'{bad!r} is no colour', settings.parse_color(bad) is None)


def rail(text):
    return settings.parse_rail(tomllib.loads(text), text)


section('parse_rail')
r, messages = rail(settings.RAIL_SKELETON)
check('the skeleton reads without a single message', messages == [], messages)
check('the skeleton: 7 folders, 6 actions', (len(r.folders), len(r.actions)) == (7, 6))
check('switching off and restarting ask first, nothing else',
      [a.name for a in r.actions if a.confirm] == ['Ausschalten', 'Neustart'])
check('suspend, not hibernate',
      any(a.command == 'systemctl suspend' for a in r.actions)
      and not any('hibernate' in a.command for a in r.actions))

r, messages = rail('')
check('an empty file: the defaults, nothing to say',
      (len(r.folders), len(r.actions), messages) == (7, 6, []))
check('default entries carry no line numbers into someone else\'s file',
      all(f.line is None for f in r.folders) and all(a.line is None for a in r.actions))
r, messages = rail('folder = []\naction = []\n')
check('folder = [] and action = []: none at all', (r.folders, r.actions, messages) == ([], [], []))
r, messages = rail('[[action]]\nname = "x"\ncommand = "true"\n')
check('only actions written: default folders, just that action',
      len(r.folders) == 7 and [a.name for a in r.actions] == ['x'])

RAIL = """[[folder]]
path = "~/Projekte"
name = "Code"
icon = "ms:code"

[[folder]]
name = "ohne Pfad"

[[folder]]
path = "~"
colour = "x"

[[action]]
name = "Eins"
command = "true"
confirm = { label = "Echt?", color = "#4caf5080", duration = 10000 }

[[action]]
name = "Zwei"
command = "true"
confirm = true
terminal = "ja"

[[action]]
name = "ohne Befehl"

[[action]]
name = "Drei"
command = "true"
confirm = { color = "grün", duration = 99, lable = "x" }

[[action]]
name = "Vier"
command = "true"
confirm = "ja"

[[action]]
name = "Fünf"
command = "true"

[[action]]
name = "Sechs"
command = "true"

[[action]]
name = "Sieben"
command = "true"

[[action]]
name = "Acht"
command = "true"
"""
r, messages = rail(RAIL)
check('folders as written', [(f.path, f.name, f.icon) for f in r.folders]
      == [('~/Projekte', 'Code', 'ms:code'), ('~', None, None)], r.folders)
check('a folder without path is reported at its line',
      has(messages, 'Zeile 6', 'ohne path'), messages)
check('a misspelt folder key is reported', has(messages, 'Zeile 9', 'colour'), messages)
one = r.actions[0]
check('confirm as a table', one.confirm == settings.Confirm(
      'Echt?', (0x4c / 255, 0xaf / 255, 0x50 / 255, 0x80 / 255), 10000), one.confirm)
check('confirm = true: the defaults', r.actions[1].confirm == settings.Confirm())
check('terminal must be a boolean', r.actions[1].terminal is False
      and has(messages, 'Zeile 18', 'terminal'), messages)
check('an action without command is reported', has(messages, 'Zeile 24', 'name und command'),
      messages)
three = r.actions[2].confirm
check('a bad colour and duration fall back, each reported',
      three.color == settings.CONFIRM_RED and three.duration == 4000
      and has(messages, 'Zeile 27', 'color') and has(messages, 'Zeile 27', 'duration'),
      messages)
check('a misspelt confirm key is reported', has(messages, 'confirm', 'lable'), messages)
check('confirm = "ja" counts as true, with a message',
      r.actions[3].confirm == settings.Confirm() and has(messages, 'Zeile 32', 'confirm'),
      messages)
check('at most six; the seventh is reported at its line',
      [a.name for a in r.actions] == ['Eins', 'Zwei', 'Drei', 'Vier', 'Fünf', 'Sechs']
      and has(messages, 'Zeile 45', 'höchstens 6', '2 fallen weg'), messages)
r, messages = rail('folder = "~"\n')
check('folder not as [[folder]]: defaults and a message',
      len(r.folders) == 7 and has(messages, '[[folder]]'), messages)
r, messages = rail('[[foldr]]\npath = "~"\n')
check('a misspelt table is reported', has(messages, 'foldr'), messages)

harness.report()
