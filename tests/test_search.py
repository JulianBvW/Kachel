'''Matching apps against a query, and the calculator.'''

from dataclasses import dataclass, field

import harness
from harness import check, section

from kachel import search


@dataclass
class A:
    name: str
    generic_name: str = ''
    keywords: tuple = ()
    executable: str = ''
    description: str = ''
    visible: bool = True
    icon: object = None


def names(query, apps):
    return [a.name for a in search.rank(query, apps)]


section('normalize')
check('lower case', search.normalize('FireFox') == 'firefox')
check('accents go', search.normalize('Écran Fingerabdrücke') == 'ecran fingerabdrucke')
check('None is empty', search.normalize(None) == '')

section('rank: tiers')
apps = [A('Firefox Web Browser', executable='firefox'),
        A('Image Viewer'),
        A('GNU Image Manipulation Program', executable='gimp-2.10'),
        A('Terminal', generic_name='Terminal Emulator', keywords=('shell', 'prompt')),
        A('Ghostty', generic_name='Terminal', keywords=('shell',)),
        A('Hidden Fire', visible=False)]
check('name start first', names('fire', apps)[0] == 'Firefox Web Browser')
check('invisible apps are never found', 'Hidden Fire' not in names('fire', apps))
check('name start beats word start',
      names('ima', apps) == ['Image Viewer', 'GNU Image Manipulation Program'],
      names('ima', apps))
check('name before generic name',
      names('term', apps) == ['Terminal', 'Ghostty'], names('term', apps))
check('keywords count', names('shell', apps) == ['Ghostty', 'Terminal'],
      names('shell', apps))
check('program name counts', names('gimp', apps) == ['GNU Image Manipulation Program'],
      names('gimp', apps))
check('letters in order find it', 'GNU Image Manipulation Program' in names('gmp', apps),
      names('gmp', apps))
check('letters out of order do not', names('pmg', apps) == [], names('pmg', apps))
check('contained in the name', names('hostt', apps) == ['Ghostty'], names('hostt', apps))

section('rank: several words, ties, edge cases')
check('every word has to fit', names('image gnu', apps) == ['GNU Image Manipulation Program'],
      names('image gnu', apps))
check('a word that fits nothing drops the app', names('image zzz', apps) == [])
tied = [A('Beta'), A('alpha'), A('Gamma')]
check('ties go alphabetically, case not counting',
      names('a', tied) == ['alpha', 'Beta', 'Gamma'], names('a', tied))
check('empty query finds nothing', names('', apps) == [] and names('   ', apps) == [])
check('accents in the query do not matter', names('ÌMAGE', apps)[0] == 'Image Viewer')

section('calculate')
cases = [
    ('2+3*4', '14'), ('(2+3)*4', '20'), ('2^10', '1024'), ('2**3**2', '512'),
    ('3,5*2', '7'), ('1,5+1', '2,5'), ('1.5+1', '2.5'), ('7/2', '3,5'),
    ('-3+1', '-2'), ('  1 + 1 ', '2'), ('0.1+0.2', '0.3'), ('3×4', '12'),
    ('10÷4', '2,5'), ('-(1+2)*2', '-6'), ('2^-1', '0,5'),
]
for text, expected in cases:
    got = search.calculate(text)
    check(f'{text!r} = {expected}', got == expected, got)
for text in ('42', '-3', '1/0', '2^99999', '10^999', 'abc', '2 3', '(1+2', '1+',
             '', '   ', 'fire', '1,5', 'e+1', '1e5+1', '(-8)^0.5', '(-2)**(1/3)'):
    got = search.calculate(text)
    check(f'{text!r} is not a sum', got is None, got)

section('prepared match fields')
prepared = A('Firefox')
prepared.match = ('firefox', ['web browser'])
check('a prepared app is matched on its prepared fields',
      search.word_score('web', prepared) == 3, search.word_score('web', prepared))
check('an app without them is normalized on the spot',
      search.match_fields(A('Écran', keywords=('Ä',))) == ('ecran', ['a']))

section('format_number')
check('whole numbers without decimals', search.format_number(14.0) == '14')
check('comma by default', search.format_number(2.5) == '2,5')
check('point on request', search.format_number(2.5, comma=False) == '2.5')
check('ten significant digits', search.format_number(1 / 3) == '0,3333333333')

section('results and header')
rows = search.results('fire', apps)
check('apps become rows with their description, or App',
      rows[0].kind == 'app' and rows[0].subtitle == 'App', rows[0])
rows = search.results('2+2', apps)
check('a sum comes first, with the question below',
      rows[0].kind == 'calc' and rows[0].title == '= 4' and rows[0].subtitle == '2+2'
      and rows[0].value == '4', rows[0])
rows = search.results('xyzqq', apps)
check('no hit: a web search instead', len(rows) == 1 and rows[0].kind == 'web'
      and rows[0].value == 'https://duckduckgo.com/?q=xyzqq', rows)
check('header says there is nothing', search.header('xyzqq', rows) == 'Keine Treffer für „xyzqq“')
many = [A(f'App {i:02}') for i in range(20)]
rows = search.results('app', many)
check('no limit of nine any more', len(rows) == 20, len(rows))
check('header counts all the hits', search.header('app', rows) == '20 Treffer')

section('scopes')
rows = search.results('2+2', apps, scope='a')
check('@a: no calculator', all(r.kind == 'app' for r in rows), rows)
rows = search.results('xyzqq', apps, scope='a')
check('@a: no web search either', rows == [], rows)
check('@a: no hits says so', search.header('xyzqq', rows, 'a') == 'Keine Treffer für „xyzqq“')
listed = [A('Alpha'), A('Beta')]
rows = search.results('  ', apps, scope='a', listed=listed)
check('@a, nothing typed: every listed app, in order',
      [r.title for r in rows] == ['Alpha', 'Beta'], rows)
check('... and the header says so', search.header('', rows, 'a') == 'Alle Apps · 2')
rows = search.results('minecraft !yt', apps, scope='w')
check('@w: exactly one row, the bang goes along',
      len(rows) == 1 and rows[0].kind == 'web'
      and rows[0].value == 'https://duckduckgo.com/?q=minecraft+%21yt', rows)
check('@w: no apps even if the word fits one', search.results('fire', apps, scope='w')[0].kind == 'web')
check('@w, nothing typed: no rows', search.results('', apps, scope='w') == [])
check('@w, nothing typed: a hint in the header',
      search.header('', [], 'w') == 'Suchbegriff eingeben')
check('the web address is escaped',
      search.web_url('a b&c') == 'https://duckduckgo.com/?q=a+b%26c')

harness.report()
