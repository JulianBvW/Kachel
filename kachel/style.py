'''The style sheet: colour tokens plus sizes relative to the system font.

No font is shipped. Everything is set in the system font, and every size is
the system size plus or minus a few points, so changing the font in the
system settings changes Kachel along with everything else.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gio, Gtk, Pango  # noqa: E402

from . import anim, query  # noqa: E402

FALLBACK_SIZE = 10.0   # points, if the font name carries no size

TEMPLATE = '''
.kachel-root {{
  color: #F3F3F3;
  font-size: {base}pt;
}}

.kachel-searchbar {{
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}}

.kachel-rail {{
  background-color: rgba(0, 0, 0, 0.05);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  border-bottom-left-radius: 16px;
}}

.kachel-slider {{
  background: none;
}}

button.rail-entry,
button.rail-entry:hover,
button.rail-entry:active {{
  background-image: none;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0;
  min-width: 0;
  min-height: 0;
}}
button.rail-entry {{
  background-color: transparent;
}}
button.rail-entry:hover {{
  background-color: rgba(255, 255, 255, 0.08);
}}

.kachel-tooltip {{
  background-color: rgba(44, 44, 48, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.38);
  padding: 7px 11px;
}}
.kachel-tooltip-name {{
  font-weight: 600;
  color: #F3F3F3;
}}
.kachel-tooltip-sub {{
  font-size: {secondary}pt;
  color: rgba(255, 255, 255, 0.55);
}}

.kachel-wall,
.kachel-wall viewport {{
  background: none;
  border: none;
}}
.kachel-wall undershoot,
.kachel-wall overshoot {{
  background: none;
}}
.kachel-wall scrollbar {{
  background: none;
  border: none;
}}
.kachel-wall scrollbar slider {{
  background-color: rgba(255, 255, 255, 0.2);
  border: none;
  border-radius: 3px;
  min-width: 4px;
  min-height: 24px;
}}

.kachel-group-header {{
  font-size: {category}pt;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
}}

button.tile {{
  background-image: none;
  background-color: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 4px;
  box-shadow: none;
  text-shadow: none;
  -gtk-icon-shadow: none;
  outline: none;
  padding: 0;
  margin: 0;
  min-width: 0;
  min-height: 0;
}}
button.tile:hover,
button.tile:active,
button.tile:checked {{
  background-image: none;
  background-color: rgba(255, 255, 255, 0.08);
  box-shadow: none;
}}
button.tile.hover {{
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.30);
}}

.tile-box {{
  background: none;
}}

.tile-textline {{
  font-size: {tile}pt;
  color: rgba(255, 255, 255, 0.85);
}}
.tile-textline.active {{
  color: #FFFFFF;
}}

button.shortcut,
button.shortcut:hover,
button.shortcut:active {{
  background-image: none;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 4px;
  padding: 0;
  min-width: 0;
  min-height: 0;
}}
button.shortcut {{
  background-color: rgba(255, 255, 255, 0.08);
}}
button.shortcut:hover {{
  background-color: rgba(255, 255, 255, 0.24);
}}

.tile-label {{
  font-size: {tile}pt;
  color: #F3F3F3;
}}

.kachel-hint,
.kachel-error {{
  font-size: {secondary}pt;
  color: rgba(255, 255, 255, 0.55);
}}
.kachel-error {{
  padding: 8px 24px 0 24px;
}}

.ms-icon {{
  color: rgba(255, 255, 255, 0.88);
}}

button.kachel-search-button,
button.kachel-search-button:hover,
button.kachel-search-button:active {{
  background-image: none;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0;
  min-width: 30px;
  min-height: 30px;
}}
button.kachel-search-button {{
  background-color: transparent;
}}
button.kachel-search-button .ms-icon {{
  color: rgba(255, 255, 255, 0.65);
}}
button.kachel-search-button:hover {{
  background-color: rgba(255, 255, 255, 0.10);
}}
button.kachel-search-button:hover .ms-icon {{
  color: #FFFFFF;
}}

button.kachel-list-button,
button.kachel-list-button:hover,
button.kachel-list-button:active,
button.kachel-list-row,
button.kachel-list-row:hover,
button.kachel-list-row:active {{
  background-image: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0;
  min-width: 0;
  min-height: 0;
}}
button.kachel-list-button .ms-icon {{
  color: rgba(255, 255, 255, 0.75);
}}
button.kachel-list-button:hover {{
  background-color: rgba(255, 255, 255, 0.10);
}}
button.kachel-list-button:hover .ms-icon,
button.kachel-list-button.active .ms-icon {{
  color: #FFFFFF;
}}
button.kachel-list-button.active {{
  background-color: rgba(255, 255, 255, 0.12);
}}

