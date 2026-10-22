#!/usr/bin/python3
'''Set Kachel up on this machine, or take it back off again.

    /usr/bin/python3 install.py
    /usr/bin/python3 install.py --in-place
    /usr/bin/python3 install.py --uninstall

Every question it asks has a default; Enter accepts it. Nothing here needs
root, and nothing outside the user's own home is touched.
'''

import json
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
# Kachel's own entry, hidden from menus: the icon for its notifications,
# and how the panel button starts it when it is not running.
APP_ENTRY = Path.home() / '.local' / 'share' / 'applications' / \
    f'{APP_ID}.desktop'
ICON_SOURCE = HERE / 'data' / f'{APP_ID}.svg'
ICONS = Path.home() / '.local' / 'share' / 'icons' / 'hicolor' / \
    'scalable' / 'apps'
ICON = ICONS / f'{APP_ID}.svg'

APPLET_UUID = 'kachel@julianbvw'
APPLET_SOURCE = HERE / 'applet' / APPLET_UUID
APPLET = Path.home() / '.local' / 'share' / 'cinnamon' / 'applets' / \
    APPLET_UUID
# The panel logos, also in the icon theme so the icon chooser of the
# button's settings can offer them.
LOGOS = ('kachel-windrad-symbolic', 'kachel-layout-symbolic')
SPICES = Path.home() / '.config' / 'cinnamon' / 'spices'
PANEL_SCHEMA = 'org.cinnamon'

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

APP_DESKTOP_ENTRY = '''[Desktop Entry]
Type=Application
Name=Kachel
Comment=Launcher with a tile wall and search
Exec={python} -m {package} --daemon
Path={path}
Icon={icon}
NoDisplay=true
Terminal=false
'''

SHORTCUTS = (
    ('Kachel: show or hide', 'toggle'),
)
DEFAULT_ACCELERATORS = ('Super_L',)


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


def with_applet(entries, uuid=APPLET_UUID):
    '''org.cinnamon enabled-applets with our button added, or None if it is
    there already. Entries read panel:zone:order:uuid:id.

    It goes first on the left of the first panel, where a start button
    sits, so the menu that is there now ends up right of it. Whatever sits
    there moves one along, so the order stays as it was.
    '''
    parsed = [entry.split(':') for entry in entries]
    if any(len(p) >= 4 and p[3] == uuid for p in parsed):
        return None
    ids = [int(p[4]) for p in parsed if len(p) >= 5 and p[4].isdigit()]
    panel, zone, order = 'panel1', 'left', 0
    same = [p for p in parsed
            if len(p) >= 3 and p[0] == panel and p[1] == zone
            and p[2].isdigit()]
    if any(int(p[2]) == order for p in same):
        for p in same:
            if int(p[2]) >= order:
                p[2] = str(int(p[2]) + 1)
    new = f'{panel}:{zone}:{order}:{uuid}:{max(ids, default=0) + 1}'
    return [':'.join(p) for p in parsed] + [new]


def without_applet(entries, uuid=APPLET_UUID):
    '''enabled-applets without our button.'''
    return [entry for entry in entries
            if entry.split(':')[3:4] != [uuid]]


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

    panel = panel_settings()
    if panel is not None:
        bindings.update(applet_bindings(panel.get_strv('enabled-applets')))
    return bindings


def applet_bindings(entries, spices=SPICES):
    '''Shortcuts panel applets hold themselves, like a menu on the Super
    key: they live in the applet's own settings, not the desktop's.'''
    bindings = {}
    for entry in entries:
        parts = entry.split(':')
        if len(parts) < 5 or parts[3] == APPLET_UUID:
            continue
        uuid, instance = parts[3], parts[4]
        for name in (f'{instance}.json', f'{uuid}.json'):
            try:
                data = json.loads((spices / uuid / name).read_text())
            except (OSError, ValueError):
                continue
            for key, setting in data.items():
                if (isinstance(setting, dict)
                        and setting.get('type') == 'keybinding'):
                    held = normalized(
                        str(setting.get('value', '')).split('::'))
                    if held:
                        bindings[f'the applet {uuid} ({key})'] = held
            break
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


