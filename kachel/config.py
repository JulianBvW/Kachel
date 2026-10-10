'''Constants, all in one place.

Everything a user would want to change lives in ~/.config/kachel/ instead
(see settings.py). What stays here are the fixed facts and the defaults that
hold while a setting is missing or broken.
'''

from pathlib import Path

# D-Bus name. Also what `gapplication action <APP_ID> toggle` addresses.
APP_ID = 'io.github.julianbvw.Kachel'

# WM_CLASS. BlurCinnamon matches the window by this, so it has to be set
# before the first window is created and must never change afterwards.
PRG_NAME = 'kachel'       # instance name  -> WM_CLASS field 1
PROGRAM_CLASS = 'Kachel'  # class name     -> WM_CLASS field 2

# The settings folder and its files. Fixed names, no paths to configure.
CONFIG_DIR = Path.home() / '.config' / 'kachel'
GENERAL_FILE = 'kachel.toml'
TILES_FILE = 'tiles.toml'
RAIL_FILE = 'rail.toml'

# Window defaults and bounds. The width is not free: it has to land on the
# tile grid, so it is derived from the number of tile columns.
COLUMNS = 2
COLUMNS_MIN, COLUMNS_MAX = 1, 4
HEIGHT = 680
HEIGHT_MIN, HEIGHT_MAX = 300, 2000

# The pane: dark glass, a hairline edge, rounded corners.
BG_RGBA = (32 / 255, 32 / 255, 36 / 255, 0.60)
BORDER_RGBA = (1.0, 1.0, 1.0, 0.10)
CORNER_RADIUS = 16

# Without a blurred backdrop, 60 % over a busy wallpaper is unreadable.
BG_RGBA_NO_BLUR = (32 / 255, 32 / 255, 36 / 255, 0.92)

# Pressing the shortcut while the window is open may first take the focus
# away (the shortcut is a keyboard grab) and only then deliver the toggle.
# A toggle arriving this soon after a focus-loss hide is taken as "hide",
# which has already happened -- not as "show again".
FOCUS_HIDE_GRACE_MS = 250

# Editors save in bursts (write, rename, change attributes). Wait for the
# folder to be quiet this long before reading the settings again.
RELOAD_DELAY_MS = 200

# The search bar on top and the icon rail on the left. Their size is part
# of the window geometry.
SEARCHBAR_HEIGHT = 56
RAIL_WIDTH = 60
