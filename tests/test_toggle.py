'''What the shortcut means: show, or hide -- including right after a focus loss.'''

import harness
from harness import check, section

from kachel import config
from kachel.window import toggle_should_show

GRACE = config.FOCUS_HIDE_GRACE_MS

section('toggle_should_show')
check('visible -> hide', toggle_should_show(True, None) is False)
check('visible, even after an old focus hide -> hide',
      toggle_should_show(True, 10) is False)
check('hidden, never lost the focus -> show',
      toggle_should_show(False, None) is True)
check('hidden by focus loss just now -> stays hidden',
      toggle_should_show(False, 30) is False)
check('right at the edge of the grace period -> stays hidden',
      toggle_should_show(False, GRACE - 1) is False)
check('grace period over -> show',
      toggle_should_show(False, GRACE) is True)
check('long after a focus hide -> show',
      toggle_should_show(False, 60_000) is True)

harness.report()
