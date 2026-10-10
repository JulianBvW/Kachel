'''Entry point.

Run it from the repository:

    /usr/bin/python3 -m kachel --daemon         the resident service
    /usr/bin/python3 -m kachel --list-apps      app IDs, for tiles.toml
    /usr/bin/python3 -m kachel --grid           where every tile ended up,
                                                and what the rail shows

`--config DIR` reads the settings from DIR instead of ~/.config/kachel.

Note the interpreter. A plain `python3` may well be a conda or miniforge
build, and those do not ship the `gi` bindings -- the failure looks like
`ModuleNotFoundError: No module named 'gi'` and has nothing to do with Kachel.
'''

import sys
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib  # noqa: E402


def config_dir(argv):
    '''The folder after --config, or None for the default.'''
    if '--config' in argv:
        index = argv.index('--config')
        if index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser()
        sys.exit('--config needs a folder')
    return None


def list_apps():
    from .apps import AppIndex
    apps = AppIndex().visible()
    width = max((len(app.id) for app in apps), default=0)
    for app in apps:
        print(f'{app.id:<{width}}  {app.name}')
    return 0


def grid(folder):
    '''The wall as text, read the same way the window reads it.'''
    from . import config, gridtext, railmodel, settings
    from .apps import AppIndex
    folder = folder or config.CONFIG_DIR
    wall, messages = settings.load_tiles(folder)
    if wall is None:
        wall = settings.Wall()
    general, more = settings.load_general(folder)
    messages = more + messages
    groups, more = settings.assemble(wall, AppIndex().resolve)
    messages += more
    height = (general or settings.General()).height
    rail, more = settings.load_rail(folder)
    messages += more
    folders, pages, more = railmodel.assemble(
        rail or settings.default_rail(), railmodel.special_dir, Path.home(),
        height)
    print(gridtext.render(groups, messages + more, (folders, pages)), end='')
    return 0


def main(argv=None):
    argv = sys.argv if argv is None else argv

    # Answered here and now, without a window and without reaching a
    # running instance.
    if '--list-apps' in argv:
        return list_apps()
    if '--grid' in argv:
        return grid(config_dir(argv))

    # Both of these decide our WM_CLASS, and they have to be set before the
    # first window exists. BlurCinnamon identifies the window by it, so
    # getting this wrong shows up as "the blur just does not happen".
    from . import config, icons
    GLib.set_prgname(config.PRG_NAME)
    Gdk.set_program_class(config.PROGRAM_CLASS)

    # The icon font has to be known before Pango first lists the fonts.
    if not icons.load_fonts():
        print('kachel: could not load the bundled icon font, '
              'using theme icons instead', file=sys.stderr)

    from .application import KachelApplication
    app = KachelApplication(config_dir=config_dir(argv),
                            verbose='--verbose' in argv)
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())
