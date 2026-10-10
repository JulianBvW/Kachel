'''The application object: one instance, reachable over the session bus.'''

import signal
import time

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import config  # noqa: E402
from .window import KachelWindow  # noqa: E402


class KachelApplication(Gtk.Application):
    '''Runs from login to logout and does nothing most of the time.

    Actions registered here are exported on the session bus automatically,
    which is what lets the keyboard shortcut reach us without starting a
    second Python interpreter:

        gapplication action io.github.julianbvw.Kachel toggle
    '''

    def __init__(self, verbose=False):
        super().__init__(
            application_id=config.APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._verbose = verbose
        self.window = None

    # -- lifecycle -------------------------------------------------------

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Keep running with no window on screen. Without this the application
        # would be free to quit the moment we hide, and the next key press
        # would pay for a cold start.
        self.hold()

        self.window = KachelWindow(verbose=self._verbose)
        self.add_window(self.window)

        for name, handler in (
            ('toggle', lambda *_: self.window.toggle()),
            ('show', lambda *_: self.window.show_kachel()),
            ('hide', lambda *_: self.window.hide_kachel()),
            ('quit', lambda *_: self.quit()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', self._timed(name, handler))
            self.add_action(action)

        # Logging out sends SIGTERM, and Python would die on the spot. Routed
        # through the main loop instead, so the exit is an orderly one.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             self._on_sigterm)

        self._log('ready')

    def _on_sigterm(self):
        self._log('SIGTERM')
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if '--daemon' in args:
            # Started from autostart: be there, but stay out of the way.
            self._log('started in daemon mode')
        else:
            self.window.toggle()
        return 0

    def do_activate(self):
        # Reached when something activates us without a command line.
        self.window.toggle()

    # -- misc ------------------------------------------------------------

    def _timed(self, name, handler):
        '''Wrap an action so --verbose can show how long it took.'''
        def wrapper(*args):
            t0 = time.monotonic()
            handler(*args)
            # Double quotes here: the message itself contains apostrophes.
            self._log(f"action '{name}' handled in "
                      f'{(time.monotonic() - t0) * 1000:.1f} ms')
        return wrapper

    def _log(self, message):
        if self._verbose:
            print(f"[kachel] {time.strftime('%H:%M:%S')} app: {message}",
                  flush=True)
