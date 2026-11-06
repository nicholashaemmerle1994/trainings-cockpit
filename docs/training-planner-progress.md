# Trainingsplaner — Arbeitsnachweis P00

**Stand:** 06.11.2026  
**Paket:** P00 — Repository und bestehenden Datenfluss erfassen  
**Basis:** Branch `feature/trainingsplaner`, HEAD `7153a19`  
**Umfang:** Nur Bestandsaufnahme. Keine Produktcode-Änderung, keine Datenbankänderung, keine API-Zugangsdaten ausgegeben.

> **Arbeitskopie-Hinweis:** Die lokale `data/cockpit.db` dieser Umgebung enthält
> 0 Aktivitäten, 0 Events und 2 Wellness-Zeilen. Reale historische Abdeckung ist
> daraus nicht ablesbar. Die Aussagen zu älteren Wochen stützen sich deshalb auf
> den tatsächlichen Code, die vorhandenen Tests und den dokumentierten Bestand
> aus `docs/ENTSCHEIDUNGEN.md` (E-01: 283 Aktivitäten vom 08.01.–29.10.2026,
> 47 Kalender-Events). Diese Zahlen sind Bestandsdokumentation, kein Nachweis
> für die aktuell leere Arbeitskopie.

## 1. Framework, Sprache, Prüfbasis

| Bereich | Tatsächlicher Befund |
|---|---|
| Backend | Python `>=3.12`, FastAPI, uvicorn, httpx, SQLite. Einstieg `src/trainings_cockpit/api.py`, CLI `src/trainings_cockpit/cli.py` (`tc`). |
| Paketmanager | `uv` mit `pyproject.toml` und `uv.lock`; Frontend `npm` mit `web/package.json` und `web/package-lock.json`. |
| Frontend | React 19.1, TypeScript 5.9, Vite 7.1. Kein CSS-Framework, keine Chart-Bibliothek, keine State-Bibliothek. |
| Router | **Kein Router.** `web/src/App.tsx` hält den aktiven Bereich als `useState<Tab>`; `web/src/tabs.ts` ist die einzige Tab-Liste. Das Backend liefert nur den SPA-Fallback (`api.py:256-263`). Es gibt keine URL-Pfade, keine History-API und keine Deep-Link-Logik im Frontend. |
| State | Lokaler React-State in `App.tsx`, `Today.tsx`, `Activities.tsx`, `WeekSheet.tsx`, `UnitSheet.tsx`, `SessionSheet.tsx`. Kein Context, kein Reducer, kein Query-Cache. |
| API-Schicht | `web/src/api.ts` (zentraler `fetch`-Wrapper), Typen in `web/src/types.ts`, Endpunkte in `src/trainings_cockpit/api.py`. |
| Zentraler Theme-/Tokenort | `web/src/styles.css`, `:root` ab Zeile 45; verbindliche Dokumentation in `DESIGN.md` Abschnitt 10. Keine Tokens außerhalb dieser beiden Orte. |
| UI-Bausteine | `Sidebar`, `ScreenHeader`, `DashboardCard`, `MetricRow`, `StatusBadge`, `WorkoutPreview`, `WeekStrip`, `Sheet`, `SessionSheet`, `SessionProfile`, `UnitSheet`, `WorkoutChart`, `WeekSheet`, `ActivityTable`. |
| Vorhandene Tests | 148 pytest-Tests in `tests/`; keine Frontend-Unit-/Komponententests, kein Vitest. `npm run build` führt `tsc --noEmit` und den Vite-Build aus. Kein CI-Verzeichnis. |
| Bild-/Prototypreferenzen | Alle acht PNGs in `docs/trainingsplaner/references/` sowie `prototype/Trainingsplaner-Referenz.html` vorhanden; PNG-Signaturen und Maße geprüft, HTML lesbar. |

### 1.1 Prüfbefehle und Ausgangsstand

| Befehl | Ergebnis am 06.11.2026 |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **148 passed**, 1 Warnung (`StarletteDeprecationWarning` zu `httpx` im TestClient), 6,05 s. |
| `npm run build --prefix web` | **Erfolg.** `tsc --noEmit` ohne Fehler; Vite baut 53 Module, `index-BJkbOUeP.js` 266,82 kB, `index-DnbPmkBP.css` 35,55 kB. |
| `UV_CACHE_DIR=.uv-cache uv run ruff check .` | **23 bestehende Fehler**, nicht durch P00 verursacht: 18 × `E501` (Zeilenlänge), 4 × `F401` (unbenutzte Importe in `tests/test_load.py` und `tools/vault_import.py`), 1 × `B905` (`zip()` ohne `strict` in `tests/test_load.py`). Keine Auto-Fixes ausgeführt. |
| `git status --short` nach den Prüfungen | leer; Build und Tests haben keine verfolgten Dateien verändert. |

`UV_CACHE_DIR=.uv-cache` war in dieser Umgebung nötig, weil der Standard-Cache
`/home/node/.cache/uv` nicht beschreibbar ist. Der reguläre Projektbefehl bleibt
`uv run pytest`; fachlich ist der Cache-Pfad ohne Bedeutung.

## 2. Tatsächlicher Datenfluss

### 2.1 Geplante Einheit: Einlesen → Anzeigen

1. **Remote lesen:** `sync.sync()` ruft `IntervalsClient.events(oldest, newest)`
   auf (`src/trainings_cockpit/sync.py:44-45`). Der Zeitraum ist
   `today - days` bis `today + 365` (`sync.py:32-34`); `days` ist standardmäßig
   365. Es wird **keine** Kategorie gefiltert.
2. **Lokal speichern:** `db.upsert_events()` schreibt je Event eine Zeile in
   `event` (`db.py:326-350`). Gespeichert werden `id`, `date` aus
   `start_date_local[:10]`, `sport`, `category`, `name`, `load`,
   `duration_s` aus `moving_time`, `distance_m`, `intensity`, `description`
   und das vollständige Roh-JSON in `raw` (`db.py:168-181`).
3. **Tageskarte:** `GET /api/overview` → `metrics.build_overview()` →
   `db.events_on(today)` und `db.events_on(tomorrow)` (`api.py:54-59`,
   `metrics.py:803-810`) → `plan.session_row()` → `plan.planned()` →
   `plan.parse_workout()` liest `event.raw.workout_doc.steps`
   (`plan.py:281-359`). Die Karte zeigt nur heute und morgen.
4. **Detail öffnen:** `Today` öffnet `SessionSheet` mit der Event-ID
   (`Today.tsx:313-315`). `GET /api/session/{event_id}` →
   `db.event_by_id()` → `plan.session()` (`api.py:84-93`,
   `plan.py:537-553`). `plan.session()` liefert geplante Dauer/Distanz,
   Schritte, Achse, Verpflegung und den heuristischen Ist-Abgleich.
5. **Darstellen:** `SessionSheet` zeigt `SessionProfile` (geplante Blöcke),
   Kennzahlen, Struktur und bei vorhandenem `actual` den Ist-Verlauf über
   `WorkoutChart` (`SessionSheet.tsx:44-149`). `_add_series()` hängt den
   gespeicherten Verlauf an (`api.py:96-102`).

**Wichtige Grenze:** Der Weg ist heute **rein lesend**. Ein Bearbeiten von
Name, Termin oder Aufbau existiert im Produktcode nicht.

### 2.2 Geplante Einheit: Bearbeiten → Remote-Antwort

**Befund: nicht vorhanden.** Konkret fehlen:

- ein Editor oder eine Edit-Route in `web/src` (kein `WorkoutEditor`, kein
  Draft-Store, kein Speichern-Button für Planungen);
- ein schreibender API-Endpunkt in `api.py` (kein `PATCH`/`PUT` für Events);
- eine Update-Methode im vorhandenen Client. `IntervalsClient` besitzt
  `upsert_events()` (POST bulk upsert, `sources/intervals.py:198-205`),
  `delete_events()` (`:207-212`) und `create_event()` (`:214-219`), aber
  **kein** gezieltes `PUT /events/{eventId}`. `event()` ist nur GET
  (`:176-177`).
- eine Serialisierung des internen Aufbaus. `plan.py` parst nur
  `workout_doc`; `spike/workout.py` baut ausschließlich den Phase-0-Testtext
  (`TEST_DESCRIPTION`) und ist kein Produkt-Serializer.

Der einzige vorhandene Schreibweg ist der CLI-Test `tc push-test`
(`cli.py:404-448`): `workout.build_test_event()` → `client.upsert_events()` →
`client.event()` zum Rücklesen → `workout.verify_event()` → optional
`client.delete_events()`. Er schreibt einen festen Testtext, hat keine
Konflikterkennung, keine stabile lokale Vorgangsidentität und ist nicht an die
UI angebunden. **Er ist kein Planer-Speicherweg.**

Damit sind für P17–P22 alle Schreib-, Konflikt-, Idempotenz- und
Offline-Vorgänge Neuimplementierungen auf dem vorhandenen Client, nicht
Erweiterungen eines bereits funktionierenden Produktpfads.

### 2.3 Aufzeichnung: Einlesen → Aktivitätsdetails

1. **intervals-Aktivitäten:** `sync.sync()` ruft
   `IntervalsClient.activities(oldest, today)` (`sync.py:44`) →
   `db.upsert_activities()` → `activity` (`db.py:187-221`).
2. **Garmin-Aktivitäten:** `sync._garmin_data()` → `fetch_garmin()` →
   `actor_rows()` (`sync.py:146-160`, `sources/garmin.py:115-176`). Nur
   `Run`, `VirtualRun`, `Swim`, `OpenWaterSwim` kommen direkt; die Last wird
   mit `load.compute_load()` berechnet (`load.py:36-45`).
3. **Dedupe vor dem Schreiben:** `dedupe.behalten()` entscheidet anhand der
   Rohdaten, welche Quelle bleibt (`sync.py:65-70`); `delete_unlisted()`
   entfernt intervals-Zeilen, die die Quelle im gesyncten Zeitraum nicht mehr
   führt (`sync.py:65-67`, `db.py:300-323`). Danach werden die Gewinner
   geschrieben und verbleibende Dubletten gelöscht (`sync.py:72-76`).
4. **Verläufe:** `streams.fetch_missing()` holt für die letzten **14 Tage**
   fehlende Sekundenwerte, aus intervals-Streams oder Garmin-FIT, und legt sie
   in 5-Sekunden-Mitteln in `activity_stream` ab (`sync.py:89-95`,
   `streams.py:24-31`, `:296-370`).
5. **API:** `GET /api/overview` liefert die letzten 12 Aktivitäten und die
   heutigen ungeplanten Einheiten (`metrics.py:797-815`). `GET /api/week`
   liefert die letzten sieben Tage (`api.py:105-119`). `GET /api/unit/{row_id}`
   liefert eine Aufzeichnung mit Zonen, Quelle und Verlauf
   (`api.py:122-131`).
6. **UI:** `Today` öffnet `UnitSheet` aus der Wochenliste oder aus
   „Zusätzlich“ (`Today.tsx:316-325`). `UnitSheet` lädt
   `api.unit(rowId)`, zeigt `WorkoutChart`, Dauer/Distanz/Last, `ZoneBar`,
   Puls/Tempo/Höhenmeter/Kalorien und die Quellenangabe
   (`UnitSheet.tsx:21-145`). `SessionSheet` nutzt für den Ist-Teil denselben
   `WorkoutChart` (`SessionSheet.tsx:113-145`).
7. **Nicht erreichbar:** `web/src/pages/Activities.tsx` und
   `components/ActivityTable.tsx` existieren, sind aber nicht in `TABS` oder
   `App.tsx` eingebunden. D-38 hat den Aktivitäten-Tab am 01.11.2026 bewusst
   abgehängt. Es gibt keine direkten Aktivitäts-URLs.

## 3. Alte Liste „Letzte 7 Tage“, Dashboard-Karte, Tabs, Planerroute

### 3.1 Aufrufstellen der alten Liste

| Stelle | Tatsächlicher Code | Befund |
|---|---|---|
| Dashboard-Karte | `web/src/pages/Today.tsx:295` `<DashboardCard as="aside" className="week" title="Letzte 7 Tage" subtitle="Umfang und Plan">` | Die Karte selbst ist **nicht** klickbar. `DashboardCard` in `ui.tsx:6-36` hat keinen `onClick`, keinen Link und keine Rolle. |
| „Umfang“ | `Today.tsx:298-302`, `MetricRow` mit `onClick={() => setWeekOpen(true)}` | Öffnet `WeekSheet`. |
| „Einheiten“ | `Today.tsx:304-308`, `MetricRow` mit demselben `onClick` | Öffnet **dieselbe** `WeekSheet`. |
| Chevron | `web/src/components/ui.tsx:75-82` | `MetricRow` rendert bei vorhandenem `onClick` ein `<button>` und den Pfeil `.metric-row__caret`; CSS `.metric-row--button` (`styles.css:1101-1122`). |
| Karten-Wrapper | `Today.tsx:295-310` | Kein zusätzlicher Wrapper-Handler, kein Karten-`onClick`. Nur die beiden `MetricRow`-Buttons sind interaktiv. |
| Overlay-Zustand | `Today.tsx:92-94`, `:316-322` | `weekOpen` und `openUnit` sind reiner React-State. `WeekSheet` wird mit `top={openUnit == null}` gerendert. |
| Detail-Overlay | `Today.tsx:323-325` | `UnitSheet` liegt als zweites `Sheet` über der Liste. |
| Listeninhalt | `WeekSheet.tsx:24-58` lädt `api.week()`; `:60-109` gruppiert und rendert | Keine Datumsnavigation, kein Query-Parameter, kein Router. |
| Tagesgruppen | `WeekSheet.tsx:62-68` | `data.units` kommt aufsteigend aus `training_between()`; die Schleife gruppiert benachbarte Tage, danach `days.reverse()`. Anzeige daher **absteigend**, neuester Tag zuerst. |
| Summen | `WeekSheet.tsx:77-90` | Umfang aus `data.seconds`, Belastung aus `data.load`, Einheiten aus `data.units.length`. |
| Einheitenzeilen | `WeekSheet.tsx:94-108` | `WorkoutPreview` mit Sport-Icon, Name, Dauer/Distanz, Last; Klick öffnet `UnitSheet`. |
| Endpunkt | `api.py:105-119` | `GET /api/week`; `today = date.today()`, `start = today - 6`, `db.training_between(start, today)`. |
| Typ | `web/src/types.ts:205-217` | `WeekUnit`, `WeekResponse`; nur für diese Liste. |

