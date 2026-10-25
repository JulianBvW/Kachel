'''@tldr: short help for a command, from the tldr pages.

The pages come as the official zip of the English pages, fetched once into
~/.cache/kachel and again when it is a week old -- only when @tldr is used.
The zip is read where it lies, nothing unpacked. Fetching and indexing run
in a thread (Design ④); the window asks again once they are done.

Only the pages for Linux and for every system are used; with both, the
Linux one wins.
'''

import os
import re
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

URL = ('https://github.com/tldr-pages/tldr/releases/latest/download/'
       'tldr-pages.en.zip')
CACHE = Path.home() / '.cache' / 'kachel' / 'tldr-pages.en.zip'
PLATFORMS = ('linux', 'common')   # the first one wins
MAX_AGE = 7 * 24 * 3600           # seconds before it is fetched again
TIMEOUT = 30
RETRY = 60                        # seconds between tries without pages
RETRY_UPDATE = 3600               # ... and between failed weekly updates
CHUNK = 1 << 16


# -- the page --------------------------------------------------------------

@dataclass(frozen=True)
class Example:
    text: str       # what it does
    command: str    # as the page writes it, placeholders in {{ }}


@dataclass(frozen=True)
class Page:
    name: str
    description: str
    examples: list = field(default_factory=list)


# `[c]reate`, `g[z]ipped`: the letter an option comes from. Only right next
# to a word, so brackets that stand on their own stay.
MNEMONIC = re.compile(r'(?<=\w)\[(\w+)\]|\[(\w+)\](?=\w)')
PLACEHOLDER = re.compile(r'\{\{(.*?)\}\}')
# `{{[-v|--verbose]}}`: an option in its short and long form, not something
# to fill in.
OPTION = re.compile(r'^\[(-[^|\]]*)\|(-[^\]]*)\]$')


def plain(text):
    '''Text from the page without mnemonic brackets and backticks.'''
    text = MNEMONIC.sub(lambda m: m[1] or m[2], text)
    return text.replace('`', '')


def parse(text):
    '''A Page from the Markdown of a tldr page.'''
    name, description, examples = '', [], []
    pending = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('# '):
            name = line[2:].strip()
        elif line.startswith('>'):
            part = line[1:].strip()
            if not part.lower().startswith('more information'):
                description.append(plain(part))
        elif line.startswith('- '):
            pending = plain(line[2:].strip().rstrip(':'))
        elif (len(line) > 1 and line.startswith('`') and line.endswith('`')
              and pending is not None):
            examples.append(Example(pending, line[1:-1]))
            pending = None
    return Page(name, ' '.join(description), examples)


def description_of(text):
    '''Only the first line of the description, for the list of names.'''
    for line in text.splitlines():
        if line.startswith('>'):
            return plain(line[1:].strip())
    return ''


def pieces(command):
    '''[(text, is_placeholder)] for showing a command. An option given in
    both forms is shown, and copied, in its long one.'''
    out = []

    def add(text, placeholder):
        if out and out[-1][1] == placeholder:
            out[-1] = (out[-1][0] + text, placeholder)
        elif text:
            out.append((text, placeholder))

    end = 0
    for match in PLACEHOLDER.finditer(command):
        add(command[end:match.start()], False)
        option = OPTION.match(match[1])
        if option:
            add(option[2], False)
        else:
            add(match[1], True)
        end = match.end()
    add(command[end:], False)
    return out


def copy_text(command):
    '''The command as it is copied: placeholders without their braces.'''
    return ''.join(text for text, _placeholder in pieces(command))


def page_name(typed):
    '''`Git Commit` -> `git-commit`, the way the pages are named.'''
    return '-'.join(typed.lower().split())


def matches(typed, names):
    '''The names that start with what is typed, then those that hold it;
    each part alphabetically.'''
    key = page_name(typed)
    if not key:
        return []
    start = sorted(n for n in names if n.startswith(key))
    inside = sorted(n for n in names if key in n and not n.startswith(key))
    return start + inside


# -- the pages on disk -----------------------------------------------------

def read_index(path):
    '''(zip, {name: member}, {name: first description line}) for the zip at
    `path`. Raises when the zip cannot be read.'''
    archive = zipfile.ZipFile(path)
    try:
        members, descriptions = {}, {}
        for platform in reversed(PLATFORMS):   # the first one overwrites
            prefix = platform + '/'
            for member in archive.namelist():
                if member.startswith(prefix) and member.endswith('.md'):
                    name = member[len(prefix):-3]
                    if '/' not in name:
                        members[name] = member
        for name, member in members.items():
            descriptions[name] = description_of(
                archive.read(member).decode('utf-8', 'replace'))
    except BaseException:
        archive.close()
        raise
    return archive, members, descriptions


