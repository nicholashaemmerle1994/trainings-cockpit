# DESIGN.md — Trainings-Cockpit

> **Status:** verbindlich · **Version:** 2.0 · **Stand:** 05.11.2026
>
> **Gilt für:** alle neuen und geänderten Oberflächen — Seiten, Tabs, Karten, Blätter, Dialoge, Diagramme und Zustände
>
> **Bezug:** D-59 (dieses Dokument ist das Designsystem), D-63 (Erholungskarte), D-64 (dunkle Fläche, lokaler Lichtschein), D-65 (Ringstrich 8), D-66 (Kartenrampe, gedämpfte Statuslabels, ruhige Navigation), D-67 (Label und Trendtexte teilen den Text-Token)
>
> **Optische Referenz:** `docs/design/cockpit-premium-reference.png` — Stilvorlage, keine Datenquelle

> **Leitsatz:** Lokaler Lichtschein auf neutraler, dunkler Oberfläche — kein türkis eingefärbter Kartenhintergrund.

## 1. Geltung

Dieses Dokument ist die **einzige verbindliche Vorgabe für Oberflächen**. `docs/UI-REGELN.md` ist abgelöst (D-59) und bleibt nur als Herkunftsnachweis stehen (unslop, CC BY 4.0).

- Es gilt für **neue und geänderte** Oberflächen. Keine Komponente weicht ohne dokumentierte Entscheidung (`D-xx` in `docs/ENTSCHEIDUNGEN.md`) ab.
- Ein neues Feature passt sich dem System an, nicht umgekehrt. Wiederverwenden geht vor neu bauen.
- Abschnitt 10 ist der **Ist-Stand** von `web/src/styles.css`, keine Wunschliste. Weicht der Code ab, gilt der Code — und die Tabelle wird sofort nachgezogen.
- Es gibt **keine Tokens außerhalb von Abschnitt 10**. Keine Hex-Werte, Freihand-Abstände oder komponenteneigenen Farbsysteme.
- Geregelt sind Aussehen und Interaktion, nicht Fachlogik, API-Verträge, Berechnungen oder Sync.

## 2. Prinzipien

1. **Information vor Dekoration.** Jedes Element muss Orientierung, Lesbarkeit, Interaktion oder eine Aussage über Daten verbessern.
2. **Ein Fokus pro Abschnitt.** Eine Karte, ein Diagramm, ein Blatt: genau ein dominanter Blickpunkt. Details liegen hinter der Übersicht, nicht daneben.
3. **Echte Daten vor schönen Daten.** Fehlt ein Wert, bleibt er leer und wird benannt — nicht geschätzt, nicht aufgefüllt, nicht erfunden.
4. **Mobile first.** Entworfen und geprüft wird auf 390 × 844; der breite Schirm zeigt dasselbe größer, nicht anders.
5. **Barrierefreiheit als Standard.** Lesbarer Kontrast, semantische Labels, Tastaturbedienung, reduzierte Bewegung.
6. **Fläche ist neutral, Licht ist lokal.** Die Fläche trägt keine Farbe; Farbe kommt als Licht von oben, eng begrenzt, oder als Akzent an einer Stelle.
7. **Gleiches Verhalten überall.** Laden, Leer, Fehler, Baseline und veralteter Sync sehen auf jeder Seite gleich aus.

## 3. Flächen und Licht

**Flächen.** Seitenhintergrund `--bg-app`, Standardkarten `--bg-surface`, hervorgehobene Zeilen `--bg-surface-raised`, interaktive Flächen `--bg-surface-interactive`. Alle sind nahezu schwarz bis anthrazit mit leichter kühler Tönung. Unterschieden wird über **Helligkeit und 1-px-Rand** (`--border-subtle`, betont `--border-strong`), nicht über Farbe.

Die Erholungskarte ist die wichtigste Fläche und liegt auf der fast schwarzen, leicht kühlen Basis `--recovery-surface`. Ihre Tiefe entsteht nur aus diesem Unterschied und dem Lichtschein, nicht aus einer Füllung.

**Licht.** Höchstens **ein** lokaler Lichtschein pro Bildschirm, oben, weich in vollständige Transparenz auslaufend, ausschließlich auf einer eigenen dekorativen Ebene (`::before`) hinter dem Inhalt. Gedimmt wird **nur diese Ebene** (`--recovery-glow-opacity`), nie die Karte oder ihre Inhalte.

