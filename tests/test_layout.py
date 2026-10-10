'''Fitting tiles onto the 6-column grid, and groups onto the wall.'''

from dataclasses import dataclass

import harness
from harness import check, section

from kachel import layout


@dataclass
class T:
    label: str
    size: str = 'medium'
    pos: tuple = None


def spots(placements):
    return [(p.tile.label, p.col, p.row, p.auto) for p in placements]


section('span')
check('1 cell = 48', layout.span(1) == 48)
check('2 cells = 102', layout.span(2) == 102)
check('4 cells = 210', layout.span(4) == 210)
check('6 cells = 318, a whole group', layout.span(6) == layout.GROUP_WIDTH)
check('0 cells = 0', layout.span(0) == 0)

section('place: fitting in, in file order')
got = spots(layout.place([T('a'), T('b'), T('c'), T('d')]))
check('three mediums fill a row, the fourth starts the next',
      got == [('a', 0, 0, True), ('b', 2, 0, True), ('c', 4, 0, True),
              ('d', 0, 2, True)], got)

got = spots(layout.place([T('L', 'large'), T('m1'), T('m2')]))
check('large on the left, two mediums stack beside it',
      got == [('L', 0, 0, True), ('m1', 4, 0, True), ('m2', 4, 2, True)], got)

got = spots(layout.place([T('s1', 'small'), T('w', 'wide'), T('s2', 'small')]))
check('a gap left by a wide tile is filled by a later small one',
      got == [('s1', 0, 0, True), ('w', 1, 0, True), ('s2', 5, 0, True)], got)

got = spots(layout.place([T('w1', 'wide'), T('w2', 'wide')]))
check('two wides do not fit side by side',
      got == [('w1', 0, 0, True), ('w2', 0, 2, True)], got)

check('no tiles, no placements', layout.place([]) == [])

section('place: hand-placed tiles')
got = spots(layout.place([T('a'), T('b', pos=(0, 0))]))
check('a pos wins over an earlier auto tile',
      got == [('a', 2, 0, True), ('b', 0, 0, False)], got)

got = spots(layout.place([T('x', pos=(4, 6))]))
check('a pos far down leaves the space above empty',
      got == [('x', 4, 6, False)], got)

placements = layout.place([T('L', 'large', pos=(3, 0))])
check('a large at column 3 sticks out and is fitted in instead',
      spots(placements) == [('L', 0, 0, True)], spots(placements))
check('... with a reason that names the width',
      '4 breit' in (placements[0].reason or ''), placements[0].reason)

placements = layout.place([T('a', pos=(0, 0)), T('b', pos=(1, 1))])
check('an overlapping pos is fitted in',
      spots(placements) == [('a', 0, 0, False), ('b', 2, 0, True)],
      spots(placements))
check('... and the reason names who is in the way',
      placements[1].reason == 'überdeckt a', placements[1].reason)

placements = layout.place([T('n', pos=(-1, 0))])
check('a negative pos is fitted in', placements[0].auto
      and 'negativ' in placements[0].reason, placements[0].reason)

check('a used pos carries no reason',
      layout.place([T('a', pos=(2, 0))])[0].reason is None)

section('group_rows')
check('empty group has no rows', layout.group_rows([]) == 0)
check('large is 4 rows', layout.group_rows(layout.place([T('L', 'large')])) == 4)
check('tallest bottom edge counts',
      layout.group_rows(layout.place([T('s', 'small', pos=(0, 5))])) == 6)

section('arrange')
one = [('A', layout.place([T('a')]))]
arrangement = layout.arrange(one, columns=2)
name, header = arrangement.headers[0]
check('header at the padding corner',
      (header.x, header.y, header.width, header.height) == (24, 18, 318, 18),
      header)
_p, rect = arrangement.tiles[0]
check('first tile below header and gap',
      (rect.x, rect.y, rect.width, rect.height) == (24, 46, 102, 102), rect)
check('height: padding, header, gap, tile, padding',
      arrangement.height == 18 + 18 + 10 + 102 + 28, arrangement.height)

cell = layout.place([T('m', pos=(2, 0))])
_p, rect = layout.arrange([('A', cell)], 2).tiles[0]
check('medium at cell (2, 0) sits 108 px in', rect.x - 24 == 108, rect)

two = [('A', layout.place([T('L', 'large')])), ('B', layout.place([T('s', 'small')])),
       ('C', layout.place([T('c')]))]
arrangement = layout.arrange(two, columns=2)
xs = [(n, r.x, r.y) for n, r in arrangement.headers]
check('two groups side by side, the third starts a new row',
      xs[0] == ('A', 24, 18) and xs[1] == ('B', 24 + 318 + 28, 18)
      and xs[2][0] == 'C' and xs[2][1] == 24, xs)
row_one = 18 + 10 + 210
check('the new row starts below the taller group of the first row',
      xs[2][2] == 18 + row_one + 28, xs[2])

arrangement = layout.arrange(two, columns=1)
ys = [r.y for _n, r in arrangement.headers]
check('one column: groups stack', ys == sorted(ys) and len(set(ys)) == 3, ys)

empty = layout.arrange([('Leer', [])], 2)
check('an empty group shows its header', len(empty.headers) == 1
      and not empty.tiles)
check('no groups: only the padding', layout.arrange([], 2).height == 18 + 28)

harness.report()