### 3.2 Tabs und Planerroute

- `web/src/tabs.ts:3-9` definiert exakt zwei Tabs: `today` („Heute“) und
  `fuel` („Verpflegung“). `Sidebar.tsx` und die Tabbar in `App.tsx:142-155`
  lesen dieselbe Liste.
- Es gibt **keinen** Tab „Trainingsplaner“ und **keine** Planerroute. D-45
  hatte am 03.11.2026 einen Tab „Woche“ und `GET /api/week/plan` beschlossen,
  aber nicht gebaut. Der aktuelle Code enthält beides nicht. Die Ablösung von
  D-42 und D-45 durch den Planer ist als **D-68** festgehalten.
- Es gibt **keinen** React Router, keine `history`-/`pushState`-Aufrufe und
  keine URL-Auswertung. Die alte Liste ist ein Overlay, keine Route. Deshalb
  existiert heute auch **keine gespeicherte alte Listen-URL**, die weitergeleitet
  werden müsste. P07 muss mit dem Planer-Tab zugleich eine Route einführen;
  eine Kompatibilitätsweiterleitung ist erst danach für dann existierende URLs
  sinnvoll.
- `web/src/pages/Activities.tsx` ist vorhanden, aber nicht eingebunden (D-38).
  Es ist kein Ersatz für den Planer und darf nicht als zweite Liste
  weiterlaufen.

### 3.3 Was bleibt, was wird umgebaut, was entfällt

**Bleibt und wird weiterverwendet:**

- `DashboardCard`, `MetricRow` (ohne `onClick`), `StatusBadge`,
  `WorkoutPreview`, `WeekStrip`, `Sheet`, `SessionSheet`, `SessionProfile`,
  `UnitSheet`, `WorkoutChart`, `ZoneBar`, `format.ts`.
- Die Dashboard-Karte „Letzte 7 Tage“ mit ihrer rollierenden Berechnung aus
  `metrics.build_overview()` (`metrics.py:785-795`, `:836-845`).

**Wird umgebaut:**

- `WeekSheet` von einer rollierenden, absteigenden Sieben-Tage-Liste zu einer
  Kalenderwochenansicht mit sieben Tagen Montag–Sonntag, Navigation und
  getrennten Plan-/Ist-Einträgen. Die vorhandene Gruppierungs- und
  `WorkoutPreview`-Struktur ist dafür verwendbar; die Datenquelle reicht nicht.
- `api.week()`/`WeekResponse` zu einem Zeitraumvertrag mit expliziten lokalen
  Grenzen oder eine neue Planerabfrage. `db.events_between()` existiert bereits,
  wird aber derzeit von keiner Stelle aufgerufen (`db.py:468-473`).
- `Today`-Zustand `weekOpen`: entfällt, sobald die separate Liste durch den
  Planer-Tab ersetzt ist. `openUnit` bleibt für Aktivitätsdetails.
- `plan.matches()`/`plan.unplanned()`: der heuristische Tagesabgleich ist kein
  belegter Beziehungsvertrag und muss für die gemeinsame Wochenliste durch
  nachgewiesene Beziehungen ersetzt bzw. klar als offener Bestand behandelt
  werden.

**Entfällt:**

- die eigenständige rollierende `WeekSheet`-Liste als zweiter Modus;
- `onClick` auf „Umfang“ und „Einheiten“ samt Chevron und Button-Semantik;
- die Vorstellung, der Planer sei über „Umfang“ erreichbar.

## 4. Ursache der bisherigen Sieben-Tage-Grenze

Die Grenze entsteht **nicht in der UI und nicht in der Speicherung**, sondern
in der festen Zeitraumberechnung des Endpunkts `GET /api/week`:

```python
# src/trainings_cockpit/api.py:105-119
today = date.today()
start = today - timedelta(days=6)
rows = db.training_between(conn, start, today)
```

`WeekSheet` ruft `api.week()` ohne Parameter auf (`WeekSheet.tsx:36-49`) und
hat keine Datumssteuerung. Die Datenbankabfrage `db.training_between()` nimmt
beliebige `start`/`end`-Werte entgegen (`db.py:371-379`); sie ist nicht auf
sieben Tage begrenzt. Es gibt keine Pagination in diesem Pfad.

Die weiteren Grenzen sind getrennt davon zu betrachten:

| Ebene | Tatsächliche Grenze | Bedeutung für ältere Wochen |
|---|---|---|
| UI | `WeekSheet` zeigt nur den einen Aufruf ohne Datumsparameter. | Kein UI-Filter, sondern fehlende Steuerung. |
| Backend | `/api/week` fest `today - 6` bis `today`. | **Hauptursache.** |
| DB/Speicherung | Keine 7-Tage-Speichergrenze; `activity`/`event` speichern alles, was der Sync schreibt. | Ältere Wochen sind bereits in der DB, sofern gesynct. |
| Sync-Zeitraum | `sync.sync()` standardmäßig 365 Tage rückwärts; Events bis 365 Tage voraus (`sync.py:32-34`). `POST /api/sync` erlaubt 7–730 Tage (`api.py:222-223`). | Ältere als der gesyncte Zeitraum fehlen; kein Vollhistorie-Versprechen. |
| Verläufe | `streams.fetch_missing()` nur 14 Tage (`streams.py:29`, `:296-309`). | Ältere Aktivitäten können in der Liste stehen, aber ohne `UnitSeries`/Diagramm. |
| Garmin-Quelle | `_all_activities()` paginiert 100 pro Seite bis maximal 1000 (`sources/garmin.py:241-260`). | Sehr große Zeiträume können gekappt werden; die Liste zeigt das nicht an. |
| intervals-Quelle | `activities(oldest, newest)` ist ein Bereichsabruf ohne eigene Pagination (`sources/intervals.py:141-153`). | Bereichsabdeckung hängt vom Sync-Zeitraum ab. |

**Kleinste Änderung für gezielt ältere Wochen:** Den vorhandenen Lesezugriff
parametrisieren, nicht die Datenhaltung ändern.

- Minimal: `GET /api/week` um validierte, inklusive lokale `from`/`to`-Parameter
  erweitern und an `db.training_between(conn, from, to)` übergeben. Für die
  Planeransicht zusätzlich `db.events_between(conn, from, to)` verwenden; diese
  Funktion existiert bereits.
- Sauberer für P06/P07: eine eigene Planerabfrage (z. B.
  `GET /api/planner?week=YYYY-MM-DD`) mit `db.training_between()` und
  `db.events_between()`, damit die Dashboard-Karte und der Planer getrennte
  Zeitraumverträge behalten. Die Dashboard-Karte liest ohnehin
  `metrics.build_overview()`, nicht `/api/week`.
- Für Wochen außerhalb des gesyncten Zeitraums: den bestehenden Sync mit
  größerem `days` aufrufen (CLI ohne Obergrenze, API bis 730) oder gezielt
  nachladen. Kein unkontrollierter Vollimport beim Öffnen des Planers.
- Für fehlende Verläufe älterer Aktivitäten: `streams.fetch_missing(days=...)`
  gezielt erweitern; die Liste darf deshalb nicht leer erscheinen, der fehlende
  Verlauf bleibt als fehlend sichtbar.

## 5. Plan-/Aktivitätsbeziehungen, Identitäten, Dedupe, Kardinalität

### 5.1 Identitäten

| Objekt | Identität im Code | Befund |
|---|---|---|
| Aktivität (Remote) | `(source, source_id)` mit `UNIQUE` (`db.py:13-35`) | `source` ist `intervals` oder `garmin`; `source_id` ist die jeweilige Remote-ID. Zwei Quellen derselben realen Einheit bleiben zunächst zwei Zeilen. |
| Aktivität (lokal/UI) | `activity.id` (`row_id`) | `UnitSheet` und `/api/unit/{row_id}` verwenden ausschließlich diese lokale Zeile. `activity_payload()` liefert zusätzlich `id = source_id` (`metrics.py:614-631`). |
| Event/Planung | `event.id` = intervals-Event-ID (`db.py:54-67`, `:168-181`) | Primärschlüssel. Eine separate lokale Plan-ID gibt es nicht. `external_id` wird nur im Roh-JSON/CLI-Test verwendet, nicht als Spalte oder Beziehung. |
| Plantyp vs. Aktivitätstyp | getrennte Tabellen und getrennte Endpunkte `/api/session/{event_id}` und `/api/unit/{row_id}` | Eine gleiche numerische ID `123` kann in beiden Tabellen vorkommen; die Endpunkte und UI-Zustände trennen sie. Ein gemeinsamer typisierter Identitätskontext (Account/Athlet/Objekttyp) fehlt. |

### 5.2 Vorhandene Plan-/Aktivitätsbeziehung

Es gibt **keine explizite Beziehung** in Schema, API oder UI:

- keine Tabelle `session_actual`, `plan_activity` oder vergleichbar;
- keine Spalte `paired_activity_id`, `activity_id` oder `completed_at` in
  `event`;
- keine Auswertung von `external_id` für ein Matching;
- `event.raw` kann weitere Remote-Felder enthalten; der Code liest sie nicht
  für eine Beziehung aus. Ob die Quelle ein solches Feld liefert, ist mit der
  leeren Arbeitsdatenbank nicht belegbar.

Die einzige Zuordnung ist die Heuristik `plan.matches()`
(`plan.py:467-487`):

1. gleicher Kalendertag (`event.date`),
2. gleiche Sportart-Familie (`plan.sport_family`),
3. bei mehreren Kandidaten die Aktivität mit der geringsten
   Dauer-Differenz zur geplanten Dauer.

`plan.session_row()` setzt `done = matches(...) is not None`
(`plan.py:556-572`). `plan.unplanned()` vergibt die so gefundenen Zeilen und
behandelt den Rest als „Zusätzlich“ (`plan.py:504-521`). Das ist **kein
Bestätigungsnachweis** für eine abgeschlossene Planung und keine
datumsübergreifende Beziehung. Ein gleichnamiger Lauf am selben Tag gilt als
Treffer, auch ohne explizite Zuordnung.

**Kardinalität:** Der Code geht faktisch von höchstens einer Aktivität pro
Event aus (`matches()` liefert genau eine Zeile). Mehrere Aktivitäten pro Plan,
Teilzuordnungen, manuell erledigte Pläne ohne Aufzeichnung und eine
datumsübergreifende Durchführung sind nicht modelliert. `plan.unplanned()`
verhindert nur, dass eine bereits vergebene Zeile zusätzlich als ungeplant
erscheint; es erzwingt keine globale Eindeutigkeit über mehrere Events.

### 5.3 Kanonische Zuordnung und Dedupe

`dedupe.py` erkennt Dubletten über Sportart, Startzeit ±300 s und mindestens
eine übereinstimmende Spur: Gesamtzeit ±300 s, Bewegungszeit ±120 s oder
(ähnliche Dauer und Distanz ±400 m) (`dedupe.py:27-39`, `:91-109`). Der
Gewinner wird nach Quelle/`device_name`/Feldzahl/Dauer bestimmt
(`dedupe.py:61-81`). `behalten()` entscheidet vor dem Schreiben
(`dedupe.py:155-163`), `delete_activities()` entfernt die Verlierer.

**Wichtig:** Es gibt keine Tabelle, die mehrere Quell-IDs auf eine dauerhafte
kanonische Aktivität abbildet. Nach dem Dedupe bleibt genau eine Zeile mit
ihrer `(source, source_id)` übrig; die andere Remote-ID ist verloren. Die
Aussage „mehrere Quellabbilder, bereits bestätigt kanonisch zugeordnet“ (F12)
ist im aktuellen Code **nicht** belegt und darf nicht als vorhanden
vorausgesetzt werden. `delete_unlisted()` kann zudem intervals-Zeilen
entfernen, bevor dedupliziert wird (`sync.py:65-70`).

## 6. Definitionen: Dauer, Belastung, Ist-Summen, Aktivitätstag, Zonen, Kurven

