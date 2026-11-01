# Phase-0-Befund — 30.10.2026

Alle vier Kanäle sind geprüft. Ergebnis: **grün**, mit einer offenen Frage zum
bestehenden 21-h-Plan.

## Kanäle

| Kanal | Ergebnis |
|---|---|
| intervals.icu API | 283 Aktivitäten (08.01.–29.10.2026), 366 Wellness-Tage, 47 Events, 4 Sport-Settings |
| Zepp/Helio-Wellness | HRV 365/366, Ruhepuls 366/366, Schlaf 365/366 |
| Garmin Personal API | 85 Aktivitäten (90 Tage), FIT-Download 9.995 B, Schlaf 91 Nächte, HRV 3 |
| Workout-Push | 3 Schritte geparst, Last 44, Intensität 78, `workout_doc` gefüllt |
| Garmin-Uhr | offen — Sync-Test liegt am 05.11.2026 im Kalender |

## Datenbild

**Aktivitäten nach Quelle:** OAUTH_CLIENT 137, GARMIN_CONNECT 123, WAHOO 19, ZEPP 4.
**Nach Sport:** Laufen 93, VirtualRide 41, Kraft 40, Schwimmen 39, Workout 26,
Gehen 14, Rad 12, VirtualRun 7, HIIT 6, Wechsel 2, Freiwasser 2, Wandern 1.

Die Garmin-Sperre würde also nur **123 von 283** Aktivitäten treffen — der Rest
kommt aus Wahoo/Zwift/Zepp und bleibt über intervals.icu verfügbar. Für die
Garmin-Daten haben wir den Direktzugriff.

**Gewicht:** 76,9 kg (22.09.2026), 48 Wellness-Tage mit Gewicht.
**Trainingslast:** in 283/283 Aktivitäten vorhanden (`icu_training_load`).

## Belastung heute

| Kennzahl | Wert |
|---|---|
| CTL | 56,6 |
| ATL | 61,8 |
| TSB | −5,2 |
| Schnitt letzte 8 volle Wochen | 7,6 h/Woche |
| Höchste Woche 2026 | 11,8 h (KW 43) |
| Höchste Woche im Plan | 9,5 h / 539 Load (KW 46) |

## Planstand in intervals.icu

- 41 geplante Workouts, letzter Eintrag **22.11.2026**.
- Struktur: Di/Do Doppel-Einheiten (Lauf + Rad), Sa Long Run, So Long Ride + Koppellauf.
- Peak KW 46 mit 9,5 h, dann Taper auf 8,4 h zur Halbmarathon-Woche.
- **Keine Events für 2027** — der Weg zum Ironman ist dort noch nicht abgebildet.

## Konsequenzen

1. **Readiness ist machbar.** Zepp liefert Schlaf, HRV und Ruhepuls an 365 von
   366 Tagen. Das ist die wichtigste Voraussetzung und funktioniert.
2. **Garmin ist nicht kritisch für die Erholung.** Die Uhr wird nur im Training
   getragen (3 HRV-Nächte in 90 Tagen). Schlaf/HRV kommen von der Helio.
3. **Aktivitäten sind breit verteilt.** Nur 43 % kommen von Garmin; die
   Architektur mit eigener DB ist bestätigt.
4. **Der 21-h-Plan ist nicht in intervals.icu.** Dort endet der Plan am 22.11.
   mit 9,5 h Peak. Wo die 21 h herkommen, muss geklärt werden.

## Offen

1. **Wo liegt der 21-h-Plan?** App, PDF, Coach? Soll er importiert und bewertet
   oder durch einen neuen Plan ersetzt werden?
2. **Sync-Test am 05.11.2026:** Erscheint „TC Spike — Testeinheit" im
   Garmin-Connect-Kalender und auf der Uhr?
3. **Halbmarathon 21.11.2026:** Zielzeit? Der Plan hinterlegt 1:59 — bei PB
   2:20 wäre das ein sehr großer Sprung.
4. **Kraft-Katalog:** Übungen an Ringen + Zusatzgewicht für die Bibliothek.

## Empfehlung

Phase 1 starten: SQLite, Collector, Dedupe, Readiness und Trends auf den
vorhandenen 10 Monaten. Der Planer kommt erst, wenn der 21-h-Plan geklärt ist —
sonst bauen wir gegen einen Plan, den wir nicht kennen.
