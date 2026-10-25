'''@tldr: reading the pages, and what is shown and copied.'''

import tempfile
import time
import zipfile
from pathlib import Path

import harness
from harness import check, section

from kachel import search, tldr

TAR = '''# tar

> Archiving utility.
> Often combined with a compression method, such as `gzip` or `bzip2`.
> More information: <https://www.gnu.org/software/tar/manual/tar.html>.

- [c]reate an archive and write it to a [f]ile:

`tar cf {{path/to/target.tar}} {{path/to/file1 path/to/file2 ...}}`

- E[x]tract a (compressed) archive [f]ile into the target directory:

`tar xf {{path/to/source.tar.ext}} {{[-C|--directory]}} {{path/to/directory}}`

- Lis[t] the contents of a tar [f]ile [v]erbosely:

`tar tvf {{path/to/source.tar}}`
'''

section('parse')
page = tldr.parse(TAR)
check('the name', page.name == 'tar', page.name)
check('the description, without "More information" and backticks',
      page.description == 'Archiving utility. Often combined with a '
      'compression method, such as gzip or bzip2.', page.description)
check('three examples', len(page.examples) == 3, page.examples)
check('mnemonic brackets go, the colon too',
      [e.text for e in page.examples] == [
          'create an archive and write it to a file',
          'Extract a (compressed) archive file into the target directory',
          'List the contents of a tar file verbosely'],
      [e.text for e in page.examples])
check('the command as written',
      page.examples[2].command == 'tar tvf {{path/to/source.tar}}')
check('brackets on their own stay', tldr.plain('a [range] of') == 'a [range] of')
check('the first description line for the list',
      tldr.description_of(TAR) == 'Archiving utility.')
check('an empty page', tldr.parse('') == tldr.Page('', '', []))

section('pieces and copy_text')
check('a placeholder',
      tldr.pieces('tar tvf {{path/to/source.tar}}')
      == [('tar tvf ', False), ('path/to/source.tar', True)])
check('an option in both forms: the long one, as text',
      tldr.pieces('tar xf {{a}} {{[-C|--directory]}} {{b}}')
      == [('tar xf ', False), ('a', True), (' --directory ', False),
          ('b', True)], tldr.pieces('tar xf {{a}} {{[-C|--directory]}} {{b}}'))
check('two placeholders side by side stay one piece',
      tldr.pieces('{{a}}{{b}}') == [('ab', True)])
check('no placeholder', tldr.pieces('ls -la') == [('ls -la', False)])
check('copied without braces',
      tldr.copy_text('tar xf {{src.tar}} {{[-C|--directory]}} {{dir}}')
      == 'tar xf src.tar --directory dir')
check('nothing to fill in: as it is', tldr.copy_text('ls -la') == 'ls -la')

section('names')
check('spaces become dashes', tldr.page_name(' Git  Commit ') == 'git-commit')
names = ['tail', 'tar', 'star', 'tarsnap', 'git-commit', 'gtar']
check('starts first, then contains, each sorted',
      tldr.matches('tar', names) == ['tar', 'tarsnap', 'gtar', 'star'],
      tldr.matches('tar', names))
check('git commit finds git-commit',
      tldr.matches('git commit', names) == ['git-commit'])
check('nothing typed: nothing', tldr.matches('  ', names) == [])
check('the header counts', search.tldr_header('ta', 2) == 'tldr · 2 Befehle')
check('... one', search.tldr_header('tar', 1) == 'tldr · 1 Befehl')
check('... none', search.tldr_header('xyz ', 0) == 'Keine Seite für „xyz“')

section('the store')
work = Path(tempfile.mkdtemp())
source = work / 'pages.zip'
with zipfile.ZipFile(source, 'w') as archive:
    archive.writestr('common/', '')
    archive.writestr('common/tar.md', TAR)
    archive.writestr('common/ls.md', '# ls\n\n> For every system.\n')
    archive.writestr('linux/ls.md', '# ls\n\n> The Linux one.\n')
    archive.writestr('osx/open.md', '# open\n\n> Only on a Mac.\n')
    archive.writestr('LICENSE.md', 'licence')

