'''Window size and place. Pure arithmetic, no GTK, so it can be tested.'''

# The tile grid the width has to land on. A rail on the left, padding on both
# sides of the tile area, and groups of 318 px with 28 px between them.
RAIL = 60
PADDING = 24
GROUP = 318
GROUP_GAP = 28


def window_width(columns):
    '''The width that fits `columns` tile groups exactly.

    1 -> 426, 2 -> 772, 3 -> 1118, 4 -> 1464. Anything below one column is
    taken as one: a window with no room for tiles is no use to anyone.
    '''
    columns = max(1, int(columns))
    return RAIL + 2 * PADDING + columns * GROUP + (columns - 1) * GROUP_GAP


def centered(area_x, area_y, area_width, area_height, width, height):
    '''Top-left corner that centres a width x height window in an area.

    The area is a monitor's work area, so the panel is never covered. A
    window bigger than the area is pinned to its top-left edge instead of
    being pushed off the screen.
    '''
    x = area_x + max(0, (area_width - width) // 2)
    y = area_y + max(0, (area_height - height) // 2)
    return x, y
