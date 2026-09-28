# Kinder-Routinen mit Live-Punktesystem für Home Assistant

> Aus "hat sie die Zähne geputzt?" wird ein Dashboard, das von selbst mitzählt:
> jede pünktlich erledigte Aufgabe gibt sofort einen Punkt, die Woche läuft auf
> ein rundes Ziel, und am Ende winkt eine selbst gewählte Belohnung – ganz ohne
> Zettel an der Kühlschranktür.

Ein Dashboard + Automations-Set für Home Assistant, mit dem eine tägliche
Kinder-Routine (z. B. "Morgenroutine" und "Mittagsroutine" als To-Do-Listen)
in ein Punkte-/Belohnungssystem verwandelt wird:

- Jede pünktlich (vor einer Frist-Uhrzeit) abgehakte Aufgabe gibt sofort
  1 Punkt (**live**, nicht erst am Abend ausgewertet).
- Ein Tagesbonus für einen komplett fristgerechten Tag.
- Ein Wochenzähler (setzt sich montags zurück) und ein Sparkonto (setzt sich
  nie zurück), aus dem Belohnungen bei festgelegten Schwellwerten eingelöst
  werden können.
- Ein Dashboard-Panel ("Punkte-Barometer") mit Balkenanzeige für Heute /
  Diese Woche / Gesamt, plus Fortschrittsbildern/-überschriften während der
  Routine.
- Ein Belohnungs-Button mit Bestätigungsdialog, der Punkte abzieht und eine
  Benachrichtigung verschickt.

Das Ganze ist aus einem konkreten Set-up für eine Morgen- und Mittagsroutine
mit insgesamt 17 Aufgaben/Tag entstanden (Ziel: 100 Punkte in einer perfekten
Woche). Alle Beispiele in diesem Repo verwenden generische Platzhalter
(`kind` statt eines echten Namens) und ein neutrales Benachrichtigungsziel –
du musst deine eigenen Entity-IDs, Aufgaben und dein eigenes Notify-Ziel
einsetzen.

## Screenshot

![Dashboard-Beispiel: Routinen-Liste, Fortschrittsbild und Punkte-Barometer](images/dashboard-beispiel.png)

Das Original-Dashboard einer Familie, die dieses System täglich nutzt – links
die abhakbare Routine, in der Mitte das Fortschrittsbild, rechts das
Punkte-Barometer (Heute / Woche / Gesamt) samt Belohnungs-Checkliste und
Einlösen-Button.

## Was das hier NICHT ist

Kein HACS-Add-on, keine Integration mit Config-Flow, kein Ein-Klick-Installer.
Home Assistant hat keinen Mechanismus, der Automationen + Helper + Dashboard
+ Bilder gebündelt bei jemand anderem installiert. Dieses Repo ist eine
dokumentierte Bauanleitung zum Nachbauen/Anpassen – die zwei Live-Punkte-
Automationen gibt es zusätzlich als [Blueprint](blueprints/automation/kinder-routine-live-punkte.yaml),
den Rest kopierst du als YAML und passt Entity-IDs an.

## Voraussetzungen

