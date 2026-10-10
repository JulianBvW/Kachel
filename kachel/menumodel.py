'''What the right-click menu offers, for what was clicked. Pure.

The window gathers the facts (is the app on the wall, in the panel, a
favourite ...) into a Target; menu_for turns them into entries. Running an
entry is the window's job, by the entry's `id`.
'''

from dataclasses import dataclass, field

SIZES = (('small', 'klein'), ('medium', 'mittel'), ('wide', 'breit'),
         ('large', 'groß'))


@dataclass
class Target:
    kind: str                     # 'app', 'tile', 'file' or 'wall'
    app_id: str = None
    actions: tuple = ()           # ((action, display name), ...) from .desktop
    groups: tuple = ()            # the wall's groups, in order
    pinned_in: str = None         # 'app': the group it is on the wall in
    tile_group: str = None        # 'tile'
    tile_size: str = None         # 'tile'
    in_panel: bool = False
    on_desktop: bool = False
    favorite: bool = False
    can_uninstall: bool = False
    folder: bool = False          # 'file': a folder
    openers: tuple = ()           # 'file': ((app ID, name), ...), default first


@dataclass
class Entry:
    id: str                       # what the window runs
    label: str = ''
    icon: str = None
    enabled: bool = True
    payload: object = None
    kind: str = 'item'            # 'item', 'sizes' or 'submenu'
    children: list = field(default_factory=list)   # for 'submenu'
    confirm: str = None           # a second click is needed; the label then


def _groups_menu(id, label, icon, groups, current=None):
    '''A submenu: every group but the current one, then a new one.'''
    children = [Entry(id, name, 'ms:folder', payload=name)
                for name in groups if name != current]
    children.append(Entry(id + '-new', 'Neue Gruppe …', 'ms:add'))
    return Entry(id, label, icon, kind='submenu', children=children)


def _app_part(target):
    '''What an app offers anywhere: panel, desktop, favourites, uninstall.'''
    entries = [
        Entry('panel', 'Schon im Panel' if target.in_panel
              else 'Zum Panel hinzufügen', 'ms:bottom_navigation',
              enabled=not target.in_panel),
        Entry('desktop', 'Schon auf dem Schreibtisch' if target.on_desktop
              else 'Zum Schreibtisch hinzufügen', 'ms:desktop_windows',
              enabled=not target.on_desktop),
        Entry('unfavorite', 'Aus Favoriten entfernen', 'ms:star')
        if target.favorite else
        Entry('favorite', 'Zu Favoriten hinzufügen', 'ms:star'),
    ]
    if target.can_uninstall:
        entries.append(Entry('uninstall', 'Deinstallieren', 'ms:delete'))
    return entries


def _actions(target):
    return [Entry('action', name, 'ms:open_in_new', payload=action)
            for action, name in target.actions]


def menu_for(target):
    '''The entries for `target`. The sections (the app's own actions,
    the wall, the desktop) follow each other without separators.'''
    sections = []
    if target.kind == 'app':
        sections.append(_actions(target))
        if target.pinned_in:
            sections.append([Entry('unpin', 'Von der Wand nehmen',
                                   'ms:remove')])
        else:
            sections.append([_groups_menu('pin', 'Anheften', 'ms:push_pin',
                                          target.groups)])
        sections.append(_app_part(target))
    elif target.kind == 'tile':
        sections.append(_actions(target))
        sections.append([
            Entry('size', kind='sizes', payload=target.tile_size),
            _groups_menu('group', 'Gruppe', 'ms:folder_open', target.groups,
                         current=target.tile_group),
            Entry('unpin', 'Von der Wand nehmen', 'ms:remove'),
        ])
        if target.app_id:
            sections.append(_app_part(target))
    elif target.kind == 'file':
        openers = [Entry('open-with', name, None, payload=app_id)
                   for app_id, name in target.openers]
        first = []
        if openers:
            first.append(Entry('open-with', 'Öffnen mit', 'ms:apps',
                               kind='submenu', children=openers))
        first += [
            Entry('reveal', 'Im Ordner zeigen', 'ms:folder_open'),
            Entry('copy-path', 'Pfad kopieren', 'ms:content_copy'),
            Entry('terminal', 'Im Terminal öffnen', 'ms:terminal'),
        ]
        sections.append(first)
        sections.append([Entry('trash', 'In den Papierkorb', 'ms:delete',
                               confirm='Sicher? Nochmal klicken')])
    elif target.kind == 'wall':
        sections.append([Entry('edit-toml', 'tiles.toml bearbeiten',
                               'ms:edit_note')])

    return [entry for section in sections for entry in section]
