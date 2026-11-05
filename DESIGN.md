# DESIGN.md — Cockpit Design System

> **Status:** Verbindliche Gestaltungsrichtlinie · **Version:** 1.0 · **Stand:** 05.11.2026  
> **Produkt:** Persönliches Trainings-, Erholungs- und Verpflegungs-Dashboard (mobile-first PWA)  
> **Visuelle Referenz:** `cockpit-premium-reference.png` (abgestimmtes Premium-Redesign vom 05.11.2026)

## 0. Zweck und Geltungsbereich

Dieses Dokument ist die **Single Source of Truth für UI/UX**. Es gilt für **alle** aktuellen und zukünftigen Screens, Tabs, Komponenten, Dialoge, Diagramme und Zustände. Es legt die *visuelle und interaktive Sprache* fest, nicht die Fachlogik oder API-Verträge.

**Prioritätsregel:** Ein neues Feature passt sich dem Designsystem an — nicht umgekehrt. Bestehende Tokens und Komponenten werden wiederverwendet. Abweichungen sind nur nach bewusster Designentscheidung zulässig und müssen hier dokumentiert werden.

**Grundidee:** *Calm performance.* Eine fast schwarze, elegante Oberfläche, die den Fokus durch Kontrast, großzügige Abstände, klare Typografie und **sparsam eingesetztes, sattes Türkis** auf die wichtigsten Informationen lenkt. Hochwertig, präzise, sportlich, nicht verspielt. Kein WHOOP-/Bevel-Klon.

**Visueller Referenzumfang:** Die Referenz ist eine **Stil- und Layoutvorlage**. Ihre Zahlen und Zustände sind Mock-Daten und dürfen **niemals** die echten Daten der App ersetzen. Insbesondere darf ein Recovery-Wert **nicht** angezeigt werden, solange die erforderliche Sensorreferenz fehlt.

---

## 1. Nicht verhandelbare Prinzipien

1. **Information vor Dekoration.** Jedes visuelle Element muss Orientierung, Lesbarkeit, Interaktion oder Datenauswertung verbessern.
2. **Premium durch Zurückhaltung.** Wenige Akzente, viel Luft, harmonische Radien und klare Hierarchie statt Neon, Glow-Flächen, übertriebener Schatten oder bunter Kacheln.
3. **Ein Fokus pro Abschnitt.** Eine Karte bekommt höchstens einen dominanten visuellen Fokus (z. B. Erholungsring, Trainingssession oder Hauptdiagramm).
4. **Echte Daten vor schönen Daten.** Nicht verfügbare Metriken bleiben nicht verfügbar; keine fiktiven Werte, Scores, Trendpfeile oder positiven Statuslabels.
5. **Gleiches Verhalten überall.** Einheitliche Navigations-, Lade-, Fehler-, Leer-, Detail- und Interaktionsmuster.
6. **Mobile first.** Optimiert für einhändige Nutzung auf iPhones, ebenso verwendbar als Android-PWA und auf Desktop.
7. **Barrierefreiheit als Standard.** Lesbarer Kontrast, semantische Labels, Tastaturbedienung, reduzierte Bewegung.
8. **Progressive Disclosure.** Die Startseite liefert den Überblick; Details und Erläuterungen liegen auf dedizierten Seiten oder nach explizitem Öffnen.

---

## 2. Design Tokens

Tokens **einmal zentral** definieren und in Komponenten verwenden. Keine verstreuten Hex-Werte, Freihand-Abstände oder komponentenspezifischen Farbsysteme. Die Werte unten sind der verbindliche Ausgangspunkt; nach Screenshot-Vergleich dürfen nur die **zentralen Tokens**, nicht einzelne Komponenten willkürlich, feinjustiert werden.

### 2.1 Farben — Dark Mode (primär)

