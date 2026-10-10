'''The window itself: a pane of dark glass in the middle of the screen.'''

import math
import time

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import blur, config, geometry  # noqa: E402

# X11-only, and only needed for a fresh server timestamp. Kept optional so the
# import does not bring the whole program down on a session without it.
try:
    gi.require_version('GdkX11', '3.0')
    from gi.repository import GdkX11
except (ValueError, ImportError):  # pragma: no cover
    GdkX11 = None


def toggle_should_show(visible, ms_since_focus_hide):
    '''What the shortcut means right now: True to show, False to hide.

    `ms_since_focus_hide` is how long ago the window was hidden for losing
    the focus, or None if that has not happened since the last show. The
    shortcut is a keyboard grab, and the grab alone can take the focus away
    before the toggle arrives. The window is then already hidden, but the
    press meant "hide" -- so a toggle that close behind a focus-loss hide
    leaves it hidden instead of bringing it straight back.
    '''
    if visible:
        return False
    if ms_since_focus_hide is not None \
            and ms_since_focus_hide < config.FOCUS_HIDE_GRACE_MS:
        return False
    return True


class KachelWindow(Gtk.Window):
    '''A window that spends most of its life hidden.

    It is never destroyed and never rebuilt. Showing it is only a matter of
    mapping it again, which is the whole reason the program stays resident:
    there is no startup left to pay for at the moment the key is pressed.
    '''

    def __init__(self, verbose=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._verbose = verbose

        # When the window last went away for losing the focus, as
        # time.monotonic(). None while it is up or was hidden any other way.
        self._focus_hidden_at = None

        self.set_title(config.PROGRAM_CLASS)
        self.set_decorated(False)

        # NORMAL, not UTILITY or DIALOG. BlurCinnamon only accepts NORMAL,
        # DOCK and DESKTOP -- anything else is simply never blurred, and
        # without any error to go on.
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        # It is an overlay, not a window you manage.
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)

        # Fixed size, placed by us. The width comes from the tile grid.
        self._width = geometry.window_width(config.COLUMNS)
        self._height = config.HEIGHT
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_default_size(self._width, self._height)
        self.set_size_request(self._width, self._height)
        self.set_resizable(False)

        self._blurred = False
        self._background = config.BG_RGBA_NO_BLUR
        self._check_blur()

        self._rgba = self._setup_transparency()
        self.connect('draw', self._on_draw)
        self.connect('key-press-event', self._on_key_press)
        self.connect('focus-out-event', self._on_focus_out)

        # Closing the window would destroy it and cost us the instant reopen.
        # Hide instead -- the only way out is the quit action.
        self.connect('delete-event', lambda *_: self.hide_kachel() or True)

        # Realise early so there is a GdkWindow to ask for a server timestamp
        # the first time we are shown.
        self.realize()
        self._log(f'{self._width}x{self._height}')

    # -- appearance ------------------------------------------------------

    def _check_blur(self):
        '''Pick the background by whether BlurCinnamon will blur us.

        Asked on every show rather than once: the extension's settings have
        no change signal to listen to, and an entry made after login should
        not need a restart. Reading the small file costs well under a
        millisecond.
        '''
        blurred = blur.active(config.PROGRAM_CLASS)
        if blurred != self._blurred:
            self._log('blurred' if blurred else 'not blurred')
        self._blurred = blurred
        self._background = config.BG_RGBA if blurred \
            else config.BG_RGBA_NO_BLUR

    def _check_compositing(self):
        '''Catch up on a compositor that was not running at autostart.

        The visual can only be chosen while the window is unrealised, so this
        runs before showing, when the window is hidden anyway.
        '''
        if self._rgba or not self.get_screen().is_composited():
            return
        self.unrealize()
        self._rgba = self._setup_transparency()
        self.realize()
        self._log('compositor appeared, switched to the transparent pane')

    def _setup_transparency(self):
        '''Ask for an RGBA visual. Returns True if we actually got one.'''
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)
            return True
        # No compositing: paint opaque rather than leave a black rectangle.
        self._log('no RGBA visual or no compositor -- falling back to opaque')
        return False

    def _on_draw(self, _widget, cr):
        r, g, b, a = self._background

        if not self._rgba:
            # No alpha channel to work with. Rounded corners would be four
            # black wedges, so stay square and opaque.
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgb(r, g, b)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            return False

        # Wipe the whole surface to nothing first. Filling only the rounded
        # path would leave whatever was outside it standing -- the corners
        # have to be made transparent on purpose.
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        width = self.get_allocated_width()
        height = self.get_allocated_height()
        radius = config.CORNER_RADIUS

        # The pane, filled right out to the edge.
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.set_source_rgba(r, g, b, a)
        cr.fill()

        # The hairline, on a path of its own half a pixel further in. A one
        # pixel line is drawn centred on its path, so only there does it land
        # on one whole row of pixels instead of smearing across two.
        self._rounded_rect(cr, 0.5, 0.5, width - 1, height - 1, radius - 0.5)
        cr.set_source_rgba(*config.BORDER_RGBA)
        cr.set_line_width(1)
        cr.stroke()
        return False

    @staticmethod
    def _rounded_rect(cr, x, y, width, height, radius):
        '''A rectangle with rounded corners as the current path.'''
        radius = min(radius, width / 2, height / 2)
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()

    # -- showing and hiding ----------------------------------------------

    def toggle(self):
        '''The shortcut: show if hidden, hide if shown.'''
        since = None
        if self._focus_hidden_at is not None:
            since = (time.monotonic() - self._focus_hidden_at) * 1000
        if toggle_should_show(self.get_visible(), since):
            self.show_kachel()
        elif self.get_visible():
            self.hide_kachel()
        else:
            self._log(f'toggle {since:.0f} ms after a focus-loss hide, '
                      'taken as hide')
            self._focus_hidden_at = None

    def show_kachel(self):
        t0 = time.monotonic()
        self._focus_hidden_at = None
        self._check_compositing()
        self._check_blur()

        # Placed on every show: on the monitor the pointer is on, which is
        # the one being looked at.
        x, y = self._placement()
        self.move(x, y)
        self.show_all()

        # A window shown from a D-Bus call has no user event behind it, so the
        # window manager may refuse it the keyboard to prevent focus stealing.
        # A fresh server timestamp is what makes the request legitimate.
        ts = self._server_time()
        self.present_with_time(ts)
        gdk_window = self.get_window()
        if gdk_window is not None:
            gdk_window.focus(ts)

        self._log(f'shown in {(time.monotonic() - t0) * 1000:.1f} ms '
                  f'at ({x}, {y})')

    def hide_kachel(self):
        self.reset()
        self.hide()
        self._log('hidden')

    def reset(self):
        '''Back to the state the next show should start from.

        Nothing to reset yet. From phase 3 on: empty input and pills, tile
        view, first action page, nothing armed.
        '''

    def _placement(self):
        '''Centred in the work area of the monitor under the pointer.'''
        display = Gdk.Display.get_default()
        monitor = None
        seat = display.get_default_seat()
        pointer = seat.get_pointer() if seat is not None else None
        if pointer is not None:
            _screen, px, py = pointer.get_position()
            monitor = display.get_monitor_at_point(px, py)
        if monitor is None:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        area = monitor.get_workarea()
        return geometry.centered(area.x, area.y, area.width, area.height,
                                 self._width, self._height)

    def _server_time(self):
        gdk_window = self.get_window()
        if GdkX11 is not None and gdk_window is not None:
            try:
                return GdkX11.x11_get_server_time(gdk_window)
            except Exception:  # not an X11 window
                pass
        return Gdk.CURRENT_TIME

    # -- input -----------------------------------------------------------

    def _on_key_press(self, _widget, event):
        # Esc hides, always. F7 is deliberately not handled here: the global
        # shortcut is a passive grab on the root window, so that key press
        # never reaches us -- both directions run through the toggle action.
        if event.keyval == Gdk.KEY_Escape:
            self.hide_kachel()
            return True
        return False

    def _on_focus_out(self, _widget, _event):
        '''Lost the keyboard: a click elsewhere, Alt+Tab, another window.'''
        if self.get_visible():
            self.hide_kachel()
            self._focus_hidden_at = time.monotonic()
            self._log('hidden on focus loss')
        return False

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[kachel] {time.strftime('%H:%M:%S')} window: {message}",
                  flush=True)
