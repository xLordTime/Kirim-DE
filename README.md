# Kirim-DE

Deutsche Version von [Kimerith WindHammer](https://github.com/MajorPain1/Kimerith-WindHammer), dem Wizard101-Discord-Bot von **MajorPain1**.

## Enthalten

- Deutsche Slash-Befehle, Hilfe, Suchmeldungen und Werteanzeigen.
- Deutsche Schul- und Filteranzeigen in einem auf Deutsch eingestellten Discord-Client.
- Deutsche und englische Zaubernamen für die Suche.
- 11.589 Spracheinträge im separat bereitgestellten deutschen Datenpaket.
- Unterstützung bereits deutscher wizdb-Datenbanken für Ausrüstung, Zauber, Gegner, Begleiter und Fische.
- Automatisches Anlegen der **.env**, ohne bestehende Einstellungen zu überschreiben.
- Serverprogramm für Einrichtung, Datenimport, Sicherungen und geprüfte Updates.

Die Spieldatenbank wird separat importiert. Der öffentliche Fork enthält ausschließlich Programmcode und Dokumentation; keine privaten Spieldatensätze, Sprachdateien, Bot-Tokens, Accountdaten oder WAD-Archive. Bilder sind optional und können wie beim Original unter **PNG_Images/** liegen.

## Schnellstart (Linux / Raspberry Pi)

Benötigt werden **Python 3.11 oder neuer**, das Python-venv-Modul und Git. Für das optionale Datenpaket wird ein ZIP-Entpacker benötigt.

```bash
git clone https://github.com/xLordTime/Kirim-DE.git
cd Kirim-DE
python3 server.py setup
```

Das Setup erstellt die Python-Umgebung und die **.env** automatisch. Trage ausschließlich deinen eigenen Discord-Bot-Token unter **DISCORD_TOKEN=** ein. Optional kann **DISCORD_GUILD_ID=** auf deinen Testserver gesetzt werden; dessen Slash-Befehle werden dann sofort synchronisiert.

### Deutsche Spieldaten übernehmen

Das separat bereitgestellte **Kirim-DE-Datenpaket.zip** kann vor oder nach dem Setup in den Projektordner entpackt werden. Bereits vorhandene Dateien erhalten:

```bash
unzip -n /pfad/Kirim-DE-Datenpaket.zip -d .
```

Alternativ eine vorhandene echte **items.db** aus WizLib oder [wizdb](https://github.com/MajorPain1/wizdb) importieren:

```bash
python3 server.py import-db /pfad/zur/items.db
python3 server.py check
python3 server.py run
```

Eine zusätzliche **decks.db** ist optional:

```bash
python3 server.py import-db /pfad/zur/decks.db --decks
```

Ohne separate Deckdatei verwendet Kirim-DE die Deckdaten aus der Spieldatenbank. Eine heruntergeladene Git-LFS-Zeigerdatei ist keine SQLite-Datenbank und wird abgelehnt.

## Dauerbetrieb mit systemd

Das folgende Kommando erstellt eine Vorlage mit deinem aktuellen Benutzer und dem tatsächlichen Projektpfad:

```bash
python3 server.py service
```

Die dabei angezeigten **sudo cp**, **daemon-reload** und **enable --now**-Befehle ausführen. Danach:

```bash
systemctl status kirim-de.service
journalctl -u kirim-de.service -f
```

Der Dienst benötigt keine privilegierten Discord-Intents. Beim Einladen des Bots die Bereiche **bot** und **applications.commands** verwenden und ihm mindestens Kanalzugriff, Nachrichten senden, Links einbetten und optional Dateien anhängen erlauben.

## Updates

Im Projektordner:

```bash
python3 server.py update
# oder
bash update.sh
```

Der Updater:

1. Prüft den Git-Ursprung und lehnt lokale Änderungen an Programmdateien ab.
2. Holt den aktuellen **main**-Stand des Forks; divergierende Historien werden nicht überschrieben.
3. Sichert .env, Spieldatenbanken und eigene Sprachdateien unter **data/backups/**.
4. Installiert neue Abhängigkeiten in einer separaten Umgebung und prüft Module, Datenbank und Tests.
5. Aktualisiert den Code erst nach erfolgreicher Vorprüfung.
6. Startet einen zuvor aktiven **kirim-de.service** neu und wartet auf die Discord-Anmeldung. Bei erkanntem Fehler stellt er den alten Code und die alte Python-Umgebung wieder her.

Im Dienstbetrieb benötigt dein Benutzer sudo-Rechte für die Dienststeuerung. Das Update selbst im gleichen Benutzerkonto ausführen, in dem das Repository eingerichtet wurde. Ohne systemd bleibt der Neustart eines Konsolenprozesses manuell. Ein laufender Vordergrundprozess sollte vor einem Update beendet werden.

Sicherungen enthalten deine lokale Konfiguration und sind deshalb nur für den Dateieigentümer lesbar. Sie werden nicht automatisch gelöscht. Ein Update verändert weder die importierten Spieldaten noch deren Datenstand.

Weitere Befehle:

```bash
python3 server.py backup
python3 server.py check
```

## Windows

Python 3.11+ und Git installieren. Im Projektordner:

```powershell
py -3 server.py setup
py -3 server.py import-db C:\Pfad\items.db
py -3 server.py run
```

**runbot.bat** startet den Bot; **update.bat** führt das Update aus. Die systemd-Vorlage ist ausschließlich für Linux.

## Befehle

| Befehl | Funktion |
| --- | --- |
| /hilfe | Befehlsübersicht |
| /status | Version und Datenumfang |
| /zauber suchen, /zauber liste | Zauber und Effekte |
| /gegenstand suchen, /gegenstand liste | Ausrüstung und Werte |
| /gegner suchen, /gegner liste | Gegnerwerte |
| /gegner deck, /gegner schaden | Gegnerdeck und Schadensrechnung |
| /begleiter suchen, /begleiter liste | Begleiter, Talente und Karten |
| /fisch suchen, /fisch liste | Fischdaten |
| /grenzwerte suchen | Werteobergrenzen |
| /schaden | Schadensrechner |

Deutsche und englische Zaubernamen werden angenommen. Ein Sternchen als Listen-Suchbegriff zeigt alle Einträge mit den gewählten Filtern. Interne Objektnamen und numerische IDs sind zusätzliche Suchoptionen. Grenzen und Sonderregeln entsprechen dem importierten Spielstand; dies ist keine Live-Abfrage der Spielserver.

## Übersetzungen ergänzen

Weitere zusammengehörige englisch/deutsche Originaldateien können ohne Änderung des Botcodes eingebunden werden:

```bash
python3 tools/compile_locale.py EN/Items.lang DE/Items.lang data/locales/items.json
```

Danach den Bot neu starten. Eigene Dateien unter **data/locales/** bleiben bei Updates erhalten. Numerische Sprachschlüssel werden nur bei passendem Originaltext verwendet; mehrdeutige Textzuordnungen werden übersprungen. Fehlt eine Übersetzung, bleibt der vorhandene Text der Spieldatenbank erhalten.

Die separat bereitgestellten Spracheinträge stammen aus dem vorhandenen EU-Datenstand vom August 2026. Der bereitgestellte deutsche Datenbankstand vom 23.08.2026 umfasst 61.737 Ausrüstungs-, 17.302 Zauber-, 6.711 Gegner-, 1.383 Begleiter- und 239 Fischeinträge. Interne Testeinträge und Varianten können darin enthalten sein. Bilder und neuere Spielinhalte werden nicht automatisch aus dem Spiel heruntergeladen.

## Entwicklung und Lizenz

Installation und Updater verwenden **requirements.txt**.

```bash
python -m bot --code-only
python -m unittest discover -s tests -v
```

Der Code basiert auf MajorPain1/Kimerith-WindHammer und dessen Vorarbeiten. Die ursprüngliche GPL-3.0-Lizenz bleibt erhalten; siehe **LICENSE**. Wizard101, Spieltexte und Grafiken gehören den jeweiligen Rechteinhabern. Kirim-DE ist ein unabhängiges Fanprojekt.
