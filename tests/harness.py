'''The little bit of scaffolding every test script shares.

No pytest: Kachel needs nothing installed beyond what the desktop already
brings, and a test suite that breaks that promise is a strange way to defend
it. Run a test file directly with /usr/bin/python3; it runs every check and
exits non-zero if any of them failed.
'''

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_ok = 0
_failed = 0


def check(name, condition, detail=''):
    global _ok, _failed
    if condition:
        _ok += 1
        print(f'  PASS  {name}')
    else:
        _failed += 1
        print(f'  FAIL  {name}  {detail}')


def section(title):
    print(f'\n{title}')


def report():
    print(f'\n===  {_ok} passed, {_failed} failed  ===')
    sys.exit(1 if _failed else 0)
