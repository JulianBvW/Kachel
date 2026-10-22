'''The numbers behind the effects.'''

import harness
from harness import check, section

from kachel import anim

section('icon_scale')
check('at rest: 1', anim.icon_scale(False, False, 1.12) == 1.0)
check('under the pointer: grown', anim.icon_scale(True, False, 1.12) == 1.12)
check('pressed: shrunk', anim.icon_scale(False, True, 1.12) == anim.PRESS_SCALE)
check('both: multiplied', abs(anim.icon_scale(True, True, 1.12) - 1.12 * anim.PRESS_SCALE) < 1e-9)
check('a row icon does not grow', anim.icon_scale(True, False, 1.0) == 1.0)

section('room')
for px in (22, 36, 40, 64, 72):
    pad = anim.room(px, anim.GROW_TILE)
    check(f'{px} px grown fits into {px + 2 * pad}', px * anim.GROW_TILE <= px + 2 * pad)
check('no growing: still a pixel', anim.room(22, 1.0) == 1)

section('curves')
for name, ease in (('ease', anim.EASE), ('ease-out', anim.EASE_OUT)):
    check(f'{name}: from 0 to 1', ease(0) == 0 and ease(1) == 1)
    check(f'{name}: halfway is past the middle', ease(0.5) > 0.5)

section('gliding')
before = {'a': (0, 0), 'b': (54, 0), 'gone': (0, 54)}
after = {'a': (0, 0), 'b': (108, 0), 'new': (0, 108)}
check('only what moved glides, from its old place',
      anim.glides(before, after) == [('b', (54, 0), (108, 0))], anim.glides(before, after))

section('on and off')
check('true and false are taken as they are', anim.resolve(True) is True and anim.resolve(False) is False)
check('"system" gives an answer', anim.resolve('system') in (True, False))

section('app list')
from kachel import applist
check('a grown list icon fits its plate, which keeps its size',
      applist.ICON + 2 * anim.room(applist.ICON, anim.GROW_LIST) <= applist.PLATE)

section('segment_enters')
middle = (0, 100, 100, 90)          # the tile between, of three in a column
check('straight down through it: in at its top edge',
      anim.segment_enters(middle, (50, 80), (50, 220)) == (50, 100))
check('slanted: in where the line crosses the top',
      anim.segment_enters(middle, (0, 0), (100, 200)) == (50, 100))
check('beside it: missed', anim.segment_enters(middle, (150, 80), (150, 220)) is None)
check('stops before it: missed', anim.segment_enters(middle, (50, 20), (50, 90)) is None)
check('starts inside: the start', anim.segment_enters(middle, (50, 150), (50, 300)) == (50, 150))
check('upwards: in at the bottom edge',
      anim.segment_enters(middle, (50, 300), (50, 50)) == (50, 190))
check('a single point outside: missed', anim.segment_enters(middle, (50, 50), (50, 50)) is None)

harness.report()