- Verlauf: `radial-gradient(100% 52% at 50% 0%, var(--recovery-glow) 0%, var(--recovery-glow-soft) 45%, transparent 72%)`.
- Ab 72 % des Radius — rund 37 % der Kartenhöhe — ist das Licht vollständig transparent. **Unterhalb des oberen Drittels dominiert die Grundfläche.**
- Der Schein darf keine sichtbare Kante haben, keine Fläche einfärben und nicht auf andere Karten wandern. Der Ring-Schein (`--recovery-ring-glow`) gehört zum Ring, nicht zur Fläche, und zählt nicht als zweiter Lichtschein.
- Ein neuer Bildschirm bekommt keinen zusätzlichen Schein. Braucht er einen, ist das eine `D-xx`-Entscheidung — und es bleibt der einzige auf diesem Bildschirm.

**Verboten:** flächige Türkis- oder Petrolverläufe als Kartenhintergrund, grünliche oder petrolfarbene Grundfüllungen, leuchtende Kartenumrandungen, türkis eingefärbte Trennlinien oder Sekundärflächen im Kartenraster, Schein auf normalen Karten. `--accent-line` ist eine **interaktive Kontur** (Auswahl, Sync-Knopf), keine Fläche; `--accent-wash` ist nur noch für Kleinteile erlaubt und derzeit ungenutzt — nie als Kartenfläche.

Schatten nur, wo sie Tiefe liefern; derzeit allein die Erholungskarte (`0 10px 30px rgba(0, 0, 0, 0.14)`).

## 4. Akzente

Türkis (`--accent`) ist kein Dekor, sondern Bedeutung. Es erscheint gezielt für:

- den **Erholungsring** und seinen dezenten Schein (`--recovery-ring-glow`),
- den **aktiven Diagrammtag**,
- die **aktive Navigation** (Icon),
- die **ausgewählte Interaktion** (gewählter Modus, Fokusring, Primäraktion).

**Hierarchie:** Ring und Kennzahlen tragen sie. Titel, Werte und die große Zahl bleiben `--text-primary`. Sekundärtext bleibt neutral (`--text-secondary`, `--text-muted`) und wird weder abgedunkelt noch grünlich getönt. Pro Abschnitt ein Akzentelement; Statuslabels zählen als Status, nicht als zweiter Akzent — sie sind gedämpft (Abschnitt 5).

## 5. Statuslabels

Statuslabels sind kleine Pillen (`.badge`, Höhe 24, `--radius-pill`, 12 px/500). Jede trägt eine **gedämpfte, semantisch passende Hintergrundtönung** mit kontrastreicher Schrift:

- positive Bedeutung: `--positive-soft` mit `--positive`,
- Hinweis: `--warning-soft` mit `--warning`,
- kritisch: `--negative-soft` mit `--negative`,
- ohne Bewertung: `--bg-surface-raised` mit `--text-secondary`.

Die Tönungen liegen bei 12 % der Statusfarbe (Ist-Wert: `--positive-soft`, `--warning-soft`, `--negative-soft`, `--band-top-soft`, `--band-low-soft` = `rgba(..., 0.12)`); die Schrift steht in der vollen Statusfarbe. Statusfarben bleiben semantisch, nicht dekorativ; die Bedeutung steht immer auch im Text („Gut", „Geplant", „Erledigt", „Zusätzlich").

**Gleicher Token für Text und Trend.** „Positive Trendtexte und positive Statuslabels verwenden dieselbe semantische Textfarbe. Statuslabels ergänzen lediglich eine dunkle, zurückhaltend getönte Hintergrundfläche." Deshalb liest `.badge--band-good` („Gut") direkt `--positive` wie `.night-delta--good`; den Weg über den Band-Alias gibt es nur noch für die Skala.

**Erholungsband.** Die Stufe des Erholungsstatus kommt aus der Band-Skala, nicht aus dem Akzent: `--band-top-soft`/`--band-top`, `--positive-soft`/`--positive` (Band `--band-good: var(--positive)`), `--warning-soft`/`--band-mid`, `--band-low-soft`/`--band-low`, `--negative-soft`/`--band-bad`. Auch das „Gut" der Erholungskarte ist eine gedämpfte Pille; die vollflächig gefüllte Akzentpille entfällt damit als Statuslabel überall. Die gemessenen Kontraste liegen bei 5,9:1 bis 11,1:1 (Nachweis: `docs/design/karten-status-navigation.md`).

