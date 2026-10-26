#!/usr/bin/env bash
# wallist entfernen. Deine Bilder in ~/.config/wallpapers bleiben.
set -euo pipefail
RICE="$HOME/.local/share/rice-apps"
pkill -u "$(id -u)" -f "share/wallist/wallist.py" 2>/dev/null || true
rm -rf "$HOME/.local/share/wallist" "$HOME/.cache/wallist"
rm -f "$HOME/.local/bin/wallist" "$HOME/.local/share/applications/wallist.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/wallist.svg"
# gemeinsame Bausteine nur entfernen, wenn keine andere Suite-App (datist, musicalist) sie noch braucht
if [ ! -d "$RICE/calendar" ] && [ ! -d "$RICE/music" ] && [ ! -d "$HOME/.local/share/mailist" ] && [ ! -d "$HOME/.local/share/sharist" ] && [ ! -d "$HOME/.local/share/linguist" ]; then
    rm -rf "$RICE/fonts" "$RICE/tui.py" "$RICE/glass.py" "$RICE/istheme.py" "$RICE/changelog.py" "$RICE/swipe.py" "$RICE/__pycache__"
    rmdir "$RICE" 2>/dev/null || true
fi
echo "wallist entfernt. Deine Bilder liegen weiter in ~/.config/wallpapers (Einstellungen: ~/.config/wallist)."
