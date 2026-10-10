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
`F7` shows and hides, the tile wall read from a file with shortcut buttons
on its large tiles, the search over every installed app, with a
calculator, the icon rail with folders and actions, and the list of all
apps.

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
| typing | search |
| `↑` `↓` `Enter` | pick a result and run it |
| `Ctrl+1` … `Ctrl+9` | run result 1 to 9 at once |
| `@a␣` `@w␣` `=␣` | narrow the search to a scope (see below) |
| `Tab` | take the highlighted `@` suggestion |
| `Backspace` in an empty field | drop the scope pill |
| `Ctrl+Backspace` | clear the search and the pill, back to the tiles |

Clicking anywhere else hides it too. Hidden is not closed: the service keeps
running, which is why the window is there the instant the key is pressed.

## Search

Typing replaces the wall with a list of results: every installed app, pinned
or not, matched by name, generic name, keywords and program name -- and by
letters in order, so `gmp` finds GIMP. A sum like `3,5*2` is worked out
(comma or point, as you like); Enter copies the answer.

The calculator knows more than the four basic operations:

| | |
|---|---|
| functions | `sqrt` or `√`, `ln`, `log` (base 10), `log2`, `log(x; b)`, `exp`, `abs`, `round(x; n)`, `floor`, `ceil`, `min(a; b; …)`, `max(…)` |
| angles | `sin cos tan asin acos atan` in degrees, `sinr cosr tanr asinr acosr atanr` in radians, `rad()` and `deg()` to convert |
| constants | `pi` or `π`, `e`, `tau`, `g` (9,80665), `c` (299792458) |
| operators | `+ - * / ^`, `%` (remainder), `!` (factorial), brackets |
| numbers | `1,5` or `1.5`, `1e6`, `2,5e-3`, `0xff`, `0b1010` |

Arguments are separated by `;`, because the comma is a decimal mark. A
function with one argument also works without brackets: `sqrt 2`, `sin 30`.
In the plain search only an obvious calculation counts -- a digit and an
operation -- so `pi` alone still looks for apps. Start with `= ` for the
calculator pill: there everything is a calculation, and what does not
work says why. With no hit at all,
Enter searches the web instead. The list scrolls and loads more as you go.

A scope narrows the search. Type its abbreviation and a space and it turns
into a pill in front of the field; typing `@` alone lists the scopes.

| Scope | |
|---|---|
| `@a` Apps | apps only, no calculator; with nothing typed, every app from A to Z |
| `@w` Web | your words on DuckDuckGo; bangs work (`minecraft !yt`) |
| `=` Calculator | at the very start: everything is a calculation |

Click the pill, or press Backspace in the empty field, to drop it. Files
(`@f`) are next.

## All apps

The button on the right of the search bar slides the wall aside for a list
of every app, A to Z. Apps that are on the wall show their group on the
right. The letters down the right edge jump to their section -- click one,
or hold the button and drag along them. The button again slides the wall
back.

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

Large and wide tiles carry **shortcuts**: buttons that run a command of
their own instead of starting the app -- up to four on a large tile, two on
a wide one. A `[[tile.shortcut]]` belongs to the tile right above it:

```toml
[[tile]]
group = "Work"
app   = "com.mitchellh.ghostty"
size  = "large"

[[tile.shortcut]]
name     = "home-server"          # shown as "› home-server" on hover
icon     = "ms:dns"               # any Material Symbol; default ms:bolt
command  = "ssh home-server"
terminal = true                   # default false: runs quietly

[[tile.shortcut]]
name     = "claude"
icon     = "ms:bolt"
command  = "cd ~/Projects/my-app ; claude --resume"
terminal = true
```

With `terminal = true` the command runs in the default terminal (as set in
Cinnamon's preferred applications), and when it ends your shell takes over
the window, in the folder the command left it in. Without it, the command
runs quietly through `sh`.

Tiles without a `pos` are fitted in, in file order: the first free spot
from the top left. Two helpers:

```
/usr/bin/python3 -m kachel --list-apps   # every app ID, to pin
/usr/bin/python3 -m kachel --grid        # where every tile ended up, and why;
                                         # and what the rail shows
```

`--grid` draws each group's grid, lists every tile with its shortcuts, and
marks the tiles that were fitted in `(auto)` -- copy that position into
`pos` to pin it there. All messages about the files are printed at the end.

Every `icon` takes one of three forms: `ms:<symbol>` for any of the
Material Symbols (browse them at fonts.google.com/icons), `theme:<name>` for
an icon from your icon theme, or a path to an image file, relative to
`~/.config/kachel/`. Without one, a tile shows its app's icon.

**`rail.toml`** -- the rail on the left: folders on top, actions at the
bottom. The entries carry no text; hovering one shows its name beside the
rail. The skeleton spells out the defaults -- your home, documents,
downloads, pictures, music, videos and desktop, and six actions:

| Page 1 | Page 2 |
|---|---|
| Settings -- `cinnamon-settings` | Restart -- `systemctl reboot` (asks first) |
| Suspend -- `systemctl suspend` | Log out -- `cinnamon-session-quit --logout --no-prompt` |
| Power off -- `systemctl poweroff` (asks first) | Lock -- `cinnamon-screensaver-command --lock` |
| More → | ← Back |

```toml
[[folder]]
path = "@XDG_DOWNLOAD_DIR"        # the system's own folder, and its name
icon = "ms:download"

[[folder]]
name = "Kachel"                   # default: the folder's own name
path = "~/Projects/Kachel"
icon = "ms:code"                  # default ms:folder

[[action]]
name    = "Power off"
icon    = "ms:power_settings_new"   # default ms:bolt
command = "systemctl poweroff"
confirm = { label = "Really power off?", color = "#ef666180", duration = 4000 }
```

A folder's `path` is `~/...`, an absolute path, or one of the system's
folders as `@XDG_DOCUMENTS_DIR` (also `DOWNLOAD`, `PICTURES`, `MUSIC`,
`VIDEOS`, `DESKTOP`, `TEMPLATES`, `PUBLICSHARE`). Those are looked up, so
the defaults are right in any language. As many folders fit as the window
height allows (10 at 680 px).

At most six actions, in file order. Up to four fit on one page; with five
or six, the fourth place turns to a second page. An action takes
`terminal = true` like a shortcut. With `confirm`, the first click only
arms it: the icon turns into a check mark and a coloured fill rises; a
second click before it reaches the top runs the action, moving away
disarms it. `confirm = true` takes the defaults ("Sicher?", red, 4000 ms);
a table can set `label`, `color` (`#rrggbb`, `#rrggbbaa` or `rgba(...)`)
and `duration` (500-60000 ms).

Leave out every `[[folder]]` (or every `[[action]]`) and the defaults come
back; `folder = []` means none at all. `--grid` lists the rail too.

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

The icon font in `kachel/fonts` is Google's Material Symbols Rounded, under
the Apache License 2.0 (see `kachel/fonts/LICENSE`). It is loaded for Kachel
alone; nothing is installed on the system.
