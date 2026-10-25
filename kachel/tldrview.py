'''A tldr page in place of the result list (Design §11.2).

On top the command's name and what it does; below, one row per example:
what it does, and under it the command in a chip. The placeholders in the
chip stand apart, in italics and a little paler. Choosing a row copies its
command.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import tldr  # noqa: E402
from .results import KEY_HINTS, moved_to, pointer_position  # noqa: E402

ROW_GAP = 2
PLACEHOLDER_ALPHA = '70%'


def chip_markup(command):
    '''Pango markup for a command, placeholders in italics.'''
    out = []
    for text, placeholder in tldr.pieces(command):
        text = GLib.markup_escape_text(text)
        if placeholder:
            text = (f'<span style="italic" alpha="{PLACEHOLDER_ALPHA}">'
                    f'{text}</span>')
        out.append(text)
    return ''.join(out)


class TldrView(Gtk.Box):
    '''`on_copy(text, timestamp)` with the command to copy, for Enter,
    Ctrl+N or a click. The pointer selects a row only when it really moves,
    as in the result list.'''

    def __init__(self, on_copy):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.get_style_context().add_class('kachel-tldr')
        self._on_copy = on_copy
        self._examples = []
        self._rows = []
        self._selected = 0
        self._pointer = None

        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        head.get_style_context().add_class('kachel-tldr-head')
        self._title = Gtk.Label(xalign=0)
        self._title.get_style_context().add_class('kachel-tldr-title')
        self._title.set_ellipsize(Pango.EllipsizeMode.END)
        self._title.set_max_width_chars(1)   # never widen the window
        self._description = Gtk.Label(xalign=0)
        self._description.get_style_context().add_class('kachel-tldr-desc')
        self._description.set_line_wrap(True)
        self._description.set_max_width_chars(1)
        head.pack_start(self._title, False, False, 0)
        head.pack_start(self._description, False, False, 0)
        self.pack_start(head, False, False, 0)

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                             spacing=ROW_GAP)
        self._list.set_valign(Gtk.Align.START)
        self._scroller = Gtk.ScrolledWindow()
        self._scroller.get_style_context().add_class('kachel-wall')
        self._scroller.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        self._scroller.add(self._list)
        self._adjustment = self._scroller.get_vadjustment()
        self._pending_scroll = False
        self._list.connect('size-allocate', self._laid_out)
        self.pack_start(self._scroller, True, True, 0)

    def show_page(self, page):
        for row in self._rows:
            self._list.remove(row)
            row.destroy()
        self._title.set_text(page.name)
        self._description.set_text(page.description)
        self._description.set_visible(bool(page.description))
        self._examples = list(page.examples)
        self._rows = [self._make_row(example, index)
                      for index, example in enumerate(self._examples)]
        for row in self._rows:
            self._list.pack_start(row, False, False, 0)
        self._list.show_all()
        self._adjustment.set_value(0)
        self._pointer = pointer_position()
        self._selected = 0
        self._pending_scroll = False
        self.select(0)

    def select(self, index, scroll=True):
        if not self._rows:
            return
        index = max(0, min(index, len(self._rows) - 1))
        self._rows[self._selected].get_style_context() \
            .remove_class('selected')
        self._selected = index
        self._rows[index].get_style_context().add_class('selected')
        if scroll:
            self._scroll_to(index)
            # A page shown just now has no layout yet; once it has, again.
            self._pending_scroll = True

    def move(self, delta):
        self.select(self._selected + delta)

    def activate(self, index, timestamp, reveal=False):
        '''Copy example `index` (0-based). False if there is none.
        `reveal` is the result list's; nothing to reveal here.'''
        if 0 <= index < len(self._examples):
            self._on_copy(tldr.copy_text(self._examples[index].command),
                          timestamp)
            return True
        return False

    def activate_selected(self, timestamp, reveal=False):
        return self.activate(self._selected, timestamp)

    def _laid_out(self, *_args):
        if self._pending_scroll and self._rows:
            self._pending_scroll = False
            self._scroll_to(self._selected)

    def _scroll_to(self, index):
        allocation = self._rows[index].get_allocation()
        if allocation.height <= 1:
            return   # not laid out yet; _laid_out comes back
        adj = self._adjustment
        top, bottom = allocation.y, allocation.y + allocation.height
        if top < adj.get_value():
            adj.set_value(top)
        elif bottom > adj.get_value() + adj.get_page_size():
            adj.set_value(bottom - adj.get_page_size())

    def _moved(self, _row, event, index):
        where = moved_to(event, self._pointer)
        if where is not None:
            self._pointer = where
            if index != self._selected:
                self.select(index, scroll=False)
        return False

    def _make_row(self, example, index):
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.set_can_focus(False)
        row.get_style_context().add_class('kachel-tldr-example')

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        text = Gtk.Label(label=example.text, xalign=0)
        text.get_style_context().add_class('kachel-tldr-text')
        text.set_line_wrap(True)
        text.set_max_width_chars(1)
        chip = Gtk.Label(xalign=0)
        chip.set_markup(chip_markup(example.command))
        chip.get_style_context().add_class('kachel-tldr-chip')
        chip.set_line_wrap(True)
        chip.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        chip.set_halign(Gtk.Align.START)
        texts.pack_start(text, False, False, 0)
        texts.pack_start(chip, False, False, 0)
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
