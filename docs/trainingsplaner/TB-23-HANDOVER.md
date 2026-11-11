# TB-23 — Handover

**Stand:** 11.11.2026 · **Branch:** `feature/tb-23-trainingsplaner-erweiterung`
**Basis:** `develop` (`585af6f`) · **Nicht autorisiert:** Merge nach `main`,
Produktionsdeployment, Live-Schreibtest gegen intervals.icu.

Diese Datei ist der dauerhafte Projektstand für P3–P8. Nach jedem Arbeitspaket
wird sie aktualisiert; Git-Verlauf und Handover bilden zusammen den Stand.

## 1. Abgeschlossen

### P0 — Audit
Befunde in `docs/ENTSCHEIDUNGEN.md` / P1-Doku eingearbeitet. Kein Commit
separat.

### P1 — lokale Vorlagen und Klon-Dienst
`0813a05` · `docs/trainingsplaner/TB-23-P1.md`

- `workout_template` (SQLite, Account-/Athleten-Scope, kein FK auf `event`)
- `planner/templates.py`, `planner/clone.py`
- kanonischer Knoten-Codec über `planner/operations.py`
- stabile Codes `CloneCode` / `TemplateCode`

### P1-Nachbesserung
`72ddc0b`

- `instantiate()` prüft Vorlagen-Scope (`scope_mismatch`)
- gespeicherte Vorlagen werden semantisch validiert (`corrupt`)

### P3–P7 — Oberfläche und Kopie
- `d9552f3` Backend: persistente Copy-Jobs, Vorschau, sequentieller Advance,
  Provenienz, Lease, lesender Abgleich; Tests und Copy-Doku.
- `1864962` Frontend: Vorlage speichern/verwenden, Wochen-/Blockkopie.
- `5ebc18d`/`d32a5d8` Doku: Bedienungsanleitung, Copy-Vertrag,
  Planer-Index und Handover.

### P2 — Vorlagen-API
`2d98b7f`

- `GET /api/planner/templates`
- `POST /api/planner/templates/from-plan/{event_id}` (nur lokale `event`-Zeile)
- `GET /api/planner/templates/{template_id}`
- `POST /api/planner/templates/{template_id}/project` (nur lokale Projektion)
- `DELETE /api/planner/templates/{template_id}`
- Teststand vor P3: **510 passed**, `ruff` grün, Frontend-Build grün.

## 2. Getroffene Entscheidungen

- D-94: Vorlagen sind lokale, unabhängige Momentaufnahmen.
- D-95: Kopierumfang 1–4 Wochen, nur `kind == "planned"`, additiv,
  `coverage == "covered"` Pflicht, Standardziel `source_start + 7·N`.
- D-96: Provenienz `(account_id, athlete_id, source_event_id, target_date)`;
  `client_request_id` idempotent.
- D-97: Copy-Job/Items vor dem ersten Write persistieren, sequentiell über den
  bestehenden `SaveCoordinator`, `unknown`/`savedUnverified` nur lesend
  abgleichen, keine automatischen Retries, kein Rollback.
- Kein zweiter Serializer, kein zweiter intervals-Schreibweg, kein
  Remote-Write beim Öffnen/Auswählen/Projizieren.

## 3. Copy-API-Vertrag (für P5–P7)

### `POST /api/planner/copy/preview`

```json
{"source_start":"2026-11-09","weeks":1,"target_start":"2026-11-16"}
```

Antwort (rein lesend, keine Persistenz):

```json
{
  "source_start":"2026-11-09","source_end":"2026-11-15",
  "target_start":"2026-11-16","target_end":"2026-11-22",
  "weeks":1,"time_zone":"Europe/Vienna",
  "coverage":{"source":"covered","target":"covered"},
  "blockers":[{"code":"source_coverage","message":"…","date":null}],
  "warnings":[{"code":"existing_target","message":"…","date":null}],
  "existing_target_count":0,
  "items":[{
    "source_event_id":"123","source_date":"2026-11-09",
    "target_date":"2026-11-16","name":"…","sport":"Run",
    "sport_label":"Laufen","seconds":2700,"metres":null,
    "status":"ready","reason":null
  }],
  "totals":{"items":1,"seconds":2700,"metres":0,
            "already_copied":0,"blocked":0}
}
```

- `source_start`/`target_start` werden auf Montag normalisiert.
- `weeks` 1–4; `target_start` fehlt ⇒ `source_start + 7·weeks`.
- Nur Einträge der Planner-Projektion mit `kind == "planned"`.
- `status`: `ready`, `already_copied`, `blocked`.
- Blocker: `invalid_source`, `invalid_target`, `invalid_weeks`, `overlap`,
  `source_coverage`, `target_coverage`, `source_not_cloneable`,
  `no_items`, `copy_running`.
- Jede unzulässige Quelle blockiert die Gesamtübernahme.

### `POST /api/planner/copy/jobs`

