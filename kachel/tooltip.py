'''The rail's tooltip: a small popover to the right of the rail.

Not a Gtk tooltip. Those come after a delay, in a window of their own and
in the theme's look; this one appears at once, inside our own window, and
in the popover style of Design §5. It floats in an overlay over the main
view and lets the pointer through to whatever is below it.
'''

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402

LEFT = 62   # Design §8.4: two pixels clear of the rail


class Tooltip(Gtk.Box):

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.get_style_context().add_class('kachel-tooltip')
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_margin_start(LEFT)

        self._name = Gtk.Label(xalign=0)
        self._name.get_style_context().add_class('kachel-tooltip-name')
        self._sub = Gtk.Label(xalign=0)
        self._sub.get_style_context().add_class('kachel-tooltip-sub')
        self.pack_start(self._name, False, False, 0)
        self.pack_start(self._sub, False, False, 0)
        self._name.show()
        # The window's show_all must not bring it up on every show.
        self.set_no_show_all(True)
        self._anchor = None

    def show_for(self, anchor, name, sub=''):
        '''Show `name` and `sub` beside `anchor`, centred on it.'''
        self._anchor = anchor
        self._name.set_text(name)
        self._sub.set_text(sub)
        self._sub.set_visible(bool(sub))
        parent = self.get_parent()
        found = anchor.translate_coordinates(parent, 0, 0) if parent else None
        if not found:
            return
        _x, y = found
        # Measured visible and without the old margin: a hidden widget
        # asks for nothing, and the margin counts into what it asks for.
        self.set_margin_top(0)
        self.show()
        _minimum, natural = self.get_preferred_height()
        top = y + (anchor.get_allocated_height() - natural) // 2
        self.set_margin_top(max(0, top))

    def hide_for(self, anchor):
        '''Hide, unless another entry has taken the tooltip over since.'''
        if anchor is self._anchor:
            self.hide_now()

    def hide_now(self):
        self._anchor = None
        self.hide()

    @property
    def anchor(self):
        return self._anchor
