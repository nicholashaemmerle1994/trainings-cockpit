# Trainingsplaner — Implementierungspaket v1.6

Dieses Paket enthält den detaillierten Implementierungsplan und **acht neu gerenderte UI-Referenzbilder**, die **nicht** aus Nutzerscreenshots, Bestands-App-Screenshots oder fremden Apps ausgeschnitten sind.

## Inhalt

- `TRAININGSPLANER_IMPLEMENTIERUNGSPLAN.md` — vollständige Spezifikation inklusive Bildverweisen.
- `references/06-approved-training-planner-week.png` — Wochenansicht Montag–Sonntag.
- `references/07-approved-planned-workout-detail.png` — geplante Einheit mit Verlauf.
- `references/08-approved-inline-block-editor.png` — Editor direkt im ausgewählten Wiederholungsabschnitt.
- `references/09-approved-add-workout.png` — neue Einheit mit **Sportart-Dropdown**.
- `references/10-approved-sport-dropdown.png` — Dropdown geöffnet: Laufen / Radfahren / Schwimmen.
- `references/11-approved-simple-run-editor.png` — einfacher Z2-Lauf aus nur einem Abschnitt.
- `references/12-approved-add-workout-desktop.png` — Desktop-Version des Anlegeformulars.
- `references/13-approved-mixed-target-graph.png` — HF-/Pace-Vorgaben auf getrennten Spuren.
- `prototype/Trainingsplaner-Referenz.html` — eigenständige HTML-Renderquelle der Bildreferenzen; **nur Designvorschau**, keine produktive Anwendung.

## Verbindliche Designentscheidungen

1. Sportart-Auswahl beim Anlegen **ausschließlich als Dropdown**; **keine Sport-Iconkacheln**. Sportart-Icons in normalen Trainingskarten sind davon nicht betroffen.
2. Darunter optionaler Name sowie drei vertikale Radio-Auswahlen für den Aufbau.
3. Ein Abschnitt wird direkt **in seinem Aufbau-Block** bearbeitet; kein separates Formular oberhalb.
4. Ein einfacher Dauerlauf benötigt nur einen Abschnitt, der Planungsgraph reflektiert dessen Ziel.
5. Der Planer öffnet nur über den **eigenen Tab**. Dashboard-`Umfang` ist eine reine Kennzahl ohne Klickziel.

`DESIGN.md` ist bereits im Projekt vorhanden und bleibt alleinige Designgrundlage. Alle Werte in den Screens sind Mock-Daten. Das HTML dokumentiert die visualisierte Bedienidee; das bestehende Produkt muss seine echten Daten und API-Anbindung verwenden.

## Verwendung

Das Paket **als Ganzes** in das Repository entpacken und `TRAININGSPLANER_IMPLEMENTIERUNGSPLAN.md` an den Coding-Agenten übergeben. Dieser beginnt mit P00 und öffnet die Bildreferenzen zur visuellen Abnahme. Keine zusätzlichen App-Screenshots erforderlich.

## Stand der Umsetzung

P00–P27 sind umgesetzt. Die finale Fähigkeitsmatrix steht in
`FAEHIGKEITSMATRIX.md`, die Übergabe mit Komponenten, Routen,
Dashboard-Volumen und Datenverfügbarkeit in `UEBERGABE.md`, der vollständige
Arbeitsnachweis in `../training-planner-progress.md`. Ein Live-Rundlauf gegen
intervals.icu, eine Geräteübertragung und ein Release wurden nicht
durchgeführt.

## TB-23 — Vorlagen und Wochenkopie

- `TB-23-P1.md` — lokales Vorlagenmodell und Klon-Dienst.
- `TB-23-P3-P4.md` — „Als Vorlage speichern“ und „Aus Vorlage erstellen“.
- `TB-23-COPY.md` — API, Schema und Sicherheitsgrenzen der Wochen-/Blockkopie.
- `TB-23-BEDIENUNG.md` — kurze Bedienungsanleitung für alle drei Kernfunktionen.
- `TB-23-HANDOVER.md` — fortgeschriebener Arbeitsstand, Commits und offene
  Punkte.
