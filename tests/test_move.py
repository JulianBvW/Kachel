'''Where a tile being moved can land.'''

from dataclasses import dataclass

import harness
from harness import check, section

from kachel import layout, move


@dataclass
class T:
    label: str
    size: str = 'medium'
    pos: tuple = None


def at(found, col, row):
    return next(s for s in found if (s.col, s.row) == (col, row))


def lands(tiles, moving, spot):
    '''Where the wall puts the moved tile after the move.'''
    placements = move.result(tiles, moving, spot)
    return next((p.col, p.row) for p in placements if p.tile.label == moving.label)


section('every cell is a spot')
row = [T('a'), T('b'), T('c'), T('d')]       # medium: (0,0) (2,0) (4,0) (0,2)
found = move.spots(row, row[0])
cells = {(s.col, s.row) for s in found}
check('every column it fits in, every row down to two empty ones below',
      cells == {(c, r) for c in range(5) for r in range(5)}, sorted(cells))
check('where it is now: no change', at(found, 0, 0).change == 0)
check('a place the order reaches: by order, no pos',
      at(found, 4, 0).pos is None and at(found, 4, 0).before is row[3])
check('a place it does not: by hand', at(found, 1, 3).pos == (1, 3))
check('the empty rows below: by hand too', at(found, 0, 4).pos == (0, 4))

mixed = [T('big', 'large'), T('s1', 'small'), T('s2', 'small'), T('m', 'medium'),
         T('s3', 'small'), T('p', 'medium', (4, 4))]
bad = []
for moving in mixed:
    for spot in move.spots(mixed, moving):
        if lands(mixed, moving, spot) != (spot.col, spot.row):
            bad.append((moving.label, spot))
check('what the frame shows is where the wall puts it, for every tile and spot', not bad, bad[:3])

small = [T('a', 'small'), T('hole', 'medium'), T('x', 'small')]
found = move.spots(small, small[2])
check('a small tile can go under the others, past a hole it would fill',
      lands(small, small[2], at(found, 2, 2)) == (2, 2) and at(found, 2, 2).pos == (2, 2))

section('tiles placed by hand')
pinned = [T('p', 'medium', (2, 0)), T('a'), T('b')]
found = move.spots(pinned, pinned[1])
spot = at(found, 2, 0)
check('onto a tile placed by hand: that one loses its pos',
      spot.pos == (2, 0) and spot.loosen == [pinned[0]], spot)
check('... and is fitted in elsewhere',
      lands(pinned, pinned[1], spot) == (2, 0))
spot = at(found, 3, 1)
check('half over it is over it too', spot.loosen == [pinned[0]], spot)
check('away from it: it keeps its pos', at(found, 0, 2).loosen == [])
moved = [T('a', 'medium', (4, 2)), T('b'), T('c')]
found = move.spots(moved, moved[0])
check('the moved tile on its own pos: nothing changes', at(found, 4, 2).change == 0)
check('by order, it loses its pos: that is a change',
      at(found, 0, 0).pos is None and at(found, 0, 0).change > 0, at(found, 0, 0))

section('nearest')
found = move.spots(row, row[0])
step = layout.CELL + layout.CELL_GAP
check('the pointer on a cell picks the spot whose middle is nearest',
      (lambda s: (s.col, s.row))(move.nearest(found, 'medium', 3 * step + 50, 2 * step + 50)) == (3, 2))
check('far below the group: the lowest row',
      move.nearest(found, 'medium', 20, 2000).row == 4)
check('above it: the first', (lambda s: (s.col, s.row))(move.nearest(found, 'medium', 0, -500)) == (0, 0))
check('a spot in pixels', move.rect(at(found, 2, 0), 'medium') == (2 * step, 0, 102, 102))
check('empty rows: as many as the tile is high',
      [move.extra_rows(s) for s in ('small', 'medium', 'wide', 'large')] == [1, 2, 2, 4])

section('found in review')
unused = [T('A', 'medium', (0, 0)), T('D', 'small', (1, 1)), T('Y')]
found = move.spots(unused, unused[2])
check('a pos that was not used (covered) is loosened too, the frame stays right',
      all(lands(unused, unused[2], s) == (s.col, s.row) for s in found)
      and (0, 0) in {(s.col, s.row) for s in found})
alone = [T('only', 'medium', (2, 1))]
found = move.spots(alone, alone[0])
check('alone in its group: only by hand, never by order',
      all(s.pos is not None for s in found) and at(found, 0, 0).pos == (0, 0))
back = [T('P', 'medium', (0, 0)), T('Q')]
check('put back on its own pos: nothing changes', at(move.spots(back, back[0]), 0, 0).change == 0)
deep = [T('L', 'large', (0, 98)), T('s', 'small')]
check('no spot below the lowest row the settings allow',
      max(s.row for s in move.spots(deep, deep[1])) == layout.MAX_ROW)

harness.report()