| Begriff | Tatsächliche Definition | Fundstelle |
|---|---|---|
| Ist-Dauer | `moving_s`, sonst `duration_s`, sonst 0. `duration_min = moving / 60`. „Mit Pausen“ ist separat `total_min` aus `duration_s` (falls abweichend). | `metrics.activity_payload()` (`metrics.py:605-631`), `plan.done_payload()` (`plan.py:490-501`), `UnitSheet.tsx:52-72`. |
| Plan-Dauer | Summe der `workout_doc`-Schrittsekunden; wenn leer, `event.duration_s`. Fehlende Distanz/Dauer wird aus dem eigenen Median der letzten 180 Tage geschätzt (`plan.speeds`, Fallback 24/8,6/2,6 km/h) und in der UI mit `≈` markiert. | `plan.planned()` (`plan.py:386-450`), `plan.estimate()` (`:365-383`), `SessionSheet.tsx:44-47`. |
| Belastung Ist | `activity.load` = `icu_training_load` aus intervals; bei Garmin-Direktaufzeichnungen `load.compute_load()` = `Stunden × Faktor × (Puls/160)²` (Lauf 75, Schwimmen 70). | `db.map_activity()` (`db.py:127-148`), `load.py:22-45`, `sources/garmin.py:136-155`. |
| Belastung Plan | `event.load` = `icu_training_load` des Events; der Planer berechnet keine eigene Last. | `db.map_event()` (`db.py:168-181`), `plan.session_row()` (`plan.py:556-572`). |
| Ist-Summen | `week_seconds` = Summe `moving_s`/`duration_s`; `week_sessions` = Anzahl der Zeilen aus `db.training_between()`; `week_load` = Summe `activity.load`. `db.training_between()` schließt `Workout` und `Transition` aus. | `metrics.py:785-795`, `:836-845`, `db.py:364-379`. |
| `/api/week`-Summen | Eigene, duplizierte Berechnung: `seconds` = Summe `moving_s`/`duration_s`, `load` = Summe `load`, Einheiten = `len(rows)`. | `api.py:105-119`. |
| Tatsächlicher Aktivitätstag | Erste 10 Zeichen von `start_date_local` (intervals) bzw. `startTimeLocal`, sonst `startTimeGMT` (Garmin). Keine UTC-Umrechnung. | `db.map_activity()` (`db.py:127-148`), `sources/garmin.py:129-145`. |
| Historische Zonen | `icu_hr_zone_times` (intervals) oder `hrTimeInZone_1…5` (Garmin) aus dem gespeicherten Roh-JSON; `zone_source` ist „intervals.icu“ bzw. „Garmin“. Keine Neuberechnung aus heutigen Profilzonen. | `metrics.zone_seconds()` (`metrics.py:645-658`), `unit_payload()` (`:661-702`), `UnitSheet.ZoneBar` (`UnitSheet.tsx:120-145`). |
| Planzonen | `sport_profile` aus intervals-Sport-Einstellungen (`max_hr`, `zones`, `ftp`, `indoor_ftp`); `_to_bpm`/`_to_watts` übersetzen für die Anzeige. Fallback `HR_ZONES` ist fest 1–7, wenn kein Profil vorliegt. | `plan.sport_profiles()` (`plan.py:70-85`), `_to_bpm()` (`:101-122`), `_to_watts()` (`:125-137`), `HR_ZONES` (`:62-63`). |
| `WeekStrip`-Balken | Tageslast (`series.load[].load`) der letzten sieben Tage; heutiger Tag akzentuiert, Spitzenwert neutral. **Keine** Umfangsbalken. | `WeekStrip.tsx:8-44`, `metrics.py:726-736`. |
| `WorkoutChart` (Ist) | Aufgezeichneter Verlauf: Hauptlinie Rad = Leistung (FTP-Referenzlinie), Lauf = Pace (Achse umgedreht, schneller oben), sonst Puls. Puls als zweite Linie bei Pace/Puls, **nicht** bei Leistung (zwei Skalen). Max. 180 Punkte, 5-s-Mittel. | `streams.payload()`/`_kind()` (`streams.py:178-253`), `WorkoutChart.tsx:14-132`, `:167-185`. |
| `SessionProfile` (Plan) | Geplante Blöcke: x = Minuten, y = Zielband (W, bpm oder %). „Arbeit“ = höchstes Band ≥95 % des Spitzenwerts, ohne Warmup/Cooldown. **Eine** Achse; gemischte Zielarten werden nicht als getrennte Spuren dargestellt. | `plan.parse_workout()` (`plan.py:281-359`), `SessionProfile.tsx:12-103`. |
| `SessionSheet` „Geplant · gemacht“ | Planwerte und `actual` aus `plan.matches()`; Ist-Dauer/-Distanz/-Last/-Intensität; optional Ist-Verlauf. | `SessionSheet.tsx:113-145`, `plan.session()` (`plan.py:537-553`). |

**Wichtige bestehende Grenzen der Planberechnung:**

- `plan._flatten()` schachtelt nur bis Tiefe 4, kappt Wiederholungen bei 30
  (`plan.py:235-261`). Das ist eine stille Darstellungsgrenze.
- `_target()` liest nur **ein** Ziel je Schritt, Priorität Leistung → HF →
  Pace (`plan.py:173-201`). Zusätzliche Ziele werden in der Anzeige nicht
  erhalten.
- `parse_workout()` wählt **eine** Achseneinheit (W vor bpm vor %) und
  ignoriert Bänder anderer Einheiten in der Achse (`plan.py:314-325`).
- Die Ende-Bedingung eines Schritts wird nicht als Typ erhalten. `planned()`
  summiert `seconds` und `distance_m` und leitet `primary` aus
  `event.distance_m` ab, nicht aus der tatsächlichen Schritt-Endbedingung
  (`plan.py:392-413`). Distanzschritte ohne Dauer erhalten `minutes = 0` und
  werden im `SessionProfile` über die Zeitachse nicht sinnvoll positioniert.
- Es gibt keinen Serializer, der die Rohstruktur beim Bearbeiten erhalten
  könnte.

## 7. Account, Athlet, Zeitzone, Authentifizierung, Persistenz, Cache, Hintergrund

| Thema | Tatsächlicher Befund |
|---|---|
| Account/Athlet | Einzelplatz, kein Multi-User. `INTERVALS_ATHLETE_ID` default `"0"` (`config.py:24-43`); `athlete()` liest den Key-Athleten. `sync` speichert `athlete_name`/`athlete_id` in `setting` (`sync.py:97-100`). Keine `account_id`/`athlete_id`-Spalten in `activity` oder `event`. |
| Authentifizierung intervals | HTTP Basic, Benutzer `API_KEY`, Passwort = API-Key (`sources/intervals.py:55-78`). Keine Zugangsdaten im Frontend. |
| Authentifizierung Garmin | Personal-API-Key; Bearer-Token-Cache unter `data/garmin/bearer-token.json` (`sync.py:150-153`, `sources/garmin.py:50-70`). |
| Authentifizierung Cockpit | Keine Anmeldung, keine Rollen, keine Account-Trennung. CORS nur `localhost:5173`/`127.0.0.1:5173` (`api.py:27-35`). |
| Zeitzone | Keine App-/Athletenzeitzone in `Settings`. Produktion setzt `TZ: Europe/Vienna` in `docker-compose.yml`; lokal gilt die Prozesszeitzone. `date.today()`/`datetime.now()` sind Prozess-lokal; `generated_at` nutzt `astimezone()`. Event-Tage kommen aus `start_date_local`, Aktivitätstage aus `startTimeLocal`. Das Frontend formatiert mit der Browserzeitzone (`format.ts:111-121`). **Kein gespeicherter Athleten-Zeitzonenwert.** |
| Lokale Persistenz | SQLite `data/cockpit.db` (`Settings.db_path`), WAL, Tabellen `activity`, `wellness`, `event`, `activity_stream`, `sync_run`, `setting` (`db.py:12-90`). Roh-JSON in `activity.raw`/`event.raw`. `data/` ist gitignored. |
| Browser-Persistenz | Keine `localStorage`, `sessionStorage`, `IndexedDB`-Nutzung. Keine Entwürfe, keine offenen Vorgänge, keine ausgewählte Woche über Reload. |
| Cache | Kein Frontend-Query-Cache. Serverseitig nur `lru_cache` für `Settings` (`api.py:38-40`) und der Garmin-Token-Cache. `activity_stream` verhindert wiederholte Stream-Abrufe. Kein HTTP-Cache, kein ETag, kein Service Worker. |
| Hintergrundaktualisierung | Keine. Sync nur manuell über Sidebar-Button (`Sidebar.tsx:45-48`) oder Pull-to-Refresh (`App.tsx:66-109`); `POST /api/sync` läuft synchron. Kein Scheduler/Cron, kein Polling, kein Refresh bei Tageswechsel. `ensure_db()` beim Start legt nur das Schema an (`cli.py:598-615`). |
| Fehler-/Leerzustände | `api.ts` wirft bei HTTP-Fehler; `App` zeigt Banner; `WeekSheet`/`UnitSheet`/`SessionSheet` zeigen eigene Fehlertexte. Keine getrennten Quellenzustände für Plan vs. Aktivität im Planer, da dieser noch nicht existiert. |

## 8. Verantwortlichkeit → tatsächliche Datei/Funktion → weiterverwenden/umbauen/entfernen

| Verantwortlichkeit | Tatsächliche Datei/Funktion | Entscheidung |
|---|---|---|
| App-Shell und Hauptnavigation | `web/src/App.tsx:19-27`, `:117-175`; `components/Sidebar.tsx`; `tabs.ts` | **weiterverwenden**, Tab-Liste erweitern. |
| Planer-Tab und Route | existiert nicht. `tabs.ts:3-9` hat nur `today`/`fuel`; `App.tsx:138-140` rendert nur `Today`/`Fuel`. | **neu in P07**; `IconList`/`IconTrends` sind vorhanden (`components/icons.tsx:24-42`). |
| Dashboard-Karte „Letzte 7 Tage“ | `Today.tsx:295-310`; `metrics.build_overview()` (`metrics.py:785-795`); `WeekStrip.tsx` | **weiterverwenden**, Kennzahlen und rollierendes Fenster unverändert lassen. |
| „Umfang“-Link | `Today.tsx:298-302` (`onClick`), `ui.tsx:75-82` (Button + Caret), `styles.css:1101-1122` | **umbauen/entfernen**: `onClick` entfernen, dadurch nicht mehr `<button>`, kein Caret, kein Tabstopp. |
| „Einheiten“-Link | `Today.tsx:304-308`, derselbe Handler | **umbauen/entfernen**: öffnet dieselbe alte Liste; `onClick` entfernen. |
| Karten-Wrapper | `Today.tsx:295` (`DashboardCard as="aside"`); `ui.tsx:6-36` | **weiterverwenden**; kein Wrapper-Handler vorhanden, nichts zu entfernen. |
| Alte Liste „Letzte 7 Tage“ | `components/WeekSheet.tsx:24-109`; `Sheet.tsx`; `WorkoutPreview.tsx` | **umbauen** zur Kalenderwoche; `Sheet`/`WorkoutPreview` weiterverwenden. |
| Sieben-Tage-Endpunkt | `api.py:105-119` `week()`; `db.py:371-379` `training_between()` | **umbauen** auf validierte Zeitraumparameter; `training_between()` weiterverwenden. |
| Planabfrage für die Woche | `db.py:468-473` `events_between()` | **weiterverwenden**; derzeit ungenutzt. |
| Tagesgruppen der alten Liste | `WeekSheet.tsx:60-68` (Gruppierung, `reverse()`), `:94-108` | **umbauen** auf Montag–Sonntag aufsteigend, leere Tage sichtbar. |
| Listensummen der alten Liste | `WeekSheet.tsx:77-90`; `api.py:112-118` | **umbauen** auf getrennte Ist-/Plan-Summen; eine gemeinsame Ist-Summenfunktion statt Duplikat. |
| Aktivitätskarte | `components/WorkoutPreview.tsx`; `Today.tsx:359-388` | **weiterverwenden**; für geplante Einträge ggf. parallel eine Plan-Variante. |
| Aktivitätsdetails | `components/UnitSheet.tsx:21-145`; `/api/unit/{row_id}` (`api.py:122-131`); `metrics.unit_payload()` (`metrics.py:661-702`) | **weiterverwenden**, unverändert lassen; kein zweiter Detailstack. |
| Aktivitätsdiagramm | `components/WorkoutChart.tsx`; `streams.payload()` (`streams.py:178-253`) | **weiterverwenden**; nicht durch Planbalken ersetzen. |
| Zonenbalken/details | `UnitSheet.tsx:120-145`; `metrics.zone_seconds()` | **weiterverwenden**; historische Zonen nicht neu berechnen. |
| Aktivitätenliste | `pages/Activities.tsx`, `components/ActivityTable.tsx` | **nicht mounten/entfernen**: per D-38 abgehängt, kein Planerersatz. |
| Planungsdetails | `components/SessionSheet.tsx:14-149`; `/api/session/{event_id}` (`api.py:84-93`); `plan.session()` | **weiterverwenden/umbauen**: Leseansicht bleibt, Editor kommt in P10–P16 hinzu. |
| Planungsgraph | `components/SessionProfile.tsx`; `plan.parse_workout()` | **umbauen** für gemischte Spuren und Distanzachsen; aktuelle Ein-Achsen-Logik reicht nicht. |
| Plan-Parser | `plan.py:173-359` (`_target`, `_flatten`, `parse_workout`) | **umbauen/erweitern**; Erhaltungs- und Editierbarkeitsregeln fehlen. |
| Plan-/Ist-Zuordnung | `plan.py:467-487` (`matches`), `:504-521` (`unplanned`), `:556-572` (`session_row`) | **umbauen/ersetzen** durch belegte Beziehung; Heuristik nicht als Bestätigung ausgeben. |
| Event-Sync (lesen) | `sync.py:44-45`, `:83`; `db.upsert_events()` (`db.py:326-350`) | **weiterverwenden**, aber Event-Löschungen/Abgleich und Identität ergänzen. |
| Event-Schreiben | `sources/intervals.py:198-219` (`upsert_events`, `create_event`, `delete_events`); `cli.py:404-448` (`push-test`) | **weiterverwenden als Clientbasis**; Produkt-Writer/Update fehlt vollständig. |
| Aktivitäts-Sync | `sync.py:44`, `:65-76`; `db.upsert_activities()`; `sources/garmin.py:115-176` | **weiterverwenden**. |
| Dedupe | `dedupe.py:27-163`; `sync.dubletten_entfernen()` | **weiterverwenden**, aber fehlende kanonische Mehrquellen-Zuordnung dokumentieren. |
| Verläufe | `streams.py:24-370`; `db.upsert_stream()`; `activity_stream` | **weiterverwenden**; 14-Tage-Grenze für ältere Details beachten. |
| Ist-Summen | `metrics.py:785-795`, `:836-845`; `api.py:112-118` | **umbauen**: eine gemeinsame, dokumentierte Summenfunktion; keine zweite Formel. |
| Account/Athlet | `config.py:24-43`; `sync.py:97-100`; `db.setting` | **weiterverwenden**, aber Single-User-Grenze und fehlende Account-Trennung dokumentieren. |
| Zeitzone | `docker-compose.yml` (`TZ: Europe/Vienna`); `date.today()` in `api.py:109`, `metrics.py:709`, `sync.py:32`; `format.ts:111-121` | **umbauen/klären**: explizite App-/Athletenzeitzone in P03; nicht Browser-UTC als Standard. |
| Persistenz | `config.py:45-51` (`db_path`); `db.py:12-122` | **weiterverwenden**; Entwurfs-/Vorgangspersistenz fehlt und kommt in P22. |
| Cache/Refresh | `App.tsx:28-42` (`load`), `api.ts`; kein Query-Cache | **weiterverwenden für den ersten Stand**; getrennte Quellenzustände und gezielte Invalidierung in P06/P23 ergänzen. |
| Theme/Tokens | `styles.css:45-142`; `DESIGN.md` Abschnitt 10 | **weiterverwenden**; keine neuen Tokens ohne D-xx. |
| Tests | `tests/test_api.py:150-213` (week/unit), `tests/test_plan.py` (Schritte, Schätzung, Matching), `tests/test_streams.py`, `tests/test_dedupe.py`, `tests/test_sync.py` | **weiterverwenden/ergänzen**; keine Frontend-Tests vorhanden. |
| Referenzbilder | `docs/trainingsplaner/references/*.png`; `prototype/Trainingsplaner-Referenz.html` | **weiterverwenden** für die visuelle Abnahme P07–P09. |

