'''Starting things: an app from its .desktop entry, or a command line.'''

import shlex
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


def _context(timestamp):
    context = Gdk.Display.get_default().get_app_launch_context()
    context.set_timestamp(timestamp)
    return context


def launch_action(info, action, timestamp):
    '''One of the actions in an app's .desktop file ("New Window").'''
    try:
        info.launch_action(action, _context(timestamp))
    except GLib.Error as error:
        return error.message
    return None


def open_with(app_id, path, timestamp):
    '''Open `path` with the app `app_id` instead of the default one.'''
    info = Gio.DesktopAppInfo.new(app_id)
    if info is None:
        return f'{app_id} gibt es nicht'
    try:
        info.launch([Gio.File.new_for_path(path)], _context(timestamp))
    except GLib.Error as error:
        return error.message
    return None


def openers(path, folder=False):
    '''((app ID, name), ...) that can open `path`, the default first.'''
    if folder:
        content_type = 'inode/directory'
    else:
        try:
            content_type = Gio.File.new_for_path(path).query_info(
                'standard::content-type', Gio.FileQueryInfoFlags.NONE,
                None).get_content_type()
        except GLib.Error:
            content_type, _uncertain = Gio.content_type_guess(path, None)
    default = Gio.AppInfo.get_default_for_type(content_type, False)
    found = [default] if default else []
    for info in Gio.AppInfo.get_recommended_for_type(content_type):
        if not any(info.get_id() == f.get_id() for f in found):
            found.append(info)
    return tuple((info.get_id(), info.get_display_name()) for info in found
                 if info.get_id())


def edit_file(path, line, timestamp):
    '''Open a text file in the default editor; with xed, at `line`.'''
    editor = Gio.AppInfo.get_default_for_type('text/plain', False)
    if editor is not None and editor.get_id() == 'org.x.editor.desktop' \
            and line:
        try:
            GLib.spawn_async(['xed', f'+{line}', str(path)],
                             flags=GLib.SpawnFlags.SEARCH_PATH)
            return None
        except GLib.Error:
            pass
    return open_path(str(path), timestamp)


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


def open_path(path, timestamp):
    '''Open a file with its default app, a folder in the file manager.'''
    return open_uri(Gio.File.new_for_path(path).get_uri(), timestamp)


def show_in_folder(path, timestamp):
    '''Open the folder `path` is in with `path` selected, through the
    file manager's D-Bus interface (Nemo has it). If that does not
    answer, just the folder. Asynchronous: never waits for the bus.'''
    uri = Gio.File.new_for_path(path).get_uri()
    folder = str(Path(path).parent)

    def fallback():
        open_path(folder, timestamp)

    def called(bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error:
            fallback()

    def connected(_source, result):
        try:
            bus = Gio.bus_get_finish(result)
        except GLib.Error:
            fallback()
            return
        # The startup id carries the click's time, so the window manager
        # lets the file manager come to the front.
        bus.call('org.freedesktop.FileManager1',
                 '/org/freedesktop/FileManager1',
                 'org.freedesktop.FileManager1', 'ShowItems',
                 GLib.Variant('(ass)', ([uri], f'_TIME{timestamp}')), None,
                 Gio.DBusCallFlags.NONE, 3000, None, called)

    Gio.bus_get(Gio.BusType.SESSION, None, connected)
    return None


# When the desktop names no terminal at all.
FALLBACK_TERMINAL = ('x-terminal-emulator', '-e')
TERMINAL_SCHEMA = 'org.cinnamon.desktop.default-applications.terminal'


def terminal_argv(terminal, exec_arg, command):
    '''The argument list that runs `command` in `terminal`. Pure.

    `terminal` is the terminal's command line ('ghostty
    --working-directory=.'), `exec_arg` what it wants before a command
    ('-e', '--', or nothing). The command goes through sh as one single
    argument, so its quotes, `;` and `~` arrive exactly as written. After
    it, the user's own shell takes over the window -- quitting nvim leaves
    you in the folder it ran in, instead of closing the terminal. The line
    break keeps a trailing `# comment` in the command from swallowing it.
    '''
    argv = shlex.split(terminal)
    if exec_arg:
        argv += shlex.split(exec_arg)
    return argv + ['sh', '-c', f'{command}\nexec "${{SHELL:-sh}}"']


def default_terminal():
    '''(terminal, exec_arg) as set in Cinnamon, or a fallback.

    Looked up before it is opened: Gio.Settings on a schema that is not
    installed aborts the whole process.
    '''
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(TERMINAL_SCHEMA, True) if source else None
    if schema is None:
        return FALLBACK_TERMINAL
    settings = Gio.Settings.new(TERMINAL_SCHEMA)
    terminal = settings.get_string('exec').strip()
    if not terminal:
        return FALLBACK_TERMINAL
    return terminal, settings.get_string('exec-arg').strip()


def run_in_terminal(command):
    '''Open the default terminal running `command`. None or the error.'''
    terminal, exec_arg = default_terminal()
    try:
        argv = terminal_argv(terminal, exec_arg, command)
    except ValueError as error:   # unbalanced quotes in the terminal setting
        return f'terminal setting {terminal!r}: {error}'
    try:
        GLib.spawn_async(argv, working_directory=str(Path.home()),
                         flags=GLib.SpawnFlags.SEARCH_PATH)
    except GLib.Error as error:
        return error.message
    return None