def write_app_entry(run_from):
    APP_ENTRY.parent.mkdir(parents=True, exist_ok=True)
    APP_ENTRY.write_text(
        APP_DESKTOP_ENTRY.format(python=PYTHON, package=PACKAGE,
                                 path=run_from, icon=APP_ID),
        encoding='utf-8')
    ICONS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_SOURCE, ICON)
    for logo in LOGOS:
        shutil.copyfile(APPLET_SOURCE / f'{logo}.svg', ICONS / f'{logo}.svg')


def _is_our_applet(path):
    '''Ours: a link to an applet folder of Kachel, or a folder whose
    metadata names our uuid.'''
    if path.is_symlink():
        return path.resolve().name == APPLET_UUID
    try:
        return f'"{APPLET_UUID}"' in (path / 'metadata.json').read_text()
    except OSError:
        return False


def install_applet(in_place):
    '''The panel button's files: linked to the clone with --in-place, so
    changes to it apply without installing again, else copied.'''
    if APPLET.is_symlink() or APPLET.exists():
        if not _is_our_applet(APPLET):
            sys.exit(f'{APPLET} exists and is not Kachel\'s. Refusing to '
                     'touch it.')
        if APPLET.is_symlink():
            APPLET.unlink()
        else:
            shutil.rmtree(APPLET)
    APPLET.parent.mkdir(parents=True, exist_ok=True)
    if in_place:
        APPLET.symlink_to(APPLET_SOURCE, target_is_directory=True)
    else:
        shutil.copytree(APPLET_SOURCE, APPLET)


def panel_settings():
    if not schema_keys(PANEL_SCHEMA):
        return None
    return Gio.Settings.new(PANEL_SCHEMA)


def on_panel():
    settings = panel_settings()
    return settings is not None and with_applet(
        settings.get_strv('enabled-applets')) is None


def set_on_panel(on):
    '''Add our button to the panel, or take it off. Cinnamon follows the
    setting at once.'''
    settings = panel_settings()
    if settings is None:
        return False
    entries = settings.get_strv('enabled-applets')
    changed = with_applet(entries) if on else without_applet(entries)
    if changed is None or changed == entries:
        return False
    settings.set_strv('enabled-applets', changed)
    Gio.Settings.sync()
    return True


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

    to_panel = False
    if panel_settings() is not None and not on_panel():
        to_panel = ask_yes('Put the Kachel button on the panel, first on '
                           'the left?', True)

    run_from = HERE if in_place else INSTALL_DIR
    print()
    if in_place:
        print(f'  Running from {run_from} (--in-place)')
    else:
        copy_package(INSTALL_DIR)
        print(f'  Copied the package to {INSTALL_DIR / PACKAGE}')

    write_autostart(run_from)
    print(f'  Wrote {AUTOSTART}')
    write_app_entry(run_from)
    print(f'  Wrote {APP_ENTRY} and the icons')
    install_applet(in_place)
    print(f'  {"Linked" if in_place else "Copied"} the panel button to '
          f'{APPLET}')
    if to_panel and set_on_panel(True):
        print('  Put the button on the panel. Its icon: right-click it, '
              'Configure.')

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

    if set_on_panel(False):
        print('  Took the button off the panel')
    if APPLET.is_symlink() or APPLET.exists():
        if _is_our_applet(APPLET):
            if APPLET.is_symlink():
                APPLET.unlink()
            else:
                shutil.rmtree(APPLET)
            print(f'  Removed {APPLET}')
        else:
            print(f'  Left {APPLET} alone: it is not Kachel\'s.')
    logos = [ICONS / f'{logo}.svg' for logo in LOGOS]
    for path in (APP_ENTRY, ICON, *logos):
        if path.exists():
            path.unlink()
            print(f'  Removed {path}')

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
