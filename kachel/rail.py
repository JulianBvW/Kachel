'''The icon rail on the left: folders on top, actions at the bottom.

Design §8. The entries carry no text; the tooltip beside the rail names
them. Actions sit on pages of four places that slide sideways, and an
action can ask before it runs: the first click arms it, a coloured fill
rises, and only a second click before it reaches the top runs it.
'''

import math

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import anim, config, icons, railmodel  # noqa: E402
from .slide import Slider, cubic_bezier  # noqa: E402

# The hairline on the rail's right edge is part of its 60 px. Whatever
# sits inside gets the rest.
RAIL_BORDER = 1
ENTRY_WIDTH = 44
ENTRY_INDENT = 8
GLYPH = 22
RADIUS = 6
DEFAULT_ACTION_ICON = 'ms:bolt'
ARMED_HINT = 'Zum Ausführen nochmal klicken'
DISARM_MS = 220
EASE_OUT = cubic_bezier(0, 0, 0.58, 1)

# The two places that turn the page.
NAVIGATION = {
    railmodel.MORE: ('ms:more_horiz', 'Mehr', 1),
    railmodel.BACK: ('ms:arrow_back', 'Zurück', 0),
}


def linear(t):
    return t


class Entry(Gtk.Button):
    '''One place on the rail: a glyph, a name for the tooltip, and for an
    action with `confirm` the fill that rises while it is armed.'''

    def __init__(self, icon, name, sub, tooltip, on_click, confirm=None,
                 base=None):
        super().__init__()
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_can_focus(False)
        self.get_style_context().add_class('rail-entry')
        self.set_size_request(ENTRY_WIDTH, railmodel.ENTRY_HEIGHT)
        self.set_halign(Gtk.Align.START)
        self.set_margin_start(ENTRY_INDENT)
        self._name, self._sub = name, sub
        self._tooltip = tooltip
        self._on_click = on_click
        self._confirm = confirm
        self._armed = False
        self._level = 0.0          # how far the fill has risen, 0 to 1
        self._animation = None     # (from, to, µs, ease, start or None)
        self._tick = None

        # Nothing inside the button may have a GdkWindow of its own: no
        # Stack, no Overlay, no DrawingArea. After the page slides, GTK
        # restacks such windows above the button's input window, and the
        # glyph then swallows hover and clicks. So the fill is drawn by
        # the button itself, under its child, and the check mark is a
        # second glyph that is shown instead of the first.
        glyphs = Gtk.Box()
        glyphs.set_halign(Gtk.Align.CENTER)
        glyphs.set_valign(Gtk.Align.CENTER)
        self._glyph = icons.icon_widget(icon, GLYPH, base=base)
        self._glyph.set_halign(Gtk.Align.CENTER)
        glyphs.pack_start(self._glyph, True, True, 0)
        self._check = None
        if confirm is not None:
            self._check = icons.icon_widget('ms:check', GLYPH)
            self._check.set_halign(Gtk.Align.CENTER)
            self._check.set_no_show_all(True)
            glyphs.pack_start(self._check, True, True, 0)
        self.add(glyphs)
        # Room around the glyph to grow into under the pointer.
        anim.make_room(glyphs, GLYPH, anim.GROW_RAIL)
        self._scale = anim.IconScale(glyphs, anim.GROW_RAIL).follow(self)
        self.connect('draw', self._draw_fill)

        self.connect('enter-notify-event', self._enter)
        self.connect('leave-notify-event', self._leave)
        self.connect('clicked', self._clicked)

    @property
    def armed(self):
        return self._armed

    # -- the tooltip -----------------------------------------------------

    def _show_tooltip(self):
        if self._armed:
            self._tooltip.show_for(self, self._confirm.label, ARMED_HINT)
        else:
            self._tooltip.show_for(self, self._name, self._sub)

    def _enter(self, _widget, event):
        if event.mode == Gdk.CrossingMode.NORMAL:
            self._show_tooltip()
            self._scale.hover(True)
        return False

    def _leave(self, _widget, event):
        # A press grabs the pointer, and that shows up as a crossing of its
        # own; only really moving away counts.
        if event.mode != Gdk.CrossingMode.NORMAL:
            return False
        self._tooltip.hide_for(self)
        self._scale.hover(False)
        if self._armed:
            self.disarm()
        return False

    # -- clicking and confirming ---------------------------------------

    def _clicked(self, _button):
        # A double-click goes through: two clicks are a decision, however
        # quick. Confirming guards against a single stray click.
        if self._confirm is not None and not self._armed:
            self.arm()
            return
        self._tooltip.hide_now()
        self._on_click(Gtk.get_current_event_time())

    def arm(self):
        '''First click: the check mark, the confirm text, and the fill
        rising linearly over the confirm duration.'''
        self._armed = True
        self._show_glyph(armed=True)
        self._animate(0.0, 1.0, self._confirm.duration, linear)
        self._show_tooltip()

    def disarm(self):
        '''Back to normal: the fill falls, glyph and name come back.'''
        self._armed = False
        self._show_glyph(armed=False)
        self._animate(self._level, 0.0, DISARM_MS, EASE_OUT)
        if self._tooltip.anchor is self:
            self._show_tooltip()

    def reset(self):
        '''Normal at once, no fall to watch: for the next show.'''
        self._scale.reset()
        self._armed = False
        if self._confirm is not None:
            self._show_glyph(armed=False)
        self._stop()
        self._level = 0.0
        self.queue_draw()

    def _animate(self, start, end, ms, ease):
        self._level = start
        self._animation = (start, end, ms * 1000, ease, None)
        if self._tick is None:
            self._tick = self.add_tick_callback(self._on_tick)

    def _on_tick(self, _widget, clock):
        start, end, duration, ease, began = self._animation
        now = clock.get_frame_time()
        if began is None:
            began = now
            self._animation = (start, end, duration, ease, began)
        t = min(1.0, (now - began) / duration)
        self._level = start + (end - start) * ease(t)
        self.queue_draw()
        if t < 1.0:
            return True
        self._tick = None
        if self._armed and end == 1.0:
            # Reached the top without a second click: the moment passed.
            self.disarm()
        return False

    def _stop(self):
        if self._tick is not None:
            self.remove_tick_callback(self._tick)
            self._tick = None

    def _show_glyph(self, armed):
        self._glyph.set_visible(not armed)
        self._check.set_visible(armed)

    def _draw_fill(self, _button, cr):
        '''Runs before the button draws itself, so the fill lies under the
        hover background and the glyph.'''
        if self._level <= 0 or self._confirm is None:
            return False
        # Inside the press margin, like the button's own background.
        margin = self.get_style_context().get_margin(self.get_state_flags())
        width = self.get_allocated_width() - margin.left - margin.right
        height = self.get_allocated_height() - margin.top - margin.bottom
        cr.save()
        cr.translate(margin.left, margin.top)
        # The entry's rounded shape as the clip, the fill rising inside it.
        r = RADIUS
        cr.new_sub_path()
        cr.arc(width - r, r, r, -math.pi / 2, 0)
        cr.arc(width - r, height - r, r, 0, math.pi / 2)
        cr.arc(r, height - r, r, math.pi / 2, math.pi)
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.clip()
        top = height * (1 - self._level)
        cr.rectangle(0, top, width, height - top)
        cr.set_source_rgba(*self._confirm.color)
        cr.fill()
        cr.restore()   # the clip must not reach the glyph
        return False


