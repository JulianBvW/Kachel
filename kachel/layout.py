'''Where every tile goes. Pure arithmetic, no GTK, so it can be tested.

Two grids, one inside the other. Groups run across the wall in `columns`
columns of 318 px. Inside a group, tiles sit on a grid of 6 columns of 48 px
cells with 6 px between them.
'''

from dataclasses import dataclass

# size -> (columns, rows) in cells
SIZES = {
    'small': (1, 1),
    'medium': (2, 2),
    'wide': (4, 2),
    'large': (4, 4),
}

GRID_COLUMNS = 6
# The lowest row a hand-placed tile may ask for. Far more than any wall
# needs, and small enough that a typo cannot ask for a wall of a billion
# pixels.
MAX_ROW = 99
CELL = 48
CELL_GAP = 6

GROUP_WIDTH = 318   # 6 * 48 + 5 * 6
GROUP_GAP = 28
HEADER_HEIGHT = 18
HEADER_GAP = 10

PAD_TOP = 18
PAD_SIDE = 24
PAD_BOTTOM = 28


@dataclass
class Placement:
    '''One tile on its group's grid.

    `auto` is True when the tile was fitted in rather than put where its
    `pos` said; `reason` says why a given `pos` was not used, or is None.
    '''
    tile: object
    col: int
    row: int
    auto: bool
    reason: str = None


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass
class Arrangement:
    '''Pixel positions for the whole wall, relative to its top-left.'''
    headers: list   # of (group name, Rect)
    tiles: list     # of (Placement, Rect)
    height: int


def span(cells):
    '''Pixels covered by `cells` cells and the gaps between them.'''
    return cells * CELL + max(0, cells - 1) * CELL_GAP


def place(tiles):
    '''Put each tile on the grid. Returns one Placement per tile, in order.

    Each tile needs `.size`, `.pos` (a (col, row) tuple or None) and
    `.label` (for the reason text). Tiles with a usable pos go first, in the
    order of the list, so a hand-placed tile always wins over one that was
    only fitted in. The rest take the first free spot that is big enough:
    top row first, left to right within a row. The grid grows downwards as
    far as it needs to.
    '''
    taken = {}          # (col, row) -> the tile holding that cell
    result = [None] * len(tiles)
    reasons = {}

    def cells(col, row, width, height):
        return [(c, r) for r in range(row, row + height)
                for c in range(col, col + width)]

    for index, tile in enumerate(tiles):
        if tile.pos is None:
            continue
        width, height = SIZES[tile.size]
        col, row = tile.pos
        if col < 0 or row < 0:
            reasons[index] = 'Position darf nicht negativ sein'
            continue
        if col + width > GRID_COLUMNS:
            reasons[index] = (f'{tile.size} ist {width} breit, passt ab '
                              f'Spalte {col} nicht in die 6 Spalten')
            continue
        wanted = cells(col, row, width, height)
        clash = next((taken[cell] for cell in wanted if cell in taken), None)
        if clash is not None:
            reasons[index] = f'überdeckt {clash.label}'
            continue
        for cell in wanted:
            taken[cell] = tile
        result[index] = Placement(tile, col, row, auto=False)

    for index, tile in enumerate(tiles):
        if result[index] is not None:
            continue
        width, height = SIZES[tile.size]
        row = 0
        while result[index] is None:
            for col in range(GRID_COLUMNS - width + 1):
                wanted = cells(col, row, width, height)
                if not any(cell in taken for cell in wanted):
                    for cell in wanted:
                        taken[cell] = tile
                    result[index] = Placement(tile, col, row, auto=True,
                                              reason=reasons.get(index))
                    break
            row += 1
    return result


def group_rows(placements):
    '''How many grid rows a group needs.'''
    return max((p.row + SIZES[p.tile.size][1] for p in placements), default=0)


def arrange(groups, columns):
    '''Pixel rectangles for headers and tiles, plus the total height.

    `groups` is a list of (name, placements). Groups fill the wall row by
    row, `columns` to a row; a row is as tall as its tallest group, so the
    next row starts level. An empty group still shows its header.
    '''
    columns = max(1, columns)
    headers, tiles = [], []
    y = PAD_TOP

    for start in range(0, len(groups), columns):
        row_groups = groups[start:start + columns]
        row_height = 0
        for slot, (name, placements) in enumerate(row_groups):
            x = PAD_SIDE + slot * (GROUP_WIDTH + GROUP_GAP)
            headers.append((name, Rect(x, y, GROUP_WIDTH, HEADER_HEIGHT)))
            top = y + HEADER_HEIGHT + HEADER_GAP
            for p in placements:
                width, height = SIZES[p.tile.size]
                tiles.append((p, Rect(x + p.col * (CELL + CELL_GAP),
                                      top + p.row * (CELL + CELL_GAP),
                                      span(width), span(height))))
            rows = group_rows(placements)
            height = HEADER_HEIGHT + HEADER_GAP + span(rows)
            row_height = max(row_height, height)
        y += row_height + GROUP_GAP

    if groups:
        y -= GROUP_GAP   # no gap after the last row
    return Arrangement(headers, tiles, y + PAD_BOTTOM)
