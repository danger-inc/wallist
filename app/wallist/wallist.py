#!/usr/bin/env python3
# wallist: verwaltet den Ordner der Super+W-Rotation und schlägt neue Bilder im eigenen Stil vor.
# Oberfläche im Suite-Look (rice-apps/tui.py wie datist/musicalist): Marken-Chip, Tabs ¹²,
# Kacheln mit Titel im Rahmen, [ knöpfe ], [■]-Schalter, Statuszeile.
# Super+W (~/.config/hypr/random_wall.sh) nimmt JEDE Datei aus ~/.config/wallpapers. Deshalb landen dort
# nur fertige, geprüfte Bilder: Downloads werden im Cache vorbereitet und erst am Ende hineingeschoben.
import concurrent.futures, datetime, hashlib, io, json, math, os, random, shutil, sys, threading, time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, Gio, GLib, Graphene, Gtk, Pango, PangoCairo
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.expanduser("~/.local/share/rice-apps"))
import sources as src  # noqa: E402
import glass  # noqa: E402
import tui  # noqa: E402
import swipe  # noqa: E402

APP_ID = "de.invincible.Wallist"
WALL_DIR = os.path.expanduser("~/.config/wallpapers")
CURRENT_FILE = os.path.expanduser("~/.cache/matugen/wallpaper")
APPLY_COLORS = os.path.expanduser("~/.config/hypr/scripts/apply-colors.sh")
# Super+W-Rotation (eigenes Hyprland-Setup). Fehlt sie (z. B. bei Freunden), ist wallist eine Sammlung,
# aus der ein Klick das Hintergrundbild setzt (GNOME, KDE, swww, feh …).
ROTATION = os.path.exists(os.path.expanduser("~/.config/hypr/random_wall.sh"))
IN_ROT = "in der rotation" if ROTATION else "in der sammlung"
TO_ROT = "zur rotation" if ROTATION else "zur sammlung"
OWN_CURRENT = os.path.expanduser("~/.config/wallist/current")
for _old, _new in (("~/.config/wallpapaer", "~/.config/wallist"), ("~/.cache/wallpapaer", "~/.cache/wallist")):
    _old, _new = os.path.expanduser(_old), os.path.expanduser(_new)   # alter Name (bis 2.0.0) → einmal umziehen
    if os.path.isdir(_old) and not os.path.exists(_new):
        try:
            os.rename(_old, _new)
        except OSError:
            pass
CFG_DIR = os.path.expanduser("~/.config/wallist")
CFG_FILE = os.path.join(CFG_DIR, "settings.json")
CACHE = os.path.expanduser("~/.cache/wallist")
THUMBS = os.path.join(CACHE, "thumbs")
REMOVED = os.path.join(CACHE, "entfernt")       # 30 Tage aufbewahrt, für "Rückgängig"
ADDED_FILE = os.path.join(CACHE, "added.json")
FEAT_FILE = os.path.join(CACHE, "features.json")
OK_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}  # liest awww und matugen sicher

DEFAULTS = {
    "keywords": ["digital painting landscape", "anime scenery", "ghibli landscape", "pixel art city", "lofi train"],
    "active": ["digital painting landscape", "anime scenery", "ghibli landscape", "pixel art city", "lofi train"],
    "sources": {"Wallhaven": True, "Pinterest": True, "Cosmos": True},
    "quality": "screen",     # "screen" = mindestens Bildschirmauflösung, "fhd" = mindestens 1920×1080
    "only_matching": True,
}
MATCH_MIN = 30  # entspricht etwa der Ähnlichkeit von Ghibli- und Pixel-Art-Treffern
TW, TH = 264, 165  # Vorschaubild in der Kachel
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# hängt an tui.CSS (gleiches Stylesheet, sonst lösen @primary usw. nicht auf)
CSS = """
window.tui .wtile { padding: 22px 10px 10px 10px; }
window.tui .wtile label.meta { font-size: 11px; color: @secondary; }
window.tui .wtile button.tbtn { font-size: 12px; padding: 1px 6px; }
window.tui .wtile label.score { font-size: 11px; color: @primary; min-width: 38px; }
window.tui .wl-bar { margin: 4px 0 8px 0; }
window.tui label.wl-add { color: @primary; font-size: 34px; }
window.tui label.wl-add-sub { font-size: 12px; color: @secondary; }
window.tui .wl-key { color: @primary; min-width: 64px; }
window.tui .wl-chip { border: 1px solid alpha(@primary, 0.3); border-radius: 4px; padding: 0 0 0 2px; }
window.tui .wl-chip button.check { padding: 0 4px; }
window.tui .wl-chip button.flat { color: alpha(@foreground, 0.45); padding: 0 5px; }
window.tui .wl-chip button.flat:hover { color: @tertiary; background: none; }
window.tui .wl-spin { color: @primary; min-width: 14px; }
window.tui .wl-backdrop { background-color: alpha(@background, 0.72); }
window.tui .wl-preview { background-color: @background; border-radius: 6px; }
window.tui.glass .wl-preview { background-color: alpha(@background, 0.88); }
window.tui .wl-mine flowboxchild, window.tui .wl-explore flowboxchild { padding: 0; background: none; }
"""


def human_size(n):
    for unit in ("b", "kb", "mb", "gb"):
        if n < 1024 or unit == "gb":
            return f"{n:.0f} {unit}" if unit == "b" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def wall_files():
    """Genau die Dateien, aus denen Super+W wählt (find -type f, auch in Unterordnern)."""
    out = []
    for root, _, files in os.walk(WALL_DIR):
        out += [os.path.join(root, f) for f in files]
    return sorted(out, key=lambda p: os.path.getmtime(p), reverse=True)


def current_wallpaper():
    for f in ((CURRENT_FILE, OWN_CURRENT) if ROTATION else (OWN_CURRENT, CURRENT_FILE)):
        try:
            return os.path.realpath(open(f).read().strip())
        except OSError:
            continue
    return None


