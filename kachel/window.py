'''The window itself: a pane of dark glass in the middle of the screen.'''

import math
import os
import shlex
import time
from pathlib import Path

import cairo
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import (anim, blur, cinnamon, config, files, geometry,  # noqa: E402
               icons, launch, listmodel, query, railmodel, search, settings,
               style, tldr, tomledit)
from .applist import AppList  # noqa: E402
from .apps import AppIndex  # noqa: E402
from .contextmenu import ContextMenu, is_right_click  # noqa: E402
from .filesearch import FileSearch, Recent  # noqa: E402
from .menumodel import Target, menu_for  # noqa: E402
from .rail import Rail  # noqa: E402
from .results import ResultList  # noqa: E402
from .searchbar import SearchBar  # noqa: E402
from .slide import Slider  # noqa: E402
from .suggest import Suggestions  # noqa: E402
from .tilewall import TileWall  # noqa: E402
from .tldrview import TldrView  # noqa: E402
from .tooltip import Tooltip  # noqa: E402
from .wallfile import WallFile  # noqa: E402

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
        self._recent = Recent()
        self._files = FileSearch(on_done=self._on_files, verbose=verbose)
        self._file_source = None   # the pause before plocate starts
        self._file_query = ('', (), ())   # text, recent hits shown, extras
        self._tldr = tldr.TldrStore(on_ready=self._on_tldr_ready,
                                    call_soon=GLib.idle_add)
        self._general = settings.General()
        self._wall_settings = settings.Wall()
        self._wallfile = WallFile(self._config_dir)
        self._groups = []          # as assembled: [(name, [Placement])]
        self._pinned = {}          # app ID -> group it is on the wall in
        self._menu_what = None     # what the open menu is about
        self._rail_settings = settings.default_rail()
        self._rail_shown = None   # (folders, pages, messages) on the rail
        self._build_body()

        written, self._setup_problems = settings.ensure_files(
            self._config_dir)
        for path in written:
            self._log(f'wrote the skeleton {path}')
        self._reload_source = None
        self._reload_only_if_changed = False
        self._read_text = None
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
                                   on_close=self.hide_kachel,
                                   on_list=self._on_list_button,
                                   on_word=self._on_word)
        root.pack_start(self.searchbar, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.tooltip = Tooltip()
        self.rail = Rail(on_folder=self._on_folder, on_action=self._on_action,
                         tooltip=self.tooltip)
        # Right-click anywhere on the rail, entries included: the rail's
        # menu. An input-only window, so that the empty part catches it.
        rail_box = Gtk.EventBox()
        rail_box.set_visible_window(False)
        rail_box.add(self.rail)
        rail_box.connect('button-press-event', self._rail_pressed)
        main.pack_start(rail_box, False, False, 0)
        self.wall = TileWall(on_activate=self._on_activate,
                             on_shortcut=self._on_shortcut,
                             on_menu=self._open_menu,
                             on_move=self._on_tile_moved)
        self.applist = AppList(
            on_activate=self._on_list_app,
            on_menu=lambda app, event: self._open_menu(('app', app), event))
        # The wall and the app list slide past each other (Design §10);
        # the rail and the search bar stay put. Sized in _apply_size.
        self.pages = Slider(1, 1, duration=440)
        self.pages.set_pages([self.wall, self.applist])
        self.pages.on_page_changed = \
            lambda page: self.searchbar.set_list_active(page == 1)
        main.pack_start(self.pages, True, True, 0)
        overlay = Gtk.Overlay()
        overlay.add(main)
        overlay.add_overlay(self.tooltip)
        # Over the wall, but never in its way: the tile under the tooltip
        # keeps its hover and its clicks.
        overlay.set_overlay_pass_through(self.tooltip, True)

        self.results = ResultList(
            on_activate=self._on_result,
            on_menu=lambda result, event, row: self._open_menu(
                ('result', result), event, row))
        self.tldrview = TldrView(on_copy=self._on_tldr_copy)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(self.results, f'set_margin_{side}')(10)
            getattr(self.tldrview, f'set_margin_{side}')(10)

        # No transition: switching is a redraw, not an animation to wait for.
        self._body = Gtk.Stack()
        self._body.set_transition_type(Gtk.StackTransitionType.NONE)
        self._body.add_named(overlay, 'main')
        self._body.add_named(self.results, 'results')
        self._body.add_named(self.tldrview, 'tldr')
        root.pack_start(self._body, True, True, 0)

        # The @ suggestions float over everything below the search bar.
        self.suggestions = Suggestions(on_pick=self._on_pick)
        top = Gtk.Overlay()
        top.add(root)
        top.add_overlay(self.suggestions)
        self._top = top
        self.menu = ContextMenu(top, on_pick=self._on_menu_pick,
                                on_close=self.searchbar.focus)
        self.add(top)
        # Shown now, so mapping the window later is all it takes.
        top.show_all()

    def reload(self):
        '''Read the settings and rebuild the wall.

        A file that is not TOML at all keeps what was there before; its
        complaint goes into the message line. Everything else counts as far
        as it is right, and what is wrong is reported.
        '''
        t0 = time.monotonic()
        before = self._settings_text()
        if self._apps_stale:
            self._apps.reload()
            self._apps_stale = False
        general, messages = settings.load_general(self._config_dir)
        messages = self._setup_problems + messages
        if general is not None:
            self._general = general
        self._apply_animations()
        wall, more, text = settings.load_tiles(self._config_dir,
                                               with_text=True)
        messages += more
        if wall is not None:
            self._wall_settings = wall
            self._wallfile.remember(text)

        rail, more = settings.load_rail(self._config_dir)
        messages += more
        if rail is not None:
            self._rail_settings = rail

        groups, more = settings.assemble(self._wall_settings,
                                         self._apps.resolve)
        messages += more

        self._apply_size()
        messages += self._build_rail()
        t1 = time.monotonic()
        visible = self._apps.visible()
        self._groups = groups
        self._pinned = listmodel.pinned_groups(groups)
        self.applist.show_apps(visible, self._pinned)
        self._log(f'app list built: {len(visible)} apps, '
                  f'{(time.monotonic() - t1) * 1000:.1f} ms')
        area = self._width - config.RAIL_WIDTH
        self.wall.show_wall(groups, self._apps, messages, area,
                            self._general.columns, self._config_dir)

        count = sum(len(p) for _name, p in groups)
        self._log(f'wall built: {len(groups)} groups, {count} tiles, '
                  f'{len(messages)} messages, '
                  f'{(time.monotonic() - t0) * 1000:.1f} ms')
        for message in messages:
            self._log(f'  {message}')
        # What was read, for skipping the watcher's echo of this very
        # state; unsure if a file changed while it was being read.
        after = self._settings_text()
        self._read_text = before if before == after else None

    def _apply_animations(self):
        '''`animations` from kachel.toml, or Cinnamon's desktop effects.'''
        on = anim.resolve(self._general.animations,
                          getattr(self, '_effects_settings', None))
        if on != anim.enabled():
            anim.set_enabled(on)
            self._style.refresh()
            self._log(f'animations {"on" if on else "off"}')

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
        self.pages.resize(width - config.RAIL_WIDTH,
                          height - config.SEARCHBAR_HEIGHT)
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

        # animations = "system" follows Cinnamon's desktop effects, also
        # when they are switched while Kachel runs.
        self._effects_settings = anim.system_settings()
        if self._effects_settings is not None:
            self._effects_settings.connect(
                'changed::desktop-effects',
                lambda *_: self._apply_animations())

        self._app_monitor = Gio.AppInfoMonitor.get()
        self._app_monitor.connect('changed', self._on_apps_changed)

    def _on_folder_changed(self, _monitor, file, other, _event):
        names = {f.get_basename() for f in (file, other) if f is not None}
        if any(name.endswith('.toml') for name in names):
            self._schedule_reload(only_if_changed=True)

    def _on_user_dirs_changed(self, *_args):
        GLib.reload_user_special_dirs_cache()
        self._schedule_reload()

    def _on_apps_changed(self, _monitor):
        # An install fires this many times in a row. Reading every .desktop
        # file once per burst is enough, so it waits for the debounced reload.
        self._apps_stale = True
        self._schedule_reload()

    def _schedule_reload(self, only_if_changed=False):
        '''Reload after a pause. `only_if_changed`: skip it if the settings
        files read exactly as at the last reload -- the watcher also sees
        Kachel's own writes, which were reloaded at once.'''
        if self._reload_source is not None:
            GLib.source_remove(self._reload_source)
            # A pending reload for another reason must still happen.
            only_if_changed = only_if_changed and self._reload_only_if_changed
        self._reload_only_if_changed = only_if_changed
        self._reload_source = GLib.timeout_add(config.RELOAD_DELAY_MS,
                                               self._reload_now)

    def _reload_now(self):
        self._reload_source = None
        if self._reload_only_if_changed and not self._apps_stale \
                and self._settings_text() == self._read_text:
            return GLib.SOURCE_REMOVE
        self.reload()
        return GLib.SOURCE_REMOVE

    def _settings_text(self):
        '''The three settings files as they are now (None: missing).'''
        found = []
        for name in (config.GENERAL_FILE, config.TILES_FILE,
                     config.RAIL_FILE):
            try:
                found.append((Path(self._config_dir) / name).read_bytes())
            except OSError:
                found.append(None)
        return tuple(found)

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

    def _on_search_changed(self, text, scope=None, extras=()):
        self._stop_files()
        if not text.strip() and scope is None:
            self._body.set_visible_child_name('main')
            return
        t0 = time.monotonic()
        code = scope.code if scope else None
        if code == 'f':
            self._search_files(text, extras)
            return
        if code == 'tldr':
            self._search_tldr(text)
            return
        # The sorted list is only needed for @a with nothing typed.
        listed = self._apps.visible() if code == 'a' and not text.strip() \
            else ()
        recent = self._recent.hits() if code is None else ()
        rows = search.results(text, self._apps.apps.values(), code,
                              listed=listed, recent=recent)
        self.results.show_results(rows, search.header(text, rows, code))
        self._body.set_visible_child_name('results')
        self._log(f'search {text!r}: {len(rows)} rows in '
                  f'{(time.monotonic() - t0) * 1000:.1f} ms')

    # -- files -----------------------------------------------------------

    FILE_PAUSE_MS = 120

    def _search_files(self, text, extras):
        '''@f: the recent files that fit at once, plocate after a pause.

        With neither words nor a type, only the recent files: a date bound
        alone would have every file on the disk looked at.'''
        words = files.words_of(text)
        types = [e.value for e in extras if e.kind == 'type']
        before = next((e.period for e in reversed(extras)
                       if e.kind == 'before'), None)
        after = next((e.period for e in reversed(extras)
                      if e.kind == 'after'), None)
        recent = [hit for hit in self._recent.hits()
                  if files.matches(hit.path, words)
                  and files.has_type(hit.path, types)
                  and files.date_ok(hit.mtime, before, after)]
        if not words and not types:
            rows = [search.file_row(hit) for hit in recent]
            self.results.show_results(rows, search.file_header(
                '', len(rows), recent_only=True))
            self._body.set_visible_child_name('results')
            return
        # The recent ones in the same order as everything else: a name
        # that fits before a path that does.
        recent = files.rank(recent, words, Path.home())
        rows = [search.file_row(hit) for hit in recent]
        self._file_query = (text, recent, extras)
        self.results.show_results(rows, search.file_header(text, 0,
                                                           running=True))
        self._body.set_visible_child_name('results')
        excluder = files.Excluder(self._general.exclude,
                                  self._general.exclude_names)

        def start():
            self._file_source = None
            self._files.start(text.split(), words, types, before, after,
                              excluder, Path.home())
            return GLib.SOURCE_REMOVE
        self._file_source = GLib.timeout_add(self.FILE_PAUSE_MS, start)

    def _stop_files(self):
        if self._file_source is not None:
            GLib.source_remove(self._file_source)
            self._file_source = None
        self._files.cancel()

    def _on_files(self, hits, truncated, problem):
        '''plocate has answered the latest search.'''
        text, recent, _extras = self._file_query
        if problem:
            # Keep the recent ones that were shown; say what is missing.
            rows = [search.file_row(hit) for hit in recent]
            rows.append(search.Result('problem', problem, ''))
            self.results.show_results(rows, problem)
            return
        seen = {hit.path for hit in recent}
        words = files.words_of(text)
        merged = files.rank(
            list(recent) + [hit for hit in hits if hit.path not in seen],
            words, Path.home())
        rows = [search.file_row(hit) for hit in merged]
        self.results.show_results(rows, search.file_header(
            text, len(rows), truncated=truncated))
        self._log(f'files {text!r}: {len(rows)} rows')

    # -- tldr ------------------------------------------------------------

    def _search_tldr(self, text):
        '''@tldr: the page when the name is exact, else the names that fit.
        The pages are fetched the first time, so the pill alone starts it.'''
        store = self._tldr
        store.ensure()
        rows, header = [], 'Befehl eingeben'
        if store.ready and text.strip():
            page = store.page(tldr.page_name(text))
            if page is not None:
                self.tldrview.show_page(page)
                self._body.set_visible_child_name('tldr')
                return
            rows = [search.Result('tldr', name, store.description(name),
                                  value=name)
                    for name in tldr.matches(text, store.names())]
            header = search.tldr_header(text, len(rows))
        elif not store.ready and store.busy:
            header = 'tldr-Seiten werden geladen…'
        elif not store.ready and store.problem:
            rows = [search.Result('problem', store.problem, '')]
            header = 'tldr'
        self.results.show_results(rows, header)
        self._body.set_visible_child_name('results')

    def _on_tldr_ready(self):
        '''The pages are there, or will not come: ask again.'''
        scope = self.searchbar.scope
        if self.get_visible() and scope is not None and scope.code == 'tldr':
            self._search_tldr(self.searchbar.text)

    def _on_tldr_copy(self, text, _timestamp):
        self._copy(text)
        self._done(text, None)

    def _on_word(self, word):
        '''The word at the cursor changed: offer scopes for an @word,
        and with @f its extra pills.'''
        self.suggestions.show_for(query.suggestions(word,
                                                    self.searchbar.scope))

    def _on_pick(self, scope):
        self.suggestions.hide_list()
        self.searchbar.complete(scope)
        self.searchbar.focus()

    def show_list(self, shown):
        '''Slide the app list in, or the wall back. The switch in the
        search bar follows through pages.on_page_changed.'''
        self.wall.cancel_move()
        self.pages.show_page(1 if shown else 0)
        self._log('app list shown' if shown else 'wall shown')

    def _on_list_button(self):
        if self.searchbar.text or self.searchbar.scope:
            # From the results straight to the list: the switch says
            # "show me everything", so the search goes.
            self.searchbar.clear()
            self.show_list(True)
        else:
            self.show_list(self.pages.page == 0)

    def _on_list_app(self, app, timestamp):
        self._done(app.name, launch.launch_app(app.info, timestamp))

    # -- the right-click menu ---------------------------------------------

    def _open_menu(self, what, event=None, widget=None):
        '''what: ('tile', tile, app), ('app', app), ('result', result) or
        ('wall',) or ('rail',). At the pointer for a click, at `widget`
        for a key.'''
        target = self._target(what)
        if target is None:
            return
        if event is not None:
            _ok, ox, oy = self._top.get_window().get_origin()
            x, y = int(event.x_root - ox), int(event.y_root - oy)
        else:
            found = widget.translate_coordinates(
                self._top, 24, widget.get_allocated_height())
            x, y = found if found else (24, 24)
        self.tooltip.hide_now()
        self.suggestions.hide_list()
        self._menu_what = what
        self.menu.open(menu_for(target), x, y)

    def _rail_pressed(self, _box, event):
        if self.wall.moving:
            # A tile in hand goes back. A right click does only that, as on
            # the wall; a left click then does what it always does.
            self.wall.cancel_move()
            return is_right_click(event)
        if is_right_click(event):
            self._open_menu(('rail',), event)
            return True
        return False

    def _target(self, what):
        '''Gather the facts menu_for needs.'''
        groups = tuple(self._wall_settings.groups)
        kind = what[0]
        if kind in ('wall', 'rail'):
            return Target(kind)
        if kind == 'result':
            result = what[1]
            if result.kind == 'file':
                return Target('file', folder=result.folder,
                              openers=launch.openers(result.value,
                                                     result.folder))
            if result.kind != 'app':
                return None
            what, kind = ('app', result.app), 'app'
        if kind == 'tile':
            tile, app = what[1], what[2]
            target = Target('tile', tile_group=tile.group,
                            tile_size=tile.size, groups=groups)
        else:
            app = what[1]
            target = Target('app', groups=groups,
                            pinned_in=self._pinned.get(app.id))
        if app is not None:
            info = app.info
            target.app_id = app.id
            target.actions = tuple((a, info.get_action_name(a))
                                   for a in info.list_actions())
            target.in_panel = cinnamon.in_panel(info)
            target.on_desktop = cinnamon.on_desktop(info)
            target.favorite = cinnamon.is_favorite(app.id)
            target.can_uninstall = cinnamon.can_uninstall(info)
        return target

    def _menu_app(self):
        what = self._menu_what
        if what[0] == 'tile':
            return what[2]
        if what[0] == 'result':
            return what[1].app
        return what[1]

    def _tile_lines(self):
        '''The header lines the menu is about: the clicked tile, or for an
        app every tile of it on the wall -- the lowest first, so removing
        one leaves the lines above it where they are.'''
        what = self._menu_what
        if what[0] == 'tile':
            return [what[1].line]
        app = self._menu_app()
        return sorted((placement.tile.line for _name, placements in
                       self._groups for placement in placements
                       if placement.tile.app == app.id), reverse=True)

    def _edit(self, *operations):
        '''Change tiles.toml; the folder watcher then rebuilds the wall.'''
        self.menu.close()
        problem = self._wallfile.change(*operations)
        if problem:
            self._log(problem)
            self.reload()             # the file may have changed meanwhile
            self.wall.notice(problem)
        else:
            # At once, not after the watcher's pause: a moved tile glides
            # from where it was put down. (The watcher's own reload follows
            # and finds the same wall.)
            self.reload()

    def _on_menu_pick(self, entry, payload):
        what = self._menu_what
        timestamp = Gtk.get_current_event_time()
        id = entry.id
        if what is None:
            return
        if what[0] == 'result' and what[1].kind == 'file':
            self._file_menu(id, what[1], payload, timestamp)
            return
        if id == 'edit-toml':
            self.menu.close()
            self._done(payload, launch.edit_file(
                self._config_dir / payload, None, timestamp))
            return
        if id == 'config-folder':
            self.menu.close()
            self._done('the settings folder', launch.open_path(
                str(self._config_dir), timestamp))
            return

        app = self._menu_app()
        lines = self._tile_lines()
        line = lines[0] if lines else None
        if id in ('pin', 'pin-new'):
            # Without '.desktop', as people write it by hand.
            ops = [(tomledit.add_tile, payload,
                    app.id.removesuffix('.desktop'))]
            if id == 'pin-new' and payload not in self._wall_settings.groups:
                ops.append((tomledit.add_group, payload))
            self._edit(*ops)
        elif id in ('group', 'group-new'):
            ops = [(tomledit.set_group, line, payload)]
            if id == 'group-new' and payload not in self._wall_settings.groups:
                ops.append((tomledit.add_group, payload))
            self._edit(*ops)
        elif id == 'size':
            self._edit((tomledit.set_size, line, payload))
        elif id == 'move':
            self.menu.close()
            self.wall.start_move(what[1])
        elif id == 'unpin':
            if not lines:
                self.menu.close()
                self._report('diese App ist nicht auf der Wand')
                return
            self._edit(*[(tomledit.remove_tile, n) for n in lines])
        elif id == 'action':
            self.menu.close()
            self._done(app.name, launch.launch_action(app.info, payload,
                                                      timestamp))
        elif id == 'panel':
            self.menu.close()
            cinnamon.add_to_panel(app.info, self._report)
        elif id == 'desktop':
            self.menu.close()
            self._report(cinnamon.add_to_desktop(app.info))
        elif id in ('favorite', 'unfavorite'):
            self.menu.close()
            self._report(cinnamon.set_favorite(app.id, id == 'favorite'))
        elif id == 'uninstall':
            self.menu.close()
            self._done(app.name, cinnamon.uninstall(app.info))

    def _on_tile_moved(self, tile, spot):
        '''A tile picked up with "Verschieben" was put down elsewhere: by
        a new order, or by `pos` (and the tiles in its way lose theirs).'''
        if spot.pos is None:
            before = spot.before.line if spot.before is not None else None
            self._edit((tomledit.move_tile, tile.line, before))
            return
        changes = [(tile.line, spot.pos)] + [(t.line, None)
                                              for t in spot.loosen]
        # From the bottom up: a line added or dropped in one tile leaves
        # the line numbers of the tiles above it as they are.
        changes.sort(reverse=True, key=lambda change: change[0])
        self._edit(*[(tomledit.set_pos, line, pos) for line, pos in changes])

    def _file_menu(self, id, result, payload, timestamp):
        path = result.value
        if id == 'trash':
            self.menu.close()
            try:
                Gio.File.new_for_path(path).trash(None)
            except GLib.Error as error:
                self._report(f'Papierkorb ging nicht: {error.message}')
                return
            self._log(f'trashed {path}')
            self._recent.forget(path)
            # The search again, so the row is gone.
            self._on_search_changed(self.searchbar.text,
                                    self.searchbar.scope,
                                    self.searchbar.extras)
            return
        self.menu.close()
        if id == 'open-with':
            self._done(result.title, launch.open_with(payload, path,
                                                      timestamp))
        elif id == 'reveal':
            self._done(result.title, launch.show_in_folder(path, timestamp))
        elif id == 'copy-path':
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(path, -1)
            clipboard.store()
            self._done(result.title, None)
        elif id == 'terminal':
            folder = path if result.folder else os.path.dirname(path)
            self._done(result.title, launch.run_in_terminal(
                f'cd {shlex.quote(folder)}'))

    def _report(self, message):
        '''A short note for the user, when something did not quite work.'''
        if message:
            self._log(message)
            self.wall.notice(message)
            app = self.get_application()
            if app is not None and not self.get_visible():
                notification = Gio.Notification.new('Kachel')
                notification.set_body(message)
                app.send_notification(None, notification)

    def _done(self, what, problem):
        '''After anything was started, copied or opened: say how it went,
        then get out of the way.'''
        if problem:
            self._log(f'could not run {what!r}: {problem}')
        else:
            self._log(f'ran {what!r}')
        self.hide_kachel()

    def _on_result(self, result, timestamp, reveal=False):
        '''A result row was chosen: start, copy or open, then go away.
        `reveal` (Ctrl): show a file in its folder instead.'''
        if result.kind == 'problem':
            return   # a calculation that does not work: nothing to run
        if result.kind == 'file':
            problem = launch.show_in_folder(result.value, timestamp) \
                if reveal else launch.open_path(result.value, timestamp)
        elif result.kind == 'app':
            problem = launch.launch_app(result.app.info, timestamp)
        elif result.kind == 'tldr':
            # A command's name: its page, in place of the list.
            self.searchbar.set_text(result.value)
            return
        elif result.kind == 'calc':
            self._copy(result.value)
            problem = None
        else:
            problem = launch.open_uri(result.value, timestamp)
        self._done(result.title, problem)

    @staticmethod
    def _copy(text):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
        # The service keeps running, so the clipboard stays filled after
        # the window is gone -- no clipboard manager needed.
        clipboard.store()

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
        self._done(entry.name, problem)

    def _on_folder(self, folder, timestamp):
        '''A folder on the rail: open it in the file manager.'''
        uri = Gio.File.new_for_path(str(folder.path)).get_uri()
        self._done(str(folder.path), launch.open_uri(uri, timestamp))

    def _on_activate(self, tile, app, timestamp):
        '''A tile was clicked: start it, then get out of the way.'''
        if tile.command:
            problem = launch.launch_command(tile.command)
        else:
            problem = launch.launch_app(app.info, timestamp)
        self._done(tile.label, problem)

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
        search field, the main view with the wall (not the app list), the
        first action page and nothing armed. No pill, no suggestions.'''
        self._stop_files()
        self.menu.close()
        self.wall.cancel_move()
        self.searchbar.reset()
        self.suggestions.hide_list()
        self.wall.reset_hover()
        self.wall.scroll_to_top()
        self.rail.reset()
        self.pages.show_page(0, animate=False)
        self.applist.reset()
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

        Esc hides, always. The shortcut is deliberately not handled here:
        it is a passive grab on the root window, so that key press never
        reaches us -- both directions run through the toggle action.
        '''
        key = event.keyval
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if self.menu.shown:
            # The menu first: Esc closes only the menu (its "new group"
            # field must be able to cancel). Other keys belong to that
            # field if it is there, and to nobody otherwise -- typing must
            # not change the search under an open menu.
            if key == Gdk.KEY_Escape:
                self.menu.close()
                return True
            return not self.menu.typing
        if self.wall.moving and not event.is_modifier:
            # A tile in hand: Esc puts it back and nothing else. Any other
            # key puts it back too, and then does what it always does.
            self.wall.cancel_move()
            if key == Gdk.KEY_Escape:
                return True
        if key == Gdk.KEY_Escape:
            self.hide_kachel()
            return True
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        if (key == Gdk.KEY_Menu or (shift and key == Gdk.KEY_F10)) \
                and self._body.get_visible_child_name() == 'results':
            self.results.menu_for_selected()
            return True
        if event.state & Gdk.ModifierType.MOD1_MASK \
                and key == Gdk.KEY_BackSpace:
            # Alt: everything goes, back to the wall or the app list,
            # whichever was showing. Ctrl+Backspace is the field's own
            # "delete a word", as everywhere else.
            self.searchbar.clear()
            return True

        if self.suggestions.shown:
            # While @ suggestions are open, the arrows and Tab/Enter are
            # theirs.
            if key in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
                self.suggestions.move(1)
                return True
            if key in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
                self.suggestions.move(-1)
                return True
            if key in (Gdk.KEY_Tab, Gdk.KEY_Return, Gdk.KEY_KP_Enter,
                       Gdk.KEY_ISO_Enter):
                self.suggestions.pick_selected()
                return True
        if key in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab) \
                and (self.searchbar.text or self.searchbar.scope):
            return True   # mid-search, Tab must not wander off the field

        # The result list, or a tldr page in its place: the same keys.
        view = {'results': self.results, 'tldr': self.tldrview}.get(
            self._body.get_visible_child_name())
        if view is None:
            return False
        if key in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            view.move(1)
            return True
        if key in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            view.move(-1)
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            view.activate_selected(event.time, reveal=ctrl)
            return True
        if ctrl and Gdk.KEY_1 <= key <= Gdk.KEY_9:
            view.activate(key - Gdk.KEY_1, event.time)
            return True
        if ctrl and Gdk.KEY_KP_1 <= key <= Gdk.KEY_KP_9:
            view.activate(key - Gdk.KEY_KP_1, event.time)
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