Die Abzeichen der Bauvariante (`.brand-tag` „Vorschau" und „Demo") sind **keine Statuslabels**; sie bleiben gefüllt, weil sie die Herkunft des Baus markieren (D-56, D-60).

## 6. Navigation

Zwei Formen, eine Sprache: Seitenleiste ab 1001 px, Tab-Leiste darunter (≤ 1000 px).

- **Aktiv:** türkises Icon, helle Beschriftung (`--text-primary`, 500); inaktiv `--text-muted`, 400. Seitenleiste und Tab-Leiste folgen denselben Werten.
- Ein sehr schwacher Schein unmittelbar am Icon ist optional (maximal ca. 6 px Blur, 8–12 % Deckkraft). **Derzeit trägt kein Navigationselement einen Schein.**
- Kein Balken, kein Halo, keine eingefärbte Navigationsfläche, kein farbiger Volltab.
- Icon 18 px, Touchfläche mindestens 44 × 44 CSS-px, gleiche Ausrichtung und derselbe Iconstil für alle Einträge.
- Die Tab-Leiste ist fixiert, halbtransparent (`--bg-app-blur`, `backdrop-filter: blur(16px)`) mit oberer 1-px-Kante und `env(safe-area-inset-bottom)`.
- Nur dauerhafte Hauptbereiche bekommen einen Tab (derzeit Heute und Verpflegung). Details öffnen ein Blatt, keinen neuen Tab; `aria-current="page"` markiert den aktiven Eintrag, Browser-Zurück bleibt funktionsfähig.

## 7. Typografie

| Rolle | Schrift | Größe / Zeilenhöhe | Gewicht |
|---|---|---|---|
| Datum im Kopf (einziger Serif-Moment) | `--font-editorial` | 36 px, mobil 32 px / 1,05 | 400 |
| Seitentitel | `--font-ui` | 26 px / 1,25 | 600 |
| Kartentitel | `--font-ui` | 20 px / 1,3 | 600 |
| Große Kennzahl (Score, Verpflegung) | `--font-ui` | 56 px, mobil bis 44 px / 0,95–1,0 | 600 |
| Kennzahl (Nachtwerte, Countdown) | `--font-ui` | 23–26 px / 1,0–1,1 | 600 |
| Fließtext | `--font-ui` | 15 px / 1,5 | 400 |
| Label, Untertitel | `--font-ui` | 13 px / 1,5 | 400–500 |
| Mikro (Metadaten, Achsen) | `--font-ui` | 12 px / 1,3–1,5 | 400–500 |

- Zwei Familien: System-UI für alles, Serif **nur** fürs Datum. `--font-numeric` ist die UI-Schrift; die Klassen `.mono`/`.n` erzeugen **keine** Monospace-Schrift, sondern `tabular-nums`.
- `font-variant-numeric: tabular-nums` für alle Zahlen; Einheit kleiner als die Zahl (`62 ms`, `46 bpm`, `6:50 h`).
- Große Zahlen mit `letter-spacing: -0.01em` bis `-0.02em`; keine Versalien für Überschriften, Sentence case.
- Keine Emojis als Icons, keine dritte Schrift, keine Systemschrift-Vergrößerung abschneiden.

## 8. Raster und Formen

