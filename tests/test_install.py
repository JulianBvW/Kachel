'''The installer's pure parts: finding a free slot, spotting a taken key.'''

import harness
from harness import check, section

import install

section('next_custom_slot')
check('empty list -> custom0', install.next_custom_slot([]) == 'custom0')
check('this machine: custom0..2 taken -> custom3',
      install.next_custom_slot(['custom0', 'custom1', 'custom2']) == 'custom3')
check('a gap is filled first',
      install.next_custom_slot(['custom0', 'custom2']) == 'custom1')
check('order does not matter',
      install.next_custom_slot(['custom1', 'custom0']) == 'custom2')
check('foreign names are ignored',
      install.next_custom_slot(['foo', 'customX', 'custom']) == 'custom0')

section('accelerator_taken')
bindings = {
    'org.cinnamon.desktop.keybindings.wm begin-move': ['<Alt>F7'],
    'custom shortcut "Zettel: show or hide"': ['F4'],
    'empty': [],
}
check('F7 is free although <Alt>F7 is taken',
      install.accelerator_taken('F7', bindings) is None)
check('F4 is held by Zettel',
      install.accelerator_taken('F4', bindings)
      == 'custom shortcut "Zettel: show or hide"')
check('<Alt>F7 is held by the window move',
      install.accelerator_taken('<Alt>F7', bindings)
      == 'org.cinnamon.desktop.keybindings.wm begin-move')
check('no bindings at all', install.accelerator_taken('F7', {}) is None)

section('normalize_accelerator')
for typed, expected in (
        ('F7', 'F7'), (' F7 ', 'F7'),
        ('<Ctrl>space', '<Primary>space'),
        ('<Super>s', '<Super>s'), ('<Mod4>s', '<Super>s'),
        ('<Alt>F7', '<Alt>F7')):
    got = install.normalize_accelerator(typed)
    check(f'{typed!r} -> {expected}', got == expected, got)
for junk in ('', 'nonsense', '<Ctrl>', '<Foo>F7', 'f7'):
    check(f'{junk!r} is not a shortcut',
          install.normalize_accelerator(junk) is None,
          install.normalize_accelerator(junk))
check('stored lists are normalised, junk dropped',
      install.normalized(['<Mod4>s', 'garbage', 'F7']) == ['<Super>s', 'F7'],
      install.normalized(['<Mod4>s', 'garbage', 'F7']))

harness.report()
