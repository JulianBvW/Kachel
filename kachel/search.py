'''Searching the apps, and the calculator. Pure, so it can be tested.

The search covers every installed app, pinned or not -- it has nothing to do
with what is on the wall. A scope pill narrows it: @a to the apps alone,
@w to a web search. Files come later, with @f.
'''

import re
import unicodedata
import urllib.parse
from dataclasses import dataclass

from . import calc


# -- matching --------------------------------------------------------------

def normalize(text):
    '''Lower case and without accents: 'Écran' and 'ecran' are the same.'''
    decomposed = unicodedata.normalize('NFKD', (text or '').casefold())
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def _words(text):
    return [w for w in re.split(r'[\s\-_.]+', text) if w]


def _is_subsequence(needle, haystack):
    '''Do the letters of `needle` appear in `haystack`, in order?'''
    letters = iter(haystack)
    return all(c in letters for c in needle)


def match_fields(app):
    '''(normalized name, [normalized extras]) for an app.

    Prepared once per app and kept on it (AppIndex does this when it reads
    the apps); normalizing everything again on every keystroke is waste.
    '''
    prepared = getattr(app, 'match', None)
    if prepared is not None:
        return prepared
    return (normalize(app.name),
            [normalize(x) for x in
             (app.generic_name, app.executable, *app.keywords) if x])


def word_score(word, app):
    '''How well one query word fits an app: 0 is best, None is no fit.

    0  the name starts with it          'fire'  -> Firefox
    1  a word in the name starts with it 'image' -> GNU Image Manipulation
    2  the name contains it
    3  generic name, keywords or program name start with it
    4  one of those contains it
    5  its letters appear in the name in order  'gmp' -> GIMP
    '''
    name, extras = match_fields(app)
    if name.startswith(word):
        return 0
    if any(w.startswith(word) for w in _words(name)):
        return 1
    if word in name:
        return 2
    if any(any(w.startswith(word) for w in _words(e)) for e in extras):
        return 3
    if any(word in e for e in extras):
        return 4
    if _is_subsequence(word, name):
        return 5
    return None


def rank(query, apps):
    '''The visible apps that fit every word of `query`, best first.

    Each app needs `name`, `generic_name`, `keywords`, `executable` and
    `visible`. The scores of all words add up; ties go alphabetically.
    '''
    words = normalize(query).split()
    if not words:
        return []
    scored = []
    for app in apps:
        if not app.visible:
            continue
        total = 0
        for word in words:
            score = word_score(word, app)
            if score is None:
                break
            total += score
        else:
            scored.append((total, match_fields(app)[0], app))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [app for _total, _name, app in scored]


# -- what the list shows ---------------------------------------------------

@dataclass
class Result:
    kind: str           # 'calc', 'app', 'web', or 'problem' (does nothing)
    title: str
    subtitle: str
    app: object = None  # for 'app'
    value: str = None   # the number to copy, or the URL to open


def web_url(query):
    return 'https://duckduckgo.com/?q=' + urllib.parse.quote_plus(
        query.strip())


def results(query, apps, scope=None, listed=()):
    '''The rows for `query` in `scope` (a query.Scope code, or None).

    '=': the calculator alone; what does not work says why.
    No scope: the sum first, then every app that fits -- no limit, the
    list loads them in portions -- and without a single hit a way on:
    searching the web. 'a': apps only; with nothing typed, all of
    `listed` (the visible apps, sorted). 'w': one row, the web search;
    bangs like `!yt` simply go along in the query.
    '''
    text = query.strip()
    if scope == '=':
        if not text:
            return []
        answer = calc.evaluate(text)
        if isinstance(answer, calc.Answer):
            return [Result('calc', f'= {answer.text}', text,
                           value=answer.text)]
        return [Result('problem', answer.message, text)]
    if scope == 'w':
        if not text:
            return []
        return [Result('web', f'„{text}“ auf DuckDuckGo suchen',
                       'Web', value=web_url(text))]
    if scope == 'a' and not text:
        return [_app_row(app) for app in listed]

    rows = []
    if scope is None:
        answer = calc.calculate(query)
        if answer is not None:
            rows.append(Result('calc', f'= {answer}', text, value=answer))
    rows += [_app_row(app) for app in rank(query, apps)]
    if not rows and text and scope is None:
        rows.append(Result('web', f'Im Web suchen: „{text}“',
                           'DuckDuckGo', value=web_url(query)))
    return rows


def _app_row(app):
    return Result('app', app.name, app.description or 'App', app=app)


def header(query, rows, scope=None):
    '''The line above the rows: how many hits, or that there are none.'''
    text = query.strip()
    if scope == '=':
        return 'Rechner' if text else 'Rechnung eingeben'
    if scope == 'w' and not text:
        return 'Suchbegriff eingeben'
    if scope == 'w':
        return 'Web'
    hits = sum(1 for row in rows if row.kind != 'web')
    if scope == 'a' and not text:
        return f'Alle Apps · {hits}'
    if hits == 0:
        return f'Keine Treffer für „{text}“'
    return f'{hits} Treffer'
