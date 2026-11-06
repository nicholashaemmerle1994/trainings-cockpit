# Trainingsplaner — unabhängiges Review (S12)

**Stand:** 06.11.2026  
**Branch:** `feature/trainingsplaner` (Ausgangs-HEAD `fe7735a`)  
**Basis:** `develop` (`32860c1`)  
**Rolle:** unabhängiger Review-Agent, keine Mitwirkung an der Implementierung  
**Ergebnis:** **FAIL** — Tests und Build sind grün, die Kernfunktionen sind
weitgehend vorhanden; die Muss-Funktion „Letzte Erholung auslassen“ bleibt
aber als gemeinsam bearbeitbare Gruppe ohne belegten Schreib-/Leseweg
gesperrt (siehe Abschnitt 4). Kein Merge, kein Push.

## 1. Geprüfter Umfang

Gelesen und als Maßstab verwendet:

- `AGENTS.md`, `DESIGN.md` (verbindliches Designsystem),
- `docs/trainingsplaner/TRAININGSPLANER_IMPLEMENTIERUNGSPLAN.md`
  (Revision 1.6, insbesondere Abschnitte 2, 4–9, 12–14),
- `docs/training-planner-progress.md` (P00–P27),
- `docs/trainingsplaner/FAEHIGKEITSMATRIX.md`, `UEBERGABE.md`,
  `KONFLIKTE.md`, `SERIALIZER-VERTRAG.md`, `SYNC.md`, `VORGAENGE.md`.

Geprüft wurde der tatsächliche Produktdiff `develop...HEAD`:

- 30 Commits, 116 geänderte Dateien, 33.334 Einfügungen / 566 Löschungen,
- die produktiven Python-Dateien des Planers, die API-Erweiterungen,
  DB- und Sync-Änderungen sowie die zugehörigen Tests gezielt geprüft,
- die neue Oberfläche (`App.tsx`, `Planner.tsx`, `PlanSheet.tsx`,
  `PlanEditor.tsx`, `AddWorkoutSheet.tsx`, `UnitSheet.tsx`, `Sheet.tsx`,
  `routing.ts`, `plannerDraft.ts`, `plannerDraftStore.ts`,
  `plannerQuery.ts`, `Today.tsx`, `tabs.ts`, `styles.css`),
- die entfernten Altdateien (`WeekSheet.tsx`, `Activities.tsx`,
  `ActivityTable.tsx`) und die verbliebenen Dashboard- und
  Aktivitätsdetailpfade.

Die Dateien unter `docs/trainingsplaner/` wurden als Arbeitsgrundlage gelesen,
nicht als eigener Prüfgegenstand bewertet. Die Paketberichte wurden mit dem
Code abgeglichen, nicht ungeprüft übernommen.

## 2. Befunde und Korrekturen

Die folgenden Punkte waren echte Fehler im Branch und wurden direkt korrigiert,
gezielt getestet und in einem eigenen Review-Commit festgehalten.

### K-01 — Teilweise abgedeckte Wochen galten als vollständig

`coverage_for_period` prüfte nur, ob sich Sync-Bereich und Woche
**überschneiden**. Eine Woche, die vor dem Sync-Beginn begann oder in der
Vergangenheit über das gelesene Ende hinausreichte, konnte dadurch als
„covered“ und bei fehlenden Zeilen als bestätigt leer erscheinen. Bei
vorhandenen Zeilen wurde sie als vollständig summiert.

**Korrektur:** `coverage_for_period` verlangt jetzt die vollständige
Containment-Bedingung (`week_start >= sync_start` und
`week_end <= sync_end`). Für die Aktivitätsquelle wird das Wochenende am
lokalen Heute begrenzt, weil in der Zukunft keine Aufzeichnung liegen kann.
`_source_state` meldet bei vorhandenen Zeilen und unvollständiger Abdeckung
`partial` statt `complete`.

**Nachweis:** `tests/test_planner_week_api.py`:
`test_nur_teilweise_abgedeckte_woche_ist_nicht_bestaetigt_leer`,
`test_teilweise_abgedeckte_woche_mit_zeilen_ist_partial`,
`test_aktuelles_wochenende_gilt_fuer_aufzeichnungen_als_abgedeckt`.

