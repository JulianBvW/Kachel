'''The app list: every app from A to Z, with an alphabet rail to jump.

Design §10. It takes the place of the tile wall -- the two slide past each
other -- and has no keyboard use of its own (§11.5). Rebuilt with the wall,
so opening it costs nothing.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import icons, listmodel  # noqa: E402
from .slide import EASE_OUT_SLOW  # noqa: E402

SECTION_HEIGHT = 30
ROW_HEIGHT = 42
PLATE = 30
ICON = 19
# The list leaves room on the right for the alphabet rail.
LIST_MARGINS = (0, 40, 16, 12)      # top, right, bottom, left
RAIL_WIDTH = 22
RAIL_RIGHT = 8
RAIL_TOP = 12
RAIL_BOTTOM = 12
SCROLL_MS = 300


class AppList(Gtk.Box):
    '''`on_activate(app, timestamp)` when a row is clicked. No header of
    its own: the list starts right under the search bar, and the switch
    there is the way back.'''

    def __init__(self, on_activate):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_activate = on_activate
        self._sections = []        # [(letter, header label)]
        self._present = set()
        self._scroll = None        # (from, to, start or None) while gliding
        self._tick = None
        self._drag_letter = None   # the letter under a held button
        self._landed = None        # (letter, scroll) of the last jump
        self._rows = {}            # app ID -> its group label
        self._shown_ids = None     # the apps the rows were built for

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top, right, bottom, left = LIST_MARGINS
        self._content.set_margin_top(top)
        self._content.set_margin_end(right)
        self._content.set_margin_bottom(bottom)
        self._content.set_margin_start(left)

        self._scroller = Gtk.ScrolledWindow()
        self._scroller.get_style_context().add_class('kachel-wall')
        # EXTERNAL: scrolls like any list, but shows no bar.
        self._scroller.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.EXTERNAL)
        self._scroller.add(self._content)
        # The headers only know where they are once laid out -- and inside
        # the allocation they are still being placed, so it waits a beat.
        self._update_source = None
        self._content.connect('size-allocate', self._queue_update)
        self._adjustment = self._scroller.get_vadjustment()
        self._adjustment.connect('value-changed', self._update_current)

        overlay = Gtk.Overlay()
        overlay.add(self._scroller)
        overlay.add_overlay(self._alphabet())
        self.pack_start(overlay, True, True, 0)

    # -- building --------------------------------------------------------

    def _alphabet(self):
        '''A–Z # on the right. One box for all letters: pressing and
        dragging work out the letter from the height, not from which
        label happens to be under the pointer.'''
        self._letters = {}
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        column.set_homogeneous(True)
        for letter in listmodel.LETTERS:
            label = Gtk.Label(label=letter)
            label.get_style_context().add_class('kachel-alpha')
            column.pack_start(label, True, True, 0)
            self._letters[letter] = label

        box = Gtk.EventBox()
        box.set_visible_window(False)
        box.add(column)
        box.set_size_request(RAIL_WIDTH, -1)
        box.set_halign(Gtk.Align.END)
        box.set_margin_end(RAIL_RIGHT)
        box.set_margin_top(RAIL_TOP)
        box.set_margin_bottom(RAIL_BOTTOM)
        box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                       | Gdk.EventMask.POINTER_MOTION_MASK
                       | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        box.connect('button-press-event', self._rail_pressed)
        box.connect('motion-notify-event', self._rail_moved)
        box.connect('leave-notify-event', lambda *_: self._hover(None))
        return box

    def show_apps(self, apps, pinned):
        '''Rebuild from `apps` (sorted) and {app ID: group}.

        Most reloads are a saved settings file, which can only change the
        group names on the right. The rows -- a few hundred widgets and
        icon lookups -- are only built again when the apps changed.'''
        ids = tuple((app.id, app.name) for app in apps)
        if ids == self._shown_ids:
            for app_id, label in self._rows.items():
                label.set_text(pinned.get(app_id, ''))
            return
        self._shown_ids = ids
        self._rows = {}
        for child in self._content.get_children():
            self._content.remove(child)
            child.destroy()
        self._sections = []
        groups = listmodel.sections(apps)
        for letter, members in groups:
            header = Gtk.Label(label=letter, xalign=0)
            header.get_style_context().add_class('kachel-group-header')
            header.get_style_context().add_class('kachel-list-section')
            header.set_size_request(-1, SECTION_HEIGHT)
            self._content.pack_start(header, False, False, 0)
            self._sections.append((letter, header))
            for app in members:
                self._content.pack_start(self._row(app, pinned.get(app.id)),
                                         False, False, 0)
        self._content.show_all()

        self._present = {letter for letter, _ in groups}
        for letter, label in self._letters.items():
            context = label.get_style_context()
            if letter in self._present:
                context.add_class('present')
            else:
                context.remove_class('present')
        self._update_current()

    def _row(self, app, group):
        '''One app. Nothing in it has a window of its own (see rail.py).'''
        row = Gtk.Button()
        row.set_relief(Gtk.ReliefStyle.NONE)
        row.set_can_focus(False)
        row.get_style_context().add_class('kachel-list-row')
        row.set_size_request(-1, ROW_HEIGHT)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        plate = Gtk.Box()
        plate.get_style_context().add_class('kachel-list-plate')
        plate.set_size_request(PLATE, PLATE)
        plate.set_valign(Gtk.Align.CENTER)
        glyph = icons.icon_widget(None, ICON, fallback=app.icon)
        glyph.set_halign(Gtk.Align.CENTER)
        glyph.set_valign(Gtk.Align.CENTER)
        plate.set_center_widget(glyph)
        content.pack_start(plate, False, False, 0)

        name = Gtk.Label(label=app.name, xalign=0)
        name.get_style_context().add_class('kachel-list-name')
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(1)
        content.pack_start(name, True, True, 0)

        where = Gtk.Label(label=group or '', xalign=1)
        where.get_style_context().add_class('kachel-list-group')
        content.pack_start(where, False, False, 0)
        self._rows[app.id] = where

        row.add(content)
        row.connect('clicked', lambda *_: self._on_activate(
            app, Gtk.get_current_event_time()))
        return row

    # -- scrolling -------------------------------------------------------

    def _offsets(self):
        '''[(letter, y of its header in the list)], read from the layout.'''
        out = []
        for letter, header in self._sections:
            found = header.translate_coordinates(self._content, 0, 0)
            if found:
                out.append((letter, found[1] + LIST_MARGINS[0]))
        return out

    def jump(self, letter, smooth=True):
        '''Scroll to the section of `letter`, or the next one that has
        apps. Returns the letter it went to.'''
        target = listmodel.jump_target(letter, self._present)
        if target is None:
            return None
        y = dict(self._offsets()).get(target, 0)
        adj = self._adjustment
        y = max(adj.get_lower(), min(y, adj.get_upper() - adj.get_page_size()))
        # Near the end the list cannot scroll far enough to bring the
        # header to the top; the letter that was asked for stays lit.
        self._landed = (target, y)
        if smooth and self.get_mapped():
            self._scroll = (adj.get_value(), y, None)
            if self._tick is None:
                self._tick = self.add_tick_callback(self._on_tick)
        else:
            self._stop()
            adj.set_value(y)
            # Landing where it already was changes no value, and so sends
            # no signal to light the new letter.
            self._update_current()
        return target

    def _on_tick(self, _widget, clock):
        start, end, began = self._scroll
        now = clock.get_frame_time()
        if began is None:
            began = now
            self._scroll = (start, end, began)
        t = min(1.0, (now - began) / (SCROLL_MS * 1000))
        self._adjustment.set_value(start + (end - start) * EASE_OUT_SLOW(t))
        if t < 1.0:
            return True
        self._tick = None
        return False

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def reset(self):
        '''Back to the top, for the next time the list opens.'''
        self._stop()
        self._landed = None
        self._adjustment.set_value(0)
        self._hover(None)
        self._update_current()

    def _queue_update(self, *_args):
        if self._update_source is None:
            self._update_source = GLib.idle_add(self._idle_update)

    def _idle_update(self):
        self._update_source = None
        self._update_current()
        return GLib.SOURCE_REMOVE

    def _update_current(self, *_args):
        adj = self._adjustment
        value = adj.get_value()
        if self._landed and self._tick is None \
                and abs(value - self._landed[1]) > 1:
            self._landed = None   # scrolled away since
        if self._landed:
            current = self._landed[0]
        else:
            current = listmodel.current_letter(
                self._offsets(), value, adj.get_upper() - adj.get_page_size())
        for letter, label in self._letters.items():
            context = label.get_style_context()
            if letter == current:
                context.add_class('current')
            else:
                context.remove_class('current')

    # -- the alphabet rail -----------------------------------------------

    def _letter_under(self, box, y):
        return listmodel.letter_at(y, box.get_allocated_height())

    def _rail_pressed(self, box, event):
        if event.button != 1 or event.type != Gdk.EventType.BUTTON_PRESS:
            return True
        self._drag_letter = self._letter_under(box, event.y)
        self.jump(self._drag_letter, smooth=True)
        return True

    def _rail_moved(self, box, event):
        letter = self._letter_under(box, event.y)
        self._hover(letter)
        if event.state & Gdk.ModifierType.BUTTON1_MASK \
                and letter != self._drag_letter:
            # Dragging onto another letter: follow at once, no gliding
            # behind the pointer. A wobble on the clicked letter is not a
            # drag and leaves its glide alone.
            self._drag_letter = letter
            self.jump(letter, smooth=False)
        return True

    def _hover(self, letter):
        for other, label in self._letters.items():
            context = label.get_style_context()
            if other == letter:
                context.add_class('hover')
            else:
                context.remove_class('hover')
