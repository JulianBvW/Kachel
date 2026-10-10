# Kachel

A launcher for the Linux desktop with a tile wall and search.

*Kachel* is German for a tile — the glazed kind on a stove or a bathroom
wall, and the kind that sat on the Windows 10 start menu.

It borrows from that start menu (pinned tiles in four sizes, grouped by
category) but sits in the middle of the screen like Spotlight or Ulauncher.
Large tiles carry shortcuts: a terminal tile with buttons for
`ssh home-server` or `cd ~/Projects/my-app ; claude --resume`, one click each.

## Status

Work in progress. What runs so far: a resident service, a pane of glass that
`F7` shows and hides, and the tile wall, read from a file and started with a
click. Search, the icon rail and the shortcuts on large tiles are next.

## Requirements

- Linux Mint / Cinnamon on X11
- Python 3 with PyGObject (`gi`) and GTK 3, as the system Python ships it

## Install

```
git clone git@github.com:JulianBvW/Kachel.git
cd Kachel
/usr/bin/python3 install.py
```

It asks for one thing, the shortcut, and suggests `F7`. The shortcut is
checked against the ones your desktop already holds before it is taken.

`/usr/bin/python3`, not `python3`: on a machine with conda or miniforge in the
PATH the latter has no `gi`, and the script says so rather than failing at the
next login.

The package is copied to `~/.local/share/kachel`, so the clone can be moved or
deleted afterwards. `--in-place` wires it to the current folder instead, which
is what you want while working on it. `--uninstall` takes everything back off,
except your settings in `~/.config/kachel`.

Cinnamon only: the shortcut goes through Cinnamon's own keybindings.

## Keys

| Key | |
|---|---|
| `F7` | show or hide |
| `Esc` | hide |

Clicking anywhere else hides it too. Hidden is not closed: the service keeps
running, which is why the window is there the instant the key is pressed.

## Configuration

No settings dialog: three plain TOML files in `~/.config/kachel/`, written
by hand. Saved changes apply at once. A mistake never stops Kachel -- it is
shown as one line above the wall, the wrong value is replaced by its
default, and everything else still counts. A file that is not TOML at all
leaves the last good wall in place.

On first start Kachel writes commented skeletons. It never overwrites a
file that is there.

**`kachel.toml`** -- the window:

```toml
[window]
columns = 2     # tile columns, 1-4; the width follows (1: 426, 2: 772 px)
height  = 680
```

**`tiles.toml`** -- the wall. `groups` is required; it names the groups and
puts them in order. Every tile says which group it belongs to:

```toml
groups = ["Work", "Games"]

[[tile]]
group = "Work"
app   = "org.gnome.Terminal"     # .desktop ID; the .desktop may be left off
size  = "large"                  # small | medium | wide | large
pos   = [0, 0]                   # [column 0-5, row], optional

[[tile]]
group = "Games"
app   = "steam"
size  = "wide"

[[tile]]
group   = "Work"
name    = "Notes"                # a tile without an app needs name + command
icon    = "theme:accessories-text-editor"
command = "xed ~/notes.txt"
```

Tiles without a `pos` are fitted in, in file order: the first free spot
from the top left. Two helpers:

```
/usr/bin/python3 -m kachel --list-apps   # every app ID, to pin
/usr/bin/python3 -m kachel --grid        # where every tile ended up, and why
```

`--grid` draws each group's grid and marks the tiles that were fitted in
`(auto)` -- copy that position into `pos` to pin it there.

**`rail.toml`** -- folders and actions for the icon rail. Not read yet.

## Blur

The glass needs the BlurCinnamon
extension and an entry for the window class `Kachel` in its settings. The
installer tells you the values, but never writes them itself. Without an
entry Kachel draws a nearly opaque pane instead.

## Tests

Plain scripts, no pytest. Run each file in `tests/` with the system Python:

```
for f in tests/test_*.py; do /usr/bin/python3 "$f"; done
```

## Licence

MIT, see [LICENSE](LICENSE).
