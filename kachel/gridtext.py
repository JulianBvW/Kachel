'''The wall as text, for `kachel --grid`. Pure, so it can be tested.

    Work                  0 1 2 3 4 5
                       0  A A A A B B
                       1  A A A A B B
      A org.gnome.Terminal  large  [0, 0]
      B code                medium [4, 0]  (auto)
'''

import string

from . import layout

LETTERS = string.ascii_uppercase + string.ascii_lowercase + string.digits


def render(groups, messages=()):
    '''`groups` as returned by settings.assemble; messages go at the end.'''
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

    if messages:
        out.append(f'{len(messages)} Meldung(en):')
        out.extend(f'  {message}' for message in messages)
    else:
        out.append('Keine Meldungen.')
    return '\n'.join(out) + '\n'
