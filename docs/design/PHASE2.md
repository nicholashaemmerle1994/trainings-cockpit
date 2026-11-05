# Phase 2 — Gemeinsame UI-Bausteine

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Basis:** `develop` (`d31df46`)
**Auftrag:** [`AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 2 · **Design:** [`DESIGN.md`](../../DESIGN.md)
**Status:** umgesetzt, geprüft, **Stopp** — Phase 3 erst nach Freigabe

Phase 0 ([`PHASE0.md`](PHASE0.md)) und Phase 1 ([`PHASE1.md`](PHASE1.md)) bleiben unverändert. Dieses Dokument beschreibt die gemeinsame Bausteinrunde.

---

## 1. Ziel und Ergebnis

**Ziel:** `DashboardCard`, `MetricRow`, `StatusBadge`, `ScreenHeader` und `WorkoutPreview` einführen und die bestehenden Stellen darauf umstellen — ohne alles zu abstrahieren und ohne Verhalten zu ändern.

**Ergebnis:**
- `DashboardCard` ersetzt den bisherigen `Card`-Baustein und die drei von Hand gebauten Kartenköpfe auf „Heute".
- `ScreenHeader` trennt **Datum (Serif)** und **Seitentitel (System-UI)**; damit ist die offene Abweichung aus Phase 1 für Verpflegung und Blatt-Titel geschlossen.
- `MetricRow` ersetzt `.week-row` und `.sheet-kv`; eine Zeile für Wochenkarte und Blätter.
- `StatusBadge` ersetzt die Textstatus in Training und Blättern; `.chip` ist wieder ausschließlich ein Knopf.
- `WorkoutPreview` ersetzt die dreimal gebaute Einheiten-Zeile in „Heute" und im Wochenblatt.
- Navigation liest eine gemeinsame `TABS`-Liste; beide Flächen tragen `aria-current="page"` und dieselbe Icon-Größe (18).
- Charts bleiben bewusst unangetastet (Begründung in 3.7).

**Nicht geändert:** API, Berechnungen, Recovery-Logik, Sync, Datenbank, Routing, Framework, Abhängigkeiten.

---

## 2. Betroffene Komponenten und Dateien

| Datei | Rolle |
|---|---|
| `web/src/components/ui.tsx` | `DashboardCard`, `MetricRow`, `StatusBadge`; `Skeleton`/`EmptyState` unverändert |
| `web/src/components/ScreenHeader.tsx` | neu: Datum oder Titel + Meta + optionale Aktion |
| `web/src/components/WorkoutPreview.tsx` | neu: eine klickbare Einheiten-Zeile |
| `web/src/tabs.ts` | neu: die eine Liste der Hauptbereiche |
| `web/src/App.tsx` | nutzt `TABS`, `aria-current` in der Tableiste |
| `web/src/components/Sidebar.tsx` | nutzt `TABS`, `aria-current`, Icon 18 statt 16 |
| `web/src/pages/Today.tsx` | Header, Erholungs-/Trainings-/Wochenkarte, Einheiten-Zeilen |
| `web/src/pages/Fuel.tsx` | Header, drei Karten |
| `web/src/pages/Activities.tsx` | Header und Karten (weiterhin unverlinkt, D-39) |
| `web/src/components/WeekSheet.tsx` | Einheiten-Zeilen über `WorkoutPreview` |
| `web/src/components/SessionSheet.tsx` | Status-Badge, Verpflegungszeilen über `MetricRow` |
| `web/src/components/UnitSheet.tsx` | Status-Badge, Zahlenzeilen über `MetricRow` |
| `web/src/styles.css` | `.screen-head`, `.metric-row`, `.badge`; `.page-head`, `.week-row`, `.sheet-kv` und das zweite `.chip` entfernt |

---

## 3. Was zusammengeführt wurde

### 3.1 `DashboardCard` (`ui.tsx:6`)

- Ein Baustein für alle Karten: `title`, `subtitle`, `action`, `className`, `children`.
- `as` erhält die Semantik: `article` für Erholung und Training, `aside` für „Letzte 7 Tage", `section` für Verpflegung und Aktivitäten.
- Der Kartenkopf wird nur noch an einer Stelle gerendert; die drei Duplikate in `Today.tsx` sind weg.
- `Fuel` und `Activities` importieren `DashboardCard`; der alte Name `Card` existiert nicht mehr.

### 3.2 `ScreenHeader` (`ScreenHeader.tsx:7`)

- **Datum** (`.screen-head__date`) bleibt Serif, 36 px (mobil 32).
- **Seitentitel** (`.screen-head__title`) steht in der Systemschrift, 26 px, Gewicht 600 — so verlangt es `DESIGN.md` 2.3/4.1.
- Verwendung: „Heute" (Datum), „Verpflegung" (Titel), „Aktivitäten" (Titel).
- **Blatt-Titel** (`.sheet-title`) sind ebenfalls auf System-UI 26/600 umgestellt; damit ist die Phase-1-Abweichung „Serif nicht nur am Datum" für diese Flächen geschlossen.
- **Bewusst offen:** `.cd-n` (Countdown-Zahlen) bleibt Serif. Das ist keine Seitentitel-Fläche und gehört laut Phase-1-Bericht 8.9 in **Phase 3a**.

### 3.3 `MetricRow` (`ui.tsx:39`)

- Eine Zeile „Label links, Wert rechts", optional als ganze Schaltfläche (`onClick`), optional kompakt (Blätter).
- Eingesetzt in der Wochenkarte (Umfang, Belastung, Einheiten, Belastungsverhältnis) und in den Blättern (Verpflegung, Zahlen).
- `.week-row`/`.week-row-link`/`.week-caret` und `.sheet-kv` sind entfernt; die Zeilen teilen sich `.metric-row`.
- Die Wochenzeile beginnt jetzt mit einer `border-top` statt `border-bottom`; die erste Zeile nach dem Streifen hat keine Linie, weil der Streifen schon mit einer Linie schließt. Sichtbar ergibt das dieselben Trennlinien wie vorher.
- **Nicht konvertiert:** die Treibertabelle `.drivers` (vier Spalten mit Track) und die Nachtwerte `.night-list` (Definitionsliste). Beide sind keine einfachen Label/Wert-Zeilen; `DESIGN.md` 4.3 erlaubt die Sonderform.

### 3.4 `StatusBadge` (`ui.tsx:89`) und `.chip`

- Status ist jetzt ein kleiner Chip: `Geplant` neutral, `Erledigt` positiv, `Zusätzlich` neutral.
- `TrainingCard` und die Blätter nutzen denselben Baustein; `.train-state` bleibt nur für die Lastzahl im Wochenblatt.
- Das doppelte `.chip` aus Phase 0 ist aufgelöst: `.chip` ist wieder der Knopf (30 px, Control-Radius, `inline-flex`), `.badge` die Pille (24 px, `--radius-pill`).
- Dadurch sind die Filter- und Dauer-Chips in Verpflegung/Aktivitäten wieder 30 px hoch statt effektiv 24 px. Das ist die Korrektur des Kaskadenfehlers; die 44-px-Touchfläche bleibt Phase 4.

### 3.5 `WorkoutPreview` (`WorkoutPreview.tsx:5`)

- Eine Zeile mit Sport-Icon, Name, Meta und optionalem `trailing`.
- „Heute" nutzt sie für geplante, morgige und zusätzliche Einheiten; das Wochenblatt für die Einheiten der letzten sieben Tage (dort ist `trailing` die Lastzahl).
- Klickpfade unverändert: geplante Einheit → `SessionSheet`, zusätzliche Einheit → `UnitSheet`, Wochenzeile → `UnitSheet`.

### 3.6 Navigation und Icons

- `TABS` in `tabs.ts` ist die einzige Liste; `Sidebar` und Tableiste lesen sie.
- `aria-current="page"` auf der aktiven Fläche in beiden Darstellungen.
- Beide Navigationsflächen nutzen Icon-Größe 18; der Strich bleibt 1,5. Kein neues Icon-Paket.

### 3.7 Charts — bewusst nicht abstrahiert

`RecoveryDial`, `WeekStrip`, `WorkoutChart` und `SessionProfile` haben unterschiedliche Datenformen (Score-Ring, sieben Lastwerte, aufgezeichneter Verlauf, Planblöcke) und keine gemeinsame Schnittstelle. Eine `TrendChart`-Hülle würde nur Props weiterreichen. Die Charts bleiben deshalb für Phase 3 stehen; die Farben laufen bereits über Tokens.

---

## 4. Beispielansichten

Aufgenommen über einen lokalen Proxy (`web/dist` + API der laufenden Vorschau), damit vorher und nachher dieselben echten Daten zeigen. Die Bilder liegen lokal unter `data/screens/` (gitignored) und sind nicht Teil des Commits.

| Ansicht | Vorher (Phase 1) | Nachher (Phase 2) |
|---|---|---|
| Heute, 390 × 844 | `data/screens/phase2-before-heute-mobile.png` | `data/screens/phase2-after-heute-mobile.png` |
| Heute, 1440 × 900 | `data/screens/phase2-before-heute-desktop.png` | `data/screens/phase2-after-heute-desktop.png` |
| Verpflegung, 390 × 844 | `data/screens/phase2-before-verpflegung-mobile.png` | `data/screens/phase2-after-verpflegung-mobile.png` |
| Verpflegung, 1440 × 900 | `data/screens/phase2-before-verpflegung-desktop.png` | `data/screens/phase2-after-verpflegung-desktop.png` |
| Einheiten-Blatt, 390 × 844 | `data/screens/phase2-before-sheet-mobile.png` | `data/screens/phase2-after-sheet-mobile.png` |
| Wochen-Blatt, 390 × 844 | — | `data/screens/phase2-after-weeksheet-mobile.png` |
| Heute bei 320 px | `data/screens/phase2-before-heute-320.png` | `data/screens/phase2-after-heute-320.png` |
| Verpflegung bei 320 px | `data/screens/phase2-before-verpflegung-320.png` | `data/screens/phase2-after-verpflegung-320.png` |

**Sichtbare Unterschiede:** Verpflegungs-Titel und Blatt-Titel in System-UI statt Serif; Status als Pille statt nackter Text; Wochenzeilen mit gemeinsamer Zeilenform; Filter-Chips wieder 30 px hoch; einheitliche Navigations-Icons. Die Erholungskarte zeigt weiterhin „Referenz wird aufgebaut", 2 von 21 Nächten und keinen Score.

**Hinweis zu den Vollbildern:** `audit-shots.mjs` nimmt `fullPage` auf; die fixierte Tab-Leiste erscheint dadurch mitten im Bild. Das ist ein Werkzeugartefakt, kein Layoutfehler.

---

## 5. Verhalten und Datenlogik

**Unverändert.** Keine Änderung an:
- `src/` (API, `metrics.py`, `fuel.py`, `sync.py`, DB),
- `web/src/api.ts`, `web/src/types.ts`,
- Berechnungen, Recovery, Sync, Routing, Abhängigkeiten.

Geprüfte Klickpfade (Chromium, echte Vorschau-Daten):
- Trainingszeile → `SessionSheet` (Titel, Status, Verpflegungszeilen).
- „Umfang" in der Wochenkarte → `WeekSheet` (12 Einheiten).
- Einheit im Wochenblatt → `UnitSheet` (zweites Blatt, Titel „Wien - Tempo Lauf").
- Escape schließt das oberste Blatt, danach das zweite; am Ende sind keine Blätter offen.
- DOM-Semantik: Erholung/Training `ARTICLE`, Woche `ASIDE`; beide Navigationen tragen `aria-current="page"`.
- 320/390/430/1440 px: kein horizontaler Überlauf (`scrollWidth === clientWidth`), keine Konsolen- oder Seitenfehler.

Der kritische Zustand bleibt: `recovery.score = null`, Label „Referenz wird aufgebaut", `reference.nights = 2`, `minimum = 21`. Es wurden keine Mockwerte ergänzt.

---

## 6. Regressionen und Risiken

1. **Status-Pille statt Text.** In der Trainingszeile nimmt die Pille Platz in der dritten Spalte. Bei 320 px bricht der Einheitenname deshalb zweizeilig; kein Überlauf, aber bewusst geprüft.
2. **Chips 30 px.** Die Korrektur des doppelten `.chip` macht Filter und Dauer-Voreinstellungen höher. Das ist gewollt, rückt aber die 44-px-Fläche aus `DESIGN.md` 2.4 in den Blick — Phase 4.
3. **Serif-Rest.** `.cd-n` bleibt Serif (Phase 3a). Das ist im Bericht und in `PHASE1.md` 8.9 als offene Abweichung vermerkt.
4. **Blatt-Titel kleiner.** 26 px System-UI statt 32 px Serif; die Hierarchie im Blatt ist dadurch flacher, folgt aber `DESIGN.md` 2.3.
5. **Aktivitäten-Seite.** Sie nutzt jetzt `ScreenHeader`/`DashboardCard`, bleibt aber unverlinkt (D-39). Keine Reaktivierung, keine neue Route.
6. **Keine Frontend-Tests.** Geprüft sind Build, Typen, Backend-Tests, DOM-/Klickprüfung und Screenshots; eine visuelle Regression bleibt manuell.

---

## 7. Build und Tests

| Prüfung | Ergebnis |
|---|---|
| `cd web && npm run build` | grün, 52 Module, 1,5 s; CSS 29,84 kB, JS 265,37 kB |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **135 passed**, 1 Warnung, 6,32 s |
| DOM-/Klickprüfung | Artikel/Aside, Wochenblatt, Einheiten-Blatt, Escape, `aria-current`, kein Überlauf, keine Konsolenfehler |
| Sichtprüfung | Heute und Verpflegung bei 320/390/1440, Einheiten-Blatt |

---

## 8. Offene Punkte und nächster Schritt

1. **Countdown-Zahlen** `.cd-n` auf System-UI umstellen — Phase 3a.
2. **Touchflächen** der Chips und Navigationsknöpfe auf 44 px — Phase 4.
3. **Charts** (Ring, Wochenstreifen, Verlauf) in Phase 3 mit den neuen Karten/Tokens zusammendenken, ohne eine gemeinsame Hülle zu erzwingen.
4. **`--band-low: #e8925f`** aus Phase 1 braucht weiterhin die Sichtabnahme (Phase-1-Bericht 8.10).
5. **Plex-Dateien/README** bleiben als Aufräumpunkt; keine funktionale Auswirkung.

**Nächster Schritt:** Phase 3a (Header/Countdowns) erst nach menschlicher Freigabe. Keine automatische Folgephase.