## 9. Offene Quellgrenzen (konkret, nicht erfunden)

1. **Keine explizite Plan-/Aktivitätsbeziehung.** Vorhanden ist nur
   `plan.matches()` (Tag + Sportfamilie + nächste Dauer). Das ist kein
   bestätigter Abschluss und keine Datumsübergangs-Beziehung.
2. **Kein Produkt-Schreibweg für Planungen.** Kein Editor, kein API-Mutations-
   endpunkt, kein `PUT`-Update, kein Serializer, keine Konflikterkennung.
3. **Kein Planer-Tab und keine Route.** `TABS` enthält nur Heute/Verpflegung;
   es gibt keinen Router und keine URL-Auswertung. Die alte Liste ist ein
   Overlay.
4. **Keine alte Listen-URL.** Deshalb ist eine „Kompatibilitätsweiterleitung“
   heute gegenstandslos; sie kann erst mit der in P07 neu geschaffenen Route
   definiert werden.
5. **Zeitzone nicht explizit gespeichert.** Produktion nutzt `TZ=Europe/Vienna`
   aus Compose; Python nutzt die Prozesszeit, der Browser seine eigene Zeitzone.
   Eine Athletenzeitzone wird nicht persistiert. P03 muss den Standard
   festlegen, bevor Kalenderwochen berechnet werden.
6. **Single-User ohne Account-Trennung.** `INTERVALS_ATHLETE_ID=0`, keine
   Account-/Athletenspalten in `activity`/`event`, keine App-Authentifizierung.
   Mehrkonto-Cache/Entwürfe sind nicht vorbereitet.
7. **Keine kanonische Mehrquellen-Zuordnung.** `(source, source_id)` ist die
   einzige Identität; Dedupe löscht den Verlierer. Eine bestätigte Zuordnung
   mehrerer Quell-IDs auf dieselbe Aktivität existiert nicht.
8. **Keine Vorgangs-/Entwurfspersistenz.** Kein Browser-Speicher, keine
   Operations-ID, kein Wiederaufsetzen nach Reload.
9. **Event-Abgleich unvollständig.** `db.upsert_events()` schreibt nur; es gibt
   kein `delete_unlisted` für Events. Remote gelöschte Events bleiben lokal.
   `db.upcoming_events()` filtert zudem nicht auf `category = WORKOUT`
   (`db.py:476-481`).
10. **Plan-Parser ist verlustbehaftet für die neue Aufgabe.** Tiefe 4,
    Wiederholungsdeckel 30, ein Ziel je Schritt, eine Achseneinheit, keine
    Ende-Bedingung als Typ, keine Distanz-Zeit-Achse, kein Erhalt beim
    Bearbeiten. Das ist für P04/P05/P09 eine Umbauaufgabe.
11. **Verläufe nur 14 Tage.** Ältere Aktivitäten können ohne `series` sein;
    `UnitSheet` zeigt dann keinen Verlauf, ohne einen Verfügbarkeitshinweis.
12. **Sync-Zeitraum standardmäßig 365 Tage.** Ältere Wochen sind ohne
    erweiterten Sync nicht in der DB. Garmin kappt bei 1000 Aktivitäten pro
    Abruf. Kein Beleg für Vollhistorie.
13. **Arbeitsdatenbank leer.** 0 Aktivitäten/0 Events; reale Abdeckung und
    echte `event.raw`-Felder (z. B. eine mögliche Remote-Beziehung) sind hier
    nicht prüfbar. E-01 dokumentiert den früheren Bestand, nicht diese Kopie.
14. **Kein Hintergrund-Sync, kein Cache, kein Tageswechsel-Refresh.** Nur
    manueller Sync/Reload; `data` liegt im React-State.
15. **Keine Frontend-Tests.** `npm run build` prüft Typen und Build, nicht
    Interaktion, Fokus, Diagramme oder Navigation.
16. **`Activities`-Seite ist toter UI-Code.** Sie ist per D-38 abgehängt und
    darf nicht als zweite Historienliste wiederverwendet werden.

## 10. Nächster einzelner Arbeitsschritt

**P01 — Referenzfälle und Fähigkeitsmatrix anlegen.** Konkret:

- F01–F15 als fachliche Fixtures im vorhandenen pytest-System anlegen, ohne
  Produktivdaten zu überschreiben;
- die acht Bildreferenzen und den Prototyp als visuellen Maßstab referenzieren;
- die Fähigkeitsmatrix aus Plan Abschnitt 8.4 mit dem tatsächlichen Adapter
  füllen: belegt / offen / nicht unterstützt;
- für jede offene Schreibfähigkeit den fehlenden Nachweis benennen
  (insbesondere gezieltes Event-Update, absolute bpm, Editorgruppierung);
- Historienfälle für explizite Beziehung, ungeplante Aktivität, Krafttraining,
  ältere Daten und Quellausfall abbilden.

Kein Produktcode in P01; keine erfundene Beziehung und keine erfundene
API-Fähigkeit.

## 11. P00-Abnahme

- [x] Framework, Sprache, Paketmanager, Router, State, API-Schicht,
  UI-Komponenten, Tokenort, Tests und Prüfbefehle sind mit tatsächlichen
  Pfaden belegt.
- [x] Der Weg einer geplanten Einheit (Lesen/Anzeigen) und der Weg einer
  Aufzeichnung bis zu den Aktivitätsdetails ist verfolgt.
- [x] Bearbeiten und Remote-Antwort sind als **fehlend** dokumentiert, nicht
  als vorhanden behauptet.
- [x] Dashboard-Karte, „Umfang“/„Einheiten“-Handler, Chevron, Karten-Wrapper,
  Tabs, alte Liste und fehlende Planerroute sind mit Datei/Funktion benannt.
- [x] Die Sieben-Tage-Grenze ist auf `GET /api/week` zurückgeführt; UI,
  Speicherung, Sync und Verläufe sind getrennt bewertet.
- [x] Die kleinste Änderung für gezielt ältere Wochen ist benannt.
- [x] Vorhandene Identitäten, Dedupe und die fehlende explizite
  Plan-/Aktivitätsbeziehung sind dokumentiert.
- [x] Dauer, Belastung, Ist-Summen, Aktivitätstag, historische Zonen und die
  Bedeutung der Diagrammkurven sind aus der Datenbindung abgeleitet.
- [x] Account/Athlet, Zeitzone, Authentifizierung, Persistenz, Cache und
  Hintergrundaktualisierung sind identifiziert.
- [x] Der Ausgangsstand von Tests, Build und Lint ist dokumentiert; bestehende
  Fehler sind von P00 verursachten unterschieden.
- [x] Alle acht PNGs und der Prototyp sind vorhanden und lesbar.
- [x] Keine Produktcode-Änderung, keine Datenbankänderung, keine Zugangsdaten
  ausgegeben.

---

# Trainingsplaner — Arbeitsnachweis P01

**Stand:** 06.11.2026  
**Paket:** P01 — Referenzfälle und Fähigkeitsmatrix anlegen  
**Basis:** Branch `feature/trainingsplaner`, HEAD `33e5457`  
**Umfang:** Testdaten und Matrix. Keine Produktcode-Änderung, keine
Datenbankänderung, kein Netzwerkaufruf.

## 1. Ergebnis

- F01–F15 liegen als fachliche JSON-Fixtures in
  `tests/fixtures/planner/cases/`. Jeder Fall trägt seine Erwartung
  ausdrücklich; die Tests summieren die Werte nicht aus zufälligen
  Nutzertrainings.
- Vier anonymisierte Remote-Beispiele liegen in
  `tests/fixtures/planner/remote/`: einfache Zone-2-Einheit, Wiederholung,
  Distanzabschnitt mit zusätzlicher geschätzter Dauer und ein Import mit
  unbekanntem Inhalt (Rampe, Trittfrequenz, Lap-Taste, Zusatzfelder).
- `tests/fixtures/planner/profiles.json` hält Lauf-, Rad- und Schwimmprofil
  separat. HF-, Pace- und Leistungszonen haben explizite String-IDs,
  Referenzwerte und Grenzen; `ride-power-sweetspot` ist bewusst nichtnumerisch.
- `tests/fixtures/planner/capability-matrix.json` und
  `docs/trainingsplaner/FAEHIGKEITSMATRIX.md` bilden Abschnitt 8.4 mit dem
  tatsächlichen Adapterbefund ab. Jede offene Schreibfähigkeit nennt den
  fehlenden Nachweis.
- Historienfälle F11–F15 sind getrennt abgebildet: Dashboard-Zeitraum versus
  Planerwoche, bestätigte und offene Beziehung mit gleicher numerischer ID,
  Durchführung außerhalb der Planwoche, Pagination/Quellausfall sowie
  Aktivitätsdetails mit Krafttraining und weiteren Sportarten.

## 2. Geänderte Dateien

- `tests/fixtures/planner/README.md` — Format, Anonymisierung und Grenzen.
- `tests/fixtures/planner/profiles.json` — synthetische Sportprofile.
- `tests/fixtures/planner/cases/f01…f15-*.json` — fachliche Fälle.
- `tests/fixtures/planner/remote/*.json` — anonymisierte Remote-Beispiele.
- `tests/fixtures/planner/capability-matrix.json` — Matrix, maschinenlesbar.
- `docs/trainingsplaner/FAEHIGKEITSMATRIX.md` — Matrix mit Befund und
  fehlenden Nachweisen.
- `tests/planner_fixtures.py` — Loader, kein Produktivpfad.
- `tests/test_planner_fixtures.py` — Vollständigkeit, Erwartungen,
  Anonymisierung, Profile und Matrix.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_fixtures.py -q` | **28 passed** |
| `UV_CACHE_DIR=.uv-cache uv run ruff check tests/test_planner_fixtures.py tests/planner_fixtures.py` | ohne Befund |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **176 passed**, 1 bestehende Starlette-Warnung; keine P01-Regression |

Die Matrix behauptet keine Fähigkeit, die nur aus der öffentlichen
Dokumentation stammt. `PUT /events/{id}` ist ausdrücklich **offen**, weil der
vorhandene Client sie nicht implementiert; absolute bpm, Leistungszonen und
benutzerdefinierte Zonen bleiben ohne belegten Schreibvertrag gesperrt.

## 4. Offene Punkte

- Die F12-Variante „mehrere Quellabbilder, bereits kanonisch zugeordnet“ ist
  im Bestand nicht belegbar; sie bleibt Fixture-Erwartung für P02/P06 und
  keine Behauptung über die vorhandene Datenbank.
- Ein Remote-Beispiel für F05 (Schwimmen) fehlt bewusst; der Fall ist
  fachlich beschrieben, nicht als Adapterbeleg ausgegeben.
- Ob intervals.icu `workout_doc` jemals als Schreibfeld akzeptiert, ist nicht
  geprüft. Der Plan behandelt es als Lesemodell.

## 5. Nächstes Paket

**P02 — Fachmodell und Identitäten ergänzen.** Das Modell muss F01–F07 ohne
UI und Netzwerk darstellen, unbekannte Knoten erhalten, Plan- und
Aktivitätsidentitäten trennen und den Schreibkoordinator auf geplante
Entwürfe begrenzen.

---

# Trainingsplaner — Arbeitsnachweis P02

**Stand:** 06.11.2026  
**Paket:** P02 — Fachmodell und Identitäten ergänzen  
**Basis:** Branch `feature/trainingsplaner`, HEAD `d5c3c8c`  
**Umfang:** Neues UI-unabhängiges Modellpaket `trainings_cockpit.planner`.
Keine Datenbankmigration, kein API-Endpunkt, kein Netzwerkaufruf, keine
Produktivdaten.

## 1. Ergebnis

- `identities.py` trennt `PlanId`, `RemoteEventId`, `ActivityId`, `DraftId`,
  `OperationId`, `RelationshipId` und `NodeId` als eigene Typen. `PlanReference`
  und `ActivityReference` tragen Account und Athlet; gleiche numerische IDs
  erzeugen verschiedene Cache-/Listenschlüssel.
- `model.py` bildet den Aufbau aus Abschnitt 4.2 ab: Zeit in Sekunden, Distanz
  in Metern, Ziele mit expliziter Einheit, Zonen als String-ID samt Zonenmodell,
  Rollen, Wiederholungen, unbekannte Knoten mit Quellreferenz. `0 W` bleibt
  eine gültige Vorgabe, ein Distanzabschnitt bleibt `DistanceEnd`.
- `Editability` kennt `full`, `metadataOnly`, `readOnly`; eingeschränkte
  Planungen brauchen einen konkreten Grund. `RestrictionCode` benennt
  unbekannten Inhalt, mehrere Ziele, Spezialschritte, fehlende Rechte.
- `SourceSnapshot` erhält den vollständigen Remote-Inhalt und den
  Workout-Text; `content_hash()` ist stabil. `WorkoutDraft` trennt Basis,
  Basissnapshot, aktuellen Stand, Feldpuffer, Auswahl und lokale Revision.
- `projections.py` ergänzt `TrainingRange` und die vier typisierten
  Listeneinträge `planned`, `recorded`, `linked`, `completionReference`.
  `completionReference` trägt keine Ist-Kennzahlen und keine Dauer.
  `TrainingRelationship` trennt Beziehung und bestätigten Abschluss.
- `write.py` zieht die Grenze im Typsystem (`WorkoutDraft`) **und** zur
  Laufzeit (`require_planned_draft` / `WriteCoordinator`). Eine
  `ActivityReference`, ein Dict oder ein blankes `PlannedWorkout` wird
  abgewiesen, bevor ein Writer aufgerufen wird.
- Das vorhandene Aktivitätsmodell in `db.py`/`metrics.py` bleibt unverändert.
  Der F15-Test liest ein Krafttraining weiterhin über `db.training_between`
  und `metrics.unit_payload`.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/__init__.py` — öffentliche Exporte.
