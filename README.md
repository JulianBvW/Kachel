# Kachel

A launcher for the Linux desktop with a tile wall and search.

*Kachel* is German for a tile — the glazed kind on a stove or a bathroom
wall, and the kind that sat on the Windows 10 start menu.

It borrows from that start menu (pinned tiles in four sizes, grouped by
category) but sits in the middle of the screen like Spotlight or Ulauncher.
Large tiles carry shortcuts: a terminal tile with buttons for
`ssh home-server` or `cd ~/Projects/my-app ; claude --resume`, one click each.

## Status

Work in progress. Nothing here runs yet.

## Requirements

- Linux Mint / Cinnamon on X11
- Python 3 with PyGObject (`gi`) and GTK 3, as the system Python ships it

## Install

To be written once there is something to install.

## Tests

Plain scripts, no pytest. Run each file in `tests/` with the system Python:

```
for f in tests/test_*.py; do /usr/bin/python3 "$f"; done
```

## Licence

MIT, see [LICENSE](LICENSE).
