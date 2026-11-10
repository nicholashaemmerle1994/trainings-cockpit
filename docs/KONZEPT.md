# Trainings- & Recovery-Cockpit — Konzept v1

**Stand:** 30.10.2026 · **Status:** Etappen 0–2 abgeschlossen: Datenzugang,
Dashboard und Verständlichkeit (Erholung, deutsche Begriffe, Countdowns, PWA).
Die Trainingsplanung wird gemeinsam entschieden, nicht automatisch.
**Athlet:** Nicholas · **Nutzung:** Einzelplatz, lokal (NAS/Docker), deutsche UI
**Ziele 2027:** IRONMAN Kärnten-Klagenfurt (A), Vienna City Marathon (B), Wörthersee Marathon (A-)

---

## 1. Zielbild

Ein lokales Dashboard, das vier Aufgaben erfüllt:

1. **Analysieren** — Aktivitäten und Erholungsdaten aus Garmin und Amazfit/Zepp zusammenführen.
2. **Bewerten** — Tagesform (Erholung), Belastungssteuerung, Trainingswirkung, Fortschritt.
3. **Planen** — periodisierter Trainingsplan auf die drei Saisonziele, mit Tagesanpassung.
4. **Senden** — Plan als Kalendereinträge nach intervals.icu, von dort auf die Geräte.

Der Plan ist ein **Vorschlag mit Freigabe**, kein Autopilot. Nichts ändert sich im Kalender ohne Klick.

---

## 2. Nicht-Ziele

- Kein Multi-User- oder SaaS-Betrieb (Garmin-Personal-API ist ausdrücklich nur für eigene Nutzung).
- Keine medizinische Diagnose, kein Ersatz für Arzt/Physio.
- Kein Ersatz für intervals.icu — intervals bleibt Kalender und Sync-Kanal zu den Geräten.
- Keine Planänderung ohne Bestätigung.

---

## 3. Datenlage (geprüft am 29.10.2026)

### 3.1 Quellen und Rollen

| Quelle | Rolle | Was wir daraus nehmen |
|---|---|---|
| **Garmin Personal API** (read-only) | Aktivitäten, Gewicht | Aktivitäten + Original-FIT, Gewicht; Schlaf/HRV nur als Fallback |
| **intervals.icu API** | Zepp/Amazfit, Kalender, Zonen | Schlaf, HRV, RHR, Zepp-Aktivitäten, Events, Sport-Settings, FTP/LTHR/Schwellenpace |
| **Manuell** | Subjektiv | Check-in (Soreness, Fatigue, Mood, Stress), RPE nach Einheit, Constraints (Reise, Schmerz) |

### 3.2 Wichtige Befunde

