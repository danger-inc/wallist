# wallist – Änderungen

## 2.4.0 (2026-10-26)
- **Design wählbar**: In den Einstellungen gibt es die Designauswahl wie in notist (Automatisch + 9 Designs). Die Wahl gilt für alle -ist-Apps zugleich und wirkt sofort. Bei „Automatisch“ (Desktop-Farben) kannst du zwischen **Dunkel** und **Hell** umschalten. Der Knopf „󰏘“ oben rechts öffnet die Auswahl.

## 2.3.1 (2026-10-25)
- **Update-Knopf**: Neben der Versionsnummer steht „󰑐“ – Klick sucht sofort nach einem Update. Gibt es eine neuere
  Version, wird daraus „󰚰 update“; ein Klick lädt und installiert sie (Linux und Windows), danach heißt er „󰑓 neu starten“.
- **Rückmeldung bei Umschalt-Knöpfen**: „An“ (z. B. „Ton behalten“) ist jetzt auch unter dem Mauszeiger zu sehen,
  Drücken färbt sofort – man muss die Maus nicht mehr wegbewegen, um zu sehen, ob der Klick angekommen ist.
- **2 Finger auch vorwärts**: Nach einem Zurück-Wischen bringt das Wischen in die andere Richtung zur verlassenen
  Seite zurück.
- **Windows: echte Titelleiste** – das Fenster lässt sich verschieben, in der Größe ändern, minimieren und
  maximieren.

## 2.3.0 (2026-10-22)
- **Öffnet sofort**: wallist bleibt nach dem Schließen unsichtbar im Hintergrund bereit (wie notist und mailist),
  der nächste Aufruf ist ohne Wartezeit da. Beim Login wird es mit `wallist --daemon` gleich vorbereitet;
  ganz beenden mit `wallist --quit`.
- **„entdecken“ ist schon gefüllt**: Die Suche nach neuen Bildern läuft im Hintergrund, bevor du auf den Tab
  klickst. Vorschläge, die älter als 3 Stunden sind, werden nach dem Schließen still erneuert – nie, während du
  gerade stöberst.

## 2.2.1 (2026-10-20)
- **Neues Zurück-Wischen im -ist-Design**: Beim Wischen mit zwei Fingern schiebt sich die vorige Seite als Rahmen vom Rand herein – mit einem echten Bild davon und ihrem Namen im Chip. Ist der Rahmen durchgezogen, führt Loslassen zurück, und die Seite klappt über das ganze Fenster auf.
- Nach dem Zurück-Wischen springt die Seite nicht mehr ein Stück nach oben (der erste Millimeter der Geste scrollte noch mit und lief nach).

## 2.2.0 (2026-10-20)
- **Zurück wischen**: Zwei Finger nach rechts auf dem Touchpad (oder die Zurück-Taste der Maus) schließen die große
  Vorschau, dann geht es von „entdecken“ zurück zu „meine“ – dort ist Schluss.
- **Blättern in der großen Vorschau** (entdecken): ← und → springen zum vorigen/nächsten Bild in der Reihenfolge der
  Liste; am Ende werden weitere Ergebnisse nachgeladen.
- **Zum Weitergeben**: wallist gibt es jetzt mit Installer (GitHub-Repo, `./install.sh`, `./update.sh`). Ohne
  eigene Super+W-Rotation ist es eine Sammlung, aus der „setzen“ das Hintergrundbild direkt setzt – auf GNOME, KDE,
  Cinnamon, MATE, Xfce, mit swww/awww, swaybg oder feh.

## 2.1.0 (2026-10-19)
- **Neuer Name: wallist** (vorher „wallpapaer“), passend zu den anderen -ist-Apps. Befehl `wallist`;
  Einstellungen und Zwischenspeicher ziehen beim ersten Start automatisch mit um.

## 2.0.0 (2026-10-19)
- **Neuer Look** wie datist, musicalist und filist: Marken-Chip, Tabs ¹ meine ² entdecken (Tasten 1/2),
  Kacheln mit Namen und Auflösung im Rahmen, schmale [ Knöpfe ], [■]-Schalter, Statuszeile mit Tastenhinweisen.
  Farben folgen live dem aktuellen Wallpaper.
- Das aktuelle Wallpaper hat einen hervorgehobenen Rahmen mit „● aktuell“.
- Entdecken: Stil-Übereinstimmung als Balken, Suchfilter in einem Kasten, Ladeanzeige in der Statuszeile.
- Große Vorschau im selben Stil; Esc schließt erst die Vorschau, dann das Fenster.
- „Rückgängig“ nach dem Entfernen steht unten in der Statuszeile.
- Strg+R lädt neu bzw. sucht neu, Strg+V im Stichwort-Feld fügt wieder Text ein.
- **Changelog**: oben rechts auf die Version klicken.
- Auch aus der Apps-Leiste von scourge startbar.
- Kacheln und große Vorschau werden beim Neuaufbau bzw. Schließen wirklich freigegeben (vorher wuchs der
  Speicher bei jedem Wallpaper-Wechsel).

## 1.0.0 (2026-10-16)
- Erste Version: verwaltet den Ordner der Super+W-Rotation (hinzufügen per Dialog, Ziehen oder Strg+V,
  entfernen mit Rückgängig, setzen mit passenden Farben).
- Entdecken: Vorschläge von Wallhaven, Pinterest und Cosmos, bewertet nach Ähnlichkeit zu deinen Wallpapern
  (optional mit Stil-KI).