class Rail(Gtk.Box):
    '''`on_folder(folder, timestamp)` and `on_action(action, timestamp)`
    are called when an entry is clicked (an action with confirm: on the
    second click).'''

    def __init__(self, on_folder, on_action, tooltip):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class('kachel-rail')
        self.set_size_request(config.RAIL_WIDTH, -1)
        self._on_folder = on_folder
        self._on_action = on_action
        self._tooltip = tooltip
        self._entries = []
        self._slider = None

        self._folders = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                spacing=railmodel.ENTRY_GAP)
        self._folders.set_margin_top(railmodel.PAD)
        self.pack_start(self._folders, False, False, 0)

    def show_rail(self, folders, pages, base):
        '''Rebuild from what railmodel.assemble worked out.'''
        # The entry under a showing tooltip is about to go.
        self._tooltip.hide_now()
        for child in self._folders.get_children():
            self._folders.remove(child)
            child.destroy()
        if self._slider is not None:
            self.remove(self._slider)
            self._slider.destroy()
            self._slider = None
        self._entries = []

        for folder in folders:
            entry = Entry(folder.icon, folder.name,
                          folder.shown, self._tooltip,
                          lambda ts, f=folder: self._on_folder(f, ts),
                          base=base)
            self._entries.append(entry)
            self._folders.pack_start(entry, False, False, 0)
        self._folders.show_all()

        if pages:
            slots = len(pages[0])
            height = slots * railmodel.ENTRY_HEIGHT \
                + (slots - 1) * railmodel.ENTRY_GAP
            self._slider = Slider(config.RAIL_WIDTH - RAIL_BORDER, height)
            self._slider.set_margin_bottom(railmodel.PAD)
            self._slider.set_pages([self._page(page, base)
                                    for page in pages])
            self._slider.on_page_changed = lambda _i: self._tooltip.hide_now()
            self.pack_end(self._slider, False, False, 0)
            self._slider.show_all()

    def _page(self, page, base):
        '''One page of actions, packed to the bottom: the page-turning
        place is the lowest on both pages, so it stays put.'''
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      spacing=railmodel.ENTRY_GAP)
        box.set_valign(Gtk.Align.END)
        # The slider gives every page its full height; the entries sink to
        # the bottom inside it.
        page_box = Gtk.Box()
        page_box.pack_start(box, True, True, 0)
        for item in page:
            if isinstance(item, str):   # MORE or BACK
                icon, name, target = NAVIGATION[item]
                entry = Entry(icon, name, '', self._tooltip,
                              lambda _ts, t=target: self._slider.show_page(t))
            else:
                entry = Entry(item.icon or DEFAULT_ACTION_ICON, item.name, '',
                              self._tooltip,
                              lambda ts, a=item: self._on_action(a, ts),
                              confirm=item.confirm, base=base)
            self._entries.append(entry)
            box.pack_start(entry, False, False, 0)
        return page_box

    @property
    def page(self):
        return self._slider.page if self._slider is not None else 0

    def show_page(self, index, animate=True):
        if self._slider is not None:
            self._slider.show_page(index, animate)

    def reset(self):
        '''First page, nothing armed, no tooltip.'''
        for entry in self._entries:
            entry.reset()
        if self._slider is not None:
            self._slider.show_page(0, animate=False)
        self._tooltip.hide_now()