### K-02 — Offene Planung verschwieg unbekannte Teilmengen

Ein Plan mit teilweise unbekanntem Aufbau (F07) lieferte
`open_plan.has_unknown = false`, weil nur geprüft wurde, ob **gar keine**
Zeit und **gar keine** Distanz bekannt war. Die Wochenzeile zeigte dadurch
eine scheinbar exakte Summe, obwohl nur ein Teil der Abschnitte bekannt war.

**Korrektur:** `build_planner_week` übernimmt jetzt auch das
`planned.has_unknown` eines Eintrags in die offene Summe.

**Nachweis:** `test_unvollstaendig_bekannter_plan_markiert_die_offene_summe`;
im Browser erscheint bei F07 „… · Angaben unvollständig“.

### K-03 — Wochenkarten zeigten geschätzte Gesamtwerte statt der belegten Teilmenge

Die Karten verwendeten `planned.minutes`/`planned.km` aus dem bestehenden
Parser. Dadurch zeigte F04 „51 min“ statt der belegten „28 min + 4,0 km“,
und F07 zeigte „20 min“, obwohl nur 10 min belegt sind. Das widerspricht
F04 und der Regel „keine angeblich exakte Gesamtzeit“.

**Korrektur:** `plannedMeta` in `web/src/pages/Planner.tsx` verwendet jetzt
`known_seconds`/`known_distance_metres`, kennzeichnet verbleibende
Schätzungen weiterhin mit „≈“ und hängt bei unbekannten Teilen
„· unvollständig“ an. Gemischte Zeit-/Distanzsummen werden mit „+“ getrennt.

**Nachweis:** Browserprüfung mit F01/F02/F04/F07; F04 zeigt
„4,0 km + 28 min“ (belegte Teilmenge), F07 „10 min · ≈ 6,7 km · unvollständig“.

### K-04 — Metadaten-editierbare Planungen hatten keinen Bearbeitungsweg

F07 ist laut Bestand `metadataOnly` (`can_edit_metadata = true`,
`can_edit_structure = false`). Die Oberfläche zeigte trotzdem keinen
Bearbeiten-Knopf, weil `startEdit` ausschließlich
`can_edit_structure` prüfte. Damit war die im Plan verlangte sichere
Namens-/Datumsänderung unter Erhalt des unbekannten Aufbaus nicht möglich.

**Korrektur:** `PlanSheet.tsx` erlaubt jetzt den Metadatenmodus
(„Name & Termin bearbeiten“). Der Aufbau bleibt dabei schreibgeschützt und
wird als `PlanNodeList` gerendert; gespeichert werden nur Name/Termin, der
Serializer lässt `description` unverändert.

**Nachweis:** Browserprüfung F07: Knopf vorhanden, Struktur nicht editierbar,
Name änderbar, Speichern aktiv; API-Projektion liefert `valid: true` und
`write.available: true`.

### K-05 — Eingaben waren während eines laufenden/unklaren Writes nicht gesperrt

Der Speicherkoordinator sperrt serverseitig weitere Writes, die Oberfläche
ließ aber Eingaben während `saving`/`savedUnverified`/`unknown` weiter zu.
Das widerspricht Abschnitt 9.3 („fachliche Eingaben während des tatsächlichen
Schreibvorgangs sperren“).

**Korrektur:** Der Struktur-Editor ist während `saving || saveLocked` in ein
`fieldset disabled` eingebettet; Name/Termin, Undo und Baustein-Aktionen sind
ebenfalls deaktiviert. „Verwerfen“ bleibt bei einem unklaren Vorgang bewusst
möglich, weil es nur den lokalen Entwurf entfernt.

**Nachweis:** Browserprüfung mit verzögerter Save-Antwort: Name/Editor
disabled, Status „Wird gespeichert …“; nach dem Fehler wieder editierbar.

### K-06 — Fehlerhinweis behauptete weiterhin einen Speichervorgang

Nach einem fehlgeschlagenen Save stand unter dem Fehler weiter
„Speichert in intervals.icu · Rückleseprüfung inklusive“. Das ist eine falsche
Statusaussage.

