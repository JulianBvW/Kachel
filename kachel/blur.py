'''Is the window going to be blurred? Asked, never changed.

The blur itself is done by the BlurCinnamon extension, matched on the window
class. Kachel only needs to know whether it will happen, to pick between the
see-through background and the nearly opaque one. Nothing here ever writes
to the extension's settings: rewriting another extension's configuration is
not this program's business.
'''

import json
from pathlib import Path

UUID = 'BlurCinnamon@klangman'
SETTINGS_FILE = (Path.home() / '.config' / 'cinnamon' / 'spices' / UUID
                 / f'{UUID}.json')


def entry_active(data, name):
    '''Does this BlurCinnamon configuration blur windows of class `name`?

    `data` is the parsed settings file. Every value in it is wrapped as
    {'value': ...}. Anything malformed counts as no.
    '''
    if not isinstance(data, dict):
        return False

    effects = data.get('enable-window-effects')
    if not isinstance(effects, dict) or effects.get('value') is not True:
        return False

    listing = data.get('windows-inclusion-list')
    if not isinstance(listing, dict):
        return False
    entries = listing.get('value')
    if not isinstance(entries, list):
        return False

    for entry in entries:
        if (isinstance(entry, dict)
                and entry.get('application') == name
                and entry.get('enabled') is True):
            return True
    return False


def extension_enabled():
    '''Is BlurCinnamon switched on in Cinnamon at all?'''
    try:
        from gi.repository import Gio
    except ImportError:
        return False
    # Looked up first, never just opened: Gio.Settings.new on a schema that
    # is not installed (any desktop but Cinnamon) aborts the whole process,
    # and no try/except gets a say in it.
    source = Gio.SettingsSchemaSource.get_default()
    if source is None or source.lookup('org.cinnamon', True) is None:
        return False
    enabled = Gio.Settings.new('org.cinnamon').get_strv('enabled-extensions')
    return UUID in enabled


def active(name):
    '''Will a window of class `name` be blurred? False on any doubt.'''
    if not extension_enabled():
        return False
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return entry_active(data, name)
