# Erholungskarte — dunkle Fläche mit lokalem Lichtschein

**Ticket:** TB-7 (Schritt 1 von 2) · **Stand:** 05.11.2026 · **Basis:** `develop` (TB-6-Stand), Branch `feature/tb-7-design-erholungskarte-auf-dunkle-flaeche`
**Ziel:** Die Erholungskarte auf eine neutrale, dunkle Fläche stellen und den flächigen Teal-Verlauf durch einen schwachen, lokal begrenzten radialen Lichtschein ersetzen. Andere Karten, Statusplakette und Navigation bleiben unverändert.

---

## 0. Kurzfassung

- **Kartenbasis:** nahezu schwarz und leicht kühl (`#080D11`) statt `#0D171D` mit flächigem 28-%-Verlauf. Die Karte wirkt auf den ersten Blick dunkel.
- **Lichtschein:** ein schwacher radialer Schein im oberen Bereich, zentriert auf die obere Kartenmitte. Er liegt auf einer eigenen dekorativen Ebene, die weich in vollständige Transparenz ausläuft; unterhalb des oberen Drittels dominiert die dunkle Fläche.
- **Nur die dekorative Ebene ist gedimmt:** Karte und Inhalte bleiben voll deckend (`opacity: 1`). Die Ebene trägt `--recovery-glow-opacity: 0.5`.
- **Ring:** bleibt satt und klar türkis (`--accent` `#35DCC5`, unverändert), er tritt durch die dunklere Umgebung hervor.
- **Unangetastet:** Statusplakette, andere Karten, Navigation, Markup, Layout, Maße, Abstände, Radien, Schriftgrößen, Inhalte, Datenlogik und Zustände.

---

## 1. Umsetzung

### 1.1 Tokens in `web/src/styles.css` (`:root`)

| Token | Wert | Zweck |
|---|---|---|
| `--recovery-surface` | `#080d11` | fast schwarze, leicht kühle Kartenbasis |
| `--recovery-glow` | `rgba(53, 220, 197, 0.36)` | Zentrum des dekorativen Lichtscheins |
| `--recovery-glow-soft` | `rgba(53, 220, 197, 0.08)` | weicher Zwischenstopp, damit keine Kante entsteht |
| `--recovery-glow-opacity` | `0.5` | Deckkraft der dekorativen Ebene (nicht der Karte) |
| `--recovery-ring-glow` | `rgba(53, 220, 197, 0.3)` | unverändert; gehört zum Ring, nicht zur Fläche |

Die alten Tokens `--recovery-wash` und `--recovery-wash-end` aus D-63 sind ersetzt und im Code nicht mehr verwendet. `--accent-wash` und alle globalen Tokens bleiben unverändert.

### 1.2 Karte (`web/src/styles.css`)

- `.recovery` bekommt `background-color: var(--recovery-surface)`, `position: relative` und `isolation: isolate`.
- `.recovery::before` ist die dekorative Hintergrundebene: `position: absolute; inset: 0; z-index: -1; border-radius: inherit; pointer-events: none`. Sie liegt hinter dem Inhalt und wird an den Kartenrundungen beschnitten.
- Der Schein: `radial-gradient(100% 52% at 50% 0%, var(--recovery-glow) 0%, var(--recovery-glow-soft) 45%, transparent 72%)`. Horizontaler Radius 100 % der Kartenbreite, vertikaler Radius 52 % der Kartenhöhe, Zentrum auf der oberen Kante. Ab 72 % des Radius — rund 37 % der Kartenhöhe — ist der Verlauf vollständig transparent.
- Nur `.recovery::before` trägt `opacity: var(--recovery-glow-opacity)`. Karte, Inhalte und Ring bleiben `opacity: 1`.

---

## 2. Nachweis

Alle Aufnahmen: Vorschau-Build dieses Branches (`VITE_APP_VARIANT=preview`), Chromium, Viewport 390 × 844, `deviceScaleFactor: 2`, Ausschnitt ausschließlich der Erholungskarte. Die API-Daten stammen von der laufenden Vorschau `http://127.0.0.1:8101`, damit der echte Zustand „ohne Score“ (2 von 21 Nächten) gilt. `8101` selbst zeigt bis Merge und Deploy noch den alten `develop`-Stand.

