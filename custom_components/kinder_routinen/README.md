# Kinder-Routinen Punktesystem – Custom Integration (v0.2)

Ein-Klick-Einrichtung mit eigenem Assistenten: Name des Kindes, Anzahl der
Routinen und die einzelnen Aufgaben je Routine werden direkt abgefragt –
keine vorher angelegte To-Do-Liste nötig. Am Ende macht die Integration
einen Vorschlag für ein "rundes" Wochenpunkteziel (mit optionalen
Bonuspunkten) und richtet danach alles automatisch ein: To-Do-Listen,
Sensoren, ein gemeinsames Punktekonto – und ein eigenes Dashboard mit
fertigen Karten in der Seitenleiste.

## Installation

1. In HACS → "Custom repositories" diese Repo-URL eintragen, Kategorie
   "Integration" (oder den Badge oben im Haupt-README nutzen).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "Kinder-Routinen
   Punktesystem"** – der Assistent führt durch die Einrichtung.

### Der Assistent, Schritt für Schritt

1. **Name des Kindes** und **Anzahl der Routinen** (z. B. "Morgen" +
   "Mittag" = 2).
2. **Pro Routine** ein eigener Schritt: Name der Routine, Frist-Uhrzeit,
   Wochentage, und die Aufgaben – eine pro Zeile, im Textfeld direkt
   eingetippt. Daraus baut die Integration automatisch eine eigene,
   integrationseigene To-Do-Liste (keine externe To-Do-Integration mehr
   nötig).
3. **Punktesystem**: die Integration zeigt, wie viele Punkte die
   eingetragenen Aufgaben pro Woche ohne Bonus ergeben, und schlägt dazu ein
   rundes Wochenziel vor (z. B. 50 oder 100 statt 47). Bonuspunkte pro
   Routine und komplett fristgerechtem Tag sind **opt-in** – standardmäßig
   aus, auf Wunsch aktivierbar, die Integration schlägt dazu einen
   passenden Wert vor. Optional: ein Notify-Ziel für Benachrichtigungen.
4. Fertig – kein manuelles Helper-Anlegen, kein manuelles Dashboard-Bauen.

## Was v0.2 tut

- **Setup-Assistent statt Formular-Wüste**: alles (Kind, Routinen, Aufgaben,
  Punktesystem, Bonus) wird in einem durchgehenden Dialog abgefragt.
- **Gemeinsames Punktekonto pro Kind**: alle Routinen eines Kindes teilen
  sich einen Wochenzähler und ein Sparkonto (statt – wie in v0.1 – pro
  Routine getrennt).
- **Eigene To-Do-Listen pro Routine**, komplett von der Integration selbst
  verwaltet (keine externe `todo`-Integration mehr nötig). Live-Punktevergabe:
  Aufgabe vor der Frist abgehakt → sofort Punkt(e) gutgeschrieben, wieder
  abgezogen, falls das Häkchen entfernt wird.
- **Automatisch angelegtes Dashboard**: ein eigenes Panel in der
  Seitenleiste mit To-Do-Karten je Routine, Punkte-Anzeige heute je Routine
  sowie Wochenpunkte/Punktekonto – ohne manuellen Dashboard-Bau. Siehe
  Hinweis zum Risiko dieser Automatik weiter unten.
- Nächtlicher Reset der To-Do-Listen (23:59 Uhr) und wöchentlicher Reset des
  Wochenzählers (montags 00:01 Uhr).
- Tagesbonus (falls aktiviert), wenn an einem konfigurierten Wochentag alle
  Aufgaben einer Routine fristgerecht erledigt wurden.
- Sensoren: *Wochenpunkte* und *Punktekonto* (Kind-weit), sowie *Punkte
  heute* und *Tagesmax* je Routine – alle mit `unique_id`, über
  HA-Neustarts hinweg persistiert.
- Options-Flow zum nachträglichen Anpassen von Bonuspunkten und Notify-Ziel.

## Wie zuverlässig ist die automatische Dashboard-Einrichtung?

