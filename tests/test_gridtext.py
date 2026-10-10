'''The --grid text for a known wall.'''

from dataclasses import dataclass
from pathlib import Path

import harness
from harness import check, section

from kachel import gridtext, layout, railmodel, settings


@dataclass
class T:
    label: str
    size: str = 'medium'
    pos: tuple = None
    shortcuts: tuple = ()


@dataclass
class S:
    name: str
    command: str
    terminal: bool = False


groups = [('Arbeit', layout.place([T('term', 'large', (0, 0)), T('code')])),
          ('Leer', [])]
text = gridtext.render(groups, ['tiles.toml, Zeile 3: kaputt'])
lines = text.splitlines()

section('render')
check('group name on its own line', lines[0] == 'Arbeit', lines[0])
check('column ruler', lines[1] == '       0 1 2 3 4 5', repr(lines[1]))
check('first row shows both tiles', lines[2] == '    0  A A A A B B', repr(lines[2]))
check('last row of the large tile, free cells as dots',
      lines[5] == '    3  A A A A . .', repr(lines[5]))
check('legend: placed by hand, no (auto)',
      'A term  large  [0, 0]' in text and 'A term  large  [0, 0]  (auto)' not in text)
check('legend: fitted in is marked', 'B code  medium [4, 0]  (auto)' in text, text)
check('an empty group says so', '  (leer)' in lines, lines)
check('messages at the end', lines[-1] == '  tiles.toml, Zeile 3: kaputt'
      and '1 Meldung(en):' in lines, lines[-3:])
check('no messages: says so', gridtext.render([]).endswith('Keine Meldungen.\n'))

term = T('term', 'large', (0, 0), (S('ssh', 'ssh home', True), S('quiet', 'touch x')))
text = gridtext.render([('A', layout.place([term]))])
check('shortcuts are listed under their tile, terminal marked',
      '      › ssh  ssh home  (Terminal)' in text and '      › quiet  touch x\n' in text, text)

section('rail')
folders = [railmodel.RailFolder('Downloads', Path('/h/Downloads'), 'ms:download', '~/Downloads')]
actions = [settings.Action(f'a{i}', f'cmd{i}') for i in range(5)]
actions[1].confirm = settings.Confirm('Echt?', duration=2000)
actions[2].terminal = True
text = gridtext.render([], [], (folders, railmodel.pages(actions)))
check('the rail section comes after the wall', 'Leiste\n  Ordner\n' in text, text)
check('folders with their shown path', '    Downloads  ~/Downloads\n' in text, text)
check('pages numbered, page turners shown',
      '  Aktionen, Seite 1\n' in text and '    › Mehr' in text
      and '  Aktionen, Seite 2\n' in text and '    ‹ Zurück' in text, text)
check('confirm and terminal are marked',
      'a1  cmd1  (Bestätigung: „Echt?“, 2000 ms)' in text
      and 'a2  cmd2  (Terminal)' in text, text)
text = gridtext.render([], [], ([], []))
check('an empty rail says so', text.count('(keine)') == 2, text)

harness.report()
