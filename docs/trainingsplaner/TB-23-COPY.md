# TB-23 — Wochen- und Blockkopie (P5–P7)

**Stand:** 11.11.2026 · **Branch:** `feature/tb-23-trainingsplaner-erweiterung`
**Entscheidungen:** D-95 (Umfang), D-96 (Provenienz), D-97 (dauerhafte Writes)
**Nicht enthalten:** Merge, Deployment, Live-Schreibtest gegen intervals.icu.

## 1. Umfang

- 1–4 aufeinanderfolgende Kalenderwochen, Montag–Sonntag.
- Nur Einträge der Planer-Projektion mit `kind == "planned"`.
- `linked`, `recorded` und `completionReference` werden nie kopiert.
- Bestehende Zielplanungen bleiben unverändert; es wird ausschließlich additiv
  ergänzt.
- Standardziel: `source_start + 7·weeks`; die Zielwoche ist manuell änderbar.
- Quell- und Zielabdeckung müssen `coverage == "covered"` sein.

## 2. API

Alle Routen sind an den vorhandenen Account-/Athleten-Scope gebunden.
Unbekannte oder fremde IDs enden als 404.

### `POST /api/planner/copy/preview`

```json
{"source_start":"2026-11-09","weeks":1,"target_start":"2026-11-16"}
```

Rein lesend. Antwort:

```json
{
  "source_start":"2026-11-09","source_end":"2026-11-15",
  "target_start":"2026-11-16","target_end":"2026-11-22",
  "weeks":1,"time_zone":"Europe/Vienna",
  "coverage":{"source":"covered","target":"covered"},
  "blockers":[{"code":"…","message":"…","date":null}],
  "warnings":[{"code":"existing_target","message":"…","date":"…"}],
  "existing_target_count":0,
  "items":[{"source_event_id":"9101","source_date":"…","target_date":"…",
    "name":"…","sport":"Run","sport_label":"Laufen","seconds":2700,
    "metres":0,"status":"ready|already_copied","reason":null}],
  "totals":{"items":1,"seconds":2700,"metres":0,
    "already_copied":0,"blocked":0}
}
```

Blocker-Codes: `invalid_source`, `invalid_target`, `invalid_weeks`,
`overlap`, `source_coverage`, `target_coverage`, `source_not_cloneable`,
`no_items`, `copy_running`. Ungültige Wochen/Daten enden als 422; fachliche
Blocker stehen in der 200-Antwort.

### `POST /api/planner/copy/jobs`

Body wie Preview plus `client_request_id` (8–200 Zeichen). Persistiert Job und
Items vor dem ersten Remote-Write. Derselbe `client_request_id` im selben Scope
liefert denselben Job (`created:false`) ohne neue Items. Blocker enden als
409/422 mit `detail.code` und `detail.blockers`, bevor Items entstehen.

### `GET /api/planner/copy/jobs?state=open`

Listet Jobs mit `queued`/`running` sowie `partial`/`failed` mit unklaren Items.
Ein solcher Job blockiert eine neue Kopie, bis er lesend geklärt ist.

### `GET /api/planner/copy/jobs/{job_id}`

`{"job": CopyJob, "items": CopyItem[]}`. Fremder Scope = 404.

### `POST /api/planner/copy/jobs/{job_id}/advance`

Verarbeitet **genau ein** offenes Item. Paralleler Aufruf = 409 `copy_busy`.
Ein Job mit unklarem Item wird über denselben Aufruf lesend geprüft; es wird
kein zweiter Create ausgelöst.

`CopyJob` enthält `state` (`queued`, `running`, `completed`, `partial`,
`failed`), `total`, `created`, `failed`, `pending`, `unknown`, `message`,
`can_advance` und `next_target_date`.

`CopyItem.state`: `pending`, `created`, `saved_unverified`, `unknown`, `failed`,
`conflict`. `created` bedeutet bestätigt und lokal eingesortiert.

## 3. Schema

