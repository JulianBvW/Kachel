'''The easing curve behind the sliding pages.'''

import harness
from harness import check, section

from kachel.slide import EASE_OUT_SLOW, cubic_bezier

section('cubic_bezier')
ease = EASE_OUT_SLOW
check('starts at 0', ease(0) == 0.0)
check('ends at 1', ease(1) == 1.0)
check('clamped outside 0..1', ease(-0.5) == 0.0 and ease(1.5) == 1.0)
values = [ease(i / 100) for i in range(101)]
check('rises and never goes back', all(b >= a for a, b in zip(values, values[1:])))
check('quick off the mark: past half way at a fifth of the time',
      ease(0.2) > 0.5, ease(0.2))
check('soft landing: still short of 1 at 70 %', ease(0.7) < 1.0, ease(0.7))
linear = cubic_bezier(1 / 3, 1 / 3, 2 / 3, 2 / 3)
check('a straight curve is linear',
      all(abs(linear(t / 10) - t / 10) < 1e-4 for t in range(11)))
# CSS ease (0.25, 0.1, 0.25, 1) at x = 0.5 is about 0.8024.
check('matches CSS "ease" at 0.5', abs(cubic_bezier(0.25, 0.1, 0.25, 1)(0.5) - 0.8024) < 1e-3,
      cubic_bezier(0.25, 0.1, 0.25, 1)(0.5))

harness.report()