.kachel-list-section {{
  padding: 0 10px;
}}
/* In every state: the reset above names :hover and :active too, and
   would otherwise pull the content to the edge under the pointer. */
button.kachel-list-row,
button.kachel-list-row:hover,
button.kachel-list-row:active {{
  padding: 0 10px;
}}
button.kachel-list-row:hover {{
  background-color: rgba(255, 255, 255, 0.08);
}}
.kachel-list-plate {{
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
}}
/* The whole row is one box under the pointer; the icon's own goes. */
button.kachel-list-row:hover .kachel-list-plate {{
  background-color: transparent;
}}
.kachel-list-name {{
  font-size: {name}pt;
  color: #F3F3F3;
}}
.kachel-list-group {{
  font-size: {secondary}pt;
  color: rgba(255, 255, 255, 0.45);
}}
.kachel-alpha {{
  font-size: {secondary}pt;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.22);
  border-radius: 4px;
}}
.kachel-alpha.present {{
  color: rgba(255, 255, 255, 0.62);
}}
.kachel-alpha.current {{
  color: #FFFFFF;
}}
.kachel-alpha.hover {{
  background-color: rgba(255, 255, 255, 0.12);
}}

button.kachel-pill,
button.kachel-pill:hover,
button.kachel-pill:active {{
  background-image: none;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0 9px 0 7px;
  min-width: 0;
  min-height: 26px;
  font-weight: 600;
}}
button.kachel-pill:hover {{
  opacity: 0.8;
}}
button.kachel-pill.extra {{
  background-color: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.24);
  color: #FFFFFF;
  padding: 0 9px;
  min-height: 24px;
}}

.kachel-menu {{
  background-color: rgba(44, 44, 48, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.38);
  padding: 6px;
}}
button.kachel-menu-row,
button.kachel-menu-row:hover,
button.kachel-menu-row:active,
button.kachel-menu-size,
button.kachel-menu-size:hover,
button.kachel-menu-size:active {{
  background-image: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0 10px;
  min-height: 34px;
  color: #F3F3F3;
}}
button.kachel-menu-row:hover,
button.kachel-menu-size:hover {{
  background-color: rgba(255, 255, 255, 0.10);
}}
button.kachel-menu-row:disabled {{
  color: rgba(255, 255, 255, 0.35);
}}
button.kachel-menu-row:disabled .ms-icon {{
  color: rgba(255, 255, 255, 0.35);
}}
button.kachel-menu-row.armed {{
  background-color: rgba(239, 102, 97, 0.5);
}}
button.kachel-menu-size,
button.kachel-menu-size:hover,
button.kachel-menu-size:active {{
  padding: 0 4px;
}}
button.kachel-menu-size {{
  min-height: 0;
  font-size: {secondary}pt;
  background-color: rgba(255, 255, 255, 0.04);
}}
button.kachel-menu-size.selected {{
  background-color: rgba(255, 255, 255, 0.16);
  color: #FFFFFF;
}}
.kachel-menu.debug-hover button.kachel-menu-row,
.kachel-menu.debug-hover button.kachel-menu-size {{
  background-color: rgba(255, 255, 255, 0.10);
}}
entry.kachel-menu-entry {{
  background-color: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 6px;
  box-shadow: none;
  color: #F3F3F3;
  caret-color: #FFFFFF;
  min-height: 30px;
  padding: 0 8px;
}}

.kachel-suggestions {{
  background-color: rgba(44, 44, 48, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.38);
  padding: 6px;
}}
button.kachel-suggestion,
button.kachel-suggestion:hover,
button.kachel-suggestion:active {{
  background-image: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 6px;
  padding: 0 10px;
  min-height: 40px;
}}
button.kachel-suggestion.selected {{
  background-color: rgba(255, 255, 255, 0.10);
}}
button.kachel-suggestion .ms-icon {{
  color: rgba(255, 255, 255, 0.75);
}}
.kachel-suggestion-code {{
  font-family: "{mono}";
  color: #F3F3F3;
}}
.kachel-suggestion-name {{
  font-weight: 600;
  color: #F3F3F3;
}}
.kachel-suggestion-hint {{
  color: rgba(255, 255, 255, 0.55);
}}

entry.kachel-search-entry {{
  background: none;
  border: none;
  box-shadow: none;
  outline: none;
  padding: 0;
  min-height: 0;
  color: #F3F3F3;
  caret-color: #FFFFFF;
  font-size: {search}pt;
}}
entry.kachel-search-entry selection {{
  background-color: rgba(255, 255, 255, 0.25);
  color: #FFFFFF;
}}

