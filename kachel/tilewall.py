'''The tile wall: group headers and tiles at fixed pixel positions.

The positions come from layout.arrange, so everything that decides where a
tile goes is plain arithmetic and tested on its own. This file only turns
rectangles into widgets.
'''

from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gio, Gtk, Pango  # noqa: E402

from . import layout  # noqa: E402

# Icon size in pixels for each tile size.
ICON_SIZES = {'small': 22, 'medium': 36, 'wide': 40, 'large': 72}
FALLBACK_ICON = 'application-x-executable'

EMPTY_HINT = ('Noch keine Kacheln — angeheftet wird in '
              '~/.config/kachel/tiles.toml')


def tile_icon(tile, app, base):
    '''The Gio.Icon for a tile: its own `icon`, else the app's, else a
    generic one. `ms:` icons need the icon font of phase 3; until then the
    app's own icon stands in. A relative file path is taken relative to the
    settings folder `base`, not to wherever the service happened to start.'''
    spec = tile.icon
    if spec and spec.startswith('theme:'):
        return Gio.ThemedIcon.new(spec[len('theme:'):])
    if spec and not spec.startswith('ms:'):
        path = Path(base) / Path(spec).expanduser()
        if path.is_file():
            return Gio.FileIcon.new(Gio.File.new_for_path(str(path)))
    if app is not None and app.icon is not None:
        return app.icon
    return Gio.ThemedIcon.new(FALLBACK_ICON)


class TileWall(Gtk.Box):
    '''Message line on top, the scrolling wall below.

    `on_activate(tile, app, timestamp)` is called when a tile is clicked.
    '''

    def __init__(self, on_activate):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_activate = on_activate

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
        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(False)
        button.get_style_context().add_class('tile')
        button.set_size_request(rect.width, rect.height)

        name = tile.name or (app.name if app else tile.label)

        overlay = Gtk.Overlay()
        # The base layer fixes the size; icon and label float on top of it.
        base = Gtk.Box()
        base.set_size_request(rect.width, rect.height)
        overlay.add(base)

        image = Gtk.Image.new_from_gicon(tile_icon(tile, app, base),
                                         Gtk.IconSize.DIALOG)
        image.set_pixel_size(ICON_SIZES[tile.size])
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.CENTER)
        overlay.add_overlay(image)
        # In GTK 3 every overlay child gets an input window of its own, on
        # top of the button's. Without pass-through, moving onto the icon
        # leaves the button -- and its hover ring goes out.
        overlay.set_overlay_pass_through(image, True)

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
            overlay.add_overlay(label)
            overlay.set_overlay_pass_through(label, True)

        button.add(overlay)
        button.connect('clicked', self._clicked, tile, app)
        return button

    def _clicked(self, _button, tile, app):
        self._on_activate(tile, app, Gtk.get_current_event_time())
