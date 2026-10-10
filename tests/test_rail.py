'''What the rail shows: folder paths, how many fit, the action pages.'''

import tempfile
from pathlib import Path

import harness
from harness import check, section

from kachel import railmodel, settings
from kachel.railmodel import BACK, MORE

HOME = Path('/home/test')
DIRS = {'DIRECTORY_DOCUMENTS': '/home/test/Dokumente',
        'DIRECTORY_DOWNLOAD': '/home/test/Downloads'}


def lookup(constant):
    return DIRS.get(constant)


def resolve(path):
    return railmodel.resolve_folder(path, lookup, HOME)


section('resolve_folder')
check('@XDG_DOCUMENTS_DIR from the system',
      resolve('@XDG_DOCUMENTS_DIR') == (Path('/home/test/Dokumente'), None))
path, problem = resolve('@XDG_FOO_DIR')
check('an unknown @XDG name is a problem', path is None and 'gibt es nicht' in problem, problem)
path, problem = resolve('@DOCUMENTS')
check('@ without XDG_..._DIR is a problem', path is None and problem, problem)
path, problem = resolve('@XDG_MUSIC_DIR')
check('a known name that is not set', path is None and 'nicht gesetzt' in problem, problem)
check('~ is the home folder', resolve('~') == (HOME, None))
check('~/x below it', resolve('~/Projekte/Kachel') == (HOME / 'Projekte/Kachel', None))
check('an absolute path', resolve('/mnt/data') == (Path('/mnt/data'), None))
path, problem = resolve('Projekte')
check('a relative path is refused', path is None and 'beginnen' in problem, problem)

section('shown_path')
check('home as ~', railmodel.shown_path(HOME, HOME) == '~')
check('below home with ~/', railmodel.shown_path(HOME / 'Bilder', HOME) == '~/Bilder')
check('elsewhere as is', railmodel.shown_path(Path('/mnt/x'), HOME) == '/mnt/x')

section('folder_capacity')
check('680 px, four action places: 10 folders (Design §13)',
      railmodel.folder_capacity(680, 4) == 10, railmodel.folder_capacity(680, 4))
check('300 px: one', railmodel.folder_capacity(300, 4) == 1, railmodel.folder_capacity(300, 4))
check('2000 px: many', railmodel.folder_capacity(2000, 4) == 41,
      railmodel.folder_capacity(2000, 4))
check('no actions: more room', railmodel.folder_capacity(680, 0) == 14,
      railmodel.folder_capacity(680, 0))
check('never negative', railmodel.folder_capacity(10, 4) == 0)

section('pages')


def actions(n):
    return [settings.Action(f'a{i}', 'true') for i in range(n)]


def names(split):
    return [[x if isinstance(x, str) else x.name for x in page] for page in split]


check('no actions, no pages', railmodel.pages([]) == [])
check('three: one page', names(railmodel.pages(actions(3))) == [['a0', 'a1', 'a2']])
check('four: one page, no "more"',
      names(railmodel.pages(actions(4))) == [['a0', 'a1', 'a2', 'a3']])
check('five: 3 + more, 2 + back',
      names(railmodel.pages(actions(5))) == [['a0', 'a1', 'a2', MORE], ['a3', 'a4', BACK]])
check('six: 3 + more, 3 + back',
      names(railmodel.pages(actions(6)))
      == [['a0', 'a1', 'a2', MORE], ['a3', 'a4', 'a5', BACK]])

section('assemble')
with tempfile.TemporaryDirectory() as tmp:
    home = Path(tmp)
    (home / 'Dokumente').mkdir()
    (home / 'Projekte').mkdir()
    dirs = {'DIRECTORY_DOCUMENTS': str(home / 'Dokumente')}
    rail = settings.Rail(folders=[
        settings.Folder('~', icon='ms:home'),
        settings.Folder('@XDG_DOCUMENTS_DIR'),
        settings.Folder('~/Projekte', name='Code'),
        settings.Folder('~/weg', line=7),
    ], actions=actions(5))
    folders, split, messages = railmodel.assemble(rail, dirs.get, home, 680)
    check('the missing folder is left out with its line',
          [f.name for f in folders] == ['Persönlicher Ordner', 'Dokumente', 'Code']
          and any('Zeile 7' in m and '~/weg' in m for m in messages), messages)
    check('default icon, shown path',
          folders[1].icon == 'ms:folder' and folders[1].shown == '~/Dokumente', folders[1])
    check('two pages', len(split) == 2)

    rail = settings.Rail(folders=[settings.Folder('~')] * 12, actions=actions(4))
    folders, split, messages = railmodel.assemble(rail, dirs.get, home, 680)
    check('more folders than fit: cut to 10 and reported',
          len(folders) == 10 and any('passen 10' in m for m in messages), messages)

harness.report()
