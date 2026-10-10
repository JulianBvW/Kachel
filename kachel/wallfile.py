'''Writing tiles.toml from the right-click menu, carefully.

The tile to change is known by the line of its header in the file as it
was when the wall was built. If the file has changed since -- saved from
the editor a moment ago -- that line may mean another tile, so the change
is refused and the wall reloads instead. A change that tomledit cannot
check is never written. Writing goes through a temporary file and a
rename, so the file is never half there.
'''

import os
import shutil
from pathlib import Path

from . import config, tomledit


class WallFile:

    def __init__(self, folder):
        self.path = Path(folder) / config.TILES_FILE
        self._seen = None    # the text the wall was last built from
        self._stale = False  # written since; the wall has the old lines

    def remember(self, text):
        '''Call with the text the wall has just been built from.'''
        self._seen = text
        self._stale = False

    def _read(self):
        try:
            return self.path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return ''
        except (OSError, UnicodeDecodeError):
            return None

    def change(self, *operations):
        '''Apply tomledit operations -> None, or why it was not done.'''
        if self._stale:
            # The wall still shows the lines from before the last change.
            return 'die Wand wird gerade neu aufgebaut, bitte noch einmal'
        text = self._read()
        if text is None:
            return 'tiles.toml ist nicht lesbar'
        if self._seen is not None and text != self._seen:
            return 'tiles.toml wurde gerade geändert, bitte noch einmal'
        new, problem = tomledit.apply(text, *operations)
        if problem:
            return f'kann tiles.toml hier nicht sicher ändern: {problem}'
        # A symlinked tiles.toml (dotfiles) stays a symlink: the real file
        # is replaced, next to where it lives, with its permissions.
        target = self.path.resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.kachel-tmp')
            temporary.write_text(new, encoding='utf-8')
            if target.exists():
                shutil.copymode(target, temporary)
            os.replace(temporary, target)
        except OSError as error:
            return f'tiles.toml konnte nicht geschrieben werden ({error})'
        self._stale = True
        return None
