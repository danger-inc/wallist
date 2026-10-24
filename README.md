# wallist

wallpapers in the terminal look of the suite (gtk4): manage your collection in `~/.config/wallpapers`,
set an image with one click and find new ones under **entdecken** (wallhaven, pinterest, cosmos),
sorted by how well they fit the images you already have.

## install – linux

```bash
gh auth login                                   # login once (repository is private, invitation needed)
gh repo clone danger-inc/wallist ~/wallist-src
cd ~/wallist-src && ./install.sh
```

the installer asks for the system packages (gtk4, pygobject, pillow, numpy – password once), copies wallist
to `~/.local/share/wallist` and creates the command `wallist` and a menu entry. the icons are bundled,
no nerd font needed.

at the end it asks about the **style model** (optional, ~90 mb): a small image model (clip) that runs entirely on
your machine and rates how well a found image fits your collection. without it wallist only compares
colors roughly. later: `~/.local/share/wallist/setup-ki.sh`.

## usage

* **¹ meine** – all images from `~/.config/wallpapers`. "setzen" makes an image the wallpaper, ✕ removes it
(can be undone for 30 days). new images: "hinzufügen" (ctrl+o), drag them into the window or ctrl+v.
* **² entdecken** – tick search terms on and off, pick sources; clicking an image shows it large,
**← / →** flip through, "zur sammlung" downloads it in full resolution.
* **back:** two fingers to the right on the touchpad (or the mouse back button) closes the preview and
returns to "meine". esc closes the preview too.

setting works on gnome, kde plasma, cinnamon, mate, xfce and with swww/awww, swaybg (sway & co.) and feh (x11).
on hyprland with its own super+w random rotation (`~/.config/hypr/random_wall.sh`) wallist shows what
super+w picks from instead, and recolors through your own color script when setting.

## runs on

| system | status |
| --- | --- |
| ubuntu 24.04+, linux mint 22+, debian 13 | should work |
| fedora 39+ | should work |
| arch, endeavouros, cachyos, manjaro | tested |
| openSUSE Tumbleweed | should work (untested) |

required is **gtk 4.12 or newer** (ubuntu 22.04 / mint 21 / debian 12 are too old). linux only.

## update / remove

`./update.sh` · `./uninstall.sh` (your images in `~/.config/wallpapers` stay)

## problems?

* **boxes instead of symbols:** `./update.sh` – the icon font comes along.
* **`wallist: command not found`:** `~/.local/bin` is missing in `PATH` (the installer shows what belongs in
`~/.bashrc`).
* **"diese arbeitsumgebung kann wallist nicht direkt setzen":** your desktop isn't recognized – the image
still ends up in `~/.config/wallpapers` and can be chosen in the system settings.