- Home Assistant (getestet mit aktuellen 2026.x-Versionen)
- HACS, für die Dashboard-Karte [`bar-card`](https://github.com/custom-cards/bar-card)
  (die Balkenanzeigen im Barometer)
- Zwei (oder mehr) `todo`-Listen für die jeweilige Routine

## Aufbau dieses Repos

```
helpers/helpers.md           Alle benötigten Helper (Counter, Input-Number, ...) mit Erklärung
blueprints/automation/       Wiederverwendbarer Blueprint für die Live-Punktevergabe
automations/                 Die restlichen Automationen als YAML zum Kopieren
scripts/                     Das Belohnungs-Einlöse-Script
dashboard/                   Die Dashboard-Sektion "Punkte-Barometer" als YAML
images/                      Hinweise zu den Fortschrittsbildern
```

## Setup – Schritt für Schritt

1. **To-Do-Listen anlegen**: z. B. `todo.kind_morgenroutine` und
   `todo.kind_mittagsroutine` mit deinen eigenen Aufgaben (Einstellungen →
   Geräte & Dienste → Helfer → To-do-Liste, oder als `todo` Integration).
   Merke dir die Anzahl der Aufgaben pro Liste – die brauchst du gleich als
   Maximalwert für die Tracker-Helper.

2. **Helper anlegen**: siehe [`helpers/helpers.md`](helpers/helpers.md) für die
   vollständige Liste (2× Counter, 2× Input-Number, 1× Input-Boolean,
   1× Input-Select, mehrere Input-Text). Passe Min/Max-Werte an deine
   Listengröße an.

3. **Live-Punkte-Automationen einrichten**: entweder den
   [Blueprint importieren](blueprints/automation/kinder-routine-live-punkte.yaml)
   und pro Routine (Morgen/Mittag) eine Instanz davon anlegen – dabei wählst
   du deine To-Do-Liste, deinen Tracker-Helper, die Frist-Uhrzeit und die
   Wochentage über ein Formular aus. Oder die YAML-Dateien in
   `automations/` direkt kopieren und die Platzhalter-Entity-IDs ersetzen.

4. **Restliche Automationen einrichten** aus `automations/`:
   - `tagesabschluss_bonus.yaml` – Tagesbonus + Status für den Wochenbericht
   - `wochenbericht.yaml` – freitagabends eine Zusammenfassung verschicken
   - `wochenreset.yaml` – montags früh Wochenzähler & Tagesstatus zurücksetzen
   - `nachtlicher_reset_morgen.yaml` / `nachtlicher_reset_mittag.yaml` –
     nachts die To-Do-Listen wieder auf "offen" setzen
   - `ausblenden_ab_frist.yaml` – Dashboard-Sichtbarkeits-Helper nach der
     Frist wieder ausblenden
   - `bild_aktualisieren.yaml` – **optional**, nur relevant, wenn du mit
     Fortschrittsbildern arbeitest (siehe `images/`)

5. **Belohnungs-Script** aus `scripts/belohnung_einloesen.yaml` einrichten
   und dein eigenes Notify-Ziel eintragen (siehe Hinweis unten).

6. **Dashboard-Sektion** aus `dashboard/routinen_dashboard_view.yaml` in
   dein Lovelace-Dashboard übernehmen (als eigene "sections"-Ansicht oder als
   Teil einer bestehenden). `bar-card` muss über HACS installiert sein.

## Wichtig: Benachrichtigungen anpassen

Das Original-Set-up verschickt Benachrichtigungen über einen privaten
Webhook (`rest_command.notify_router`), der individuell für die
ursprüngliche Familie eingerichtet ist – der funktioniert bei dir nicht.
Deshalb ist in allen YAML-Dateien hier stattdessen `notify.notify`
(Standard-Benachrichtigung in Home Assistant) eingetragen. Ersetze das durch
dein eigenes Ziel, z. B. `notify.mobile_app_<dein_handy>` oder eine eigene
Telegram-/Signal-/Webhook-Integration.

## Die Punkte-Mathematik anpassen

Die Formel: `Wochenmaximum = (Aufgaben pro Tag × 1 Punkt + Tagesbonus) × Anzahl Schultage`.
Im Original: (17 Aufgaben × 1 + 3 Bonus) × 5 Tage = 100 Punkte/Woche.
Willst du eine andere Zielsumme oder eine andere Aufgabenzahl, passe den
Tagesbonus in `tagesabschluss_bonus.yaml` und die Max-Werte der Tracker-Helper
entsprechend an, damit es wieder aufgeht.

## Lizenz

MIT – siehe [LICENSE](LICENSE). Mach damit, was du willst; eine Erwähnung
freut mich, ist aber keine Pflicht.