def fetch(path, url=URL):
    '''Download the zip next to `path`, check it, then put it in place --
    a failed download leaves the old one alone.'''
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + '.part')
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as answer, \
                open(part, 'wb') as out:
            while True:
                chunk = answer.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
        with zipfile.ZipFile(part) as archive:
            if archive.testzip() is not None:
                raise zipfile.BadZipFile('damaged download')
        os.replace(part, path)
    finally:
        if part.exists():
            part.unlink()


class TldrStore:
    '''The tldr pages, once they are there.

    `ensure()` starts what is missing: fetching (no file, or a week old)
    and reading the index. Both in a thread; `on_ready()` comes on the main
    thread when there is something new -- pages or a problem. `call_soon`
    hands work to the main thread (GLib.idle_add in the window).
    '''

    def __init__(self, on_ready, call_soon, path=CACHE, url=URL,
                 now=time.time):
        self._on_ready = on_ready
        self._call_soon = call_soon
        self._path = Path(path)
        self._url = url
        self._now = now
        self._archive = None
        self._members = {}
        self._descriptions = {}
        self._fetched_at = None   # the zip's mtime when it was read
        self._working = False
        self._tried_at = float('-inf')
        self.problem = None

    @property
    def ready(self):
        return self._archive is not None

    @property
    def busy(self):
        return self._working

    def ensure(self):
        if self._working:
            return
        if self.ready:
            # Known since it was read: no disk access on every key.
            if self._now() - self._fetched_at <= MAX_AGE:
                return
            stale, wait = True, RETRY_UPDATE
        else:
            try:
                age = self._now() - self._path.stat().st_mtime
            except OSError:
                age = None
            stale, wait = age is None or age > MAX_AGE, RETRY
        # After a try that did not work out (no network, say): not again
        # on every key, but a while later.
        if self._now() - self._tried_at < wait:
            return
        self._working = True
        self._tried_at = self._now()
        threading.Thread(target=self._work, args=(stale,),
                         daemon=True).start()

    def _work(self, stale):
        index, problem = None, None
        try:
            if stale:
                problem = self._fetch()
            if problem is None or not self.ready:
                index, unreadable = self._read()
                if index is None and not stale:
                    # A zip that will not open is no better than none.
                    problem = self._fetch()
                    if problem is None:
                        index, unreadable = self._read()
                problem = problem or unreadable
        except Exception as error:   # whatever it is, the window must hear
            problem = f'tldr-Seiten: {error}'
        finally:
            self._call_soon(lambda: self._store(index, problem))

    def _fetch(self):
        '''Download; None, or what went wrong.'''
        try:
            fetch(self._path, self._url)
            return None
        except Exception as error:
            # urllib wraps the real cause: 'no network', not '<urlopen
            # error [Errno -3] ...>'.
            reason = getattr(error, 'reason', None) or error
            return f'tldr-Seiten konnten nicht geladen werden: {reason}'

    def _read(self):
        '''(index, None), or (None, what went wrong).'''
        try:
            mtime = self._path.stat().st_mtime
            return (*read_index(self._path), mtime), None
        except Exception as error:
            return None, f'tldr-Seiten lassen sich nicht lesen: {error}'

    def _store(self, index, problem):
        self._working = False
        first = not self.ready
        if index is not None:
            if self._archive is not None:
                self._archive.close()
            (self._archive, self._members, self._descriptions,
             self._fetched_at) = index
        # With pages at hand, a failed update is not worth a word.
        problem = None if self.ready else problem
        # Only the first pages and a new problem change what is shown; a
        # weekly update must not reset the page being read.
        changed = (first and self.ready) or problem != self.problem
        self.problem = problem
        if changed:
            self._on_ready()
        return False

    def names(self):
        return self._members.keys()

    def description(self, name):
        return self._descriptions.get(name, '')

    def page(self, name):
        '''The Page called `name`, or None.'''
        member = self._members.get(name)
        if member is None or self._archive is None:
            return None
        try:
            text = self._archive.read(member).decode('utf-8', 'replace')
        except Exception:   # a damaged member: as if it were not there
            return None
        return parse(text)
