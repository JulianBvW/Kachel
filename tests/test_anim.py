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

harness.report()
