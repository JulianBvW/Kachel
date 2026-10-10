'''Starting things: an app from its .desktop entry, or a command line.'''

from pathlib import Path

import gi

gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, GLib  # noqa: E402


def launch_app(info, timestamp):
    '''Start a Gio.DesktopAppInfo. Returns None, or what went wrong.

    The launch context carries the timestamp of the click, which is what
    lets the window manager hand the new window the focus instead of
    treating it as an intruder.
    '''
    context = Gdk.Display.get_default().get_app_launch_context()
    context.set_timestamp(timestamp)
    try:
        info.launch([], context)
    except GLib.Error as error:
        return error.message
    return None


def launch_command(command):
    '''Run a command line through the shell, detached. None or the error.

    Through /bin/sh so that `~`, `;` and `&&` work the way they do when
    typed. GLib reaps the child itself, so nothing is left behind as a
    zombie in a process that runs all session.
    '''
    try:
        GLib.spawn_async(['/bin/sh', '-c', command],
                         working_directory=str(Path.home()))
    except GLib.Error as error:
        return error.message
    return None


def open_uri(uri, timestamp):
    '''Open a web address in the default browser. None or the error.'''
    context = Gdk.Display.get_default().get_app_launch_context()
    context.set_timestamp(timestamp)
    try:
        Gio.AppInfo.launch_default_for_uri(uri, context)
    except GLib.Error as error:
        return error.message
    return None
