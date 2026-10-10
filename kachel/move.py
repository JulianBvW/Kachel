'''Where a tile that is being moved could land. Pure.

Every cell of its group where it fits is a spot, and below the group's last
row there are as many empty rows as the tile is high, so it can go under
everything too. How the file gets there:

- If putting the tile at another place in the order of the file already
  lands it on that cell, that is all that changes: a tile without `pos`
  goes to the first free spot (layout.place), the others move up.
- Otherwise the tile gets that cell as its `pos`. A tile placed by hand
  that is in the way loses its `pos` and is fitted in again.
'''

from dataclasses import dataclass, field, replace

from . import layout


@dataclass
class Spot:
    '''The tile lands on (col, row).

    By order: it is put before `before` (None: behind the group's last
    tile), without `pos`. By hand: `pos` is set to (col, row) and the
    tiles in `loosen` lose theirs. `change` is 0 when nothing would
    change at all.'''
    col: int
    row: int
    before: object = None
    pos: tuple = None
    loosen: list = field(default_factory=list)
    change: int = 0


def _covers(col, row, size, other_col, other_row, other_size):
    width, height = layout.SIZES[size]
    other_width, other_height = layout.SIZES[other_size]
    return (col < other_col + other_width and other_col < col + width
            and row < other_row + other_height and other_row < row + height)


def _by_order(tiles, moving):
    '''{(col, row): Spot} for every place a new order reaches; of two
    orders with the same result, the smaller change.'''
    others = [tile for tile in tiles if tile is not moving]
    # By identity: two tiles of the same app are equal as dataclasses.
    now = next(i for i, tile in enumerate(tiles) if tile is moving)
    loose = replace(moving, pos=None)
    found = {}
    for index in range(len(others) + 1):
        order = others[:index] + [loose] + others[index:]
        placement = layout.place(order)[index]
        change = abs(index - now) + (moving.pos is not None)
        spot = Spot(placement.col, placement.row,
                    before=others[index] if index < len(others) else None,
                    change=change)
        key = (spot.col, spot.row)
        if key not in found or spot.change < found[key].change:
            found[key] = spot
    return found


def extra_rows(size):
    '''How many empty rows the group gets below while a tile is moved.'''
    return layout.SIZES[size][1]


def spots(tiles, moving):
    '''Every spot `moving` can land on in its group (`tiles`, in the order
    of the file, `moving` included). Each one is checked against
    layout.place: the frame shows exactly where the tile will be.'''
    width, height = layout.SIZES[moving.size]
    placed = layout.place(tiles)
    rows = min(layout.group_rows(placed) + extra_rows(moving.size),
               layout.MAX_ROW + height)
    # Alone in its group there is no tile to put it before or behind.
    ordered = _by_order(tiles, moving) if len(tiles) > 1 else {}
    pinned = [t for t in tiles if t.pos is not None and t is not moving]
    found = []
    for row in range(rows - height + 1):
        for col in range(layout.GRID_COLUMNS - width + 1):
            here = (col, row)
            if moving.pos == here:
                found.append(Spot(col, row, pos=here, change=0))
                continue
            if here in ordered:
                found.append(ordered[here])
                continue
            # Every tile whose pos is in the way, used or not: freeing a
            # cell can let an unused pos win again.
            loosen = [t for t in pinned
                      if _covers(col, row, moving.size,
                                 t.pos[0], t.pos[1], t.size)]
            spot = Spot(col, row, pos=here, loosen=loosen, change=1)
            if _lands(tiles, moving, spot) == here:
                found.append(spot)
    return found


def _order(tiles, moving, spot):
    '''The group in the order of the file after the move, and the moved
    tile in it.'''
    others = [replace(t, pos=None) if any(t is l for l in spot.loosen)
              else t for t in tiles if t is not moving]
    if spot.pos is not None:       # by hand: it keeps its place in the order
        index = next(i for i, t in enumerate(tiles) if t is moving)
    elif spot.before is None:
        index = len(others)
    else:
        index = next(i for i, t in enumerate(
            t for t in tiles if t is not moving) if t is spot.before)
    loose = replace(moving, pos=spot.pos)
    return others[:index] + [loose] + others[index:], loose


def result(tiles, moving, spot):
    '''The group's placements after the move, as the wall will show it.'''
    return layout.place(_order(tiles, moving, spot)[0])


def _lands(tiles, moving, spot):
    order, loose = _order(tiles, moving, spot)
    return next((p.col, p.row) for p in layout.place(order)
                if p.tile is loose)


def rect(spot, size):
    '''(x, y, width, height) of a spot in pixels, from the group's top
    left.'''
    width, height = layout.SIZES[size]
    step = layout.CELL + layout.CELL_GAP
    return (spot.col * step, spot.row * step,
            layout.span(width), layout.span(height))


def nearest(found, size, x, y):
    '''The spot whose middle is nearest to (x, y), pixels from the group's
    top left; on a tie, the one that changes less.'''
    def distance(spot):
        left, top, width, height = rect(spot, size)
        dx = left + width / 2 - x
        dy = top + height / 2 - y
        return (dx * dx + dy * dy, spot.change)
    return min(found, key=distance)
