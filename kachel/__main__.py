'''Entry point.

Run it from the repository:

    /usr/bin/python3 -m kachel --daemon

Note the interpreter. A plain `python3` may well be a conda or miniforge
build, and those do not ship the `gi` bindings -- the failure looks like
`ModuleNotFoundError: No module named 'gi'` and has nothing to do with Kachel.
'''

import sys

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib  # noqa: E402


def main(argv=None):
    argv = sys.argv if argv is None else argv

    # Both of these decide our WM_CLASS, and they have to be set before the
    # first window exists. BlurCinnamon identifies the window by it, so
    # getting this wrong shows up as "the blur just does not happen".
    from . import config
    GLib.set_prgname(config.PRG_NAME)
    Gdk.set_program_class(config.PROGRAM_CLASS)

    from .application import KachelApplication
    app = KachelApplication(verbose='--verbose' in argv)
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())