**Korrektur:** `DraftStatus` zeigt bei einem Fehler jetzt
„Der Entwurf bleibt lokal erhalten; der Fehler steht oben.“; der konkrete
Fehler bleibt in der Statuszeile sichtbar.

**Nachweis:** Browserprüfung ohne konfigurierten API-Key (kein Remote-Write):
Meldung „Kein intervals.icu-Key konfiguriert.“, Entwurf bleibt erhalten.

### K-07 — Konflikt bei extern gelöschter Einheit bot „Remote übernehmen“ an

Bei einem gelöschten Remote-Event ist `conflict.remote = null`. Der Knopf
„Entwurf verwerfen, Remote übernehmen“ hätte in diesem Fall einen
`planRemote`-Aufruf ausgelöst und wäre mit 404 gescheitert.

**Korrektur:** Bei fehlender Remoteversion heißt die Aktion jetzt
„Entwurf verwerfen und schließen“; `adoptRemote` schließt in diesem Fall ohne
Remote-Leseversuch.

**Nachweis:** Code-Review; der nicht-gelöschte Konfliktpfad bleibt unverändert.

### K-08 — Sync-Zeitraum verwendete die Serverzeitzone

`sync.sync()` setzte `oldest`/`synced_range` aus `date.today()` der
Prozesszeitzone. Der Planer rechnet dagegen mit `TC_TIME_ZONE`. Am
UTC-Tagesrand konnten dadurch Abdeckungsmarke und Planerwoche um einen Tag
auseinanderliegen.

**Korrektur:** Ohne explizit übergebenes `today` verwendet `sync()` jetzt
`local_today(settings.time_zone)`.

**Nachweis:** `tests/test_sync.py::test_sync_nutzt_die_athletenzeitzone_fuer_den_lesebereich`.

### K-09 — Entwicklerhinweis im Anlegeformular

Das Formular zeigte den Satz „Sportart wird ausschließlich in einem
Text-Dropdown ausgewählt. Keine Icon-Kacheln als Sportauswahl.“ Das ist eine
Implementierungsanweisung, kein Produkttext, und widerspricht der
 DESIGN.md-Vorgabe „Information vor Dekoration“.

**Korrektur:** Hinweis und die zugehörige ungenutzte CSS-Regel entfernt.
Die drei Radios bleiben vertikal, das Sportart-Dropdown unverändert.

## 3. Ausgeführte Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `UV_CACHE_DIR=$PWD/.uv-cache uv run pytest -q` | **380 passed**, 1 bestehende Starlette-Deprecation-Warnung |
| `cd web && npm run build` | `tsc --noEmit` und Vite-Build erfolgreich (61 Module) |
| `uv run ruff check` auf alle geänderten Python-Dateien | ohne Befund |
| `git diff --check` | ohne Befund |
| `data/cockpit.db` | unverändert: 0 Aktivitäten, 0 Events, 2 Wellness-Zeilen, 0 Planer-Vorgänge |
| Browser | eigener Port 8099, separate SQLite-Kopie, keine Console-/Page-Fehler |

Manuell im Browser geprüft (390 × 844, 1440 × 1100 und 320 × 700):

- Dashboard mit „Letzte 7 Tage“; „Umfang“ ist ein `DIV` ohne Link, Button,
  `role`, `tabindex` oder Chevron; der umschließende `ASIDE`-Container hat
  keinen Aktionsfokus.
- Planer über den eigenen Tab; sieben Tagesgruppen Montag–Sonntag,
  Wochenwechsel vor/zurück, „Diese Woche“, Kalenderwochenlabel.
- Planungsdetail F02 mit getrennten HF-/Pace-Spuren, Blockliste und
  „Bearbeiten“.
- Inline-Editor direkt im Kindblock (nicht oberhalb des Aufbaus), genau ein
  `.plan-inline`, `aria-controls` passt zur Region; Fokus, Cursorposition und
  Input-Identität bleiben beim Tippen erhalten (Marker-Test: `active = true`,
  `selectionStart = 3`, Wert `BeXlastung`).
