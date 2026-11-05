# Erholungskarte — Vergleich mit der Referenz

**Ticket:** TB-6 · **Stand:** 05.11.2026 · **Basis:** `develop` (TB-3 Premium-Redesign, TB-4 Demo-Zustand, TB-5 fünfte Stufe)
**Ziel:** Startseite im Vorschau-Build näher an `cockpit-premium-reference.png`; Vergleichsmaßstab ist `?demo=recovery`.

---

## 0. Kurzfassung

- Die Erholungskarte trägt jetzt den **einzigen kräftigen Farbverlauf** der Seite:
  Türkis von 28 % Deckkraft oben, nach unten auslaufend. Die übrigen Karten
  bleiben neutral. Der Score-Ring bekommt einen dezenten inneren Schein.
- **Mit Score** steht die Karte mobil (≤ 1000 px) zweispaltig: links Score mit
  „/ 100", gefüllte Türkis-Plakette, „Nacht vom …" und die Referenzzeile; rechts
  der Ring (148 px bei 390 px) mit Puls-Icon und Referenzmarker. Darunter eine
  Trennlinie und HRV, Ruhepuls, Schlaf als drei Spalten mit Delta zur eigenen
  Baseline.
- **Ohne Score** bleibt die Anordnung unverändert: zentrierter Ring,
  „Referenz wird aufgebaut", „2 von 21 Nächten". Nur die Kartenfarbe gilt auch
  hier, weil sie zur Karte gehört.
- Die Demo bleibt ausschließlich im Vorschau-Build und nur mit sichtbarem
  Abzeichen „Demo"; der stabile Bau enthält den Zweig nicht.

---

## 1. Aufnahme

- **Baulage:** lokaler Vorschau-Build (`VITE_APP_VARIANT=preview`) dieses
  Branches, ausgeliefert über einen lokalen Proxy. Die API kam von der
  laufenden Vorschau `http://127.0.0.1:8101`, damit derselbe echte
  Referenzaufbau (2 von 21 Nächten, kein Score) gilt wie in der Vorschau.
  `8101` selbst zeigt bis zum Merge weiterhin den alten `develop`-Stand.
- **Branch-Basis:** bewusst von `develop` statt `main` abgezweigt. `?demo=recovery`
  (TB-4, D-60), das Premium-Redesign (TB-3) und D-61/D-62 liegen nur auf
  `develop`; `main` ist ein Vorfahr. Von `main` aus wäre der geforderte
  Demo-Vergleich nicht möglich.
- **Browser:** Chromium (`CHROME_PATH=/usr/bin/chromium`) über Puppeteer,
  Viewport-Screenshots (`fullPage: false`), `deviceScaleFactor=1`.
- **Viewports:** 390 × 844 und 1440 × 900.
- **Referenz:** `cockpit-premium-reference.png` (852 × 1846) unverändert als
  dritte Spalte, auf die jeweilige Viewport-Höhe skaliert.

| Bild | Inhalt |
|---|---|
| [ohne-score-390x844.png](screens/recovery/ohne-score-390x844.png) | Vorschau 390 × 844, echte Daten ohne Score (2/21) |
| [mit-score-390x844.png](screens/recovery/mit-score-390x844.png) | 390 × 844, Demo `?demo=recovery` |
| [vergleich-390x844.png](screens/recovery/vergleich-390x844.png) | ohne Score · mit Score · Referenz |
| [ohne-score-1440x900.png](screens/recovery/ohne-score-1440x900.png) | Desktop 1440 × 900, ohne Score |
| [mit-score-1440x900.png](screens/recovery/mit-score-1440x900.png) | Desktop 1440 × 900, Demo |
| [vergleich-1440x900.png](screens/recovery/vergleich-1440x900.png) | ohne Score · mit Score · Referenz |

---

## 2. Punkt für Punkt

### 2.1 Kartenfarbe

**Jetzt gleich:** Die Erholungskarte ist die einzige farbige Fläche. Der Verlauf
beginnt oben kräftig türkis (28 % Deckkraft) und läuft nach unten aus
(`--recovery-wash`, `--recovery-wash-end`, transparent bei 82 %). Kartenkontur,
Radius und der neutrale Grundton bleiben; Training und „Letzte 7 Tage" sind
unverändert neutral. Kein Neon, kein Schein auf anderen Karten.

**Noch abweichend:** Die Referenz läuft etwas früher ins Schwarze; im direkten
Vergleich wirkt unsere Karte in der unteren Hälfte eine Spur türkiser. Der
Verlauf ist bewusst als Token angelegt und nicht pro Komponente improvisiert.

### 2.2 Anordnung mobil (≤ 1000 px, nur mit Score)

**Jetzt gleich:**

