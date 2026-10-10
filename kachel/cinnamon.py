'''Talking to Cinnamon: the panel, the favourites, the desktop, uninstalling.

The panel is the one awkward part. The stock menu runs inside Cinnamon
and calls the window list's acceptNewLauncher() directly; Kachel is a
program of its own. So it asks Cinnamon over D-Bus to make that very call
(org.Cinnamon.Eval, a fixed script with only the app ID put in, as JSON).
Should that fail -- a future Cinnamon renaming things -- it writes the
window list's setting instead (org.Cinnamon.updateSetting, the way the
settings dialog does), which the list only picks up after a restart.
'''

import json
import os
import shutil
from pathlib import Path

from gi.repository import Gio, GLib

WINDOW_LIST = 'grouped-window-list@cinnamon.org'
SPICES = Path.home() / '.config' / 'cinnamon' / 'spices'
UNINSTALLER = '/usr/bin/cinnamon-remove-application'

ADD_LAUNCHER = '''(function () {
    const manager = imports.ui.appletManager;
    const provider = manager.get_role_provider(manager.Roles.PANEL_LAUNCHER);
    if (!provider) return false;
    provider.acceptNewLauncher(%s);
    return true;
})()'''


_opened = {}


def _settings(schema_id):
    '''Gio.Settings, or None if the schema is not installed -- opening a
    missing one would abort the process. Opened once, then kept: it
    follows changes by itself.'''
    if schema_id not in _opened:
        source = Gio.SettingsSchemaSource.get_default()
        if source is None or source.lookup(schema_id, True) is None:
            _opened[schema_id] = None
        else:
            _opened[schema_id] = Gio.Settings.new(schema_id)
    return _opened[schema_id]


def panel_id(info):
    '''The ID Cinnamon knows an app by: Flatpaks carry ':flatpak'.'''
    app_id = info.get_id()
    filename = info.get_filename() or ''
    if '/flatpak/exports/' in filename and not app_id.endswith(':flatpak'):
        app_id += ':flatpak'
    return app_id


def _window_list_instance():
    '''The instance ID of the grouped window list, or None.'''
    settings = _settings('org.cinnamon')
    if settings is None:
        return None
    for entry in settings.get_strv('enabled-applets'):
        parts = entry.split(':')
        if len(parts) >= 5 and parts[3] == WINDOW_LIST:
            return parts[4]
    return None


def _pinned(instance):
    try:
        data = json.loads((SPICES / WINDOW_LIST / f'{instance}.json')
                          .read_text(encoding='utf-8'))
        return list(data['pinned-apps']['value'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def in_panel(info):
    instance = _window_list_instance()
    pinned = _pinned(instance) if instance else None
    return bool(pinned) and panel_id(info) in pinned


def add_to_panel(info, done):
    '''Pin to the panel. `done(message)` afterwards: None when the icon is
    there, or a note when it only comes after a restart, or the error.'''
    app_id = panel_id(info)

    def fallback():
        instance = _window_list_instance()
        pinned = _pinned(instance) if instance else None
        if pinned is None:
            done('Zum Panel hinzufügen ging nicht: keine Fensterliste '
                 'gefunden')
            return
        if app_id not in pinned:
            pinned.append(app_id)
        _call('updateSetting', GLib.Variant(
            '(ssss)', (WINDOW_LIST, instance, 'pinned-apps',
                       json.dumps(pinned))),
            lambda result: done(
                'Im Panel eingetragen, erscheint nach dem nächsten '
                'Cinnamon-Neustart' if result is not None else
                'Zum Panel hinzufügen ging nicht'))

    def evaluated(result):
        if result is not None and result.unpack() == (True, 'true'):
            done(None)
        else:
            fallback()

    _call('Eval', GLib.Variant('(s)', (ADD_LAUNCHER % json.dumps(app_id),)),
          evaluated)


def _call(method, parameters, callback):
    '''An asynchronous call to org.Cinnamon; callback(result or None).'''
    def finished(bus, result):
        try:
            callback(bus.call_finish(result))
        except GLib.Error:
            callback(None)

    def connected(_source, result):
        try:
            bus = Gio.bus_get_finish(result)
        except GLib.Error:
            callback(None)
            return
        bus.call('org.Cinnamon', '/org/Cinnamon', 'org.Cinnamon', method,
                 parameters, None, Gio.DBusCallFlags.NONE, 3000, None,
                 finished)

    Gio.bus_get(Gio.BusType.SESSION, None, connected)


# -- favourites ------------------------------------------------------------

def is_favorite(app_id):
    settings = _settings('org.cinnamon')
    return settings is not None and app_id in settings.get_strv(
        'favorite-apps')


def set_favorite(app_id, favorite):
    settings = _settings('org.cinnamon')
    if settings is None:
        return 'Cinnamons Favoriten gibt es hier nicht'
    apps = [a for a in settings.get_strv('favorite-apps') if a != app_id]
    if favorite:
        apps.append(app_id)
    settings.set_strv('favorite-apps', apps)
    return None


# -- desktop ---------------------------------------------------------------

def _desktop_copy(info):
    folder = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)
    filename = info.get_filename()
    if not folder or not filename:
        return None
    return Path(folder) / Path(filename).name


def on_desktop(info):
    target = _desktop_copy(info)
    return target is not None and target.exists()


def add_to_desktop(info):
    '''Copy the .desktop file to the desktop, executable and trusted, so
    Nemo starts it without asking. None or the error.'''
    target = _desktop_copy(info)
    if target is None:
        return 'kein Schreibtisch-Ordner gefunden'
    try:
        shutil.copyfile(info.get_filename(), target)
        os.chmod(target, 0o755)
        Gio.File.new_for_path(str(target)).set_attribute_string(
            'metadata::trusted', 'true', Gio.FileQueryInfoFlags.NONE, None)
    except (OSError, GLib.Error) as error:
        return f'Zum Schreibtisch ging nicht ({error})'
    return None


# -- uninstalling ----------------------------------------------------------

def can_uninstall(info):
    return os.path.exists(UNINSTALLER) and bool(info.get_filename())


def uninstall(info):
    '''Mint's own helper; it asks before it removes anything.'''
    try:
        GLib.spawn_async([UNINSTALLER, info.get_filename()])
    except GLib.Error as error:
        return error.message
    return None
