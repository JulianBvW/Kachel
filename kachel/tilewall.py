'''The tile wall: group headers and tiles at fixed pixel positions.

The positions come from layout.arrange, so everything that decides where a
tile goes is plain arithmetic and tested on its own. This file only turns
rectangles into widgets.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import icons, layout  # noqa: E402

# Icon size in pixels for each tile size.
ICON_SIZES = {'small': 22, 'medium': 36, 'wide': 40, 'large': 72}

# Large and wide tiles with shortcuts (Design §9).
SHORTCUT_PAD = 10
LARGE_SHORTCUT_ICON = 64
WIDE_SHORTCUT_ICON = 34
LARGE_BUTTON_HEIGHT = 36
WIDE_BUTTON = 40
BUTTON_GAP = 6
WIDE_GAP = 8
TEXT_LINE_HEIGHT = 16
TEXT_LINE_GAP = 8       # between the text line and the buttons
TEXT_LINE_INDENT = 2
SHORTCUT_GLYPH = 19
DEFAULT_SHORTCUT_ICON = 'ms:bolt'

EMPTY_HINT = ('Noch keine Kacheln — angeheftet wird in '
              '~/.config/kachel/tiles.toml')


class TileWall(Gtk.Box):
    '''Message line on top, the scrolling wall below.

    `on_activate(tile, app, timestamp)` is called when a tile is clicked,
    `on_shortcut(shortcut, timestamp)` when one of its shortcut buttons is.
    '''

    def __init__(self, on_activate, on_shortcut):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_activate = on_activate
        self._on_shortcut = on_shortcut
        self._tile_buttons = []
        self._lines = []

        # One line for what is wrong with the settings. Hidden when nothing is.
        self._error = Gtk.Label(xalign=0)
        self._error.get_style_context().add_class('kachel-error')
        self._error.set_ellipsize(Pango.EllipsizeMode.END)
        # The window is not resizable, and GTK sizes such a window to the
        # natural size of its contents. An ellipsized label still asks for
        # its whole text as natural width -- a long message would widen the
        # window off the tile grid. One character is all it may ask for; it
        # gets the full width anyway.
        self._error.set_max_width_chars(1)
        self._error.set_hexpand(True)
        self._error.set_no_show_all(True)
        self.pack_start(self._error, False, False, 0)

        self._fixed = Gtk.Fixed()
        self._scroller = Gtk.ScrolledWindow()
        self._scroller.get_style_context().add_class('kachel-wall')
        self._scroller.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        self._scroller.add(self._fixed)

        self._hint = Gtk.Label(label=EMPTY_HINT)
        self._hint.get_style_context().add_class('kachel-hint')
        self._hint.set_line_wrap(True)
        self._hint.set_max_width_chars(30)   # same reason as the message line
        self._hint.set_justify(Gtk.Justification.CENTER)
        self._hint.set_halign(Gtk.Align.CENTER)
        self._hint.set_valign(Gtk.Align.CENTER)
        self._hint.set_no_show_all(True)

        overlay = Gtk.Overlay()
        overlay.add(self._scroller)
        overlay.add_overlay(self._hint)
        self.pack_start(overlay, True, True, 0)

    def show_wall(self, groups, apps, messages, width, columns, base):
        '''Rebuild from `groups` (as from settings.assemble).

        `apps` is the AppIndex, `width` the width of the tile area,
        `columns` the number of group columns, `base` the settings folder.
        '''
        for child in self._fixed.get_children():
            self._fixed.remove(child)
            child.destroy()
        self._tile_buttons = []   # for reset_hover
        self._lines = []          # (text line, its normal text)

        arrangement = layout.arrange(groups, columns)
        for name, rect in arrangement.headers:
            header = Gtk.Label(label=name, xalign=0)
            header.get_style_context().add_class('kachel-group-header')
            header.set_ellipsize(Pango.EllipsizeMode.END)
            header.set_size_request(rect.width, rect.height)
            self._fixed.put(header, rect.x, rect.y)

        for placement, rect in arrangement.tiles:
            tile = placement.tile
            app = apps.get(tile.app) if tile.app else None
            button = self._make_tile(tile, app, rect, base)
            self._fixed.put(button, rect.x, rect.y)

        self._fixed.set_size_request(width, arrangement.height)
        self._fixed.show_all()

        empty = not arrangement.tiles and not arrangement.headers
        self._hint.set_visible(empty)

        if messages:
            text = messages[0]
            if len(messages) > 1:
                text += f'  (+{len(messages) - 1} weitere, alle mit --grid)'
            self._error.set_text(text)
            self._error.set_tooltip_text('\n'.join(messages))
            self._error.show()
        else:
            self._error.hide()

    def _make_tile(self, tile, app, rect, base):
        '''One tile: the button that starts the app, with its icon and
        label floating on top, and on large and wide tiles a row of
        shortcut buttons that run their own commands instead.

        The hover ring is set by hand rather than by :hover. A shortcut
        button has its own input window, and moving onto it would count as
        leaving the tile button -- the ring would go out right where the
        pointer still is on the tile.
        '''
        name = tile.name or (app.name if app else tile.label)

        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(False)
        button.get_style_context().add_class('tile')
        button.set_size_request(rect.width, rect.height)
        button.connect('clicked', self._clicked, tile, app)
        self._tile_buttons.append(button)

        overlay = Gtk.Overlay()
        overlay.add(button)

        if tile.shortcuts and tile.size in ('large', 'wide'):
            self._with_shortcuts(overlay, tile, app, name, rect, base)
        else:
            self._plain(overlay, tile, app, name, rect, base)

        # A box with a window of its own, so that the overlay's windows are
        # inside it: moving between them is then "inferior", not leaving.
        box = Gtk.EventBox()
        box.set_visible_window(True)
        box.get_style_context().add_class('tile-box')
        box.add(overlay)
        box.connect('enter-notify-event', self._ring, button, True)
        box.connect('leave-notify-event', self._ring, button, False)
        return box

    @staticmethod
    def _ring(_box, event, button, entering):
        if not entering and event.detail == Gdk.NotifyType.INFERIOR:
            return False   # only moved onto something inside the tile
        context = button.get_style_context()
        if entering:
            context.add_class('hover')
        else:
            context.remove_class('hover')
        return False

    @staticmethod
    def _float(overlay, widget, passive=True):
        '''Put `widget` over the tile button. Passive widgets let the
        pointer through to the button below.'''
        overlay.add_overlay(widget)
        overlay.set_overlay_pass_through(widget, passive)

    def _plain(self, overlay, tile, app, name, rect, base):
        '''Icon in the middle, label at the bottom (none on small).'''
        image = icons.icon_widget(tile.icon, ICON_SIZES[tile.size],
                                  fallback=app.icon if app else None,
                                  base=base)
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        self._float(overlay, image)

        if tile.size != 'small':
            label = Gtk.Label(label=name, xalign=0, yalign=1)
            label.get_style_context().add_class('tile-label')
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_lines(2)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(1)   # let the size request decide
            label.set_size_request(rect.width - 16, -1)
            label.set_halign(Gtk.Align.START)
            label.set_valign(Gtk.Align.END)
            label.set_margin_start(8)
            label.set_margin_end(8)
            label.set_margin_bottom(6)
            self._float(overlay, label)

    def _text_line(self, name, width):
        '''The one-line name that shows `› shortcut` while one is hovered.'''
        line = Gtk.Label(label=name, xalign=0)
        line.get_style_context().add_class('tile-textline')
        line.set_ellipsize(Pango.EllipsizeMode.END)
        line.set_max_width_chars(1)
        line.set_size_request(width, TEXT_LINE_HEIGHT)
        line.set_halign(Gtk.Align.START)
        line.set_valign(Gtk.Align.END)
        return line

    def _shortcut_button(self, shortcut, size, line, name):
        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(False)
        button.get_style_context().add_class('shortcut')
        button.set_size_request(*size)
        glyph = icons.icon_widget(shortcut.icon or DEFAULT_SHORTCUT_ICON,
                                  SHORTCUT_GLYPH)
        glyph.set_halign(Gtk.Align.CENTER)
        glyph.set_valign(Gtk.Align.CENTER)
        button.add(glyph)

        def hover(_button, _event, active):
            line.set_text(f'› {shortcut.name}' if active else name)
            context = line.get_style_context()
            if active:
                context.add_class('active')
            else:
                context.remove_class('active')
            return False

        button.connect('enter-notify-event', hover, True)
        button.connect('leave-notify-event', hover, False)
        button.connect('clicked', lambda *_: self._on_shortcut(
            shortcut, Gtk.get_current_event_time()))
        return button

    def _with_shortcuts(self, overlay, tile, app, name, rect, base):
        '''Design §9, both big sizes.

        large: icon 64 in the free space, the text line, and up to four
        buttons of 36 px in four equal columns along the bottom.
        wide:  icon 34 top left, the text line below it, and up to two
        buttons of 40 x 40 on the right, bottom-aligned.

        Every button floats on its own. A row container would catch the
        clicks in the gaps between the buttons and do nothing with them;
        this way a click there still starts the app.
        '''
        large = tile.size == 'large'
        inner = rect.width - 2 * SHORTCUT_PAD
        count = len(tile.shortcuts)

        if large:
            width = (inner - 3 * BUTTON_GAP) // 4
            size, gap = (width, LARGE_BUTTON_HEIGHT), BUTTON_GAP
            bottom = SHORTCUT_PAD + LARGE_BUTTON_HEIGHT + TEXT_LINE_GAP
            free = rect.height - SHORTCUT_PAD - bottom - TEXT_LINE_HEIGHT
            icon_size = LARGE_SHORTCUT_ICON
            line = self._text_line(name, inner - TEXT_LINE_INDENT)
            line.set_margin_start(SHORTCUT_PAD + TEXT_LINE_INDENT)
            line.set_margin_bottom(bottom)
        else:
            size, gap = (WIDE_BUTTON, WIDE_BUTTON), WIDE_GAP
            row_width = count * WIDE_BUTTON + (count - 1) * WIDE_GAP
            icon_size = WIDE_SHORTCUT_ICON
            line = self._text_line(name, inner - row_width - WIDE_GAP)
            line.set_margin_start(SHORTCUT_PAD)
            line.set_margin_bottom(SHORTCUT_PAD)

        image = icons.icon_widget(tile.icon, icon_size,
                                  fallback=app.icon if app else None,
                                  base=base)
        image.set_valign(Gtk.Align.START)
        if large:
            image.set_halign(Gtk.Align.CENTER)
            image.set_margin_top(SHORTCUT_PAD + (free - icon_size) // 2)
        else:
            image.set_halign(Gtk.Align.START)
            image.set_margin_start(SHORTCUT_PAD)
            image.set_margin_top(SHORTCUT_PAD)
        self._float(overlay, image)
        self._float(overlay, line)
        self._lines.append((line, name))

        step = size[0] + gap
        for index, shortcut in enumerate(tile.shortcuts):
            button = self._shortcut_button(shortcut, size, line, name)
            button.set_valign(Gtk.Align.END)
            button.set_margin_bottom(SHORTCUT_PAD)
            if large:   # left to right from the left edge
                button.set_halign(Gtk.Align.START)
                button.set_margin_start(SHORTCUT_PAD + index * step)
            else:       # packed against the right edge
                button.set_halign(Gtk.Align.END)
                button.set_margin_end(SHORTCUT_PAD
                                      + (count - 1 - index) * step)
            self._float(overlay, button, passive=False)

    def reset_hover(self):
        '''Rings off, names back. Clicking a button hides the window under
        a resting pointer, and no leave event comes to undo the hover --
        without this the next show would greet you with a lit tile.'''
        for button in self._tile_buttons:
            button.get_style_context().remove_class('hover')
        for line, name in self._lines:
            line.set_text(name)
            line.get_style_context().remove_class('active')

    def _clicked(self, _button, tile, app):
        self._on_activate(tile, app, Gtk.get_current_event_time())
