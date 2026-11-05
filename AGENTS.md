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
  geht. Nach `main` kommt ein Stand erst nach der Abnahme durch den Menschen —
  dann über den **Release**-Knopf im Board.

## Vor der ersten Änderung lesen

1. `docs/ENTSCHEIDUNGEN.md` — warum etwas so ist. Groß: gezielt mit `grep`
   suchen, nicht am Stück lesen.
2. `DESIGN.md` — verbindlich für **jede** Arbeit an der Oberfläche. Die alte
   `docs/UI-REGELN.md` ist ersetzt und bleibt nur als Herkunftsnachweis stehen.
3. `docs/KONZEPT.md` — Produkt und Datenmodell, wenn das Ticket es berührt.

## Regeln

- **Entscheidungen zuerst.** Eine Änderung, die eine Entscheidung braucht, wird
  als `D-xx` in `docs/ENTSCHEIDUNGEN.md` festgehalten, dann gebaut.
- **`DESIGN.md` ist bindend**, nicht Empfehlung: Tokens, Typografie, Abstände,
  Radien und Komponenten stehen dort. Ein neues Feature passt sich dem
  Designsystem an, nicht umgekehrt.
- **Prüfen, bevor du abgibst:** `uv run pytest` und, bei Oberflächenarbeit,
  die betroffene Seite tatsächlich aufrufen und ansehen.
- **Nichts erfinden.** Fehlt eine Zahl in der Quelle, wird sie nicht geschätzt
  und nicht aufgefüllt.
- **Commits** nach dem Muster `Bereich: Was` (max. 72 Zeichen), darunter zwei
  bis fünf Zeilen Warum. Nie `git add .` blind, nie `--force`.

## Vorschau

`develop` läuft auf dem Homeserver als eigene Instanz mit eigener Datenbank-
Kopie. Sie ist zum Testen da, nicht als Produktivsystem.
