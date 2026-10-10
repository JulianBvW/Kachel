'''The search bar's text and its scope pill.'''

import harness
from harness import check, section

from kachel import query

section('take_pill')
scope, text, cursor = query.take_pill('@a ', 3)
check('@a + space at the start: the Apps pill, nothing left',
      (scope.code, text, cursor) == ('a', '', 0), (scope, text, cursor))
scope, text, cursor = query.take_pill('minecraft @w ', 13)
check('at the end: Web, the text stays',
      (scope.code, text, cursor) == ('w', 'minecraft ', 10), (text, cursor))
scope, text, cursor = query.take_pill('foo @w bar', 10)
check('in the middle, cursor behind it moves along',
      (scope.code, text, cursor) == ('w', 'foo bar', 7), (text, cursor))
scope, text, cursor = query.take_pill('@W ', 3)
check('case does not count', scope is not None and scope.code == 'w')
for typed in ('@x ', 'a@b.de ', '@w', '@ai ', '@before:2025 '):
    scope, text, _ = query.take_pill(typed, len(typed))
    check(f'{typed!r} stays text', scope is None and text == typed, scope)
scope, text, _ = query.take_pill('@x @a hi', 8)
check('an unknown one before a known one is skipped',
      scope.code == 'a' and text == '@x hi', text)

scope, text, cursor = query.take_pill('= sqrt(2)', 9)
check('= and a space at the start: the calculator pill',
      (scope.code, text, cursor) == ('=', 'sqrt(2)', 7), (scope, text, cursor))
for typed in ('x = 5', '=5', ' = 5', '=='):
    scope, text, _ = query.take_pill(typed, len(typed))
    check(f'{typed!r} stays text', scope is None and text == typed, scope)
check('the calculator pill has a CSS name of its own', query.CALC.css == 'calc')
scope, text, _ = query.take_pill('= vs ==', 7, calc=False)
check('= is text while another pill is there', scope is None and text == '= vs ==')
check('and is never offered for @', all(s.code != '=' for s in query.suggestions('@')))

section('take_extra')
extra, text, cursor = query.take_extra('@type:pdf ', 10)
check('@type:pdf + space: a type pill', (extra.kind, extra.label, text, cursor) == ('type', '.pdf', '', 0), extra)
extra, text, _ = query.take_extra('rechnung @before:2026 ', 22)
check('@before:2026 in the text: a date pill',
      (extra.kind, extra.label, text) == ('before', 'vor 2026', 'rechnung '), extra)
check('its period is the year', extra.period == query.files.parse_date('2026'))
extra, _, _ = query.take_extra('@AFTER:10.11.2025 ', 18)
check('after with a full date, any case', extra.label == 'nach 10.11.2025')
for typed in ('@before:13.2025 ', '@after:abc ', '@type: ', '@type:a/b ', '@before:2025'):
    extra, text, _ = query.take_extra(typed, len(typed))
    check(f'{typed!r} stays text', extra is None and text == typed, extra)

section('word_at')
check('right behind a word', query.word_at('foo @w', 6) == (4, '@w'))
check('inside a word', query.word_at('foo @web', 6) == (4, '@web'))
check('after a space: empty word', query.word_at('foo ', 4) == (4, ''))
check('empty text', query.word_at('', 0) == (0, ''))

section('suggestions')
check('@ alone: every active scope', [s.code for s in query.suggestions('@')] == ['f', 'a', 'w'])
check('@w: only Web', [s.code for s in query.suggestions('@w')] == ['w'])
check('@f: the files', [s.code for s in query.suggestions('@f')] == ['f'])
check('@ai: nothing yet (switched off)', query.suggestions('@ai') == [])
files_scope = query.BY_CODE['f']
check('with @f active, its extra pills come first',
      [s.code for s in query.suggestions('@', files_scope)][:3] == ['type:', 'before:', 'after:'])
check('@b with @f: only before:', [s.code for s in query.suggestions('@b', files_scope)] == ['before:'])
check('extras are not offered without @f', all(':' not in s.code for s in query.suggestions('@')))
before = query.EXTRAS[1]
check('completing an extra leaves the cursor after the colon',
      query.complete('@be', 3, before) == ('@before:', 8))
check('... and keeps a following word apart',
      query.complete('@be foo', 3, before) == ('@before: foo', 8))
check('@before: nothing', query.suggestions('@before:') == [])
check('no @: nothing', query.suggestions('w') == [])

section('complete')
web = query.BY_CODE['w']
check('replaces the word at the cursor',
      query.complete('mine @', 6, web) == ('mine @w ', 8))
check('inside the text, no double space',
      query.complete('@ minecraft', 1, web) == ('@w minecraft', 3))
scope, text, cursor = query.take_pill(*query.complete('@', 1, web))
check('and then becomes the pill', (scope.code, text, cursor) == ('w', '', 0))

harness.report()