- **4-px-Raster**: `--space-1` 4, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-5` 20, `--space-6` 24, `--space-8` 32. Keine 17/19/27 px für Standardabstände.
- Seitenrand mobil 20 px, Desktop 32 px. Kartenabstand 16 px, Karteninhalt 24 px (mobil 20 px), Zeilen mit 7–10 px vertikalem Padding; antippbare Zeilen sind 44 px hoch.
- Radien: Karte 22 px, eingebettete Fläche 14 px, Bedienelement 12 px, Pille 999 px.
- **Keine Karte in der Karte in der Karte.** Eine Zeile bleibt eine Zeile mit 1-px-Trenner, keine zweite große Karte.
- Gruppieren zuerst über Typografie und Abstand, dann über Linien, zuletzt über Container.
- Touchflächen folgen Abschnitt 13.

## 9. Responsive

| Breite | Verhalten |
|---|---|
| ≤ 1180 px | Zweispaltige Startseite wird einspaltig, Seitenrand 24 px |
| ≤ 1000 px | Mobil: Seitenleiste entfällt, Tab-Leiste erscheint, Karten-Padding 20 px, Datum 32 px |
| ≤ 360 px | Trainingszeile zweizeilig, Pfeil entfällt |
| ≥ 720 px | Blätter werden als modaler Dialog mit Rand und Radius gezeigt |
| ≥ 1001 px | Seitenleiste, Erholungskarte im zweispaltigen Raster |

- Inhalt max. 1200 px, Seitenleiste 248 px, mobil einspaltig.
- Zuerst mobil bauen, semantisch nach oben skalieren — keine eigene visuelle Sprache pro Gerät.
- Notch, Safe Areas, iOS-Zoom (Eingabefelder ≥ 16 px) und fehlenden horizontalen Überlauf bei 320 px prüfen.

## 10. Tokens — Ist-Stand

Quelle: `web/src/styles.css` (`:root`), Stand 05.11.2026. Änderungen zuerst im Code, dann hier.

**Flächen, Text, Status**

| Token | Wert |
|---|---|
| `--bg-app` | `#05090d` |
| `--bg-surface` | `#0b1318` |
| `--bg-surface-raised` | `#0e181e` |
| `--bg-surface-interactive` | `#121f26` |
| `--border-subtle` | `#1c272e` |
| `--border-strong` | `#2a373f` |
| `--text-primary` | `#f6f8fa` |
| `--text-secondary` | `#abb8c4` |
| `--text-muted` | `#82919f` |
| `--accent` | `#35dcc5` |
| `--accent-hover` | `#5ce8d5` |
| `--accent-soft` | `#123831` |
| `--on-accent` | `#04100e` |
| `--positive` / `--negative` | `#49dea4` / `#f1787f` |
| `--warning` | `#f3be6a` |
| `--info` | `#64bde2` |
| `--chart-neutral` / `--chart-neutral-strong` | `#465763` / `#78909e` |

**Zusätzliche Töne (abgeleitet, im Code vorhanden)**

| Token | Wert |
|---|---|
| `--positive-soft` | `rgba(73, 222, 164, 0.12)` |
| `--warning-soft` | `rgba(243, 190, 106, 0.12)` |
| `--negative-soft` | `rgba(241, 120, 127, 0.12)` |
| `--band-top-soft` | `rgba(126, 240, 192, 0.12)` |
| `--band-low-soft` | `rgba(232, 146, 95, 0.12)` |
| `--on-warning` | `#1c1406` |
| `--accent-line` | `rgba(53, 220, 197, 0.45)` |
| `--accent-wash` | `rgba(53, 220, 197, 0.045)` — nur Kleinteile, derzeit ungenutzt |
| `--backdrop` / `--bg-app-blur` | `rgba(3, 6, 9, 0.72)` / `rgba(5, 9, 13, 0.94)` |

**Erholung und Skala**

| Token | Wert |
|---|---|
| `--recovery-surface` | `#080d11` |
| `--recovery-glow` | `rgba(53, 220, 197, 0.36)` |
| `--recovery-glow-soft` | `rgba(53, 220, 197, 0.08)` |
| `--recovery-glow-opacity` | `0.5` |
| `--recovery-ring-glow` | `rgba(53, 220, 197, 0.3)` |
| `--band-top` | `#7ef0c0` |
| `--band-good` | `var(--positive)` |
| `--band-mid` | `var(--warning)` |
| `--band-low` | `#e8925f` |
| `--band-bad` | `var(--negative)` |

Jedes Band ist eine semantische Stufe der Erholungsskala (sehr gut, gut, mittel, Erholungsbedarf, Ruhetag) und darf nur dort Farbe tragen.

**Typografie, Raster, Radien**