```sql
planner_copy_job(
  job_id, account_id, athlete_id, client_request_id, state,
  source_start, target_start, weeks, time_zone, total, message,
  lease_owner, lease_expires_at, created_at, updated_at
)
planner_copy_item(
  item_id, job_id, account_id, athlete_id, ordinal,
  source_event_id, source_date, target_date,
  draft_id, local_id, name, sport, nodes_json, state,
  operation_id, remote_id, message, created_at, updated_at
)
```

- Eindeutig: `(account_id, athlete_id, client_request_id)`.
- Genau ein aktiver Job je Scope (`queued`/`running`).
- Provenienz-Index auf `(account_id, athlete_id, source_event_id,
  target_date)` für `pending`, `created`, `saved_unverified`, `unknown`,
  `conflict`. `failed` blockiert eine bewusste neue Kopie nicht.
- `nodes_json` ist die vorhandene API-Knotenform; sie wird über
  `build_new_draft` in den bestehenden Entwurf überführt, nicht über einen
  zweiten Serializer.

## 4. Sicherheitsgrenzen

- Job/Items werden vor dem ersten Remote-Write committet.
- Pro `advance`: prozesslokaler Lock plus DB-Lease (30 s). Ohne Claim kein
  Write; nach einem Absturz wird der Lease nach Ablauf übernommen.
- Writes gehen ausschließlich über `SaveCoordinator`/`EventWriteService` und
  den vorhandenen `planner_operation`-Pfad.
- Offene `planner_operation`-Einträge werden vor einem neuen Fortschritt
  gelesen (`restore_open`, `reconcile`).
- `unknown`/`savedUnverified` lösen keinen zweiten Create aus.
- Bereits bestätigte Quelle/Ziel-Kombinationen werden als `already_copied`
  erkannt und nicht erneut angelegt.
- Kein Rollback und kein automatisches Löschen bereits angelegter Events.
- Vorlagen-/Copy-Tabellen tragen den Scope selbst; `event` bleibt unverändert.

## 5. Tests

`tests/test_planner_copy_api.py` (16) und `tests/test_planner_copy.py` (2)
decken ab:

- lesende Vorschau ohne Job-/Event-Schreibe;
- Coverage fehlt, Überlappung, 1–4 Wochen, Monats-/Jahres-/Sommerzeit;
- bestehende Zielplanung bleibt;
- bereits absolvierte (linked) Einheit wird nicht kopiert;
- Doppelstart/derselbe `client_request_id` erzeugt keinen zweiten Job;
- sequentieller Advance, bestätigter Zielplan, kein Create vor dem ersten
  Advance;
- paralleler Advance = 409;
- Timeout/unklarer Create, lesender Abgleich ohne zweiten Create;
- Neustart des Koordinators mit offenem Vorgang;
- teilweise Kopie ohne Rollback;
- Quelle zwischen Vorschau und Start entfernt;
- bereits kopierte Quelle wird nicht dupliziert;
- fremder Scope = 404;
- Schema-Upgrade auf bestehender DB und Provenienz-Index.

Gesamtsuite: **528 passed**, 1 bekannte Starlette-Deprecation-Warnung.
`ruff` grün.

## 6. Bekannte Grenzen

- Kein Live-Rundlauf gegen intervals.icu; alle Writes liefen über kontrollierte
  Adapter.
- Schrittnamen mit Maßangabe (z. B. „100 m“) bleiben nicht kopierbar; die
  Vorschau blockiert die Gesamtübernahme mit `source_not_cloneable`.
- Archivierte Quell-Events sind lokal nicht sicher erkennbar; die
  Coverage-Prüfung ist die Grenze.
- `event` hat keine Account-/Athleten-Spalten; der Scope kommt aus den
  Settings, die Copy-Tabellen tragen ihn selbst.
- Ein `partial`/`failed`-Job mit unklarem Item bleibt sichtbar und muss bewusst
  über „Status prüfen“ fortgesetzt werden; es gibt keinen Auto-Retry.
