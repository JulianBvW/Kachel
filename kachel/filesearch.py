'''Looking for files: the recent ones, and everything else through plocate.

plocate runs in a thread, so the window never waits for it. Every search
gets a generation number; an answer whose search has been overtaken by
the next keystroke is dropped.
'''

import os
import stat
import subprocess
import threading
import time

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk  # noqa: E402

from . import files  # noqa: E402
from .files import FileHit  # noqa: E402

MAX_CANDIDATES = 5000    # after the exclude list; then plocate is stopped
TIMED = 300              # without a date bound, only these get an mtime
CHUNK = 1 << 16


class Recent:
    '''The recently used files, as GTK keeps them.

    Which ones still exist is looked up in a thread, at the start and
    whenever the list changes: a recent file on a network share that has
    gone to sleep would otherwise stall the window on a stat(). Until
    then, the last answer stands.'''

    def __init__(self):
        self._manager = Gtk.RecentManager.get_default()
        self._manager.connect('changed', lambda _m: self._refresh())
        self._hits = []
        self._generation = 0
        self._refresh()

    def hits(self):
        '''Newest use first.'''
        return self._hits

    def _refresh(self):
        items = sorted(self._manager.get_items(),
                       key=lambda item: item.get_modified(), reverse=True)
        paths = []
        for item in items:
            uri = item.get_uri()
            if uri.startswith('file://'):
                try:
                    paths.append(GLib.filename_from_uri(uri)[0])
                except GLib.Error:
                    pass
        self._generation += 1
        generation = self._generation
        threading.Thread(target=self._look, args=(generation, paths),
                         daemon=True).start()

    def _look(self, generation, paths):
        hits, seen = [], set()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            try:
                info = os.stat(path)
            except OSError:
                continue
            hits.append(FileHit(path, stat.S_ISDIR(info.st_mode),
                                info.st_mtime))

        def store():
            if generation == self._generation:
                self._hits = hits
            return GLib.SOURCE_REMOVE
        GLib.idle_add(store)


class FileSearch:
    '''`on_done(hits, truncated, problem)` with the answer to the latest
    search, on the main thread.'''

    def __init__(self, on_done, verbose=False):
        self._on_done = on_done
        self._verbose = verbose
        self._generation = 0
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._generation += 1

    def start(self, typed, words, types, before, after, excluder, home):
        '''`typed`: the words as typed, for plocate, which only ignores
        case -- 'Straße' has to reach it as such. `words`: normalized,
        for ranking.'''
        with self._lock:
            self._generation += 1
            generation = self._generation
        threading.Thread(
            target=self._run, daemon=True,
            args=(generation, typed, words, types, before, after, excluder,
                  str(home))).start()

    def _current(self, generation):
        with self._lock:
            return generation == self._generation

    def _run(self, generation, typed, words, types, before, after, excluder,
             home):
        t0 = time.monotonic()
        patterns = [files.escape_pattern(w) for w in typed]
        if len(types) == 1:
            # One type narrows plocate itself; several are an 'or', which
            # its 'and' cannot say -- those are only checked below.
            patterns.append('.' + files.escape_pattern(types[0].lstrip('.')))

        # Two passes: first the words in the file name alone (-b), then
        # anywhere in the path. The candidates are capped, and in database
        # order the folder-only matches could fill the cap before the
        # file that is called what was typed.
        hits, seen, truncated = [], set(), False
        for basename in ((True, False) if typed else (False,)):
            try:
                truncated = self._collect(generation, patterns, basename,
                                          types, excluder, hits, seen)
            except OSError:
                self._deliver(generation, [], False, 'plocate fehlt')
                return
            if truncated or not self._current(generation):
                break
        if not self._current(generation):
            return
        t1 = time.monotonic()

        if before or after:
            # Every candidate needs its date to be judged.
            hits = [hit for hit in hits if self._stat(hit)
                    and files.date_ok(hit.mtime, before, after)]
        else:
            hits.sort(key=lambda hit: files.tier(hit.path, words, home))
            hits = [hit for hit in hits[:TIMED] if self._stat(hit)] + \
                hits[TIMED:]
        hits = files.rank(hits, words, home)
        if self._verbose:
            print(f'[kachel] files: {len(hits)} hits, plocate+filter '
                  f'{(t1 - t0) * 1000:.0f} ms, stat+rank '
                  f'{(time.monotonic() - t1) * 1000:.0f} ms', flush=True)
        self._deliver(generation, hits, truncated, None)

    def _collect(self, generation, patterns, basename, types, excluder,
                 hits, seen):
        '''One plocate run into `hits`. True when the cap is reached.

        -e leaves out what is gone since the last updatedb; read1 hands
        over whatever is there, so an overtaken search notices soon.'''
        args = ['plocate', '-i', '-0', '-e'] + (['-b'] if basename else [])
        process = subprocess.Popen(args + patterns, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        rest = b''
        try:
            while self._current(generation):
                chunk = process.stdout.read1(CHUNK)
                if not chunk:
                    break
                *paths, rest = (rest + chunk).split(b'\0')
                for raw in paths:
                    path = os.fsdecode(raw)
                    if path in seen or excluder.excluded(path) or \
                            not files.has_type(path, types):
                        continue
                    seen.add(path)
                    hits.append(FileHit(path))
                    if len(hits) >= MAX_CANDIDATES:
                        return True
        finally:
            if process.poll() is None:
                process.kill()
            process.stdout.close()
            process.wait()
        return False

    @staticmethod
    def _stat(hit):
        '''Fill in mtime and folder (through a link, as Recent does).
        False for a file that is gone.'''
        try:
            info = os.stat(hit.path)
        except OSError:
            return False
        hit.mtime = info.st_mtime
        hit.folder = stat.S_ISDIR(info.st_mode)
        return True

    def _deliver(self, generation, hits, truncated, problem):
        def deliver():
            if self._current(generation):
                self._on_done(hits, truncated, problem)
            return GLib.SOURCE_REMOVE
        GLib.idle_add(deliver)
