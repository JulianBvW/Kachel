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

section('with_applet')
here = ['panel1:left:2:grouped-window-list@cinnamon.org:2', 'panel1:right:1:systray@cinnamon.org:3',
        'panel1:right:12:cornerbar@cinnamon.org:14', 'panel1:left:0:menu@example:15']
got = install.with_applet(here)
check('first on the left, left of the menu, a new id',
      got and got[-1] == 'panel1:left:0:kachel@julianbvw:16', got)
check('the menu and the window list move one along, the right side stays',
      got[:-1] == ['panel1:left:3:grouped-window-list@cinnamon.org:2', 'panel1:right:1:systray@cinnamon.org:3',
                   'panel1:right:12:cornerbar@cinnamon.org:14', 'panel1:left:1:menu@example:15'], got)
got = install.with_applet(['panel1:left:1:menu@example:1', 'panel1:right:0:calendar@cinnamon.org:3'])
check('a free place: nothing else moves',
      got == ['panel1:left:1:menu@example:1', 'panel1:right:0:calendar@cinnamon.org:3',
              'panel1:left:0:kachel@julianbvw:4'], got)
got = install.with_applet(['panel2:left:0:grouped-window-list@cinnamon.org:7'])
check('only other panels: first on the left of the first panel',
      got == ['panel2:left:0:grouped-window-list@cinnamon.org:7', 'panel1:left:0:kachel@julianbvw:8'], got)
check('there already: None', install.with_applet(here + ['panel1:left:1:kachel@julianbvw:16']) is None)
check('without_applet takes only ours',
      install.without_applet(here + ['panel1:left:1:kachel@julianbvw:16']) == here)
check('no applets at all', install.with_applet([]) == ['panel1:left:0:kachel@julianbvw:1'])

section('applet_bindings')
import json, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
    spices = Path(tmp)
    (spices / 'menu@example').mkdir()
    (spices / 'menu@example' / '15.json').write_text(json.dumps({
        'overlay-key': {'type': 'keybinding', 'value': 'Super_L::Super_R'},
        'menu-icon': {'type': 'iconfilechooser', 'value': 'start-here'}}))
    (spices / 'gone@example').mkdir()
    (spices / 'gone@example' / '9.json').write_text(json.dumps({
        'key': {'type': 'keybinding', 'value': 'F9'}}))
    (spices / 'one@example').mkdir()
    (spices / 'one@example' / 'one@example.json').write_text(json.dumps({
        'key': {'type': 'keybinding', 'value': '<Super>x::'}, '__md5__': 'abc'}))
    (spices / 'broken@example').mkdir()
    (spices / 'broken@example' / '4.json').write_text('{ not json')
    got = install.applet_bindings(['panel1:left:0:menu@example:15', 'panel1:left:1:one@example:3',
                                   'panel1:left:2:broken@example:4', 'panel1:left:3:empty@example:5'], spices)
    check('a menu on Super, a single-instance applet, broken and missing files skipped, only enabled ones',
          got == {'the applet menu@example (overlay-key)': ['Super_L', 'Super_R'],
                  'the applet one@example (key)': ['<Super>x']}, got)
    check('Super_L counts as taken', install.accelerator_taken('Super_L', got) is not None)

harness.report()
