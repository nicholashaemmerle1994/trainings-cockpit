# Übergabe — Trainingsplaner P26/P27

**Stand:** 06.11.2026 · **Branch:** `feature/trainingsplaner` · **Kein Release
und kein Deployment in diesem Paket.**

Diese Datei ist die kurze Übergabe. Der vollständige Arbeitsnachweis steht in
`docs/training-planner-progress.md` (P26/P27), die verbindliche
Fähigkeitsgrenze in `FAEHIGKEITSMATRIX.md`.

## 1. Was gebaut und was wiederverwendet wurde

| Bereich | Zustand | Dateien |
|---|---|---|
| Planer-Tab und Kalenderwoche | neu aufgebaut | `web/src/pages/Planner.tsx`, `web/src/plannerQuery.ts` |
| Planungsdetail, Inline-Editor, Anlegen | neu aufgebaut | `web/src/components/PlanSheet.tsx`, `PlanEditor.tsx`, `AddWorkoutSheet.tsx` |
| Bestehende Aktivitätsdetails | **erhalten und weiterverwendet** | `web/src/components/UnitSheet.tsx`, `SessionProfile.tsx`, `WorkoutChart.tsx` |
| Tageskarte, Vorschau, Sportlabels | **erhalten und weiterverwendet** | `web/src/pages/Today.tsx`, `WorkoutPreview.tsx`, `sportIcon.tsx`, `format.ts` |
| Dashboard „Letzte 7 Tage“ | **erhalten**; Umfang bleibt reine Kennzahl | `web/src/pages/Today.tsx` mit `WeekStrip`, `MetricRow` |
| Wochen-/Planungsprojektion | neu, getrennte Quellen | `src/trainings_cockpit/planner/week.py`, `api.py` |
| Fachmodell, Remote-Adapter, Serializer | neu | `src/trainings_cockpit/planner/model.py`, `remote.py`, `serializer.py` |
| Speichern, Konflikte, Vorgänge, Sync | neu | `planner/save.py`, `event_write.py`, `conflicts.py`, `operations.py`, `syncmerge.py` |
| Alte Aktivitätenliste | **entfernt**, kein zweiter Listenmodus | gelöscht: `web/src/pages/Activities.tsx`, `web/src/components/ActivityTable.tsx` |

Die gelöschten Dateien waren über keinen Tab und keine Route erreichbar. Die
Dashboard-Auswahl `WeekStrip`/`MetricRow` und die Aktivitätsdetails in
`UnitSheet` wurden **nicht** entfernt.

## 2. Alte Routen und Deep-Links

| Aufruf | Verhalten |
|---|---|
| `/woche`, `/week`, `/planner/week`, `/planer/week` | per `replaceState` auf `/planer?woche=<Montag>` kanonisiert; keine zweite Liste, keine Schleife |
| `/planer/<JJJJ-MM-TT>`, `/planner/<…>`, `/woche/<…>`, `/week/<…>` | Datum wird auf den Montag seiner Woche abgebildet |
| `?datum=`, `?date=`, `?tag=`, `?von=`, `?bis=`, `?woche=` | auf die Planerwoche abgebildet; `bis`/`to`/`end` verankert einen Bereich am Enddatum |
| `/aktivitaet/<id>`, `/activity/<id>`, `/einheit/<id>`, `/unit/<id>` | öffnet dieselbe bestehende Aktivität über die lokale Zeilen-ID im Planer; der Detailpfad bleibt erhalten, die Woche kommt aus dem gespeicherten Planer-Kontext |
| Unbekannte Pfade | fallen auf „Heute“ zurück |

Die Umfang-Kennzahl erzeugt keinen dieser Zustände und hat keinen Link, keinen
Chevron und keinen `tabindex`.

## 3. Dashboard-Volumen bleibt unabhängig

- Das Dashboard nutzt weiterhin `metrics.build_overview` mit dem rollierenden
  Sieben-Tage-Fenster `today-6 … today`.
- Der Planer nutzt eine eigene Kalenderwochen-Projektion
  (`planner/week.py`, Montag–Sonntag) mit getrennten Quellenschlüsseln.
