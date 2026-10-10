'''Changing tiles.toml without touching anything else.'''

import harness
from harness import check, section

from kachel import tomledit as te

# Cut from a real tiles.toml: comments everywhere, aligned keys, a large
# tile with shortcuts, inline comments on headers.
SAMPLE = '''\
# Kachel -- the tile wall.

groups = ["Arbeit", "Internet"]


# -- Arbeit ----------------------------------------------------------

[[tile]]                                  # the reason for the project:
group = "Arbeit"                          # a terminal with buttons
app   = "com.mitchellh.ghostty"
size  = "large"
pos   = [0, 0]

[[tile.shortcut]]
name     = "htop"
command  = "htop"
terminal = true

[[tile.shortcut]]
name     = "Projekte"
command  = "cd ~/Projekte ; ls"
terminal = true

[[tile]]
group = "Arbeit"
app   = "org.x.editor"

[[tile]]
group = "Arbeit"
app   = "thunderbird"
name  = "Thunderbird"   # `name` overrides the app's own
size  = "medium"


# -- Internet --------------------------------------------------------

[[tile]]
group = "Internet"
app   = "firefox"
size  = "medium"
'''


def run(text, *ops):
    new, problem = te.apply(text, *ops)
    return new, problem


def diff(old, new):
    import difflib
    return [d for d in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm='', n=0)
            if d[:1] in '+-' and d[:3] not in ('+++', '---')]


section('blocks')
found = te.blocks(SAMPLE)
check('four tiles', len(found) == 4, found)
first = found[0]
check('the first block takes its shortcuts along',
      SAMPLE.splitlines()[first[1] - 1] == 'terminal = true'
      and SAMPLE.splitlines()[first[0]].startswith('[[tile]]'), first)
check('the comment before the next group is not part of a block',
      SAMPLE.splitlines()[found[2][1] - 1].startswith('size'), found[2])

section('set_size')
new, problem = run(SAMPLE, (te.set_size, 8, 'wide'))
check('replaces the size line, keeps the alignment',
      problem is None and diff(SAMPLE, new) == ['-size  = "large"', '+size  = "wide"'], diff(SAMPLE, new or ''))
line_editor = [s + 1 for s, _ in found][1]
new, problem = run(SAMPLE, (te.set_size, line_editor, 'small'))
check('inserts a size line behind app, lined up',
      problem is None and diff(SAMPLE, new) == ['+size  = "small"'], (problem, diff(SAMPLE, new or '')))
check('... right after the app line',
      new.splitlines()[new.splitlines().index('app   = "org.x.editor"') + 1] == 'size  = "small"')
plain = 'groups = ["A"]\n\n[[tile]]\ngroup = "A"\napp = "x"\n\n[[tile.shortcut]]\nname = "s"\ncommand = "c"\n'
new, problem = run(plain, (te.set_size, 3, 'large'))
check('with shortcuts below and no size: it goes into the tile, not the shortcut',
      problem is None and new.index('size') < new.index('[[tile.shortcut]]'), new)
new, problem = run(SAMPLE, (te.set_size, 99, 'wide'))
check('no tile at that line: refused', new is None and 'Zeile 99' in problem, problem)

section('set_group')
new, problem = run(SAMPLE, (te.set_group, 8, 'Internet'))
check('changes the group and drops pos',
      problem is None and diff(SAMPLE, new) == ['-group = "Arbeit"                          # a terminal with buttons',
                                                '+group = "Internet"                          # a terminal with buttons',
                                                '-pos   = [0, 0]'], diff(SAMPLE, new or ''))

section('remove_tile')
new, problem = run(SAMPLE, (te.remove_tile, 8))
removed = diff(SAMPLE, new)
check('the tile and both shortcuts go (15 lines, and one of two blank lines that meet), nothing else',
      problem is None and sum(1 for d in removed if d.startswith('-')) == 16
      and not any(d.startswith('+') for d in removed), removed)
check('the group comment above stays', '# -- Arbeit' in new)
check('the shortcuts of the next tile are untouched', new.count('[[tile.shortcut]]') == 0
      and new.count('[[tile]]') == 3)
last = [s + 1 for s, _ in found][3]
new, problem = run(SAMPLE, (te.remove_tile, last))
check('the last tile: the Internet comment stays, the file still reads',
      problem is None and '# -- Internet' in new and 'firefox' not in new, problem)
only = 'groups = ["A"]\n\n[[tile]]\ngroup = "A"\napp = "x"\n'
new, problem = run(only, (te.remove_tile, 3))
check('the only tile: an empty wall', problem is None and new.strip() == 'groups = ["A"]', (problem, new))

section('add_tile')
new, problem = run(SAMPLE, (te.add_tile, 'Arbeit', 'org.gimp.GIMP'))
lines = new.splitlines()
at = lines.index('app   = "org.gimp.GIMP"')
check('behind the last tile of the group, before the next group comment',
      problem is None and lines[at - 2] == '[[tile]]' and lines[at - 1] == 'group = "Arbeit"'
      and lines.index('# -- Internet --------------------------------------------------------') > at, problem)