_archive, members, descriptions = tldr.read_index(source)
check('linux and common, nothing else', sorted(members) == ['ls', 'tar'],
      sorted(members))
check('linux wins over common', descriptions['ls'] == 'The Linux one.')

calls = []
clock = [time.time()]
cache = work / 'cache' / 'tldr.zip'
store = tldr.TldrStore(on_ready=lambda: calls.append('ready'),
                       call_soon=lambda f: f(),
                       path=cache, url=source.as_uri(),
                       now=lambda: clock[0])
check('nothing there yet', not store.ready and store.page('tar') is None)
store.ensure()
deadline = time.time() + 5
while not calls and time.time() < deadline:
    time.sleep(0.01)
check('fetched and read', store.ready and calls == ['ready'], calls)
check('the zip is in the cache', cache.exists())
check('no part file left', not cache.with_name(cache.name + '.part').exists())
check('a page', store.page('tar') == page)
check('a page that is not there', store.page('open') is None)
check('a description', store.description('ls') == 'The Linux one.')

store.ensure()
check('fresh: nothing started again', not store.busy)

broken = tldr.TldrStore(on_ready=lambda: calls.append('broken'),
                        call_soon=lambda f: f(),
                        path=work / 'other' / 'tldr.zip',
                        url=(work / 'missing.zip').as_uri())
broken.ensure()
deadline = time.time() + 5
while 'broken' not in calls and time.time() < deadline:
    time.sleep(0.01)
check('a failed download says so',
      not broken.ready and broken.problem is not None
      and broken.problem.startswith('tldr-Seiten konnten nicht geladen'),
      broken.problem)
broken.ensure()
check('and is not tried again right away', not broken.busy)

# A week later: fetched again, the pages stay usable meanwhile.
clock[0] += tldr.MAX_AGE + 10
first = cache.stat().st_ino
calls.clear()
store.ensure()
check('the old pages meanwhile', store.page('tar') == page)
deadline = time.time() + 5
while store.busy and time.time() < deadline:
    time.sleep(0.01)
check('a week old: fetched again, quietly (the page shown stays)',
      cache.stat().st_ino != first and calls == [], calls)
check('and read again', store.ready and store.page('ls') is not None)


def wait_for(store, seconds=5):
    deadline = time.time() + seconds
    while store.busy and time.time() < deadline:
        time.sleep(0.01)


# A week on, offline: the pages stay, nothing is re-shown, and the next
# try waits an hour, not a minute.
calls.clear()
store._url = (work / 'missing.zip').as_uri()
clock[0] += tldr.MAX_AGE + 10
store.ensure()
wait_for(store)
check('a failed update: pages stay, no word, nothing re-shown',
      store.ready and store.problem is None and calls == [], calls)
clock[0] += tldr.RETRY + 1
store.ensure()
check('... and no new try a minute later', not store.busy)
tries = []
real_fetch = tldr.fetch
tldr.fetch = lambda *a: tries.append(1) or real_fetch(*a)
clock[0] += tldr.RETRY_UPDATE
store.ensure()
wait_for(store)
tldr.fetch = real_fetch
check('... but an hour later', tries == [1], tries)

# A fresh zip that will not open is fetched again.
damaged = work / 'damaged' / 'tldr.zip'
damaged.parent.mkdir()
damaged.write_bytes(b'not a zip')
fixed = []
repaired = tldr.TldrStore(on_ready=lambda: fixed.append(1),
                          call_soon=lambda f: f(), path=damaged,
                          url=source.as_uri())
repaired.ensure()
wait_for(repaired)
check('a damaged zip is fetched again', repaired.ready and fixed == [1],
      repaired.problem)

# Something other than OSError in the thread: the store still answers.
odd = tldr.TldrStore(on_ready=lambda: None, call_soon=lambda f: f(),
                     path=work / 'odd' / 'tldr.zip', url=source.as_uri())
tldr.fetch = lambda *_: (_ for _ in ()).throw(ValueError('cut off'))
odd.ensure()
wait_for(odd)
tldr.fetch = real_fetch
check('any error ends the work with a problem',
      not odd.busy and odd.problem is not None and 'cut off' in odd.problem,
      odd.problem)

harness.report()