- Wochenwechsel im Planer ändern weder das Dashboard-Fenster noch dessen
  Umfang. Ein später eintreffender alter Wochen-Response wird über
  Query-Generation und Wochen-Schlüssel verworfen.
- Die Umfang-Karte ist im DOM ein `<aside class="card week">` ohne Link,
  Button oder Fokusziel. Ein Klick auf Wert oder Kartenfläche navigiert nicht.

## 4. Datenverfügbarkeit älterer Wochen

- Aktivitäten und Planungen kommen aus der lokalen SQLite-Datenbank
  (`activity`, `event`); der Planer liest sie über getrennte Quellen.
- `synced_range` unterscheidet „vollständig gelesen“ von „nicht verfügbar“.
  Eine Woche außerhalb des nachgewiesenen Bereichs wird **nicht** als
  bestätigte Null ausgegeben.
- Ein Ausfall einer Quelle entfernt die andere nicht; Ist- und Plan-Summen
  bleiben getrennt und werden als unvollständig markiert.
- **Intervals.icu:** Die vorhandenen Clients fragen einen Datumsbereich ab.
  Es gibt keine Seiten-/Cursor-Schleife. Bei Events ist kein `limit` gesetzt
  (API-Dokumentation: „default is all“); bei Aktivitäten ist `limit` optional.
  Eine serverseitige Kappung könnte die aktuelle Implementierung nicht
  erkennen. Diese Grenze ist im Abnahmebericht P26 benannt.
- **Garmin:** Aktivitäten werden in 100er-Seiten bis maximal 1000 geladen;
  die Nachtsignale laufen in 28-Tage-Fenstern.
- **Reichweite:** `tc sync --days 365` ist der Standard; die API akzeptiert
  maximal 730 Tage. Events werden zusätzlich 365 Tage in die Zukunft gelesen.
  Ältere Wochen sind nur so vollständig, wie sie im lokalen Bestand liegen.
- F14 prüft mehrere Seiten, vollständig leer, nicht verfügbar und getrennte
  Quellenfehler als Konzeptfälle. Die tatsächliche Pagination-Grenze von
  intervals.icu bleibt die oben genannte Einschränkung.

## 5. Lokale Prüfung und Start

```bash
uv sync
uv run pytest -q
cd web && npm run build && cd ..
uv run tc serve --port 8000
```

Danach `http://127.0.0.1:8000` öffnen. Für einen echten Sync müssen `.env` und
die Keys gesetzt sein. Ohne ausdrücklich vorgesehenen Testdatensatz und
Freigabe **keine produktiven Schreibzugriffe** gegen intervals.icu ausführen.

## 6. Geprüft / nicht geprüft

**Geprüft:** 380 Backend-Tests, `tsc --noEmit`, Vite-Build, manuelle Abläufe
A–D mit separater SQLite-Kopie und lokalem Kontrolladapter, langsamer
Wochenwechsel, alte Routen, Deep-Links, Krafttraining, Aktivitätsdetails und
Dashboard-Volumen.

**Nicht geprüft / nicht behauptet:** Live-Create/Update gegen intervals.icu,
Übertragung auf ein Gerät, echte Plan-/Aktivitätsbeziehung im Produktbestand,
Skip-Gruppe als speicherbare Gruppe, serverseitige Pagination-Garantie,
iOS-/Safari-Geräteprüfung (P25: Chromium/Viewport) und ein Release/Deployment.

## 7. Verbleibende Grenzen

Die vollständige Liste steht in `FAEHIGKEITSMATRIX.md`. Kurz: absolute bpm,
Leistungszonen, benutzerdefinierte Zonen, verschachtelte Wiederholungen,
mehrere Ziele, Rampen/Lap/Spezialschritte und globale Zielpriorität bleiben
gesperrt. Die Skip-Gruppe braucht den lesenden `EditorShapeMetadata`-Weg. Der
Vorab-GET/PUT ist nicht atomar; die Restlücke ist in `KONFLIKTE.md` benannt.