`--font-ui: -apple-system, BlinkMacSystemFont, "Segoe UI", "Liberation Sans", Arial, sans-serif` · `--font-editorial: "Iowan Old Style", Baskerville, "Instrument Serif", Georgia, serif` · `--font-numeric: var(--font-ui)` · `--text-micro` 12 · `--text-label` 13 · `--text-body` 15 · `--text-card` 20 · `--text-screen` 26 · `--text-editorial` 36 · `--text-editorial-sm` 32 · `--text-hero` 56 · `--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4` 16 · `--space-5` 20 · `--space-6` 24 · `--space-8` 32 · `--radius-card` 22 · `--radius-inner` 14 · `--radius-control` 12 · `--radius-pill` 999 · `--ease: cubic-bezier(0.22, 1, 0.36, 1)`.

**Übergangs-Aliase (Bestand, nicht für neuen Code)**

`--card` → `--bg-surface`, `--raised` → `--bg-surface-raised`, `--line` → `--border-subtle`, `--text-2` → `--text-secondary`, `--text-3` → `--text-muted`. Ebenso: `--bg`/`--side` → `--bg-app`, `--raised-2` → `--bg-surface-interactive`, `--line-strong` → `--border-strong`, `--text` → `--text-primary`, `--sans`/`--mono`/`--serif` → die Schrift-Tokens, `--r-card`/`--r-control` → die Radius-Tokens. Neuer Code verwendet ausschließlich die kanonischen Tokens, nicht die Aliase.

## 11. Bausteine

**Kopf und Karte.** `ScreenHeader`: Datum serif, Meta-Zeile 12 px `--text-muted`, 1-px-Abschluss. `DashboardCard` (`.card`): `--bg-surface`, 1-px `--border-subtle`, `--radius-card`, 24 px Padding (mobil 20), Titel 20/600 + optionale Untertitelzeile; keine Deko-Icons, kein zweiter Fokus.

**Erholungskarte.** Wichtigste Karte; Ring oder Score ist der eine Schwerpunkt.

- *Mit Score, mobil (≤ 1000 px):* zweispaltig `minmax(0, 1fr) clamp(120px, 38vw, 150px)` — bei 390 px rund 148 px Ring. Links Score 56 px (mobil 44–56) mit `/ 100`, gedämpfte Statusplakette im Bandton (12 %), „Nacht vom …", Referenzzeile; rechts der Ring mit Puls-Icon. Darunter eine Trennlinie und HRV, Ruhepuls, Schlaf **dreispaltig**, je Wert, Einheit und Delta zur eigenen Baseline (aus vorhandenen Feldern gerechnet, nichts erfunden).
- *Mit Score, Desktop (≥ 1001 px):* Raster `minmax(240px, 300px) minmax(0, 1fr)`; Ring links, rechts die Treibertabelle heute / Schnitt / üblich mit Skalenmarke; die Nachtwerte treten dort nicht zusätzlich auf.
- *Ohne Score und ohne Treiberzeile:* Der Ring bleibt zentriert, „—" statt Zahl, Label und „x von 21 Nächten"; der Fortschritt ist neutral (`--chart-neutral-strong`), nie grün und nie türkis. Die Nachtwerte treten dreispaltig an die Stelle der Treiberzeile (D-58), ohne Delta. Kein erfundener Score, kein positiver Status.
- *Ring:* `SIZE` 220 im viewBox, `RING` 92, `STROKE` 8, `strokeLinecap="round"`, Start oben; Spur `--bg-surface-raised`, Fortschritt mit Score `--accent`, ohne Score `--chart-neutral-strong`; Schein nur mit Score: `drop-shadow(0 0 7px var(--recovery-ring-glow))`; Referenzmarke als Linie mit Strichstärke 2 in `--text-muted`. Gerendert mobil: 186 px ohne Score, 148 px mit Score bei 390 px. `role="img"` und sprechendes `aria-label`.
- Die Karte trägt als einzige den Lichtschein aus Abschnitt 3.

**Training.** Die Karte „Training": Zeile `WorkoutPreview` 56 px hoch, Icon 36 px in `--accent-soft`/`--accent`, Name 15/500, Meta 12 px `--text-muted`, Status rechts. „Nichts geplant" als ruhiger Satz, optional „Morgen" mit Datum. Klick öffnet das Blatt der Einheit.

**Letzte 7 Tage.** `WeekStrip`: sieben Spalten, 84 px hoch, 6 px Abstand; neutrale Balken (`--chart-neutral-strong` → `--chart-neutral`), Spitzenwert `--text-muted` → `--chart-neutral-strong`, **heute** `--accent-hover` → `--accent` samt türkisem Tageslabel. Darunter `MetricRow`s für Umfang, Belastung, Einheiten, Belastungsverhältnis.