- Gruppe „Hauptteil 4×“ mit „Gilt für alle 4 Wiederholungen“; ein weiterer
  Block öffnet den Editor an der neuen Position, nicht als zweites Formular.
- Aktivitätsdetail „Morgenrunde“ über dieselbe bestehende `UnitSheet`-Ansicht
  mit Messreihe, Zonen, Quelle und Ist-Werten.
- Anlegen über Tages-Plus: ein Text-Dropdown mit genau Laufen/Radfahren/
  Schwimmen, keine Iconkacheln, drei vertikal gestapelte Radios, Datum
  „Samstag, 7. November“ übernommen; „Weiter“ erzeugt nur einen lokalen
  Entwurf, keinen Remote-Create.
- F07 (`metadataOnly`): Name/Termin editierbar, Aufbau nur lesend,
  Speichern nach Namensänderung aktiv.
- Alte Liste `/woche?datum=2026-08-03` → `/planer?woche=2026-08-03`;
  Bereich `/woche?von=2026-07-01&bis=2026-07-07` → Woche 06.–12.07.2026;
  Aktivitäts-Deep-Link `/aktivitaet/1` → `/planer?woche=…&einheit=1` mit
  geöffneter Aktivität; keine zweite Liste, keine Schleife.
- 320 px: kein horizontaler Overflow in Woche, Detail und Inline-Editor
  (`scrollWidth = 320`).

Screenshots liegen unter `data/screens/review-*` (nicht committet), unter
anderem:

- `review-dashboard-390.png`, `review-dashboard-1440.png`
- `review-week-390.png`, `review-week-1440.png`, `review-week-320.png`
- `review-plan-detail-390.png`, `review-plan-detail-1440.png`,
  `review-plan-detail-320.png`
- `review-inline-child-390.png`, `review-inline-child-320.png`,
  `review-inline-child-1440.png`
- `review-activity-detail-390.png`
- `review-add-390.png`
- `review-metadata-only-390.png`

Es gab **keinen** Schreibzugriff gegen intervals.icu oder Garmin. Die
Browserprüfung lief gegen eine separate SQLite-Kopie mit Fixtures; die
Produktivdatenbank `data/cockpit.db` blieb unverändert.

## 4. Verbleibende Grenzen und konkreter Blocker

1. **Skip-Gruppe ist nicht speicherbar (Blocker).**
   „Letzte Erholung auslassen“ funktioniert lokal (34 min, neun
   Ausführungen), wird aber als Gruppe vor der Payload-Erzeugung mit
   „nicht verlustfrei darstellbar“ abgelehnt. Der vorbereitete
   `EditorShapeMetadata`-Weg hat noch keinen lesenden Konsumenten. Die
   sichere Alternative ist das bewusste Auflösen in Einzelabschnitte; das
   erhält Ablauf und Summe, aber nicht die gemeinsame Gruppe. Damit ist ein
   Punkt aus P15/DoD („Auslassen … beim Speichern erhalten“) offen.

2. **Kein Live-Rundlauf.** Create, Update, Rücklesen und Konflikte sind nur
   gegen den kontrollierten Adapter belegt. Ein echter intervals.icu-
   Schreibzugriff und eine Geräteübertragung wurden nicht durchgeführt und
   werden nicht behauptet.

3. **Keine bestätigte Plan-/Aktivitätsbeziehung im Produktbestand.** Der
   Planer stellt den übergebenen Beziehungsvertrag dar, erzeugt aber keine
   Beziehung. Die bestehende Tageskarte auf „Heute“ verwendet außerhalb des
   neuen Planers weiterhin die alte `plan.matches()`-Heuristik
   (Tag + Sportfamilie + ähnliche Dauer); ein solcher Treffer ist keine
   bestätigte Beziehung und kann dort weiterhin „Erledigt“ anzeigen. Das ist
   ein vorbestehender Pfad, der beim Planer-Umbau nicht mit umgestellt wurde,
   und bleibt als Folgearbeit offen.

4. **Intervals-Pagination.** Der vorhandene Client fragt einen Datumsbereich
   ab, ohne Seiten-/Cursor-Schleife. Eine serverseitige Kappung könnte die
   Implementierung nicht erkennen. Garmin lädt 100er-Seiten bis maximal 1000.
   Die historische Verfügbarkeit endet dort, wo der lokale Sync sie hinterlässt.

