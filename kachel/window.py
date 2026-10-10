'''The window itself: a pane of dark glass in the middle of the screen.'''

import math
import time
from pathlib import Path

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import (blur, config, geometry, icons, launch,  # noqa: E402
               railmodel, search, settings, style)
from .apps import AppIndex  # noqa: E402
from .rail import Rail  # noqa: E402
from .results import ResultList  # noqa: E402
from .searchbar import SearchBar  # noqa: E402
from .tilewall import TileWall  # noqa: E402
from .tooltip import Tooltip  # noqa: E402

# X11-only, and only needed for a fresh server timestamp. Kept optional so the
# import does not bring the whole program down on a session without it.
try:
    gi.require_version('GdkX11', '3.0')
    from gi.repository import GdkX11
except (ValueError, ImportError):  # pragma: no cover
    GdkX11 = None


def toggle_should_show(visible, ms_since_focus_hide):
    '''What the shortcut means right now: True to show, False to hide.

    `ms_since_focus_hide` is how long ago the window was hidden for losing
    the focus, or None if that has not happened since the last show. The
    shortcut is a keyboard grab, and the grab alone can take the focus away
    before the toggle arrives. The window is then already hidden, but the
    press meant "hide" -- so a toggle that close behind a focus-loss hide
    leaves it hidden instead of bringing it straight back.
    '''
    if visible:
        return False
    if ms_since_focus_hide is not None \
            and ms_since_focus_hide < config.FOCUS_HIDE_GRACE_MS:
        return False
    return True