- `src/trainings_cockpit/planner/primitives.py` — lokale Datums-, Zeit- und
  Zeitzonenvalidierung.
- `src/trainings_cockpit/planner/identities.py` — typisierte IDs und
  Referenzen.
- `src/trainings_cockpit/planner/model.py` — Planungsmodell, Snapshot,
  Feldpuffer, Entwurf, Verschieben.
- `src/trainings_cockpit/planner/projections.py` — `TrainingRange`,
  Listeneinträge, Beziehung.
- `src/trainings_cockpit/planner/write.py` — Schreibgrenze.
- `tests/planner_fixtures.py` — baut P02-Modelle aus den P01-Fixtures.
- `tests/test_planner_model.py` — F01–F07, F12/F13, Identitäten, Verschieben,
  Feldpuffer und Schreibgrenze.
- `tests/fixtures/planner/cases/f06-empty-workouts.json` — Wiederholung des
  Nur-Erholungs-Falls auf 1 gesetzt, damit der Fall wie spezifiziert **null**
  ausgeführte Abschnitte hat.
- `docs/ENTSCHEIDUNGEN.md` — D-69.
- `docs/training-planner-progress.md` — dieser Nachweis.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_model.py -q` | **19 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **195 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/planner tests/planner_fixtures.py tests/test_planner_fixtures.py tests/test_planner_model.py` | ohne Befund |
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich; keine UI-Änderung |

Die Modelltests brauchen weder UI noch Netzwerk. F01–F07 werden aus den
P01-Fixtures gebaut; F12/F13 werden mit getrennten Plan- und
Aktivitätsreferenzen geprüft. F06 wird nur **dargestellt**; die
Speicherverweigerung selbst gehört zu P05/P17 und ist hier nicht vorweggenommen.

## 4. Offene Punkte

- Der Remote-Adapter fehlt weiterhin: P04 muss `workout_doc.steps` auf
  `WorkoutNode` abbilden und die Ende-Bedingung aus dem Quellvertrag
  feststellen.
- Die gemeinsame Ausführungsfolge und Summenberechnung (inklusive
  `skipFinalRecovery`) folgt in P05. Die Tests zählen F01–F06 nur lokal, um
  die Modellvollständigkeit zu belegen.
- Eine projektive Funktion, die aus realen P06-Daten `TrainingListEntry`s
  erzeugt, folgt mit P06/P07. P02 liefert die Typen und die Identitätsgrenze.
- `completionReference` wird derzeit durch den Aufrufer nur dann erzeugt, wenn
  die Beziehung nachweislich abgeschlossen ist; die Projektionsfunktion in
  P06 muss diese Bedingung zentral erzwingen.
- Keine Frontend-Typen in P02: Die API-Form entsteht mit P06/P07, damit keine
  zweite, unbenutzte Quelle der Wahrheit gepflegt wird.

## 5. Nächstes Paket

**P03 — Wochen- und Datumsfunktionen absichern.** Sieben lokale Tage,
Monats-/Jahreswechsel, beide Zeitumstellungen und die Trennung von
rollierendem Dashboard-Zeitraum und Kalenderwoche.

---

# Trainingsplaner — Arbeitsnachweis P03

**Stand:** 06.11.2026
**Paket:** P03 — Wochen- und Datumsfunktionen absichern
**Basis:** Branch `feature/trainingsplaner`, HEAD `7ba7fcc`
**Umfang:** Neues UI-unabhängiges Datumsmodul `trainings_cockpit.planner.dates`.
Keine Datenbankmigration, kein API-Endpunkt, keine UI-Änderung.

## 1. Ergebnis

- Eine Woche ist ein lokales Montagsdatum plus sechs Kalendertage. Der Sonntag
  bleibt in seiner Woche; Monats- und Jahreswechsel sowie beide
  Europe/Vienna-Zeitumstellungen erzeugen weiterhin genau sieben Tage.
- `rolling_dashboard_range()` (heute plus sechs Tage) und
  `planner_week_range()` (Montag bis Sonntag) sind getrennte
  `TrainingRange`-Verträge. Die Dashboard-Zahl wird nicht aus der Planerwoche
  abgeleitet.
- `parse_week_parameter()` validiert einen lokalen API-Wert und normalisiert
  ihn auf Montag; ein leerer Parameter kommt aus der Laufzeit, ein gesetzter
  Wert niemals aus einem festen Demotag.
- `PlannedWorkout.reschedule()` und `reschedule_plan()` ändern nur das lokale
  Datum. Lokale Uhrzeit, Zeitzone, Remote-ID und Knoten-IDs bleiben erhalten.
- Die Zeitzone ist explizit (`DEFAULT_TIME_ZONE`, `Settings.time_zone`,
  `TC_TIME_ZONE`); die Prozesszeitzone entscheidet nicht still mit (D-70).

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/dates.py` — Wochen, Tage, Zeiträume,
  Wochenparameter, Beschriftung, Verschieben.
- `src/trainings_cockpit/planner/model.py` — `reschedule()`.
- `src/trainings_cockpit/config.py`, `.env.example` — explizite Zeitzone.
- `src/trainings_cockpit/planner/__init__.py` — Exporte.
- `tests/test_planner_dates.py` — Sonntag, Monats-/Jahreswechsel, beide
  Zeitumstellungen, F08/F11/F13-Zeiträume, Verschieben.
- `docs/ENTSCHEIDUNGEN.md` — D-70.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_dates.py -q` | **10 passed** |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/planner tests/test_planner_dates.py src/trainings_cockpit/config.py` | ohne Befund |

## 4. Offene Punkte

- P03 liefert die Zeitraumfunktionen, noch keine Wochen-API. Die Anbindung der
  Abfrage und der Ladezustände bleibt P06; Tab und Route bleiben P07.
- Die UI-Form der Wochenbeschriftung wird erst in P07 sichtbar geprüft.

## 5. Nächstes Paket

**P04 — Remote-Leseadapter und Erhaltungsregeln.**

---

# Trainingsplaner — Arbeitsnachweis P04

**Stand:** 06.11.2026
**Paket:** P04 — Remote-Leseadapter und Erhaltungsregeln
**Basis:** Branch `feature/trainingsplaner`, HEAD `3d21107`
**Umfang:** Neues Lesemodul `trainings_cockpit.planner.remote`, Ergänzung der
Beziehungsprojektion. Kein Netzwerkaufruf, kein Schreibpfad, keine UI.

## 1. Ergebnis

- `read_remote_event()` liest Event-ID, Name, Sport, lokalen Termin, Aufbau und
  Notizen aus dem vorhandenen Event-Rohdatenpfad und legt das vollständige
  Event-Dict unverändert in `SourceSnapshot.raw` ab.
- Distanz plus berechnete Dauer bleibt ein Distanzabschnitt, wenn die Quelle
  die Dauer als Schätzung kennzeichnet (`duration_source=estimated`, F04).
  Ohne eindeutige Quellenangabe wird der Schritt als unbekannt erhalten, statt
  die Ende-Bedingung zu raten.
- Rampen, Lap-Tasten, Trittfrequenz, Zusatzanweisungen und mehrere Ziele werden
  als `UnsupportedNode` mit Quellreferenz erhalten. Sie begrenzen die
  Editierbarkeit auf `metadataOnly`; der Rohinhalt bleibt vollständig.
- Fehlende Remote-Schreibrechte (`writable=False`, `read_only`) ergeben
  `readOnly`. Unbekannte Sportarten bleiben mit ihrem Rohcode erhalten und
  erhalten ein neutrales Label, statt den Tag abzubrechen. Fehlgeleitete
  Zonenwerte werden ebenfalls als unbekannter Knoten erhalten, statt den
  ganzen Import abzubrechen.
- Aufzeichnungen werden ausschließlich über
  `activity_reference_from_record()` / `recorded_entry_from_record()` auf den
  vorhandenen Aktivitätspfad verwiesen. `NotAPlannedWorkout` weist
  Nicht-WORKOUT-Events ab; eine Aktivität wird nie als `PlannedWorkout`
  dekodiert.
- `relationship_entries()` übernimmt nur bestätigte Beziehungen in die
  Anzeigeprojektion. Mehrere Aktivitäten bleiben tagesgetrennt; eine
  `completionReference` entsteht nur am abweichenden Plantermin ohne eigene
  Ist-Werte. Offene/teilweise Beziehungen erzeugen keinen Erledigt-Eintrag.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/remote.py` — Eventleser, Erhaltungsregeln,
  Aktivitätsbrücke, neutrales Sportlabel.
- `src/trainings_cockpit/planner/projections.py` — `relationship_entries()`,
  `RelationshipProjectionError`.
- `src/trainings_cockpit/planner/__init__.py` — Exporte.
- `tests/test_planner_remote.py` — F01/F02/F04/F07, unbekannte Sportart,
  Schreibrecht, Aktivitätspfad, F12/F13-Beziehungen.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_remote.py -q` | **12 passed** |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/planner/remote.py src/trainings_cockpit/planner/projections.py tests/test_planner_remote.py` | ohne Befund |

## 4. Offene Punkte

- Der Adapter liest nur. Ein Serializer, ein gezieltes Event-Update und die
  Konflikterkennung bleiben P17/P18; die Fähigkeitsmatrix bleibt für
  Schreibfähigkeiten deshalb offen.
- Absolute bpm- und Prozent-HF-Ziele ohne belegte Zonenreferenz werden bewusst
  nicht in eine scheinbar sichere Struktur übersetzt.
- Die F12-Variante mit mehreren Quellabbildern derselben kanonischen Aktivität
  bleibt eine Fixture-Erwartung; der Bestand hat keine dauerhafte
  Mehrquellen-Zuordnung.

## 5. Nächstes Paket

**P05 — Gemeinsame Validierung, Ausführungsfolge und Summen.**

---

# Trainingsplaner — Arbeitsnachweis P05

**Stand:** 06.11.2026
**Paket:** P05 — Gemeinsame Validierung, Ausführungsfolge und Summen
**Basis:** Branch `feature/trainingsplaner`, HEAD `3d21107`
**Umfang:** Neues Modul `planner/validation.py`, neues Modul
`planner/summaries.py`, gemeinsame Ist-Dauer in `metrics.py`, `api.py` und
`plan.py`. Keine UI-Änderung, keine neue Trainingslast.

## 1. Ergebnis

- Gemeinsame Parser für Dauer, Distanz, Dezimalzahlen, Pace, Pacebereiche und
  Wertebereiche. Leer ist `incomplete`, unlesbar `invalid`; `0` bleibt ein
  gültiger Wert, `0 W` ist nicht „Ohne Ziel“.
- Feldvalidierung (`parse_field_input`) und Workoutvalidierung
  (`validate_workout`/`validate_draft`) sind getrennt. Struktur- und
  Metadatenmodus unterscheiden unbekannte Inhalte von einer sicheren
  Namensänderung.
- Die Ausführungsfolge trägt Knoten-ID, Gruppen-ID, Wiederholungsindex,
  Wiederholungspfad und Position. `skip_final_recovery` wirkt genau einmal in
  der letzten Wiederholung. Große Wiederholungszahlen werden für Summen
  algebraisch gerechnet und für die Darstellung mit einer ausdrücklichen
  `ExecutionCompression` begrenzt.
- F01–F06 liefern 45/36/65/28+4/800 m+4 min/0 Ausführungen. F06 wird in allen
  drei Formen von der Workoutvalidierung und der Schreibgrenze abgewiesen.
- `KnownTotals` mischt keine Schätzung unter. Die Formatierung rundet erst an
  der Anzeigegrenze; F04 bleibt `28 min + 4 km`, F05 `800 m + 4 min`.
- Die bestehende Ist-Dauer (`moving_s`, sonst `duration_s`) liegt jetzt zentral
  in `recorded_seconds()` und wird von Dashboard, `/api/week`, Tageskarte und
  den neuen Summen verwendet. Eindeutige Aktivitäten zählen nach ihrem
  tatsächlichen Datum einmal; offene Planung ist eine getrennte Ableitung.
- F12: `relationship_actuals()` ergibt 42 Minuten / Last 40 / eine Aktivität;
  `open_plan_totals()` ergibt separat 30 Minuten. F13 zählt die Aufzeichnung
  nur in der Woche 09.–15.11., der Plan bleibt am 08.11. mit
  „Erledigt am 9. November“ erreichbar.
