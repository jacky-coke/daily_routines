# Fortschrittsbilder (optional)

Im Original-Set-up zeigt das Dashboard während der Morgenroutine ein
KI-generiertes Bild des Kindes, das sich passend zum zuletzt abgehakten
Eintrag ändert (z. B. "Zähne putzen" erledigt → Bild mit Zahnbürste). Das
ist rein kosmetisch und **komplett optional** – die Punktelogik funktioniert
ohne jedes Bild.

Wenn du das übernehmen willst:

1. Lege eigene Bilder unter `/config/www/todo_kind/` ab (dann erreichbar
   unter `/local/todo_kind/<dateiname>`), oder verzichte auf `picture`-Karten
   und behalte nur die Fortschritts-Überschriften ("Aktueller Fortschritt: 4/10").
2. Trage deine Aufgaben → Dateinamen-Zuordnung in
   `automations/bild_aktualisieren.yaml` (`zuordnung:`) ein.
3. Binde die Bilder im Dashboard analog zu `dashboard/routinen_dashboard_view.yaml`
   ein (eine `picture`-Karte pro Bild, sichtbar wenn
   `input_text.kind_routinebild` == Dateiname).

Wenn dir das zu viel Aufwand ist: einfach weglassen und nur die
Fortschritts-Überschriften + das Punkte-Barometer nutzen – das ist der
Kern des Systems.
