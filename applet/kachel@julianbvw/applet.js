// The panel button for Kachel: a click shows or hides it, like F7.
//
// Kachel is a resident GApplication; this talks to it over D-Bus with the
// same `toggle` action the shortcut uses. If it is not running, the
// button starts it and shows it once it is on the bus.

const Applet = imports.ui.applet;
const Settings = imports.ui.settings;
const Util = imports.misc.util;
const Mainloop = imports.mainloop;
const Gio = imports.gi.Gio;
const GLib = imports.gi.GLib;

const APP_ID = 'io.github.julianbvw.Kachel';
const OBJECT_PATH = '/io/github/julianbvw/Kachel';
const START_TIMEOUT_MS = 5000;
const DEFAULT_ICON = 'kachel-windrad-symbolic';

class KachelApplet extends Applet.IconApplet {
    constructor(metadata, orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);
        this._path = metadata.path;
        this._watch = 0;
        this._giveUp = 0;
        this.set_applet_tooltip('Kachel');
        this.settings = new Settings.AppletSettings(this, metadata.uuid,
                                                    instanceId);
        this.settings.bind('panel-icon', 'panelIcon',
                           () => this._updateIcon());
        this._updateIcon();
    }

    _updateIcon() {
        // What the icon chooser gave: one of Kachel's own logos, which come
        // from this folder so they work even where install.py has not put
        // them into the icon theme, a file, or an icon name.
        const icon = (this.panelIcon || '').trim() || DEFAULT_ICON;
        const own = this._path + '/' + icon + '.svg';
        if (!icon.includes('/') && GLib.file_test(own, GLib.FileTest.EXISTS))
            this.set_applet_icon_symbolic_path(own);
        else if (icon.startsWith('/'))
            if (icon.includes('-symbolic'))
                this.set_applet_icon_symbolic_path(icon);
            else
                this.set_applet_icon_path(icon);
        else if (icon.endsWith('-symbolic'))
            this.set_applet_icon_symbolic_name(icon);
        else
            this.set_applet_icon_name(icon);
    }

    on_applet_clicked(_event) {
        this._activate('toggle', true);
    }

    _activate(action, startIfMissing) {
        Gio.DBus.session.call(
            APP_ID, OBJECT_PATH, 'org.gtk.Actions', 'Activate',
            new GLib.Variant('(sava{sv})', [action, [], {}]),
            null, Gio.DBusCallFlags.NO_AUTO_START, 1000, null,
            (connection, result) => {
                try {
                    connection.call_finish(result);
                } catch (error) {
                    // Only when nobody has the name: a slow answer from a
                    // running Kachel must not start a second one.
                    const missing =
                        error.matches(Gio.DBusError,
                                      Gio.DBusError.SERVICE_UNKNOWN) ||
                        error.matches(Gio.DBusError,
                                      Gio.DBusError.NAME_HAS_NO_OWNER);
                    if (startIfMissing && missing)
                        this._start();
                    else
                        global.logError('Kachel: ' + error.message);
                }
            });
    }

    _start() {
        // The .desktop file install.py writes runs the resident service;
        // it starts hidden, so `show` follows once it has its bus name.
        if (this._watch)
            return;
        this._watch = Gio.bus_watch_name(
            Gio.BusType.SESSION, APP_ID, Gio.BusNameWatcherFlags.NONE,
            () => {
                this._stopWatching();
                this._activate('show', false);
            },
            null);
        this._giveUp = Mainloop.timeout_add(START_TIMEOUT_MS, () => {
            this._giveUp = 0;
            this._stopWatching();
            return false;
        });
        Util.spawn(['gtk-launch', APP_ID]);
    }

    _stopWatching() {
        if (this._watch) {
            Gio.bus_unwatch_name(this._watch);
            this._watch = 0;
        }
        if (this._giveUp) {
            Mainloop.source_remove(this._giveUp);
            this._giveUp = 0;
        }
    }

    on_applet_removed_from_panel() {
        this._stopWatching();
        this.settings.finalize();
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new KachelApplet(metadata, orientation, panelHeight, instanceId);
}
