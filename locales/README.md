# Lokale Sprachdaten

Dieser öffentliche Fork enthält keine aus privaten Beständen übernommenen
Sprachdateien. Das separat bereitgestellte Datenpaket legt die deutschen
Sprachzuordnungen unter **data/locales/** ab. Sie werden beim Start automatisch
geladen und bei Updates erhalten.

Jeder JSON-Schlüssel hat die Form **Namensraum_ID** und verweist auf ein Paar
**[englischer Originaltext, deutscher Originaltext]**. Platzhalter und
Bildreferenzen bleiben erhalten. Mit **tools/compile_locale.py** lassen sich
weitere eigene Paare englisch/deutscher .lang-Dateien lokal zusammenführen.

Die Anzahl der Sprachzeilen entspricht nicht der Anzahl unterschiedlicher
Zauber. Manche Eigennamen und interne Texte sind im deutschen Original
ebenfalls englisch. Spieltexte gehören ihren jeweiligen Rechteinhabern;
die Code-Lizenz ändert diese Rechte nicht.
