'''What the right-click menu offers for what.'''

import harness
from harness import check, section

from kachel.menumodel import Target, menu_for


def ids(entries):
    return [e.id for e in entries if e.kind != 'separator']


section('app')
app = Target('app', 'firefox.desktop', actions=(('new-window', 'Neues Fenster'),),
             groups=('Arbeit', 'Internet'), can_uninstall=True)
entries = menu_for(app)
check('actions first, then pin, panel, desktop, favourites, uninstall',
      ids(entries) == ['action', 'pin', 'panel', 'desktop', 'favorite', 'uninstall'], ids(entries))
pin = next(e for e in entries if e.id == 'pin')
check('pin opens the groups and a new one',
      [c.label for c in pin.children] == ['Arbeit', 'Internet', 'Neue Gruppe …']
      and pin.children[-1].id == 'pin-new', pin.children)
check('no separators between the sections', all(e.kind != 'separator' for e in entries))
entries = menu_for(Target('app', 'x', pinned_in='Arbeit', favorite=True, in_panel=True,
                          on_desktop=True))
check('on the wall already: take it off instead; the rest says what is done',
      ids(entries) == ['unpin', 'panel', 'desktop', 'unfavorite'], ids(entries))
check('panel and desktop are greyed out then',
      [e.enabled for e in entries if e.id in ('panel', 'desktop')] == [False, False])
check('no actions, no uninstaller: no empty section',
      menu_for(Target('app', 'x'))[0].id == 'pin')

section('tile')
tile = Target('tile', 'ghostty.desktop', groups=('Arbeit', 'Internet', 'Spiele'),
              tile_group='Arbeit', tile_size='large')
entries = menu_for(tile)
check('sizes, group, take off, then the app part (tiles.toml only on the empty wall)',
      ids(entries) == ['size', 'group', 'unpin', 'panel', 'desktop', 'favorite'],
      ids(entries))
check('the sizes know the current one', entries[0].kind == 'sizes' and entries[0].payload == 'large')
group = next(e for e in entries if e.id == 'group')
check('group leaves out the current one',
      [c.label for c in group.children] == ['Internet', 'Spiele', 'Neue Gruppe …'])
entries = menu_for(Target('tile', None, tile_group='A', tile_size='medium'))
check('a command tile: only the wall part', ids(entries) == ['size', 'group', 'unpin'])

section('file and wall')
entries = menu_for(Target('file', openers=(('xed.desktop', 'Texteditor'), ('code.desktop', 'VS Code'))))
check('open with, reveal, copy, terminal, then trash',
      ids(entries) == ['open-with', 'reveal', 'copy-path', 'terminal', 'trash'], ids(entries))
check('open with lists the apps, default first',
      [c.payload for c in entries[0].children] == ['xed.desktop', 'code.desktop'])
check('the trash asks with a second click', entries[-1].confirm)
check('no openers: no empty submenu', ids(menu_for(Target('file')))[0] == 'reveal')
check('the wall: edit tiles.toml', ids(menu_for(Target('wall'))) == ['edit-toml'])

harness.report()