- Die zusätzliche Aufzeichnung A2 aus der F12-Fixture bleibt als eigene
  Aktivität sichtbar (und zählt bei vollständiger Wochensumme mit); die
  F12-Abnahme „42 Minuten“ ist die Summe der bestätigten Beziehung, nicht eine
  stillschweigend gelöschte ungeplante Aufzeichnung.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/validation.py` — Parser, Validierung,
  Ausführungsfolge, bekannte Mengen, Formatierung.
- `src/trainings_cockpit/planner/summaries.py` — Ist-Summen, offene Planung,
  Wochenzusammenfassung und gemeinsame Listenprojektion.
- `src/trainings_cockpit/planner/write.py` — Workoutvalidierung an der
  Schreibgrenze.
- `src/trainings_cockpit/planner/__init__.py` — Exporte.
- `src/trainings_cockpit/metrics.py`, `api.py`, `plan.py` — gemeinsame
  Ist-Dauerdefinition statt vier lokaler Formeln.
- `tests/test_planner_validation.py` — Parser, F01–F07, F11–F13,
  Großwiederholung, Präzision, leere Woche.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_validation.py -q` | **20 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **237 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/planner tests/test_planner_validation.py` | ohne Befund |
| `npm run build --prefix web` | keine UI-Änderung; Build bleibt unberührt |

## 4. Offene Punkte

- Die Wochenabfrage mit echten P06-Daten, Lade-/Fehlerzuständen und
  Cache-Schlüsseln fehlt weiterhin. `summaries.py` ist die reine Fachlogik
  dafür, keine Datenbank- oder HTTP-Schicht.
- `open_plan_totals()` kennzeichnet unbekannte Aufbauinhalte; fehlende
  Quellenabdeckung einer ganzen Woche wird erst in P06 als Ladezustand
  ausgewiesen.
- Die F12-Aufzeichnung A2 bleibt zusätzlich sichtbar; die Beziehungssumme und
  die vollständige Wochensumme sind bewusst zwei getrennte Aussagen.
- Der Graph selbst (`buildWorkoutProfileData`) und die Inline-Editor-Anbindung
  folgen in P08/P09; P05 liefert die gemeinsame Ausführungsfolge und
  Formatierung.

## 5. Nächstes Paket

**P06 — Wochenabfrage und Cache an die vorhandene Datenstrecke anbinden.**

---

# Trainingsplaner — Arbeitsnachweis P06

**Stand:** 06.11.2026
**Paket:** P06 — Wochenabfrage und Cache an die vorhandene Datenstrecke anbinden
**Basis:** Branch `feature/trainingsplaner`, HEAD `1bcf35a`
**Umfang:** Neue Wochenabfrage `GET /api/planner` und Zeitraumparameter am
bestehenden `GET /api/week`, getrennte Quellenzustände in
`planner/week.py`, Sync-Bereichsmarke. Keine UI-Änderung in diesem Paket.

## 1. Ergebnis

- `GET /api/planner?week=JJJJ-MM-TT` liefert genau sieben lokale Tage
  Montag–Sonntag, den vollständigen Wochenzeitraum, Kalenderwoche und die
  gemeinsame Anzeigeprojektion. `GET /api/planner/week` ist derselbe Vertrag
  für ausdrückliche Verlinkungen.
- `/api/week` bleibt ohne Parameter die bisherige rollierende
  Sieben-Tage-Antwort. Mit `week`, `from`/`to` liefert derselbe Leseweg einen
  gezielten Zeitraum. Damit ist die in P00 gefundene feste
  `today - 6`-Grenze parametrisiert; die Datenbankabfrage selbst war nie auf
  sieben Tage begrenzt.
- Planungen (`db.events_between`) und Aufzeichnungen
  (`db.training_between`) werden getrennt gelesen und getrennt gemeldet.
  Zustände: `complete`, `empty`, `partial`, `error`, `unavailable`; die UI
  ergänzt `loading`. Ein Fehler der einen Quelle liefert die andere weiter.
- Eine Woche außerhalb der zuletzt vom Sync nachweislich gelesenen Grenzen
  wird nicht als bestätigt leer ausgegeben (`synced_range` mit getrennten
  Grenzen für Aktivitäten und Events). Ohne Marke bleibt der lokale Bestand
  maßgeblich; das ist kein erfundener Historienanspruch.
- Cache-/Query-Schlüssel enthalten Objekttyp/Quelle, Account/Athlet,
  Zeitzone und Zeitraumgrenzen. Die Wochenprojektion
  (`planner:...:projection:week`) ist vom rollierenden Dashboard-Schlüssel
  (`dashboard:...:projection:rolling`) getrennt.
- Die Anzeigeprojektion nutzt `TrainingListEntry` und die bestätigte
  Beziehung aus P05. Beziehungen werden nur aus dem ausdrücklich übergebenen
  Vertrag gebildet, nie aus gleichem Tag, Namen oder gleicher Dauer. Für den
  aktuellen Bestand existiert keine persistierte explizite Beziehung; die
  Wochenansicht zeigt deshalb Plan und Aufzeichnung getrennt.
- Offene Planung und Ist-Summe bleiben getrennt. Bekannte Dauern und
  Distanzen kommen aus dem P04/P05-Modell; geschätzte Hälften zählen nicht in
  die Summe. `has_unknown` kennzeichnet fehlende Vorgaben.
- Die weiterhin benötigte Dashboard-Aggregation liest unverändert
  `metrics.build_overview()` mit ihrem eigenen rollierenden Fenster. Sie ist
  nicht an die gewählte Planerwoche gekoppelt.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/week.py` — Wochenprojektion, Quellenzustände,
  Query-Schlüssel, bekannte Planmengen, Beziehungs-Serialisierung.
- `src/trainings_cockpit/api.py` — `/api/planner`, `/api/planner/week`,
  Zeitraumparameter an `/api/week`, Athletenzeitzone für Overview und Woche.
- `src/trainings_cockpit/sync.py` — `synced_range` als Abdeckungsmarke nach
  erfolgreichem Lesen.
- `tests/test_planner_week_api.py` — F11-Zeitraum, getrennte Quellenausfälle,
  nicht gesyncte Woche, vollständig leere Woche, gezielter `/api/week`-Zeitraum.
- `tests/test_planner_week_projection.py` — F12/F13-Projektion einer bestätigten
  Beziehung ohne Doppelzählung und Abschlussreferenz außerhalb der Planwoche.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **247 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check ...` (P06-Dateien) | ohne Befund |
| `curl /api/planner?week=2026-11-06` | 7 Tage, 2.–8.11.2026, getrennte Quellen |

## 4. Offene Punkte

- Es gibt weiterhin keine persistierte explizite Plan-/Aktivitätsbeziehung im
  Bestand. Die Projektion kann bestätigte Beziehungen darstellen, der
  Produktpfad liefert derzeit eine leere Beziehungsliste. Die Heuristik
  `plan.matches()` bleibt aus der Wochenprojektion ausgeschlossen.
- Die lokale Datenbank hat keine Pagination. Die vorhandene Pagination der
  Garmin-Quelle bleibt im Sync-Pfad; `/api/planner` liest den bereits
  gespeicherten Bestand und erfindet keine Historienabdeckung.
- Die Ladezustände `loading` und veraltete Antworten entstehen in der
  Oberfläche (P07); der Server liefert nur bestätigte bzw. fehlerhafte
  Quellenzustände.

## 5. Nächstes Paket

**P07 — Bestehende Liste zum Trainingsplaner umbauen und Dashboard-Links bereinigen.**

---

# Trainingsplaner — Arbeitsnachweis P07

**Stand:** 06.11.2026
**Paket:** P07 — Bestehende Liste zum Trainingsplaner umbauen und Dashboard-Links bereinigen
**Basis:** Branch `feature/trainingsplaner`, HEAD `8715f9d`
**Umfang:** Planer-Seite und Haupttab, Wochennavigation, sieben Tagesgruppen,
getrennte Quellenhinweise, Ist-/Plan-Zusammenfassung, lesende Detailblätter,
alte URL-Weiterleitung; Dashboard-Karte ohne Umfang-/Einheiten-Navigation.

## 1. Ergebnis

- Die alte `WeekSheet`-Liste ist entfernt. Es gibt keinen zweiten rollierenden
  Listenmodus und keinen aktiven Dashboard-Weg dorthin.
- Der Haupttab „Planer“ öffnet `/planer?woche=JJJJ-MM-TT`; die Seite zeigt
  **Trainingsplaner**, den vollständigen Wochenzeitraum, Kalenderwoche,
  Montag–Sonntag und sieben aufsteigende Tagesgruppen.
- Drei Navigationsaktionen: vorige Woche, nächste Woche, „Diese Woche“.
  Wochenwechsel nutzen `replaceState` und stapeln keine Zurück-Schritte.
  Die gewählte Woche bleibt über Tabwechsel und Detailblätter erhalten.
- Jeder Tag hat eine Plus-Aktion. Bis zum Anlegepaket öffnet sie einen
  ehrlichen Hinweis ohne Schreibzugriff; sie ist an jedem Tag vorhanden.
- Einträge sind typisiert und stabil sortiert: Tage aufsteigend, vorhandene
  Startzeit aufsteigend, Einträge ohne Uhrzeit danach, dann Typ und Key.
  Gleichnamige Planungen bleiben getrennt.
- Bestätigte Beziehungen werden über die P05-Projektion dargestellt; eine
  Beziehung erzeugt keine zweite unmarkierte Karte und keine doppelte
  Ist-Zeit. Ohne belegte Beziehung bleiben Plan und Aufzeichnung getrennt.
- Leere Tage erscheinen ruhig als „Keine Einheiten“ nur dann, wenn beide
  relevanten Quellen vollständig geladen sind. Fehler, Teilzustände und
  fehlende Abdeckung stehen als Quellenhinweis mit gezieltem
  Wiederholen-Knopf; erfolgreiche Daten der anderen Quelle bleiben sichtbar.
- Zusammenfassung: **Absolviert**, **Belastung**, **Einheiten** aus den
  eindeutigen Aufzeichnungen; darunter separat „Noch geplant: …“ mit
  gemischten Zeit-/Distanzvorgaben und Kennzeichnung unbekannter Angaben.
  Die Werte sind nicht mit der rollierenden Dashboard-Karte gekoppelt.
- Während eines Wochenwechsels werden Antworten über die laufende Anfrage und
  den Antwort-Schlüssel verworfen, wenn sie nicht zur zuletzt gewählten Woche
  gehören. Ein kurzer lokaler Cache zeigt nur Daten derselben Woche als
  „wird aktualisiert“.
- Dashboard-Karte „Letzte 7 Tage“ bleibt mit Volumeninfo, Kennzahlen,
  Wochenstreifen und rollierender Berechnung erhalten. „Umfang“ und
  „Einheiten“ sind reine `MetricRow`-Informationen ohne Button, Link,
  Handler, Chevron, Fokus oder Karten-Wrapper. `MetricRow` selbst kennt keine
  Aktion mehr.
- Alte gespeicherte URLs (`/woche`, `/week`, `?tab=woche`, Datum oder Bereich)
  werden validiert und per `replaceState` auf `/planer` geführt: ohne
  Datumsbezug zur aktuellen Woche, mit Einzeldatum in dessen Woche, mit
  Bereich über das Enddatum. Ungültige Daten fallen auf die aktuelle Woche
  zurück; es entsteht keine Zurück-Schleife.

## 2. Geänderte Dateien

- `web/src/pages/Planner.tsx` — Wochenplaner, Tagesgruppen, Quellenhinweise,
  Zusammenfassung, Plus-Aktion, Lese-Detailblätter.
- `web/src/plannerQuery.ts` — Wochenabfrage, lokaler Query-Cache,
  Stale-Schutz und gezieltes Wiederholen je Quelle.
- `web/src/routing.ts` — Planerroute, Altlisten-Aliase, Wochenanker,
  `replaceState`-Konventionen, Sitzungswiederherstellung.
- `web/src/App.tsx` — Haupttab-Navigation, Browser-Zurück, Route statt
  Tab-State.
- `web/src/pages/Today.tsx`, `web/src/components/ui.tsx`,
  `web/src/styles.css` — Dashboard-Karte ohne Umfang-/Einheiten-Navigation,
  `MetricRow` als reine Information, Planer-Gestaltung.
- `web/src/tabs.ts`, `web/src/components/icons.tsx` — Planer-Tab und
  Kalender-/Plus-/Weiter-Symbole.
- `web/src/types.ts`, `web/src/api.ts` — Planer-API-Form, Entfernen des alten
  Listen-API-Aufrufs.
- `web/src/components/WeekSheet.tsx` — entfernt.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **247 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check ...` (P06/P07-Dateien) | ohne Befund |

**Lesende Abnahme:** Die App wurde mit einer separaten lokalen
Vorschau-Datenbank (keine echten Quellen, keine Schreibaktion) auf
`127.0.0.1:8020` gestartet und bei 390 × 844 sowie 1440 × 900 geprüft:

- gefüllte Woche 2.–8.11.2026: sieben Tage, geplante und absolvierte Einträge,
  leerer Donnerstag, „Heute“-Markierung am Freitag, sieben Plus-Aktionen;
- vollständig leere Woche 10.–16.8.2026: sieben ruhige „Keine Einheiten“;
- alte URL `/woche?datum=2026-11-03` → `/planer?woche=2026-11-02`;
  alte Bereichs-URL → Enddatumswoche, ohne zweiten Modus;
- Dashboard-Karte: keine `button`-, `a`- oder `role="button"`-Elemente und
  kein Chevron in der Wochenkarte;
- Aktivitätsdetail aus der Woche: Rückkehr bei unveränderter Scrollposition
  (`676 → 676`), ausgewählte Woche bleibt erhalten;
