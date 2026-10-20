# Zwei Finger nach rechts wischen (Touchpad) oder Maustaste „zurück“ = eine Ebene zurück, wie im Browser.
# Pfeil-Blase kommt vom linken Rand herein; ist sie voll, löst Loslassen aus, und ein Standbild der alten
# Ansicht gleitet nach rechts weg. Vorlage: filist (views.py). Kopien: notist app/swipe.py, rice-apps/swipe.py.
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

CSS = """
label.swipe-bubble { background-color: alpha(@background, 0.92); border: 2px solid alpha(@primary, 0.7);
    border-radius: 999px; min-width: 44px; min-height: 44px; color: @primary; font-size: 22px; }
label.swipe-bubble.ready { background-color: @primary; border-color: @primary; color: @on_primary; }
"""

DIST = 150           # so weit (px) wischen, bis es auslöst
SIZE = 48
ARROW = "\U000F004D"


class SwipeBack:
    """content in ein Overlay packen (→ .widget einsetzen). can_back() sagt, ob es zurück geht, back() führt es aus.
    blocked(widget) darf True liefern, wenn das Widget unter dem Zeiger das Wischen selbst braucht."""

    def __init__(self, content, can_back, back, blocked=None):
        self.can_back, self.back, self.blocked = can_back, back, blocked
        self.widget = Gtk.Overlay(child=content, hexpand=True, vexpand=True)
        self.widget.set_overflow(Gtk.Overflow.HIDDEN)
        self.layer = Gtk.Fixed(can_target=False)
        self.pic = Gtk.Picture(can_shrink=True, content_fit=Gtk.ContentFit.FILL, visible=False)
        self.bubble = Gtk.Label(label=ARROW, visible=False, xalign=0.5)
        self.bubble.add_css_class("swipe-bubble")
        self.layer.put(self.pic, 0, 0)
        self.layer.put(self.bubble, 0, 0)
        self.widget.add_overlay(self.layer)
        self._st = None
        self._anim = None
        self._tid = None
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        sc.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        sc.connect("scroll-begin", lambda *_: self._begin())
        sc.connect("scroll", self._scroll)
        sc.connect("scroll-end", lambda c: self._end(c))
        self.widget.add_controller(sc)
        mouse = Gtk.GestureClick(button=8)                 # Seitentaste „zurück“ der Maus
        mouse.connect("pressed", lambda *_: self.trigger())
        self.widget.add_controller(mouse)

    def trigger(self, animate=True):
        if self._anim or not self.can_back():
            return False
        self._commit(animate)
        return True

    # ---------- Geste ----------
    def _begin(self):
        self._st = {"dx": 0.0, "dy": 0.0, "lock": None}

    def _target_scrolls(self, ctrl):
        """Liegt unter dem Zeiger etwas, das selbst nach links scrollen kann? Dann gehört die Geste ihm."""
        ev = ctrl.get_current_event()
        native = self.widget.get_native()
        if ev is None or native is None:
            return False
        ok, x, y = ev.get_position() if len(ev.get_position()) == 3 else (True, *ev.get_position())
        if not ok:
            return False
        tx, ty = native.get_surface_transform()
        root = native if isinstance(native, Gtk.Widget) else self.widget.get_root()
        w = root.pick(x - tx, y - ty, Gtk.PickFlags.DEFAULT)
        while w is not None and w is not self.widget:
            if self.blocked and self.blocked(w):
                return True
            if isinstance(w, Gtk.ScrolledWindow):
                a = w.get_hadjustment()
                if a.get_upper() - a.get_lower() > a.get_page_size() + 1 and a.get_value() > a.get_lower() + 0.5:
                    return True
            w = w.get_parent()
        return False

    def _scroll(self, ctrl, dx, dy):
        if ctrl.get_unit() != Gdk.ScrollUnit.SURFACE:      # Mausrad: nichts zu tun
            return False
        st = self._st
        if st is None:                                     # manche Geräte melden kein scroll-begin
            st = self._st = {"dx": 0.0, "dy": 0.0, "lock": None}
        if self._anim:
            return st["lock"] == "h"
        st["dx"] += dx
        st["dy"] += dy
        if st["lock"] is None and abs(st["dx"]) + abs(st["dy"]) > 14:
            # Touchpad „natürlich“ oder nicht: zurück = Finger nach rechts = dx < 0 (wie filist)
            if (st["dx"] < 0 and abs(st["dx"]) > 1.6 * abs(st["dy"]) and self.can_back()
                    and not self._target_scrolls(ctrl)):
                st["lock"] = "h"
            else:
                st["lock"] = "v"
        if st["lock"] != "h":
            return False
        self._show(min(max(0.0, -st["dx"]) / DIST, 1.0))
        if self._tid:
            GLib.source_remove(self._tid)
        self._tid = GLib.timeout_add(600, self._timeout)   # falls kein Ende gemeldet wird
        return True

    def _timeout(self):
        self._tid = None
        self._end(None)
        return False

    def _show(self, p):
        b = self.bubble
        b.set_visible(True)
        h = self.widget.get_height()
        self.layer.move(b, -SIZE + p * (SIZE + 18), max(0, h / 2 - SIZE / 2))
        b.set_opacity(0.35 + 0.65 * p)
        (b.add_css_class if p >= 1 else b.remove_css_class)("ready")

    def _hide(self):
        self.bubble.set_visible(False)
        self.bubble.remove_css_class("ready")

    def _end(self, ctrl):
        if self._tid and ctrl is not None:
            GLib.source_remove(self._tid)
            self._tid = None
        st, self._st = self._st, None
        if not st or st.get("lock") != "h" or self._anim:
            return False
        if -st["dx"] >= DIST and self.can_back():
            self._commit(True)
        else:
            self._hide()
        return False

    def _commit(self, animate):
        w, h = self.widget.get_width(), self.widget.get_height()
        snap = None
        if animate and w > 0:
            try:
                snap = Gtk.WidgetPaintable.new(self.widget.get_child()).get_current_image()
            except Exception:
                snap = None
        self.back()
        if snap is None:
            self._hide()
            return
        pic, bubble = self.pic, self.bubble
        pic.set_paintable(snap)
        pic.set_size_request(w, h)
        self.layer.move(pic, 0, 0)
        pic.set_opacity(1)
        pic.set_visible(True)
        bubble.set_visible(True)
        bx = -SIZE + SIZE + 18
        t0 = [None]
        DUR = 260_000

        def tick(widget, clock):
            now = clock.get_frame_time()
            if t0[0] is None:
                t0[0] = now
            t = min(1.0, (now - t0[0]) / DUR)
            e = 1 - (1 - t) ** 3
            self.layer.move(pic, e * w, 0)
            pic.set_opacity(1 - 0.5 * e)
            self.layer.move(bubble, bx + e * 40, max(0, h / 2 - SIZE / 2))
            bubble.set_opacity(1 - e)
            if t >= 1:
                pic.set_visible(False)
                pic.set_paintable(None)
                self._hide()
                self._anim = None
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        self._anim = self.widget.add_tick_callback(tick)
