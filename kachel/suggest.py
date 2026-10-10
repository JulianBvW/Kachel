'''The suggestion list under the search bar while an @word is typed.

Design §7: a popover with one row per scope abbreviation that fits what
is typed so far, the first one highlighted. It floats over the window and
takes clicks itself.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402

LEFT = 12
TOP = 52
WIDTH = 440
ROW_HEIGHT = 40
GLYPH = 18
CODE_WIDTH = 76
NAME_WIDTH = 60


class Suggestions(Gtk.Box):
    '''`on_pick(scope)` when a row is taken by click (Tab and Enter go
    through pick_selected, from the window's key handler).'''

    def __init__(self, on_pick):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.get_style_context().add_class('kachel-suggestions')
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_margin_start(LEFT)
        self.set_margin_top(TOP)
        self.set_size_request(WIDTH, -1)
        self._on_pick = on_pick
        self._scopes = []
        self._rows = []
        self._selected = 0

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pack_start(self._list, False, False, 0)
        self._list.show()
        # Not part of the window's show_all; it comes when @ is typed.
        self.set_no_show_all(True)

    @property
    def shown(self):
        return self.get_visible()

    def show_for(self, scopes):
        '''Offer `scopes`, the first one highlighted -- or hide when the
        list would be empty. Unchanged offers keep their highlight.'''
        if not scopes:
            self.hide()
            return
        if scopes != self._scopes:
            self._scopes = list(scopes)
            for row in self._rows:
                self._list.remove(row)
                row.destroy()
            self._rows = [self._make_row(scope) for scope in self._scopes]
            for row in self._rows:
                self._list.pack_start(row, False, False, 0)
            self._list.show_all()
            self.select(0)
        self.show()

    def hide_list(self):
        self.hide()
        self._scopes = []

    def select(self, index):
        self._selected = max(0, min(index, len(self._rows) - 1))
        for position, row in enumerate(self._rows):
            context = row.get_style_context()
            if position == self._selected:
                context.add_class('selected')
            else:
                context.remove_class('selected')

    def move(self, delta):
        self.select(self._selected + delta)

    def pick_selected(self):
        if self._scopes:
            self._on_pick(self._scopes[self._selected])

    def _make_row(self, scope):
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.set_can_focus(False)
        row.get_style_context().add_class('kachel-suggestion')
        row.set_size_request(-1, ROW_HEIGHT)

        content = Gtk.Box(spacing=12)
        glyph = icons.icon_widget(scope.icon, GLYPH)
        glyph.set_valign(Gtk.Align.CENTER)
        content.pack_start(glyph, False, False, 0)
        code = Gtk.Label(label=f'@{scope.code}', xalign=0)
        code.get_style_context().add_class('kachel-suggestion-code')
        code.set_size_request(CODE_WIDTH, -1)
        content.pack_start(code, False, False, 0)
        name = Gtk.Label(label=scope.name, xalign=0)
        name.get_style_context().add_class('kachel-suggestion-name')
        name.set_size_request(NAME_WIDTH, -1)
        content.pack_start(name, False, False, 0)
        hint = Gtk.Label(label=scope.hint, xalign=0)
        hint.get_style_context().add_class('kachel-suggestion-hint')
        hint.set_ellipsize(Pango.EllipsizeMode.END)
        hint.set_max_width_chars(1)
        content.pack_start(hint, True, True, 0)
        row.add(content)
        row.connect('clicked', lambda *_: self._on_pick(scope))
        return row
