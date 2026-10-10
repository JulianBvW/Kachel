'''The result list that takes the place of rail and wall while searching.'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402

ROW_HEIGHT = 54
ROW_GAP = 2
PLATE = 36
ICON = 22
# Rows are built in portions: a search for 'e' fits most of the apps, and
# @f will find thousands of files. The next portion comes when the list is
# scrolled to its end or the selection gets there.
BATCH = 20
KEY_HINTS = 9    # Ctrl+1 ... Ctrl+9

# The symbol for rows that are not apps.
KIND_ICONS = {'calc': 'ms:calculate', 'web': 'ms:public'}


class ResultList(Gtk.Box):
    '''A header line and a scrolling list of rows, one of them selected.

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

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                             spacing=ROW_GAP)
        self._list.set_valign(Gtk.Align.START)
        self._scroller = Gtk.ScrolledWindow()
        self._scroller.get_style_context().add_class('kachel-wall')
        self._scroller.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        self._scroller.add(self._list)
        self._pending_scroll = False
        self._rebuilding = False
        self._list.connect('size-allocate', self._laid_out)
        self._adjustment = self._scroller.get_vadjustment()
        self._adjustment.connect('value-changed', self._scrolled)
        self.pack_start(self._scroller, True, True, 0)

    def show_results(self, results, header):
        for row in self._rows:
            self._list.remove(row)
            row.destroy()
        self._results = list(results)
        self._rows = []
        self._selected = 0
        # Back to the top before building: scrolling sends value-changed,
        # and with the old range that would build a portion too many.
        self._rebuilding = True
        self._adjustment.set_value(0)
        self._rebuilding = False
        self._load_more()
        self._header.set_text(header)
        # Where the pointer rests now does not count as a move; only
        # leaving this spot does.
        self._pointer = self._pointer_position()
        self.select(0)

    def _load_more(self):
        '''Build the next portion of rows. False when all are built.'''
        start = len(self._rows)
        if start >= len(self._results):
            return False
        for index in range(start, min(start + BATCH, len(self._results))):
            row = self._make_row(self._results[index], index)
            self._rows.append(row)
            self._list.pack_start(row, False, False, 0)
        self._list.show_all()
        return True

    def _scrolled(self, adjustment):
        '''Near the end of what is built: build the next portion.'''
        if self._rebuilding:
            return
        bottom = adjustment.get_value() + adjustment.get_page_size()
        if bottom >= adjustment.get_upper() - ROW_HEIGHT:
            self._load_more()

    def select(self, index, scroll=True):
        '''Select row `index`, building rows up to it if need be. With
        `scroll`, the list follows so the row is in view -- not when the
        pointer chose it, that row is in view already.'''
        if not self._results:
            return
        index = max(0, min(index, len(self._results) - 1))
        while index >= len(self._rows) and self._load_more():
            pass
        if self._selected < len(self._rows):
            self._rows[self._selected].get_style_context() \
                .remove_class('selected')
        self._selected = index
        self._rows[index].get_style_context().add_class('selected')
        if scroll:
            self._scroll_to(index)
            # Rows built just now only count into the scroll range once the
            # list has been laid out again; then it scrolls once more.
            self._pending_scroll = True

    def _laid_out(self, *_args):
        if self._pending_scroll:
            self._pending_scroll = False
            self._scroll_to(self._selected)

    def _scroll_to(self, index):
        # Where the row really is, once laid out. A row built just now has
        # no allocation yet; until the next layout pass (see _laid_out)
        # its place is estimated from the minimum row height.
        adj = self._adjustment
        allocation = self._rows[index].get_allocation()
        if allocation.height > 1:
            top, bottom = allocation.y, allocation.y + allocation.height
        else:
            top = index * (ROW_HEIGHT + ROW_GAP)
            bottom = top + ROW_HEIGHT
        if top < adj.get_value():
            adj.set_value(top)
        elif bottom > adj.get_value() + adj.get_page_size():
            adj.set_value(bottom - adj.get_page_size())

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
                self.select(index, scroll=False)
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

        if index < KEY_HINTS:
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