Body wie Preview plus `"client_request_id":"…"` (Pflicht, 8–200 Zeichen).
Antwort `{"job": CopyJob, "items": CopyItem[], "created": true}`.
Derselbe `client_request_id` im selben Scope liefert denselben Job
(`created:false`), ohne neue Items. Bei Blockern 422 mit `detail.code` und
`detail.blockers`. Bei bereits laufendem Job `409 copy_running`.

### `GET /api/planner/copy/jobs?state=open`

`{"jobs":[CopyJob]}` im Account-/Athleten-Scope.

### `GET /api/planner/copy/jobs/{job_id}`

`{"job": CopyJob, "items": CopyItem[]}`; fremde ID = 404.

### `POST /api/planner/copy/jobs/{job_id}/advance`

Verarbeitet **genau ein** offenes Item, danach Antwort wie GET. Parallelaufruf
auf denselben Job = `409 copy_busy`. Kein Fortschritt mehr ⇒ Job endet
`completed` oder `partial`.

`CopyJob`:

```json
{"job_id":"…","client_request_id":"…","state":"queued|running|completed|partial|failed",
 "source_start":"…","target_start":"…","weeks":1,
 "total":3,"created":1,"failed":0,"pending":2,"unknown":0,
 "message":"…","created_at":"…","updated_at":"…","can_advance":true,
 "next_target_date":"2026-11-17"}
```

`CopyItem`:

```json
{"item_id":"…","job_id":"…","source_event_id":"123",
 "source_date":"…","target_date":"…","draft_id":"…","local_id":"…",
 "name":"…","sport":"Run","state":"pending|created|saved_unverified|unknown|failed|conflict|skipped",
 "operation_id":null,"remote_id":null,"message":null}
```

## 4. Nächste Schritte

1. P8: Regression, Build, visuelle Prüfung, Push, PR gegen `develop`.

## 4a. Umgesetzt (P3–P7)

- `web/src/components/TemplateSaveSheet.tsx`: Vorlage aus persistierter
  Planung speichern, Name 1–120, Doppelklick-Schutz, verständliche
  `CloneCode`-Fehler, Erfolg ohne Remote-Write.
- `web/src/components/PlanSheet.tsx`: Aktion nur in der Leseansicht; im
  Entwurf gesperrt mit Hinweis auf den gespeicherten Stand. Nested Sheet,
  Fokus/Escape über `Sheet`.
- `web/src/components/AddWorkoutSheet.tsx`: „Aus Vorlage erstellen“,
  Liste/Suche/Leer-/Fehlerzustand, Projektion mit neuer `draft_id`, Aufbau
  als `nodes` in den bestehenden Entwurf.
- `web/src/plannerDraftStore.ts`: Vorlagenaufbau überlebt die
  Entwurfswiederherstellung.
- `web/src/components/CopyWeekSheet.tsx`: 1–4 Wochen, Standardziel,
  Vorschau, Blocker, bestehende Zielplanungen, Fortschritt, Teil-/Fehlerzustand,
  offene Jobs fortsetzen, Zielwoche öffnen.
- `web/src/pages/Planner.tsx`: dezente Aktion „Woche kopieren“ in der
  Wochen-Navigation, Kopiernotiz, Dateninvalidierung.
- `web/src/api.ts`/`types.ts`: typisierte Template-/Copy-Verträge und
  strukturierte `ApiError`-Details.
- `web/src/styles.css`: Tokens/Abstände des Designsystems, 320–1440 geprüft,
  kein horizontaler Überlauf.

## 4b. API-Abweichungen

- Die in Abschnitt 3 skizzierte Start-Antwort ist umgesetzt; `POST /jobs`
  liefert 200 (idempotent), nicht 201.
- `GET /copy/jobs?state=open` enthält auch `partial`/`failed` mit unklaren
  Items, damit „Status prüfen“ sichtbar bleibt.
- `can_advance` ist bei unklaren Items wahr; das Frontend loopt aber nur bei
  `pending > 0` automatisch, sonst bewusster „Status prüfen“-Klick.

## 5. Teststatus

Aktuell: `UV_CACHE_DIR=$PWD/.uv-cache uv run pytest` → **529 passed** (17 Copy-API-, 2 Copy-Schema-Tests), 1 bekannte
Starlette-Deprecation-Warnung. `ruff` grün. `npm run build` grün.

## 6. Bekannte Grenzen

- Schrittnamen mit Maßangabe (z. B. „100 m“) lehnt der bestehende Serializer ab;
  Vorlagen/Kopien solcher Einheiten enden als `serialization_failed` bzw.
  `source_not_cloneable`.
- Archivierte Quell-Events sind lokal nicht sicher erkennbar; die
  Coverage-Prüfung ist die Grenze.
- `event` hat keine Account-/Athleten-Spalten; der Planer-Scope kommt aus den
  Settings, die Vorlagen-/Copy-Tabellen tragen ihn selbst.
- Kein Live-Rundlauf gegen intervals.icu.
