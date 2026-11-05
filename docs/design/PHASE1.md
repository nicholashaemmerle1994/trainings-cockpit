# Phase 1 — Tokens und Basis-Styles

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Basis:** `develop` (`aa834fc`)
**Auftrag:** [`AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 1 · **Design:** [`DESIGN.md`](../../DESIGN.md)
**Status:** umgesetzt, geprüft, **Stopp** — Phase 2 erst nach Freigabe

Phase 0 bleibt unverändert in [`PHASE0.md`](PHASE0.md). Dieses Dokument beschreibt die sichtbare Token- und Basisrunde.

---

## 1. Ziel und tatsächlich geändert

**Ziel:** Farb-, Typografie-, Abstands-, Kontrast- und Radius-Tokens aus `DESIGN.md` zentral einführen, bestehende Styles darauf umstellen, ohne Layout, Markup oder Datenlogik umzubauen.

**Tatsächlich:**
- eine zentrale Token-Schicht mit Aliasen für die bestehenden Namen,
- DESIGN-Farbpalette inklusive Erholungs-Skala,
- System-UI als Oberflächenschrift, Serif für Datum und die noch nicht getrennten Seitentitel (offene Abweichung, siehe 8.9; Instrument Serif als lokaler Rückfall),
- Typografie-Rollen für Body, Kartentitel, Mikro-/Label-Texte und Hauptkennzahlen,
- Abstands- und Radius-Tokens, angewendet auf die bestehenden Regeln,
- Diagramm-Neutralfarben und PWA-Farben auf derselben Palette,
- Bandfarben aus `format.ts` auf die CSS-Tokens umgestellt.

**Nicht geändert:** Markup, Komponentenstruktur, Routing, API, Berechnungen, Recovery-Logik, Sync, Datenbank, Tests.

---

## 2. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `web/src/styles.css` | Token-Schicht (`:root`), Typografie, Farben, Abstände, Radien; 384 Zeilen Diff (231 Einfügungen, 173 Entfernungen) |
| `web/src/format.ts` | `BAND_COLORS` liefert CSS-Variablen statt Hex-Werte |
| `web/index.html` | `theme-color` auf `#05090d` |
| `web/public/manifest.webmanifest` | `background_color`/`theme_color` auf `#05090d` |
| `web/public/manifest-vorschau.webmanifest` | dito |
| `docs/design/PHASE1.md` | dieser Bericht |

Keine Datei unter `src/`, `web/src/pages/`, `web/src/components/` oder `tests/` wurde geändert.

---

## 3. Die Token-Schicht

`web/src/styles.css:45` führt jetzt die Werte aus `DESIGN.md` und hält die alten Namen als Aliase. Dadurch bleiben die 273 bestehenden `var(--…)`-Verwendungen gültig; Phase 2/3 löst die Aliase auf.

| Gruppe | Tokens |
|---|---|
| Flächen | `--bg-app`, `--bg-surface`, `--bg-surface-raised`, `--bg-surface-interactive` |
| Konturen | `--border-subtle`, `--border-strong` |
| Text | `--text-primary`, `--text-secondary`, `--text-muted` |
| Akzent | `--accent`, `--accent-hover`, `--accent-soft`, `--on-accent` |
| Status | `--positive`, `--warning`, `--negative`, `--info` |
| Diagramm | `--chart-neutral`, `--chart-neutral-strong` |
| Erholungs-Skala | `--band-good`, `--band-mid`, `--band-low`, `--band-bad` |
| Typografie | `--font-ui`, `--font-editorial`, `--font-numeric`; `--text-micro/label/body/card/editorial/editorial-sm/hero` |
| Raster | `--space-1…6`, `--space-8` |
| Form | `--radius-card` (22), `--radius-inner` (14), `--radius-control` (12), `--radius-pill` |
| Bewegung | `--ease` (unverändert) |

**Abgeleitete Werte**, die nicht wörtlich in `DESIGN.md` stehen und deshalb hier festgehalten sind:
- `--negative-soft` (Fehlerfläche), `--accent-line` (ausgewählte Kontur), `--backdrop` (Blatt-Hintergrund), `--bg-app-blur` (Tab-Leiste).
- `--band-low: #e8925f`: die vierte Stufe „Erholungsbedarf" (35–49). Grün, Gelb und Rot sind `--positive`, `--warning`, `--negative`; für die Zwischenstufe gibt das Designsystem keine eigene Farbe her. Sie bleibt eine semantische Skalenfarbe, keine Dekoration.

**Aliase** (bewusst als Brücke, nicht als neues Vokabular): `--bg`, `--side`, `--card`, `--raised`, `--raised-2`, `--line`, `--line-strong`, `--text`, `--text-2`, `--text-3`, `--good`, `--mid`, `--low`, `--bad`, `--r-card`, `--r-control`.

---

## 4. Was sichtbar geworden ist

### 4.1 Farben

- Seitenhintergrund `#05090d`, Karte `#0d171d`, erhöhte Fläche `#102229`, interaktive Fläche `#132b31` (vorher `#08090f`, `#11141c`, `#1a1e28`, `#232a37`).
- Konturen sind jetzt deckend (`#203039`/`#2d4650`) statt weißer Transparenz; dadurch ruhigere, präzisere Kanten.
- Akzent von `#3f9e8f` auf `#35dcc5`; Hover `#5ce8d5`. Der Akzent trägt weiterhin nur aktive Tabs, den heutigen Balken und die eine Handlung.
- Text: `#f6f8fa` / `#abb8c4` / `#82919f`. `--text-muted` ist auf der Karte von 4,79:1 auf 5,62:1 gestiegen.
- Fehlerflächen nutzen `--negative`/`--negative-soft`; das alte `#f0b4b4` und die beiden `rgba(207,91,91,…)`-Werte sind weg.
- Wochenbalken: `--chart-neutral` für normale Tage, `--chart-neutral-strong` für den höchsten Tag, `--accent` für heute.

**Gemessene Kontraste (WCAG 2.1, berechnet):**

| Paar | Verhältnis |
|---|---|
| Text primär auf Karte | 17,04:1 |
| Text sekundär auf Karte | 8,97:1 |
| Text gedämpft auf Karte | 5,62:1 |
| Akzent auf Seitenhintergrund | 11,60:1 |
| Text auf Akzentfläche | 11,23:1 |
| Positiv / Warnung / Negativ auf Karte | 10,60 / 10,70 / 6,68:1 |
| Diagramm neutral auf Karte | **2,42:1** (siehe 8.1) |

### 4.2 Typografie

- `--font-ui`: `-apple-system, BlinkMacSystemFont, "Segoe UI", "Liberation Sans", Arial, sans-serif`. Auf dem iPhone SF, auf dem Linux-Homeserver Liberation Sans, auf Windows Segoe UI.
- `--font-editorial`: `"Iowan Old Style", Baskerville, "Instrument Serif", Georgia, serif`. Die selbst gehostete Instrument Serif bleibt als Rückfall erhalten, damit der Homeserver nicht auf DejaVu Serif fällt. Serif ist derzeit **nicht** auf das Datum begrenzt: `h1` (Datum und Verpflegungs-Seitentitel), `.cd-n` (Countdown-Zahlen) und `.sheet-title` (Blatt-Titel) nutzen weiterhin `var(--serif)`. Das ist eine offene Abweichung zu `DESIGN.md` 4.1 („Das Datum darf als einziges serif gesetzt werden"), siehe 8.9.
- `--font-numeric` zeigt auf die Systemschrift; `.mono`/`.n` behalten `tabular-nums`. Plex Sans und Plex Mono sind damit aus der Oberfläche, die Dateien bleiben ungenutzt im Repo (siehe 8.2).
- Body 15/1,5 (vorher 14/1,45), `font-variant-numeric: tabular-nums` global.
- Kartentitel 20/1,3, Gewicht 600 (vorher 15/500) — der deutlichste optische Schritt.
- `h1` 36 (mobil 32) — derzeit Datum und Seitentitel, siehe 8.9; Hauptkennzahl 56, Label 13, Mikro 12.
- `.meta`, `.card-sub`, `.dial-band`, `.dial-ref`, `.night-head`, `.drivers th`, `.train-meta`, `.train-state`, `.empty` und `.note` sind auf die Rollen umgestellt.
- **Bewusst noch nicht angefasst:** die sehr kleinen Diagramm- und Zusatzgrößen (9,5–11,5 px, u. a. `.week-days`, `.fuel-time`, `.sheet-crumb`, `.profile-tick`). Sie gehören in die jeweilige Komponentenrunde; ein pauschales Hochziehen hätte die 7-Tage-Achse und die Blätter in einem Schritt umgebrochen.

### 4.3 Abstände und Formen

- `--space-1…8` eingeführt; 86 Stellen in `padding`, `margin`, `gap` und `column-gap` exakt auf Tokens umgestellt (nur Werte, die schon auf dem 4-px-Raster lagen). Keine Position hat sich dadurch verschoben.
- Kartenradius 22 (vorher 14), Innenradius 14, Control-Radius 12. Angewendet auf Karten, Modus-Karten, Felder, Blatt, Sheet-Zellen, Icon-Knöpfe und Skelette.
- Die 22 px sind der zweitgrößte sichtbare Unterschied nach der Schrift: die Karten wirken ruhiger und näher an der Referenz.

### 4.4 PWA

`theme-color` und `background_color` stehen jetzt in beiden Manifesten und im HTML auf `#05090d`; der Startbildschirm und die Browserleiste tragen dieselbe Farbe wie der Canvas.

---

## 5. Screenshots

Aufgenommen über einen lokalen Proxy (`web/dist` + API der laufenden Vorschau auf 8101), damit vorher und nachher dieselben echten Daten zeigen. Die Dateien liegen lokal unter `data/screens/` (gitignored) und sind nicht Teil des Commits.

| Ansicht | Vorher | Nachher |
|---|---|---|
| Heute, 390 × 844 | `data/screens/phase1-before-heute-mobile.png` | `data/screens/phase1-after-heute-mobile.png` |
| Heute, 1440 × 900 | `data/screens/phase1-before-heute-desktop.png` | `data/screens/phase1-after-heute-desktop.png` |
| Verpflegung, 390 × 844 | `data/screens/phase1-before-verpflegung-mobile.png` | `data/screens/phase1-after-verpflegung-mobile.png` |
| Verpflegung, 1440 × 900 | `data/screens/phase1-before-verpflegung-desktop.png` | `data/screens/phase1-after-verpflegung-desktop.png` |
| Einheiten-Blatt | — | `data/screens/phase1-after-sheet-mobile.png` |
| Heute bei 320 px | — | `data/screens/phase1-after-heute-320.png` |
| Verpflegung bei 320 px | — | `data/screens/phase1-after-verpflegung-320.png` |
| Vorschau-Variante, 390 × 844 | — | `data/screens/phase1-after-preview-mobile.png` |

**Hinweis zu den Vollbildern:** `audit-shots.mjs` nimmt `fullPage` auf; die fixierte Tab-Leiste erscheint dadurch mitten im Bild. Das ist ein Artefakt des Werkzeugs, kein Layoutfehler. Bei 320 px ist kein horizontaler Überlauf sichtbar; der Trainingszeilen-Name bricht dort sauber zweizeilig.

---

## 6. Datenlogik unverändert?

**Ja.** Keine Änderung an:
- `src/` (API, `metrics.py`, `fuel.py`, `sync.py`, DB),
- `web/src/api.ts`, `web/src/types.ts`,
- `web/src/pages/` und `web/src/components/` (kein Markup, keine Props, keine Zustände),
- `tests/`.

Der Erholungszustand bleibt unverändert: Ohne gültige Referenz liefert die API `score: null`, `label: "Referenz wird aufgebaut"`, `reference.nights = 2`, `minimum = 21`; die Karte zeigt „—", den Text und die Nachtwerte. Es wurde keine Zahl ergänzt und kein Mockwert übernommen. Der einzige Unterschied ist typografisch: Kartentitel, Labels und die Zahl im Ring stehen jetzt in der Systemschrift; die Zahl selbst bleibt 56 px.

---

## 7. Build und Tests

| Prüfung | Ergebnis |
|---|---|
| `cd web && npm run build` | grün, 49 Module, 1,52 s; CSS 29,22 kB (gzip 6,09 kB), JS 266,34 kB (gzip 81,90 kB) |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **135 passed**, 1 Warnung, 6,12 s |
| Sichtprüfung | Heute und Verpflegung bei 390 und 1440; Einheiten-Blatt; 320 px |

Die CSS-Datei wächst von 26,42 kB auf 29,22 kB, weil Tokens, Kommentare und Aliase dazukommen; JS bleibt praktisch gleich.

---

## 8. Offene Punkte und Risiken

1. **Ring ohne Score.** `RecoveryDial` zeichnet die vier farbigen Zonenbögen weiterhin auch ohne Score (`RecoveryDial.tsx:60-75`, Deckkraft 0,3). Mit den satteren Bandfarben ist der Ring etwas präsenter. Der Zustand ist inhaltlich korrekt (kein Score, „Referenz wird aufgebaut"), aber `DESIGN.md` 4.4 will ohne Referenz ein neutrales Ringskelett. Das ist **Phase 3b**, nicht Phase 1.
2. **Plex-Dateien.** `@font-face` für Plex Sans/Mono steht noch in `styles.css:1-33`, wird aber nicht mehr referenziert und daher nicht geladen. Die Dateien unter `web/public/fonts/` bleiben. Aufräumen und die README-Aussage „drei Schriften“ gehören in eine spätere Doku-Runde.
3. **`.chip` bleibt doppelt definiert** (Knopf 30 px, Pille 24 px; die spätere Regel gewinnt). Das ist der bekannte Kaskadenfehler aus Phase 0 und wird in Phase 2 mit `StatusBadge` gelöst.
4. **Mikro-Typografie** unter 12 px bleibt in Diagrammen und Metazeilen. Sie folgt in den Komponentenrunden (Phase 2/3), damit die 7-Tage-Achse und die Blätter nicht gleichzeitig brechen.
5. **Diagramm-Kontrast.** `--chart-neutral` (#465763) erreicht auf der Karte nur 2,42:1. `DESIGN.md` gibt den Wert so vor; für Informationsgrafiken sind 3:1 das Ziel. In Phase 3 (Diagramm) prüfen, ob der normale Balken `--chart-neutral-strong` bekommt oder die Tokentabelle angepasst wird.
6. **Schrift auf dem Homeserver.** Die System-UI fällt unter Linux auf Liberation Sans zurück; das ist gewollt und näher an SF als DejaVu. Die tatsächliche iPhone-Darstellung (SF Pro, Iowan Old Style) lässt sich hier nicht rendern.
7. **Vorschau 8101.** Sie läuft noch auf `develop` und zeigt bis zum Deploy den alten Stand. Die Nachher-Bilder stammen aus dem lokalen Build mit den echten Vorschau-Daten.
8. **Keine Frontend-Tests.** Geprüft sind Build, Typen, Backend-Tests und Screenshots. Eine visuelle Regression kann nur über die Bilder beurteilt werden.
9. **Serif nicht nur am Datum.** `h1` (Verpflegungs-Seitentitel), `.cd-n` (Countdown-Zahlen) und `.sheet-title` (Blatt-Titel) setzen weiterhin `var(--serif)`; `DESIGN.md` 4.1 erlaubt Serif nur für das Datum. Die Trennung Datum/Seitentitel braucht Markup bzw. eine eigene Klasse und folgt in Phase 2 (`ScreenHeader`: Verpflegung und Blatt-Titel auf System-UI) sowie Phase 3a (Countdown-Zahlen). Die Commit-Message „Serif fuer das Datum“ ist an dieser Stelle zu weit gefasst; dieser Bericht korrigiert sie.
10. **Vierte Bandfarbe.** `--band-low: #e8925f` steht nicht wörtlich in `DESIGN.md` und war nicht Teil der Freigabe-Rückfrage (bestätigt wurden Umfang Phase 1 und der Schriftwechsel). Sie erhält die bestehende Viererskala (35–49 „Erholungsbedarf“) und braucht die Sichtabnahme mit diesem Bericht.

---

## 9. Nächster kleiner Schritt

**Phase 2 — gemeinsame UI-Bausteine** (`DashboardCard`, `ScreenHeader`, `MetricRow`, `StatusBadge`, `WorkoutPreview`, eine Navigationsliste). Erst nach menschlicher Freigabe; keine automatische Folgephase.