| Token | Hex | Verwendung |
|---|---|---|
| `--bg-app` | `#05090D` | Seitenhintergrund, App-Canvas |
| `--bg-surface` | `#0D171D` | Standard-Karten |
| `--bg-surface-raised` | `#102229` | leicht hervorgehobene Zeilen, Training-Preview |
| `--bg-surface-interactive` | `#132B31` | Hover/Pressed, aktive untergeordnete Elemente |
| `--border-subtle` | `#203039` | Kartenkontur, Listentrenner |
| `--border-strong` | `#2D4650` | fokussierte Eingaben, betonte Konturen |
| `--text-primary` | `#F6F8FA` | Titel, Kernwerte, wichtigste Labels |
| `--text-secondary` | `#ABB8C4` | Beschreibung, Einheiten, Standardmetadaten |
| `--text-muted` | `#82919F` | Achsen, Hilfstexte, Nebendaten |
| `--accent` | `#35DCC5` | aktiver Tab, aktueller Datenpunkt, Interaktion |
| `--accent-hover` | `#5CE8D5` | Hover und Fokusakzent |
| `--accent-soft` | `#123831` | kleine ausgewählte Flächen und Badges |
| `--positive` | `#49DEA4` | positive Veränderung, gute Statuswerte |
| `--warning` | `#F3BE6A` | Hinweise, mittelmäßiger Zustand |
| `--negative` | `#F1787F` | kritischer Status, Fehler |
| `--info` | `#64BDE2` | neutrale Information |
| `--chart-neutral` | `#465763` | normale Diagrammbalken |
| `--chart-neutral-strong` | `#78909E` | ausgewählter neutraler Balken |

**Kontrastziel:** Normaler Text mindestens WCAG-AA 4,5:1, große Schrift 3:1; interaktive Elemente und Informationsgrafiken möglichst 3:1. Tokenwerte bei Bedarf **zentral** nach tatsächlichem Kontrasttest anpassen. `--text-muted` ist für beiläufige Labels, nicht für längere Fließtexte.

**Accent-Budget:** Türkis ist keine allgemeine Dekorationsfarbe. Pro Karte normalerweise **maximal ein dominantes Accent-Element**. Zahlen bleiben in der Regel weiß. Weitere Akzente nur bei bedeutungstragenden Datenpunkten, Status oder Interaktion.

**Statusfarben sind semantisch:** Positive/negative Trends nicht allein über Rot/Grün vermitteln: immer auch Text, Vorzeichen, Richtung oder Bezeichnung verwenden. Ein hoher Wert ist nicht automatisch positiv; die Datenlogik bestimmt die Bewertung.

### 2.2 Hintergrund, Verläufe und Glow

- Seitenhintergrund grundsätzlich **nahezu schwarz und ruhig**.
- Karten dürfen ein **sehr schwaches** vertikales Ton-in-Ton-Farbspiel bekommen (ca. 2–5 % Differenz). Keine sichtbaren, großflächigen bunten Farbwolken.
- Kartenkontur: 1 px `--border-subtle`, Schatten nur wenn sie tatsächlich Tiefe liefern (z. B. `0 10px 30px rgba(0,0,0,.14)`).
- **Aktiver Bottom-Tab:** Icon in `--accent`, Label `--text-primary`. Optional ein **sehr kleiner, nahezu unsichtbarer** Akzent unter dem Icon; Blur maximal ca. 6 px, geringe Deckkraft (ca. 8–12 %). **Kein breiter Halo/Hue-Glow, kein leuchtender Balken.**
- Erholungsring und aktiver Diagrammbalken dürfen klar türkis sein — **ohne** starke Neon-Aura.
- Farbverläufe ausschließlich für dezente Oberflächentiefe oder fachlich sinnvolle Datenskalen; niemals automatisch pro Karte.

### 2.3 Typografie

