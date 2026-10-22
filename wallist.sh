#!/usr/bin/env bash
# Starter für wallist. Läuft wallist schon (auch unsichtbar im Hintergrund), geht der Aufruf direkt per D-Bus
# hin – ohne Python-/GTK-Start, das Fenster ist sofort da. Sonst wird wallist gestartet (mit Stil-KI-Umgebung,
# falls eingerichtet: ~/.local/share/wallist/setup-ki.sh).
#   wallist [bild …]   wallist --daemon   wallist --quit
APP=de.invincible.Wallist
d=$HOME/.local/share/wallist
if [ $# -eq 0 ] && gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner "$APP" 2>/dev/null | grep -q true; then
    gdbus call --session --dest "$APP" --object-path /de/invincible/Wallist \
        --method org.freedesktop.Application.Activate "{}" >/dev/null 2>&1 && exit 0
fi
py=$d/venv/bin/python
[ -x "$py" ] || py=python3
exec "$py" "$d/wallist.py" "$@"
