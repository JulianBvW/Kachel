# Kachel

A launcher for the Linux desktop with a tile wall and search.

*Kachel* is German for a tile — the glazed kind on a stove or a bathroom
wall, and the kind that sat on the Windows 10 start menu.

It borrows from that start menu (pinned tiles in four sizes, grouped by
category) but sits in the middle of the screen like Spotlight or Ulauncher.
Large tiles carry shortcuts: a terminal tile with buttons for
`ssh home-server` or `cd ~/Projects/my-app ; claude --resume`, one click each.

## Status

In daily use, still beside the old menu. Everything described here works: a
resident service, a pane of glass that the Super key or a panel button shows
and hides, the tile wall with shortcut buttons on its large tiles, the search
over apps and files with a calculator and scope pills, short help for
commands from the tldr pages, the icon rail with
folders and actions, the list of all apps, and a right-click menu that
changes the wall in place.

## Requirements

- Linux Mint / Cinnamon on X11
- Python 3 with PyGObject (`gi`) and GTK 3, as the system Python ships it

## Install

```
git clone git@github.com:JulianBvW/Kachel.git
cd Kachel
/usr/bin/python3 install.py
```

It asks two things: the shortcut, suggesting the left Super key (`Super_L`)
and checked against the ones your desktop and its panel applets already
hold, and whether to put the Kachel button on the panel, first on the left
(Enter: yes). A menu that sits there moves one along.

If a menu applet holds the Super key, give it another one first, in its own
settings (right-click it, **Configure**), or type another shortcut, e.g.
`F7`.

`/usr/bin/python3`, not `python3`: on a machine with conda or miniforge in the
PATH the latter has no `gi`, and the script says so rather than failing at the
next login.

The package is copied to `~/.local/share/kachel`, so the clone can be moved or
deleted afterwards. `--in-place` wires it to the current folder instead, which
is what you want while working on it. `--uninstall` takes everything back off,
the panel button included, except your settings in `~/.config/kachel`.

Besides the autostart entry it writes a hidden `.desktop` entry with
Kachel's icon (for its notifications, and for the panel button to start it),
the panel button's applet in `~/.local/share/cinnamon/applets/`, and its two
logos into the icon theme in `~/.local/share/icons/`.

## Panel button

A button on the panel, like the start button of a menu: a click shows or
hides Kachel, exactly as the shortcut does, in the middle of the screen. If
Kachel is not running, the click starts it.

Its icon is Kachel-Windrad, four tiles turning like a pinwheel. To change
it, right-click the button, **Configure**: the group **Kachel** holds
Windrad and Kachel-Layout (a large tile, two small ones and a wide one), the
group **Linux** the usual start button icons, and every other icon of the
theme or any file can be picked too.

Cinnamon only: the shortcut goes through Cinnamon's own keybindings.

## Keys

| Key | |
|---|---|
| `Super` | show or hide (whatever shortcut you installed it with) |
| `Esc` | hide |
| typing | search |
| `↑` `↓` `Enter` | pick a result and run it |
| `Ctrl+1` … `Ctrl+9` | run result 1 to 9 at once |
| `@a␣` `@w␣` `@tldr␣` `=␣` | narrow the search to a scope (see below) |
| `Tab` | take the highlighted `@` suggestion |
| `Backspace` in an empty field | drop the last pill |
| `Ctrl+Enter`, Ctrl+click | show a file in its folder |
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
| `@f` Files | every file on the disk, through plocate (see below) |
| `@w` Web | your words on DuckDuckGo; bangs work (`minecraft !yt`) |
| `@tldr` tldr | short help for a command (see below) |
| `=` Calculator | at the very start: everything is a calculation |

Click the pill, or press Backspace in the empty field, to drop it.

**Files.** The plain search also shows your recently used files: those
whose name starts with what you typed come before the apps, the rest after
them. `@f` searches every file through `plocate` -- all words must appear
in the path, names before folders, home before the rest, newer first. With
nothing typed it lists the recent files. Narrow it with extra pills:
`@type:pdf`, `@before:2025`, `@after:10.11.2025` (dates as `YYYY`,
`MM.YYYY`, `DD.MM.YYYY` or `MM/DD/YYYY`; the date itself never counts, so
`@before:2026` ends on 31.12.2025). Enter opens a file, Ctrl+Enter or
Ctrl+click shows it in its folder.