Home Assistant bietet für Custom Integrations **keine offizielle,
dokumentierte API**, um ein Dashboard automatisch in der Seitenleiste
anzulegen. v0.2 nutzt dafür bewusst denselben internen Mechanismus, den die
`lovelace`-Komponente selbst intern verwendet (Storage-Modus, Panel-
Registrierung). Das funktioniert nachweislich – wurde auf der isolierten
Testinstanz mehrfach end-to-end verifiziert, inklusive sauberem erneuten
Speichern beim Reload (keine Duplikate) und sauberem Entfernen beim
Löschen der Integration (siehe Bugfix #2 unten). Trotzdem: **das ist eine
interne API, die sich mit künftigen Home-Assistant-Versionen ändern
könnte.** Schlägt die automatische Registrierung fehl, greift automatisch
ein Fallback: die Integration erzeugt stattdessen eine fertige
Dashboard-YAML-Datei im Konfigurationsverzeichnis und zeigt eine
Benachrichtigung mit einer kurzen Anleitung zum manuellen Hinzufügen
(2 Klicks: Dashboard hinzufügen → aus YAML). Der Rest der Integration
(Punktevergabe, To-Do-Listen, Sensoren) läuft davon komplett unabhängig
weiter, falls das passiert.

## Was v0.2 (noch) NICHT tut – Roadmap

- Belohnungs-Auswahl (`select`) + Einlösen-Button (`button`) als native
  Entities, statt manuellem Script.
- Freitags-Wochenbericht mit Status/fehlenden Aufgaben pro Wochentag.
- Nachträgliches Ändern von Routinen selbst (Aufgaben, Uhrzeiten, Anzahl)
  über den Options-Flow – aktuell nur durch Entfernen und neues Einrichten
  möglich; der Options-Flow deckt bisher nur Bonus und Notify-Ziel ab.
- Englische Übersetzung (aktuell nur Deutsch).

## Getestet gegen eine echte Instanz

Wie schon v0.1 wurde auch v0.2 nicht nur geschrieben, sondern vollständig
gegen eine frische, isolierte Home-Assistant-Testinstanz (Docker, getrennt
vom Produktivsystem) deployt und durchgetestet – Setup-Assistent per
simuliertem Config-Flow-Durchlauf, Live-Punktevergabe über die native
To-Do-Liste, Neustart-Verhalten, automatische Dashboard-Registrierung
(inklusive Reload und Entfernen) und Options-Flow. Dabei wurden zwei echte
Bugs gefunden und gefixt, bevor der Code hier landete:

1. **`todo.update_item` führte zu einem 500er-Fehler** (`AttributeError:
   'str' object has no attribute 'value'`): Home Assistant übergibt den
   Status eines To-Do-Items je nach Aufrufer entweder als
   `TodoItemStatus`-Enum oder bereits als rohen String. Die Integration hat
   das nicht robust genug behandelt. Gefixt durch eine Typprüfung vor dem
   Zugriff auf `.value`.
2. **Das automatisch angelegte Dashboard blieb beim Löschen der Integration
   als Karteileiche in der Seitenleiste zurück.** Ursache: Home Assistant
   räumt beim endgültigen Entfernen eines Eintrags zuerst die
   In-Memory-Daten der Integration ab (`async_unload_entry`), bevor die
   eigentliche Aufräum-Funktion (`async_remove_entry`) überhaupt läuft – zu
   dem Zeitpunkt waren die Dashboard-Infos also schon weg. Gefixt, indem
   die Dashboard-Infos stattdessen direkt aus dem eigenen, unabhängig
   persistierten Speicher der Integration gelesen werden. Danach wurde das
   erneut getestet: Löschen des Eintrags entfernt jetzt zuverlässig sowohl
   den Sidebar-Eintrag als auch alle zugehörigen Speicherdateien, ganz ohne
   Fehler im Log.

Zusätzlich wurde gezielt verifiziert, dass die in v0.1 gefundene
"Neustart schreibt fälschlich Punkte gut"-Bugklasse durch die neue
Architektur (integrationseigene To-Do-Liste statt externer To-Do-Integration
+ `state_changed`-Events) strukturell ausgeschlossen ist: ein echter
Container-Neustart während einer laufenden Routine hat die Punktestände
nachweislich unverändert gelassen.

## Lizenz

MIT, wie der Rest des Repos – siehe [../../LICENSE](../../LICENSE).
