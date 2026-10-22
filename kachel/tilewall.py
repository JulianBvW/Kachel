'''The tile wall: group headers and tiles at fixed pixel positions.

The positions come from layout.arrange, so everything that decides where a
tile goes is plain arithmetic and tested on its own. This file only turns
rectangles into widgets.
'''

import math

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from . import anim, icons, layout, move  # noqa: E402
from .contextmenu import is_right_click  # noqa: E402

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

# Moving a tile.
GHOST_ALPHA = 0.6       # the copy at the pointer
LIFTED_ALPHA = 0.4      # the tile at its old place
FRAME_DASH = (6, 4)
FRAME_RADIUS = 4        # as the tiles'

TILE_RADIUS = 4         # as button.tile's border-radius in style.py

EMPTY_HINT = ('Noch keine Kacheln — angeheftet wird in '
              '~/.config/kachel/tiles.toml')


class TileWall(Gtk.Box):
    '''Message line on top, the scrolling wall below.

    `on_activate(tile, app, timestamp)` is called when a tile is clicked,
    `on_shortcut(shortcut, timestamp)` when one of its shortcut buttons is,
    `on_menu(what, event)` on a right-click: what is ('tile', tile, app) or
    ('wall',) for the empty space. `on_move(tile, spot)` when a tile that
    was picked up with start_move is put down somewhere else; `spot` (a
    move.Spot) says where and how.
    '''

    def __init__(self, on_activate, on_shortcut, on_menu=None, on_move=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_activate = on_activate
        self._on_shortcut = on_shortcut
        self._on_menu = on_menu or (lambda what, event: None)
        self._on_move = on_move or (lambda tile, spot: None)
        self._tile_buttons = []
        self._lines = []
        self._groups = []
        self._grid_origins = {}   # group name -> (x, y) of its grid
        self._boxes = {}          # id(tile) -> (its box, its rect)
        self._height = 0
        self._moving = None       # the tile in hand, or None
        self._effects = {}        # tile button -> (Glow, IconScale)
        self._header_rects = {}   # group name -> its header's Rect
        self._order = []          # (tile, its box), as on the wall
        self._glide_from = None   # where things were before a move
        self._glide_tick = None

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
        # The wheel moves the wall under a resting pointer: aim again.
        self._scroller.get_vadjustment().connect(
            'value-changed', lambda _a: self._aim_at_pointer())
        # Catches the right-clicks that no tile took: the empty wall.
        space = Gtk.EventBox()
        space.set_visible_window(False)
        space.add(self._fixed)
        space.connect('button-press-event', self._pressed, ('wall',))
        self._scroller.add(space)

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
        self.cancel_move(relayout=False)   # the tile in hand goes with the rest
        self._stop_glide()
        for child in self._fixed.get_children():
            self._fixed.remove(child)
            child.destroy()
        self._tile_buttons = []   # for reset_hover
        self._lines = []          # (text line, its normal text)
        self._groups = groups
        self._columns = columns
        self._width = width
        self._grid_origins = {}
        self._boxes = {}
        self._headers = {}
        self._header_rects = {}
        self._effects = {}
        self._order = []

        arrangement = layout.arrange(groups, columns)
        for name, rect in arrangement.headers:
            self._grid_origins[name] = (
                rect.x, rect.y + layout.HEADER_HEIGHT + layout.HEADER_GAP)
            header = Gtk.Label(label=name, xalign=0)
            self._headers[name] = header
            self._header_rects[name] = rect
            header.get_style_context().add_class('kachel-group-header')
            header.set_ellipsize(Pango.EllipsizeMode.END)
            header.set_size_request(rect.width, rect.height)
            self._fixed.put(header, rect.x, rect.y)

        for placement, rect in arrangement.tiles:
            tile = placement.tile
            app = apps.get(tile.app) if tile.app else None
            button = self._make_tile(tile, app, rect, base)
            self._fixed.put(button, rect.x, rect.y)
            self._boxes[id(tile)] = (button, rect)
            self._order.append((tile, button))

        self._height = arrangement.height
        self._fixed.set_size_request(width, arrangement.height)
        self._fixed.show_all()

        # Over everything, but only while a tile is in hand.
        self._layer = MoveLayer(self._moved, self._dropped,
                                self.cancel_move)
        self._fixed.put(self._layer, 0, 0)

        if self._glide_from is not None:
            self._glide(self._glide_from)
            self._glide_from = None

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
            image = self._with_shortcuts(overlay, tile, app, name, rect, base)
        else:
            image = self._plain(overlay, tile, app, name, rect, base)
        self._effects[button] = (
            anim.Glow(button, TILE_RADIUS),
            anim.IconScale(image, anim.GROW_TILE).follow(button))

        # A box with a window of its own, so that the overlay's windows are
        # inside it: moving between them is then "inferior", not leaving.
        box = Gtk.EventBox()
        box.set_visible_window(True)
        box.get_style_context().add_class('tile-box')
        box.add(overlay)
        box.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        box.connect('enter-notify-event', self._ring, button, True)
        box.connect('motion-notify-event', self._glow_follows, button)
        box.connect('button-press-event', self._pressed, ('tile', tile, app))
        box.connect('leave-notify-event', self._ring, button, False)
        return box

    def _pressed(self, _widget, event, what):
        if is_right_click(event):
            self._on_menu(what, event)
            return True
        return False

    def _ring(self, box, event, button, entering):
        if not entering and event.detail == Gdk.NotifyType.INFERIOR:
            return False   # only moved onto something inside the tile
        context = button.get_style_context()
        glow, scale = self._effects[button]
        if entering:
            context.add_class('hover')
            glow.enter(*_inside(box, event))
        else:
            context.remove_class('hover')
            glow.leave()
        scale.hover(entering)
        return False

    def _glow_follows(self, box, event, button):
        # From the root: the event may come from a window inside the tile
        # (a shortcut button, the floating name), with coordinates of its own.
        self._effects[button][0].move(*_inside(box, event))
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
        anim.make_room(image, ICON_SIZES[tile.size], anim.GROW_TILE)
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
        return image

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
        # Room to grow into, taken from the space around: the icon itself
        # stays exactly where it was.
        pad = anim.make_room(image, icon_size, anim.GROW_TILE)
        image.set_valign(Gtk.Align.START)
        if large:
            image.set_halign(Gtk.Align.CENTER)
            image.set_margin_top(SHORTCUT_PAD + (free - icon_size) // 2 - pad)
        else:
            image.set_halign(Gtk.Align.START)
            image.set_margin_start(SHORTCUT_PAD - pad)
            image.set_margin_top(SHORTCUT_PAD - pad)
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
        return image

    # -- moving a tile -----------------------------------------------------

    @property
    def moving(self):
        return self._moving is not None

    def group_tiles(self, tile):
        '''The tiles of `tile`'s group on the wall, in the file's order.'''
        for _name, placements in self._groups:
            tiles = [p.tile for p in placements]
            if any(t is tile for t in tiles):
                return tiles
        return []

    def start_move(self, tile):
        '''Pick `tile` up: a copy follows the pointer, a dashed frame shows
        where it would land, a left click puts it there. Its group gets
        empty rows below for the time being, room to put it under all.'''
        self.cancel_move()
        if id(tile) not in self._boxes:
            return
        found = move.spots(self.group_tiles(tile), tile)
        box, rect = self._boxes[id(tile)]
        self.reset_hover()
        ghost = _snapshot(box, rect)
        self._moving = tile
        self._spots = found
        self._spot = None
        self._relayout({tile.group: move.extra_rows(tile.size)})
        # Every click on the visible wall must reach the layer, also below
        # a short wall.
        visible = self._scroller.get_allocated_height()
        self._layer.set_size_request(self._width, max(self._height, visible))
        self._layer.lift(ghost, rect)
        box.set_opacity(LIFTED_ALPHA)
        self._layer.show()
        # Above the tiles' own windows, whatever GTK restacked meanwhile.
        self._layer.get_window().raise_()
        self._aim_at_pointer()

    def cancel_move(self, relayout=True):
        '''Put the tile back where it was, nothing changed. Without
        `relayout` the empty rows stay: a rebuild follows anyway.'''
        if self._moving is None:
            return
        found = self._boxes.get(id(self._moving))
        if found:
            found[0].set_opacity(1)
        self._moving = None
        self._layer.hide()
        self._layer.set_size_request(-1, -1)
        if relayout:
            self._relayout({})

    def _relayout(self, extra):
        '''Put headers and tiles where layout.arrange says, with `extra`
        empty rows for some groups; the widgets stay, they only move.'''
        self._stop_glide()   # it would pull them back to its own targets
        arrangement = layout.arrange(self._groups, self._columns, extra)
        for name, rect in arrangement.headers:
            self._grid_origins[name] = (
                rect.x, rect.y + layout.HEADER_HEIGHT + layout.HEADER_GAP)
            self._fixed.move(self._headers[name], rect.x, rect.y)
            self._header_rects[name] = rect
        for placement, rect in arrangement.tiles:
            box, _old = self._boxes[id(placement.tile)]
            self._boxes[id(placement.tile)] = (box, rect)
            self._fixed.move(box, rect.x, rect.y)
        self._height = arrangement.height
        self._fixed.set_size_request(self._width, arrangement.height)

    def _aim_at_pointer(self):
        if self._moving is not None:
            found = self._pointer()
            if found:
                self._moved(*found)

    def _pointer(self):
        '''Where the pointer is, in the wall's coordinates.'''
        window = self._layer.get_window() or self._fixed.get_window()
        seat = Gdk.Display.get_default().get_default_seat()
        if window is None or seat is None:
            return None
        _window, x, y, _mask = window.get_device_position(seat.get_pointer())
        if window is not self._layer.get_window():
            allocation = self._fixed.get_allocation()
            x, y = x - allocation.x, y - allocation.y
        return x, y

    def _moved(self, x, y):
        tile = self._moving
        if tile is None:
            return
        ox, oy = self._grid_origins[tile.group]
        self._spot = move.nearest(self._spots, tile.size, x - ox, y - oy)
        left, top, width, height = move.rect(self._spot, tile.size)
        self._layer.aim(x, y, (ox + left, oy + top, width, height))

    def _dropped(self):
        tile, spot = self._moving, self._spot
        if tile is not None and spot is not None and spot.change:
            self.cancel_move(relayout=False)
            # The rebuild after the write glides from here.
            self._glide_from = self._places()
            self._on_move(tile, spot)
        else:
            self.cancel_move()

    # -- gliding -----------------------------------------------------------

    def _keyed(self):
        '''{key: (widget, Rect)} for every tile and header, with keys that
        find the same tile again after a rebuild. Two equal tiles in a
        group cannot be told apart that way: those do not glide.'''
        found = {}
        keys = [('tile', t.group, t.app, t.name, t.command)
                for t, _box in self._order]
        for key, (tile, box) in zip(keys, self._order):
            if keys.count(key) == 1:
                found[key] = (box, self._boxes[id(tile)][1])
        for name, rect in self._header_rects.items():
            found[('header', name)] = (self._headers[name], rect)
        return found

    def _stop_glide(self):
        if self._glide_tick is not None:
            self._fixed.remove_tick_callback(self._glide_tick)
            self._glide_tick = None

    def _places(self):
        return {key: (rect.x, rect.y)
                for key, (_widget, rect) in self._keyed().items()}

    def _glide(self, before):
        keyed = self._keyed()
        after = {key: (rect.x, rect.y) for key, (_w, rect) in keyed.items()}
        moves = [(keyed[key][0], start, end)
                 for key, start, end in anim.glides(before, after)]
        self._glide_tick = anim.glide(self._fixed, moves)

    def scroll_to_top(self):
        '''For the next show: the wall starts at its first row again.'''
        self._scroller.get_vadjustment().set_value(0)

    def notice(self, text):
        '''A note in the message line, until the wall is built again.'''
        self._error.set_text(text)
        self._error.set_tooltip_text(text)
        self._error.show()

    def reset_hover(self):
        '''Rings off, names back. Clicking a button hides the window under
        a resting pointer, and no leave event comes to undo the hover --
        without this the next show would greet you with a lit tile.'''
        for button in self._tile_buttons:
            button.get_style_context().remove_class('hover')
            for effect in self._effects.get(button, ()):
                effect.reset()
        for line, name in self._lines:
            line.set_text(name)
            line.get_style_context().remove_class('active')

    def _clicked(self, _button, tile, app):
        self._on_activate(tile, app, Gtk.get_current_event_time())


def _snapshot(box, rect):
    '''The tile as it looks now, as a picture, before it is dimmed.'''
    # As sharp as the screen: on a scaled display, scaled pixels.
    scale = box.get_scale_factor()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, rect.width * scale,
                                 rect.height * scale)
    surface.set_device_scale(scale, scale)
    box.draw(cairo.Context(surface))
    return surface


class MoveLayer(Gtk.DrawingArea):
    '''Over the whole wall while a tile is in hand: it takes the pointer,
    so no tile starts or lights up, and draws the frame where the tile
    would land and the tile's copy at the pointer. The wheel goes through
    to the wall, which still scrolls.

    `on_motion(x, y)` as the pointer moves, `on_drop()` on a left click,
    `on_cancel()` on a right one.'''

    def __init__(self, on_motion, on_drop, on_cancel):
        super().__init__()
        self._on_motion = on_motion
        self._on_drop = on_drop
        self._on_cancel = on_cancel
        self._ghost = None
        self._ghost_size = (0, 0)
        self._pointer = None
        self._frame = None
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK
                        | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('motion-notify-event', self._motion)
        self.connect('button-press-event', self._pressed)
        self.connect('draw', self._draw)
        self.set_no_show_all(True)

    def lift(self, ghost, rect):
        self._ghost = ghost
        self._ghost_size = (rect.width, rect.height)
        self._pointer = None
        self._frame = None

    def aim(self, x, y, frame):
        self._pointer = (x, y)
        self._frame = frame
        self.queue_draw()

    def _motion(self, _widget, event):
        self._on_motion(event.x, event.y)
        return True

    def _pressed(self, _widget, event):
        if event.type != Gdk.EventType.BUTTON_PRESS:
            return True           # the rest of a double click
        if event.button == 1:
            self._on_motion(event.x, event.y)
            self._on_drop()
        elif event.button == 3:
            self._on_cancel()
        return True

    def _draw(self, _widget, cr):
        if self._frame is not None:
            x, y, width, height = self._frame
            _rounded(cr, x + 1, y + 1, width - 2, height - 2, FRAME_RADIUS)
            cr.set_source_rgba(1, 1, 1, 0.55)
            cr.set_line_width(2)
            cr.set_dash(FRAME_DASH)
            cr.stroke()
            cr.set_dash(())
        if self._ghost is not None and self._pointer is not None:
            width, height = self._ghost_size
            cr.set_source_surface(self._ghost, self._pointer[0] - width / 2,
                                  self._pointer[1] - height / 2)
            cr.paint_with_alpha(GHOST_ALPHA)
        return False


def _rounded(cr, x, y, width, height, radius):
    cr.new_sub_path()
    cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _inside(widget, event):
    '''The pointer of `event` in `widget`'s coordinates, whichever window
    inside it the event came from.'''
    _ok, x, y = widget.get_window().get_origin()
    return event.x_root - x, event.y_root - y
