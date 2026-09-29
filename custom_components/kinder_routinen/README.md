# Kinder-Routinen Punktesystem – Custom Integration (v1.0)

Ein-Klick-Einrichtung mit eigenem Assistenten: Name des Kindes, Anzahl der
Routinen, die einzelnen Aufgaben je Routine – und ab v1.0 direkt im selben
Assistenten optional ein Bild pro Aufgabe, dazu ein Grundbild und ein
"Alles erledigt"-Bild. Am Ende macht die Integration einen Vorschlag für ein
"rundes" Wochenpunkteziel (mit optionalen Bonuspunkten) und richtet danach
alles automatisch ein: To-Do-Listen, Sensoren, ein gemeinsames Punktekonto,
ein eigenes Dashboard – und, falls Bilder hochgeladen wurden, ein
Fortschrittsbild, das sich automatisch passend zur zuletzt erledigten
Aufgabe ändert (genau das Verhalten des ursprünglichen YAML-Set-ups, jetzt
ganz ohne eigene YAML-Bildautomation). Alles, was einmal eingerichtet ist,
lässt sich danach jederzeit über "Konfigurieren" am Eintrag nachträglich
anpassen, ohne die Integration neu einzurichten – siehe
[Nachträglich verwalten](#nachträglich-verwalten-der-options-flow).

## Installation

1. In HACS → "Custom repositories" diese Repo-URL eintragen, Kategorie
   "Integration" (oder den Badge oben im Haupt-README nutzen).
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "Kinder-Routinen
   Punktesystem"** – der Assistent führt durch die Einrichtung.

## Der Einrichtungsassistent, Schritt für Schritt

> Screenshots aus einem Testlauf folgen hier in Kürze. Bis dahin die
> Kurzbeschreibung jedes Schritts:

### Schritt 1 – Kind und Anzahl der Routinen

- **Name des Kindes**: nur zur Beschriftung (Dashboard-Titel, Sensor-Namen,
  Benachrichtigungstexte) – kein technischer Bezug zu einer bestehenden
  Entität nötig.
- **Anzahl Routinen**: wie viele eigenständige Tagesabschnitte es geben
  soll, z. B. `2` für "Morgen" + "Mittag". Jede Routine bekommt gleich
  einen eigenen Schritt (Aufgaben) und optional einen eigenen Bilder-Schritt.

### Schritt 2 – Aufgaben je Routine

Pro Routine (z. B. "Routine 1 von 2"):

- **Name der Routine** (z. B. "Morgen"), vorausgefüllt mit einem Vorschlag.
- **Frist-Uhrzeit**: bis wann eine an diesem Tag abgehakte Aufgabe noch als
  "pünktlich" zählt und einen Punkt gibt.
- **Wochentage**: an welchen Tagen diese Routine überhaupt läuft (z. B.
  Schultage Mo–Fr).
- **Aufgaben**: ein Textfeld, eine Aufgabe pro Zeile. Daraus baut die
  Integration automatisch eine eigene, integrationseigene To-Do-Liste –
  keine externe To-Do-Integration nötig, keine manuelle Aufgabenzählung.

### Schritt 3 – Bilder je Aufgabe (neu in v1.0, optional)

Für jede eben eingetragene Aufgabe erscheint ein eigenes Upload-Feld
("Bild_aufgabe_0", "Bild_aufgabe_1", …, in der Reihenfolge der Aufgaben von
oben). Das hochgeladene Bild wird angezeigt, sobald **diese Aufgabe als
letzte** in der Routine erledigt wurde – genau wie im ursprünglichen
YAML-Set-up, nur ohne eigene Bild-Automation. Zusätzlich gibt es:

- **Grundbild**: wird angezeigt, bevor überhaupt eine Aufgabe der Routine
  erledigt ist.
- **Alles erledigt**: wird angezeigt, sobald wirklich alle Aufgaben der
  Routine abgehakt sind.

Alle Uploads sind optional – ohne Bilder funktioniert die Integration
genauso, nur eben ohne Fortschrittsbild. Jedes Bild lässt sich später über
"Konfigurieren" einzeln nachreichen oder austauschen, ganz ohne die Routine
neu anzulegen.

### Schritt 4 – Punktesystem

- Die Integration zeigt, wie viele Punkte die eingetragenen Aufgaben pro
  Woche ohne Bonus ergeben, und schlägt dazu ein rundes Wochenziel vor
  (z. B. 50 oder 100 statt 47).
- **Bonuspunkte aktivieren**: opt-in, standardmäßig aus. Aktiviert, fragt
  die Integration die Bonuspunkte pro Routine und komplett fristgerechtem
  Tag ab (mit Vorschlag).
- **Notify-Ziel**: optional, z. B. `notify.mobile_app_handy`, für
  Benachrichtigungen (Tagesbonus etc.).

Fertig – kein manuelles Helper-Anlegen, kein manuelles Dashboard-Bauen,
kein manuelles Verdrahten von Bildautomationen.

## Nachträglich verwalten (der Options-Flow)

Über **"Konfigurieren"** am Eintrag (Einstellungen → Geräte & Dienste →
Kinder-Routinen Punktesystem → Zahnrad-Symbol) öffnet sich ein Menü mit
sechs Funktionen, ganz ohne die Integration neu einzurichten:

1. **Bonuspunkte & Benachrichtigung** – wie bisher in v0.2.
2. **Neue Routine hinzufügen** – inklusive der optionalen Bilder-Schritte
   aus dem Einrichtungsassistenten.
3. **Aufgaben einer Routine bearbeiten** – ein vorausgefülltes Textfeld
   (eine Aufgabe pro Zeile). Unveränderte Zeilen behalten ihren Status und
   ihr Bild, gelöschte Zeilen verschwinden, neue Zeilen werden als neue
   Aufgabe angelegt.
4. **Bild einer Aufgabe ändern** – Routine und Aufgabe auswählen, neues
   Bild hochladen; alle anderen Aufgaben/Bilder bleiben unangetastet.
5. **Routine bearbeiten** – Name, Frist-Uhrzeit, Wochentage sowie optional
   Grundbild/"Alles erledigt"-Bild austauschen (leer lassen, um das
   bestehende Bild zu behalten).
6. **Routine entfernen** – inklusive automatischer Bereinigung der
   zugehörigen To-Do-Liste, Sensoren und aller für diese Routine
   hochgeladenen Bilddateien.

## Wie die Fortschrittsbilder technisch angezeigt werden

Genau wie im ursprünglichen YAML-Set-up wird das zuletzt passende Bild über
eine normale Home-Assistant-`entity_picture` ausgeliefert: Ein Sensor pro
Routine trägt als `entity_picture`-Attribut den Pfad des aktuell
passenden Bildes (Grundbild → Aufgabenbild der zuletzt erledigten Aufgabe →
"Alles erledigt"-Bild), und im automatisch angelegten Dashboard zeigt eine
ganz normale, native `picture-entity`-Karte dieses Bild an. Kein eigenes
Frontend-Element, keine eigene Bild-Automation – nur HA-Bordmittel.

## Was v1.0 tut

Alles aus v0.2 (Setup-Assistent, gemeinsames Punktekonto pro Kind, eigene
To-Do-Listen pro Routine, automatisch angelegtes Dashboard, Live-
Punktevergabe, nächtlicher/wöchentlicher Reset, Tagesbonus), plus:

- **Bild-Upload pro Aufgabe** direkt im Einrichtungsassistenten (siehe
  oben), inklusive Grundbild und "Alles erledigt"-Bild.
- **Fortschrittsbild-Anzeige** über eine native `sensor.entity_picture` +
  `picture-entity`-Karte im automatisch angelegten Dashboard.
- **Vollständige Verwaltungsoberfläche** über einen erweiterten
  Options-Flow: Routinen hinzufügen/entfernen, Aufgaben bearbeiten, Bilder
  austauschen, Name/Frist/Wochentage ändern – alles nachträglich, ohne
  Neueinrichtung (siehe oben).
- Sensoren: *Wochenpunkte* und *Punktekonto* (Kind-weit), sowie *Punkte
  heute*, *Tagesmax* und *Aktuelles Bild* je Routine – alle mit
  `unique_id`, über HA-Neustarts hinweg persistiert.

## Was v1.0 (noch) NICHT tut – Roadmap

- Belohnungs-Auswahl (`select`) + Einlösen-Button (`button`) als native
  Entities, statt manuellem Script.
- Freitags-Wochenbericht mit Status/fehlenden Aufgaben pro Wochentag.
- Englische Übersetzung (aktuell nur Deutsch).

## Wie zuverlässig ist die automatische Dashboard-Einrichtung?

Home Assistant bietet für Custom Integrations **keine offizielle,
dokumentierte API**, um ein Dashboard automatisch in der Seitenleiste
anzulegen. Die Integration nutzt dafür bewusst denselben internen
Mechanismus, den die `lovelace`-Komponente selbst intern verwendet
(Storage-Modus, Panel-Registrierung). Das funktioniert nachweislich – wurde
auf der isolierten Testinstanz mehrfach end-to-end verifiziert, inklusive
sauberem erneuten Speichern beim Reload (keine Duplikate) und sauberem
Entfernen beim Löschen der Integration. Trotzdem: **das ist eine interne
API, die sich mit künftigen Home-Assistant-Versionen ändern könnte.**
Schlägt die automatische Registrierung fehl, greift automatisch ein
Fallback: die Integration erzeugt stattdessen eine fertige
Dashboard-YAML-Datei im Konfigurationsverzeichnis und zeigt eine
Benachrichtigung mit einer kurzen Anleitung zum manuellen Hinzufügen
(2 Klicks: Dashboard hinzufügen → aus YAML). Der Rest der Integration
(Punktevergabe, To-Do-Listen, Sensoren, Bilder) läuft davon komplett
unabhängig weiter, falls das passiert.

## Getestet gegen eine echte Instanz

Wie schon v0.1 und v0.2 wurde auch v1.0 nicht nur geschrieben, sondern
vollständig gegen eine frische, isolierte Home-Assistant-Testinstanz
(Docker, getrennt vom Produktivsystem) deployt und durchgetestet – der
komplette Einrichtungsassistent inklusive Bild-Upload (per simuliertem
Config-Flow-Durchlauf **und** einmal vollständig über die echte
Weboberfläche), die Fortschrittsbild-Anzeige-Logik (Grundbild →
Aufgabenbild → "Alles erledigt"-Bild), die automatische
Dashboard-Erstellung, sowie alle sechs Funktionen des erweiterten
Options-Flow einzeln – darunter, als architektonisch anspruchsvollster
Fall, das Entfernen einer Routine: Store, verwaiste Sensoren/To-Do-Liste
und alle zugehörigen Bilddateien auf der Platte wurden danach korrekt und
vollständig bereinigt.

Dabei wurde ein echter Bug gefunden und gefixt, bevor der Code hier landete:

1. **Hochgeladene Bilder waren bis zum nächsten HA-Neustart mit 404 nicht
   erreichbar.** Ursache: Home Assistants eingebauter `/local`-Pfad
   (`config/www`) wird von der `frontend`-Komponente nur beim HA-Start
   registriert, und auch nur dann, wenn der Zielordner zu diesem Zeitpunkt
   schon existiert. Der Bilderordner dieser Integration entsteht aber
   typischerweise erst beim ersten Bild-Upload, oft lange nach dem Start.
   Gefixt, indem die Integration beim ersten Upload selbst und dynamisch
   einen eigenen, unabhängigen statischen Pfad (`/kinder_routinen_media`)
   registriert – unabhängig vom Ladezeitpunkt von `/local`. Live
   verifiziert: Bilder sind seitdem sofort nach dem Upload erreichbar, ganz
   ohne Neustart.

Zusätzlich wurde erneut verifiziert, dass die in v0.1 gefundene "Neustart
schreibt fälschlich Punkte gut"-Bugklasse strukturell ausgeschlossen bleibt.

## Lizenz

MIT, wie der Rest des Repos – siehe [../../LICENSE](../../LICENSE).
