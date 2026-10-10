'''The search bar: a button on the left, the input field beside it.'''

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: E402

from . import config, icons  # noqa: E402

PLACEHOLDER = 'Suchen…'
BUTTON_SIZE = 30
GLYPH_SIZE = 22


class SearchBar(Gtk.Box):
    '''`on_changed(text)` on every edit, `on_close()` when the button is
    clicked with nothing left to clear.'''

    def __init__(self, on_changed, on_close):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.get_style_context().add_class('kachel-searchbar')
        self.set_size_request(-1, config.SEARCHBAR_HEIGHT)
        self._on_changed = on_changed
        self._on_close = on_close

        # Magnifier at rest, a cross under the pointer: the button clears,
        # and when there is nothing to clear, it closes.
        self._glyphs = Gtk.Stack()
        self._glyphs.add_named(icons.icon_widget('ms:search', GLYPH_SIZE),
                               'search')
        self._glyphs.add_named(icons.icon_widget('ms:close', GLYPH_SIZE),
                               'close')
        self._button = Gtk.Button()
        self._button.set_relief(Gtk.ReliefStyle.NONE)
        self._button.set_can_focus(False)   # the field keeps the keyboard
        self._button.get_style_context().add_class('kachel-search-button')
        self._button.set_size_request(BUTTON_SIZE, BUTTON_SIZE)
        self._button.set_valign(Gtk.Align.CENTER)
        self._button.set_margin_start(20)
        self._button.add(self._glyphs)
        self._button.connect('enter-notify-event', self._hover, 'close')
        self._button.connect('leave-notify-event', self._hover, 'search')
        self._button.connect('clicked', self._clicked)
        self.pack_start(self._button, False, False, 0)

        self._entry = Gtk.Entry()
        self._entry.get_style_context().add_class('kachel-search-entry')
        self._entry.set_has_frame(False)
        self._entry.set_placeholder_text(PLACEHOLDER)
        self._entry.set_hexpand(True)
        self._entry.set_valign(Gtk.Align.CENTER)
        self._entry.set_margin_end(12)
        self._entry.connect('changed', self._changed)
        self.pack_start(self._entry, True, True, 0)

    @property
    def text(self):
        return self._entry.get_text()

    def set_text(self, text):
        self._entry.set_text(text)
        self._entry.set_position(-1)

    def clear(self):
        self._entry.set_text('')

    def reset(self):
        '''Empty, and the magnifier back: a hide while the pointer was on
        the button brings no leave event to switch it back.'''
        self.clear()
        self._glyphs.set_visible_child_name('search')

    def focus(self):
        self._entry.grab_focus_without_selecting()

    def _changed(self, entry):
        self._on_changed(entry.get_text())

    def _hover(self, _widget, _event, glyph):
        self._glyphs.set_visible_child_name(glyph)
        return False

    def _clicked(self, _button):
        if self._entry.get_text():
            self.clear()
            self.focus()
        else:
            self._on_close()
