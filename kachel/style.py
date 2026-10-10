'''The style sheet: colour tokens plus sizes relative to the system font.

No font is shipped. Everything is set in the system font, and every size is
the system size plus or minus a few points, so changing the font in the
system settings changes Kachel along with everything else.
'''

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gdk, Gtk, Pango  # noqa: E402

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
button.tile:hover {{
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.30);
}}
button.tile:active,
button.tile:checked {{
  background-image: none;
  background-color: rgba(255, 255, 255, 0.08);
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
'''


def base_size(font_name):
    '''The size in points from a font name like 'Ubuntu 10'.'''
    description = Pango.FontDescription.from_string(font_name or '')
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        size = size * 72 / 96   # pixels, at the usual 96 dpi
    return size if size > 0 else FALLBACK_SIZE


def css(base):
    '''The style sheet for a system font of `base` points, as bytes.'''
    def pt(delta):
        return f'{base + delta:g}'
    return TEMPLATE.format(base=pt(0), category=pt(-1.5), tile=pt(-1.5),
                           secondary=pt(-1)).encode('utf-8')


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
        self._provider.load_from_data(css(base_size(name)))