**tldr.** `@tldr tar` shows the [tldr page](https://tldr.sh) for `tar` in
place of the list: what it does, and one row per example with the command
in a chip, placeholders in italics. `↑` `↓` pick an example; Enter, a click
or `Ctrl+1` … `Ctrl+9` copies it -- placeholders without their braces, an
option given in both forms (`{{[-C|--directory]}}`) in its long one -- and
hides Kachel. A name that is not exact lists the commands that fit
(`@tldr ta`); spaces count as dashes, so `@tldr git commit` is the page
`git-commit`. Only the English pages for Linux and every system are used.
They come as one zip (about 3,5 MB) from the tldr project into
`~/.cache/kachel/` the first time `@tldr` is used, and again when it is a
week old -- fetched in the background, read where it lies. Nothing is
installed.

`plocate`'s database is updated once a day, so a file from this morning
may only turn up tomorrow (`sudo updatedb` to hurry it) -- unless you
opened it, then it is among the recent ones. System folders, caches and
the like are left out; the list is in `kachel.toml` under `[files]`.

## All apps

The button on the right of the search bar slides the wall aside for a list
of every app, A to Z. Apps that are on the wall show their group on the
right. The letters down the right edge jump to their section -- click one,
or hold the button and drag along them. The button again slides the wall
back.

## Right-click

Right-click a tile, a result, an app in the list, the empty wall or the
rail for a menu:

| On | |
|---|---|
| an app | its own actions (New Window …), pin to the wall ▸ group (or take it off), add to the panel, to the desktop, to the favourites, uninstall |
| a tile | its actions, size, move to another group ▸, move within the group, take off the wall (with its shortcuts), show in `tiles.toml`, and the app entries above |
| a file | open with ▸, show in folder, copy path, open a terminal there, move to the trash (click twice) |
| the empty wall | edit `tiles.toml`, open the settings folder `~/.config/kachel` |
| the rail | edit `rail.toml`, open the settings folder |

Everything that changes the wall edits `tiles.toml` in place: only the
lines of that tile, its `size` or `group`, or the `groups` list change;
comments and layout stay. Each change is read back before it is written,
and one that cannot be made safely is not written at all. Esc closes the
menu; the menu key or Shift+F10 opens it for the selected result.

**Move** picks a tile up: a faint copy follows the pointer, a dashed
frame shows the cell it would land on, and its group gets empty rows below
for the time being. A left click puts it there and the others make room;
a right click or Esc puts it back. Where a new order of the tiles in
`tiles.toml` gets it there, only the order changes; otherwise the tile
gets a `pos`, and a tile with a `pos` in its way loses its own.

## Configuration

No settings dialog: three plain TOML files in `~/.config/kachel/`, written
by hand. Saved changes apply at once. A mistake never stops Kachel -- it is
shown as one line above the wall, the wrong value is replaced by its
default, and everything else still counts. A file that is not TOML at all
leaves the last good wall in place.

On first start Kachel writes commented skeletons. It never overwrites a
file that is there.

**`kachel.toml`** -- effects and the window:

```toml
animations = "system"   # true | false | "system" (Cinnamon's desktop effects)

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
second click before it reaches the top runs the action -- a double-click
too -- and moving away disarms it. `confirm = true` takes the defaults ("Sicher?", red, 4000 ms);
a table can set `label`, `color` (`#rrggbb`, `#rrggbbaa` or `rgba(...)`)
and `duration` (500-60000 ms).

Leave out every `[[folder]]` (or every `[[action]]`) and the defaults come
back; `folder = []` means none at all. `--grid` lists the rail too.

## Animations

Small and quick, none on opening -- that would be a wait every time:

- the ring and fill of whatever is under the pointer fade in and out; a
  tile stays lit a moment, and tiles a fast pointer flew over light up
  briefly too, so a quick sweep shows every tile it crossed,
- a soft light follows the pointer over a tile,
- a tile's icon grows a little under the pointer, a rail icon and an app's
  icon in the list too (there its own plate gives way to the row's),
- a pressed tile, row or rail entry sinks in and its icon shrinks,
- tiles glide into place after a move,
- the rail's action page and the app list slide.

`animations = false` turns off all but the slides and the rising fill of an
action that asks twice, which carry meaning. `"system"` follows Cinnamon's
desktop effects, also while Kachel runs.

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
