'''The --grid text for a known wall.'''

from dataclasses import dataclass

import harness
from harness import check, section

from kachel import gridtext, layout


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

harness.report()
