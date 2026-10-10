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
button.kachel-list-row {{
  padding: 0 10px;
}}
button.kachel-list-row:hover {{
  background-color: rgba(255, 255, 255, 0.08);
}}
.kachel-list-plate {{
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
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
  min-height: 54px;
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
'''


def base_size(font_name):
    '''The size in points from a font name like 'Ubuntu 10'.'''
    description = Pango.FontDescription.from_string(font_name or '')
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        size = size * 72 / 96   # pixels, at the usual 96 dpi
    return size if size > 0 else FALLBACK_SIZE


def css(base, mono='Monospace'):
    '''The style sheet for a system font of `base` points, as bytes.

    `mono` is the family of the system's monospace font, for key hints.
    '''
    def pt(delta):
        return f'{base + delta:g}'
    return TEMPLATE.format(base=pt(0), category=pt(-1.5), tile=pt(-1.5),
                           secondary=pt(-1), search=pt(5), name=pt(1),
                           mono=mono.replace('"', '')).encode('utf-8')


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
                                          monospace_family()))
