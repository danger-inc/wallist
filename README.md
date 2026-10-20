# wallist

Hintergrundbilder im Terminal-Look der Suite (GTK4): deine Sammlung in `~/.config/wallpapers` verwalten,
ein Bild mit einem Klick setzen und unter **entdecken** neue Wallpaper finden (Wallhaven, Pinterest, Cosmos),
sortiert danach, wie gut sie zu deinen bisherigen Bildern passen.

## Installieren – Linux

```bash
gh auth login                                   # einmalig (Repo ist privat, Einladung nötig)
gh repo clone invincible-nix/wallist ~/wallist-src
cd ~/wallist-src && ./install.sh
```

Der Installer fragt nach den Systempaketen (GTK4, PyGObject, Pillow, numpy – einmal Passwort), kopiert wallist
nach `~/.local/share/wallist` und legt den Befehl `wallist` und einen Menüeintrag an. Die Symbole bringt wallist
selbst mit, eine Nerd Font ist nicht nötig.

Zum Schluss fragt er nach der **Stil-KI** (optional, ~90 MB): ein kleines Bildmodell (CLIP), das komplett auf
deinem Rechner läuft und bewertet, wie gut ein gefundenes Bild zu deiner Sammlung passt. Ohne sie vergleicht
wallist nur grob die Farben. Nachträglich: `~/.local/share/wallist/setup-ki.sh`.

## Bedienung

- **¹ meine** – alle Bilder aus `~/.config/wallpapers`. „setzen“ macht ein Bild zum Hintergrund, ✕ entfernt es
  (30 Tage rückgängig machbar). Neue Bilder: „hinzufügen“ (Strg+O), ins Fenster ziehen oder Strg+V.
- **² entdecken** – Suchbegriffe an- und abhaken, Quellen wählen; Klick auf ein Bild zeigt es groß,
  **← / →** blättern, „zur sammlung“ lädt es in voller Auflösung herunter.
- **Zurück**: zwei Finger nach rechts auf dem Touchpad (oder Zurück-Taste der Maus) schließt die Vorschau und
  führt zurück zu „meine“. Esc schließt die Vorschau ebenfalls.

Setzen klappt auf GNOME, KDE Plasma, Cinnamon, MATE, Xfce sowie mit swww/awww, swaybg (Sway & Co.) und feh (X11).
Auf Hyprland mit eigener Super+W-Zufallsrotation (`~/.config/hypr/random_wall.sh`) zeigt wallist stattdessen,
woraus Super+W wählt, und färbt beim Setzen über das eigene Farbskript mit um.

## Läuft auf

| System | Status |
|---|---|
| Ubuntu 24.04+, Linux Mint 22+, Debian 13 | sollte gehen |
| Fedora 39+ | sollte gehen |
| Arch, EndeavourOS, CachyOS, Manjaro | getestet |
| openSUSE Tumbleweed | sollte gehen (ungetestet) |

Nötig ist **GTK 4.12 oder neuer** (Ubuntu 22.04 / Mint 21 / Debian 12 sind zu alt). Nur Linux.

## Aktualisieren / entfernen

`./update.sh` · `./uninstall.sh` (deine Bilder in `~/.config/wallpapers` bleiben)

## Probleme?

- **Kästchen statt Symbolen:** `./update.sh` – die Symbolschrift kommt mit.
- **`wallist: Befehl nicht gefunden`:** `~/.local/bin` fehlt im PATH (der Installer zeigt, was in die `~/.bashrc`
  gehört).
- **„diese arbeitsumgebung kann wallist nicht direkt setzen“:** deine Oberfläche wird nicht erkannt – das Bild
  liegt trotzdem in `~/.config/wallpapers` und lässt sich in den Systemeinstellungen wählen.