5. **Konfliktfenster.** Vorab-GET und PUT sind keine atomare Vorbedingung;
   die Restlücke ist in `KONFLIKTE.md` dokumentiert.

6. **Weitere gesperrte Fähigkeiten.** Absolute bpm, Leistungszonen,
   benutzerdefinierte Zonen, verschachtelte Wiederholungen, mehrere Ziele pro
   Schritt, Rampen/Lap-Taste/Spezialschritte und globale Zielpriorität sind
   bewusst nicht freigegeben und in der Fähigkeitsmatrix benannt.

7. **Geräte-/Browserabdeckung.** Geprüft wurde Chromium/Headless in 320, 390
   und 1440 px, keine echte iOS-/Safari-Geräteprüfung.

8. **Designsystem-Aliase.** Neuer CSS-Code verwendet mehrfach die
   Übergangs-Aliase (`--line`, `--raised`, `--text-2`, `--r-control` usw.),
   obwohl `DESIGN.md` für neuen Code die kanonischen Tokens verlangt. Das ist
   kein funktionaler Blocker, aber ein offener Designsystem-Befund; die
   Tokens selbst und die dunkle Gestaltung stimmen.

## 5. DoD-Checkliste (Auszug, ehrlich bewertet)

| DoD-Punkt | Status | Beleg / Anmerkung |
|---|---|---|
| DESIGN.md und vorhandene Komponenten verwendet | [x] | Tokens, `ScreenHeader`, `DashboardCard`, `StatusBadge`, `Sheet`, `UnitSheet`, `WorkoutChart`; Alias-Befund siehe 4.8 |
| Integrierter Planer, keine zweite Demo-App | [x] | eigener Tab, `Planner.tsx` im bestehenden `App`-Shell |
| Bestehende Historie/Details wiederverwendet, keine parallele Aktivitätshaltung | [x] | `UnitSheet`, `WorkoutChart`, `metrics.unit_payload`; alte `ActivityTable` entfernt |
| Montag–Sonntag inkl. leerer Tage | [x] | Browser 390/1440, API-Tests |
| Alte Sieben-Tage-Liste ersetzt, kein zweiter Listenmodus | [x] | `WeekSheet`/`Activities` entfernt; `/woche` leitet weiter |
| Dashboard „Letzte 7 Tage“ rollierend und unabhängig | [x] | `build_overview` unverändert rollierend; Wochenwechsel ändert Wert nicht |
| „Umfang“ ohne Navigation/Chevron/Wrapper | [x] | DOM-Prüfung: `DIV`, kein `role`/`tabindex`/Link/Button, `ASIDE` ohne Fokus |
| Planer über eigenen Haupttab | [x] | Tab „Planer“, Route `/planer` |
| Plan und Aufzeichnung getrennt, getrennte Summen | [x] | `build_planner_week`, F12/F13-Tests |
| Aktivitätsdetails, Messreihen, Quellen, Sportarten erhalten | [x] | `UnitSheet`; Krafttraining im Browser geöffnet |
| Getrennte Identitäten, Writer nur für Planentwürfe | [x] | `plan:`/`activity:`-Keys, `require_planned_draft`, Tests |
| Nur belegte Beziehungen im Planer | [x] | `relationships=()` im Produktpfad; keine Namens-/Datumsheuristik im Planer |
| Jede kanonische Aktivität einmal am tatsächlichen Datum | [x] | `recorded_totals`, Projektionstests |
| Offene Planung separat, nicht mit Ist addiert | [x] | `summary.open_plan`; F12/F13 |
| Ältere Wochen, Pagination, Leere/Verfügbarkeit unterscheidbar | [x] | K-01; Quellenzustände, F14-Tests; Paginationgrenze dokumentiert |
| Quellenausfall isoliert | [x] | API-Tests für getrennte Fehler |
| Navigation, Zurück, Wochenwechsel | [x] | Browserprüfung; `replaceState` für Wochenwechsel |
| Alte URLs und Aktivitäts-Deep-Links | [x] | Browserprüfung `/woche`, Bereich, `/aktivitaet/1` |
| Rückkehr aus Details ohne Wochen-Reset | [x] | `App`-Routing/Scroll; Browserprüfung |
| Mehrere Einheiten pro Tag | [x] | Fixtures/Projektion; Browserwoche |
| Datum vom Tages-Plus | [x] | Browser: „Samstag, 7. November“ |
| Sportart nur Text-Dropdown, drei vertikale Radios | [x] | Browser: 1 Select, 3 Radios, keine Kacheln |
| Einheit aus genau einem Abschnitt | [x] | F01; `simple`-Vorlage |
| Lokale Bearbeitung von Abschnitten/Gruppen | [x] | Editor, Tests |
| Höchstens ein Editor direkt im Block | [x] | DOM: 1 `.plan-inline`, `aria-controls` im selben `LI` |
| Fokus/Cursor beim Tippen erhalten | [x] | Marker-/Selection-Test |
| Zeit, Distanz, HF-Zone, Pace, Watt korrekt | [x] | F01–F05, Validierungstests |
| Gemischte Ziele pro Abschnitt | [x] | F02/F03, getrennte Spuren |
| Graph ohne erfundene gemeinsame Skala/Gesamtdauer | [x] | Profiltests, Screenshot F02/F04 |
| Unfertige Eingaben über Blockwechsel/Undo | [x] | Draft-/Undo-Tests |
| Wiederholungen/Auslassen/Auflösen dieselbe Semantik | [ ] | Auflösen und lokal 34 min funktionieren; **Speichern der Skip-Gruppe blockiert** (4.1) |
| Importierte unbekannte Inhalte erhalten | [x] | F07: `UnsupportedNode` + Rohsnapshot; Metadatenmodus K-04 |
| Speichern über vorhandenen intervals.icu-Datenfluss | [x] | `IntervalsClient`/Upsert/Update; kein Live-Nachweis |
| Update behält Event-ID, Create erhält bestätigte ID | [x] | `event_write`, Tests |
| Double-Tap/Timeout/Reload ohne blinde Doppelanlage | [x] | `save.py`, F09-Tests |
| Konflikte, Entwurfserhalt, dokumentierte Restlücke | [x] | `conflicts.py`, `KONFLIKTE.md` |
| Rundlaufprüfungen dokumentiert | [x] | kontrollierter Adapter; Live offen |
| Nicht-native Gruppierung über Metadatenweg | [ ] | vorbereitet, aber ohne lesenden Konsumenten (4.1) |
| Lade-/Leer-/Fehler-/Offline-/Speicherzustände | [x] | `plannerQuery`, Quellenzustände, Browser |
| Mobile Breiten/Tastatur/Safe Areas geprüft | [x] | 320/390/1440 Chromium; keine echte Geräteprüfung |
| Tests und Build grün | [x] | 380 passed; `tsc` + Vite erfolgreich |
| Keine Demodaten/simulierter Speichererfolg in produktiven Pfaden | [x] | keine Demo-IDs/Speicherpfade; Fehlerpfad im Browser geprüft |
| Offene API-Fähigkeiten dokumentiert | [x] | `FAEHIGKEITSMATRIX.md`, P26/P27 |

## 6. Fazit

Der Branch ist deutlich weiter als eine Attrappe: Wochenprojektion,
Identitätstrennung, Inline-Editor, lokaler Entwurf, Serializer,
Speicherkoordinator, Konflikt- und Vorgangspfad sind vorhanden und durch 380
Tests sowie echte Browserdurchläufe belegt. Die Review-Korrekturen schließen
vier konkrete Fehler bei Abdeckung, Summen, Metadatenbearbeitung und
Eingabesperre.

Der Status bleibt trotzdem **FAIL**, weil die Skip-Gruppe als gemeinsam
bearbeitbare Gruppe nicht gespeichert werden kann und damit ein Muss-Punkt aus
P15/DoD mit konkretem Blocker offen ist. Zusätzlich bleibt die alte
Heuristik der Dashboard-Tageskarte außerhalb des Planers bestehen (4.3).
