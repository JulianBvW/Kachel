'''The small effects (Design §12): glow, growing icons, the press, gliding.

GTK 3 CSS has no transform, so whatever scales is drawn scaled: a handler
on the widget's `draw` signal runs before the widget draws itself and
scales the cairo context around its middle. Nothing is laid out again,
so nothing around it moves.

Every number that shapes how the effects feel is here, at the top, and
style.py takes its CSS durations from here too: tuning happens in one
place.
'''

import math

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gio', '2.0')
from gi.repository import Gio, Gtk  # noqa: E402

from .slide import cubic_bezier  # noqa: E402

# -- the values ---------------------------------------------------------

HOVER_MS = 180          # ring and fill fade in and out (CSS)
HOVER_MIN_MS = 100      # a tile stays lit at least this long: a quick
                        # pass over it shows, rather than nothing
FLYOVER_MS = 150        # a leave and the next enter this close together:
                        # the tiles in between were flown over
GROW_TILE = 1.12        # a tile's icon under the pointer
GROW_RAIL = 1.14        # a rail icon under the pointer
GROW_LIST = 1.15        # an icon in the app list under the pointer
GROW_MS = 180
PRESS_SCALE = 0.9       # an icon while its button is held down
PRESS_MARGIN = 2        # px the surface shrinks by on each side (CSS)
PRESS_MS = 140
GLOW_RADIUS = 150       # px
GLOW_ALPHA = 0.15       # white, in the middle
GLOW_STOP = 0.7         # where it has faded out, of the radius
GLOW_MS = 220
GLIDE_MS = 150
HOVER_FILL_OFF = 0.13   # a tile's fill under the pointer without effects

EASE = cubic_bezier(0.25, 0.1, 0.25, 1)          # CSS "ease"
EASE_OUT = cubic_bezier(0, 0, 0.58, 1)           # CSS "ease-out"

# -- on or off ----------------------------------------------------------

_enabled = True


def enabled():
    return _enabled


def set_enabled(on):
    global _enabled
    _enabled = bool(on)


def system_settings():
    '''org.cinnamon, if it has desktop-effects, else None. Looked up
    first: opening a schema that is not there aborts the process.'''
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup('org.cinnamon', True) if source else None
    if schema is None or not schema.has_key('desktop-effects'):
        return None
    return Gio.Settings.new('org.cinnamon')


def resolve(setting, settings=None):
    '''`animations` from kachel.toml -> on or off. "system" follows
    Cinnamon's desktop effects (`settings`: system_settings(), if at
    hand).'''
    if isinstance(setting, bool):
        return setting
    settings = settings or system_settings()
    return settings is None or settings.get_boolean('desktop-effects')


# -- the pure parts -----------------------------------------------------

def icon_scale(hover, pressed, grow):
    '''How big an icon is drawn: grown under the pointer, shrunk while
    pressed, both at once multiplied.'''
    return (grow if hover else 1.0) * (PRESS_SCALE if pressed else 1.0)


def room(px, grow):
    '''Extra pixels on each side of an icon of `px`, so that drawn `grow`
    times bigger it is not cut off at its own edge.'''
    return math.ceil(px * (grow - 1) / 2) + 1


def glides(before, after):
    '''[(key, from, to)] for everything that is somewhere else now.
    `before` and `after` map a key to an (x, y); what is new or gone does
    not glide.'''
    return [(key, before[key], to) for key, to in after.items()
            if key in before and before[key] != to]


def segment_enters(rect, p, q):
    '''Where the line from `p` to `q` first gets into `rect` (x, y,
    width, height): the point, or None if it misses it.'''
    x, y, width, height = rect
    (px, py), (qx, qy) = p, q
    dx, dy = qx - px, qy - py
    low, high = 0.0, 1.0
    for step, start, lo, hi in ((dx, px, x, x + width),
                                (dy, py, y, y + height)):
        if step == 0:
            if not lo <= start <= hi:
                return None
            continue
        t0, t1 = (lo - start) / step, (hi - start) / step
        if t0 > t1:
            t0, t1 = t1, t0
        low, high = max(low, t0), min(high, t1)
        if low > high:
            return None
    return px + dx * low, py + dy * low


# -- moving a value over time --------------------------------------------

class Tween:
    '''A number that moves to a target, frame by frame, calling
    `on_change` after each step. Without effects, or while the widget is
    not on screen, it is at the target at once.'''

    def __init__(self, widget, value, on_change):
        self._widget = widget
        self.value = value
        self._target = value
        self._on_change = on_change
        self._tick = None
        widget.connect('unmap', lambda _w: self.jump())

    def to(self, target, ms, ease=EASE_OUT):
        if not _enabled or ms <= 0 or not self._widget.get_mapped():
            self._target = target
            self.jump()
            return
        if target == self._target and self._tick is not None:
            return
        self._target = target
        self._from, self._ms, self._ease = self.value, ms, ease
        self._start = None
        if self._tick is None:
            self._tick = self._widget.add_tick_callback(self._step)

    def jump(self):
        '''Straight to the target.'''
        if self._tick is not None:
            self._widget.remove_tick_callback(self._tick)
            self._tick = None
        if self.value != self._target:
            self.value = self._target
            self._on_change()

    def _step(self, _widget, clock):
        now = clock.get_frame_time()                 # microseconds
        if self._start is None:
            self._start = now
        t = min(1.0, (now - self._start) / (self._ms * 1000))
        self.value = self._from + (self._target - self._from) * self._ease(t)
        self._on_change()
        if t >= 1:
            self._tick = None
            return False
        return True


