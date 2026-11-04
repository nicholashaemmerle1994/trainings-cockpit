# Trainings-Cockpit — Arbeitsregeln

Diese Datei gilt für jede Sitzung, die in diesem Repository arbeitet — ob Mensch
oder Agent.

## Was das hier ist

Das Cockpit ist ein Trainings-Dashboard: eine Python-App (FastAPI, `src/`),
eine React-Oberfläche (`web/`) und eine SQLite-Datenbank unter `data/`. Die
Zahlen kommen aus intervals.icu und Garmin, die Bewertung steht im Vault
(`Sport-Gehirn/`, außerhalb dieses Repos).

## Branch-Modell

- `main` ist der stabile Stand, der auf dem Homeserver läuft.
- `develop` ist die Integrationsstrecke und läuft als **Vorschau-Instanz**
  (siehe `docs/DEPLOY-DEVELOP.md`).
- Jedes Ticket arbeitet auf `feature/<ticket-id>-<slug>`, abgezweigt von `main`.
- Gemerged wird nach `develop`, wenn das Ticket nach `ready-for-deployment`
  geht. Nach `main` kommt ein Stand erst nach der Abnahme durch den Menschen.

## Vor der ersten Änderung lesen

1. `docs/ENTSCHEIDUNGEN.md` — warum etwas so ist. Groß: gezielt mit `grep`
   suchen, nicht am Stück lesen.
2. `docs/UI-REGELN.md` — verbindlich für **jede** Arbeit an der Oberfläche.
3. `docs/KONZEPT.md` — Produkt und Datenmodell, wenn das Ticket es berührt.

## Regeln

- **Entscheidungen zuerst.** Eine Änderung, die eine Entscheidung braucht, wird
  als `D-xx` in `docs/ENTSCHEIDUNGEN.md` festgehalten, dann gebaut.
- **UI-Regeln sind bindend**, nicht Empfehlung: ein helles Element je
  Bildschirm, ruhiger Rahmen, neutrale Grautöne, ein Akzent — die Maße und
  Tokens stehen in `docs/UI-REGELN.md`.
- **Prüfen, bevor du abgibst:** `uv run pytest` und, bei Oberflächenarbeit,
  die betroffene Seite tatsächlich aufrufen und ansehen.
- **Nichts erfinden.** Fehlt eine Zahl in der Quelle, wird sie nicht geschätzt
  und nicht aufgefüllt.
- **Commits** nach dem Muster `Bereich: Was` (max. 72 Zeichen), darunter zwei
  bis fünf Zeilen Warum. Nie `git add .` blind, nie `--force`.

## Vorschau

`develop` läuft auf dem Homeserver als eigene Instanz mit eigener Datenbank-
Kopie. Sie ist zum Testen da, nicht als Produktivsystem.
