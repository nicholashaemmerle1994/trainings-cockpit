# Phase 0 — Audit

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Status:** Audit abgeschlossen, **keine Codeänderung**
**Auftrag:** [`docs/design/AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 0
**Verbindlich:** [`DESIGN.md`](../../DESIGN.md) · **Optische Referenz:** [`cockpit-premium-reference.png`](cockpit-premium-reference.png) (Mockup, keine Datenquelle)

Gelesen wurden `README.md`, `DESIGN.md`, `docs/KONZEPT.md`, `docs/UI-REGELN.md` (Herkunftsnachweis), `docs/design/AGENT_MIGRATION.md`, die Oberfläche unter `web/src/` und die Recovery-Ausgabe in `src/trainings_cockpit/metrics.py`. Der Stand der Vorschau auf Port 8101 wurde zusätzlich aufgerufen und gesichtet.

---

## 0. Kurzfassung

- **Stack:** React 19 + TypeScript + Vite, ausgeliefert von FastAPI. Kein Router, keine State-Bibliothek, keine UI-Bibliothek, kein Diagramm-Paket. Eine Oberfläche, drei Blätter (Overlays).
- **Styling:** **ein globales CSS** (`web/src/styles.css`, 2.162 Zeilen) mit CSS-Variablen. Keine CSS Modules, kein Tailwind, kein CSS-in-JS.
- **Navigation:** Zwei Tabs („Heute", „Verpflegung") über `useState` in `App.tsx`. Ab 1001 px Seitenleiste, darunter feste Tableiste. Detailansichten sind Blätter, keine Routen. `pages/Activities.tsx` liegt unverlinkt im Code (D-39).
- **Reihenfolge der Startseite entspricht bereits dem Zielbild:** Kopf → Countdowns → Erholung → Training → Letzte 7 Tage → (mobil) Tabs.
- **Der kritische Zustand ist korrekt:** Solange die Referenz läuft, zeigt die Karte „Referenz wird aufgebaut", 2 von 21 Nächten und **keinen Score**. Dieser Zustand ist in jeder Phase zu schützen.
- **Größte technische Schulden:** eine Monolith-CSS-Datei mit überlagernden Regeln, vier Varianten derselben Kennzahlenzeile, zwei Navigationslisten, zwei Farbsysteme (CSS und `format.ts`), keine Frontend-Tests.
- **Empfehlung:** fünf kleine Phasen nach `AGENT_MIGRATION.md`; Phase 1 beginnt mit einer **Alias-Schicht** auf den bestehenden Tokens, nicht mit dem Umbenennen von 273 `var(--…)`-Verwendungen.

---

## 1. Tech-Stack, Styling und Navigation

### 1.1 Stack

| Bereich | Stand | Ort |
|---|---|---|
| UI | React 19.1, TypeScript 5.9 | `web/package.json`, `web/src/` |
| Build | Vite 7, `tsc --noEmit && vite build` → `web/dist` | `web/vite.config.ts`, `web/package.json` |
| Auslieferung | FastAPI mountet `dist/assets` und liefert `index.html` als SPA-Fallback | `src/trainings_cockpit/api.py` (ab Z. 250) |
| Styling | eine globale CSS-Datei, CSS Custom Properties | `web/src/styles.css` |
| Routing | **kein Router**; `useState<Tab>` (`today` \| `fuel`) | `web/src/App.tsx:23-30` |
| Detailansichten | Portal-Overlay `Sheet` + drei Blätter | `web/src/components/Sheet.tsx` |
| Zustand | `useState`/`useEffect` je Seite; kein Store | `App.tsx`, `Today.tsx`, `Fuel.tsx` |
| Icons | selbst gezeichnete Inline-SVGs, ein Strich (1,5), Größen 16–20 | `web/src/components/icons.tsx`, `sportIcon.tsx` |
| Diagramme | handgezeichnetes SVG (Ring, Wochenbalken, Verlauf, Zonenbalken) | `RecoveryDial`, `WeekStrip`, `WorkoutChart`, `SessionProfile`, `UnitSheet` |
| Schriften | selbst gehostet: Plex Sans, Plex Mono, Instrument Serif | `web/public/fonts/`, `styles.css:1-41` |
| PWA | Manifest, Icons, Vorschau-Variante über `VITE_APP_VARIANT` | `web/index.html`, `web/vite.config.ts`, `web/src/variant.ts` |
| Tests | nur Backend (pytest); **keine Frontend-Tests** | `tests/` |

**Keine neue Bibliothek** ist im Projekt vorhanden oder nötig: Charts und Icons sind bereits eigene, schlanke Lösungen. Ein Icon-Paket oder eine Chart-Bibliothek wäre eine neue Abhängigkeit und braucht Freigabe.

### 1.2 Styling-Ansatz

- **Globales CSS, keine Module.** Alle Klassen sind global; Komponenten tragen ihre Gestalt über Klassennamen (`.card`, `.dial`, `.train-row`, `.sheet-kv`). Das macht die Datei einfach zu lesen, aber anfällig für Kaskadenfehler (siehe 2.2).
- **Tokens nur teilweise:** `:root` (`styles.css:45-75`) definiert Farben, drei Schriftfamilien, `--ease` und zwei Radien (`--r-card: 14px`, `--r-control: 8px`). **Es gibt keine Abstands-, Typografie- oder Höhen-Tokens**; Padding, Schriftgrößen und Breakpoints stehen als Zahlen in den Regeln. `var(--…)` wird 273-mal verwendet.
- **Zwei Farbsysteme:** Die Erholungsfarben stehen als `--good/--mid/--low/--bad` im CSS (`styles.css:63-66`) **und** als Hex-Werte in `BAND_COLORS` (`web/src/format.ts:3-9`). `RecoveryDial` benutzt für die Zonen zusätzlich `var(--bad/--low/--mid/--good)` (`RecoveryDial.tsx:10-15`).
- **Inline-Styles nur für Dynamik** (6 Stellen): Position im Treiber-Track, Pull-to-Refresh, Ring-Transition, Skeleton-Höhe, Balkenhöhe, Zonenbreite. Das ist vertretbar; statische Gestaltung gehört ins CSS.
- **Responsive:** Breakpoints bei **1180 px** (Split stapeln), **1001 px** (Desktop-Seitenleiste), **1000 px** (Mobil, Tableiste, Listen umbauen), **720 px** (Blatt als Dialog). Die mobile Sammelregel liegt mitten in der Datei (Z. 1572–1742), danach folgen weitere Komponenten (Training, Blatt). Spätere Regeln überschreiben frühere — genau das passiert bei `.chip`.

**Abweichungen zu `DESIGN.md` (Phase 1):**

| Token | Ist | Soll (`DESIGN.md`) |
|---|---|---|
| Seitenhintergrund | `#08090f` | `#05090D` |
| Karte | `#11141c` | `#0D171D` |
| Akzent | `#3f9e8f` (gedämpft) | `#35DCC5` (satt) |
| Kartenradius | 14 px | 22 px |
| Control-Radius | 8 px | 12 px |
| Schrift | drei Familien (Sans, Mono, Serif) | System-UI + Serif **nur** fürs Datum |
| Zahlen | Plex Mono | System-UI mit `tabular-nums` |
| Abstände | freie px-Werte | 4-px-Raster mit `--space-*` |
| Kontrast | Text-3 auf Karte 4,79:1 (knapp AA) | mindestens 4,5:1, Ziel 5,6:1 (`--text-muted`) |

### 1.3 Navigationsstruktur

- **Zustand statt URL.** `App.tsx` hält `tab` im Speicher; ein Neuladen führt immer auf „Heute". Browser-Zurück wechselt nicht den Tab. Direkte URLs auf „Verpflegung" gibt es nicht. `DESIGN.md` (3.2) verlangt, dass Browser-Back und direkte URLs nicht brechen — heute gibt es schlicht keine Routen. Ein Router wäre eine Architekturänderung und damit **nicht** Teil dieser Migration (Entscheidung nötig, siehe 6).
- **Zwei Navigationsflächen, zwei Listen.** Mobil `.tabbar` (`App.tsx:145-157`, sichtbar nur ≤1000 px, `styles.css:1711-1742`), Desktop `Sidebar` (`Sidebar.tsx:26-64`, sichtbar ≥1001 px). Die Einträge stehen doppelt: `TABS` in `App.tsx:11-14` und `NAV` in `Sidebar.tsx:6-9`. Der Typ `Tab` lebt in `Sidebar.tsx:4`.
- **Aktiver Zustand:** Seitenleiste = Fläche `--raised` + helle Schrift; Tableiste = türkises Icon + helle Schrift. `aria-current="page"` fehlt in beiden.
- **Blätter:** `Sheet` (Portal, Escape, Scroll-Lock) → `SessionSheet` (geplante Einheit), `WeekSheet` (letzte 7 Tage), `UnitSheet` (erledigte Einheit). Sie öffnen keinen neuen Tab und sind gestapelt (`top`-Flag). Das entspricht `DESIGN.md` 3.2 („Detailansichten eröffnen keinen neuen Haupttab").
- **Unverlinkte Seite:** `pages/Activities.tsx` ist vollständig gebaut (Skelett, Leerzustand, Fehler, „Mehr laden"), aber seit D-39 nicht erreichbar. Sie bleibt liegen und wird in dieser Migration nicht reaktiviert.

---

## 2. Wiederverwendbare Bausteine und Duplikate

### 2.1 Bereits wiederverwendbar

| Baustein | Ort | Genutzt von | Bewertung |
|---|---|---|---|
| `Card` | `components/ui.tsx:3-30` | `Fuel.tsx` | Gute Basis für `DashboardCard`; die Startseite benutzt sie **nicht**, sondern baut den Kopf dreimal von Hand. |
| `Sheet` | `components/Sheet.tsx` | drei Blätter | Sauberer gemeinsamer Rahmen (Portal, Escape, Scroll-Lock, Dialog-Rolle). Unverändert weiterverwenden. |
| `Skeleton`, `EmptyState` | `components/ui.tsx:32-53` | nur `Activities.tsx` | Existieren, sind aber im erreichbaren UI ungenutzt. Kandidaten für Lade-/Leerzustände in Phase 2/5. |
| `sportIcon` | `components/sportIcon.tsx` | `Today.tsx`, `WeekSheet.tsx` | Eine Zuordnung für Liste und Blatt — genau richtig. |
| `format.ts` | `web/src/format.ts` | überall | Zentrale Formatierung; aber mit überlappenden Funktionen (siehe 2.2). |
| `BrandMark`, `PreviewTag` | `components/Brand.tsx` | `App`, `Sidebar` | Klein und klar; Vorschau-Kennzeichnung (D-56) nicht antasten. |
| `RecoveryDial` | `components/RecoveryDial.tsx` | `Today.tsx` | Fachlich richtig (kein Wert ohne Score). Wird zu `RecoveryGauge`, nicht ersetzt. |
| `WeekStrip` | `components/WeekStrip.tsx` | `Today.tsx` | Klein, ohne Bibliothek; Kandidat für `WeeklyActivityChart`. |
| `ActivityTable` | `components/ActivityTable.tsx` | nur `Activities.tsx` | Bleibt liegen (D-39). |
| `SessionProfile`, `WorkoutChart` | `components/` | Blätter | Eigene SVGs, `role="img"` + Label vorhanden. Nicht in dieser Migration anfassen, außer Farb-Tokens. |

### 2.2 Dupliziert oder widersprüchlich

1. **Kartenkopf dreimal von Hand** — `Today.tsx:97-111`, `313-318`, `182-187` wiederholen exakt das Markup von `Card` (`ui.tsx:17-27`). Ein `DashboardCard` behebt das.
2. **Kennzahlenzeile in vier Formen** — `.drivers` (Tabelle, `styles.css:638-678`), `.night-list` (`565-589`), `.week-row` (`812-863`), `.sheet-kv` (`2102-2117`), dazu `.plan-row` (`872-886`) und `.fuel-row` (`1289-1329`). Immer „Label links, Wert rechts, feine Trennlinie" — `DESIGN.md` 4.3 nennt das `MetricRow`.
3. **`.chip` ist zweimal definiert.** Einmal als Knopf (`styles.css:1096-1118`: 30 px hoch, `--r-control`, 12,5 px) und einmal als Status-Pille (`styles.css:1896-1905`: 24 px hoch, 6 px Radius, 11,5 px). Die spätere Regel gewinnt: **alle** Chips im Verpflegungsrechner sind effektiv 24 px hoch, also unter der 44-px-Touchfläche und nicht auf dem Control-Radius. Das ist ein konkreter Kaskadenfehler, kein Geschmacksthema.
4. **Zwei Navigationslisten** — `TABS` (`App.tsx:11-14`) und `NAV` (`Sidebar.tsx:6-9`). Jede Änderung muss doppelt erfolgen; ein gemeinsames Modul ist Phase 2.
5. **Status ohne gemeinsame Komponente** — „Geplant/Erledigt/Zusätzlich" als nackter Text (`.train-state`, `styles.css:1799`), als `.chip` im Blatt, als `.brand-tag` für die Vorschau, als `.mode-option` im Rechner. `DESIGN.md` 4.7 will `StatusBadge`.
6. **Farben doppelt** — `BAND_COLORS` in `format.ts:3-9` gegen `--good/--mid/--low/--bad` in `styles.css:63-66`; `#f0b4b4` zweimal (`styles.css:427`, `1487`); Hover `#4bb0a0` hart (`389`); Fehler-Rahmen als `rgba(207,91,91,…)` (`423-425`).
7. **`@keyframes shimmer` doppelt** — `styles.css:1415` und `2140` (identisch). Die zweite Definition ist toter Ballast.
8. **Drei Kopf-Idiome** — `.page-head` (Seiten), `.sheet-top`/`.sheet-title`/`.sheet-kind` (Blätter), Marke + Vorschau (Seitenleiste bzw. mobil im Inhalt). Ein `ScreenHeader` für die Seiten reicht; die Blätter behalten ihren eigenen Kopf.
9. **Fokus inkonsistent** — `:focus-visible` nur für `.btn`, `.nav button`, `.chip`, `.link-btn` (`styles.css:401-407`). Es fehlen u. a. `.train-row`, `.week-row-link`, `.mode-option`, `.tabbar button`, `.icon-btn`, `.side-sync`, die Range- und Zahlenfelder.
10. **Touchflächen unter 44 px** — `.nav button` 34 px (`styles.css:223`), `.side-sync` 34 px (`263`), `.chip` effektiv 24 px, `.week-row` ca. 35 px. `DESIGN.md` 2.4/6 verlangt mindestens 44 × 44.
11. **Zwei Zeitformate nebeneinander** — `fmtClock` und `fmtHours` formatieren dieselbe Uhrzeit, nur `fmtHours` hängt die Einheit an (`format.ts:30-42`); `fmtMinutes`, `fmtDuration` und `fmtSpan` überschneiden sich. `DESIGN.md` 5 will ein Format je Bedeutung.
12. **Keine Abstands-Tokens** — `padding: 20px`, `gap: 16px`, `font-size: 12.5px` usw. stehen über die Datei verteilt; das 4-px-Raster ist eingehalten, aber nicht zentral änderbar.

---

## 3. Fundstellen der geforderten Abschnitte

| Abschnitt | Markup | Gestalt | Daten |
|---|---|---|---|
| **Header** | `Today.tsx:75-80` (`.page-head`, Serif-Datum, „Zuletzt synchronisiert"), mobil zusätzlich `App.tsx:133-139` (Marke + Vorschau), Desktop `Sidebar.tsx:28-63` | `styles.css:343-372` (`.page-head`, `h1`, `.meta`), `296-315` (`.main`, `.preview-brand`) | `today.date`, `data.generated_at` |
| **Wettkampf-Countdown** | `Today.tsx:82-94` (`.countdowns`, bis zu drei `.countdown`) | `styles.css:430-472`; mobil `1605-1626` | `data.goals` (`name`, `days`) |
| **Erholung** | `Today.tsx:96-171` (`article.card.recovery`), `RecoveryDial.tsx`, `VendorScore.tsx` | `styles.css:504-760` (`.recovery`, `.dial`, `.drivers`, `.night`, `.note`, `.vendor`) | `today.recovery` (`score`, `band`, `label`, `components`, `reference`, `explanation`, `vendor_prompt`), `today.hrv/rhr/sleep` |
| **Training** | `Today.tsx:173-179` + `TrainingCard` `244-333` (`.train`, `.train-row`) | `styles.css:1744-1818` | `data.sessions` (`day: today/tomorrow`), `data.unplanned` |
| **Letzte 7 Tage** | `Today.tsx:181-217` (`.card.week`), `WeekStrip.tsx`, Drilldown `WeekSheet.tsx` | `styles.css:766-886` (`.week-strip`, `.week-bars`, `.week-row`) | `data.series.load`, `today.load.week_seconds/week_load/week_sessions/acwr`, `GET /api/week` |
| **Bottom Tabs** | `App.tsx:145-157` (`.tabbar`), Desktop `Sidebar.tsx:26-46` | `styles.css:1557-1559` (versteckt) und `1711-1742` (mobil sichtbar); Seitenleiste `154-251` | Tabs lokal, `tab`-State |

**Zusätzlich relevant:** `App.tsx:159-169` (Pull-to-Refresh), `171-175` (Popup), `180-197` (Splash), `Sheet.tsx` (Blattrahmen), `styles.css:1822-2162` (Blätter), `web/scripts/audit-shots.mjs` (Screenshot-Werkzeug).

---

## 4. Zustände der Screens

### 4.1 Erholung — der fachlich kritische Bereich

Die API liefert vier unterscheidbare Fälle (`metrics.py:172-323`); die Oberfläche muss alle vier erhalten:

| Fall | API | Anzeige heute | Zu bewahren |
|---|---|---|---|
| **Referenz wird aufgebaut** | `score: null`, `label: "Referenz wird aufgebaut"`, `components: []`, `reference.nights < minimum` | Karte: „Neuer Sensor · 2 von 21 Nächten"; Ring mit „—", Label, Referenzzeile; darunter HRV/Ruhepuls/Schlaf der letzten Nacht (D-58); Erklärsatz; ggf. Bevel-Feld | **Kein Score, kein positiver Status, kein grüner Ring.** Text und Nachtwerte bleiben. |
| **Pflichtsignal fehlt** | `score: null`, `label: "Keine Daten"`, `components: []`, `missing: [ … ]`, Erklärung nennt das Signal | Ring „—", Label „Keine Daten", Untertitel „Wartet auf die Nacht"; Nachtwerte, soweit vorhanden, sonst „—"; Erklärsatz | Kein Teilwert, keine Renormierung (D-26). `missing` und `confidence` werden **nicht** gerendert. |
| **Vollständig** | `score`, `band`, `label` („Gut erholt", „Solide", „Erholungsbedarf", „Ruhetag"), Treiber, `reference` | Score im Ring, Bandfarbe, Treibertabelle (heute/Schnitt/üblich), Referenzmarke, Erklärsatz, ggf. Bevel-Abgleich | Treiberzeile und Erklärung sind der Wert; die Zahl allein reicht nicht. |
| **Einzelwert fehlt** innerhalb der Nachtwerte | `null` je Feld | „—" je Zeile (`valueWithUnit`) | Nicht auffüllen, nicht schätzen. |

**Visuelles Risiko:** `RecoveryDial` zeichnet die vier farbigen Zonenbögen **immer** (`RecoveryDial.tsx:60-75`, Deckkraft 0,3), auch ohne Score. Die farbigen Bögen allein könnten wie ein Status wirken. `DESIGN.md` 4.4 verlangt ohne Referenz ein neutrales Ringskelett. Das ist in Phase 3b zu lösen — ohne die Zahl zu erfinden.

**Referenztext:** `Today.tsx:59-67` leitet den Text in fünf Zweigen aus `reference` und dem 21-Tage-Schnitt ab. Das ist korrekt, aber fragil; Kandidat für eine kleine, getestete Hilfsfunktion in Phase 2.

### 4.2 Übrige Zustände

| Zustand | Wo | Verhalten heute | Lücke / Risiko |
|---|---|---|---|
| **Erstes Laden** | `App.tsx:115-117`, `180-197` | Splash mit Marke, „Daten werden geladen…"; darunter die ganze Seite erst nach Antwort | Kein Skelett in Kartenform, also Layoutsprung. `Skeleton` existiert, wird aber nicht genutzt. |
| **Fehler beim ersten Laden** | `Splash` | Meldung + „Erneut versuchen" | Gut. |
| **Fehler nach dem Laden** | `App.tsx:140` (`.banner`) | Rote Leiste über der Seite; verschwindet beim nächsten erfolgreichen Laden | Kein Wiederholen-Knopf, keine Quelle. `DESIGN.md` 5 will eine konkrete Aktion. |
| **Sync läuft** | `App.tsx:54-68`, `Sidebar.tsx:48-55`, Pull-Toast | „Synchronisiert…", Toast „Aktualisiert HH:MM" | Gut; Toast-Zeit kommt aus dem Datensatz, nicht aus der Geräteuhr (Kommentar Z. 60). |
| **Sync veraltet** | `Today.tsx:68-71`, `Sidebar.tsx:53-63` | Nur Uhrzeit („Zuletzt synchronisiert 14:15", „Sync 14:15") | **Kein Datum, kein Alter, keine Warnung.** Ein Sync von vorgestern sieht aus wie von heute. `DESIGN.md` 5 verlangt den Zustand „Sync veraltet". |
| **Training leer** | `TrainingCard` `Today.tsx:320-321` | „Für heute steht nichts im Plan."; morgen wird gezeigt, wenn bekannt | Entspricht `DESIGN.md` 4.5 („keine erzwungene leere Grafik"). |
| **Zusätzliche Einheit** | `Today.tsx:288-309` | Zeile mit „Zusätzlich" | Korrekt (D-43); Status ist aber nur Text. |
| **Letzte 7 Tage, keine Last** | `WeekStrip.tsx:15-33` | Balken mit Höhe 0 (`min-height: 3px` im CSS) | Kein Empty State; die Achse bleibt stehen, was richtig ist. Null ≠ fehlender Tag ist im Diagramm nicht unterschieden. |
| **Blätter laden/fehlern** | `SessionSheet`, `WeekSheet`, `UnitSheet` | `.sheet-loading`-Fläche bzw. `.sheet-error` | Gut; Fehler ohne Wiederholen. |
| **Woche leer** | `WeekSheet.tsx:105` | „Keine Einheit in diesen sieben Tagen." | Gut. |
| **Verpflegung** | `Fuel.tsx:35-64`, `75` | Während des Rechnens bleibt das letzte Ergebnis stehen; Fehler als Banner; keine Ladeanzeige, kein Empty State | Die Eingaben sind bewusste Standardwerte, keine erfundenen Messdaten. Fehlerzustand nicht gestaltet. |
| **Aktivitäten** | `Activities.tsx:63-91` | Skelett, Leerzustand, Fehler, „Mehr laden" | Seite ist unverlinkt (D-39) — nicht reaktivieren, nicht löschen. |
| **Offline** | — | Nicht behandelt; `fetch`-Fehler landen im Splash oder Banner | Kein „letzter bestätigter Stand mit Zeitstempel". `DESIGN.md` 5 nennt den Zustand. |
| **Teilweise Daten** | — | Für die Ladung existiert kein Teilzustand; Nachtwerte können einzeln fehlen | Einzelne „—" sind vorhanden; `recovery.missing` bleibt ungenutzt. |

### 4.3 Bewegung und Barrierefreiheit

- `prefers-reduced-motion` ist für `.page` (`styles.css:335-339`) und `.skeleton` (`1424-1428`) gesetzt. **Nicht** abgedeckt: Ring-Transition (`RecoveryDial.tsx:91`, 700 ms inline), `.sheet-loading` (`2131-2138`), `.popup` (`1514`), `.pull` (`1548`). `DESIGN.md` 6/8 will eine globale Regel.
- `aria-current="page"` fehlt an beiden Navigationsflächen; die Tabbar-Buttons haben kein zusätzliches Label (Text ist sichtbar, das genügt).
- Diagramme: `RecoveryDial`, `SessionProfile`, `WorkoutChart` haben `role="img"` und ein Label; `WeekStrip` hat **nur** `title` an den Balken, keine zugängliche Zusammenfassung.
- Blätter: `role="dialog"`, `aria-modal` und Escape sind vorhanden; der Fokus wird nicht auf den Schließen-Knopf gesetzt und nicht im Blatt gefangen. Für Phase 4 vormerken.

---

## 5. Migrationsplan in kleinen Phasen

Reihenfolge nach `AGENT_MIGRATION.md`: Tokens → Bausteine → Startseite → Navigation → Qualität. Nach **jeder** Phase Stopp und Abnahme. Keine Phase fasst `src/`, `api.ts`, `types.ts`, Sync, DB oder Berechnungen an.

### Phase 1 — Tokens und Basis-Styles

**Ziel:** `DESIGN.md`-Werte zentral verfügbar machen, ohne Layout oder Markup zu ändern.

**Dateien:**
- `web/src/styles.css` — `:root` um `--space-1…8`, `--radius-*`, `--bg-app/--bg-surface/…` ergänzen; **Alias-Schicht** `--bg: var(--bg-app)`, `--card: var(--bg-surface)`, `--raised: …`, `--line: …`, `--text: …`, `--text-2/3: …`, `--accent: …`. Bestehende Namen bleiben zunächst stehen, damit die 273 Verwendungen nicht brechen.
- `web/src/format.ts` — `BAND_COLORS` auf `var(--positive/--warning/…)` umstellen (wird als Inline-`stroke`/`color` benutzt, `var()` funktioniert dort).
- `web/index.html` — `theme-color` an `--bg-app` angleichen.
- Schriften: Entscheidung vor der Umsetzung (siehe 6, Punkt 1). Bei „System-UI + Serif" nur die Font-Stacks in `:root` ändern, `@font-face` und Dateien vorerst behalten.

**Reihenfolge:** Aliase → Farben → Radien/Abstände → Typografie → Kontrast messen → Screenshots.

**Risiko:** Umbenennen statt aliasen bricht hunderte Regeln. Fontwechsel ändert Zeilenlängen, Tabellen und Diagramm-Labels. Akzentwechsel kann die 0,3-transparenten Ringzonen anders wirken lassen.

**Nicht in Phase 1:** Markup, Komponentenstruktur, Breakpoints, Abstände umbauen.

### Phase 2 — Gemeinsame UI-Bausteine

**Ziel:** `DashboardCard`, `ScreenHeader`, `MetricRow`, `StatusBadge`, `WorkoutPreview`, gemeinsame Navigation und Icon-Stil — „ohne alles zu abstrahieren" (`AGENT_MIGRATION.md` 46-49).

**Dateien:** `components/ui.tsx` (ausbauen), `styles.css` (Konsolidierung), `App.tsx` + `Sidebar.tsx` (gemeinsame Tab-Liste), `Today.tsx` (Kartenköpfe auf `Card`), `Fuel.tsx` (Chips/Status), `WeekSheet.tsx`, `SessionSheet.tsx`, `UnitSheet.tsx` (nur Zeilen/Status, keine Inhalte).

**Schritte:**
1. `Card` → `DashboardCard` (Titel/Untertitel/Action) und in `Today` einsetzen; dreifachen Kopf ersetzen.
2. `MetricRow`/`MetricGroup` einführen; `.night-list`, `.week-row`, `.sheet-kv` darauf abbilden. **Ausnahme:** die Treibertabelle `.drivers` bleibt eine Tabelle mit Track — sie ist laut `DESIGN.md` 4.3 eine zulässige Sonderform.
3. `StatusBadge` für „Geplant/Erledigt/Zusätzlich/Ausgefallen"; `.train-state` und Blatt-`.chip` darauf umstellen.
4. `.chip`-Doppeldefinition auflösen (Knopf ≠ Pille), Touchfläche ≥44 px, Fokusring für alle interaktiven Elemente.
5. `shimmer` einmal definieren; Leerzustände aus `ui.tsx` in den erreichbaren Fluss holen, wo sinnvoll.
6. `TABS`/`NAV` in ein Modul ziehen; `aria-current` ergänzen.
7. `WorkoutPreview` als Zeile (nicht als zweite Karte) aus `TrainingCard` herauslösen; `WeekSheet` nutzt dieselbe Zeile.

**Risiko:** Zu frühe Abstraktion. Die Blattzeilen (`.sheet-kv`, `.sheet-row`) sind Grids mit drei Spalten; eine zu breite `MetricRow` würde sie verbiegen. Jede Umstellung einzeln prüfen (Startseite **und** Blätter).

### Phase 3 — Cockpit-Startseite (ein Abschnitt pro Freigabe)

**3a Header + Countdowns** — `Today.tsx:74-94`, `styles.css:343-472`, `1605-1626`. `ScreenHeader` einführen; Produktkennung, Datum, Sync-Zeit zusammenführen; Countdowns als ruhige Spalten mit Trennlinien. Risiko: drei Ziele bei 320 px (Umbruch statt Abschneiden).

**3b Erholung** — `Today.tsx:96-171`, `RecoveryDial.tsx`, `VendorScore.tsx`, `styles.css:504-760`. Karte als wichtigstes Element; Score/Nachtmetriken/Hinweis in der Hierarchie der Referenz. **Ohne gültige Referenz:** neutrales Ringgerüst + „Referenz wird aufgebaut" + „2 von 21 Nächten"; farbige Zonenbögen nur mit Score. Nachtwerte bleiben sichtbar (D-58), Bevel-Zeile bleibt im Vergleichsfenster (D-52). **Höchstes Risiko der ganzen Migration.**

**3c Training** — `Today.tsx:173-179`, `244-333`, `styles.css:1744-1818`. Ein Tagesstatus, nächste Einheit als Vorschau, Status-Chip; Empty State und „Morgen" bleiben.

**3d Letzte 7 Tage** — `Today.tsx:181-217`, `WeekStrip.tsx`, `WeekSheet.tsx`, `styles.css:766-886`. Balken ruhiger, heutiger Tag türkis nur wenn sachlich richtig; Summen als `MetricRow`; Drilldown unverändert.

Jeder Teilschritt: Screenshot 390 px + Desktop, Diff, kurze Erklärung, **Stopp**.

### Phase 4 — Navigation und Feinschliff

**Dateien:** `App.tsx` (Tabbar), `Sidebar.tsx`, `styles.css` (Tabbar/Seitenleiste/Fokus/Safe-Areas), `icons.tsx`/`sportIcon.tsx` (nur falls eine Größe/Strichweite vereinheitlicht wird), `web/scripts/audit-shots.mjs` (Werkzeug, siehe 6).

- Aktiver Tab: türkises Outline-Icon + helles Label, **kein** breiter Glow; `aria-current="page"`.
- Eine Tab-Liste, zwei Darstellungen; Touchflächen ≥44 px; Fokus sichtbar; Safe-Area unten; Scrollinhalt hat genug Platz.
- Prüfen bei 320/390/430 px und Desktop; dokumentieren, was auffällt.

**Risiko:** Zwei Navigationsimplementierungen gleichzeitig ändern. Erst die gemeinsame Liste, dann die Gestalt, dann die Barrierefreiheit — je ein Schritt.

### Phase 5 — Qualitätsprüfung und Dokumentation

- Alle Zustände aus 4.1/4.2 durchspielen: Laden, kein Workout, fehlende Nachtwerte, Referenzaufbau, Sync alt, API-Fehler. Für „Sync veraltet" und „Offline" ist eine **Entscheidung** nötig, ob sie in dieser Migration entstehen (siehe 6).
- 320/375/390/430 px + Desktop, Tastatur, Screenreader-Labels, Kontrast nachmessen, `prefers-reduced-motion` global.
- `npm run build`, `uv run pytest`, `node web/scripts/audit-shots.mjs`; Screenshots vorher/nachher.
- `DESIGN.md` nur ergänzen, wenn tatsächlich nötig; Abweichungen dort festhalten.

**Reihenfolge insgesamt:** Tokens zuerst, weil sonst jede spätere Phase gegen wechselnde Farben prüft. Die Startseite vor der Navigation, weil die Tabbar auf dem fertigen Layout beurteilt werden muss. Qualität zuletzt, weil sie alle Zustände braucht.

---

## 6. Risiken und offene Entscheidungen

| # | Thema | Warum es eine Entscheidung braucht | Vorschlag |
|---|---|---|---|
| 1 | **Schriften** | `DESIGN.md` 2.3 verlangt System-UI + Serif nur fürs Datum; das Projekt hat Plex Sans/Mono/Serif selbst gehostet und nutzt Mono für alle Zahlen. Das ist der sichtbarste Unterschied zur Referenz. | Vor Phase 1 entscheiden: (a) System-UI + Serif wie `DESIGN.md`, Plex-Dateien bleiben ungenutzt liegen; oder (b) Plex als bestehende „Systemschrift" dokumentierte Abweichung. Empfehlung: (a), weil `DESIGN.md` bindend ist — aber nur nach ausdrücklicher Freigabe, weil es den ganzen Look ändert. |
| 2 | **Seitenleiste vs. Bottom-Navigation** | `DESIGN.md` 3.2 beschreibt eine Bottom-Tabbar; auf Desktop gibt es eine Seitenleiste (248 px). | Als responsive Variante behalten und in `DESIGN.md` als bewusste Abweichung notieren. Kein Umbau ohne Freigabe. |
| 3 | **Kein Router** | `DESIGN.md` 3.2 verlangt funktionierendes Browser-Back und direkte URLs. Heute gibt es keine Routen; ein Router wäre Architektur **und** ggf. neue Abhängigkeit. | Zustand beibehalten (Auftrag: Routing bleibt bestehen). Abweichung dokumentieren. Router nur als eigenes Ticket. |
| 4 | **`missing` und `confidence`** | Die API liefert beides, die UI nutzt es nicht. `DESIGN.md` 5 will fehlende Signale explizit markieren; die Erklärung nennt sie bereits im Satz. | Keine neue Anzeige in Phase 1/2. In Phase 3b prüfen, ob ein kurzes „Fehlt: Atmung" die Karte verbessert — ohne neue Logik. |
| 5 | **Referenzgrafik widerspricht den Regeln** | Das Mockup zeigt einen fertigen Score samt positivem Status, obwohl im selben Bild nur 2 von 21 Nächten vorliegen. Diese Kombination darf das Produkt nie zeigen. | Nur die visuelle Sprache übernehmen (Ring, Karten, Typografie, Abstände), **nie** den Zustand. Der Zustand kommt ausschließlich aus `recovery.score`/`reference`. Keine Zahl aus dem Mockup. |
| 6 | **Sync veraltet / Offline** | Beide Zustände fehlen; `DESIGN.md` 5 nennt sie. Sie zu bauen ist UI, aber sie brauchen eine definierte Datenquelle (Alter aus `generated_at` genügt). | In Phase 5 entscheiden: „Alter aus `generated_at`" ist reine Darstellung und ohne API-Änderung möglich. Wenn gewünscht, dort umsetzen. |
| 7 | **Aktivitäten-Seite** | Vollständig, aber unverlinkt (D-39). | Liegen lassen. Nicht löschen, nicht verlinken, nicht gestalten. |
| 8 | **Cascade-Risiko** | Eine Datei, 2.162 Zeilen, mobile Sammelregel in der Mitte, `.chip` und `shimmer` doppelt. Kleine Token-Änderungen können weit wirken. | Phase 1 mit Aliasen; danach jede Phase mit Screenshots bei 390 px und Desktop; keine Regel „mal eben" umsortieren. |
| 9 | **Keine Frontend-Tests** | Regressionen sind nur visuell prüfbar; `npm run build` prüft Typen, nicht Layout. | Build + Screenshot-Vergleich als Pflicht je Phase. Vitest wäre eine neue Abhängigkeit → nur mit Freigabe. |
| 10 | **Screenshot-Werkzeug** | `audit-shots.mjs` kennt noch „Aktivitäten" (seit D-39 nicht erreichbar) und wartet nur auf `.dial-score`; bei fixierter Tabbar im `fullPage`-Bild sitzt die Leiste mitten im Inhalt. | In Phase 4/5 korrigieren: Seitenliste auf „Heute/Verpflegung", auf Daten warten, fixierte Leiste aus dem Vollbild nehmen oder Viewport-Shots nutzen. Kein Produktcode. |
| 11 | **Dokumentstand** | `DESIGN.md` liegt auf `main`; der zugehörige Eintrag D-59 steht bisher nur auf `develop` (`219206b`). `docs/UI-REGELN.md` verweist aber schon auf D-59. | Beim Merge nach `develop` entsteht kein Konflikt. Kein Nachtrag in diesem Ticket (nur `PHASE0.md`) — die Lücke ist auf `develop` bereits geschlossen. |

**Nicht Teil dieser Migration:** API, `metrics.py`, `fuel.py`, DB, Sync, `api.ts`, `types.ts` (außer reinen Darstellungsfeldern, falls Phase 2 sie braucht), Framework, Build-Ziel, PWA-Manifest, Vorschau-Kennzeichnung (D-56).

---

## 7. Abgabe im geforderten Review-Format

1. **Ziel / tatsächlich geändert:** Audit der bestehenden Oberfläche gegen `DESIGN.md` und `AGENT_MIGRATION.md`. Keine UI- und keine Codeänderung; nur dieser Bericht.
2. **Geänderte Dateien:** `docs/design/PHASE0.md` (neu).
3. **Vorher/Nachher:** entfällt, da keine sichtbare Änderung. Der Ist-Stand wurde auf der Vorschau (Port 8101) gesichtet; die Startseite zeigt aktuell „Referenz wird aufgebaut", 2 von 21 Nächten, keinen Score.
4. **Datenlogik unverändert?** Ja. Keine Datei unter `src/`, `web/src/` oder `tests/` geändert; keine API, Berechnung, Recovery-, DB- oder Sync-Änderung.
5. **Build/Tests:** `npm run build` erfolgreich (49 Module, CSS 26,42 kB, JS 266,29 kB). `uv run pytest`: 135 bestanden. (Im Container braucht uv `UV_CACHE_DIR=.uv-cache`, weil `~/.cache/uv` nicht beschreibbar ist.)
6. **Offene Punkte / Risiken:** Schriften (6.1), Seitenleiste vs. Tabbar (6.2), fehlender Router (6.3), Sync-alt/Offline (6.6), Screenshot-Werkzeug (6.10).
7. **Nächster kleiner Schritt:** Phase 1 — Tokens und Alias-Schicht, nach Freigabe. **Nicht** in diesem Ticket begonnen.

---

## 8. Prüfquellen

- `DESIGN.md` (Tokens, Komponenten, Zustände, Anti-Patterns)
- `docs/design/AGENT_MIGRATION.md` (Phasen, Stopps, Abnahmekriterien)
- `docs/ENTSCHEIDUNGEN.md`: D-26 (Erholung nur aus vollständigen Daten), D-39 (Aktivitäten abgehängt), D-52 (Bevel-Fenster), D-55/D-56 (Vorschau), D-58 (Nachtwerte ohne Score), D-59 (Designsystem, auf `develop`)
- `docs/KONZEPT.md` (Produkt, Datenmodell)
- `docs/UI-REGELN.md` (Herkunftsnachweis, ersetzt)
- `web/src/` (Stand dieses Branches), `src/trainings_cockpit/metrics.py:160-323`