# -- icons that grow and shrink ------------------------------------------

class IconScale:
    '''Draws `icon` bigger under the pointer (`grow`) and smaller while
    pressed. Call make_room() first if it grows, so it is not cut off.'''

    def __init__(self, icon, grow=1.0):
        self._icon = icon
        self._grow = grow
        self._hover = False
        self._pressed = False
        self._tween = Tween(icon, 1.0, icon.queue_draw)
        icon.connect('draw', self._draw)

    def hover(self, on):
        if on != self._hover:
            self._hover = on
            self._tween.to(self._target(), GROW_MS)

    def press(self, on):
        if on != self._pressed:
            self._pressed = on
            self._tween.to(self._target(), PRESS_MS)

    def follow(self, button, hover=False):
        '''Shrink while `button` is held down; with `hover`, also grow
        while the pointer is on it.'''
        def changed(widget, _old):
            flags = widget.get_state_flags()
            if hover:
                self.hover(bool(flags & Gtk.StateFlags.PRELIGHT))
            self.press(bool(flags & Gtk.StateFlags.ACTIVE))
        button.connect('state-flags-changed', changed)
        return self

    def reset(self):
        self._hover = self._pressed = False
        self._tween.to(1.0, 0)

    def _target(self):
        if not _enabled:
            return 1.0
        return icon_scale(self._hover, self._pressed, self._grow)

    def _draw(self, widget, cr):
        value = self._tween.value
        if value != 1.0 and _enabled:   # switched off midway: plain at once
            x = widget.get_allocated_width() / 2
            y = widget.get_allocated_height() / 2
            cr.translate(x, y)
            cr.scale(value, value)
            cr.translate(-x, -y)
        return False


def make_room(icon, px, grow):
    '''Give `icon` (drawn at `px`) space around it to grow into; returns
    the pixels added on each side.'''
    pad = room(px, grow)
    icon.set_size_request(px + 2 * pad, px + 2 * pad)
    return pad


# -- the glow under the pointer ------------------------------------------

class Glow:
    '''A soft round light that follows the pointer over `button`, drawn
    over its fill and under everything floating on it. `radius` is the
    surface's corner radius.'''

    def __init__(self, button, radius):
        self._button = button
        self._radius = radius
        self._at = None
        self._tween = Tween(button, 0.0, button.queue_draw)
        button.connect_after('draw', self._draw)

    def enter(self, x, y):
        self._at = (x, y)
        self._tween.to(1.0, GLOW_MS, EASE)

    def move(self, x, y):
        self._at = (x, y)
        if self._tween.value > 0:
            self._button.queue_draw()

    def leave(self):
        self._tween.to(0.0, GLOW_MS, EASE)

    def reset(self):
        self._tween.to(0.0, 0)

    def _draw(self, widget, cr):
        strength = self._tween.value
        if strength <= 0 or self._at is None or not _enabled:
            return False
        context = widget.get_style_context()
        margin = context.get_margin(widget.get_state_flags())
        x0, y0 = margin.left, margin.top
        width = widget.get_allocated_width() - margin.left - margin.right
        height = widget.get_allocated_height() - margin.top - margin.bottom
        if width <= 0 or height <= 0:
            return False
        cr.save()
        r = min(self._radius, width / 2, height / 2)
        cr.new_sub_path()
        cr.arc(x0 + width - r, y0 + r, r, -math.pi / 2, 0)
        cr.arc(x0 + width - r, y0 + height - r, r, 0, math.pi / 2)
        cr.arc(x0 + r, y0 + height - r, r, math.pi / 2, math.pi)
        cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()
        x, y = self._at
        light = cairo.RadialGradient(x, y, 0, x, y, GLOW_RADIUS)
        light.add_color_stop_rgba(0, 1, 1, 1, GLOW_ALPHA * strength)
        light.add_color_stop_rgba(GLOW_STOP, 1, 1, 1, 0)
        cr.set_source(light)
        cr.paint()
        cr.restore()
        return False


# -- gliding into place --------------------------------------------------

def glide(fixed, moves):
    '''Move widgets of `fixed` from where they were to where they are now:
    `moves` is [(widget, (x, y) from, (x, y) to)]. They start at the old
    place at once and get to the new one in GLIDE_MS. Returns the tick
    callback's id (for remove_tick_callback), or None.'''
    if not moves or not _enabled or not fixed.get_mapped():
        return None
    for widget, start, _end in moves:
        fixed.move(widget, *start)
    state = {'start': None}

    def step(_widget, clock):
        now = clock.get_frame_time()
        if state['start'] is None:
            state['start'] = now
        t = min(1.0, (now - state['start']) / (GLIDE_MS * 1000))
        eased = EASE_OUT(t)
        for widget, (x0, y0), (x1, y1) in moves:
            if widget.get_parent() is fixed:
                fixed.move(widget, round(x0 + (x1 - x0) * eased),
                           round(y0 + (y1 - y0) * eased))
        return t < 1
    return fixed.add_tick_callback(step)
