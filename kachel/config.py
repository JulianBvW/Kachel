'''Constants, all in one place.

Provisional: from phase 2 on, most of these come out of settings.json. Until
then there is nothing to configure, so there is no file to read either.
'''

# D-Bus name. Also what `gapplication action <APP_ID> toggle` addresses.
APP_ID = 'io.github.julianbvw.Kachel'

# WM_CLASS. BlurCinnamon matches the window by this, so it has to be set
# before the first window is created and must never change afterwards.
PRG_NAME = 'kachel'       # instance name  -> WM_CLASS field 1
PROGRAM_CLASS = 'Kachel'  # class name     -> WM_CLASS field 2

# The width is not free: it has to land on the tile grid, so it is derived
# from the number of tile columns (see geometry.window_width).
COLUMNS = 2
HEIGHT = 680

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
