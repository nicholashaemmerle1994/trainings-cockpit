# Bidirektionaler Sync und betroffene Ansichten — P23

**Stand:** 06.11.2026 · **Paket:** P23 · **Grundlage:** Abschnitt 9.9 und
Arbeitspaket P23.

## 1. Eine Identität, eine Zeile

Ein bestätigter Planer-Write wird über die tatsächliche Remote-Event-ID in die
vorhandene `event`-Tabelle geschrieben (`planner/syncmerge.py`). Der nächste
Sync liest genau diese Event-ID und aktualisiert dieselbe Zeile. Eine lokal
gespeicherte Änderung erscheint dadurch nach dem Sync genau einmal und mit
derselben Identität; die externe Identität bleibt der Zuordnungsschlüssel für
eine Neuanlage, nicht der Anzeigeschlüssel.

Aktivitäten bleiben über ihre vorhandene kanonische Zeile (`activity.id` bzw.
`source`/`source_id`) verbunden. Ein neuer oder korrigierter Datensatz
aktualisiert dieselbe Zeile und damit dieselbe Woche, dieselbe rollierende
Dashboard-Kennzahl und dasselbe Aktivitätsdetail.

## 2. Keine Feedbackschleife

- Der Sync schreibt nur den lokalen Bestand; er ruft keinen Event-Schreibpfad
  auf.
- Die Darstellung einer Plan-/Aktivitätsbeziehung erzeugt keinen Event-Write.
- Ein bestätigter Write wird nicht allein wegen einer anderen Normalisierung
  erneut geschrieben. `prepare_write`/`NoWriteNeeded` beendet unveränderte
  Entwürfe ohne Request.
- Ein offener Editor wird von einem Hintergrund-Read nicht überschrieben; die
  Revisionsprüfung und `draftActive` schützen den Entwurf.

## 3. Betroffene Ansichten

Nach einem bestätigten Write oder Sync erhöht die App eine Revision. Damit
werden geladen:

- die gewählte Planerwoche (Wochenliste und getrennte Summen),
- die Planungsdetails, sofern sie nicht gerade bearbeitet werden,
- die bestehende Aufzeichnungsansicht (gleiche `row_id`),
- die rollierende Dashboard-Karte und die Tages-/Nächste-Einheit-Vorschau.

Bei einer Terminänderung werden alte und neue Woche entwertet; nach
erfolgreichem Speichern öffnet der Planer die Woche des gespeicherten Termins.
Ein Wochenwechsel ändert den rollierenden Dashboard-Zeitraum nicht.

## 4. Veraltete Antworten und getrennte Quellen

Die Wochenabfrage verwirft Antworten, die nicht zur zuletzt gewählten Woche
gehören (Query-Generation plus Wochen-Schlüssel). Die Entwurfsprüfung verwirft
veraltete Antworten über eine laufende Sequenz; der Speichervorgang hat eine
eigene Sequenz und akzeptiert keine verspätete ältere Antwort. Planungen und
Aufzeichnungen behalten getrennte Quellenzustände; ein Fehler der einen Quelle
entfernt die andere nicht.

## 5. Account und Logout

Vorgänge sind in der Datenbank an `account_id`/`athlete_id` gebunden; die API
listet und gleicht nur Vorgänge des aktuellen Accounts ab. Die Planer-Seite
wird bei einem Wechsel der Account-Identität neu aufgebaut; der lokale
Wochen-Cache wird bei einer Antwort eines anderen Accounts verworfen.
Formularentwürfe liegen seit P24 in einer browserlokalen Ablage, deren
Schlüssel und Datensatz Account und Athlet enthalten. Beim Öffnen werden
fremde Einträge ignoriert; wiederhergestellt wird nur nach ausdrücklicher
Entscheidung. Ein Entwurf ist kein Remote-Vorgang und wird nie automatisch
geschrieben.

## 6. Beziehungen

Ausdrückliche Plan-/Aktivitätsbeziehungen kommen aus der Tabelle `plan_link`
(manuell zugeordnet oder ausdrücklich getrennt). Automatische Paare werden
nicht gespeichert: Sie entstehen beim Lesen, wenn am selben lokalen Tag
dieselbe Sportart (bekannte Varianten zusammengefasst) genau einmal als
Planung und genau einmal als Aufzeichnung vorliegt. Der Wochenleser löst beides
in den vorhandenen Beziehungsvertrag auf; Änderungen aktualisieren die
gemeinsame Listenprojektion und die getrennten Summen. Sie erzeugen keinen
Event-Write und kopieren keine Messwerte. Eine Durchführung außerhalb der
Planwoche bleibt als Abschlussreferenz am abweichenden Plantermin erreichbar,
ohne die Aktivitätswoche umzuschreiben.

## 7. Produkt-Endpunkte

- `POST /api/planner/plan/{event_id}/save` — bestätigtes Update.
- `POST /api/planner/draft/save` — bestätigte Neuanlage.
- `GET /api/planner/plan/{event_id}/remote` — aktuelle Remoteversion lesen und
  als bestätigten Lese-Datenstand einsortieren (kein Event-Write).
- `GET /api/planner/operations` / `POST …/reconcile` — offene Vorgänge und
  lesender Abgleich (P22).

Tests ersetzen die Client-Brücke durch kontrollierte Adapter; der Testlauf
schreibt nicht gegen intervals.icu oder Garmin.
