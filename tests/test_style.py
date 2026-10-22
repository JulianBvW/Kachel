'''Sizes from the system font, and the style sheet built from them.'''

import harness
from harness import check, section

from kachel import style

section('base_size')
check('Ubuntu 10 -> 10 pt', style.base_size('Ubuntu 10') == 10)
check('Noto Sans Bold 11 -> 11 pt', style.base_size('Noto Sans Bold 11') == 11)
check('no size -> fallback', style.base_size('Ubuntu') == style.FALLBACK_SIZE)
check('empty name -> fallback', style.base_size('') == style.FALLBACK_SIZE)
check('None -> fallback', style.base_size(None) == style.FALLBACK_SIZE)

section('css')
sheet = style.css(10).decode()
check('category label at -1.5 pt', 'font-size: 8.5pt;' in sheet)
check('base size on the root', 'font-size: 10pt;' in sheet)
check('secondary text at -1 pt', 'font-size: 9pt;' in sheet)
check('tile fill 0.08', 'rgba(255, 255, 255, 0.08)' in sheet)
check('hover ring inset 1 px 0.30', 'inset 0 0 0 1px rgba(255, 255, 255, 0.30)' in sheet)
sheet = style.css(11).decode()
check('follows a bigger font', 'font-size: 9.5pt;' in sheet and 'font-size: 11pt;' in sheet)

sheet = style.css(10, 'DejaVu Sans Mono').decode()
check('search field at +5 pt', 'font-size: 15pt;' in sheet)
check('key hints in the system monospace', 'font-family: "DejaVu Sans Mono";' in sheet)
check('monospace family is read from the system',
      isinstance(style.monospace_family(), str) and style.monospace_family())

section('effects')
sheet = style.css(10).decode()
check('our surfaces fade in 180 ms, not at the theme\'s pace',
      'transition: background-color 180ms ease, box-shadow 180ms ease' in sheet)
check('a pressed surface shrinks by 2 px a side', 'margin: 2px;' in sheet)
off = style.css(10, animated=False).decode()
check('without effects: no transition time, no press',
      'background-color 0ms' in off and 'margin: 0px;' in off)
check('without effects: a lighter fill instead of the glow',
      'rgba(255, 255, 255, 0.13)' in off and 'rgba(255, 255, 255, 0.13)' not in sheet)

harness.report()
