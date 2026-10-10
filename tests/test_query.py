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
for typed in ('@x ', 'a@b.de ', '@w', '@f ', '@before:2025 '):
    scope, text, _ = query.take_pill(typed, len(typed))
    check(f'{typed!r} stays text', scope is None and text == typed, scope)
scope, text, _ = query.take_pill('@x @a hi', 8)
check('an unknown one before a known one is skipped',
      scope.code == 'a' and text == '@x hi', text)

section('word_at')
check('right behind a word', query.word_at('foo @w', 6) == (4, '@w'))
check('inside a word', query.word_at('foo @web', 6) == (4, '@web'))
check('after a space: empty word', query.word_at('foo ', 4) == (4, ''))
check('empty text', query.word_at('', 0) == (0, ''))

section('suggestions')
check('@ alone: every active scope', [s.code for s in query.suggestions('@')] == ['a', 'w'])
check('@w: only Web', [s.code for s in query.suggestions('@w')] == ['w'])
check('@f: nothing yet (switched off)', query.suggestions('@f') == [])
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