- keine Browser-Fehler in der Konsole.

Screenshots liegen nur lokal unter `data/screens/` (ignoriert) und sind keine
Produktivdaten.

## 4. Offene Punkte

- Die Plus-Aktion öffnet bis P10 nur einen Hinweis; der Anlege-Editor und der
  eigentliche lokale Entwurf folgen dort.
- Geplante Einträge öffnen vorerst das vorhandene `SessionSheet`. Die neue
  Planungsdetailansicht, „Plan ansehen“ und das typabhängige Detailrouting
  folgen in P08.
- Es gibt weiterhin keine persistierte explizite Plan-/Aktivitätsbeziehung im
  Bestand; die Anzeige kann sie darstellen, der Produktpfad liefert derzeit
  keine. Die Heuristik `plan.matches()` wird dafür nicht verwendet.

## 5. Nächstes Paket

**P08 — Planungsdetails und bestehende Aktivitätsdetails verbinden.**

---

# Trainingsplaner — Arbeitsnachweis P08

**Stand:** 06.11.2026
**Paket:** P08 — Planungsdetails und bestehende Aktivitätsdetails verbinden
**Basis:** Branch `feature/trainingsplaner`, HEAD `0176c6a`
**Umfang:** Typabhängiges Öffnen von Planungen und Aufzeichnungen, lesende
Planungsdetails mit Notizen und Berechtigungen, „Plan ansehen“ für bestätigte
Beziehungen, Rückwege über Woche und Planbezug. Kein Schreibpfad.

## 1. Ergebnis

- Eine Planung öffnet über ihre vorhandene Event-ID, eine Aufzeichnung über
  die vorhandene lokale Aktivitätszeile (`row_id`). Die Wege bleiben getrennt;
  eine Aktivitäts-ID wird nie als Event-ID verwendet.
- `GET /api/planner/plan/{event_id}` (Alias `GET /api/plan/{event_id}`)
  liefert die Leseansicht: Name, Sport, Datum, Uhrzeit, vorhandene Notiz,
  sichere bekannte Umfänge, Berechtigungen, Aufbau und Graphdaten. Der
  Endpunkt liest ausschließlich; Öffnen und Auswahl erzeugen keinen Write.
- Die Planungsdetails zeigen `Quelle erlaubt Bearbeitung`, `Quelle erlaubt
  Metadaten` oder `Nur lesbar` samt Grund und Erhaltungsgrenzen. Es gibt
  bewusst keinen Bearbeiten-Knopf; der Editor folgt in P10–P16.
- Aufbau und Wiederholungsgruppen werden ohne Eingabefelder gerendert.
  Nicht unterstützte Knoten bleiben mit Quellreferenz und konkreter Erklärung
  sichtbar. Eine Wiederholungsgruppe zeigt ihre Kinder einmal, nicht als
  vielfach dupliziertes Formular.
- Aufzeichnungen öffnen weiterhin das bestehende `UnitSheet` über
  `/api/unit/{row_id}`. Messreihen, Zonen, Zahlen und Quellen bleiben
  unverändert. `UnitSheet` bekam nur eine optionale Planreferenz und den
  Knopf „Plan ansehen“; der bestehende Aktivitätsvertrag wurde nicht ersetzt.
- Bei einer bestätigten Beziehung öffnet der Eintrag primär die Aufzeichnung;
  der Plan bleibt über „Plan ansehen“ erreichbar. Mehrere Aufzeichnungen
  einer Beziehung bleiben als getrennte Zeilen und getrennte Detailziele
  erreichbar.
- Die URL trägt `woche`, optional `plan` und `einheit`. Öffnen legt einen
  History-Eintrag an, Schließen ersetzt den aktuellen Eintrag. „Plan ansehen“
  ergänzt den Planbezug, ohne die Aktivitätsansicht zu verlieren; Schließen
  führt zurück zur Aufzeichnung, danach zur gewählten Woche. Die gewählte
  Woche und die Scrollposition der Woche bleiben erhalten.
- Bestehende direkte Aktivitätslinks werden über `?einheit=<row_id>` weiter
  unterstützt. Die frühere App hatte keine eigenen Aktivitäts-URLs; der neue
  Parameter ist deshalb kein Ersatz für einen bestehenden Pfad, sondern die
  stabile typisierte Detailadresse des Planers.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/details.py` — lesende Detailprojektion,
  Rechte, Notizen, Knoten und Graph.
- `src/trainings_cockpit/api.py` — `GET /api/planner/plan/{id}` und
  `GET /api/plan/{id}`.
- `src/trainings_cockpit/planner/__init__.py` — Exporte.
- `web/src/components/PlanSheet.tsx` — Planungsdetails und Aufbau ohne
  Eingabefelder.
- `web/src/components/UnitSheet.tsx` — optionale Planreferenz, „Plan ansehen“,
  sonst unveränderte Aktivitätsdetails.
- `web/src/pages/Planner.tsx` — typabhängiges Öffnen, mehrere Aufzeichnungen,
  Planbezug und Rückwege.
- `web/src/routing.ts`, `web/src/App.tsx` — `plan`/`einheit` in der Route,
  History-Konventionen und Erhalt der gewählten Woche.
- `web/src/api.ts`, `web/src/types.ts` — Detailvertrag.
- `src/trainings_cockpit/plan.py` — `work` bleibt auch ohne Ziel definiert;
  ein Plan ohne Ziel darf die Tageskarte nicht mit `KeyError` abbrechen.
- `tests/test_planner_details.py` — Detailendpunkt, Rechte, Notizen,
  Identität, unveränderter Rohinhalt und 404.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_details.py -q` | **8 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **255 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/plan.py src/trainings_cockpit/api.py src/trainings_cockpit/planner tests/test_planner_details.py` | ohne Befund |
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich |

**Lesende Abnahme:** Separate lokale Vorschau-Datenbank auf
`127.0.0.1:8030`, keine echten Quellen, keine Schreibaktion. Geprüft bei
390 × 844 und 1440 × 900:

- F02 „Gemischte HF- und Pace-Intervalle“ als Planung geöffnet: Name, Sport,
  Datum, 36 min, vier Wiederholungen, getrennte HF-/Pace-Spuren, Aufbau,
  Planungsnotiz und Berechtigung sichtbar;
- F04 „Bahnintervalle mit Distanz“ als schematische Detailansicht;
- F07 als Import mit unbekannten Inhalten: konkrete Erklärung und
  `metadataOnly`, kein stilles Weglassen;
- bestehende Aufzeichnung „Lockerer Dauerlauf“: dieselbe Aktivitätsansicht mit
  gemessener Kurve, Ist-Zahlen und Quelle;
- Deep-Link `?woche=2026-11-02&plan=9102` öffnet die Planung, Schließen führt
  zurück auf die Woche; `?einheit=2` öffnet die bestehende Aktivitätsansicht;
- kein horizontaler Überlauf, keine Browser-Fehler.

Screenshots liegen lokal unter `data/screens/` (`p08-plan-detail-390.png`,
`p08-plan-detail-1440.png`, `p08-plan-notes-390.png`,
`p08-plan-notes-1440.png`, `p08-activity-detail-1440.png`,
`p08-plan-group-selected-1440.png`) und sind keine Produktivdaten.

## 4. Offene Punkte

- Der Produktpfad liefert weiterhin keine persistierte bestätigte Beziehung;
  die Darstellung „Plan ansehen“ ist über den vorhandenen
  `TrainingRelationship`-Vertrag gebaut und durch die P05/P06-Projektion
  abgesichert. Ohne Beziehung bleiben Plan und Aufzeichnung getrennt.
- Die Planungsdetails sind rein lesend. Bearbeiten, Feldpuffer und Speichern
  folgen in P10–P22; es gibt keinen Schein-Editor und keinen deaktivierten
  Speichern-Knopf.
- Der Graph ist noch nicht Teil des `SessionSheet` auf der Heute-Seite. Die
  bestehende Aktivitätskurve bleibt dort unverändert; P09 bindet den neuen
  Graph ausschließlich an die Planungsdetails.

## 5. Nächstes Paket

**P09 — Trainingsverlauf als reine Darstellung integrieren.**

---

# Trainingsplaner — Arbeitsnachweis P09

**Stand:** 06.11.2026
**Paket:** P09 — Trainingsverlauf als reine Darstellung integrieren
**Basis:** Branch `feature/trainingsplaner`, HEAD `0176c6a`
**Umfang:** Graphdaten aus der zentralen Ausführungsfolge, Zeit-/Distanz-/
schematische Achse, getrennte Zielspuren, Auswahl über Knoten-IDs,
responsive Breite, Textalternative und ausdrückliche Kompression.

## 1. Ergebnis

- `src/trainings_cockpit/planner/profile.py` erzeugt die Graphdaten als reine
  Funktion aus `derive_execution_sequence()` und
  `calculate_known_totals()`. Es gibt keine zweite Wiederholungs- oder
  Summenlogik im Frontend.
- Achsen: alle Zeitabschnitte → proportionale Zeitachse; alle Distanzen →
  proportionale Distanzachse; gemischte oder offene Enden → gleich breite
  schematische Abschnitte. Eine Distanz wird nicht über eine erfundene Pace
  in Zeit umgerechnet.
- Spuren werden je Zielmetrik und Einheit getrennt: HF-Zonen, HF-bpm,
  Pace min/km, Pace /100 m, Leistung W, Leistung % FTP und „Ohne Ziel“.
  Numerische Spuren haben eine eigene, nur für diese Einheit gültige Skala.
  HF und Watt werden nie auf eine gemeinsame unbeschriftete Achse gelegt.
- Pace ist umgedreht: schnellere Vorgaben liegen höher; die Oberfläche nennt
  „Schneller“ und „Langsamer“ über die Achsenrichtung. Bereiche werden als
  Band dargestellt, Einzelwerte als schmale Marke. `0 W` bleibt ein gültiger
  Wert und wird nicht zu „Ziel fehlt“.
- Jeder Graphabschnitt trägt die Knoten-ID der Ausführung. Die Aufbauliste
  verwendet dieselbe ID. Auswahl einer Gruppe hebt alle Ausführungen ihrer
  Kinder hervor; Auswahl eines Kindes hebt alle Wiederholungen dieses Kindes
  hervor. Die Aufbauliste bleibt die vollständige, tastaturbedienbare
  Alternative zu schmalen Graphsegmenten.
- Die Breite wird per `ResizeObserver` gemessen. Die SVG wird nicht als feste
  breite Grafik herunterskaliert; Achsen, Spurlabels und Einheiten bleiben bei
  320 und 390 px lesbar. Eine Textalternative beschreibt Summe, Ausführungen
  und Spuren.
- Große Wiederholungsmengen werden ab einem Darstellungsbudget von 160
  Ausführungen als eigener Block „+N“ zusammengefasst. Die Gesamtsummen
  stammen weiterhin aus der algebraischen Berechnung und bleiben unverändert;
  die Oberfläche nennt die Zahl der zusammengefassten Ausführungen.
- Der neue Graph hängt ausschließlich an geplanten Vorgaben. Die bestehende
  gemessene Aktivitätskurve (`WorkoutChart`) und ihre Legende werden weder
  ersetzt noch als Planvorgabe gedeutet.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/profile.py` — Achsen, Segmente, Spuren,
  Zonenauflösung, Pace-Richtung, Kompression und Textalternative.
- `src/trainings_cockpit/planner/details.py` — Graph an die Detailantwort,
  Darstellungsbudget 160 Ausführungen.
- `web/src/components/PlanSheet.tsx` — `WorkoutProfile`, Achsen, Spuren,
  Auswahl, Textalternative und komprimierter Block.
- `web/src/styles.css` — Planungsdetail-, Aufbau- und Graphgestaltung mit
  bestehenden Tokens; keine neuen Farb- oder Abstandssysteme.
- `tests/test_planner_details.py` — F01–F05, F07, `0 W`, ein Abschnitt ohne
  Ziel, Kompression ohne Summenänderung und getrennte Spuren.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_details.py -q` | **8 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **255 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/planner tests/test_planner_details.py` | ohne Befund |
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich |

**Sichtprüfung:** F02 (HF + Pace, Zeitachse), F04 (Zeit + Distanz,
schematisch), F05 (Schwimmen, 800 m + 4 min) und eine 300-fache Serie
(160 gezeichnete Blöcke, 440 komprimiert, Summe 5 h) bei 390 × 844 und
1440 × 900 geöffnet. Kein horizontaler Überlauf (`scrollWidth` = Viewport),
keine abgeschnittenen Labels, keine Browser-Fehler. Die bestehende
Aktivitätsansicht zeigt weiterhin ihre gemessene Kurve.

Screenshots liegen lokal unter `data/screens/`:
`p09-distance-graph-390.png`, `p09-distance-graph-1440.png`,
`p09-swim-390.png`, `p09-swim-1440.png`,
`p09-compressed-390.png`, `p09-compressed-1440.png`; für P08 zusätzlich
`p08-plan-detail-*` und `p08-plan-notes-*`.

## 4. Offene Punkte

- Der Graph ist eine Leseansicht. Die Bearbeitung, Feldpuffer und
  Vorschau-Aktualisierung während der Eingabe folgen in P10–P16; die
  Graphdaten sind dafür bereits die gemeinsame Ableitung.
- Die Plan-/Ist-Überlagerung ist nicht Teil dieses Pakets. Die gemessene Kurve
  bleibt in der Aktivitätsansicht; „Plan ansehen“ öffnet die Vorgaben separat.
- Zonen werden als eigene ordinale Spur dargestellt. Eine physiologische
  Rangfolge aus benutzerdefinierten Zonennamen wird nicht erfunden; ohne
  belegte Zonenreferenz bleibt die Vorgabe lesbar und die Spur neutral.

## 5. Nächstes Paket