| Rolle | Schrift | Größe/Zeilenhöhe | Gewicht | Verwendung |
|---|---|---|---|---|
| Editorial-Datum | `Iowan Old Style`, `Baskerville`, `Georgia`, serif | 32/38 px, mobil responsiv 28–36 | 400 | **nur** großes Datum bzw. editorialer Hauptmoment |
| Screen-Titel | System UI (`-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, sans-serif) | 26/32 px | 600 | normale Seitentitel |
| Card-Titel | System UI | 20/26 px | 600 | „Erholung“, „Training“, „Letzte 7 Tage“ |
| Hauptkennzahl | System UI | 50–64/1.0 px | 650 | ein fokussierter Score pro Bereich |
| Kennzahl | System UI | 23–28/1.2 px | 600 | HRV, Ruhepuls, Umfang |
| Body | System UI | 15–16/23 px | 400 | Erklärungen, Zeilen |
| Secondary / Label | System UI | 13–14/19 px | 400–500 | Einheiten, Hilfstexte, Chartlabels |
| Micro | System UI | 12/16 px | 500 | nur sparsam für kurze Zusatzlabels |

- Keine Emoji-Zeichen als UI-Icons.
- Maximal **zwei Schriftfamilien**: System-UI plus **ein Serif-Akzent ausschließlich beim Datum**.
- `font-variant-numeric: tabular-nums` für Kennzahlen und zeilenweise vergleichbare Werte; kein technisch wirkendes Monospace als allgemeine UI-Schrift.
- Überschriften nicht durchgehend in Versalien; wenn überhaupt nur kurze Metadaten.
- Große Zahlen: schmale Buchstabenabstände (ca. `-0.02em`); Fließtext normal.
- Einheit optisch kleiner als Zahl (`62 ms`, `46 bpm`, `6:50 h`), aber noch gut lesbar.
- Nutzerseitige System-Schriftvergrößerung unterstützen; Zahlen/Zeilen dürfen nicht abgeschnitten werden.

### 2.4 Abstände, Raster, Formen

| Token | Wert | Regel |
|---|---|---|
| `--space-1` | 4 px | Miniabstand |
| `--space-2` | 8 px | zusammengehörige Elemente |
| `--space-3` | 12 px | kleinere Gruppen |
| `--space-4` | 16 px | normale innere Gruppen |
| `--space-5` | 20 px | **Standard-Seitenrand mobil** |
| `--space-6` | 24 px | Standard-Card-Padding |
| `--space-8` | 32 px | größerer Abschnittsabstand |
| `--radius-card` | 22 px | Hauptkarten |
| `--radius-inner` | 14 px | eingebettete Elemente |
| `--radius-control` | 12 px | Buttons, kleine Felder |
| `--radius-pill` | 999 px | Statuschips |

- **4-px-Basisraster**. Keine zufälligen Werte wie 17, 19, 27 px für Standardabstände.
- Seitenrand mobil: 20 px; bei sehr schmalen Screens 16 px. Kartenabstand: 16–20 px.
- Karteninhalt: 20–24 px; kompakte Reihen mindestens 12–16 px vertikaler Nutzraum.
- Inhalt zwischen Sektionen optisch gruppieren: erst Typografie/Spacing, danach Linien und zusätzliche Container.
- Mobile Touchfläche mindestens 44 × 44 CSS-px; primäre Touchflächen bevorzugt 48 px hoch.
- **Keine „Card in Card in Card“-Ketten.** Ein eingebetteter Trainingsvorschau-Eintrag darf als subtile Zeile dargestellt werden, nicht als vollwertige zweite große Karte.

### 2.5 Iconografie

- Eine einheitliche Outline-Iconfamilie (z. B. **Lucide**), nicht mehrere Stile mischen.
- Größen: 18–20 px in Listen und Tabbar; 22–24 px in wichtigen Actions.
- Stroke meist 1,75–2 px, geometrisch konsistent.
- Icons nur für Erkennbarkeit/Navigation: sparsam, keine Icons vor **jeder** Kennzahl.
- Fachicons (Rad, Schlaf, Herz) erhalten Accent nur dann, wenn ausgewählt oder bewusst hervorgehoben.
- **Keine Emojis**, bunte Illustrationen, Sticker oder generischen Cliparts.

---

## 3. Layout und Navigation

### 3.1 Startseite (verbindliche Hierarchie)

1. **Header:** kompakte Produktkennung „Cockpit“ + ggf. Preview/Sync-Status; großes, elegantes Datum mit Serif-Akzent; „Zuletzt synchronisiert …“ als sekundäre Information.
2. **Wettkampf-Countdowns:** bis zu drei Ziele als ruhige Spalten mit feinen Trennlinien; Tage optisch führend, Wettkampfbezeichnung sekundär.
3. **Erholung:** wichtigste Hauptkarte; Zustand/Score bzw. Baseline-Aufbau, anschließend Nachtmetriken und nachvollziehbarer Hinweis.
4. **Training:** Tagesstatus sowie nächste geplante Einheit als übersichtliche, klickbare Vorschau.
5. **Letzte 7 Tage:** zurückhaltendes Balkendiagramm mit Tag-Markierung und wichtige Summen in Listenform.
6. **Bottom Navigation:** dauerhaft erreichbar, ruhig und klar.

**Nicht alles muss über der Falz liegen.** Lesbarkeit ist wichtiger als maximale Datenmenge im ersten Bildschirm.

### 3.2 Bottom Navigation

- Für 2–5 wesentliche Hauptbereiche. Aktive Tabs: türkises Outline-Icon + helles Label; inaktive: `--text-muted`.
- **Sehr dezente** Hinterlegung/Glow für aktiv; möglichst nur der Iconfarbwechsel und die Typografie unterscheiden den Zustand.
- Keine farbigen vollflächigen Tabs, keine springenden/auffälligen Animationen.
- Gleicher Iconstil, gleich große Touchfläche und identische vertikale Ausrichtung bei allen Tabs.
- Fixierte Leiste inklusive `env(safe-area-inset-bottom)`; Scrollinhalt muss unten entsprechend Platz haben.
- Detailansichten eröffnen **keinen neuen Haupttab**. Navigation erfolgt über Unterseiten mit klarer Zurückfunktion.
- Browser-Back (PWA), direkte URLs und Wiederherstellung der ausgewählten Seite dürfen nicht brechen.

**Desktop-Variante:** Ab 1001 px erscheint dieselbe Navigation als ruhige Seitenleiste (248 px). Sie nutzt dieselbe Liste und denselben Iconstil; der aktive Zustand ist auch dort nur Akzent-Icon und helles Label. Die Bottom-Tabbar bleibt die mobile Hauptnavigation.

### 3.3 Responsive

- **Mobile:** einspaltig, ca. 320–430 px breit; bei 320 px Zweizeiler und Overflow bewusst prüfen.
- **Tablet (ab ca. 768 px):** nutzbare Inhaltsbreite begrenzen, optionale 2 Spalten für sekundäre Karten; Hauptmetrik prominent.
- **Desktop (ab ca. 1100 px):** Dashboard in begrenztem Container (ca. 1080–1200 px), maximal 2–3 sinnvolle Bereiche nebeneinander; keine extrem breiten Karten/Diagramme.
- Gestalte zuerst mobil, skaliere semantisch nach oben; keine separate visuelle Sprache je Gerät.
- Berücksichtige Notch, Dynamic Island, Scrollbars, WebView/PWA-Safe-Areas und iOS-Zoom.

---

## 4. Wiederverwendbare Komponenten

### 4.1 `ScreenHeader`

**Aufbau:** Kontext/Product Label → optional Sync-/Preview-Hinweis → großes Datum/Seitentitel → kompakte Statuszeile. Keine unnötigen Grafiken. Das Datum darf als einziges serif gesetzt werden.

### 4.2 `DashboardCard`

- Oberfläche `--bg-surface`, 1-px-Rand, `--radius-card`, 20–24 px Padding.
- Kopf aus Titel + optionalem Untertitel/Action; keine Standard-Dekoicons in jedem Header.
- Card-Titel linksbündig, Daten in klarem Raster.
- Gleiche Abstände für alle Karten; unterschiedliche Höhe ergibt sich aus Inhalt, nicht aus Fantasie-Minheights.
- Clickable Card nur, wenn die gesamte Card wirklich navigiert; sonst eindeutige interne Actions.

### 4.3 `MetricRow` und `MetricGroup`

- Links ein klares Label, rechts ein gut lesbarer Wert mit Einheit.
- Optional darunter Trend, Referenzwert und Zeitraum; Veränderungen sind nie ohne Vergleichszeitraum dargestellt.
- Reihen mit feinen Dividern statt vielen Kästchen.
- Bei einer kleinen 3er-Metrikgruppe darf die Darstellung horizontal sein, wenn die Werte auf 320–375 px lesbar bleiben; sonst untereinander.
- Keine farbigen Icons vor HRV, Puls, Schlaf usw., wenn sie nichts zur Interpretation beitragen.

### 4.4 `RecoveryCard` / `RecoveryGauge`

- Die Karte ist das wichtigste Datenelement; Ring oder Score als **ein** visueller Schwerpunkt.
- **Mit gültiger Referenz:** berechneten Score plus sinnvoll zugeordneten Status und Datenbasis darstellen. Große Zahl; Ring/Progress nur ergänzend.
- **Ohne gültige Referenz (z. B. 2 von 21 Nächten):** **kein Score, kein positiver Status, keine fiktive Prozentanzeige und kein grüner „fertiger“ Ring**. Stattdessen neutrales Ringskelett/Referenzfortschritt plus „Referenz wird aufgebaut“ und „2 von 21 Nächten“.
- Letzte Nacht: HRV, Ruhepuls, Schlaf (nur wenn vorhanden) dürfen unabhängig von der Recovery-Kalibrierung angezeigt werden, klar als Nachtwerte beschriftet.
- Hinweis auf neuen Sensor ist funktional und verständlich, nicht als dominantes Warnfeld.
- Ringe nie allein durch Farbe verständlich machen; Zahlen/Text ergänzen.

### 4.5 `WorkoutPreview`

- Sportarten-Icon dezent; Workout-Name vorrangig; darunter Dauer, Ziel/Distanz und Status.
- „Geplant“, „Erledigt“ oder „Ausgefallen“ als kleine semantische Statuschips, nicht riesige Vollflächen.
- Bei „Heute nichts geplant“ ruhig erklären und optional **morgen** zeigen; keine erzwungene leere Grafik.
- Klick öffnet Workout-Details; Card verschwindet bei fehlenden Daten nicht ersatzlos, sondern zeigt einen klaren Empty State.

### 4.6 `TrendChart` / `WeeklyActivityChart`

- Bars für nicht ausgewählte Tage in zurückhaltendem Blau-Grau. **Aktueller Tag** in Türkis, aber nur wenn diese Markierung sachlich richtig ist.
- Keine starken Glows oder 3D-Verläufe. Sehr sanfte vertikale Tiefenabstufung ist erlaubt.
- Minimale, gut lesbare Achsenbeschriftung. Einheit, Zeitraum und Datenbasis explizit benennen.
- Fehlende Tage ≠ null Trainingslast. Unvollständige Tage visuell unterscheiden, falls relevant.
- Ein ausgewählter Balken erhält klar erkennbare Dateninformation/Tooltip oder Detailansicht.
- Diagramme immer mit textlicher Zusammenfassung bzw. zugänglichem Alternativinhalt anbieten.

### 4.7 `StatusBadge`, `Action`, `Divider`, `Skeleton`, `EmptyState`

- `StatusBadge`: kleine Pill, gedämpfter semantischer Hintergrund; keine grellen Vollflächen.
- `Action`: Primäraktionen in Türkis nur, wenn tatsächlich handlungsrelevant; Sekundäraktionen zurückhaltend.
- `Divider`: 1 px `--border-subtle` und ausreichender Luftabstand.
- `Skeleton`: Form der späteren Inhalte übernehmen, sanftes Shimmer nur ohne `prefers-reduced-motion`.
- `EmptyState`: konkrete Ursache, mögliche nächste Aktion; niemals erfundene Inhalte.

---

## 5. Daten- und Zustandsdesign

Eine Premium-Oberfläche überzeugt durch **Verlässlichkeit**, nicht nur Optik.

| Zustand | UI-Verhalten | Verbot |
|---|---|---|
| Laden | Platzhalter in tatsächlicher Layoutform | Layoutsprünge, irreführende Nullen |
| Keine Daten | „Noch keine Daten vorhanden“ und Datenquelle/Handlung | `0` als Ersatz für `null` |
| Baseline wird aufgebaut | Fortschritt `x von y Nächten`; neutrale Visualisierung | erfundener Recovery-Score oder „Gut“ |
| Sync veraltet | Zeitpunkt des letzten erfolgreichen Syncs, optional Refresh | stillschweigend „aktuell“ suggerieren |
| API-Fehler | freundlich, konkret, mit Wiederholen-Aktion | leere Karten ohne Erklärung |
| Teilweise Daten | verfügbare Kennzahlen zeigen, fehlende explizit markieren | ganze Karte verstecken oder schätzen |
| Training nicht geplant | ruhiger Empty State, nächstes Training falls bekannt | Demo-Einheit als echt anzeigen |
| Offline | letzten bestätigten Datenstand mit Zeitstempel zeigen | so tun, als wären Daten live |

- Datums- und Zeitformat deutsch, Zeitzone bewusst behandeln; kein Vermischen von Sync-Zeit, Workout-Zeit und Gerätedatum.
- Abkürzungen wie HRV und Belastungsverhältnis sollten eine auffindbare Erläuterung erhalten.
- Zahlenformat in Deutsch (`1,28`, `11 h 21 min`), Einheiten konsistent (`ms`, `bpm`, `km`, `W`, `h`).
- Veränderungen nur mit Referenz erklären: `+8 % vs. persönlicher Basiswert`, nicht nur `+8 %`.
- Bei gesundheitlich wirkenden Scores nicht suggerieren, dass ein UI-Indikator allein eine medizinische Entscheidung begründet.

---

## 6. Interaktion, Motion und Accessibility

- Navigation/Interaktionen müssen vorhersehbar sein. Keine Tap-Ziele in Konkurrenz und keine unklaren Klickflächen.
- Taps visuell unmittelbar quittieren; Pressed-Zustand kann Oberfläche minimal aufhellen.
- Animationen sparsam: üblicherweise **160–240 ms**, easing `ease-out`; keine springenden Kennzahlen, pulsierenden Glows oder unnötiges Parallax.
- `prefers-reduced-motion: reduce` konsequent berücksichtigen.
- Mobile Touchflächen mind. 44×44 CSS-px, genügend Abstand für Fehlertaps.
- Texte lassen sich vergrößern, Content kann horizontal nicht ungewollt scrollen.
- Semantische HTML-Elemente, sichtbarer Fokus, Tastaturbedienbarkeit, Screenreader-Beschreibungen für Scores und Charts.
- Aktive Zustände nicht nur farblich unterscheiden: aktives Tab erhält z. B. helleres Label und `aria-current="page"`.
- Ohne aktive Eingabe keine dauernd laufenden Animations-/Polling-Effekte im Frontend.

---

## 7. Muster für neue Features

**Ein neuer Screen muss aus wiederverwendbaren Bausteinen zusammengesetzt werden:**

1. **ScreenHeader** mit passendem Titel/Zeitraum.
2. **Eine Hauptinformation** („Hero“), sofern fachlich sinnvoll.
3. **Sekundäre Kennzahlen** als MetricRows oder kleine MetricGroup.
4. **Ein sinnvoller Verlauf** bei zeitabhängigen Daten.
5. **Details / Erklärungen** hinter vertiefender Navigation statt alles auf der Startseite.
6. **Alle Zustände:** Loading, Empty, Error, Partial, Offline, Success.
7. **Tabs nur bei dauerhaften Hauptbereichen**, nicht für jede neue Funktion.

**Beispiel „Verpflegung“:** Oben Tagesziel und bisherige Aufnahme als ruhige Hauptkennzahl; danach Kalorien/Kohlenhydrate/Flüssigkeit in derselben Typografie und denselben MetricRows; Einträge als kompakte Liste; Verlauf im gemeinsamen `TrendChart`; türkiser Akzent nur für aktuelle Auswahl oder einen fachlich relevanten Fortschritt — **keine bunten Lebensmittel-Emojis**.

**Beispiel „Trainingsdetail“:** Trainingsname und Status, wesentliche Vorgaben (Sportart/Dauer/Intensität), zeitlicher Verlauf falls vorhanden, Notizen und Quellhinweise; die gleiche Card-, Listen- und Icon-Sprache wie auf dem Dashboard.

---

## 8. Technische Umsetzungshinweise (frameworkneutral)

Empfohlene zentrale CSS Custom Properties als Ausgangspunkt:

```css
:root {
  color-scheme: dark;
  --bg-app: #05090d;
  --bg-surface: #0d171d;
  --bg-surface-raised: #102229;
  --bg-surface-interactive: #132b31;
  --border-subtle: #203039;
  --border-strong: #2d4650;
  --text-primary: #f6f8fa;
  --text-secondary: #abb8c4;
  --text-muted: #82919f;
  --accent: #35dcc5;
  --accent-hover: #5ce8d5;
  --accent-soft: #123831;
  --positive: #49dea4;
  --warning: #f3be6a;
  --negative: #f1787f;
  --info: #64bde2;
  --chart-neutral: #465763;
  --chart-neutral-strong: #78909e;
  --radius-card: 22px;
  --radius-inner: 14px;
  --radius-control: 12px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
}

body {
  background: var(--bg-app);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-variant-numeric: tabular-nums;
}

.dashboard-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: var(--space-6);
}

