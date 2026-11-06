# Offene Vorgänge und dauerhafte Zuordnung — P22

**Stand:** 06.11.2026 · **Paket:** P22 · **Grundlage:** Abschnitt 9.7 und
Arbeitspaket P22.

## 1. Was vor dem Senden gespeichert wird

Die vorhandene SQLite-Datenbank bekommt die Tabelle `planner_operation`. Ein
Eintrag hält zusammen:

| Feld | Zweck |
|---|---|
| `operation_id` | stabile lokale Vorgangs-ID über Reload/Neustart |
| `account_id`, `athlete_id` | Zuordnung; ein fremder Account sieht den Vorgang nicht |
| `local_id`, `draft_id` | lokale Einheit und Entwurf |
| `remote_id` | tatsächliche Remote-ID nach bestätigter Anlage |
| `external_id` | stabile externe Identität vor dem ersten Request |
| `mode`, `kind`, `state` | Update/Create, Metadaten/Struktur, Speicherzustand |
| `payload_json` | eingefrorener Payload des Vorgangs |
| `snapshot_json` | vollständiger `SaveSnapshot` inklusive beabsichtigter und basaler Planung |
| `editor_shape_json`, `editor_shape_state` | optionale Editorform, `prepared` bis zur Bestätigung |
| `created_at`, `updated_at` | Aufbewahrung und Nachvollziehbarkeit |

Der Koordinator schreibt den `saving`-Eintrag **vor** dem Adapteraufruf.
Scheitert diese Speicherung, wird nichts gesendet und der Status ist
`failed` mit `persistence_error`. Nach dem Adapteraufruf wird derselbe Eintrag
mit Ergebnis, Remote-ID und externer Identität aktualisiert. Scheitert nur
diese Aktualisierung, bleibt das bestätigte Remote-Ergebnis bestehen; es wird
kein zweiter Write ausgelöst.

## 2. `unknown` und `savedUnverified`

- `unknown`: Der Write könnte angekommen sein. Der Vorgang bleibt gesperrt und
  wird lesend abgeglichen. Ein abgestürzter `saving`-Zustand wird beim
  Wiederöffnen ebenfalls zu `unknown`.
- `savedUnverified`: Der Write wurde bestätigt, die Darstellung ist aber noch
  nicht nachgeprüft. Die tatsächliche Remote-ID bleibt erhalten; ein erneutes
  Anlegen ist ausgeschlossen.

Nach einem Reload findet `SaveCoordinator.restore_open()` die offenen Vorgänge
über Account und Athlet wieder. `reconcile()` liest bei einem Update dieselbe
Remote-ID, bei einer Neuanlage ausschließlich über die externe Identität und den
geplanten Tag. Kennt die Neuanlage aus der Create-Antwort bereits eine
Remote-ID, wird zusätzlich genau diese ID gelesen; ein 404 dieser ID ohne
externen Treffer beendet den Vorgang als `failed` (`not_found`), weil die
Anlage nachweislich nicht mehr existiert. Ein bestätigter Treffer übernimmt die
Remote-ID; kein Treffer ohne bekannte Remote-ID bleibt offen; mehrere Treffer
werden Konflikt. Ein Update auf eine verschwundene Remote-ID endet ebenfalls als
`failed`. Es gibt keinen automatischen Retry.

## 3. Aufbewahrung

Endgültig abgeschlossene Vorgänge (`saved`, `failed`, `conflict`) werden nach
**sieben Tagen** gelöscht. Offene, unklare und unbestätigte Vorgänge bleiben
unabhängig vom Alter erhalten. Die Bereinigung läuft beim Abruf der offenen
Vorgänge und beim Abgleich; sie ist keine neue Hintergrundschleife.

## 4. EditorShapeMetadata

Die Editorform wird nur mitgesichert, wenn ein Aufrufer sie tatsächlich
braucht. Sie wird vor dem Remote-Request als `prepared` abgelegt und erst nach
bestätigtem Rundlauf auf `confirmed` gesetzt. Eine fehlgeschlagene lokale
Metadatenspeicherung nach erfolgreichem Remote-Write erzeugt keinen zweiten
Remote-Write. Der aktuelle Leseadapter rekonstruiert die unterstützten
Editorformen nativ; die Metadaten bleiben deshalb ein vorbereiteter, optionaler
Pfad.

## 5. API

- `GET /api/planner/operations` listet offene Vorgänge des aktuellen Accounts
  ohne vollständige Payloads.
- `POST /api/planner/operations/{operation_id}/reconcile` setzt einen offenen
  Vorgang lesend fort. Ein Vorgang eines anderen Accounts liefert 404.

## 6. F09-Nachweis

`tests/test_planner_operations.py` und `tests/test_planner_operations_api.py`
prüfen: Snapshot vor Dispatch sichtbar, Timeout erzeugt `unknown`, Reload findet
denselben Vorgang, der Abgleich erkennt genau eine bereits angelegte Einheit,
ein bestätigtes Create mit fehlgeschlagenem Read behält die Remote-ID, ein
Persistenzfehler vor dem Senden verhindert den Write, und ein fremder Account
erhält keinen Zugriff.
