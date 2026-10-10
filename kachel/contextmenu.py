'''The right-click menu: a popover inside the window, in Kachel's style.

Not a Gtk.Menu: that would be a window of its own, in the theme's look,
and could take the focus away -- and Kachel hides when it loses the focus.
This one floats in the window's overlay like the tooltip and the @
suggestions. A submenu opens as a second popover beside the first, which
stays; a click beside both closes them, and so does Esc.
'''

import os

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import icons  # noqa: E402
from .menumodel import SIZES  # noqa: E402

WIDTH = 260
ROW_HEIGHT = 34
GLYPH = 18
GAP = 2               # between rows, the same everywhere
EDGE = 8              # kept clear of the window's edge
SIDE_GAP = 4          # between the menu and its submenu
CONFIRM_MS = 4000

# KACHEL_DEBUG_HOVER=1: every row shows its hover surface all the time, to
# check the spacing by eye.
DEBUG_HOVER = os.environ.get('KACHEL_DEBUG_HOVER') == '1'


def is_right_click(event):
    '''A plain press of the right button (not the second of a double).'''
    return event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS


def _popover(overlay):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GAP)
    context = box.get_style_context()
    context.add_class('kachel-menu')
    if DEBUG_HOVER:
        context.add_class('debug-hover')
    box.set_halign(Gtk.Align.START)
    box.set_valign(Gtk.Align.START)
    box.set_size_request(WIDTH, -1)
    box.set_no_show_all(True)
    overlay.add_overlay(box)
    return box


def _clear(box):
    for child in box.get_children():
        box.remove(child)
        child.destroy()


