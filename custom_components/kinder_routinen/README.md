# Kinder-Routinen Punktesystem – Custom Integration (v0.1)

Ersetzt für den Live-Punkte-Teil des Systems das manuelle Anlegen von
Helpern + den Blueprint durch eine echte Home-Assistant-Integration mit
Config-Flow.

## Installation

1. In HACS → "Custom repositories" diese Repo-URL eintragen, Kategorie
   "Integration" (oder den Badge oben im Haupt-README nutzen).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "Kinder-Routinen
   Punktesystem"** – pro Routine (z. B. "Ronja Morgen", "Ronja Mittag") eine
   eigene Instanz anlegen.

Im Formular wählst du: Name, To-Do-Liste (Entity-Picker), Frist-Uhrzeit,
Wochentage, Tagesbonus, Notify-Ziel. Die Aufgabenzahl wird automatisch aus
der gewählten To-Do-Liste ausgelesen – kein manuelles Zählen/Eintragen nötig.

## Was v0.1 tut

- Live-Punktevergabe: Aufgabe vor der Frist abgehakt → sofort 1 Punkt (und
  wieder abgezogen, falls das Häkchen entfernt wird).
- Nächtlicher Reset der To-Do-Liste + Tages-Tracker (23:59 Uhr).
- Wöchentlicher Reset des Wochenzählers (montags 00:01 Uhr).
- Tagesbonus, wenn an einem konfigurierten Wochentag alle Aufgaben der
  Routine fristgerecht erledigt wurden.
- Vier Sensoren pro Routine: *Punkte heute*, *Tagesmax*, *Wochenpunkte*,
  *Punktekonto* – alle mit `unique_id`, über HA-Neustarts hinweg persistiert.

## Was v0.1 (noch) NICHT tut – Roadmap

- **Mehrere Routinen auf ein gemeinsames Punktekonto zusammenführen.**
  Aktuell führt jede Config-Entry (= jede Routine) ihren eigenen
  Wochenzähler/Sparkonto. Für "Morgen + Mittag = ein gemeinsames Konto"
  ist ein Hub-Entry-Modell (HA Subentries) geplant.
- Belohnungs-Auswahl (`select`) + Einlösen-Button (`button`) als native
  Entities, statt `input_select` + Script.
- Freitags-Wochenbericht mit Status/fehlenden Aufgaben pro Wochentag.
- Options-Flow-Feinschliff (z. B. Aufgabenzahl bei Listenänderung neu
  ermitteln).
- Eigene Lovelace-Karte statt der "eine Karte pro Zwischenstand"-Krücke im
  YAML-Dashboard.
- Englische Übersetzung (aktuell nur Deutsch).

## Getestet gegen eine echte Instanz

v0.1 wurde nicht nur geschrieben, sondern auch tatsächlich deployt und
gegen eine frische, isolierte Home-Assistant-Testinstanz (Docker, getrennt
vom Produktivsystem) durchgetestet – inklusive Config-Flow, Live-Update per
Abhaken, Neustart-Verhalten und Options-Flow. Dabei wurden drei echte Bugs
gefunden und gefixt, bevor der Code hier landete:

1. Eine Frist-Uhrzeit von 23:59 ließ die Integration beim Start abstürzen
   (Stunden-Überlauf auf 24 bei der Tagesbonus-Zeitberechnung).
2. Alle vier Sensoren einer Routine bekamen denselben Anzeigenamen
   (fehlende Entity-Namen).
3. Jeder Neustart von Home Assistant schrieb fälschlich einen zusätzlichen
   Punkt gut (ein State-Change-Event ohne echten Vorher-Zustand direkt nach
   dem Neuladen wurde als "Aufgabe erledigt" fehlinterpretiert).

## Lizenz

MIT, wie der Rest des Repos – siehe [../../LICENSE](../../LICENSE).