- Zweispaltig: links Score **82** groß, „/ 100" klein daneben; darunter die
  **gefüllte Türkis-Plakette** mit dunkler Schrift („Gut").
- Darunter „Nacht vom 5. November" und die Zeile
  „21 von 21 Nächten · Schnitt 76". Beide stehen in der linken Spalte; die
  Zeile läuft **nicht** unter dem Ring durch. Gemessen bei 390 px: linke Spalte
  41–188,8 px, Ring 200,8–349 px, dazwischen 12 px Luft.
- Rechts der Ring mit **148 px** bei 390 px, **Puls-Icon mittig** (24 px) und
  dem vorhandenen Marker für den Referenzschnitt (76).
- Unter einer Trennlinie die Nachtwerte als **drei Spalten**: HRV 62 ms,
  Ruhepuls 46 bpm, Schlaf 6:50 h. Darunter das Delta zur eigenen Baseline:
  **+8 %**, **−3 bpm**, **−10 min**. Die Deltas rechnen aus den vorhandenen
  Feldern (`today` gegen `baseline`, ersatzweise `average`) der
  Erholungskomponenten; kein neues API-Feld, keine erfundene Zahl.
- Bei 320 px bleiben zwei Spalten: Der Ring schrumpft auf 122 px, der Score auf
  44 px; gemessen kein horizontaler Überlauf (`scrollWidth == clientWidth`).

**Noch abweichend:**

- Die Referenz zeigt an dieser Stelle weder „Nacht vom …" noch die
  Referenzzeile — beides ist Ticketvorgabe und deshalb bewusst zusätzlich da.
  Bei 390 px bricht die Referenzzeile nach „Schnitt" auf zwei Zeilen; das ist
  der schmalen linken Spalte geschuldet und überlappt den Ring nicht.
- Die Referenz zeigt beim Schlaf „91 % Ziel"; wir zeigen auftragsgemäß das
  Delta zur Baseline („−10 min"). Das ist eine andere, aber belegte Kennzahl.
- Der Demo-Zustand trägt weiterhin das Band „Gut" (aus TB-4). Die echten Daten
  nutzen seit D-61 „Gut erholt"; die Demo wurde in diesem Ticket nicht
  umbenannt, weil sie nur der Optik dient.

### 2.3 Ohne Score

**Jetzt gleich:** zentrierter Ring, „Referenz wird aufgebaut" und
„2 von 21 Nächten" — unverändert, inklusive Nachtwerten und Bevel-Zeile. Dieser
Zustand bleibt bis zum 24.11. der Normalfall.

**Noch abweichend:** Nur die Kartenfarbe ist neu; die Anordnung ist identisch
mit dem Stand vor diesem Ticket. Die Referenz bildet diesen Zustand nicht ab.

### 2.4 Puls-Icon

**Jetzt gleich:** `IconPulse` in `web/src/components/icons.tsx` ist ein
Outline-Icon im 24er-Raster, Strichstärke 1.5 wie alle anderen Icons, ohne
Füllung. Es sitzt mittig im Score-Ring (24 × 24 CSS-px) und folgt dem Akzent.

**Noch abweichend:** Die Referenz zeichnet das Icon mit einem weichen Schein.
Wir bleiben beim ruhigen Akzentstrich; der dezente Schein liegt am Ring, nicht
am Icon.

### 2.5 Bilder und Bericht

Alle sechs Bilder liegen unter `docs/design/screens/recovery/`, die
Dreispalten-Vergleiche enthalten die Referenz als dritte Spalte. Dieser Bericht
ist `docs/design/recovery-vergleich.md`.

---

## 3. Desktop (1440 px)

Das Ticket nennt die neue Anordnung ausdrücklich nur für ≤ 1000 px. Desktop
behält deshalb das bestehende Raster: Ring (220 px) mit Score mittig, daneben
die Treiberzeile heute/Schnitt/üblich. Die Kartenfarbe und der Ring-Schein
gelten auch dort; die Referenzzeile bricht jetzt innerhalb des Rings auf zwei
Zeilen um, statt seitlich unter dem Ringband zu verschwinden.

---

## 4. Prüfung

- `uv run pytest`: **148 passed**, 1 bestehende Starlette-Warnung.
- `npm run build` (stabil): grün, 53 Module, CSS 34,76 kB, JS 266,70 kB.
- `VITE_APP_VARIANT=preview npm run build`: grün, Demo-Zweig enthalten.
- Stabiler Bau: kein `demo=recovery`, kein „Demo", kein „Vorschau" im Bundle.
- Sichtprüfung 320 / 360 / 375 / 390 / 430 / 768 / 1000 / 1001 / 1440 px:
  kein horizontaler Überlauf; Umschaltung mobil/desktop genau bei 1000/1001 px.
- Safe Area (CDP, oben 47 px / unten 34 px): Tab-Leiste bleibt frei, Labels
  26 px über der Unterkante (unverändert zu TB-4).
- `ruff`: 22 bestehende Befunde in `src/`/`tests/`, keine Datei dieses Tickets
  betroffen.

---

## 5. Offene Punkte

- Ein echter 21-Nächte-Score existiert erst ab 24.11.2026; beurteilbar ist der
  Score-Zustand weiterhin nur über die Demo.
- `8101` zeigt den neuen Stand erst nach Merge und Deploy; die Bilder stammen
  aus dem lokalen Vorschau-Build mit API von `8101`.
- Bei 320 px ist der Ring 122 px statt „ca. 150 px"; das ist der Preis für die
  zwei Spalten ohne Überlauf.
