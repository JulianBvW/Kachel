# Kachel

A launcher for the Linux desktop with a tile wall and search.

*Kachel* is German for a tile — the glazed kind on a stove or a bathroom
wall, and the kind that sat on the Windows 10 start menu.

It borrows from that start menu (pinned tiles in four sizes, grouped by
category) but sits in the middle of the screen like Spotlight or Ulauncher.
Large tiles carry shortcuts: a terminal tile with buttons for
`ssh home-server` or `cd ~/Projects/my-app ; claude --resume`, one click each.

## Status

Work in progress. What runs so far is the frame: a resident service and an
empty pane of glass that `F7` shows and hides.

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
is what you want while working on it. `--uninstall` takes everything back off.

Cinnamon only: the shortcut goes through Cinnamon's own keybindings.

## Keys

| Key | |
|---|---|
| `F7` | show or hide |
| `Esc` | hide |

Clicking anywhere else hides it too. Hidden is not closed: the service keeps
running, which is why the window is there the instant the key is pressed.

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