**Kennzahlen.** `MetricRow`: Label 13 px `--text-secondary` links, Wert 14 px `--text-primary` mit `tabular-nums` rechts, 1-px-Trenner oben, 44 px hoch wenn antippbar. Keine Kästen, keine Sparklines, keine Icons vor jeder Zahl.

**Diagramme und Blätter.** Von Hand gezeichnete SVGs, kein Diagramm-Paket: Raster `--border-subtle`, Basislinie `--border-strong`, eine Akzentlinie, Achsen 9–12 px `--text-muted`, textliche Zusammenfassung. Blätter (`.sheet`) nutzen dieselben Karten-, Zeilen- und Badge-Regeln; auf ≥ 720 px als Dialog, darunter vollflächig.

**Neues Feature.** Wiederverwenden: `ScreenHeader`, `DashboardCard`, `MetricRow`, `StatusBadge`, `WorkoutPreview`, `WeekStrip`, vorhandene Diagramme. Festlegen: welche Bausteine es nutzt, welchen Zustand es zeigt (Abschnitt 12) und **wo das eine Akzentelement sitzt**. Kein neuer Tab, kein neues Token, keine neue Komponente ohne Not.

## 12. Daten- und Zustandsdesign

Daten werden so gezeigt, wie sie sind — vollständig, benannt und vergleichbar:

- Datum und Uhrzeit deutsch, Zeitzone bewusst; Sync-Zeit, Einheiten-Zeit und Gerätedatum nicht vermischen.
- Zahlenformat deutsch (`1,28`, `11 h 21 min`), Einheiten konsistent (`ms`, `bpm`, `km`, `W`, `h`); Einheit kleiner als die Zahl.
- Veränderungen nur mit Vergleichszeitraum oder Bezugsgröße; wo der Bezug nicht aus der Überschrift hervorgeht, wird er benannt („+8 % vs. eigener Basis").
- Fehlende Werte stehen als „—", nie als `0`; Abkürzungen wie HRV und Belastungsverhältnis bleiben auffindbar erklärt.
- Ein UI-Indikator begründet keine medizinische Entscheidung; ein hoher Wert ist nicht automatisch positiv.

| Zustand | Verhalten | Verboten |
|---|---|---|
| Laden | Platzhalter in der späteren Layoutform | Layoutsprünge, Nullen als Ersatz |
| Keine Daten | „Noch keine Daten" plus Quelle oder Handlung | `0` statt `null` |
| Baseline wird aufgebaut | „x von 21 Nächten", neutraler Ring, kein Score | erfundener Score, „Gut", grüner Ring |
| Sync veraltet | Zeitpunkt des letzten erfolgreichen Syncs | „aktuell" suggerieren |
| Fehler | konkreter Satz, `--negative`, Wiederholen-Aktion | leere Karte ohne Erklärung |
| Teilweise Daten | vorhandene Werte zeigen, fehlende als „—" | schätzen oder die Karte verstecken |
| Offline | letzter bestätigter Stand mit Zeitstempel | Daten als live ausgeben |

**Demo-Werte** gibt es ausschließlich im Vorschau-Bau (`VITE_APP_VARIANT=preview`, `?demo=recovery`) und nur mit sichtbarem Abzeichen „Demo". Im stabilen Bau existiert der Zweig nicht; ein Demo-Wert darf nie als echter Wert erscheinen. Während der Referenzaufbau läuft, erscheint **kein** Score.

## 13. Bewegung und Barrierefreiheit

- Übergänge 140–160 ms, `--ease`; Seitenwechsel 380 ms mit 8 px Versatz; Ring füllt in 700 ms; Skeletons 1,4–1,6 s. Keine springenden Zahlen, pulsierenden Glows, kein Parallax.
- `prefers-reduced-motion: reduce` setzt Animationen und Übergänge global auf 0,01 ms.
- Sichtbarer Fokus: 2 px `--accent`, außen 2 px Abstand (Tab-Leiste innen). Tastaturbedienung, semantische Elemente, `aria-current`, `aria-label` für Ring und Diagramme.
- Textkontrast mindestens AA (4,5:1 normal, 3:1 groß); Sekundärtext bleibt lesbar statt abgedunkelt.
- Tap-Ziele mindestens 44 × 44 CSS-px (ausgenommen die kompakte Kopf-Schaltfläche, 40 px), ausreichend Abstand; Content scrollt nicht ungewollt horizontal.

## 14. Technik

- React 19 + Vite + TypeScript; eine globale `web/src/styles.css`, Tokens in `:root`. Kein CSS-Framework, kein Diagramm-Paket, keine neue Bibliothek ohne Freigabe.
- `@font-face` für Plex Sans/Mono liegt noch in der Datei; aktiv sind die Token-Stapel: System-UI (`--font-ui`) und der editoriale Serif fürs Datum (`--font-editorial`, mit Instrument Serif als Fallback).
- Icons: eine Outline-Familie in `web/src/components/icons.tsx`, 18 px in Navigation und Listen, 16–24 px für Aktionen, Strich 1,5 px; keine Emojis, keine gemischten Stile.
- Gestaltung bleibt von Fachlogik getrennt: keine Mockdaten in produktiven Komponenten, keine Designänderung an API, Berechnung, Datenbank oder Sync.

## 15. Prüfliste vor dem Abschluss

- [ ] Karten wirken dunkel und **nicht grün**; keine Karte hat eine farbige Grundfüllung.
- [ ] Lichtschein subtil, weich und lokal; höchstens einer pro Bildschirm; nur die dekorative Ebene ist gedimmt.
- [ ] Ring und Kennzahlen bleiben die Schwerpunkte; der Blick fällt zuerst auf sie.
- [ ] Normale Karten konkurrieren nicht durch eigene Farbeffekte, Scheine oder Akzentkanten.
- [ ] Aktiver Tab eindeutig, aber dezent: türkises Icon, helles Label, kein Balken, kein Halo.
- [ ] Texte und Statuslabels gut lesbar; Sekundärtext neutral, nicht abgedunkelt oder grünlich.
- [ ] Oberfläche insgesamt nicht grauer oder ausgewaschen.
- [ ] Layout, Abstände, Größen und Funktionen unverändert (Kartenmaße vor/nach gemessen).
- [ ] Kein erfundener Wert; Loading, Empty, Error, Baseline und Stale Sync geprüft.
- [ ] Nur Tokens aus Abschnitt 10; keine Hex-Werte in Komponenten, keine neuen Aliase.
- [ ] 320, 390, 430 px und Desktop geprüft; kein horizontaler Überlauf, Tap-Ziele belegt.
- [ ] `prefers-reduced-motion`, sichtbarer Fokus und Screenreader-Labels geprüft.
- [ ] Bei Code: `uv run pytest` und `npm run build` grün.
- [ ] Vergleichsbilder bei gleicher dargestellter Kartenbreite vorhanden.

## 16. Änderungsprozess

1. Zuerst dieses Dokument und die Referenz lesen, dann vorhandene Tokens und Bausteine suchen.
2. Klein und reviewbar ändern — ein Schritt, ein Diff, ein Vorher/nachher.
3. **Vergleichsbilder bei gleicher dargestellter Kartenbreite**: die Referenz auf die Kartenbreite skalieren, nie verkleinert danebenstellen; Oberkanten bündig.
4. Jede bewusste Abweichung vor der Umsetzung als **`D-xx`** in `docs/ENTSCHEIDUNGEN.md` festhalten (Grund, Umfang, Fundstellen) und danach die Werte hier nachziehen.
5. Ändert sich ein Token, zuerst den Code, dann Abschnitt 10 — nie umgekehrt.

**Anti-Patterns.** Türkis oder Petrol als Kartenfläche; flächige Verläufe über Karten; leuchtende Ränder; türkise Trenner oder flächige Sekundärflächen; Licht auf normalen Karten; Dimmen von Karte oder Inhalt statt der dekorativen Ebene; vollflächig gefüllte Statuspillen (auch die Erholung); eingefärbte Navigationsflächen, Balken oder Halos; Neon, Bloom, Glassmorphism; fremde App-Layouts 1:1; Emojis oder gemischte Iconstile; Monospace als UI-Schrift; erfundene Scores, Demo-Werte im stabilen Bau, `0` statt `null`; graue, ausgewaschene Sekundärtexte; ein zweiter Fokus pro Abschnitt.
