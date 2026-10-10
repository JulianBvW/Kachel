#!/usr/bin/python3
'''Set Kachel up on this machine, or take it back off again.

    /usr/bin/python3 install.py
    /usr/bin/python3 install.py --in-place
    /usr/bin/python3 install.py --uninstall

The one question it asks has a default; Enter accepts it. Nothing here needs
root, and nothing outside the user's own home is touched.
'''

import shutil
import subprocess
import sys
import time
from pathlib import Path

PYTHON = '/usr/bin/python3'

try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gio, GLib, Gtk
except (ImportError, ValueError):
    sys.exit(f'This Python ({sys.executable}) cannot import gi or GTK 3.\n'
             f'Run the installer with {PYTHON} -- a conda or miniforge '
             'python3 in PATH has no gi.\nOn Mint, if that one lacks it too: '
             'sudo apt install python3-gi')

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from kachel import blur, config  # noqa: E402

PACKAGE = 'kachel'
APP_ID = config.APP_ID

INSTALL_DIR = Path.home() / '.local' / 'share' / 'kachel'
AUTOSTART = Path.home() / '.config' / 'autostart' / 'kachel.desktop'

CUSTOM_SCHEMA = 'org.cinnamon.desktop.keybindings.custom-keybinding'
CUSTOM_PATH = '/org/cinnamon/desktop/keybindings/custom-keybindings/'
LIST_SCHEMA = 'org.cinnamon.desktop.keybindings'
SHORTCUT_SCHEMAS = (
    'org.cinnamon.desktop.keybindings',   # Looking Glass, desklets, zoom
    'org.cinnamon.desktop.keybindings.wm',
    'org.cinnamon.desktop.keybindings.media-keys',
    'org.cinnamon.muffin.keybindings',
)

DESKTOP_ENTRY = '''[Desktop Entry]
Type=Application
Name=Kachel
Comment=Launcher with a tile wall and search, resident so the shortcut is instant
Exec={python} -m {package} --daemon
Path={path}
Terminal=false
X-GNOME-Autostart-enabled=true
'''

SHORTCUTS = (
    ('Kachel: show or hide', 'toggle'),
)
DEFAULT_ACCELERATORS = ('F7',)


# -- the part that only computes, so it can be tested ---------------------

def next_custom_slot(taken):
    '''The lowest customN not in `taken`.

    Searched, not guessed: slot custom0 may well hold someone else's shortcut,
    and writing over it would be rude at best.
    '''
    used = set()
    for name in taken:
        if name.startswith('custom') and name[len('custom'):].isdigit():
            used.add(int(name[len('custom'):]))
    number = 0
    while number in used:
        number += 1
    return f'custom{number}'


def accelerator_taken(accelerator, bindings):
    '''Who already holds this accelerator, or None.

    Whole accelerators are compared, never substrings: <Alt>F7 is the window
    move and has nothing to do with a bare F7.
    '''
    for holder, held in bindings.items():
        if accelerator in held:
            return holder
    return None


def normalize_accelerator(text):
    '''The canonical spelling of an accelerator, or None if it is not one.

    Typed by hand, '<Ctrl>space' and '<Mod4>s' are fine to GTK but would
    never string-match the '<Primary>space' and '<Super>s' the desktop has
    stored. Both sides go through this before comparing. Key names are
    case-sensitive to GTK, so 'f7' is not a shortcut and is asked again
    rather than written down as one that silently does nothing.
    '''
    key, mods = Gtk.accelerator_parse(text.strip())
    if key == 0:
        return None
    if mods & Gdk.ModifierType.MOD4_MASK:
        # Mod4 is Super on every keyboard this will meet, and Cinnamon
        # spells it that way.
        mods = Gdk.ModifierType((mods & ~Gdk.ModifierType.MOD4_MASK)
                                | Gdk.ModifierType.SUPER_MASK)
    return Gtk.accelerator_name(key, mods)


# -- asking ---------------------------------------------------------------

def ask(question, default):
    answer = input(f'  {question} [{default}]: ').strip()
    return answer or default


def ask_yes(question, default=True):
    hint = 'Y/n' if default else 'y/N'
    answer = input(f'  {question} [{hint}]: ').strip().lower()
    if not answer:
        return default
    return answer.startswith(('y', 'j'))


# -- looking around -------------------------------------------------------

def schema_keys(schema_id):
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(schema_id, True)
    return schema.list_keys() if schema is not None else []


