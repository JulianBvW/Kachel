'''Icons: Material Symbols for the chrome, the icon theme for the apps.

Every icon field takes one of three forms:

    ms:power_settings_new    a symbol from the bundled icon font
    theme:system-shutdown    a named icon from the icon theme
    /path/to/picture.svg     a file

The icon font ships in kachel/fonts and is loaded for this process only.
Nothing gets installed; `fc-list` never hears of it.
'''

import ctypes
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gio, Gtk, Pango, PangoCairo  # noqa: E402

FONT_DIR = Path(__file__).resolve().parent / 'fonts'
FONT_FILES = ('MaterialSymbolsRounded.ttf', 'MaterialSymbolsRoundedFilled.ttf')
OUTLINE = 'Material Symbols Rounded'
FILLED = 'Material Symbols Rounded Filled'

# Stand-ins from the icon theme for the symbols Kachel's own chrome uses, in
# case the font could not be loaded. Monochrome, like the symbols.
FALLBACK = {
    'search': 'system-search-symbolic',
    'close': 'window-close-symbolic',
    'apps': 'view-app-grid-symbolic',
    'calculate': 'accessories-calculator-symbolic',
    'public': 'web-browser-symbolic',
}
GENERIC_ICON = 'application-x-executable'

_available = None


def load_fonts():
    '''Make the bundled font known to this process. True if it worked.

    Has to run before Pango first looks at the fonts: the font map is built
    once, from whatever fontconfig knows at that moment.
    '''
    try:
        fontconfig = ctypes.CDLL('libfontconfig.so.1')
    except OSError:
        return False
    add = fontconfig.FcConfigAppFontAddFile
    add.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    add.restype = ctypes.c_int
    ok = True
    for name in FONT_FILES:
        path = FONT_DIR / name
        # None: the current configuration, the one Pango is about to use.
        if not path.is_file() or not add(None, str(path).encode()):
            ok = False
    return ok


def reload_fonts():
    '''Load the font again after fontconfig built itself a new config.

    Kachel runs all session. When fonts are installed or removed, GTK
    throws the font configuration away and builds a fresh one -- without
    fonts added the way ours are. Hooked to that moment by the window.
    '''
    global _available
    ok = load_fonts()
    font_map = PangoCairo.FontMap.get_default()
    if hasattr(font_map, 'config_changed'):
        font_map.config_changed()
    _available = None
    return ok


def ms_available():
    '''Can Pango draw Material Symbols? Asked once.'''
    global _available
    if _available is None:
        families = {family.get_name() for family in
                    PangoCairo.FontMap.get_default().list_families()}
        # Both, or neither: half a font would draw some symbols as words.
        _available = OUTLINE in families and FILLED in families
    return _available


def parse_icon(spec):
    '''('ms', name), ('theme', name), ('file', path) or None.'''
    if not isinstance(spec, str) or not spec.strip():
        return None
    spec = spec.strip()
    if spec.startswith('ms:'):
        name = spec[len('ms:'):].strip()
        return ('ms', name) if name else None
    if spec.startswith('theme:'):
        name = spec[len('theme:'):].strip()
        return ('theme', name) if name else None
    return ('file', spec)


def symbol(name, px, filled=False):
    '''A label showing one Material Symbol, `px` pixels high.

    The font draws a symbol for the name itself: 'search' is a ligature
    that turns into the magnifier glyph.
    '''
    label = Gtk.Label(label=name)
    family = FILLED if filled else OUTLINE
    attributes = Pango.AttrList()
    attributes.insert(Pango.attr_font_desc_new(
        Pango.FontDescription.from_string(f'{family} {px}px')))
    label.set_attributes(attributes)
    label.get_style_context().add_class('ms-icon')
    label.set_size_request(px, px)
    return label


def _image(gicon, px):
    image = Gtk.Image.new_from_gicon(gicon, Gtk.IconSize.DIALOG)
    image.set_pixel_size(px)
    return image


def icon_widget(spec, px, fallback=None, base=None, filled=False):
    '''A widget for an icon field, `px` pixels high.

    `fallback` is a Gio.Icon for when the field is empty or does not work
    out (for a tile: its app's icon). A relative file path is taken
    relative to `base`, the settings folder.
    '''
    parsed = parse_icon(spec)
    if parsed is not None:
        kind, value = parsed
        if kind == 'ms':
            if ms_available():
                return symbol(value, px, filled)
            if value in FALLBACK:
                return _image(Gio.ThemedIcon.new(FALLBACK[value]), px)
        elif kind == 'theme':
            return _image(Gio.ThemedIcon.new(value), px)
        else:
            path = Path(base or Path.home()) / Path(value).expanduser()
            if path.is_file():
                return _image(Gio.FileIcon.new(
                    Gio.File.new_for_path(str(path))), px)
    if fallback is not None:
        return _image(fallback, px)
    return _image(Gio.ThemedIcon.new(GENERIC_ICON), px)
