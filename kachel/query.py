'''What was typed into the search bar: text, and the scope pill. Pure.

An abbreviation followed by a space -- `@a ` or `@w ` -- turns into a pill
and leaves the text. Words starting with `@` that are not abbreviations
(mail addresses, say) stay text. The abbreviation for the files, AI and
tldr are known already but not switched on yet.
'''

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    code: str          # what follows the @
    name: str          # on the pill
    icon: str          # a filled Material Symbol
    hint: str          # in the suggestion list
    fill: str          # pill background (Design §5, oklch turned into hex)
    ink: str           # pill text
    active: bool = True


SCOPES = (
    Scope('f', 'Dateien', 'ms:description', 'Dateien und Ordner',
          '#fdb171', '#411f00', active=False),
    Scope('a', 'Apps', 'ms:apps', 'nur installierte Apps',
          '#86caff', '#072a4a'),
    Scope('w', 'Web', 'ms:public', 'mit DuckDuckGo im Web suchen',
          '#89da9b', '#063215'),
    Scope('ai', 'KI', 'ms:auto_awesome', 'eine KI fragen',
          '#d6b4ff', '#3a1a5c', active=False),
    Scope('tldr', 'tldr', 'ms:terminal', 'Befehle nachschlagen',
          '#7fd9d0', '#00302c', active=False),
)
BY_CODE = {scope.code: scope for scope in SCOPES if scope.active}

# @code followed by whitespace, at the start or after whitespace.
PILL = re.compile(r'(^|(?<=\s))@(\w+)\s')


def take_pill(text, cursor):
    '''-> (scope or None, text, cursor). The first known @code that is
    followed by whitespace becomes the scope and leaves the text; the
    cursor keeps its place relative to what is left.'''
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


def suggestions(word):
    '''The scopes to offer for the word at the cursor: those whose code
    starts with what follows the @. Nothing for a word without @, or
    one with a ':' (that is an extra pill like @before:2025, later).'''
    if not word.startswith('@') or ':' in word:
        return []
    typed = word[1:].lower()
    return [scope for scope in SCOPES
            if scope.active and scope.code.startswith(typed)]


def complete(text, cursor, scope):
    '''Replace the word at the cursor with `@code ` -> (text, cursor).
    The space makes take_pill turn it into the pill right away.'''
    start, word = word_at(text, cursor)
    end = start + len(word)
    inserted = f'@{scope.code} '
    rest = text[end:].lstrip(' ')
    return text[:start] + inserted + rest, start + len(inserted)