class ContextMenu:
    '''`on_pick(entry, payload)` when an entry is chosen: the payload is
    the size for the size buttons, the name typed for a new group, else
    the entry's own payload.'''

    def __init__(self, overlay, on_pick, on_close=None):
        self._overlay = overlay
        self._on_pick = on_pick
        self._on_close = on_close or (lambda: None)
        self._confirm_source = None
        self._sub_entry = None     # the submenu entry that is open

        # Behind the popovers, over everything else: a click there closes.
        self._backdrop = Gtk.EventBox()
        self._backdrop.set_visible_window(False)
        self._backdrop.connect('button-press-event', self._backdrop_clicked)
        self._backdrop.set_no_show_all(True)
        overlay.add_overlay(self._backdrop)

        self._box = _popover(overlay)
        self._sub = _popover(overlay)

    @property
    def shown(self):
        return self._box.get_visible()

    @property
    def typing(self):
        '''Is the "new group" field there to take the keys?'''
        return any(isinstance(child, Gtk.Entry)
                   for child in self._sub.get_children())

    def open(self, entries, x, y):
        '''Show `entries` with the top left corner at (x, y), in the
        overlay's coordinates.'''
        self._stop_confirm()
        self._close_sub()
        _clear(self._box)
        for entry in entries:
            self._box.pack_start(self._widget(entry), False, False, 0)
        for child in self._box.get_children():
            child.show_all()
        self._box.show()
        self._backdrop.show()
        self._place(self._box, x, y, flip_x=True)

    def close(self):
        if not self.shown:
            return
        self._stop_confirm()
        self._close_sub()
        self._box.hide()
        self._backdrop.hide()
        self._on_close()

    # -- placing -----------------------------------------------------------

    def _measure(self, box):
        '''Its natural size. The margins of the last placement must not
        count into it: GTK adds them to what a widget asks for.'''
        box.set_margin_start(0)
        box.set_margin_top(0)
        _minimum, natural = box.get_preferred_size()
        return natural.width, natural.height

    def _place(self, box, x, y, flip_x):
        '''At (x, y), inside the window. Sticking out to the right, it goes
        to the left of x instead (if `flip_x`); sticking out at the bottom,
        it goes up as far as needed.'''
        w, h = self._measure(box)
        width = self._overlay.get_allocated_width()
        height = self._overlay.get_allocated_height()
        if flip_x and x + w > width - EDGE:
            x -= w
        if y + h > height - EDGE:
            y = height - EDGE - h
        box.set_margin_start(max(EDGE, min(x, width - w - EDGE)))
        box.set_margin_top(max(EDGE, y))

    # -- rows --------------------------------------------------------------

    def _widget(self, entry):
        if entry.kind == 'sizes':
            return self._sizes(entry)
        if entry.kind == 'submenu':
            row = self._row(entry.icon, entry.label, None, more=True)
            row.connect('clicked', self._open_sub, entry)
            row.connect('enter-notify-event',
                        lambda r, _e: self._open_sub(r, entry) or False)
        elif entry.id.endswith('-new'):
            row = self._row(entry.icon, entry.label,
                            lambda *_: self._ask_name(entry))
        elif entry.confirm:
            row = self._row(entry.icon, entry.label, None)
            row.connect('clicked', self._confirm_clicked, entry)
        else:
            row = self._row(entry.icon, entry.label,
                            lambda *_: self._on_pick(entry, entry.payload))
        if entry.kind != 'submenu' and self._sub_entry is None:
            # Into a plain row of the main menu: the submenu goes.
            row.connect('enter-notify-event', self._leave_sub)
        row.set_sensitive(entry.enabled)
        return row

    def _row(self, icon, label, on_click, more=False):
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.set_can_focus(False)
        row.get_style_context().add_class('kachel-menu-row')
        row.set_size_request(-1, ROW_HEIGHT)
        content = Gtk.Box(spacing=10)
        glyph = icons.icon_widget(icon, GLYPH) if icon else Gtk.Box()
        glyph.set_size_request(GLYPH, GLYPH)
        glyph.set_valign(Gtk.Align.CENTER)
        content.pack_start(glyph, False, False, 0)
        text = Gtk.Label(label=label, xalign=0)
        text.set_ellipsize(Pango.EllipsizeMode.END)
        text.set_max_width_chars(1)
        content.pack_start(text, True, True, 0)
        if more:
            content.pack_start(icons.icon_widget('ms:chevron_right', GLYPH),
                               False, False, 0)
        row.add(content)
        if on_click is not None:
            row.connect('clicked', on_click)
        return row

    def _sizes(self, entry):
        '''Four buttons side by side, the current size lit. As tall as a
        row, so the gaps above and below are the same as everywhere.'''
        box = Gtk.Box(spacing=4, homogeneous=True)
        box.set_size_request(-1, ROW_HEIGHT)
        for size, label in SIZES:
            button = Gtk.Button(label=label)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.set_can_focus(False)
            context = button.get_style_context()
            context.add_class('kachel-menu-size')
            if size == entry.payload:
                context.add_class('selected')
            button.connect('clicked',
                           lambda _b, s=size: self._on_pick(entry, s))
            box.pack_start(button, True, True, 0)
        return box

    # -- the submenu -------------------------------------------------------

    def _open_sub(self, row, entry):
        '''Beside the main menu, level with its row; on the left if there
        is no room on the right.'''
        if self._sub_entry is entry and self._sub.get_visible():
            return
        self._stop_confirm()
        self._sub_entry = entry
        _clear(self._sub)
        for child in entry.children:
            self._sub.pack_start(self._widget(child), False, False, 0)
        for child in self._sub.get_children():
            child.show_all()
        self._sub.show()
        self._place_sub(row)

    def _place_sub(self, row):
        w, _h = self._measure(self._sub)
        main_x = self._box.get_margin_start()
        found = row.translate_coordinates(self._box, 0, 0)
        y = self._box.get_margin_top() + (found[1] if found else 0) \
            - 6 - 1   # the popover's padding and border, so the rows align
        x = main_x + WIDTH + SIDE_GAP
        if x + w > self._overlay.get_allocated_width() - EDGE:
            x = main_x - SIDE_GAP - w
        self._place(self._sub, x, y, flip_x=False)

    def _leave_sub(self, *_args):
        self._close_sub()
        return False

    def _close_sub(self):
        self._sub_entry = None
        self._sub.hide()
        _clear(self._sub)

    def _ask_name(self, entry):
        '''The "new group" row turns into a field. Enter takes the name.'''
        rows = self._sub.get_children()
        for row in rows[-1:]:
            self._sub.remove(row)
            row.destroy()
        field = Gtk.Entry()
        field.get_style_context().add_class('kachel-menu-entry')
        field.set_placeholder_text('Name der neuen Gruppe')
        field.set_size_request(-1, ROW_HEIGHT)
        field.connect('activate', lambda f: self._named(entry, f.get_text()))
        self._sub.pack_start(field, False, False, 0)
        field.show()
        field.grab_focus()

    def _named(self, entry, name):
        if name.strip():
            self._on_pick(entry, name.strip())

    # -- asking twice ------------------------------------------------------

    def _confirm_clicked(self, row, entry):
        context = row.get_style_context()
        if context.has_class('armed'):
            self._stop_confirm()
            self._on_pick(entry, entry.payload)
            return
        context.add_class('armed')
        label = row.get_child().get_children()[1]
        label.set_text(entry.confirm)

        def disarm():
            self._confirm_source = None
            context.remove_class('armed')
            label.set_text(entry.label)
            return GLib.SOURCE_REMOVE
        self._stop_confirm()
        self._confirm_source = GLib.timeout_add(CONFIRM_MS, disarm)

    def _stop_confirm(self):
        if self._confirm_source is not None:
            GLib.source_remove(self._confirm_source)
            self._confirm_source = None

    def _backdrop_clicked(self, _box, _event):
        self.close()
        return True
