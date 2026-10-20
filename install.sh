#!/usr/bin/env bash
# wallist installieren (ins eigene Benutzerverzeichnis, root nur für Systempakete).
#   ./install.sh            normal (fragt nach Systempaketen und der Stil-KI)
#   ./install.sh --update   ohne Rückfragen (von update.sh)
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SRC/pkg.sh"
DIR="$HOME/.local/share/wallist"
RICE="$HOME/.local/share/rice-apps"
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
UPDATE=0; [[ "${1:-}" == "--update" ]] && UPDATE=1

say "== wallist installieren =="
basics_missing() {
    python3 -c 'import gi, PIL, numpy; gi.require_version("Gtk", "4.0")' 2>/dev/null && return 1
    return 0
}
if { (( UPDATE )) && basics_missing && say "Es fehlen Systempakete – werden nachinstalliert …"; } \
   || ask "Systempakete installieren (GTK4, PyGObject, Pillow, numpy)?"; then
    pkg_install \
        "gtk4 python python-gobject python-cairo python-pillow python-numpy adwaita-icon-theme curl xdg-utils" \
        "python3 python3-venv python3-gi python3-gi-cairo gir1.2-gtk-4.0 python3-pil python3-numpy adwaita-icon-theme curl xdg-utils" \
        "python3 python3-gobject python3-cairo gtk4 python3-pillow python3-numpy adwaita-icon-theme curl xdg-utils" \
        "python3 python3-gobject python3-gobject-cairo python3-gobject-Gdk typelib-1_0-Gtk-4_0 python3-Pillow python3-numpy adwaita-icon-theme curl xdg-utils" \
        || warn "Paketinstallation nicht vollständig – weiter."
fi
echo

say "Kopiere wallist nach $DIR …"
mkdir -p "$DIR" "$RICE/fonts" "$BIN" "$APPS" "$ICONS" "$HOME/.config/wallpapers"
cp -f "$SRC"/app/wallist/*.py "$SRC"/app/wallist/VERSION "$SRC"/app/wallist/CHANGELOG.md "$DIR/"
install -m 755 "$SRC/app/wallist/setup-ki.sh" "$DIR/setup-ki.sh"
cp -f "$SRC/app/tui.py" "$SRC/app/glass.py" "$SRC/app/changelog.py" "$SRC/app/swipe.py" "$RICE/"   # gemeinsame Bausteine
cp -f "$SRC"/app/fonts/* "$RICE/fonts/"                           # Symbolschrift (Icons ohne Nerd Font)
install -m 755 "$SRC/wallist.sh" "$BIN/wallist"
sed "s|@EXEC@|$BIN/wallist|g" "$SRC/wallist.desktop.in" > "$APPS/wallist.desktop"
cp -f "$SRC/wallist.svg" "$ICONS/wallist.svg"
refresh_desktop

# Stil-KI (CLIP-Bildmodell, lokal): bewertet, wie gut neue Bilder zu deinen passen. Ohne sie nur grob über Farben.
if (( ! UPDATE )) && [ ! -s "$DIR/models/clip-vit-b32-vision-q.onnx" ]; then
    echo
    if ask "Stil-KI einrichten? (lädt ~90 MB, läuft komplett lokal; später auch mit $DIR/setup-ki.sh)" n; then
        "$DIR/setup-ki.sh" || warn "Stil-KI nicht eingerichtet – wallist läuft trotzdem (Stil nur über Farben)."
    fi
fi

echo
say "Prüfe …"
check_gtk || warn "Ohne passendes GTK startet wallist nicht – siehe README."
python3 -c 'import PIL, numpy' 2>/dev/null && echo "  Pillow/numpy: ok" || warn "  Pillow oder numpy fehlt (python3-pil / python3-numpy)"
if [ -s "$DIR/models/clip-vit-b32-vision-q.onnx" ] && [ -x "$DIR/venv/bin/python" ]; then
    echo "  Stil-KI: eingerichtet"
else
    echo "  Stil-KI: aus (optional: $DIR/setup-ki.sh)"
fi
echo
path_hint
say "Fertig!  Starten mit:  wallist   (oder über das Anwendungsmenü)"
echo "Deine Bilder liegen in ~/.config/wallpapers.   Aktualisieren: ./update.sh   Entfernen: ./uninstall.sh"
