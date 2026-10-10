'''Window width from the tile grid, and centring in a work area.'''

import harness
from harness import check, section

from kachel import geometry

section('window_width')
for columns, expected in ((1, 426), (2, 772), (3, 1118), (4, 1464)):
    width = geometry.window_width(columns)
    check(f'{columns} columns -> {expected}', width == expected, width)
check('0 columns is taken as 1', geometry.window_width(0) == 426)
check('negative columns is taken as 1', geometry.window_width(-3) == 426)

section('centered')
check('this machine: 2560x1035 work area, 772x680 window',
      geometry.centered(0, 0, 2560, 1035, 772, 680) == (894, 177),
      geometry.centered(0, 0, 2560, 1035, 772, 680))
check('second monitor to the right keeps its offset',
      geometry.centered(2560, 0, 1920, 1080, 772, 680) == (2560 + 574, 200),
      geometry.centered(2560, 0, 1920, 1080, 772, 680))
check('panel at the top shifts the area down',
      geometry.centered(0, 45, 2560, 1035, 772, 680) == (894, 222))
check('window wider than the area is pinned left, not pushed off',
      geometry.centered(0, 0, 400, 1035, 772, 680) == (0, 177))
check('window taller than the area is pinned to the top',
      geometry.centered(100, 50, 2560, 600, 772, 680) == (100 + 894, 50))

harness.report()
