# Benötigte Helper

Alle Helper lassen sich über **Einstellungen → Geräte & Dienste → Helfer →
Helfer erstellen** anlegen. Die Entity-IDs unten sind Vorschläge (`kind_`
als Platzhalter für den Namen deines Kindes/deiner Routine) – du kannst sie
frei wählen, musst sie dann aber überall konsistent in den Automationen/dem
Dashboard verwenden.

Beispielwerte in Klammern beziehen sich auf das Original-Set-up (10 Aufgaben
morgens, 7 mittags, macht 17/Tag). Passe die Max-Werte an deine eigene
Listengröße an.

## Counter

| Entity-ID | Zweck | Einstellungen |
|---|---|---|
| `counter.kind_wochenpunkte` | Punkte der laufenden Woche | Minimum 0, kein Maximum (wird per Automation auf 0 zurückgesetzt) |
| `counter.kind_punktekonto` | Lebenslanges "Sparkonto" für Belohnungen, wird NIE automatisch zurückgesetzt | Minimum 0, kein Maximum |

## Input Number (Live-Tracker "heute")

Je Routine (Morgen/Mittag/…) ein Tracker, der die heute schon fristgerecht
erledigten Aufgaben zählt. Max = Anzahl Aufgaben in der jeweiligen Liste.

| Entity-ID | Min | Max (Beispiel) |
|---|---|---|
| `input_number.kind_erledigt_morgen_heute` | 0 | 10 |
| `input_number.kind_erledigt_mittag_heute` | 0 | 7 |

Schrittweite 1, Anzeige-Modus "Kasten" (box).

## Input Boolean

| Entity-ID | Zweck |
|---|---|
| `input_boolean.kind_morgenroutine_sichtbar` | Steuert, ob die Morgenroutine-Karte/-Liste auf dem Dashboard sichtbar ist (wird nachts an-, nach der Frist ausgeschaltet) |

## Input Select (Belohnungen)

`input_select.kind_belohnung_auswahl` – die Optionen kodieren die Kosten am
Anfang des Strings, getrennt durch " – " (wird vom Script geparst):

```
100 – 15 Min Medienzeit
200 – 2x 15 Min Medienzeit
300 – 1 Std. Medienzeit
500 – Schwimmbad
1000 – Kino
```

Passe Belohnungen/Schwellwerte frei an deine eigene Familie an.

## Input Text (Wochenstatus, für den Freitagsbericht)

Je Wochentag ein Paar: der erreichte Status ("X/17") und die liegen
gebliebenen Aufgaben als Text.

```
input_text.kind_status_montag        input_text.kind_fehlten_montag
input_text.kind_status_dienstag      input_text.kind_fehlten_dienstag
input_text.kind_status_mittwoch      input_text.kind_fehlten_mittwoch
input_text.kind_status_donnerstag    input_text.kind_fehlten_donnerstag
input_text.kind_status_freitag       input_text.kind_fehlten_freitag
```

Max-Länge ruhig auf 255 setzen, damit auch längere Aufgabenlisten reinpassen.

## Input Text (nur relevant mit Fortschrittsbildern, siehe `images/`)

```
input_text.kind_fehlten_morgen_heute   (Zwischenspeicher, meist nicht mehr aktiv genutzt)
input_text.kind_routinebild            (Dateiname des aktuell anzuzeigenden Morgen-Bilds)
input_text.kind_mittagsbild            (analog für die Mittagsroutine, falls gewünscht)
```

## Template-Sensoren

Werden nicht über den Helfer-Dialog, sondern unter **Einstellungen → Geräte
& Dienste → Helfer → Helfer erstellen → Template** angelegt (Typ: Sensor).

**`sensor.kind_punkte_heute`** – heute bereits erreichte Punkte (Morgen +
Mittag + Bonus-Vorschau, sobald alles erledigt ist):

```jinja
{{ states('input_number.kind_erledigt_morgen_heute') | int(0)
   + states('input_number.kind_erledigt_mittag_heute') | int(0)
   + (3 if (states('input_number.kind_erledigt_morgen_heute') | int(0)
            + states('input_number.kind_erledigt_mittag_heute') | int(0)) == 17
      else 0) }}
```

(die `17` und den Bonus `3` an deine eigene Aufgabenzahl/Zielsumme anpassen)

**`sensor.kind_tagesmax`** – wie viele Punkte heute *maximal* schon erreichbar
sind (steigt, sobald die Morgenroutine-Phase vorbei ist, damit das
Tagesbarometer nicht die ganze Zeit auf ein fixes Maximum von 20 zeigt,
obwohl mittags noch gar nichts erreichbar war):

```jinja
{{ 10 if is_state('input_boolean.kind_morgenroutine_sichtbar', 'on') else 20 }}
```

(`10`/`20` an deine eigenen Aufgabenzahlen morgens/gesamt anpassen)

Beide mit `state_class: measurement`.
