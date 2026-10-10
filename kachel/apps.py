'''The installed apps, as the desktop knows them.

Read through Gio, which walks the same .desktop files the menu does --
system, ~/.local/share/applications and the Flatpak exports alike.
'''

from dataclasses import dataclass

import gi

gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib  # noqa: E402


@dataclass
class App:
    id: str          # the .desktop ID, e.g. 'org.gnome.Terminal.desktop'
    name: str
    icon: object     # Gio.Icon, or None
    info: object     # Gio.DesktopAppInfo
    visible: bool    # False for NoDisplay entries


class AppIndex:
    '''Every app by ID. Built once and rebuilt when the desktop says so.'''

    def __init__(self):
        self.apps = {}
        self.reload()

    def reload(self):
        apps = {}
        for info in Gio.AppInfo.get_all():
            app_id = info.get_id()
            if not app_id:
                continue
            apps[app_id] = App(app_id, info.get_display_name() or app_id,
                               info.get_icon(), info, info.should_show())
        self.apps = apps

    def resolve(self, app_id):
        '''The installed ID for what a settings file says, or None.

        The .desktop ending may be left off: 'code' finds 'code.desktop'.
        '''
        if app_id in self.apps:
            return app_id
        if not app_id.endswith('.desktop') and f'{app_id}.desktop' in self.apps:
            return f'{app_id}.desktop'
        return None

    def get(self, app_id):
        return self.apps.get(app_id)

    def visible(self):
        '''The apps a menu would show, sorted the way people read them.'''
        shown = [app for app in self.apps.values() if app.visible]
        return sorted(shown, key=lambda app: sort_key(app.name))


def sort_key(name):
    '''Alphabetical in the user's language, case not counting.'''
    return GLib.utf8_collate_key(name.casefold(), -1)