class KachelWindow(Gtk.Window):
    '''A window that spends most of its life hidden.

    It is never destroyed and never rebuilt. Showing it is only a matter of
    mapping it again, which is the whole reason the program stays resident:
    there is no startup left to pay for at the moment the key is pressed.
    '''

    def __init__(self, config_dir=None, verbose=False):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._verbose = verbose
        self._config_dir = config_dir or config.CONFIG_DIR

        # When the window last went away for losing the focus, as
        # time.monotonic(). None while it is up or was hidden any other way.
        self._focus_hidden_at = None

        self.set_title(config.PROGRAM_CLASS)
        self.set_decorated(False)

        # NORMAL, not UTILITY or DIALOG. BlurCinnamon only accepts NORMAL,
        # DOCK and DESKTOP -- anything else is simply never blurred, and
        # without any error to go on.
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        # It is an overlay, not a window you manage.
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)

        # Fixed size, placed by us. The width comes from the tile grid; both
        # are set for real by _apply_size once the settings are read.
        self._width = self._height = None
        self.set_position(Gtk.WindowPosition.NONE)
        self.set_resizable(False)

        self._blurred = False
        self._background = config.BG_RGBA_NO_BLUR
        self._check_blur()

        self._rgba = self._setup_transparency()
        self.connect('draw', self._on_draw)
        self.connect('key-press-event', self._on_key_press)
        self.connect('focus-out-event', self._on_focus_out)

        # Closing the window would destroy it and cost us the instant reopen.
        # Hide instead -- the only way out is the quit action.
        self.connect('delete-event', lambda *_: self.hide_kachel() or True)

        self._style = style.Style()
        Gtk.Settings.get_default().connect(
            'notify::gtk-fontconfig-timestamp', self._on_fontconfig_changed)
        self._apps = AppIndex()
        self._general = settings.General()
        self._wall_settings = settings.Wall()
        self._rail_settings = settings.default_rail()
        self._rail_shown = None   # (folders, pages, messages) on the rail
        self._build_body()

        written, self._setup_problems = settings.ensure_files(
            self._config_dir)
        for path in written:
            self._log(f'wrote the skeleton {path}')
        self._reload_source = None
        self._apps_stale = False
        self._watch()
        self.reload()

        # Realise early so there is a GdkWindow to ask for a server timestamp
        # the first time we are shown.
        self.realize()

    # -- contents --------------------------------------------------------

    def _build_body(self):
        '''Search bar on top; below it either the main view or the results.

        The main view is the rail on the left and the wall, with the rail's
        tooltip floating over both. While there is something in the search
        field, a single result list takes the place of all that.
        '''
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class('kachel-root')

        self.searchbar = SearchBar(on_changed=self._on_search_changed,
                                   on_close=self.hide_kachel)
        root.pack_start(self.searchbar, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.tooltip = Tooltip()
        self.rail = Rail(on_folder=self._on_folder, on_action=self._on_action,
                         tooltip=self.tooltip)
        main.pack_start(self.rail, False, False, 0)
        self.wall = TileWall(on_activate=self._on_activate,
                             on_shortcut=self._on_shortcut)
        main.pack_start(self.wall, True, True, 0)
        overlay = Gtk.Overlay()
        overlay.add(main)
        overlay.add_overlay(self.tooltip)
        # Over the wall, but never in its way: the tile under the tooltip
        # keeps its hover and its clicks.
        overlay.set_overlay_pass_through(self.tooltip, True)

        self.results = ResultList(on_activate=self._on_result)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(self.results, f'set_margin_{side}')(10)

        # No transition: switching is a redraw, not an animation to wait for.
        self._body = Gtk.Stack()
        self._body.set_transition_type(Gtk.StackTransitionType.NONE)
        self._body.add_named(overlay, 'main')
        self._body.add_named(self.results, 'results')
        root.pack_start(self._body, True, True, 0)

        self.add(root)
        # Shown now, so mapping the window later is all it takes.
        root.show_all()

    def reload(self):
        '''Read the settings and rebuild the wall.

        A file that is not TOML at all keeps what was there before; its
        complaint goes into the message line. Everything else counts as far
        as it is right, and what is wrong is reported.
        '''
        t0 = time.monotonic()
        if self._apps_stale:
            self._apps.reload()
            self._apps_stale = False
        general, messages = settings.load_general(self._config_dir)
        messages = self._setup_problems + messages
        if general is not None:
            self._general = general
        wall, more = settings.load_tiles(self._config_dir)
        messages += more
        if wall is not None:
            self._wall_settings = wall

        rail, more = settings.load_rail(self._config_dir)
        messages += more
        if rail is not None:
            self._rail_settings = rail

        groups, more = settings.assemble(self._wall_settings,
                                         self._apps.resolve)
        messages += more

        self._apply_size()
        messages += self._build_rail()
        area = self._width - config.RAIL_WIDTH
        self.wall.show_wall(groups, self._apps, messages, area,
                            self._general.columns, self._config_dir)

        count = sum(len(p) for _name, p in groups)
        self._log(f'wall built: {len(groups)} groups, {count} tiles, '
                  f'{len(messages)} messages, '
                  f'{(time.monotonic() - t0) * 1000:.1f} ms')
        for message in messages:
            self._log(f'  {message}')

    def _assemble_rail(self):
        return railmodel.assemble(self._rail_settings, railmodel.special_dir,
                                  Path.home(), self._height)

    def _build_rail(self):
        '''Work out the rail and rebuild it. -> messages.'''
        folders, pages, messages = self._assemble_rail()
        self._rail_shown = (folders, pages, messages)
        self.rail.show_rail(folders, pages, self._config_dir)
        self._log(f'rail built: {len(folders)} folders, '
                  f'{len(pages)} action pages')
        return messages

    def _check_rail(self):
        '''Folders come and go without any .toml being saved. Looked at
        on every show -- a few stat calls -- and rebuilt if that changed
        what the rail shows.'''
        if self._assemble_rail() != self._rail_shown:
            self._log('folders changed on disk')
            self.reload()

    def _apply_size(self):
        width = geometry.window_width(self._general.columns)
        height = self._general.height
        if (width, height) == (self._width, self._height):
            return
        self._width, self._height = width, height
        self.set_default_size(width, height)
        self.set_size_request(width, height)
        self.resize(width, height)
        if self.get_visible():
            self.move(*self._placement())
        self._log(f'size {width}x{height}')

    def _watch(self):
        '''Rebuild when a settings file is saved or an app is installed.

        The folder is watched, not the files: editors often save by writing
        a new file and renaming it over the old one, and a watch on the old
        file would quietly die with it.
        '''
        folder = Gio.File.new_for_path(str(self._config_dir))
        self._monitor = folder.monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.connect('changed', self._on_folder_changed)

        # Where the system keeps @XDG_DOCUMENTS_DIR and friends. GLib reads
        # it once and caches it; it is read again only when it changes,
        # since dropping the cache may leak what it handed out before.
        dirs = Gio.File.new_for_path(
            str(Path(GLib.get_user_config_dir()) / 'user-dirs.dirs'))
        self._dirs_monitor = dirs.monitor_file(Gio.FileMonitorFlags.NONE,
                                               None)
        self._dirs_monitor.connect('changed', self._on_user_dirs_changed)

        self._app_monitor = Gio.AppInfoMonitor.get()
        self._app_monitor.connect('changed', self._on_apps_changed)

    def _on_folder_changed(self, _monitor, file, other, _event):
        names = {f.get_basename() for f in (file, other) if f is not None}
        if any(name.endswith('.toml') for name in names):
            self._schedule_reload()

    def _on_user_dirs_changed(self, *_args):
        GLib.reload_user_special_dirs_cache()
        self._schedule_reload()

    def _on_apps_changed(self, _monitor):
        # An install fires this many times in a row. Reading every .desktop
        # file once per burst is enough, so it waits for the debounced reload.
        self._apps_stale = True
        self._schedule_reload()

    def _schedule_reload(self):
        if self._reload_source is not None:
            GLib.source_remove(self._reload_source)
        self._reload_source = GLib.timeout_add(config.RELOAD_DELAY_MS,
                                               self._reload_now)

    def _reload_now(self):
        self._reload_source = None
        self.reload()
        return GLib.SOURCE_REMOVE

    def _on_fontconfig_changed(self, *_args):
        # GTK rebuilds the font configuration in its own handler for this
        # signal; ours has to come after that, hence the idle callback.
        GLib.idle_add(self._reload_fonts)

    def _reload_fonts(self):
        ok = icons.reload_fonts()
        self._log('fontconfig changed, icon font loaded again'
                  if ok else 'fontconfig changed, icon font not loaded')
        self.reload()
        return GLib.SOURCE_REMOVE

    # -- searching -------------------------------------------------------

    def search(self, text):
        '''Show the window with `text` in the search field.

        Behind the `search` action, so the result list can be driven
        without a keyboard -- for testing, and for scripts later on.
        '''
        if not self.get_visible():
            self.show_kachel()
        self.searchbar.set_text(text)

    def _on_search_changed(self, text):
        if not text.strip():
            self._body.set_visible_child_name('main')
            return
        t0 = time.monotonic()
        rows = search.results(text, self._apps.apps.values())
        self.results.show_results(rows, search.header(text, rows))
        self._body.set_visible_child_name('results')
        self._log(f'search {text!r}: {len(rows)} rows in '
                  f'{(time.monotonic() - t0) * 1000:.1f} ms')

    def _on_result(self, result, timestamp):
        '''A result row was chosen: start, copy or open, then go away.'''
        if result.kind == 'app':
            problem = launch.launch_app(result.app.info, timestamp)
        elif result.kind == 'calc':
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(result.value, -1)
            # The service keeps running, so the clipboard stays filled
            # after the window is gone -- no clipboard manager needed.
            clipboard.store()
            problem = None
        else:
            problem = launch.open_uri(result.value, timestamp)
        if problem:
            self._log(f'could not run {result.title!r}: {problem}')
        else:
            self._log(f'ran {result.title!r}')
        self.hide_kachel()

    def _on_shortcut(self, shortcut, _timestamp):
        '''A shortcut button: its command, in a terminal or quietly.'''
        self._run(shortcut)

    def _on_action(self, action, _timestamp):
        '''An action on the rail -- confirmed already, if it asks.'''
        self._run(action)

    def _run(self, entry):
        '''Run what a shortcut or an action says, then go away.'''
        if entry.terminal:
            problem = launch.run_in_terminal(entry.command)
        else:
            problem = launch.launch_command(entry.command)
        if problem:
            self._log(f'could not run {entry.name!r}: {problem}')
        else:
            self._log(f'ran {entry.name!r}')
        self.hide_kachel()

    def _on_folder(self, folder, timestamp):
        '''A folder on the rail: open it in the file manager.'''
        uri = Gio.File.new_for_path(str(folder.path)).get_uri()
        problem = launch.open_uri(uri, timestamp)
        if problem:
            self._log(f'could not open {folder.path}: {problem}')
        else:
            self._log(f'opened {folder.path}')
        self.hide_kachel()

    def _on_activate(self, tile, app, timestamp):
        '''A tile was clicked: start it, then get out of the way.'''
        if tile.command:
            problem = launch.launch_command(tile.command)
        else:
            problem = launch.launch_app(app.info, timestamp)
        if problem:
            self._log(f'could not start {tile.label}: {problem}')
        else:
            self._log(f'started {tile.label}')
        self.hide_kachel()

    # -- appearance ------------------------------------------------------

    def _check_blur(self):
        '''Pick the background by whether BlurCinnamon will blur us.

        Asked on every show rather than once: the extension's settings have
        no change signal to listen to, and an entry made after login should
        not need a restart. Reading the small file costs well under a
        millisecond.
        '''
        blurred = blur.active(config.PROGRAM_CLASS)
        if blurred != self._blurred:
            self._log('blurred' if blurred else 'not blurred')
        self._blurred = blurred
        self._background = config.BG_RGBA if blurred \
            else config.BG_RGBA_NO_BLUR

    def _check_compositing(self):
        '''Catch up on a compositor that was not running at autostart.

        The visual can only be chosen while the window is unrealised, so this
        runs before showing, when the window is hidden anyway.
        '''
        if self._rgba or not self.get_screen().is_composited():
            return
        self.unrealize()
        self._rgba = self._setup_transparency()
        self.realize()
        self._log('compositor appeared, switched to the transparent pane')

    def _setup_transparency(self):
        '''Ask for an RGBA visual. Returns True if we actually got one.'''
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)
            return True
        # No compositing: paint opaque rather than leave a black rectangle.
        self._log('no RGBA visual or no compositor -- falling back to opaque')
        return False

    def _on_draw(self, _widget, cr):
        r, g, b, a = self._background

        if not self._rgba:
            # No alpha channel to work with. Rounded corners would be four
            # black wedges, so stay square and opaque.
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.set_source_rgb(r, g, b)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            return False

        # Wipe the whole surface to nothing first. Filling only the rounded
        # path would leave whatever was outside it standing -- the corners
        # have to be made transparent on purpose.
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        width = self.get_allocated_width()
        height = self.get_allocated_height()
        radius = config.CORNER_RADIUS

        # The pane, filled right out to the edge.
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.set_source_rgba(r, g, b, a)
        cr.fill()

        # The hairline, on a path of its own half a pixel further in. A one
        # pixel line is drawn centred on its path, so only there does it land
        # on one whole row of pixels instead of smearing across two.
        self._rounded_rect(cr, 0.5, 0.5, width - 1, height - 1, radius - 0.5)
        cr.set_source_rgba(*config.BORDER_RGBA)
        cr.set_line_width(1)
        cr.stroke()
        return False

    @staticmethod
    def _rounded_rect(cr, x, y, width, height, radius):
        '''A rectangle with rounded corners as the current path.'''
        radius = min(radius, width / 2, height / 2)
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()

    # -- showing and hiding ----------------------------------------------

    def toggle(self):
        '''The shortcut: show if hidden, hide if shown.'''
        since = None
        if self._focus_hidden_at is not None:
            since = (time.monotonic() - self._focus_hidden_at) * 1000
        if toggle_should_show(self.get_visible(), since):
            self.show_kachel()
        elif self.get_visible():
            self.hide_kachel()
        else:
            self._log(f'toggle {since:.0f} ms after a focus-loss hide, '
                      'taken as hide')
            self._focus_hidden_at = None

    def show_kachel(self):
        t0 = time.monotonic()
        self._focus_hidden_at = None
        self._check_compositing()
        self._check_blur()
        self._check_rail()

        # Placed on every show: on the monitor the pointer is on, which is
        # the one being looked at.
        x, y = self._placement()
        self.move(x, y)
        self.show_all()

        # A window shown from a D-Bus call has no user event behind it, so the
        # window manager may refuse it the keyboard to prevent focus stealing.
        # A fresh server timestamp is what makes the request legitimate.
        ts = self._server_time()
        self.present_with_time(ts)
        gdk_window = self.get_window()
        if gdk_window is not None:
            gdk_window.focus(ts)
        # Typing starts at once, without a click into the field first.
        self.searchbar.focus()

        self._log(f'shown in {(time.monotonic() - t0) * 1000:.1f} ms '
                  f'at ({x}, {y})')

    def hide_kachel(self):
        self.reset()
        self.hide()
        self._log('hidden')

    def reset(self):
        '''Back to the state the next show should start from: an empty
        search field, the main view, the first action page and nothing
        armed. (Later also: no pills.)'''
        self.searchbar.reset()
        self.wall.reset_hover()
        self.rail.reset()
        self._body.set_visible_child_name('main')

    def _placement(self):
        '''Centred in the work area of the monitor under the pointer.'''
        display = Gdk.Display.get_default()
        monitor = None
        seat = display.get_default_seat()
        pointer = seat.get_pointer() if seat is not None else None
        if pointer is not None:
            _screen, px, py = pointer.get_position()
            monitor = display.get_monitor_at_point(px, py)
        if monitor is None:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        area = monitor.get_workarea()
        return geometry.centered(area.x, area.y, area.width, area.height,
                                 self._width, self._height)

    def _server_time(self):
        gdk_window = self.get_window()
        if GdkX11 is not None and gdk_window is not None:
            try:
                return GdkX11.x11_get_server_time(gdk_window)
            except Exception:  # not an X11 window
                pass
        return Gdk.CURRENT_TIME

    # -- input -----------------------------------------------------------

    def _on_key_press(self, _widget, event):
        '''Keys for the search, taken before the input field sees them.

        Esc hides, always. F7 is deliberately not handled here: the global
        shortcut is a passive grab on the root window, so that key press
        never reaches us -- both directions run through the toggle action.
        '''
        key = event.keyval
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if key == Gdk.KEY_Escape:
            self.hide_kachel()
            return True
        if ctrl and key == Gdk.KEY_BackSpace:
            # Instead of the field's own "delete a word": everything goes,
            # back to the wall.
            self.searchbar.clear()
            return True

        if self._body.get_visible_child_name() != 'results':
            return False
        if key in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            self.results.move(1)
            return True
        if key in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            self.results.move(-1)
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            self.results.activate_selected(event.time)
            return True
        if ctrl and Gdk.KEY_1 <= key <= Gdk.KEY_9:
            self.results.activate(key - Gdk.KEY_1, event.time)
            return True
        if ctrl and Gdk.KEY_KP_1 <= key <= Gdk.KEY_KP_9:
            self.results.activate(key - Gdk.KEY_KP_1, event.time)
            return True
        return False

    def _on_focus_out(self, _widget, _event):
        '''Lost the keyboard: a click elsewhere, Alt+Tab, another window.'''
        if self.get_visible():
            self.hide_kachel()
            self._focus_hidden_at = time.monotonic()
            self._log('hidden on focus loss')
        return False

    # -- misc ------------------------------------------------------------

    def _log(self, message):
        if self._verbose:
            print(f"[kachel] {time.strftime('%H:%M:%S')} window: {message}",
                  flush=True)
