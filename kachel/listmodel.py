'''The app list's sections and its alphabet rail. Pure, so it can be tested.'''

import string
import unicodedata

LETTERS = list(string.ascii_uppercase) + ['#']

# Latin letters that do not come apart into base letter and accent, but
# that collation sorts among the plain ones.
LATIN = {'Æ': 'A', 'Ø': 'O', 'Œ': 'O', 'Ł': 'L', 'Đ': 'D', 'Þ': 'T',
         'ẞ': 'S'}


def letter_of(name):
    '''The section a name goes in: 'Ärger' -> 'A', '7-Zip' -> '#'.'''
    decomposed = unicodedata.normalize('NFKD', (name or '').strip())
    for c in decomposed:
        if unicodedata.combining(c):
            continue
        c = c.upper()
        c = LATIN.get(c, c)
        return c if c in string.ascii_uppercase else '#'
    return '#'


def sections(apps):
    '''[(letter, [apps])] in the order of `apps`, which come sorted. Only
    letters that have apps; '#' last, as on the rail -- collation would
    put digits first.'''
    by_letter = {}
    for app in apps:
        by_letter.setdefault(letter_of(app.name), []).append(app)
    return [(letter, by_letter[letter]) for letter in LETTERS
            if letter in by_letter]


def jump_target(letter, present):
    '''Where a click on `letter` goes: itself if it has apps, else the next
    letter that has, else (at the end) the one before. None without apps.'''
    if letter in present:
        return letter
    index = LETTERS.index(letter)
    for other in LETTERS[index + 1:]:
        if other in present:
            return other
    for other in reversed(LETTERS[:index]):
        if other in present:
            return other
    return None


def letter_at(y, height):
    '''The rail letter at `y` on a rail `height` pixels high, each letter
    getting an equal share.'''
    if height <= 0:
        return LETTERS[0]
    index = int(y * len(LETTERS) // height)
    return LETTERS[max(0, min(len(LETTERS) - 1, index))]


def pinned_groups(groups):
    '''{app ID: group} from settings.assemble's groups. An app on the wall
    twice counts for the first group it is in.'''
    pinned = {}
    for name, placements in groups:
        for placement in placements:
            app = placement.tile.app
            if app and app not in pinned:
                pinned[app] = name
    return pinned


def current_letter(offsets, scroll, bottom=None):
    '''The section at the top of the view: the last one whose header is at
    or above `scroll`. `offsets` is [(letter, y)] in order.

    At the very end of the list (`scroll` == `bottom`, the furthest it
    goes) the last few headers can never reach the top. There the last
    section counts -- otherwise a click on Z would light up W.'''
    if offsets and bottom is not None and scroll >= bottom - 1 \
            and offsets[-1][1] > scroll + 1:
        return offsets[-1][0]
    current = offsets[0][0] if offsets else None
    for letter, y in offsets:
        if y <= scroll + 1:
            current = letter
        else:
            break
    return current
