'''The app list's sections and alphabet rail.'''

from dataclasses import dataclass

import harness
from harness import check, section

from kachel import listmodel


@dataclass
class A:
    name: str


@dataclass
class Tile:
    app: str


@dataclass
class P:
    tile: Tile


section('letter_of')
for name, letter in (('Firefox', 'F'), ('ärger', 'A'), ('Öffnen', 'O'), ('7-Zip', '#'),
                     ('_x', '#'), ('', '#'), ('  steam', 'S'), ('Ελληνικά', '#'),
                     ('Øvelse', 'O'), ('Łódź', 'L'), ('æble', 'A')):
    check(f'{name!r} -> {letter}', listmodel.letter_of(name) == letter,
          listmodel.letter_of(name))

section('sections')
apps = [A('7-Zip'), A('Anno'), A('Ärger'), A('blender'), A('Zen')]
result = listmodel.sections(apps)
check('letters with apps only, # at the end',
      [letter for letter, _ in result] == ['A', 'B', 'Z', '#'], result)
check('order within a section kept', [a.name for a in result[0][1]] == ['Anno', 'Ärger'])
check('no apps, no sections', listmodel.sections([]) == [])

section('jump_target')
present = {'A', 'B', 'R', 'S'}
check('a letter with apps stays', listmodel.jump_target('S', present) == 'S')
check('an empty one goes to the next', listmodel.jump_target('Q', present) == 'R')
check('an empty one at the end goes back', listmodel.jump_target('#', present) == 'S')
check('C goes on to R', listmodel.jump_target('C', present) == 'R')
check('without apps: None', listmodel.jump_target('A', set()) is None)

section('letter_at')
check('top: A', listmodel.letter_at(0, 270) == 'A')
check('bottom: #', listmodel.letter_at(269, 270) == '#')
check('each gets a tenth here: 25 -> C', listmodel.letter_at(25, 270) == 'C')
check('above and below are clamped',
      listmodel.letter_at(-5, 270) == 'A' and listmodel.letter_at(999, 270) == '#')
check('no height: A', listmodel.letter_at(10, 0) == 'A')

section('pinned_groups')
groups = [('Arbeit', [P(Tile('ghostty.desktop')), P(Tile(None))]),
          ('Spiele', [P(Tile('steam.desktop')), P(Tile('ghostty.desktop'))])]
check('first group wins, a tile without app is skipped',
      listmodel.pinned_groups(groups)
      == {'ghostty.desktop': 'Arbeit', 'steam.desktop': 'Spiele'})

section('current_letter')
offsets = [('A', 0), ('B', 300), ('S', 900)]
check('at the top: A', listmodel.current_letter(offsets, 0) == 'A')
check('just short of B: still A', listmodel.current_letter(offsets, 290) == 'A')
check('at B', listmodel.current_letter(offsets, 300) == 'B')
check('far down: S', listmodel.current_letter(offsets, 5000) == 'S')
check('empty list: None', listmodel.current_letter([], 0) is None)
check('at the very end, the last section counts even below the top',
      listmodel.current_letter(offsets, 700, bottom=700) == 'S')
check('not at the end: as before', listmodel.current_letter(offsets, 600, bottom=700) == 'B')

harness.report()