- **Garmin-Sperre:** Garmin hat die Partnerbedingungen geändert. intervals.icu rechnet damit, Garmin-Daten künftig nicht mehr über seine API ausliefern zu dürfen (analog Strava). Final ist das noch nicht; auch der Workout-Upload zu Garmin ist offen. Quelle: [API-Thread](https://forum.intervals.icu/t/api-access-to-intervals-icu/609).
  **Konsequenz:** Garmin-Aktivitäten lesen wir direkt über die Personal API. intervals.icu bleibt der Schreib-/Kalenderkanal.
- **Garmin Personal API:** seit Oktober 2026 für Einzelpersonen, Key in Garmin Connect → Settings → Personal API, Token-Tausch, **read-only**, volle FIT-Dateien (identisch zum manuellen Export). Quellen: [Garmin Docs](https://developer.garmin.com/gc-developer-program/personal/personal-api), [Python-Client](https://github.com/garmin/connect-personal-api-python).
- **Zepp/Amazfit:** native intervals.icu-Integration; Aktivitäten + Wellness (Schlaf, RHR, inzwischen auch HRV), **kein Gewicht**. Quelle: [Ankündigung](https://forum.intervals.icu/t/amazfit-zepp-support-available/107652).
- **intervals.icu API:** Basic Auth (`API_KEY` + Key), Athlete-ID `0` = eigener Account, 5.000 Requests/Tag, 2.500 pro 15 min, Cloudflare blockt `Python-urllib`-User-Agent. Quelle: [Doku](https://intervals.icu/api-docs.html), [Rate Limits](https://forum.intervals.icu/t/api-access-to-intervals-icu/609).
- **Workout-Upload:** `POST /api/v1/athlete/0/events/bulk?upsert=true` mit `external_id` ist idempotent; der Workout-**Text** wird serverseitig geparst (`workout_doc`, `icu_training_load`). Quelle: [Guide](https://forum.intervals.icu/t/uploading-planned-workouts-to-intervals-icu/63624).

### 3.3 Konsequenz für die Architektur

Weil die Geräte-Rollen klar sind (Helio 24/7, Garmin nur im Training), ist die Aufteilung günstig:

- **Erholung** (Schlaf, HRV, RHR) kommt von Zepp über intervals.icu — dieser Weg ist von der Garmin-Sperre nicht betroffen.
- **Aktivitäten** kommen direkt von Garmin — damit sind wir unabhängig davon, ob intervals.icu sie später noch ausliefert.
- **Gewicht** kommt von Garmin (Zepp liefert es nicht).

---

## 4. Architektur

```
Garmin Connect ──Personal API (read-only)──┐
                                           ├──► Collector ──► SQLite + FIT-Archiv
intervals.icu ──REST (Zepp, Zonen, Kalender)┘         │
                                                      ├──► Metrics   (Analysieren/Bewerten)
                                                      ├──► Planner   (Plan erzeugen)
                                                      └──► Publisher ──► intervals.icu Kalender
                                                                          └──► Garmin/Zepp
```

### 4.1 Komponenten

| Komponente | Aufgabe | Technik |
|---|---|---|
| **Collector** | Ingest, Backfill, Dedupe, Normalisierung | Python, httpx, pydantic |
| **Store** | Eigene Wahrheit, Verlauf, Audit | SQLite (WAL), FIT-Dateien auf Volume |
| **Metrics** | CTL/ATL/TSB, ACWR, Erholung, Trends | Python, numpy/pandas, pytest-Goldens |
| **Planner** | Periodisierung, Wochen-/Tagesplan, Guardrails | Python, deterministisch, versioniert |
| **Publisher** | Events upserten, verifizieren, protokollieren | Python, intervals-Client |
| **Web** | Dashboard, Plan-Editor, Freigaben | React + Vite + TypeScript, ECharts |
| **API** | REST für Web, Auth lokal | FastAPI |
| **Scheduler** | Sync, Erholung, Wochenvorschlag | APScheduler im API-Container |

### 4.2 Stack

- Python 3.12, FastAPI, SQLModel, httpx, pydantic, numpy/pandas
- React 19, Vite, TypeScript, ECharts, Tailwind
- SQLite (eine Datei), Docker Compose (api/web), Volume für DB + FIT
- Tests: pytest (Metriken/Planner mit Golden-Datasets), Vitest (UI-Logik)

### 4.3 Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| D1 | Eigene DB ist die Wahrheit, nicht der API-Proxy | Garmin-Daten könnten aus der intervals-API verschwinden |
| D2 | Garmin direkt, Zepp über intervals.icu | jeweiliger kürzester, stabilster Weg |
| D3 | Regelkern deterministisch, LLM nur für Text | Nachvollziehbarkeit, Testbarkeit, Sicherheit |
| D4 | Freigabe statt Autopush | Verletzungsrisiko, Vertrauen |
| D5 | Docker auf NAS | Dauerbetrieb unabhängig vom Mac |
| D6 | IM = A-Rennen | 8 Wochen nach VCM reichen sonst nicht |
| D7 | Workout-Text senden, kein handgebautes `workout_doc` | bekannter Bug: leere FITs bei API-Docs |
| D8 | Erholung selbst rechnen | Zepp liefert keinen belastbaren Score |

---

## 5. Datenmodell (Entwurf)

```sql
athlete(id, name, tz, weight_kg, height_cm, birth_year)
goal(id, name, date, sport, priority, target_time_s, status)
phase(id, goal_id, name, start_date, end_date, focus)

activity(id, source, source_id, start_local, sport, sub_sport, name,
         duration_s, moving_s, distance_m, elevation_m,
         avg_hr, max_hr, avg_power, np, avg_pace, calories,
         load, load_method, intervals_activity_id, garmin_activity_id,
         raw_path, created_at)
activity_stream(activity_id, channel, encoding, data)

wellness_raw(date, source, field, value, payload_json)
wellness_day(date, hrv_ms, rhr, sleep_s, sleep_deep_s, sleep_rem_s,
             sleep_score, respiration, spo2, stress, body_battery,
             weight_kg, subjective_json, quality, updated_at)
recovery_day(date, score, band, components_json, drivers_json,
              confidence, model_version)

plan(id, goal_id, created_at, status)
plan_version(id, plan_id, rev, reason, diff_json, approved_at)
session(id, plan_version_id, date, sport, type, name, description,
        duration_s, load_target, intensity_target, locked, status,
        intervals_event_id, external_id)
session_actual(session_id, activity_id, compliance_json)

sync_run(id, source, started_at, finished_at, status, stats_json, error)
push_log(id, session_id, external_id, action, http_status, response_json, verified)
setting(key, value_json)
```

**Dedupe:** gleicher Sport, Startzeit ±3 min, Dauer ±5 % → ein Datensatz. Garmin gewinnt bei Aktivitäten, Zepp bei Schlaf/HRV, Garmin bei Gewicht.

---

## 6. Metriken

### 6.1 Belastung

| Kennzahl | Definition | Zweck |
|---|---|---|
| **Load** | `icu_training_load` aus intervals; falls nicht verfügbar: TSS aus NP/FTP, sonst hrTSS | einheitliche Lastbasis |
| **CTL** | EWMA 42 Tage | Fitness |
| **ATL** | EWMA 7 Tage | Ermüdung |
| **TSB** | CTL − ATL | Form |
| **ACWR** | Load 7 d / Load 28 d | Sprünge erkennen |
| **Monotonie** | Mittel(Tageslast 7 d) / SD(Tageslast 7 d) | „jeden Tag mittel" |
| **Strain** | Wochenlast × Monotonie | Belastungsspitze |

### 6.2 Erholung (0–100)

Teilscores 0–100, gewichtetes Mittel **ohne Renormierung**: fehlt ein
Pflichtsignal, entsteht kein Wert (D-26). Bewertet wird die letzte vollständige
Nacht; die Referenz sind die eigenen letzten **60 Kalendertage** (mindestens 5
gültige Nächte, D-88). **Training fließt nicht direkt ein** (Bevel-Logik).

| Input | Gewicht | Basis |
|---|---|---|
| HRV | 35 % | Tageswert gegen den 60-d-Median (Median/MAD, Mindeststreuung) |
| Ruhepuls | 25 % | dito, invertiert |
| Schlaf | 30 % | 60 % Dauer gegen Sleep Need/Ziel, 25 % Wachheit, 15 % Phasen; ohne Phasen 70/30 |
| Atmung | 10 % | 60-d-Median, invertiert |

Skala: `80 + 16·z` unter dem Üblichen, `80 + 10·z` darüber, geklemmt auf 0–100.
Bänder: 85/70/55/40 (provisorisch). Vier Warnregeln senken den Score um
insgesamt höchstens 15 Punkte (D-89). SpO₂ und Body Battery sind nicht im Score.
Garmin-Sleep-Score und Schlafkonsistenz zählen nicht.

Anzeige: je Signal **heute / Schnitt / üblich**, „Nacht vom …“, Referenz x/60,
plus ein Satz, der den Score erklärt. Fachbegriffe (CTL, ATL, TSB, ACWR)
erscheinen nicht in der UI.

Ausgabe: Score, Band, **Treiber** und **Erklärung**; ohne Score die Nachtwerte
(D-58).

### 6.3 Wirkung und Fortschritt

- **Compliance:** |Ist-Last − Soll-Last| / Soll-Last, plus Zonenzeit im Zielbereich.
- **EF:** Geschwindigkeit/HR (Lauf) bzw. Power/HR (Rad), rollierender 28-d-Median auf Z2-Einheiten.
- **Decoupling:** Drift EF erste vs. zweite Hälfte langer Einheiten.
- **Best Efforts / CP:** aus intervals-Power-Curves bzw. lokal aus Streams.
- **Verteilung:** Zeit in Zonen, Polarisation (80/20).

### 6.4 Datenqualität

Jeder Tag bekommt ein Qualitätsflag (0–1) und ein Alter pro Feld. Die UI zeigt „Datenstand: heute 05:12" bzw. „Zepp-Daten fehlen seit 2 Tagen".

---

### 6.5 Verpflegung

Eigener Rechenweg, unabhängig von der Erholung: **wie viele Kohlenhydrate, wie
viel Wasser, wie viel Salz** – und was daraus konkret einzupacken ist.

- **Zwei Modi:** `locker` (Long Run, Zone 2) und `race` (Wettkampf).
- **Bänder nach Dauer**, Mitte des Bandes, nicht das obere Ende:
  < 45 min 0 · 45–75 min 22 · 75–120 min 45 · 2–3 h 60 · 3–4 h 75 · > 4 h 82 g/h.
  Modusfaktor 0,75 bzw. 1,10, Deckel **90 g/h**.
- **Zwei Türen:** SGLT1 ≈ 60 g/h Glukose, GLUT5 ≈ 30 g/h Fruktose. Über 60 g/h
  nur als Mischung, sonst bleibt der Rest im Darm.
- **Aufteilung:** rund die Hälfte über das Getränk (Konzentration ≤ 8 %), der
  Rest über Gels. Daraus entstehen Zeitplan und Einkaufsliste.
- **Wasser und Salz** skalieren mit Dauer und Temperatur; Wasser bleibt unter
  der Schweissrate (Hyponatriämie).
- **Gewicht** zählt nur für Vortag, Frühstück und Mahlzeit danach.

Modul: `src/trainings_cockpit/fuel.py`, Endpunkt `GET /api/fuel`.

## 7. Planungslogik

### 7.1 Makro

- Rückwärts von den Renndaten: Phasen Base → Build → Peak → Taper.
- Ein **A-Rennen** bekommt eine volle Periodisierung; B-Rennen werden eingebettet (kein eigener Taper-Block); C-Rennen sind Trainingsreize.
- Lastziel pro Woche: CTL-Rampe +3–5 Punkte, harte Obergrenze +8 % Wochenlast.

### 7.2 Meso (Woche)

- 3:1-Rhythmus, jede 4. Woche Deload (−35 %).
- Maximal 2 Qualitätseinheiten, ≥ 48 h Abstand.
- Lange Einheit am Wochenende, Kraft an Nicht-Schlüsseltagen.
- Wochenlast wird auf die verfügbaren Tage verteilt, nicht umgekehrt.

### 7.3 Mikro (Tag)

| Erholung | Anpassung |
|---|---|
| ≥ 70 | Plan wie geplant |
| 50–69 | Intensität raus, Volumen −20 % |
| 35–49 | nur Z1/Z2 locker oder Ruhetag |
| < 35 / krank | Ruhetag, Einheit verschieben |

Jede Anpassung ist ein **Vorschlag mit Begründung**; der Plan of record bleibt unverändert, bis freigegeben.

### 7.4 Guardrails (hart)

- CTL +3–5/Woche, Wochenlast +≤ 8 % (Rückkehr nach Pause +≤ 5 %).
- Deload jede 4. Woche, Taper −25 % / −40 %.
- Max. 2 Qualitätseinheiten, ≥ 48 h zwischen harten Reizen.
- Kein Schlüsselreiz bei Erholung < 50, kein neuer Reiz in der Rennwoche.
- Schmerz/Verletzung → Impact raus, Arzthinweis.
- 21-h-Wochen sind eine **Obergrenze**, kein Ziel: nur wenn die Vorgeschichte sie trägt.

### 7.5 Session-Bibliothek

Je Sport und Typ (Z2, Tempo, Schwelle, VO2, Long, Brick, Technik, Kraft A/B) eine Vorlage mit Ziel, Dauer, Intensität und „Warum". Der Planer füllt Parameter, nicht Prosa.

---

## 8. Saison 2027

| Datum | Rennen | Priorität | Ziel |
|---|---|---|---|
| So 18.04.2027 | Vienna City Marathon | **B** | kontrolliert, MP +10–15 s/km, kein All-out |
| So 13.06.2027 | IRONMAN Kärnten-Klagenfurt | **A** | Finish stark, Zeit nebensächlich |
| So 26.09.2027 | Wörthersee Marathon | **A-** | zweiter Höhepunkt nach kurzem Block |

**Der Konflikt:** 8 Wochen zwischen VCM und IM. Ein All-out-Marathon kostet 3–4 Wochen Erholung; dann blieben 4–5 Wochen IM-spezifisch. Deshalb VCM als B-Rennen.

| Zeitraum | Block | Fokus |
|---|---|---|
| Nov–Dez 2026 | Off-Season | Kraft 2×, Technik, Z2, Rad/Schwimmen locker |
| Jan–Feb 2027 | Basis | Laufumfang, Long Runs 20–25 km, 2× Rad, 2× Swim, Kraft 2× |
| Mär–18. Apr | Marathon-spezifisch | MP-Blöcke, Long Runs 30–35 km; Rad/Swim als Erhalt |
| 19. Apr–3. Mai | Regeneration | locker, kein Qualitätsreiz |
| 4. Mai–13. Jun | IM-spezifisch | Long Rides 4–5 h, Koppelläufe, 3× Swim, Lauf kurz |
| 14. Jun–5. Jul | Transition | Erholung, Kraft zurück |
| 6. Jul–16. Aug | Marathon-Basis | Umfang, Long Runs, Kraft 2× |
| 17. Aug–26. Sep | Marathon-spezifisch | MP-Blöcke, Taper |
| Okt–Dez | Off-Season | — |

**Belastbarkeits-Check:** aktuell ~12 h/Woche, geplanter Peak ~21 h. Für das Profil (HM 2:20, Oly 2:47, wenig Rad) ist 21 h sportlich sehr hoch. Der Planer prüft die tatsächliche CTL-Historie und kappt, wenn die Rampe nicht tragbar ist. Ziel ist ein stabiles Finish, nicht die maximale Wochenstundenzahl.

---

## 9. intervals.icu-Integration

### 9.1 Lesen

```
GET /api/v1/athlete/0/activities?oldest=2026-01-01&newest=2026-10-29
GET /api/v1/athlete/0/wellness?oldest=...&newest=...
GET /api/v1/athlete/0/events?oldest=...&newest=...
GET /api/v1/athlete/0/sport-settings
```

Auth: Basic, User `API_KEY`, Passwort = Key. Athlete `0` = eigener Account.
Header: browserähnlicher `User-Agent` (Cloudflare), `Accept: application/json`.

### 9.2 Schreiben

```
POST /api/v1/athlete/0/events/bulk?upsert=true
[{
  "category": "WORKOUT",
  "start_date_local": "2027-01-12T00:00:00",
  "type": "Ride",
  "name": "VO2 4x4",
  "description": "- 15m 60%\n\n4x\n- 4m 115%\n- 4m 50%\n\n- 10m 55%",
  "moving_time": 3600,
  "target": "POWER",
  "external_id": "tc:2027-W02:2027-01-12:ride-vo2:r1"
}]
```

- `external_id` = `tc:<woche>:<datum>:<session>:<rev>` → idempotent, Updates ohne Duplikate.
- `type` muss dem intervals-Sportnamen entsprechen (`Ride`, `Run`, `Swim`, `WeightTraining`, …).
- Danach **verifizieren**: Event per `GET` zurücklesen, `workout_doc.steps` nicht leer, `icu_training_load` gesetzt. Fehlschläge landen sichtbar im Push-Log.
- Löschen nur über `PUT /events/bulk-delete` und nur nach Bestätigung.

### 9.3 Betriebsgrenzen

- 5.000 Requests/Tag, 2.500/15 min → Collector cached, Backfill in Batches.
- 429 → `Retry-After` respektieren, exponentielles Backoff.
- Kein Polling im Sekundentakt; Sync 2×/Tag + manueller Button.

### 9.4 Garmin

- Key-Erneuerung: 30 Tage bis 1 Jahr; Erinnerung 7 Tage vor Ablauf, „Key erneuern"-Flow.
- Falls intervals.icu Workouts nicht mehr zu Garmin pusht: FIT-Export pro Einheit + manueller Import (Phase-0-Befund entscheidet).

---

## 10. Oberfläche

| Seite | Inhalt |
|---|---|
| **Heute** | Erholung mit Klartext-Erklärung + Treibern, Countdowns, Tageseinheit, 7-Tage-Ausblick |
| **Woche** | Wochenplan, Soll/Ist-Last, Diff zum Vorschlag, Freigeben/Ablehnen, Einheiten sperren |
| **Verpflegung** | Modus, Dauer, Gewicht, Temperatur → g/h, Getränk, Gels, Wasser, Salz, Zeitplan, Einkaufsliste |
| **Trends** | *ausgesetzt seit 31.10.2026 (D-13)* – CTL/ATL/TSB, ACWR, Wochenlast je Sport, HRV/RHR/Schlaf mit Baseline |
| **Review** | Einheit vs. Plan (Compliance, Zonen, Decoupling), Notizen, RPE |
| **Saison** | Ziele, Phasen, Countdown, Konflikte |
| **Einstellungen** | Quellen, Prioritäten je Feld, Zonen, Verfügbarkeit, Blackouts, Keys, Backup |

---

## 11. Betrieb

- Docker Compose: `api` (FastAPI + Scheduler), `web` (statisch via nginx), Volume `data/` (SQLite, FIT, Logs).
- Scheduler: 05:30 Sync + Erholung + Tagesvorschlag; 21:00 Sync; So 18:00 Wochenvorschlag.
- Secrets: `.env` mit `chmod 600` oder Docker-Secret; nie im Repo, nie im Chat.
- Backup: täglich SQLite-Kopie + FIT-Archiv, 30 Tage Rotation.
- Zugriff: nur LAN/VPN (Tailscale), kein Port im Internet.
- Healthcheck: `/health` prüft DB, letzter Sync, Key-Ablauf.

---

## 12. Risiken

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Garmin-Daten verschwinden aus intervals-API | Aktivitäten fehlen | Direktzugriff Garmin + eigene DB (D1) |
| intervals.icu pusht Workouts nicht mehr zu Garmin | Plan erreicht Uhr nicht | Phase-0-Test; Fallback FIT-Export |
| Zepp-Wellness wird nur bei Web-Besuch gepollt | morgens veraltete Daten | Phase-0-Messung; Sync-Zeit anpassen; Datenstand anzeigen |
| Zepp-HRV-Bugs | Erholung wackelt | Fallback RHR + Schlaf + Subjektiv, Konfidenz anzeigen |
| Doppelte Aktivitäten | falsche Last | Dedupe-Regeln, Quellen-Priorität |
| 21-h-Peak überfordert | Übertraining/Verletzung | Guardrails, Erholung-Gating, Deload |
| n=1-Statistik | Scheinkorrelationen | Hinweise statt Kausalität, keine Auto-Regeln daraus |
| Key-Ablauf | Sync stoppt | Erinnerung + Healthcheck |

---

## 13. Etappen

**Phase 0 — Spike (Gate)**
Keys, 30/90 Tage Ingest, FIT-Download, ein Test-Workout pushen und verifizieren, Zepp-Verzögerung messen.
*Akzeptanz:* Befundpapier mit Go/No-Go je Kanal.

**Phase 1 — Datenschicht + Heute + Trends**
Collector, SQLite, Dedupe, Erholung, CTL/ACWR, Charts.
*Akzeptanz:* 90 Tage Daten sichtbar, Erholung erklärbar, Sync stabil über 7 Tage.

**Phase 2 — Planer + Woche + Push**
Periodisierung, Session-Bibliothek, Wochenvorschlag, Diff, Freigabe, Push + Verifikation.
*Akzeptanz:* Eine Woche wird vorgeschlagen, freigegeben, gepusht, auf der Uhr gesehen.

**Phase 3 — Automatisierung + Review + Briefing**
Scheduler, Compliance, LLM-Briefing und Constraint-Parsing.
*Akzeptanz:* Sonntagsvorschlag und Morgencheck laufen ohne Handgriff.

**Phase 4 — Feinschliff**
Erholung-Rückschreiben nach intervals.icu, mobile Ansicht, Benachrichtigungen.

---

## 14. Offene Punkte

1. **Garmin-Key** anlegen (Connect → Settings → Personal API) und lokal ablegen.
2. **Bestehender 21-h-Plan:** Woher kommt er, soll er importiert und bewertet werden?
3. **HM am 21.11.2026:** Zielzeit? (Erster Messpunkt für die Erholung-Logik.)
4. **Kraft-Katalog:** Übungen an Ringen + Zusatzgewicht für die Session-Bibliothek.
5. **Benachrichtigungen:** Telegram, ntfy oder E-Mail?