def desktop_setter(path):
    """Befehl, der auf dieser Arbeitsumgebung das Hintergrundbild setzt (oder None)."""
    desk = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" + os.environ.get("DESKTOP_SESSION", "")).lower()
    uri = Gio.File.new_for_path(path).get_uri()
    if shutil.which("awww"):
        return ["awww", "img", path]
    if shutil.which("swww"):
        return ["swww", "img", path]
    if "kde" in desk or "plasma" in desk:
        if shutil.which("plasma-apply-wallpaperimage"):
            return ["plasma-apply-wallpaperimage", path]
    if any(d in desk for d in ("gnome", "unity", "budgie", "pantheon", "ubuntu", "pop")) and shutil.which("gsettings"):
        return ["sh", "-c", 'gsettings set org.gnome.desktop.background picture-uri "$1"; '
                'gsettings set org.gnome.desktop.background picture-uri-dark "$1" 2>/dev/null; '
                'gsettings set org.gnome.desktop.background picture-options zoom', "sh", uri]
    if "cinnamon" in desk and shutil.which("gsettings"):
        return ["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri]
    if "mate" in desk and shutil.which("gsettings"):
        return ["gsettings", "set", "org.mate.background", "picture-filename", path]
    if "xfce" in desk and shutil.which("xfconf-query"):
        return ["sh", "-c", 'for p in $(xfconf-query -c xfce4-desktop -l | grep last-image); do '
                'xfconf-query -c xfce4-desktop -p "$p" -s "$1"; done', "sh", path]
    if shutil.which("swaybg") and os.environ.get("WAYLAND_DISPLAY"):
        return ["sh", "-c", 'pkill -x swaybg; setsid -f swaybg -m fill -i "$1" >/dev/null 2>&1', "sh", path]
    if shutil.which("feh") and os.environ.get("DISPLAY"):
        return ["feh", "--bg-fill", path]
    return None


def file_key(path):
    st = os.stat(path)
    return hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()


def make_thumb(img, width=560):
    im = img.copy()
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    im = im.convert("RGB")
    im.thumbnail((width, width))
    buf = io.BytesIO()
    im.save(buf, "PNG", compress_level=1)
    return buf.getvalue()


def texture(png):
    return Gdk.Texture.new_from_bytes(GLib.Bytes.new(png))


def res_tag(w, h):
    return "8k" if w >= 7680 else "5k" if w >= 5120 else "4k" if w >= 3840 else f"{w}×{h}"


def primary():
    p = tui.colors().get("primary")
    if p is None:
        p = Gdk.RGBA()
        p.parse("#ffb68e")
    return p


# ---------- Bausteine ----------
class Frame(Gtk.Box):
    """Kachel im Suite-Look: 1-px-Rahmen mit Titel links und Marke rechts in der oberen Linie
    (wie die Kästen in datist/btop). Ohne deckenden Hintergrund, damit Glas sauber aussieht."""
    PAD = (22, 10, 10, 10)          # muss zu .wtile { padding } passen (oben, rechts, unten, links)

    def __init__(self, title="", tag="", dashed=False, spacing=6, hover=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, halign=Gtk.Align.CENTER,
                         valign=Gtk.Align.START)
        self.add_css_class("wtile")
        self.title, self.tag, self.dashed = title, tag, dashed
        self.active = self.hover = False
        self.font = Pango.FontDescription.from_string(f"{tui.FONT} Bold 10")
        if hover:
            m = Gtk.EventControllerMotion()
            m.connect("enter", lambda *_: self._set_hover(True))
            m.connect("leave", lambda *_: self._set_hover(False))
            self.add_controller(m)

    def _set_hover(self, on):
        self.hover = on
        self.queue_draw()

    def set_title(self, title):
        self.title = title
        self.queue_draw()

    def set_tag(self, tag):
        self.tag = tag
        self.queue_draw()

    def set_active(self, on):
        self.active = on
        self.queue_draw()

    def _layout(self, text):
        lay = self.create_pango_layout(f" {text} ")
        lay.set_font_description(self.font)
        return lay

    def do_snapshot(self, snap):
        Gtk.Box.do_snapshot(self, snap)
        w, h = self.get_width(), self.get_height()
        if w < 4 or h < 4:
            return
        p = primary()
        top, pr, pb, pl = self.PAD
        W, H = w + pl + pr, h + top + pb
        snap.save()
        pt = Graphene.Point()
        pt.init(-pl, -top)
        snap.translate(pt)
        cr = snap.append_cairo(Graphene.Rect().init(0, 0, W, H))
        r, x0, x1, y1, y0 = 6, 0.5, W - 0.5, H - 0.5, 9.5
        cr.set_line_width(1)
        tag_w = 0
        if self.tag:
            tl = self._layout(self.tag)
            tag_w, th = tl.get_pixel_size()
            cr.set_source_rgba(p.red, p.green, p.blue, 1)
            cr.move_to(W - 12 - tag_w, y0 - th / 2)
            PangoCairo.show_layout(cr, tl)
        gap = None
        if self.title:
            lay = self._layout(self.title)
            lay.set_width(max(1, W - 36 - tag_w) * Pango.SCALE)
            lay.set_ellipsize(Pango.EllipsizeMode.END)
            tw, th = lay.get_pixel_size()
            gap = (12, 12 + tw)
            cr.set_source_rgba(p.red, p.green, p.blue, 1 if (self.active or self.hover) else 0.85)
            cr.move_to(12, y0 - th / 2)
            PangoCairo.show_layout(cr, lay)
        alpha = 1.0 if self.active else 0.8 if self.hover else 0.4
        cr.set_source_rgba(p.red, p.green, p.blue, alpha)
        if self.dashed:
            cr.set_dash([4, 3])
        cr.move_to(gap[1] if gap else x0 + r, y0)
        if tag_w:
            cr.line_to(W - 12 - tag_w, y0)
            cr.move_to(W - 12, y0)
        cr.line_to(x1 - r, y0)
        cr.arc(x1 - r, y0 + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.line_to(x1, y1 - r)
        cr.arc(x1 - r, y1 - r, r, 0, 0.5 * math.pi)
        cr.line_to(x0 + r, y1)
        cr.arc(x0 + r, y1 - r, r, 0.5 * math.pi, math.pi)
        cr.line_to(x0, y0 + r)
        cr.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
        if gap:
            cr.line_to(gap[0], y0)
        else:
            cr.close_path()
        cr.stroke()
        snap.restore()


class Thumb(Gtk.DrawingArea):
    """Vorschaubild in fester Kachelgröße, randlos zugeschnitten, kleine Rundung wie die Rahmen.
    (Gtk.Picture würde die Kachel auf die Pixelbreite des Bildes aufblähen.)"""

    def __init__(self, w=TW, h=TH):
        super().__init__(content_width=w, content_height=h, hexpand=False, halign=Gtk.Align.CENTER)
        self.surface = None
        self.set_draw_func(self.draw)

    def set_png(self, png):
        import cairo
        self.surface = cairo.ImageSurface.create_from_png(io.BytesIO(png))
        self.queue_draw()

    def draw(self, area, cr, w, h):
        r = 4
        cr.new_sub_path()
        cr.arc(w - r, r, r, -math.pi / 2, 0); cr.arc(w - r, h - r, r, 0, math.pi / 2)
        cr.arc(r, h - r, r, math.pi / 2, math.pi); cr.arc(r, r, r, math.pi, 1.5 * math.pi)
        cr.close_path()
        cr.clip()
        if not self.surface:
            p = primary()
            cr.set_source_rgba(p.red, p.green, p.blue, 0.06)
            cr.paint()
            return
        sw, sh = self.surface.get_width(), self.surface.get_height()
        sc = max(w / sw, h / sh)
        cr.translate((w - sw * sc) / 2, (h - sh * sc) / 2)
        cr.scale(sc, sc)
        cr.set_source_surface(self.surface, 0, 0)
        cr.get_source().set_filter(4)  # cairo.FILTER_BEST
        cr.paint()


def button(text, cb=None, tip=None, danger=False):
    return tui.Button(text, cb, danger=danger, tooltip=tip)


class WallWindow(tui.TuiWindow):
    APP_ID = APP_ID

    def _key(self, c, kv, code, state):
        app = self.get_application()
        if kv == Gdk.KEY_Escape and getattr(app, "preview", None):
            app.close_preview()
            return True
        if getattr(app, "preview", None) and kv in (Gdk.KEY_Left, Gdk.KEY_Right):
            app.preview_step(-1 if kv == Gdk.KEY_Left else 1)      # große Vorschau: blättern
            return True
        return super()._key(c, kv, code, state)


class Wallist(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.win = None
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        self.search_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.pinterest = src.Pinterest()
        self.pin_lock = threading.Lock()
        self.settings = {**DEFAULTS, **load_json(CFG_FILE, {})}
        self.added = load_json(ADDED_FILE, {})          # Quell-ID -> Dateiname
        self.feat_cache = load_json(FEAT_FILE, {})      # file_key -> Merkmale
        self.profile = []
        self.profile_lock = threading.Lock()
        self.cache_lock = threading.Lock()      # feat_cache wird aus mehreren Threads benutzt
        self.search_gen = 0
        self.seen = set()
        self.pages = {}
        self.pending = 0
        self.found = 0
        self.preview = None
        self._undo = None
        self._undo_id = None
        self._spin_id = None
        self._spin_i = 0
        self.last_error = None
        self.daemon = False             # --daemon: beim Login unsichtbar vorbereiten
        self._held = False
        self.searched_at = 0            # wann „entdecken“ zuletzt gesucht hat (Vorladen im Hintergrund)
        for d in (THUMBS, REMOVED, CFG_DIR, WALL_DIR):
            os.makedirs(d, exist_ok=True)
        self.cleanup_removed()

    # ================= Start =================
    def do_activate(self):
        # Läuft im Hintergrund weiter (Schließen = verstecken): der nächste Aufruf kommt per D-Bus und das Fenster
        # ist sofort da. „entdecken“ sucht schon vorher, damit die Vorschläge beim Klick auf den Tab bereitstehen.
        first = not self.win
        if first:
            self.build()
        if not self._held and os.name != "nt":
            self.hold()
            self._held = True
        if self.daemon:                         # Autostart: nur vorbereiten, nichts zeigen
            self.daemon = False
            GLib.timeout_add_seconds(8, self.preload_explore)
            return
        if first or not self.seen:              # noch nichts da (z. B. beim Login offline gewesen)
            GLib.timeout_add(600, self.preload_explore)
        getattr(glass, "bring_here", lambda w: None)(self.win)
        self.win.present()

    def preload_explore(self):
        """„entdecken“ im Hintergrund füllen: beim ersten Mal und – nach dem Schließen – wenn die Vorschläge
        älter als 3 h sind (so tauscht nichts aus, während man gerade stöbert)."""
        if self.pending or (self.seen and time.time() - self.searched_at < 3 * 3600):
            return False
        if self.seen and self.win.get_visible():
            return False
        self.start_search()
        return False

    def do_open(self, files, n, hint):
        self.do_activate()
        self.add_paths([f.get_path() for f in files if f.get_path()])

    def screen_size(self):
        try:
            mon = Gdk.Display.get_default().get_monitors().get_item(0)
            g, s = mon.get_geometry(), mon.get_scale()
            return round(g.width * s), round(g.height * s)
        except Exception:
            return 1920, 1080

    def min_size(self):
        if self.settings["quality"] == "fhd":
            return 1920, 1080
        w, h = self.screen_size()
        return max(w, 1920), max(h, 1080)

    # ================= Aufbau =================
    def build(self):
        if CSS not in tui.CSS:
            tui.CSS += CSS + swipe.CSS
        tui.Theme.get().load()
        self.monitors = []
        mon2 = Gio.File.new_for_path(CURRENT_FILE).monitor_file(Gio.FileMonitorFlags.NONE, None)
        mon2.connect("changed", lambda *_: self.queue_refresh())
        mon3 = Gio.File.new_for_path(WALL_DIR).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        mon3.connect("changed", lambda *_: self.queue_refresh())
        self.monitors += [mon2, mon3]

        win = WallWindow(self, "wallist", [("mine", "meine", "󰸉"), ("explore", "entdecken", "󰈈")],
                         size=(1240, 820), hints=(("strg+o", "hinzufügen"), ("strg+v", "einfügen"),
                                                  ("strg+r", "neu laden")))
        self.win = win                        # Schließen versteckt nur (TuiWindow), wallist bleibt bereit
        win.connect("hide", lambda *_: self.on_hidden())
        win.add_changelog("wallist", HERE)
        win.add_design_button()
        quit_act = Gio.SimpleAction.new("quit", None)
        quit_act.connect("activate", lambda *_: self.quit())
        self.add_action(quit_act)
        for name, cb, keys in (("add", self.on_add, ["<Control>o"]), ("paste", self.on_paste, ["<Control>v"]),
                               ("close", lambda *_: win.close(), ["<Control>w", "<Control>q"])):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            win.add_action(act)
            self.set_accels_for_action(f"win.{name}", keys)

        # Rückgängig erscheint rechts neben der Meldung in der Statuszeile
        self.undo_btn = button("󰕌 rückgängig", self.do_undo)
        self.undo_btn.set_visible(False)
        win.statusbar.insert_child_after(self.undo_btn, win.status)

        # große Vorschau legt sich als Overlay über alles
        root = win.get_child()
        win.set_child(None)
        self.overlay = Gtk.Overlay(child=root)
        # zwei Finger nach rechts / Maustaste „zurück“: Vorschau zu → entdecken → meine hintergrundbilder
        self.swipe = swipe.SwipeBack(self.overlay, self.can_back, self.go_back,
                                     where=self.swipe_where, target=self.swipe_target,
                                     goto=self.swipe_goto)
        win.set_child(self.swipe.widget)

        win.add_page("mine", self.build_mine(), scroll=False)
        win.add_page("explore", self.build_explore(), scroll=False)
        win.on_tab = self.show_tab
        win.on_refresh = lambda: self.start_search() if win.current_tab() == "explore" else self.refresh_mine()

        target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        target.set_gtypes([Gdk.FileList.__gtype__, Gdk.Texture.__gtype__])
        target.connect("drop", self.on_drop)
        win.add_controller(target)

        self.refresh_mine()
        self.pool.submit(self.safe, self.build_profile)

    def on_hidden(self):
        self.close_preview()
        GLib.timeout_add_seconds(5, self.preload_explore)
        GLib.timeout_add(1500, lambda: (tui.trim_memory(), False)[1])

    def can_back(self):
        return bool(self.preview) or self.win.current_tab() != "mine"

    TAB_TITLES = {"mine": "meine", "explore": "entdecken"}

    def swipe_where(self):
        if self.preview:
            return ("preview", id(self.preview)), "vorschau"
        tab = self.win.current_tab()
        return ("tab", tab), self.TAB_TITLES.get(tab, tab)

    def swipe_target(self):
        tab = self.win.current_tab() if self.preview else "mine"
        return ("tab", tab), self.TAB_TITLES.get(tab, tab)

    def swipe_goto(self, key):
        if key[0] != "tab":
            return False
        self.win.show_tab(key[1])
        return True

    def go_back(self):
        if self.preview:
            self.close_preview()
        else:
            self.win.show_tab("mine")

    def show_tab(self, name):
        if name == "explore" and not self.seen and self.pending == 0:
            self.start_search()

    # ---------- Meine Wallpaper ----------
    def build_mine(self):
        box = tui.vbox(spacing=6)
        self.mine_info = tui.label("", "dim", hexpand=True, ellipsize=True)
        bar = tui.hbox(self.mine_info,
                       button("󰉋 ordner", lambda: Gtk.FileLauncher(file=Gio.File.new_for_path(WALL_DIR))
                              .launch(self.win, None, None), "Im Dateimanager öffnen"),
                       button("󰐕 hinzufügen", self.on_add, "Strg+O – oder Bilder ins Fenster ziehen, oder Strg+V"),
                       spacing=8)
        bar.add_css_class("wl-bar")
        box.append(bar)
        self.warn = tui.label("", "warn", wrap=True)
        self.warn.add_css_class("banner")
        self.warn.set_visible(False)
        box.append(self.warn)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.mine_flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                     column_spacing=12, row_spacing=12, max_children_per_line=8,
                                     margin_bottom=12, valign=Gtk.Align.START)
        self.mine_flow.add_css_class("wl-mine")
        scroll.set_child(self.mine_flow)
        box.append(scroll)
        self._refresh_pending = False
        return box

    def queue_refresh(self):
        if not self._refresh_pending:
            self._refresh_pending = True
            GLib.timeout_add(400, self.refresh_mine)

    def refresh_mine(self):
        self._refresh_pending = False
        tui.clear(self.mine_flow)
        files = wall_files()
        cur = current_wallpaper()
        self.mine_flow.append(self.add_tile())
        for path in files:
            self.mine_flow.append(self.wall_tile(path, os.path.realpath(path) == cur))
        n = len(files)
        if ROTATION:
            self.mine_info.set_label(f"super+w wählt zufällig aus {n} bild{'ern' if n != 1 else ''} · "
                                     f"~/.config/wallpapers")
        else:
            self.mine_info.set_label(f"{n} bild{'er' if n != 1 else ''} in ~/.config/wallpapers · "
                                     f"klick auf „setzen“ macht es zum hintergrund")
        if n < 2 and ROTATION:
            self.warn.set_label("super+w braucht mindestens 2 bilder, damit es wechseln kann – füge noch welche hinzu.")
        self.warn.set_visible(n < 2 and ROTATION)
        return False

    def add_tile(self):
        f = Frame("neu", dashed=True)
        inner = tui.vbox(tui.label("󰐕", "wl-add", xalign=0.5), tui.label("bilder hinzufügen", xalign=0.5),
                         tui.label("klicken, hierher ziehen oder strg+v", "wl-add-sub", xalign=0.5),
                         spacing=4, valign=Gtk.Align.CENTER, vexpand=True)
        f.set_size_request(TW + 20, TH + 80)
        f.append(inner)
        f.set_valign(Gtk.Align.FILL)          # so hoch wie die Bildkacheln daneben
        f.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.on_add())
        f.add_controller(click)
        return f

    def wall_tile(self, path, is_current):
        name = os.path.relpath(path, WALL_DIR)
        tile = Frame(os.path.splitext(name)[0], "● aktuell" if is_current else "")
        tile.set_active(is_current)
        pic = Thumb()
        tile.append(pic)
        meta = tui.label(human_size(os.path.getsize(path)), "meta", ellipsize=True)
        tile.append(meta)
        set_b = button("󰸉 setzen", lambda: self.apply_wallpaper(path), "Jetzt als Hintergrund setzen, mit passenden Farben")
        set_b.set_sensitive(not is_current)
        rm_b = button("󰆴 entfernen", lambda: self.remove_wallpaper(path), "Aus der Rotation nehmen", danger=True)
        tile.append(tui.hbox(set_b, tui.label("", hexpand=True), rm_b, spacing=6))

        def work():
            key = file_key(path)
            tpath = os.path.join(THUMBS, key + ".png")
            img = None
            if not os.path.exists(tpath):
                img = Image.open(path)
                with open(tpath + ".tmp", "wb") as f:
                    f.write(make_thumb(img))
                os.replace(tpath + ".tmp", tpath)
            w, h, fmt = self.feat_cache.get(key, {}).get("size") or (None, None, None)
            if w is None:
                img = img or Image.open(path)
                (w, h), fmt = img.size, img.format
            if img is not None:
                img.close()
            png = open(tpath, "rb").read()

            def show():
                pic.set_png(png)
                if os.path.exists(path):
                    meta.set_label(f"{(fmt or '?').lower()} · {w}×{h} · {human_size(os.path.getsize(path))}")
                if not is_current:
                    tile.set_tag(res_tag(w, h))
                return False
            GLib.idle_add(show)
        self.pool.submit(self.safe, work)
        return tile

    def safe(self, fn, *a):
        try:
            fn(*a)
        except Exception as e:
            print("wallist:", repr(e), file=sys.stderr)

    # ---------- Stil-Profil ----------
    def build_profile(self):
        prof = []
        changed = False
        for path in wall_files():
            try:
                key = file_key(path)
                entry = self.feat_cache.get(key) or {}
                kind = "clip" if src.clip_available() else "color"
                if "f" not in entry or entry["f"][0] != kind:
                    with Image.open(path) as img:
                        entry.update({"f": src.features(img), "size": [img.size[0], img.size[1], img.format]})
                    with self.cache_lock:
                        self.feat_cache[key] = entry
                    changed = True
                prof.append(entry["f"])
            except Exception as e:
                print("Profil:", path, e, file=sys.stderr)
        with self.profile_lock:
            self.profile = prof
        if changed:
            with self.cache_lock:
                save_json(FEAT_FILE, self.feat_cache)

    # ---------- Wallpaper setzen / entfernen ----------
    def apply_wallpaper(self, path):
        if shutil.which("awww") and os.access(APPLY_COLORS, os.X_OK):
            # genau wie Super+W: awww setzt das Bild, apply-colors.sh baut die Farben und merkt sich das Bild
            Gio.Subprocess.new(["sh", "-c", 'awww img "$1" && "$2" "$1"', "sh", path, APPLY_COLORS],
                               Gio.SubprocessFlags.NONE)
            self.notify(f"setze {os.path.basename(path)} …")
            return
        cmd = desktop_setter(path)
        if not cmd:
            self.notify("diese arbeitsumgebung kann wallist nicht direkt setzen – bild liegt im ordner", error=True)
            return
        try:
            Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error as e:
            self.notify(f"setzen fehlgeschlagen: {e.message}", error=True)
            return
        try:
            os.makedirs(os.path.dirname(OWN_CURRENT), exist_ok=True)
            with open(OWN_CURRENT, "w") as f:
                f.write(path)
        except OSError:
            pass
        self.notify(f"setze {os.path.basename(path)} …")
        GLib.timeout_add(500, lambda: (self.queue_refresh(), False)[1])

    def remove_wallpaper(self, path):
        files = wall_files()
        if len(files) <= 2 and ROTATION:
            self.notify("mindestens 2 bilder müssen bleiben, sonst kann super+w nicht wechseln", error=True)
            return
        if os.path.realpath(path) == current_wallpaper() and len(files) > 1:
            # sonst zeigt der Login-Start auf ein Bild, das es nicht mehr gibt
            others = [f for f in files if f != path]
            self.apply_wallpaper(random.choice(others))
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(REMOVED, f"{stamp}__{os.path.basename(path)}")
        shutil.move(path, dest)
        self._undo = (dest, path)
        self.notify(f"{os.path.basename(path)} entfernt", undo=True)

    def do_undo(self):
        if self._undo:
            dest, path = self._undo
            if os.path.exists(dest) and not os.path.exists(path):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.move(dest, path)
                self.notify(f"{os.path.basename(path)} ist wieder da")
            self._undo = None
        self.undo_btn.set_visible(False)

    def cleanup_removed(self):
        limit = time.time() - 30 * 86400
        for f in os.listdir(REMOVED):
            p = os.path.join(REMOVED, f)
            if os.path.getmtime(p) < limit:
                os.remove(p)

    # ---------- Hinzufügen (Dateien, Zwischenablage, Downloads) ----------
    def on_add(self, *_):
        f = Gtk.FileFilter(name="Bilder")
        f.add_mime_type("image/*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dlg = Gtk.FileDialog(title="Bilder zur Rotation hinzufügen", filters=filters,
                             initial_folder=Gio.File.new_for_path(os.path.expanduser("~/Pictures")))
        dlg.open_multiple(self.win, None, self.on_add_done)

    def on_add_done(self, dlg, res):
        try:
            files = dlg.open_multiple_finish(res)
        except GLib.Error:
            return
        self.add_paths([files.get_item(i).get_path() for i in range(files.get_n_items())])

    def add_paths(self, paths):
        def work():
            ok, msgs = 0, []
            for p in paths:
                try:
                    with open(p, "rb") as f:
                        data = f.read()
                    r = self.store_image(data, os.path.splitext(os.path.basename(p))[0])
                    ok += r is True
                    if isinstance(r, str):
                        msgs.append(r)
                except Exception:
                    msgs.append(f"{os.path.basename(p)}: kein lesbares bild")
            GLib.idle_add(self.notify, f"{ok} bild{'er' if ok != 1 else ''} hinzugefügt" if ok else
                          (msgs[0] if msgs else "nichts hinzugefügt"))
        self.pool.submit(self.safe, work)

    def existing_hashes(self):
        hs = {}
        for p in wall_files():
            key = file_key(p)
            with self.cache_lock:
                e = self.feat_cache.setdefault(key, {})
            if "sha" not in e:
                with open(p, "rb") as f:
                    e["sha"] = hashlib.sha1(f.read()).hexdigest()
            hs[e["sha"]] = p
        return hs

    def store_image(self, data, stem, source_id=None):
        """Prüft das Bild und legt es fertig in den Ordner. True, oder eine Meldung als Text."""
        img = src.image_from_bytes(data)
        w, h = img.size
        if w < 1280 or h < 720:
            return f"{stem}: zu klein für ein wallpaper ({w}×{h})"
        sha = hashlib.sha1(data).hexdigest()
        if sha in self.existing_hashes():
            return f"{stem} ist schon {IN_ROT}"
        rotated = (img.getexif() or {}).get(0x0112, 1) != 1
        if img.format in OK_FORMATS and not rotated:
            ext, out = OK_FORMATS[img.format], data
        else:  # unbekanntes Format oder gedrehtes Handyfoto: sauber als PNG ablegen
            im = ImageOps.exif_transpose(img).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "PNG")
            ext, out = ".png", buf.getvalue()
        stem = "".join(c if c.isalnum() or c in "-_." else "-" for c in stem)[:60] or "wallpaper"
        dest = os.path.join(WALL_DIR, stem + ext)
        i = 2
        while os.path.exists(dest):
            dest = os.path.join(WALL_DIR, f"{stem}-{i}{ext}")
            i += 1
        # Zwischendatei neben (nicht in) dem Ordner: gleiches Laufwerk, also ist das Verschieben atomar,
        # und Super+W sieht die Datei erst, wenn sie vollständig ist
        tmp_dir = os.path.join(os.path.dirname(WALL_DIR), ".wallist-tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp = os.path.join(tmp_dir, os.path.basename(dest) + ".part")
        with open(tmp, "wb") as f:
            f.write(out)
        os.replace(tmp, dest)
        if source_id:
            self.added[source_id] = os.path.basename(dest)
            save_json(ADDED_FILE, self.added)
        self.pool.submit(self.safe, self.build_profile)  # neue Bilder schärfen den Stil-Vergleich
        return True

    def on_paste(self, *_):
        focus = self.win.get_focus()
        if isinstance(focus, Gtk.Text):          # im Stichwort-Feld: normal Text einfügen
            focus.emit("paste-clipboard")
            return
        cb = self.win.get_clipboard()
        fmts = cb.get_formats()
        if fmts.contain_gtype(Gdk.FileList.__gtype__):
            cb.read_value_async(Gdk.FileList.__gtype__, GLib.PRIORITY_DEFAULT, None,
                                lambda c, r: self.add_paths([f.get_path() for f in c.read_value_finish(r).get_files()
                                                             if f.get_path()]))
        elif fmts.contain_gtype(Gdk.Texture.__gtype__):
            def got(c, r):
                try:
                    png = c.read_texture_finish(r).save_to_png_bytes().get_data()
                except GLib.Error:
                    return self.notify("in der zwischenablage ist kein bild", error=True)
                stem = "eingefuegt-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                self.pool.submit(self.safe, lambda: GLib.idle_add(self.notify, self.result_text(self.store_image(png, stem))))
            cb.read_texture_async(None, got)
        else:
            self.notify("in der zwischenablage ist kein bild", error=True)

    def result_text(self, r):
        return "bild hinzugefügt" if r is True else r

    def on_drop(self, target, value, x, y):
        if isinstance(value, Gdk.Texture):
            png = value.save_to_png_bytes().get_data()
            stem = "gezogen-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            self.pool.submit(self.safe, lambda: GLib.idle_add(self.notify, self.result_text(self.store_image(png, stem))))
        else:
            self.add_paths([f.get_path() for f in value.get_files() if f.get_path()])
        self.win.show_tab("mine")
        return True

    # ================= Entdecken =================
    def build_explore(self):
        box = tui.vbox(spacing=8)
        panel = tui.Panel("suche")
        body = panel.body
        body.set_spacing(6)

        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6,
                                 max_children_per_line=12, hexpand=True, homogeneous=False)
        self.kw_entry = tui.Entry("+ stichwort", width=16, activate=lambda: self.on_add_keyword(self.kw_entry))
        self.kw_entry.set_valign(Gtk.Align.START)
        row = tui.hbox(tui.label("stil", "wl-key"), self.chips, self.kw_entry, spacing=8)
        row.get_first_child().set_valign(Gtk.Align.START)
        body.append(row)

        # Filter als umbrechende Gruppen, damit das Fenster auch halb breit funktioniert
        opts = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=22, row_spacing=6,
                           max_children_per_line=6, homogeneous=False)

        def group(title, *widgets):
            g = tui.hbox(spacing=4)
            if title:
                g.append(tui.label(title, "wl-key"))
            for w in widgets:
                g.append(w)
            opts.append(g)

        srcs = [tui.Check(name.lower(), self.settings["sources"].get(name, True),
                          lambda on, name=name: self.set_source(name, on)) for name in ("Wallhaven", "Pinterest", "Cosmos")]
        group("quellen", *srcs)
        sw, sh = self.screen_size()
        self.q_checks = {}
        for q, text, tip in (("screen", f"≥ {sw}×{sh}", "Mindestens so scharf wie dein Bildschirm"),
                             ("fhd", "≥ 1920×1080", None)):
            self.q_checks[q] = tui.Check(text, self.settings["quality"] == q, lambda on, q=q: self.set_quality(q),
                                         tooltip=tip)
        group("qualität", *self.q_checks.values())
        self.match_chk = tui.Check("nur passende", self.settings["only_matching"], self.on_match_toggled,
                                   tooltip=f"Blendet Bilder mit weniger als {MATCH_MIN} % Stil-Übereinstimmung aus")
        group(None, self.match_chk, button("󰑐 neu suchen", self.start_search, "Strg+R"))
        body.append(opts)

        self.spin = tui.label("", "wl-spin")
        self.status_lbl = tui.label("", "dim", hexpand=True, wrap=True)
        body.append(tui.hbox(self.spin, self.status_lbl, spacing=6))
        box.append(panel)

        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        inner = tui.vbox(spacing=12, margin_bottom=12, margin_top=4)
        self.res_flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                    column_spacing=12, row_spacing=12, max_children_per_line=8,
                                    valign=Gtk.Align.START)
        self.res_flow.add_css_class("wl-explore")
        self.res_flow.set_sort_func(lambda a, b: b.score - a.score)
        self.res_flow.set_filter_func(lambda c: not self.settings["only_matching"] or c.score >= MATCH_MIN)
        inner.append(self.res_flow)
        self.more_btn = button("mehr laden", self.load_more)
        self.more_btn.set_halign(Gtk.Align.CENTER)
        self.more_btn.set_visible(False)
        inner.append(self.more_btn)
        scroll.set_child(inner)
        box.append(scroll)
        self.refresh_chips()
        return box

    def refresh_chips(self):
        tui.clear(self.chips)
        for kw in self.settings["keywords"]:
            t = tui.Check(kw, kw in self.settings["active"], lambda on, kw=kw: self.toggle_keyword(kw, on),
                          tooltip="An/aus: wird bei der Suche verwendet")
            x = Gtk.Button(label="✕", tooltip_text="Stichwort löschen", valign=Gtk.Align.CENTER)
            x.add_css_class("flat")
            x.connect("clicked", lambda *_, kw=kw: self.remove_keyword(kw))
            chip = tui.hbox(t, x, spacing=0, halign=Gtk.Align.START)
            chip.add_css_class("wl-chip")
            self.chips.append(chip)

    def save_settings(self):
        save_json(CFG_FILE, self.settings)

    def set_setting(self, key, value, research=False):
        self.settings[key] = value
        self.save_settings()
        if research:
            self.start_search()

    def set_quality(self, q):
        for k, chk in self.q_checks.items():      # verhält sich wie Radioknöpfe
            chk.set_active(k == q)
        if self.settings["quality"] != q:
            self.set_setting("quality", q, research=True)

    def set_source(self, name, on):
        self.settings["sources"][name] = on
        self.save_settings()

    def on_match_toggled(self, on):
        self.settings["only_matching"] = on
        self.save_settings()
        self.res_flow.invalidate_filter()
        self.update_status()

    def toggle_keyword(self, kw, on):
        act = [k for k in self.settings["active"] if k != kw] + ([kw] if on else [])
        self.set_setting("active", act)

    def remove_keyword(self, kw):
        self.settings["keywords"].remove(kw)
        self.settings["active"] = [k for k in self.settings["active"] if k != kw]
        self.save_settings()
        self.refresh_chips()

    def on_add_keyword(self, entry):
        kw = entry.get_text().strip()
        if kw and kw not in self.settings["keywords"]:
            self.settings["keywords"].append(kw)
            self.settings["active"].append(kw)
            self.save_settings()
            self.refresh_chips()
        entry.set_text("")

    # ---------- Suche ----------
    def start_search(self):
        self.searched_at = time.time()
        self.search_gen += 1
        tui.clear(self.res_flow)
        self.seen = set(self.added)
        self.pages = {}
        self.found = 0
        self.pending = 0
        jobs = [(s, kw) for kw in self.settings["active"] for s, on in self.settings["sources"].items() if on]
        if not jobs:
            self.update_status()
            self.status_lbl.set_label("wähle mindestens ein stichwort und eine quelle.")
            return
        for s, kw in jobs:
            self.pages[(s, kw)] = [1, True]
            self.run_search(s, kw, 1)
        self.update_status()

    def load_more(self):
        for (s, kw), (page, more) in list(self.pages.items()):
            if more:
                self.pages[(s, kw)][0] = page + 1
                self.run_search(s, kw, page + 1)
        self.update_status()

    def run_search(self, source, kw, page):
        gen = self.search_gen
        self.pending += 1
        mw, mh = self.min_size()

        def work():
            try:
                if source == "Wallhaven":
                    res, more = src.search_wallhaven(kw, mw, mh, page)
                elif source == "Pinterest":
                    with self.pin_lock:
                        res, more = self.pinterest.search(kw, mw, mh, page)
                else:
                    res, more = src.search_cosmos(kw, mw, mh, page)
                err = None
            except Exception as e:
                res, more, err = [], False, e
            GLib.idle_add(self.on_results, gen, source, kw, res, more, err)
        self.search_pool.submit(work)

    def on_results(self, gen, source, kw, res, more, err):
        if gen != self.search_gen:
            return False
        self.pending -= 1
        if (source, kw) in self.pages:
            self.pages[(source, kw)][1] = more
        if err:
            print(f"{source} ({kw}):", err, file=sys.stderr)
            self.last_error = f"{source.lower()} gerade nicht erreichbar"
        for r in res:
            if r["id"] in self.seen or r["full"] in self.seen:
                continue
            self.seen.update((r["id"], r["full"]))
            self.pending += 1
            self.pool.submit(self.prepare_result, gen, r)
        self.update_status()
        return False

    def prepare_result(self, gen, r):
        if gen != self.search_gen:                  # neue Suche gestartet: alte Vorschauen nicht mehr laden
            GLib.idle_add(self.add_result, gen, r, None)
            return
        try:
            data = src.http_get(r["thumb"])
            img = src.image_from_bytes(data)
            with self.profile_lock:
                prof = list(self.profile)
            r["score"] = src.style_score(src.features(img), prof)
            png = make_thumb(img, 560)
        except Exception as e:
            print("Vorschau:", r.get("thumb"), e, file=sys.stderr)
            png = None
        GLib.idle_add(self.add_result, gen, r, png)

    def add_result(self, gen, r, png):
        if gen != self.search_gen:
            return False
        self.pending -= 1
        if png:
            self.found += 1
            self.res_flow.append(self.result_tile(r, png))
        self.update_status()
        return False

    def _spin(self):
        self._spin_i += 1
        self.spin.set_label(SPIN[self._spin_i % len(SPIN)])
        return True

    def update_status(self):
        shown = sum(1 for c in self.iter_children(self.res_flow) if c.get_child_visible())
        busy = self.pending > 0
        if busy and not self._spin_id:
            self._spin_id = GLib.timeout_add(90, self._spin)
        elif not busy and self._spin_id:
            GLib.source_remove(self._spin_id)
            self._spin_id = None
        self.spin.set_label(SPIN[self._spin_i % len(SPIN)] if busy else "▸")
        txt = f"{self.found} bilder gefunden"
        if self.settings["only_matching"] and self.found:
            txt += f", {shown} passen zu deinem stil"
        if not src.clip_available():
            txt += " · stil-ki nicht eingerichtet (setup-ki.sh), bewertung nur grob über farben"
        if busy:
            txt = "suche läuft … " + txt
        elif self.found == 0:
            txt = "nichts gefunden – probier andere stichworte oder ≥ 1920×1080."
        if self.last_error:
            txt += f" · {self.last_error}"
            self.last_error = None
        self.status_lbl.set_label(txt)
        self.more_btn.set_visible(not busy and any(m for _, m in self.pages.values()))

    def iter_children(self, flow):
        c = flow.get_first_child()
        while c:
            yield c
            c = c.get_next_sibling()

    def result_tile(self, r, png):
        child = Gtk.FlowBoxChild()
        child.score = r.get("score", 0)
        w, h = r["width"], r["height"]
        tile = Frame(r["source"].lower(), res_tag(w, h))
        pic = Thumb()
        pic.set_png(png)
        pic.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        pic.set_tooltip_text("Klicken für große Vorschau")
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.open_preview(r, png, add_btn, child))
        pic.add_controller(click)
        tile.append(pic)
        meter = tui.Meter(interactive=False, small=True, mark=False)
        meter.set_value(child.score)
        meter.set_tooltip_text("Wie gut das Bild zu deinen Wallpapern passt")
        tile.append(tui.hbox(tui.label("stil", "meta"), meter, tui.label(f"{child.score} %", "score", xalign=1),
                             spacing=6))
        add_btn = button(f"󰐕 {TO_ROT}", lambda: self.download(r, add_btn))
        tile.append(tui.hbox(add_btn, tui.label("", hexpand=True), tui.label(f"{w}×{h}", "meta"), spacing=6))
        child.set_child(tile)
        child.r, child.png, child.add_btn = r, png, add_btn      # fürs Blättern in der großen Vorschau
        return child

    def download(self, r, btn, after=None):
        btn.set_sensitive(False)
        btn.set_label("lädt volle auflösung …")

        def work():
            try:
                data = src.http_get(r["full"], timeout=90)
                res = self.store_image(data, r["id"], source_id=r["id"])
            except Exception as e:
                res = f"download fehlgeschlagen: {e}"
            GLib.idle_add(done, res)

        def done(res):
            if res is True:
                btn.set_label(f"󰄬 {IN_ROT}")
                self.notify("hinzugefügt – super+w kann es ab jetzt wählen" if ROTATION else "zur sammlung hinzugefügt")
            else:
                btn.set_label(f"󰐕 {TO_ROT}")
                btn.set_sensitive(True)
                self.notify(res, error=True)
            if after:
                after(res)
            return False
        self.pool.submit(work)

    def preview_step(self, d):
        """← / →: in der großen Vorschau zum vorigen/nächsten Bild der Ergebnisliste (sortierte Reihenfolge)."""
        child = getattr(self, "preview_child", None)
        if not self.preview or child is None or child.get_parent() is None:
            return
        nxt = self.res_flow.get_child_at_index(child.get_index() + d)
        if nxt is None or not hasattr(nxt, "r"):
            if d > 0 and self.pending == 0:
                self.load_more()
                self.notify("letztes bild – lade weitere …")
            else:
                self.notify("erstes bild" if d < 0 else "letztes bild – weitere werden geladen …")
            return
        self.open_preview(nxt.r, nxt.png, nxt.add_btn, nxt)
        GLib.idle_add(lambda: (self._scroll_to(nxt), False)[1])

    def _scroll_to(self, child):
        """Kachel des gerade gezeigten Bilds in der Liste sichtbar halten."""
        sc = self.res_flow.get_ancestor(Gtk.ScrolledWindow)
        ok, pt = child.compute_point(self.res_flow, Graphene.Point()) if child.get_parent() else (False, None)
        if not sc or not ok:
            return
        a = sc.get_vadjustment()
        y, h = pt.y, child.get_height()
        if y < a.get_value():
            a.set_value(y)
        elif y + h > a.get_value() + a.get_page_size():
            a.set_value(y + h - a.get_page_size())

    def open_preview(self, r, png, tile_btn, child=None):
        self.close_preview()
        self.preview_child = child
        back = tui.vbox(spacing=0)
        back.add_css_class("wl-backdrop")
        card = Frame(f"vorschau · {r['source'].lower()}", f"{r['width']}×{r['height']}", spacing=10, hover=False)
        card.add_css_class("wl-preview")
        card.set_active(True)
        card.set_halign(Gtk.Align.FILL)
        card.set_valign(Gtk.Align.FILL)
        card.set_vexpand(True)
        for side in ("top", "bottom", "start", "end"):
            getattr(card, f"set_margin_{side}")(28)
        back.append(card)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, paintable=texture(png), vexpand=True)
        card.append(pic)
        nav = " · ← → blättern" if child is not None else ""
        info = tui.label(f"stil {r.get('score', 0)} % · lädt volle auflösung …{nav}", "dim", hexpand=True, wrap=True)
        add = button(f"󰐕 {TO_ROT}")
        if not tile_btn.get_sensitive():
            add.set_sensitive(False)
            add.set_label(tile_btn.get_label())
        add.connect("clicked", lambda *_: self.download(r, add, after=lambda res: res is True and (
            tile_btn.set_label(f"󰄬 {IN_ROT}"), tile_btn.set_sensitive(False))))
        card.append(tui.hbox(info, button("󰏌 quelle", lambda: Gtk.UriLauncher(uri=r["page"]).launch(self.win, None, None),
                                          "Seite der Quelle im Browser öffnen"),
                             add, button("✕ schließen", self.close_preview, "Esc"), spacing=8))
        click = Gtk.GestureClick()  # Klick neben die Karte schließt
        click.connect("released", lambda g, n, x, y: card.contains(*back.translate_coordinates(card, x, y))
                      or self.close_preview())
        back.add_controller(click)
        self.overlay.add_overlay(back)
        self.preview = back

        def work():  # scharfe Vorschau nachladen, ohne den Ordner anzufassen
            try:
                img = src.image_from_bytes(src.http_get(r["full"], timeout=90))
                big = make_thumb(img, 2400)
                size = img.size
                img.close()

                def show():
                    if back is self.preview:
                        pic.set_paintable(texture(big))
                        card.set_tag(f"{size[0]}×{size[1]}")
                        info.set_label(f"stil {r.get('score', 0)} % · volle auflösung{nav}")
                    return False
                GLib.idle_add(show)
            except Exception:
                GLib.idle_add(lambda: (info.set_label("volle auflösung nicht ladbar"), False)[-1])
        self.pool.submit(work)

    def close_preview(self):
        self.preview_child = None
        if self.preview:
            self.overlay.remove_overlay(self.preview)
            tui.release_later(self.preview)       # samt großer Textur wirklich freigeben
            self.preview = None

    # ================= Meldungen =================
    def notify(self, msg, undo=False, error=False):
        self.win.say(msg, error=error, seconds=8 if undo else 5)
        self.undo_btn.set_visible(undo)
        if self._undo_id:
            GLib.source_remove(self._undo_id)
            self._undo_id = None
        if undo:
            self._undo_id = GLib.timeout_add_seconds(8, self._hide_undo)
        return False

    def _hide_undo(self):
        self.undo_btn.set_visible(False)
        self._undo_id = None
        return False


if __name__ == "__main__":
    if "--quit" in sys.argv:                 # Hintergrund-Instanz beenden (z. B. nach einem Update)
        app = Wallist()
        app.register(None)
        if app.get_is_remote():
            app.activate_action("quit", None)
        sys.exit(0)
    if "--daemon" in sys.argv:               # Autostart: unsichtbar vorbereiten
        app = Wallist()
        app.register(None)
        if app.get_is_remote():
            sys.exit(0)
        app.daemon = True
        sys.exit(app.run([sys.argv[0]]))
    sys.exit(Wallist().run(sys.argv))
