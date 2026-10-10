'''Searching the apps, and the calculator. Pure, so it can be tested.

The search covers every installed app, pinned or not -- it has nothing to do
with what is on the wall. Files come later, with @f.
'''

import math
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass

MAX_ROWS = 9


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


# -- the calculator --------------------------------------------------------

TOKEN = re.compile(r'\s*(?:(\d+(?:[.,]\d+)?|[.,]\d+)|(\*\*|[-+*/^()×÷]))')
MAX_EXPONENT = 1000


class _NotACalculation(Exception):
    pass


class _Parser:
    '''Recursive descent over the tokens. No eval, ever.

        expr   = term  (('+' | '-') term)*
        term   = unary (('*' | '/') unary)*
        unary  = ('+' | '-') unary | power
        power  = atom (('^' | '**') unary)?      right-associative
        atom   = number | '(' expr ')'
    '''

    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0
        self.operators = 0   # binary ones; '-3' alone is not a sum

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) \
            else None

    def take(self):
        token = self.peek()
        self.index += 1
        return token

    def expr(self):
        value = self.term()
        while self.peek() in ('+', '-'):
            op = self.take()
            self.operators += 1
            right = self.term()
            value = value + right if op == '+' else value - right
        return value

    def term(self):
        value = self.unary()
        while self.peek() in ('*', '/', '×', '÷'):
            op = self.take()
            self.operators += 1
            right = self.unary()
            if op in ('*', '×'):
                value = value * right
            elif right == 0:
                raise _NotACalculation('division by zero')
            else:
                value = value / right
        return value

    def unary(self):
        if self.peek() in ('+', '-'):
            sign = self.take()
            value = self.unary()
            return -value if sign == '-' else value
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() in ('^', '**'):
            self.take()
            self.operators += 1
            exponent = self.unary()
            if abs(exponent) > MAX_EXPONENT:
                raise _NotACalculation('exponent too large')
            try:
                value = base ** exponent
            except (OverflowError, ZeroDivisionError):
                raise _NotACalculation('out of range')
            # A negative base to a fractional power is complex in Python,
            # (-8) ** 0.5 for one. No answer a launcher should give.
            if isinstance(value, complex):
                raise _NotACalculation('not a real number')
            return value
        return base

    def atom(self):
        token = self.take()
        if token == '(':
            value = self.expr()
            if self.take() != ')':
                raise _NotACalculation('unclosed bracket')
            return value
        if isinstance(token, float):
            return token
        raise _NotACalculation(f'unexpected {token!r}')


def _tokenize(text):
    '''Numbers as floats, operators as strings, and the decimal separators
    that were used. (None, ...) if there is anything else in `text`.'''
    tokens, position, separators = [], 0, set()
    text = text.strip()
    while position < len(text):
        match = TOKEN.match(text, position)
        if match is None:
            return None, separators
        number, operator = match.groups()
        if number is not None:
            separators.update(c for c in number if c in ',.')
            tokens.append(float(number.replace(',', '.')))
        else:
            tokens.append(operator)
        position = match.end()
        while position < len(text) and text[position].isspace():
            position += 1
    return tokens, separators


def format_number(value, comma=True):
    '''Whole numbers without decimals, the rest with up to 10 digits.'''
    if value == int(value) and abs(value) < 1e15:
        text = str(int(value))
    else:
        text = f'{value:.10g}'
    return text.replace('.', ',') if comma else text


def calculate(text):
    '''The result of a sum as text, or None if `text` is not a sum.

    A decimal comma and a decimal point both work. The answer uses the
    comma unless the question used a point -- '1.5+1' gives '2.5',
    '1,5+1' and '7/2' give '2,5' and '3,5'. A plain number is not a sum:
    '42' is something to search for.
    '''
    if not text or not text.strip():
        return None
    tokens, separators = _tokenize(text)
    if not tokens:
        return None
    uses_point = separators == {'.'}
    parser = _Parser(tokens)
    try:
        value = parser.expr()
        if parser.peek() is not None:
            return None
    except (_NotACalculation, IndexError):
        return None
    if parser.operators == 0 or math.isnan(value) or math.isinf(value):
        return None
    return format_number(value, comma=not uses_point)


# -- what the list shows ---------------------------------------------------

@dataclass
class Result:
    kind: str           # 'calc', 'app' or 'web'
    title: str
    subtitle: str
    app: object = None  # for 'app'
    value: str = None   # the number to copy, or the URL to open


def web_url(query):
    return 'https://duckduckgo.com/?q=' + urllib.parse.quote_plus(
        query.strip())


def results(query, apps, max_rows=MAX_ROWS):
    '''The rows for `query`: the sum first, then the apps, at most nine.

    Without a single hit there is still a way on: searching the web.
    '''
    rows = []
    answer = calculate(query)
    if answer is not None:
        rows.append(Result('calc', f'= {answer}', query.strip(),
                           value=answer))
    for app in rank(query, apps)[:max_rows - len(rows)]:
        rows.append(Result('app', app.name, app.description or 'App',
                           app=app))
    if not rows and query.strip():
        rows.append(Result('web', f'Im Web suchen: „{query.strip()}“',
                           'DuckDuckGo', value=web_url(query)))
    return rows


def header(query, rows):
    '''The line above the rows: how many hits, or that there are none.'''
    hits = sum(1 for row in rows if row.kind != 'web')
    if hits == 0:
        return f'Keine Treffer für „{query.strip()}“'
    return f'{hits} Treffer'
