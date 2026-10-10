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
check('its shortcut comes along', first.shortcuts == [{'name': 'x', 'command': 'y'}],
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
check('both skeletons are written', sorted(p.name for p in written)
      == ['kachel.toml', 'tiles.toml'] and not problems, written)
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
      written == [] and len(problems) == 2, problems)
blocked.unlink()
blocked.parent.rmdir()

harness.report()