.bottom-nav__item[aria-current="page"] {
  color: var(--accent);
  /* Absichtlich KEIN großflächiger Glow. */
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Framework-Regel:** Bestehendes Framework respektieren (React/Vue/Blazor/Svelte etc.). Tokens an vorhandene CSS- oder Theme-Mechanismen anbinden. Kein Frameworkwechsel nur für das Design.

**Architekturregel:** Fachlogik, API-Clients, Authentifizierung, Persistenz, Synchronisierung und Trainingsberechnungen bleiben vom Designsystem getrennt. Visualisierung bindet an bestehende Datenmodelle; keine hartcodierten Mock-Daten in produktiven Komponenten.

---

## 9. Qualitätskontrolle und Definition of Done

Jeder neue Screen und jede wesentlich geänderte Komponente muss diese Checkliste erfüllen:

- [ ] Nutzt ausschließlich zentrale Design Tokens, keine willkürlichen Farben/Abstände.
- [ ] Verwendet vorhandene `DashboardCard`, `MetricRow`, `StatusBadge`, `TrendChart` etc. wo passend.
- [ ] Hat nachvollziehbare visuelle Hierarchie: Titel → Hauptwert → Kontext → Details.
- [ ] Türkis wird gezielt verwendet; aktiver Tab hat **höchstens minimalen** Glow.
- [ ] Keine Emojis und keine Mischung verschiedener Iconstile.
- [ ] Karten haben konsistente Radien, Innenabstände, Konturen und Trenner.
- [ ] Echte Daten und echte Zustände: null, Loading, Error, Baseline, Stale Sync korrekt.
- [ ] Keine Änderung an Fachlogik, API-Verträgen, Berechnungen oder Auth durch UI-Arbeiten.
- [ ] Geprüft auf schmalem iPhone (320 px), regulärem iPhone (375–393 px), großem Telefon (430 px), Desktop.
- [ ] Navigation, Back-Handling, Scrollbereich und Safe Areas funktionieren.
- [ ] Mindestens AA-Textkontrast (nachgemessen), Tap-Ziele und Screenreader-Labels geprüft.
- [ ] Screenshots vor/nach der Änderung mit `cockpit-premium-reference.png` verglichen.
- [ ] Tests/Build laufen; UI-Änderungen und bewusste Abweichungen dokumentiert.

### Gestalterische Verbote (Anti-Patterns)

- Keine Bevel-/WHOOP-Layouts 1:1 übernehmen.
- Keine farbenfrohen Emojis als Ersatz für Icons.
- Keine übertriebenen Hue-, Bloom-, Neon- oder Glassmorphism-Effekte.
- Keine großen türkisen Flächen ohne funktionale Begründung.
- Keine fünf voneinander unabhängigen Card-Designs auf einer Seite.
- Keine Dark-Mode-Texte in zu hellem Grau auf zu hellem Dunkelgrau („ausgewaschen“).
- Keine Mockwerte statt nicht verfügbarer Sensordaten.
- Kein „alles neu schreiben“, wenn ein schrittweiser Umbau möglich ist.

---

## 10. Änderungsprozess für dieses Designsystem

1. Bei einem neuen Feature zuerst dieses Dokument und den Referenzscreen lesen.
2. Bereits verfügbare Tokens/Komponenten identifizieren.
3. Wenn ein Muster fehlt: eine kleine, allgemeingültige Komponente vorschlagen; nicht lokal improvisieren.
4. Designabweichungen **vor** der Umsetzung ausdrücklich begründen und zur Freigabe vorlegen.
5. Nach Freigabe Token-/Komponentenänderung hier dokumentieren; anschließend alle betroffenen Screens konsistent aktualisieren.
6. Änderungen als kleine, reviewbare Schritte mit visueller Kontrolle umsetzen.

**Leitfrage für jeden PR:** „Sieht das Feature nach *Cockpit* aus — oder nach einer fremden App, die zufällig im selben Projekt liegt?“
