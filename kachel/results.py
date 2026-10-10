'''The result list that takes the place of rail and wall while searching.'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402

ROW_HEIGHT = 54
PLATE = 36
ICON = 22

# The symbol for rows that are not apps.
KIND_ICONS = {'calc': 'ms:calculate', 'web': 'ms:public'}


class ResultList(Gtk.Box):
    '''A header line and up to nine rows, one of them selected.

    `on_activate(result, timestamp)` is called for Enter, Ctrl+N or a
    click. Moving the pointer over a row selects it, so mouse and keys
    never disagree about which row Enter means -- but only a pointer that
    really moves. Rows appearing under a resting pointer would otherwise
    "enter" it, and Enter would start the third hit instead of the first.
    '''

    def __init__(self, on_activate):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.get_style_context().add_class('kachel-results')
        self._on_activate = on_activate
        self._results = []
        self._rows = []
        self._selected = 0
        self._pointer = None   # last (x, y) on screen that selected a row

        self._header = Gtk.Label(xalign=0)
        self._header.get_style_context().add_class('kachel-results-header')
        self._header.set_ellipsize(Pango.EllipsizeMode.END)
        self._header.set_max_width_chars(1)   # never widen the window
        self.pack_start(self._header, False, False, 0)

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.pack_start(self._list, False, False, 0)

    def show_results(self, results, header):
        for row in self._rows:
            self._list.remove(row)
            row.destroy()
        self._results = list(results)
        self._rows = [self._make_row(result, index)
                      for index, result in enumerate(self._results)]
        for row in self._rows:
            self._list.pack_start(row, False, False, 0)
        self._header.set_text(header)
        self._list.show_all()
        # Where the pointer rests now does not count as a move; only
        # leaving this spot does.
        self._pointer = self._pointer_position()
        self.select(0)

    def select(self, index):
        if not self._rows:
            return
        self._selected = max(0, min(index, len(self._rows) - 1))
        for position, row in enumerate(self._rows):
            context = row.get_style_context()
            if position == self._selected:
                context.add_class('selected')
            else:
                context.remove_class('selected')

    def move(self, delta):
        self.select(self._selected + delta)

    def activate(self, index, timestamp):
        '''Run row `index` (0-based). False if there is no such row.'''
        if 0 <= index < len(self._results):
            self._on_activate(self._results[index], timestamp)
            return True
        return False

    def activate_selected(self, timestamp):
        return self.activate(self._selected, timestamp)

    def _pointer_position(self):
        seat = Gdk.Display.get_default().get_default_seat()
        pointer = seat.get_pointer() if seat is not None else None
        if pointer is None:
            return None
        _screen, x, y = pointer.get_position()
        return (float(x), float(y))

    def _moved(self, _row, event, index):
        where = (float(int(event.x_root)), float(int(event.y_root)))
        if where != self._pointer:
            self._pointer = where
            if index != self._selected:
                self.select(index)
        return False

    def _make_row(self, result, index):
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.set_can_focus(False)
        row.get_style_context().add_class('kachel-result')
        row.set_size_request(-1, ROW_HEIGHT)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)

        plate = Gtk.Box()
        plate.get_style_context().add_class('kachel-result-plate')
        plate.set_size_request(PLATE, PLATE)
        plate.set_valign(Gtk.Align.CENTER)
        if result.kind == 'app':
            glyph = icons.icon_widget(None, ICON, fallback=result.app.icon)
        else:
            glyph = icons.icon_widget(KIND_ICONS[result.kind], ICON)
        glyph.set_halign(Gtk.Align.CENTER)
        glyph.set_valign(Gtk.Align.CENTER)
        plate.set_center_widget(glyph)
        content.pack_start(plate, False, False, 0)

        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        texts.set_valign(Gtk.Align.CENTER)
        name = Gtk.Label(label=result.title, xalign=0)
        name.get_style_context().add_class('kachel-result-name')
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(1)
        sub = Gtk.Label(label=result.subtitle, xalign=0)
        sub.get_style_context().add_class('kachel-result-sub')
        sub.set_ellipsize(Pango.EllipsizeMode.END)
        sub.set_max_width_chars(1)
        texts.pack_start(name, False, False, 0)
        texts.pack_start(sub, False, False, 0)
        content.pack_start(texts, True, True, 0)

        hint = Gtk.Label(label=f'Ctrl {index + 1}')
        hint.get_style_context().add_class('kachel-key-hint')
        hint.set_valign(Gtk.Align.CENTER)
        content.pack_start(hint, False, False, 0)

        row.add(content)
        row.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        row.connect('motion-notify-event', self._moved, index)
        row.connect('clicked', lambda *_: self.activate(
            index, Gtk.get_current_event_time()))
        return row