| Bild | Inhalt |
|---|---|
| [mit-score-390x844.png](screens/recovery-dunkel/mit-score-390x844.png) | `?demo=recovery`, Score 82, nur die Karte |
| [ohne-score-390x844.png](screens/recovery-dunkel/ohne-score-390x844.png) | ohne Score, „Referenz wird aufgebaut“, 2 von 21 Nächten, nur die Karte |
| [vergleich-mit-score-390x844.png](screens/recovery-dunkel/vergleich-mit-score-390x844.png) | Umsetzung und Referenz bei **gleicher Kartenbreite 350 CSS-px**; die Referenz ist auf die Kartenbreite beschnitten und mitskaliert |
| [vergleich-ohne-score-390x844.png](screens/recovery-dunkel/vergleich-ohne-score-390x844.png) | dito für den Zustand ohne Score |

Der Demo-Score 82 erscheint ausschließlich im Vorschau-Build unter `?demo=recovery`; das Demo-Abzeichen sitzt außerhalb des Kartenausschnitts im Seitenkopf. Ohne Score wird kein Wert erfunden.

**Gemessene Farben an der Karte** (2×-Aufnahme, obere Kante mittig / Basis unten):

| Punkt | Vorher (8101) | Nachher | Referenz |
|---|---|---|---|
| oben, mittig | `#174E4B` | `#103231` | `#093736` |
| Basis unten | `#0D171D` | `#080D11` | `#041115` |

Die Karte ist damit deutlich dunkler als vorher; der Lichtschein ist schwächer als in der Referenz und läuft früher ins Schwarze — genau die gewünschte Richtung „dunkle Fläche, lokaler Schein“.

---

## 3. Umfang

**Geändert:**

- `web/src/styles.css` — Recovery-Tokens, `.recovery`, `.recovery::before`
- `docs/ENTSCHEIDUNGEN.md` — D-64 und Log-Zeile
- `docs/design/recovery-dunkel.md` — dieser Bericht
- `docs/design/screens/recovery-dunkel/` — die vier Nachweisbilder

**Nicht geändert:**

- `web/src/pages/Today.tsx`, `web/src/components/RecoveryDial.tsx`, `web/src/components/ui.tsx`
- Karten `Training` und `Letzte 7 Tage`, Statusplakette, Navigation
- API, Berechnungen, Datenbank, Sync, Demo-Logik

---

## 4. Prüfung

- `uv run pytest`: **148 passed**, 1 bestehende Starlette-Warnung.
- `npm run build` (stabil, ohne Vorschau-Variante): grün, CSS 35,04 kB, JS 266,70 kB.
- `VITE_APP_VARIANT=preview npm run build`: grün, Demo-Zweig enthalten; die Bilder stammen aus diesem Build.
- Kartenmaße unverändert gegenüber 8101: bei 390 px `350 × 431,39 px` (mit Score) bzw. `350 × 506,80 px` (ohne Score); bei 1440 px `1128 × 327,50 px`. Kein horizontaler Überlauf bei 320, 390 und 1440 px.
- Andere Flächen unverändert: Training und Woche `rgb(13, 23, 29)` ohne Hintergrundbild; Statusplakette `rgb(53, 220, 197)` auf `rgb(4, 16, 14)`; Ring `rgb(53, 220, 197)` bei Score.
- Deckkraft: Karte `1`, Inhalte `1`, nur `.recovery::before` `0.5`.
- Kontrast auf der neuen Basis: Titel 18,33:1, Sekundärtext 9,65:1, Muted 6,04:1, Untertitel im Scheinbereich 5,74:1, Statusplakette 11,23:1.
- Branch bewusst von `develop` statt `main` abgezweigt: TB-3 (Premium-Redesign), TB-4 (Demo), TB-5 und TB-6 liegen nur auf `develop`; `main` ist ein Vorfahr. Von `main` aus wäre dieser Stand nicht erreichbar.

---

## 5. Offene Punkte

- **Schritt 2** (andere Karten, Statusplakette, Navigation) ist nicht begonnen; nach diesem Schritt STOPP und Freigabe abwarten.
- Ein echter 21-Nächte-Score entsteht erst ab 24.11.2026; der Score-Zustand ist weiterhin nur über die Demo beurteilbar.
- `8101` zeigt den neuen Stand erst nach Merge und Deploy.