.kachel-results-header {{
  font-size: {category}pt;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.55);
  padding: 8px 14px;
}}

button.kachel-result,
button.kachel-result:hover,
button.kachel-result:active {{
  background-image: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  text-shadow: none;
  outline: none;
  border-radius: 8px;
  padding: 0 14px;
  min-height: 0;   /* the row asks for its 54 px itself: a press margin must not add to it */
}}
button.kachel-result.selected {{
  background-color: rgba(255, 255, 255, 0.10);
}}

.kachel-result-plate {{
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
}}
.kachel-result-name {{
  font-size: {name}pt;
  color: #F3F3F3;
}}
.kachel-result-sub {{
  font-size: {secondary}pt;
  color: rgba(255, 255, 255, 0.55);
}}
.kachel-key-hint {{
  font-family: "{mono}";
  font-size: {secondary}pt;
  color: rgba(255, 255, 255, 0.6);
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  padding: 3px 7px;
}}

/* The effects (Design §12); the numbers come from anim.py. Set here for
   every surface of ours, so the theme's own (slower) transition on
   `button` does not apply. Press: GTK 3 has no transform, so the surface
   takes a margin instead and shrinks around its content. */
button.tile,
button.shortcut,
button.kachel-result,
button.kachel-list-row,
button.kachel-list-button,
button.rail-entry,
button.kachel-menu-row,
button.kachel-menu-size,
button.kachel-pill,
button.kachel-search-button {{
  transition: background-color {hover_ms}ms ease, box-shadow {hover_ms}ms ease,
              margin {press_ms}ms ease-out;
}}
.kachel-list-plate {{
  transition: background-color {hover_ms}ms ease;
}}
button.tile:active,
button.kachel-result:active,
button.kachel-list-row:active,
button.rail-entry:active {{
  margin: {press_margin}px;
}}
{effects_off}'''


EFFECTS_OFF = f'''button.tile.hover {{
  background-color: rgba(255, 255, 255, {anim.HOVER_FILL_OFF});
}}
'''


def base_size(font_name):
    '''The size in points from a font name like 'Ubuntu 10'.'''
    description = Pango.FontDescription.from_string(font_name or '')
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        size = size * 72 / 96   # pixels, at the usual 96 dpi
    return size if size > 0 else FALLBACK_SIZE


def css(base, mono='Monospace', animated=True):
    '''The style sheet for a system font of `base` points, as bytes.

    `mono` is the family of the system's monospace font, for key hints.
    Without `animated`, no transitions and no press; a tile under the
    pointer gets a lighter fill instead of the glow.
    '''
    def pt(delta):
        return f'{base + delta:g}'
    sheet = TEMPLATE.format(base=pt(0), category=pt(-1.5), tile=pt(-1.5),
                            secondary=pt(-1), search=pt(5), name=pt(1),
                            mono=mono.replace('"', ''),
                            hover_ms=anim.HOVER_MS if animated else 0,
                            press_ms=anim.PRESS_MS if animated else 0,
                            press_margin=anim.PRESS_MARGIN if animated else 0,
                            effects_off='' if animated else EFFECTS_OFF)
    return (sheet + pill_css()).encode('utf-8')


def pill_css():
    '''One colour pair per scope pill (Design §5), from query.SCOPES.'''
    rules = []
    for scope in query.SCOPES:
        rules.append(
            f'button.kachel-pill.scope-{scope.css},\n'
            f'button.kachel-pill.scope-{scope.css} .ms-icon {{\n'
            f'  color: {scope.ink};\n}}\n'
            f'button.kachel-pill.scope-{scope.css} {{\n'
            f'  background-color: {scope.fill};\n}}\n')
    return ''.join(rules)


def monospace_family():
    '''The family of the system's monospace font, e.g. 'DejaVu Sans Mono'.

    Looked up before it is opened: Gio.Settings on a schema that is not
    installed aborts the process.
    '''
    schema_id = 'org.gnome.desktop.interface'
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(schema_id, True) if source else None
    if schema is None or not schema.has_key('monospace-font-name'):
        return 'Monospace'
    name = Gio.Settings.new(schema_id).get_string('monospace-font-name')
    return Pango.FontDescription.from_string(name).get_family() or 'Monospace'


class Style:
    '''Installs the style sheet for the whole screen and keeps it current.'''

    def __init__(self):
        self._provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), self._provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        settings = Gtk.Settings.get_default()
        settings.connect('notify::gtk-font-name', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        name = Gtk.Settings.get_default().get_property('gtk-font-name')
        self._provider.load_from_data(css(base_size(name),
                                          monospace_family(),
                                          animated=anim.enabled()))