def current_bindings():
    '''Every accelerator the desktop already holds: holder -> list.'''
    bindings = {}
    for schema_id in SHORTCUT_SCHEMAS:
        keys = schema_keys(schema_id)
        if not keys:
            # Looked up first, never just opened: Gio.Settings.new on a
            # schema that is not installed aborts the whole process, and no
            # try/except gets a say in it.
            continue
        settings = Gio.Settings.new(schema_id)
        for key in keys:
            if key == 'custom-list':
                continue   # slot names, not accelerators
            value = settings.get_value(key)
            if value.get_type_string() == 'as':
                bindings[f'{schema_id} {key}'] = normalized(value.unpack())

    for slot in Gio.Settings.new(LIST_SCHEMA).get_strv('custom-list'):
        settings = custom_settings(slot)
        if APP_ID in settings.get_string('command'):
            # Our own, from an earlier run. Reinstalling should not report a
            # conflict with itself.
            continue
        label = settings.get_string('name') or slot
        bindings[f'custom shortcut "{label}"'] = normalized(
            settings.get_strv('binding'))
    return bindings


def normalized(accelerators):
    '''The canonical spellings of a stored list, unparsable ones dropped.'''
    result = []
    for accelerator in accelerators:
        name = normalize_accelerator(accelerator)
        if name is not None:
            result.append(name)
    return result


def custom_settings(slot):
    return Gio.Settings.new_with_path(CUSTOM_SCHEMA, f'{CUSTOM_PATH}{slot}/')


