'''What was typed into the search bar: text, and the scope pill. Pure.

An abbreviation followed by a space -- `@a ` or `@w ` -- turns into a pill
and leaves the text; so does `= ` at the very start, for the calculator.
Words starting with `@` that are not abbreviations (mail addresses, say)
stay text. The abbreviation for AI is known already but not switched on
yet.

With the files pill, `@type:pdf `, `@before:2025 ` and `@after:10.2026 `
become extra pills that narrow the files further.
'''

import re
from dataclasses import dataclass

from . import files


@dataclass(frozen=True)
class Scope:
    code: str          # what follows the @
    name: str          # on the pill
    icon: str          # a filled Material Symbol
    hint: str          # in the suggestion list
    fill: str          # pill background (Design §5, oklch turned into hex)
    ink: str           # pill text
    active: bool = True
    key: str = None    # for CSS class names; the code unless that won't do
    prefix: str = '@'  # what comes before the code; '' for '='

    @property
    def css(self):
        return self.key or self.code


SCOPES = (
    Scope('f', 'Dateien', 'ms:description', 'Dateien und Ordner',
          '#fdb171', '#411f00'),
    Scope('a', 'Apps', 'ms:apps', 'nur installierte Apps',
          '#86caff', '#072a4a'),
    Scope('w', 'Web', 'ms:public', 'mit DuckDuckGo im Web suchen',
          '#89da9b', '#063215'),
    Scope('ai', 'KI', 'ms:auto_awesome', 'eine KI fragen',
          '#d6b4ff', '#3a1a5c', active=False),
    Scope('tldr', 'tldr', 'ms:terminal', 'Befehle nachschlagen',
          '#7fd9d0', '#00302c'),
    # Typed as '= ' at the very start, never offered after an @.
    Scope('=', 'Rechner', 'ms:calculate', 'rechnen, auch mit Funktionen',
          '#d6c665', '#312900', key='calc', prefix=''),
)
CALC = SCOPES[-1]
BY_CODE = {scope.code: scope for scope in SCOPES
           if scope.active and scope.prefix == '@'}

# @code followed by whitespace, at the start or after whitespace.
PILL = re.compile(r'(^|(?<=\s))@(\w+)\s')

# The extra pills of the files scope, offered in the suggestions like the
# scopes. Their code ends in ':' -- a value follows, not a space.
EXTRAS = (
    Scope('type:', 'Typ', 'ms:draft', 'nur diese Endung, z. B. @type:pdf',
          '', ''),
    Scope('before:', 'vor', 'ms:history',
          'geändert vor …, z. B. @before:2025', '', ''),
    Scope('after:', 'nach', 'ms:update',
          'geändert nach …, z. B. @after:10.2026', '', ''),
)
EXTRA = re.compile(r'(^|(?<=\s))@(type|before|after):(\S+)\s', re.IGNORECASE)


@dataclass(frozen=True)
class Extra:
    '''An extra pill: a file type or a date bound.'''
    kind: str              # 'type', 'before' or 'after'
    value: str             # as typed: 'pdf', '2025', '10.11.2025'
    period: tuple = None   # (start, end) for the dates

    @property
    def label(self):
        if self.kind == 'type':
            return '.' + self.value.lower().lstrip('.')
        return ('vor ' if self.kind == 'before' else 'nach ') + self.value


def make_extra(kind, value):
    '''An Extra, or None when the value does not work (no real date, or
    an ending with a slash in it).'''
    kind = kind.lower()
    if kind == 'type':
        value = value.lstrip('.')
        if not value or '/' in value:
            return None
        return Extra('type', value)
    period = files.parse_date(value)
    return Extra(kind, value, period) if period else None


def take_extra(text, cursor):
    '''Like take_pill, for @type:, @before: and @after: followed by a
    space. A value that does not work stays text.'''
    for match in EXTRA.finditer(text):
        extra = make_extra(match[2], match[3])
        if extra is None:
            continue
        start, end = match.start(2) - 1, match.end()
        rest = text[:start] + text[end:]
        if cursor >= end:
            cursor -= end - start
        elif cursor > start:
            cursor = start
        return extra, rest, cursor
    return None, text, cursor


def take_pill(text, cursor, calc=True):
    '''-> (scope or None, text, cursor). The first known @code that is
    followed by whitespace becomes the scope and leaves the text; the
    cursor keeps its place relative to what is left. '= ' counts only at
    the very start, and only with `calc` -- not while another pill is
    there: with Web, '= vs ==' is something to look up.'''
    match = re.match(r'=\s', text) if calc else None
    if match:
        return CALC, text[match.end():], max(0, cursor - match.end())
    for match in PILL.finditer(text):
        scope = BY_CODE.get(match[2].lower())
        if scope is None:
            continue
        start, end = match.start(2) - 1, match.end()
        rest = text[:start] + text[end:]
        if cursor >= end:
            cursor -= end - start
        elif cursor > start:
            cursor = start
        return scope, rest, cursor
    return None, text, cursor


def word_at(text, cursor):
    '''(start, word) of the word the cursor is in or right behind.'''
    start = cursor
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    end = cursor
    while end < len(text) and not text[end].isspace():
        end += 1
    return start, text[start:end]


def suggestions(word, scope=None):
    '''What to offer for the word at the cursor: the scopes whose code
    starts with what follows the @, and with the files scope active its
    extra pills first. Nothing for a word without @, or once a ':' is
    typed (the value comes then).'''
    if not word.startswith('@') or ':' in word:
        return []
    typed = word[1:].lower()
    offer = list(EXTRAS) if scope is not None and scope.code == 'f' else []
    offer += BY_CODE.values()
    return [s for s in offer if s.code.startswith(typed)]


def complete(text, cursor, scope):
    '''Replace the word at the cursor with `@code ` -> (text, cursor).
    The space makes take_pill turn it into the pill right away.'''
    start, word = word_at(text, cursor)
    end = start + len(word)
    # An extra pill wants its value next, right after the colon.
    space = '' if scope.code.endswith(':') else ' '
    inserted = f'{scope.prefix}{scope.code}{space}'
    rest = text[end:].lstrip(' ') if space else text[end:]
    return text[:start] + inserted + rest, start + len(inserted)
