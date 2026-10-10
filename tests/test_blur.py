'''Reading BlurCinnamon's settings: is there an active entry for Kachel?'''

import copy

import harness
from harness import check, section

from kachel import blur


def entry(application, enabled=True):
    return {'enabled': enabled, 'application': application,
            'override': True, 'blurtype': 8, 'radius': 18}


# Shaped like the real file: every setting wrapped as {'value': ...}.
GOOD = {
    'enable-window-effects': {'type': 'switch', 'value': True},
    'windows-inclusion-list': {'type': 'list', 'value': [
        entry('Default window settings', enabled=False),
        entry('Zettel'),
        entry('Kachel'),
    ]},
}

section('entry_active')
check('active entry for Kachel', blur.entry_active(GOOD, 'Kachel'))
check('other application is not us', not blur.entry_active(GOOD, 'Nemo'))
check('name must match exactly', not blur.entry_active(GOOD, 'kachel'))

data = copy.deepcopy(GOOD)
data['windows-inclusion-list']['value'][2]['enabled'] = False
check('entry switched off', not blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
del data['windows-inclusion-list']['value'][2]
check('no entry at all', not blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
data['enable-window-effects']['value'] = False
check('window effects switched off globally',
      not blur.entry_active(data, 'Kachel'))

section('malformed input counts as no')
check('None', not blur.entry_active(None, 'Kachel'))
check('a list instead of a dict', not blur.entry_active([], 'Kachel'))
check('empty dict', not blur.entry_active({}, 'Kachel'))

data = copy.deepcopy(GOOD)
data['enable-window-effects'] = True
check('setting not wrapped in {value}', not blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
data['enable-window-effects']['value'] = 'true'
check('string instead of boolean', not blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
data['windows-inclusion-list']['value'] = 'Kachel'
check('list value is a string', not blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
data['windows-inclusion-list']['value'].insert(0, 'junk')
check('junk entries are skipped, the real one still counts',
      blur.entry_active(data, 'Kachel'))

data = copy.deepcopy(GOOD)
data['windows-inclusion-list']['value'][2]['enabled'] = 1
check('enabled must be a real boolean', not blur.entry_active(data, 'Kachel'))

harness.report()