def system_python_has_gi():
    '''The autostart entry runs /usr/bin/python3, so that one needs gi.

    On this machine `python3` in PATH is miniforge and has no gi at all; the
    failure would be a ModuleNotFoundError at login, long after anyone is
    watching.
    '''
    try:
        subprocess.run([PYTHON, '-c', 'import gi'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


# -- doing ----------------------------------------------------------------

def copy_package(target):
    destination = target / PACKAGE
    if destination.exists():
        # Emptied first, so files dropped from the project do not live on --
        # but only once it has been established that this really is ours.
        if not (destination / '__main__.py').is_file():
            sys.exit(f'{destination} exists and is not a Kachel install. '
                     'Refusing to touch it.')
        shutil.rmtree(destination)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(HERE / PACKAGE, destination,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def write_autostart(run_from):
    AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART.write_text(
        DESKTOP_ENTRY.format(python=PYTHON, package=PACKAGE, path=run_from),
        encoding='utf-8')


def install_shortcuts(accelerators):
    '''Write the shortcuts, custom-list last.

    That order matters: csd-media-keys only re-reads the sub-keys when the
    list changes. Set the list first and it reads empty entries, and the
    shortcut silently does nothing.
    '''
    # Any of ours from an earlier run go first, or installing twice would
    # leave the shortcut bound in two places at once.
    remove_shortcuts()

    listing = Gio.Settings.new(LIST_SCHEMA)
    slots = list(listing.get_strv('custom-list'))

    for (label, action), accelerator in zip(SHORTCUTS, accelerators):
        slot = next_custom_slot(slots)
        settings = custom_settings(slot)
        settings.set_string('name', label)
        settings.set_string('command',
                            f'gapplication action {APP_ID} {action}')
        settings.set_strv('binding', [accelerator])
        slots.append(slot)

    Gio.Settings.sync()
    listing.set_strv('custom-list', slots)   # last, always
    Gio.Settings.sync()
    return slots


def remove_shortcuts():
    '''Drop every custom shortcut that points at us. The list goes last.'''
    listing = Gio.Settings.new(LIST_SCHEMA)
    keep, dropped = [], []
    for slot in listing.get_strv('custom-list'):
        settings = custom_settings(slot)
        if APP_ID in settings.get_string('command'):
            for key in ('name', 'command', 'binding'):
                settings.reset(key)
            dropped.append(slot)
        else:
            keep.append(slot)
    Gio.Settings.sync()
    listing.set_strv('custom-list', keep)
    Gio.Settings.sync()
    return dropped


def stop_daemon():
    '''Ask a running instance to quit, and wait until it really has.

    The quit action returns as soon as it is delivered, not when the old
    process lets go of its bus name. A new one started in that gap finds the
    name still taken, hands its --daemon to the dying instance and exits --
    and then nothing is running at all.
    '''
    subprocess.run(['gapplication', 'action', APP_ID, 'quit'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        reply = bus.call_sync(
            'org.freedesktop.DBus', '/org/freedesktop/DBus',
            'org.freedesktop.DBus', 'NameHasOwner',
            GLib.Variant('(s)', (APP_ID,)), GLib.VariantType('(b)'),
            Gio.DBusCallFlags.NONE, -1, None)
        if not reply.unpack()[0]:
            return True
        time.sleep(0.05)
    return False


def start_daemon(run_from):
    subprocess.Popen([PYTHON, '-m', PACKAGE, '--daemon'], cwd=str(run_from),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


# -- the two commands -----------------------------------------------------

def install(in_place):
    print('\nKachel\n')

    if not system_python_has_gi():
        sys.exit(f'{PYTHON} cannot import gi, and that is what the autostart '
                 'entry will run.\nOn Mint: sudo apt install python3-gi')

    bindings = current_bindings()
    accelerators = []
    for (label, _action), default in zip(SHORTCUTS, DEFAULT_ACCELERATORS):
        while True:
            what = label.split(': ')[1]
            typed = ask(f'Shortcut to {what}', default)
            accelerator = normalize_accelerator(typed)
            if accelerator is None:
                print(f'    {typed} is not a shortcut GTK understands, '
                      'try e.g. F7 or <Super>space.')
                continue
            holder = accelerator_taken(accelerator, bindings)
            if holder is None:
                break
            print(f'    {accelerator} is already held by {holder}.')
            if ask_yes('    Use it anyway?', False):
                break
        accelerators.append(accelerator)

    run_from = HERE if in_place else INSTALL_DIR
    print()
    if in_place:
        print(f'  Running from {run_from} (--in-place)')
    else:
        copy_package(INSTALL_DIR)
        print(f'  Copied the package to {INSTALL_DIR / PACKAGE}')

    write_autostart(run_from)
    print(f'  Wrote {AUTOSTART}')

    slots = install_shortcuts(accelerators)
    keys = ', '.join(accelerators)
    used = ', '.join(slots[-len(accelerators):])
    print(f'  Shortcut {keys} on {used}')

    if not stop_daemon():
        sys.exit('\n  The running Kachel did not quit within three seconds. '
                 'Not starting a second one.')
    start_daemon(run_from)
    print(f'\n  Running. Press {accelerators[0]}.')

    if blur.active(config.PROGRAM_CLASS):
        print('\n  BlurCinnamon blurs the window already.')
    else:
        print(BLUR_HINT)
    print()


BLUR_HINT = '''
  BlurCinnamon does not blur Kachel yet, so it draws a nearly opaque pane.
  For the glass, in BlurCinnamon's settings under "Component specific
  settings", switch on "Enable window effects" and add an entry:

      Application           Kachel
      Custom                on
      Opacity               100
      Dim                   0        (Kachel brings its own 60 %)
      Background            Dual Kawase dynamic blur
      Intensity             18
      Saturation            100      (the most the settings dialog allows)
      Corner Radius         16       (same as the window's own)
      Rounded Top / Bottom  both on

  Kachel looks again every time it is shown, so there is nothing to restart.
'''


def uninstall():
    print('\nKachel -- taking it back off\n')

    stop_daemon()

    dropped = remove_shortcuts()
    removed = ', '.join(dropped) if dropped else 'none'
    print(f'  Shortcuts removed: {removed}')

    if AUTOSTART.exists():
        AUTOSTART.unlink()
        print(f'  Removed {AUTOSTART}')

    # The same check as on installing: only a folder that is recognisably
    # ours goes, and the parent only if nothing else is left in it.
    package = INSTALL_DIR / PACKAGE
    if (package / '__main__.py').is_file():
        shutil.rmtree(package)
        print(f'  Removed {package}')
    elif package.exists():
        print(f'  Left {package} alone: it is not a Kachel install.')
    if INSTALL_DIR.is_dir() and not any(INSTALL_DIR.iterdir()):
        INSTALL_DIR.rmdir()
        print(f'  Removed {INSTALL_DIR}')

    if config.CONFIG_DIR.is_dir():
        print(f'\n  Your settings in {config.CONFIG_DIR} are still there -- '
              'they are yours,\n  and installing again picks them up.')
    print('\n  A BlurCinnamon entry for Kachel, if you made one, is still '
          'there.\n  It is yours to remove; this script never touched it.\n')


def main(argv):
    if '--uninstall' in argv:
        uninstall()
    else:
        install(in_place='--in-place' in argv)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
