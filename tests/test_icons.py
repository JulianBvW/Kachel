'''The three forms an icon field can take.'''

import harness
from harness import check, section

from kachel import icons

section('parse_icon')
check('ms: symbol', icons.parse_icon('ms:power_settings_new') == ('ms', 'power_settings_new'))
check('theme: name', icons.parse_icon('theme:system-shutdown') == ('theme', 'system-shutdown'))
check('absolute path', icons.parse_icon('/usr/share/x.svg') == ('file', '/usr/share/x.svg'))
check('home path', icons.parse_icon('~/i.png') == ('file', '~/i.png'))
check('relative path', icons.parse_icon('icons/a.svg') == ('file', 'icons/a.svg'))
check('surrounding spaces', icons.parse_icon('  ms:dns ') == ('ms', 'dns'))
check('empty', icons.parse_icon('') is None)
check('None', icons.parse_icon(None) is None)
check('ms: without a name', icons.parse_icon('ms:') is None)
check('theme: without a name', icons.parse_icon('theme:  ') is None)
check('not a string', icons.parse_icon(5) is None)

section('the bundled font')
check('both font files are there', all((icons.FONT_DIR / n).is_file() for n in icons.FONT_FILES))
check('the licence is there', (icons.FONT_DIR / 'LICENSE').is_file())
check('loading them works', icons.load_fonts())
check('Pango then knows the symbol font', icons.ms_available())

harness.report()
