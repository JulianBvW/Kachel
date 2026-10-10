'''The wall as text, for `kachel --grid`. Pure, so it can be tested.

    Work                  0 1 2 3 4 5
                       0  A A A A B B
                       1  A A A A B B
      A org.gnome.Terminal  large  [0, 0]
      B code                medium [4, 0]  (auto)
'''

import string

from . import layout, railmodel

LETTERS = string.ascii_uppercase + string.ascii_lowercase + string.digits


def render(groups, messages=(), rail=None):
    '''`groups` as returned by settings.assemble, `rail` as (folders,
    pages) from railmodel.assemble; messages go at the end.'''
    out = []
    if not groups:
        out.append('Keine Gruppen.')

    for name, placements in groups:
        out.append(name or '(ohne Namen)')
        rows = layout.group_rows(placements)
        cells = {}
        for index, p in enumerate(placements):
            mark = LETTERS[index % len(LETTERS)]
            width, height = layout.SIZES[p.tile.size]
            for row in range(p.row, p.row + height):
                for col in range(p.col, p.col + width):
                    cells[(col, row)] = mark

        out.append('       ' + ' '.join(str(c) for c in
                                         range(layout.GRID_COLUMNS)))
        for row in range(rows):
            line = ' '.join(cells.get((col, row), '.')
                            for col in range(layout.GRID_COLUMNS))
            out.append(f'  {row:>3}  {line}')
        if not placements:
            out.append('  (leer)')

        width = max((len(p.tile.label) for p in placements), default=0)
        for index, p in enumerate(placements):
            mark = LETTERS[index % len(LETTERS)]
            where = f'[{p.col}, {p.row}]'
            auto = '  (auto)' if p.auto else ''
            out.append(f'  {mark} {p.tile.label:<{width}}  '
                       f'{p.tile.size:<6} {where}{auto}')
            for shortcut in p.tile.shortcuts:
                how = '  (Terminal)' if shortcut.terminal else ''
                out.append(f'      › {shortcut.name}  {shortcut.command}{how}')
        out.append('')

    if rail is not None:
        out.extend(render_rail(*rail))
        out.append('')

    if messages:
        out.append(f'{len(messages)} Meldung(en):')
        out.extend(f'  {message}' for message in messages)
    else:
        out.append('Keine Meldungen.')
    return '\n'.join(out) + '\n'


def _rail_line(item):
    if item == railmodel.MORE:
        return '› Mehr'
    if item == railmodel.BACK:
        return '‹ Zurück'
    line = f'{item.name}  {item.command}'
    if item.terminal:
        line += '  (Terminal)'
    if item.confirm is not None:
        line += (f'  (Bestätigung: „{item.confirm.label}“, '
                 f'{item.confirm.duration} ms)')
    return line


def render_rail(folders, pages):
    '''The rail as lines of text: folders, then the action pages.'''
    out = ['Leiste', '  Ordner']
    width = max((len(f.name) for f in folders), default=0)
    out.extend(f'    {f.name:<{width}}  {f.shown}' for f in folders)
    if not folders:
        out.append('    (keine)')
    if not pages:
        out.append('  Aktionen')
        out.append('    (keine)')
    for number, page in enumerate(pages, 1):
        out.append(f'  Aktionen, Seite {number}' if len(pages) > 1
                   else '  Aktionen')
        out.extend(f'    {_rail_line(item)}' for item in page)
    return out