**P10 — Lokalen Entwurf und Feldpuffer einführen.**

---

# Trainingsplaner — Arbeitsnachweis P10

**Stand:** 06.11.2026  
**Paket:** P10 — Lokalen Entwurf und Feldpuffer einführen  
**Basis:** Branch `feature/trainingsplaner`, HEAD `258402a`  
**Umfang:** Lokaler Entwurf, Feldpuffer je Knoten-ID/Feldpfad, serverseitige
Projektion ohne Remote-Schreiben, Bearbeitungsbeginn und Verwerfen.

## 1. Ergebnis

- `WorkoutDraft` bleibt die Grenze: Basisplan, Source-Snapshot und aktueller
  Entwurf sind getrennt. Der Browser hält Basis und Snapshot unverändert; die
  Eingaben liegen als Rohtext unter `node_id` + Feldpfad.
- `POST /api/planner/plan/{id}/draft` liest die gespeicherte Basis über den
  vorhandenen P04-Adapter, baut den Entwurf mit `validate_draft`, und liefert
  Detail, Summen, Diagramm und Feldfehler. Es gibt keinen Netzwerkaufruf zu
  intervals.icu und keinen Schreibvorgang.
- Unfertige Werte (`5:`, leerer Umfang, `1,`) bleiben Rohtext mit
  `incomplete`/`invalid`. Das validierte Modell behält den zuletzt gültigen
  Wert; leere Eingaben werden nicht zu `0`.
- Ein ausdrücklich gewechseltes, noch leeres Ende ist als `OpenEnd` im
  Entwurfsmodell sichtbar. Diagramm und Summe markieren den Abschnitt als
  offen, statt eine Dauer oder Geschwindigkeit zu erfinden.
- Dirty ist semantisch: Ein gültiger Feldpuffer mit demselben Wert ist nicht
  dirty; Auswahl und aufgeklappter Block werden nicht an die Projektion
  geschickt und ändern den Status nicht.
- Ein begonnener Entwurf setzt eine Schutzmarke. Ein später eintreffender
  Detail-Read überschreibt ihn nicht. Verwerfen setzt Basis, Puffer und
  Auswahl zurück; die gespeicherte Planung bleibt unverändert.
- P10 verändert kein Remote-Event und enthält noch keinen Speicherknopf. Der
  Schreibpfad folgt in P17.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/model.py` — `OpenEnd` nur für Entwürfe.
- `src/trainings_cockpit/planner/drafts.py` — Entwurfsprojektion, Parser der
  Feldpuffer, semantische Dirty-Prüfung.
- `src/trainings_cockpit/planner/details.py` — gemeinsame Detailantwort für
  Leseansicht und Entwurf inklusive Source-Snapshot-Metadaten.
- `src/trainings_cockpit/planner/validation.py` — offene Enden zählen als
  unbekannt und blockieren die Workoutvalidierung.
- `src/trainings_cockpit/api.py` — lokaler Draft-Endpunkt.
- `web/src/plannerDraft.ts` — Feldpuffer, Serialisierung, Dirty-Vergleich.
- `web/src/components/PlanSheet.tsx` — Entwurfszustand, Bearbeitungsbeginn,
  Verwerfen, Schutz vor überschreibenden Reads.
- `web/src/types.ts`, `web/src/api.ts` — Entwurfsvertrag.
- `tests/test_planner_drafts.py` — F01, Semantik, Puffer, OpenEnd, keine
  Schreibwirkung.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_drafts.py -q` | **9 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **264 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/api.py src/trainings_cockpit/planner tests/test_planner_drafts.py` | ohne Befund |
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich |

**Sichtprüfung:** Bearbeiten, Verwerfen und ein absichtlich unfertiger Wert
(`5:`) bei 390 × 844 und 1440 × 900 geöffnet. Der Entwurf bleibt beim
Einklappen und erneuten Öffnen erhalten; die gespeicherte Summe bleibt
unverändert, solange der Wert ungültig ist.

## 4. Offene Punkte

- Speichern, Konflikte und Remote-Rücklesen folgen in P17/P18.
- Abschnitt hinzufügen/entfernen/verschieben folgt in P14; Pace, Watt und
  gemischte Ziele folgen in P13.

## 5. Nächstes Paket

**P11 — Inline-Akkordeon und stabilen Fokus umsetzen.**

---

# Trainingsplaner — Arbeitsnachweis P11

**Stand:** 06.11.2026  
**Paket:** P11 — Inline-Akkordeon und stabilen Fokus umsetzen  
**Basis:** Branch `feature/trainingsplaner`, HEAD nach P10  
**Umfang:** Formularregion im Block, genau ein offener Editor, Kopf- und
Graphauswahl, stabile DOM-Identität.

## 1. Ergebnis

- Die Formularregion liegt als eigenes `section` unmittelbar nach dem Kopf und
  innerhalb desselben `<li>` des Blocks. Es gibt keinen Editor oberhalb des
  Aufbaus und kein zweites Formular.
- Höchstens ein Editor ist offen; `null` ist gültig. Ein Kopfklick öffnet,
  derselbe Kopf schließt, ein anderer Kopf wechselt. Ein Klick in ein Input
  löst keine erneute Blockauswahl aus.
- Gruppen und Kinder sind korrekt verschachtelt: Der Gruppeneditor steht vor
  der Kinderliste, der Kindereditor innerhalb des Kindes. Beim Wechsel wird
  der jeweils andere Editor geschlossen.
- Jeder Auswahlkopf ist ein echter Button mit sichtbarem Text, ergänzendem
  `aria-label`, `aria-expanded` und `aria-controls`. Die referenzierte Region
  trägt dieselbe ID und ist ein `role="region"` mit `aria-labelledby`.
- Komponenten-Keys stammen ausschließlich aus `node.node_id`. Beim Tippen
  werden weder Liste noch Editor neu aufgebaut; Eingabefeld, Fokus und
  Cursorposition bleiben erhalten, während Projektion, Kopfzeile und Diagramm
  aktualisieren.
- Beim Aufklappen wird nicht automatisch fokussiert und keine Tastatur
  geöffnet. Gescrollt wird nur, wenn der gewählte Kopf außerhalb des sichtbaren
  Bereichs liegt, etwa nach einer Graphauswahl.
- Die Graphauswahl öffnet den zugehörigen Abschnitt. Erneutes Wählen desselben
  Segments lässt ihn offen.

## 2. Geänderte Dateien

- `web/src/components/PlanEditor.tsx` — Akkordeon, Kopfzeilen, Gruppen- und
  Kinderverschachtelung, Formularregion.
- `web/src/components/PlanSheet.tsx` — ein offener Editor, Kopf-/Graphwechsel,
  Scroll-Helfer und stabile Zustandsführung.
- `web/src/styles.css` — Blockkopf, Inline-Fläche, Formularraster und
  Fokuszustände mit vorhandenen Tokens.

## 3. Prüfung

| Prüfung | Ergebnis |
|---|---|
| Kopfklick / erneuter Klick / Wechsel | `aria-expanded` wechselt korrekt; 1 → 0 → 1 Editor |
| Graphauswahl / erneute Auswahl | Kindeditor offen; erneute Auswahl bleibt offen |
| Klick in ein Input | Editor bleibt offen (`aria-expanded="true"`) |
| Tippen im Namen | dasselbe Input-DOM, `selectionStart=4`, Fokus erhalten |
| Gruppen-/Kindeditor | 1 Editor, Kindeditor innerhalb des Kindes, Gruppe geschlossen |
| `npm run build --prefix web` | erfolgreich |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **264 passed** |

**Sichtprüfung:** F01 (einfacher Lauf) und F02 (Wiederholungsgruppe) bei
390 × 844 und 1440 × 900. Kein horizontaler Überlauf (`scrollWidth` =
Viewport). Screenshots unter `data/screens/`: `p10-p11-simple-390.png`,
`p10-p11-simple-1440.png`, `p11-group-390.png`, `p11-group-1440.png`,
`p11-child-390.png`, `p11-child-1440.png`.

## 4. Offene Punkte

- Hinzufügen, Entfernen, Verschieben und Undo folgen in P14.
- Gruppeneinstellungen und Auflösen der Wiederholungen folgen in P15.

## 5. Nächstes Paket

**P12 — Umfang und HF-Ziele eines Einzelabschnitts bearbeiten.**

---

# Trainingsplaner — Arbeitsnachweis P12

**Stand:** 06.11.2026  
**Paket:** P12 — Umfang und HF-Ziele eines Einzelabschnitts  
**Basis:** Branch `feature/trainingsplaner`, HEAD nach P11  
**Umfang:** Name, Rolle, Zeit/Distanz, HF-Zonen aus Profil, Feldfehler,
Summen und Diagramm aus dem Entwurf.

## 1. Ergebnis

- Abschnittsname und Rolle sind angebunden. Die Rolle bietet gleichmäßig,
  Aufwärmen, Belastung, Erholung und Abwärmen; sie ändert nur den Entwurf.
- „Abschnitt endet nach“ schaltet zwischen Zeit und Distanz. Der Wechsel löscht
  den bisherigen Umfang und setzt kein Tempo und keine Dauer aus dem anderen
  Wert. Ein leeres Ende bleibt als `OpenEnd` sichtbar.
- Distanz wird kanonisch in Metern gespeichert: `1,5 km` ergibt `1500` m; die
  Eingabe bleibt als Rohtext `1,5 km` erhalten. `1.500 m` und deutsche Kommas
  werden vom gemeinsamen Parser verarbeitet.
- HF-Zonen kommen ausschließlich aus `sport_profile` der tatsächlichen
  Sportart. Es werden keine Grenzen aus einer Formel ergänzt. Fehlt das Profil,
  bleibt die Liste leer und „Ohne Ziel“ möglich.
- Eine gespeicherte, im Profil unbekannte Zonenreferenz bleibt erhalten und
  wird als „Referenz nicht im Profil“ markiert. Sie wird nicht still ersetzt.
- `capabilities.targets` trennt lokale Modellfähigkeit von Remote-Unterstützung:
  HF-Zonen sind lokal bearbeitbar, aber noch nicht als synchronisierbar
  freigeschaltet; absolute bpm sind lokal modelliert, aber hinter dem
  `absolute_hr`-Adapter-Gate gesperrt. Die Oberfläche erklärt beides am Feld.
- Feldfehler erscheinen am betroffenen Feld, nicht als Toast pro Tastendruck.
  Ein leerer oder unfertiger Wert bleibt stehen und blockiert die Validierung.
- Summen, Hero und Diagramm stammen aus der Serverprojektion des validierten
  Entwurfs. Offene Enden erscheinen als „offene Abschnitte“/schematische Achse
  und als ruhiger Hinweis; der Kopf trägt „unvollständig“.
- Ein Zeit-/Distanzwechsel erfindet keine Geschwindigkeit. `1,5 km` aktualisiert
  Summe (`1,5 km`) und Achse (`Distanz (km)`), ohne die alte Dauer zu behalten.

## 2. Geänderte Dateien

- `src/trainings_cockpit/planner/profile.py` — `heart_rate_zone_options` aus dem
  tatsächlichen Profil; HF-Grenzen und stabile String-IDs.
- `src/trainings_cockpit/planner/details.py` — Zonenoptionen, Fähigkeiten,
  Source-Snapshot und offene Enden in der Detailprojektion.
- `web/src/components/PlanEditor.tsx` — Namens-, Rollen-, Zeit-/Distanz-,
  Zielart- und Zonenfelder sowie Fehler- und Unbekannt-Hinweise.
- `web/src/plannerDraft.ts`, `web/src/types.ts` — Serialisierung und Vertrag.
- `tests/test_planner_drafts.py` — `1,5 km` → `1500 m`, offenes Ende,
  unfertiger Wert, gleicher Wert nicht dirty, Profil fehlt, unbekannte Zone,
  keine Schreibwirkung.

## 3. Prüfung

| Befehl | Ergebnis |
|---|---|
| `UV_CACHE_DIR=.uv-cache uv run pytest tests/test_planner_drafts.py -q` | **9 passed** |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **264 passed**, 1 bestehende Starlette-Warnung |
| `UV_CACHE_DIR=.uv-cache uv run ruff check src/trainings_cockpit/api.py src/trainings_cockpit/planner tests/test_planner_drafts.py` | ohne Befund |
| `npm run build --prefix web` | `tsc --noEmit` und Vite-Build erfolgreich |

**Sichtprüfung:** F01 bei 390 × 844 und 1440 × 900: `1,5 km` eingegeben,
Summe `1,5 km`, Achse `Distanz (km)`, Knoten-Meta `1,5 km · Zone 2`; leeres
Ende und `5:` separat geprüft. Kein horizontaler Überlauf. Screenshots unter
`data/screens/`: `p12-distance-sum-390.png`, `p12-distance-sum-1440.png`,
`p12-distance-full-390.png`, `p12-distance-full-1440.png`.

## 4. Offene Punkte

- Pace, Watt, % FTP und „ohne Ziel“ als editierbare Zielart folgen in P13.
  Importierte Pace-/Watt-Ziele bleiben in P12 sichtbar und unverändert.
- Speichern und Synchronisieren folgen in P17; absolute bpm bleiben bis zu
  einem belegten Schreibvertrag gesperrt.

## 5. Nächstes Paket

**P13 — Pace, Watt und gemischte Ziele ergänzen.**

---

## Ergänzung: Entscheidung und Abgrenzung P10–P12

Die Architektur ist als **D-72** in `docs/ENTSCHEIDUNGEN.md` festgehalten:
Feldpuffer und UI-Zustand liegen im Browser, die fachliche Projektion entsteht
serverseitig aus derselben Ausführungsfolge wie Summen und Diagramm. Der
Draft-Endpunkt liest die gespeicherte Basis und schreibt nichts. `OpenEnd`
existiert nur im Entwurf und ist nicht speicherbar.
