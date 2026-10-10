'''Pages that slide sideways: the rail's actions now, the app list later.

Gtk.Stack can slide too, but with its own easing built in. The design asks
for cubic-bezier(0.2, 0.8, 0.2, 1) -- quick off the mark, a long soft
landing -- so the curve is computed here and the strip moved by hand, once
per frame.
'''

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402


def cubic_bezier(x1, y1, x2, y2):
    '''The CSS timing function as f(t) -> progress, both 0 to 1. Pure.

    The curve is given in a parameter s, not in time: x(s) is the time,
    y(s) the progress. So t is first turned back into s -- a few Newton
    steps, with halving as the fallback where the slope is too flat.
    '''
    def at(a, b, s):
        # B(s) with B(0) = 0, B(1) = 1 and control points a, b.
        return 3 * a * (1 - s) ** 2 * s + 3 * b * (1 - s) * s ** 2 + s ** 3

    def slope(a, b, s):
        return 3 * a * (1 - s) ** 2 + 6 * (b - a) * (1 - s) * s \
            + 3 * (1 - b) * s ** 2

    def solve(t):
        s = t
        for _ in range(8):
            error = at(x1, x2, s) - t
            if abs(error) < 1e-6:
                return s
            d = slope(x1, x2, s)
            if abs(d) < 1e-6:
                break
            s -= error / d
        low, high, s = 0.0, 1.0, t
        for _ in range(40):
            x = at(x1, x2, s)
            if abs(x - t) < 1e-6:
                break
            if x < t:
                low = s
            else:
                high = s
            s = (low + high) / 2
        return s

    def ease(t):
        if t <= 0:
            return 0.0
        if t >= 1:
            return 1.0
        return at(y1, y2, solve(t))
    return ease


EASE_OUT_SLOW = cubic_bezier(0.2, 0.8, 0.2, 1)


class Slider(Gtk.Layout):
    '''Pages side by side in a strip, one of them in view.

    A Gtk.Layout clips its children to its own size, which is the window
    the strip moves behind.
    '''

    def __init__(self, page_width, height, duration=380, ease=EASE_OUT_SLOW):
        super().__init__()
        self.get_style_context().add_class('kachel-slider')
        self.set_size_request(page_width, height)
        self._page_width = page_width
        self._height = height
        self._duration = duration * 1000   # the frame clock counts in µs
        self._ease = ease
        self._strip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.put(self._strip, 0, 0)
        self._page = 0
        self._offset = 0.0
        self._from = self._to = 0.0
        self._start = None
        self._tick = None
        self.on_page_changed = None

    @property
    def page(self):
        return self._page

    def set_pages(self, widgets):
        for child in self._strip.get_children():
            self._strip.remove(child)
            child.destroy()
        for widget in widgets:
            widget.set_size_request(self._page_width, self._height)
            self._strip.pack_start(widget, False, False, 0)
        self._strip.show_all()
        self.show_page(0, animate=False)

    def show_page(self, index, animate=True):
        '''Bring page `index` into view. A new target while sliding starts
        from where the strip is now, so nothing jumps.'''
        self._page = index
        target = -index * self._page_width
        if not animate or not self.get_mapped():
            self._stop()
            self._set_offset(target)
        else:
            self._from, self._to = self._offset, target
            self._start = None
            if self._tick is None:
                self._tick = self.add_tick_callback(self._on_tick)
        if self.on_page_changed:
            self.on_page_changed(index)

    def do_draw(self, cr):
        # A layout is supposed to clip its children to its own window, but
        # in our RGBA window it does not: the next page would show beside
        # this one. So the clip is set here, by hand. (Input is clipped by
        # the window hierarchy all the same.)
        cr.rectangle(0, 0, self.get_allocated_width(),
                     self.get_allocated_height())
        cr.clip()
        return Gtk.Layout.do_draw(self, cr)

    def _on_tick(self, _widget, clock):
        now = clock.get_frame_time()
        if self._start is None:
            self._start = now
        t = min(1.0, (now - self._start) / self._duration)
        self._set_offset(self._from + (self._to - self._from) * self._ease(t))
        if t >= 1.0:
            self._tick = None
            return False
        return True

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def _set_offset(self, offset):
        self._offset = offset
        self.move(self._strip, round(offset), 0)