new, problem = run(SAMPLE, (te.add_tile, 'Neu', 'vlc'))
check('a group without tiles: at the end', problem is None and new.rstrip().endswith('size  = "medium"')
      and new.index('"vlc"') > new.index('firefox'), problem)
new, problem = run('', (te.add_tile, 'A', 'x'), (te.add_group, 'A'))
check('an empty file: groups and the tile', problem is None
      and te._data(new) == {'groups': ['A'], 'tile': [{'group': 'A', 'app': 'x', 'size': 'medium'}]}, (problem, new))

section('add_group')
new, problem = run(SAMPLE, (te.add_group, 'Spiele'))
check('one-line list: appended', problem is None
      and diff(SAMPLE, new) == ['-groups = ["Arbeit", "Internet"]', '+groups = ["Arbeit", "Internet", "Spiele"]'])
multi = 'groups = [\n  "A",\n  "B",\n]\n'
new, problem = run(multi, (te.add_group, 'C'))
check('one per line with a trailing comma', problem is None and new == 'groups = [\n  "A",\n  "B",\n  "C",\n]\n', new)
multi2 = 'groups = [\n  "A",\n  "B"   # last\n]\n'
new, problem = run(multi2, (te.add_group, 'C'))
check('one per line, no trailing comma, a comment', problem is None
      and te._data(new)['groups'] == ['A', 'B', 'C'], (problem, new))
new, problem = run('groups = []\n', (te.add_group, 'A'))
check('empty list', problem is None and new == 'groups = ["A"]\n', new)
new, problem = run('groups = ["a]b"]\n', (te.add_group, 'x"y'))
check('brackets in names and quotes in the new one',
      problem is None and te._data(new)['groups'] == ['a]b', 'x"y'], (problem, new))
new, problem = run('# just a comment\n', (te.add_group, 'A'))
check('no groups line: one is added', problem is None and te._data(new)['groups'] == ['A'], (problem, new))

commented = 'groups = [\n  # main\n  "A",\n  "B",  # second\n]\n'
new, problem = run(commented, (te.add_group, 'C'))
check('comments inside the list', problem is None and te._data(new)['groups'] == ['A', 'B', 'C'], (problem, new))
new, problem = run('groups = ["C# Dev", "B"]\n', (te.add_group, 'X'))
check('a # inside a name is no comment', problem is None
      and te._data(new)['groups'] == ['C# Dev', 'B', 'X'], (problem, new))

section('several at once')
new, problem = run(SAMPLE, (te.set_group, 8, 'Neu'), (te.add_group, 'Neu'))
check('move into a new group: both changes, checked together', problem is None
      and te._data(new)['groups'][-1] == 'Neu' and te._data(new)['tile'][0]['group'] == 'Neu', problem)

section('verify refuses')
inline = 'groups = ["A"]\ntile = [{group = "A", app = "x", size = "small"}]\n'
new, problem = run(inline, (te.set_size, 2, 'large'))
check('an inline table', new is None and problem, problem)
weird = 'groups = ["A"]\n\n[[tile]]\ngroup = "A"\napp = "x"\nsize = """small"""\n'
new, problem = run(weird, (te.set_size, 3, 'large'))
check('a value written in a way it does not understand', new is None and problem, problem)
check('a broken file', te.verify('groups = [', 'groups = []\n') is not None)
check('a change that does more than expected', te.verify('a = 1\n', 'a = 2\n') is not None)
check('an exact change passes', te.verify('a = 1\n', 'a = 2\n', lambda d: d.__setitem__('a', 2)) is None)
check('toml_string escapes', te.toml_string('a"b\\c\nd') == '"a\\"b\\\\c\\nd"')


section('WallFile')
import os
import tempfile
from pathlib import Path
from kachel.wallfile import WallFile
with tempfile.TemporaryDirectory() as tmp:
    real = Path(tmp) / 'dotfiles'
    real.mkdir()
    (real / 'tiles.toml').write_text(SAMPLE, encoding='utf-8')
    os.chmod(real / 'tiles.toml', 0o640)
    folder = Path(tmp) / 'config'
    folder.mkdir()
    (folder / 'tiles.toml').symlink_to(real / 'tiles.toml')
    wf = WallFile(folder)
    wf.remember(SAMPLE)
    check('a change goes through', wf.change((te.set_size, 8, 'wide')) is None)
    check('the link is still a link, the real file changed, mode kept',
          (folder / 'tiles.toml').is_symlink() and 'size  = "wide"' in (real / 'tiles.toml').read_text()
          and oct(os.stat(real / 'tiles.toml').st_mode & 0o777) == '0o640')
    check('until the wall is rebuilt, the next change waits',
          'neu aufgebaut' in (wf.change((te.set_size, 8, 'small')) or ''))
    wf.remember((real / 'tiles.toml').read_text())
    (real / 'tiles.toml').write_text(SAMPLE + '\n# edited\n', encoding='utf-8')
    check('changed behind its back: refused',
          'gerade geändert' in (wf.change((te.set_size, 8, 'small')) or ''))
    wf.remember((real / 'tiles.toml').read_text())
    check('a change that cannot be checked is not written',
          'nicht sicher' in (wf.change((te.set_size, 99, 'small')) or '')
          and (real / 'tiles.toml').read_text().endswith('# edited\n'))

harness.report()
