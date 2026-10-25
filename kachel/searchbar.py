'''The search bar: a button on the left, the input field beside it.'''

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk  # noqa: E402

from . import config, icons, query  # noqa: E402

PLACEHOLDER = 'Suchen…'
PLACEHOLDER_SCOPED = 'Suchbegriff…'
PILL_HEIGHT = 26
PILL_GLYPH = 16
BUTTON_SIZE = 30
GLYPH_SIZE = 22
LIST_BUTTON_SIZE = 34


class SearchBar(Gtk.Box):
    '''`on_changed(text, scope, extras)` on every edit or change of a
    pill (scope: a query.Scope or None; extras: the files scope's extra
    pills, a tuple of query.Extra), `on_word(word)` whenever the word at
    the cursor may have changed, `on_close()` when the button is clicked
    with nothing left to clear, `on_list()` when the app list button on
    the right is clicked.'''

    def __init__(self, on_changed, on_close, on_list, on_word=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.get_style_context().add_class('kachel-searchbar')
        self.set_size_request(-1, config.SEARCHBAR_HEIGHT)
        self._on_changed = on_changed
        self._on_close = on_close
        self._on_word = on_word or (lambda word: None)
        self._scope = None
        self._extras = []
        self._taking = False   # while the text is rewritten for a pill
        self._took_pill = False

        # Magnifier at rest, a cross under the pointer: the button clears,
        # and when there is nothing to clear, it closes.
        self._glyphs = Gtk.Stack()
        self._glyphs.add_named(icons.icon_widget('ms:search', GLYPH_SIZE),
                               'search')
        self._glyphs.add_named(icons.icon_widget('ms:close', GLYPH_SIZE),
                               'close')
        self._button = Gtk.Button()
        self._button.set_relief(Gtk.ReliefStyle.NONE)
        self._button.set_can_focus(False)   # the field keeps the keyboard
        self._button.get_style_context().add_class('kachel-search-button')
        self._button.set_size_request(BUTTON_SIZE, BUTTON_SIZE)
        self._button.set_valign(Gtk.Align.CENTER)
        self._button.set_margin_start(20)
        self._button.add(self._glyphs)
        self._button.connect('enter-notify-event', self._hover, 'close')
        self._button.connect('leave-notify-event', self._hover, 'search')
        self._button.connect('clicked', self._clicked)
        self.pack_start(self._button, False, False, 0)

        # The scope pill, between the button and the field. One button,
        # restyled per scope; a click on it takes it away.
        self._pill = Gtk.Button()
        self._pill.set_relief(Gtk.ReliefStyle.NONE)
        self._pill.set_can_focus(False)
        self._pill.get_style_context().add_class('kachel-pill')
        self._pill.set_size_request(-1, PILL_HEIGHT)
        self._pill.set_valign(Gtk.Align.CENTER)
        self._pill_box = Gtk.Box(spacing=4)
        self._pill.add(self._pill_box)
        self._pill.connect('clicked', lambda *_: self._drop_pill())
        self._pill.set_no_show_all(True)
        self.pack_start(self._pill, False, False, 0)

        # The extra pills of the files scope, behind it.
        self._extras_box = Gtk.Box(spacing=6)
        self._extras_box.set_valign(Gtk.Align.CENTER)
        self.pack_start(self._extras_box, False, False, 0)

        self._entry = Gtk.Entry()
        self._entry.get_style_context().add_class('kachel-search-entry')
        self._entry.set_has_frame(False)
        self._entry.set_placeholder_text(PLACEHOLDER)
        self._entry.set_hexpand(True)
        self._entry.set_valign(Gtk.Align.CENTER)
        self._entry.connect('changed', self._changed)
        self._entry.connect('notify::cursor-position',
                            lambda *_: self._on_word(self.word))
        self._entry.connect('key-press-event', self._key_pressed)
        self.pack_start(self._entry, True, True, 0)

        # The app list switch (Design §7). Lit while the list is open.
        self._list_button = Gtk.Button()
        self._list_button.set_relief(Gtk.ReliefStyle.NONE)
        self._list_button.set_can_focus(False)
        self._list_button.get_style_context().add_class('kachel-list-button')
        self._list_button.set_size_request(LIST_BUTTON_SIZE, LIST_BUTTON_SIZE)
        self._list_button.set_valign(Gtk.Align.CENTER)
        self._list_button.set_margin_end(11)
        self._list_button.add(icons.icon_widget('ms:apps', GLYPH_SIZE))
        self._list_button.connect('clicked', lambda *_: on_list())
        self.pack_start(self._list_button, False, False, 0)

    @property
    def text(self):
        return self._entry.get_text()

    @property
    def scope(self):
        return self._scope

    @property
    def extras(self):
        return tuple(self._extras)

    @property
    def word(self):
        '''The word at the cursor, for the suggestion list.'''
        return query.word_at(self.text, self._entry.get_position())[1]

    def set_text(self, text, cursor=-1):
        self._entry.set_text(text)
        self._entry.set_position(cursor)

    def complete(self, scope):
        '''Put `@code ` in place of the word at the cursor; it turns into
        the pill at once.'''
        text, cursor = query.complete(self.text, self._entry.get_position(),
                                      scope)
        self._took_pill = False
        self._entry.set_text(text)
        # Taking the pill has placed the cursor already, in the text that
        # is left; the position worked out above belongs to the old one.
        if not self._took_pill:
            self._entry.set_position(cursor)

    def set_scope(self, scope):
        '''Show the pill for `scope`, or none.'''
        if scope == self._scope:
            return
        if scope is None or scope.code != 'f':
            self._set_extras([])   # they belong to the files scope
        context = self._pill.get_style_context()
        if self._scope is not None:
            context.remove_class(f'scope-{self._scope.css}')
        self._scope = scope
        for child in self._pill_box.get_children():
            self._pill_box.remove(child)
            child.destroy()
        if scope is None:
            self._pill.hide()
            self._entry.set_placeholder_text(PLACEHOLDER)
            return
        context.add_class(f'scope-{scope.css}')
        self._pill_box.pack_start(
            icons.icon_widget(scope.icon, PILL_GLYPH, filled=True),
            False, False, 0)
        self._pill_box.pack_start(Gtk.Label(label=scope.name), False, False, 0)
        self._pill_box.show_all()
        self._pill.show()
        self._entry.set_placeholder_text(PLACEHOLDER_SCOPED)

    def _set_extras(self, extras):
        self._extras = list(extras)
        for child in self._extras_box.get_children():
            self._extras_box.remove(child)
            child.destroy()
        for extra in self._extras:
            pill = Gtk.Button(label=extra.label)
            pill.set_relief(Gtk.ReliefStyle.NONE)
            pill.set_can_focus(False)
            pill.get_style_context().add_class('kachel-pill')
            pill.get_style_context().add_class('extra')
            pill.set_size_request(-1, PILL_HEIGHT)
            pill.connect('clicked', lambda _b, e=extra: self._drop_extra(e))
            self._extras_box.pack_start(pill, False, False, 0)
        self._extras_box.show_all()

    def _drop_extra(self, extra):
        self._set_extras([e for e in self._extras if e is not extra])
        self._notify()
        self.focus()

    def _notify(self):
        self._on_changed(self.text, self._scope, self.extras)

    def clear(self):
        '''Text and pills, all of them.'''
        had_text = bool(self.text)
        self.set_scope(None)
        self._entry.set_text('')
        if not had_text:
            # Only pills went: no 'changed' to pass that on.
            self._notify()

    def reset(self):
        '''Empty, and the magnifier back: a hide while the pointer was on
        the button brings no leave event to switch it back.'''
        self.clear()
        self._glyphs.set_visible_child_name('search')

    def set_list_active(self, active):
        context = self._list_button.get_style_context()
        if active:
            context.add_class('active')
        else:
            context.remove_class('active')

    def focus(self):
        self._entry.grab_focus_without_selecting()

    def _changed(self, entry):
        if self._taking:
            return
        text, cursor = entry.get_text(), entry.get_position()
        took = False
        while True:
            scope, text, cursor = query.take_pill(text, cursor,
                                                  calc=self._scope is None)
            if scope is not None:
                self.set_scope(scope)
                took = True
                continue
            if self._scope is not None and self._scope.code == 'f':
                extra, text, cursor = query.take_extra(text, cursor)
                if extra is not None:
                    self._set_extras(self._extras + [extra])
                    took = True
                    continue
            break
        if took:
            # Rewriting the text sends 'changed' again; that one is ours.
            self._taking = True
            entry.set_text(text)
            entry.set_position(cursor)
            self._taking = False
            self._took_pill = True
        self._notify()
        self._on_word(self.word)

    def _drop_pill(self):
        self.set_scope(None)
        self._notify()
        self._on_word(self.word)
        self.focus()

    def _key_pressed(self, entry, event):
        '''Backspace in front of everything takes a pill away: the last
        extra pill first, then the scope (Design §11.5). Ctrl+Backspace
        too -- the pill is the word before the cursor.'''
        if event.keyval == Gdk.KEY_BackSpace and self._scope is not None \
                and entry.get_position() == 0 \
                and not entry.get_selection_bounds():
            if self._extras:
                self._drop_extra(self._extras[-1])
            else:
                self._drop_pill()
            return True
        return False

    def _hover(self, _widget, _event, glyph):
        self._glyphs.set_visible_child_name(glyph)
        return False

    def _clicked(self, _button):
        if self._entry.get_text() or self._scope is not None:
            self.clear()
            self.focus()
        else:
            self._on_close()
