'''Finding files: dates, what is left out, what comes first.'''

from datetime import date, datetime

import harness
from harness import check, section

from kachel import files
from kachel.files import FileHit

HOME = '/home/test'


def ts(*args):
    return datetime(*args).timestamp()


section('parse_date')
check('a year', files.parse_date('2026') == (ts(2026, 1, 1), ts(2027, 1, 1)))
check('a month', files.parse_date('11.2025') == (ts(2025, 11, 1), ts(2025, 12, 1)))
check('December runs into the next year',
      files.parse_date('12.2025') == (ts(2025, 12, 1), ts(2026, 1, 1)))
check('a day, German', files.parse_date('10.11.2025') == (ts(2025, 11, 10), ts(2025, 11, 11)))
check('a day, American', files.parse_date('11/10/2025') == (ts(2025, 11, 10), ts(2025, 11, 11)))
check('a leap day', files.parse_date('29.02.2024') is not None)
for bad in ('13.2025', '31.02.2025', '29.02.2025', 'abc', '20255', '1.1.25', '', '13/01/2025'):
    check(f'{bad!r} is no date', files.parse_date(bad) is None)

section('date_ok: the period itself never counts')
before_2026 = files.parse_date('2026')
after_2025 = files.parse_date('2025')
check('before 2026: 31.12.2025 counts', files.date_ok(ts(2025, 12, 31, 23), before=before_2026))
check('before 2026: 1.1.2026 does not', not files.date_ok(ts(2026, 1, 1), before=before_2026))
check('after 2025: 1.1.2026 counts', files.date_ok(ts(2026, 1, 1), after=after_2025))
check('after 2025: 31.12.2025 does not', not files.date_ok(ts(2025, 12, 31, 23), after=after_2025))
check('after 11.2025 starts on 1.12.2025',
      files.date_ok(ts(2025, 12, 1), after=files.parse_date('11.2025'))
      and not files.date_ok(ts(2025, 11, 30), after=files.parse_date('11.2025')))
check('after 31.12.2025 starts on 1.1.2026',
      files.date_ok(ts(2026, 1, 1), after=files.parse_date('31.12.2025'))
      and not files.date_ok(ts(2025, 12, 31, 12), after=files.parse_date('31.12.2025')))
check('no bounds: anything', files.date_ok(ts(1999, 1, 1)))
check('no time known: only without bounds',
      files.date_ok(None) and not files.date_ok(None, before=before_2026))

section('when')
today = date(2026, 10, 10)
check('today', files.when(ts(2026, 10, 10, 8), today) == 'heute')
check('yesterday', files.when(ts(2026, 10, 9, 23), today) == 'gestern')
check('earlier: the date', files.when(ts(2025, 1, 14), today) == '14.01.2025')

section('Excluder')
ex = files.Excluder(home=HOME)
for path, out in (('/usr/lib/x', True), ('/usr', True), ('/usrlocal/x', False),
                  ('/home/test/.cache/a', True), ('/home/test/.cachefoo/a', False),
                  ('/home/test/p/node_modules/x/y.js', True),
                  ('/home/test/node_modules_notes.txt', False),
                  ('/home/test/p/.git/config', True), ('/home/test/VirtualBox VMs/w.vdi', True),
                  ('/timeshift/snapshots/x', True), ('/mnt/wsl/x', False),
                  ('/home/test/Dokumente/a.pdf', False)):
    check(f'{path} {"out" if out else "in"}', ex.excluded(path) == out)
check("'/' or an empty entry leaves out nothing, not everything",
      not files.Excluder(paths=('/', ''), names=(), home=HOME).excluded('/home/test/a'))
check('name_matches looks at the name alone',
      files.name_matches('/home/test/kachel/brief.txt', ['brief'])
      and not files.name_matches('/home/test/kachel/brief.txt', ['kachel']))
check('own lists replace the defaults',
      not files.Excluder(paths=(), names=(), home=HOME).excluded('/usr/x'))

section('matching')
check('all words somewhere in the path',
      files.matches('/home/test/Steuer/Rechnung_2025.pdf', ['rechnung', 'steuer']))
check('one missing: no', not files.matches('/home/test/Rechnung.pdf', ['rechnung', '2024']))
check('accents do not matter', files.matches('/home/test/Übersicht.odt', ['uber']))
check('type: any of the endings',
      files.has_type('/a/B.PDF', ['pdf']) and files.has_type('/a/b.odt', ['pdf', 'odt'])
      and not files.has_type('/a/pdf.txt', ['pdf']) and files.has_type('/a/x', []))

section('strong')
check('kachel is strong for Kachel-Notizen.md', files.strong('Kachel-Notizen.md', ['kachel']))
check('notiz too, it starts a word', files.strong('Kachel-Notizen.md', ['notiz']))
check('chel is not', not files.strong('Kachel-Notizen.md', ['chel']))
check('every word must start one', not files.strong('Kachel-Notizen.md', ['kachel', 'zen']))
check('no words, nothing strong', not files.strong('a.txt', []))

section('rank')
hits = [
    FileHit('/usr2/rechnung.pdf', mtime=50),
    FileHit('/home/test/rechnung/brief.txt', mtime=90),
    FileHit('/home/test/.config/rechnung.pdf', mtime=99),
    FileHit('/mnt/data/rechnung.pdf', mtime=10),
    FileHit('/home/test/Dokumente/rechnung_alt.pdf', mtime=20),
    FileHit('/home/test/Dokumente/rechnung_neu.pdf', mtime=80),
    FileHit('/home/test/rechnung_ohne_zeit.pdf'),
]
order = [h.path for h in files.rank(hits, ['rechnung'], HOME)]
check('name before path, home before /mnt before the rest, hidden later, newer first',
      order == ['/home/test/Dokumente/rechnung_neu.pdf', '/home/test/Dokumente/rechnung_alt.pdf',
                '/home/test/rechnung_ohne_zeit.pdf', '/home/test/.config/rechnung.pdf',
                '/mnt/data/rechnung.pdf', '/usr2/rechnung.pdf', '/home/test/rechnung/brief.txt'],
      order)

section('shown_dir and escape_pattern')
check('home as ~', files.shown_dir('/home/test/a.txt', HOME) == '~')
check('below home', files.shown_dir('/home/test/Dokumente/a.txt', HOME) == '~/Dokumente')
check('elsewhere as is', files.shown_dir('/mnt/x/a.txt', HOME) == '/mnt/x')
check('glob characters are escaped', files.escape_pattern('a*b?[c]') == r'a\*b\?\[c\]')

harness.report()
