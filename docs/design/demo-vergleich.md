# Demo-Vergleich — Score-Zustand und Tab-Leiste

**Ticket:** TB-4 · **Stand:** 05.11.2026 · **Basis:** `develop` (TB-3 Premium-Redesign)
**Zweck:** den Erholungs-Score-Zustand für die nächste Designentscheidung sichtbar
machen und die Tab-Leiste prüfen. **Keine Umgestaltung der Karte**, nur
Demo-Anzeige, Tab-Abstand und Beobachtung.

---

## 0. Kurzfassung

- Der Demo-Zustand erscheint **nur** im Vorschau-Bau
  (`VITE_APP_VARIANT=preview`) **und** nur unter `?demo=recovery`. Er zeigt
  Score **82**, Band **„Gut"**, HRV 62 ms / Ruhepuls 46 bpm / Schlaf 6:50 h
  und „Nacht vom 5. November". Neben der Plakette **„Vorschau"** steht ein
  deutlich abweichendes Abzeichen **„Demo"**.
- Der stabile Bau (`VITE_APP_VARIANT` nicht gesetzt) enthält weder das
  Demo-Abzeichen noch die Demo-Werte. `?demo=recovery` ändert dort nichts
  (im DOM geprüft: kein „Demo", Score bleibt „—").
- Die Tab-Leiste hat jetzt `padding-bottom: max(4px, calc(env(safe-area-inset-bottom) - 14px))`
  und `gap: 2px` in den Buttons. Bei 34 px Safe-Area-Inset sind das 20 px statt
  rechnerisch 42 px; die Labels enden 26 px über der Unterkante.
- Der Vergleich zeigt: Reihenfolge, Kopf, Countdowns, Training, „Letzte 7 Tage"
  und die Tab-Leiste entsprechen der Referenz. Die **Erholungskarte** ist
  anders angeordnet (Ring mittig statt Score links, Treiberzeile statt
  Nachtwerte-Zeile), der **Farbhauch** ist schwächer, das **Puls-Icon** fehlt,
  das Band **„Gut"** ist Text statt Pill, und die Referenz-Deltas stehen nicht
  als eigene Zeile. Das ist Beobachtung, keine Änderung.

---

## 1. Aufnahme

- **Baulage:** lokaler Vorschau-Build (`VITE_APP_VARIANT=preview`) dieses
  Branches, ausgeliefert über einen lokalen Proxy. Die API kam von der
  laufenden Vorschau `http://127.0.0.1:8101`, damit dieselben Echtdaten wie in
  der Vorschau gelten. Die Vorschau selbst läuft noch auf dem deployten
  `develop` ohne diesen Branch; deshalb der lokale Bau.
- **Browser:** Chromium (`CHROME_PATH=/usr/bin/chromium`) über
  `web/scripts/audit-shots.mjs`, Viewport-Screenshots (nicht Full-Page),
  `deviceScaleFactor=1`.
- **Viewports:** 390 × 844 und 1440 × 900. Zusätzlich eine Aufnahme mit
  emulierter Safe Area oben 47 px / unten 34 px (CDP).
- **Daten:** 8101 zeigt den echten Referenzaufbau (2 von 21 Nächten, kein
  Score). Der Demo-Zustand ersetzt nur im Browser die Anzeigedaten.

| Bild | Inhalt |
|---|---|
| [aktuell-390x844.png](screens/demo/aktuell-390x844.png) | Vorschau, ohne Score (Referenz 2/21) |
| [demo-390x844.png](screens/demo/demo-390x844.png) | Demo, Score 82, `?demo=recovery` |
| [vergleich-390x844.png](screens/demo/vergleich-390x844.png) | Aktuell · Demo · Referenz als drei Spalten |
| [aktuell-1440x900.png](screens/demo/aktuell-1440x900.png) | Desktop, ohne Score |
| [demo-1440x900.png](screens/demo/demo-1440x900.png) | Desktop, Demo mit Score 82 |
| [vergleich-1440x900.png](screens/demo/vergleich-1440x900.png) | Aktuell · Demo · Referenz als drei Spalten |
| [demo-390x844-safearea.png](screens/demo/demo-390x844-safearea.png) | Demo mit emulierter Safe Area (34 px unten) |

Die Referenz liegt unverändert unter
[cockpit-premium-reference.png](cockpit-premium-reference.png). Sie ist ein
Mockup, keine Datenquelle; im Vergleich dient sie nur der Optik.

---

## 2. Bild für Bild

### 2.1 `aktuell-390x844.png` (ohne Score)

**Gleich:** Kopf mit Serif-Datum und Sync-Zeit, Countdown-Zeile, die
Erholungskarte als dominante Fläche, Training, „Letzte 7 Tage", Tab-Leiste mit
zwei Einträgen und denselben Icons. Kartenradius, dunkle Tinten-Rampe und der
eine Teal-Akzent entsprechen der Referenz.

**Abweichend:** Die Karte zeigt den echten Zwischenzustand: „Neuer Sensor",
neutraler Ring, „Referenz wird aufgebaut", „2 von 21 Nächten", darunter die
Nachtwerte HRV 29 ms, Ruhepuls 58 bpm, Schlaf 6:50 h und das Bevel-Feld. Die
Referenz zeigt an dieser Stelle bereits 82 und „Gut" — sie ist ein Mockup und
kein gültiger Datenstand (DESIGN.md 0/1.4).

### 2.2 `demo-390x844.png` (Score 82)

**Gleich:** dieselbe Seitenstruktur und dieselbe Karte; der Score-Zustand
füllt die Karte jetzt vollständig. 82, „Gut", die Treiberzeile mit
heute/Schnitt/üblich und der Erklärungssatz sind sichtbar. Das Abzeichen
„Demo" steht direkt neben „Vorschau" im Kopf.

**Abweichend:** Die Referenz setzt **82 links** und den **Ring rechts**, mit
einem **Puls-Icon** im Ring. Die aktuelle Karte setzt den Ring **mittig**, die
Zahl **im Ring**, das Band als Text darunter und die Treiberzeile darunter.
Der Farbhauch der Karte ist schwächer (4,5 % Teal-Verlauf, oben auslaufend)
als die deutlich grünliche Fläche der Referenz. Das Band „Gut" ist in der
Referenz eine grüne **Pill**, hier nur farbiger Text. Die Referenz zeigt
**+8 %** unter HRV und **−3 bpm** unter Ruhepuls; die aktuelle Karte zeigt
stattdessen die drei Spalten (62 ms / 58 / 57 und 46 bpm / 47 / 49). Die
Demo-Werte sind so gewählt, dass diese Deltas in den Zahlen stecken
(62 gegen 57,4 = +8 %, 46 gegen 49 = −3 bpm), aber die Karte beschriftet sie
nicht.

**Fundstelle, unverändert:** Die lange Referenzzeile
„21 von 21 Nächten · Schnitt 76" läuft bei 390 px über den Ring hinaus und
wird am linken Rand angeschnitten. Das war schon in
[Phase 5](phase5-pruefung.md) als offener Punkt notiert; dieses
Ticket ändert die Karte nicht.

### 2.3 `vergleich-390x844.png`

**Gleich:** Die drei Spalten haben denselben Aufbau (Kopf → Countdowns →
Erholung → Training → Letzte 7 Tage → Tabs). Die Reihenfolge und die
Hierarchie sind erkennbar dieselben; die Referenz ist nur eine andere
Ausbaustufe derselben Seite.

**Abweichend:** Die Erholungskarte ist der größte Unterschied (Anordnung,
Puls-Icon, Band-Pill, Deltas, Referenzzeile). Dazu kommen der stärkere
Farbhauch der Referenzkarte und die dort sichtbare iOS-Statusleiste mit
Uhrzeit, Dynamic Island und Home-Indicator. Die Demo-Spalte trägt das
zusätzliche amberfarbene „Demo"-Abzeichen, das die Referenz nicht kennt — es
ist die Absicherung gegen die Verwechslung der 82 mit einem echten Wert.

### 2.4 `aktuell-1440x900.png` (ohne Score)

**Gleich:** Die Seite nutzt die breite Fläche mit Seitenleiste, Countdowns,
Erholungskarte, Training und „Letzte 7 Tage". Die Karte ist hier zweispaltig
(Ring links, Treiber/Nachtwerte rechts), die Kartenfarben und die ruhige
Desktop-Navigation entsprechen dem Designsystem.

**Abweichend:** Die Referenz ist ausschließlich mobil (852 × 1846). Ein
echtes Desktop-Pendant existiert nicht; der Vergleich ist deshalb nur
inhaltlich, nicht im Layout. Auf dem Desktop zeigt die aktuelle Karte den
Nachtwerte-Block rechts neben dem Ring, die Referenz untereinander.

### 2.5 `demo-1440x900.png` (Score 82)

**Gleich:** Score 82, Band „Gut", Treiberzeile und Erklärung sind vollständig;
das Demo-Abzeichen steht in der Seitenleiste neben „Vorschau". Die
Seitenleiste und die zweispaltige Erholungskarte funktionieren unverändert.

**Abweichend:** In der Referenz steht die Zahl links und der Ring rechts; auf
dem Desktop ist es umgekehrt (Ring links, Tabelle rechts). Die
Referenzzeile „21 von 21 Nächten · Schnitt 76" liegt im Ring und berührt
dessen linke Kante; bei 390 px wird sie angeschnitten. Das Puls-Icon und die
Delta-Zeilen der Referenz fehlen auch hier.

### 2.6 `vergleich-1440x900.png`

**Gleich:** Die Inhaltsfolge und die Informationshierarchie sind in allen drei
Spalten dieselben; die aktuelle Seite ist die Desktop-Erweiterung derselben
mobilen Struktur.

**Abweichend:** Die dritte Spalte ist die mobile Referenz, nur auf 900 px
Höhe skaliert. Sie zeigt keine Seitenleiste und keine zweispaltige
Erholungskarte; ein direkter Desktop-Vergleich ist damit nicht möglich. Für
die eigentliche Entscheidung ist die 390er-Spalte maßgeblich.

### 2.7 `demo-390x844-safearea.png`

Die Aufnahme mit emulierter Safe Area (oben 47 px, unten 34 px) zeigt die
Tab-Leiste mit 20 px unterem Innenabstand. Die Labels „Heute" und
„Verpflegung" enden bei y = 818 px (Viewport 844 px), also 26 px über der
Unterkante; der Home-Indicator-Bereich bleibt frei. Chromium zeichnet den
weißen Indicator selbst nicht, die Lage ist an den gemessenen Werten geprüft.

---

## 3. Tab-Leiste

**Geändert:** `web/src/styles.css`:

- `padding: var(--space-2) var(--space-2) max(4px, calc(env(safe-area-inset-bottom) - 14px))`
- Button-`gap: 2px` (vorher `var(--space-1)` = 4 px)

Die Leiste bleibt full-bleed (`left: 0; right: 0; bottom: 0`), Hintergrund und
Blur bleiben. Gemessen bei 390 × 844:

| Zustand | `padding-bottom` | Label-Unterkante | Abstand zur Unterkante |
|---|---|---|---|
| ohne Safe Area | 4 px | 818 px | 26 px |
| 34 px Safe Area (emuliert) | 20 px | 818 px | 26 px |

Mit 34 px Inset entspricht das der Vorgabe (rechnerisch vorher 42 px, jetzt
20 px). Der sichtbare Home-Indicator sitzt im untersten Bereich; die Labels
liegen darüber.

---

## 4. Demo-Zustand — Abgrenzung

- Neue Datei `web/src/demo.ts`: `isDemoRecovery` ist nur wahr, wenn
  `isPreview` **und** `?demo=recovery`. `withDemoRecovery()` gibt sonst das
  unveränderte `Overview` zurück.
- `web/src/App.tsx` ruft `withDemoRecovery()` nach dem API-Laden auf;
  `web/src/components/Brand.tsx` liefert das `DemoTag`,
  `Sidebar.tsx` und der mobile Kopf zeigen es neben `PreviewTag`.
- Demo-Werte: Score 82, `band: "green"`, Label „Gut", HRV 62 ms (Schnitt 58,
  üblich 57,4), Ruhepuls 46 bpm (Schnitt 47, üblich 49), Schlaf 6:50 h
  (Schnitt 6:36, üblich 7:00), Referenz 21/21 mit Schnitt 76, Erklärungssatz,
  `vendor_prompt: false`. „Nacht vom 5. November" kommt aus dem vorhandenen
  `as_of`-Feld.
- **Keine** Änderung an `api.ts`, `types.ts`, Backend, Berechnung, Recovery,
  Datenbank oder Sync. Die Demo ersetzt nur Anzeigedaten im Frontend.
- **Stabiler Bau:** `npm run build` ohne `VITE_APP_VARIANT` → 53 Module,
  CSS 32,65 kB, JS 265,04 kB; im JS-Bundle kommen weder „Demo" noch die
  Demo-Werte vor. `?demo=recovery` im stabilen Bau geprüft: kein
  `.brand-tag.demo`, Score „—", kein „82" im Text. Vorschau-Bau: 53 Module,
  CSS 32,65 kB, JS 266,34 kB, Demo-Zweig enthalten.

---

## 5. Prüfung

| Punkt | Ergebnis |
|---|---|
| `uv run pytest` | 135 passed, 1 Warnung |
| `npm run build` (stabil) | grün, 53 Module, CSS 32,65 kB, JS 265,04 kB |
| `VITE_APP_VARIANT=preview npm run build` | grün, 53 Module, CSS 32,65 kB, JS 266,34 kB |
| Demo nur in Vorschau + `?demo=recovery` | ja; stabiler Bau im DOM ohne Demo, Score „—" |
| Abzeichen „Demo" sichtbar | ja, mobil im Kopf und Desktop in der Seitenleiste, neben „Vorschau" |
| Keine API-/Berechnungs-/Typänderung | ja; nur `web/src/demo.ts` und Anzeige-Verdrahtung |
| Bilder vollständig | 390/1440 je aktuell + Demo, dazu zwei Vergleichsbilder und eine Safe-Area-Aufnahme |

---

## 6. Beobachtungen für die nächste Entscheidung

Nur festgehalten, nicht umgesetzt:

1. **Anordnung:** Referenz zeigt den Score links und den Ring rechts mit
   Puls-Icon; die aktuelle Karte dreht das (Ring mittig/mobil, Ring links auf
   Desktop) und stellt die Treiberzeile darunter.
2. **Band:** „Gut" ist in der Referenz eine Pill, aktuell farbiger Text im
   Ring.
3. **Deltas:** Die Referenz beschriftet +8 % und −3 bpm; die aktuelle Karte
   zeigt die drei Spalten ohne Delta-Label.
4. **Farbhauch:** Die Referenzkarte ist deutlich grünlicher; aktuell nur ein
   schwacher 4,5-%-Teal-Verlauf.
5. **Puls-Icon:** fehlt aktuell vollständig.
6. **Referenzzeile:** „21 von 21 Nächten · Schnitt 76" überläuft den Ring bei
   390 px; das ist ein bestehender Zustand, kein Demo-Fehler.
7. **Tab-Leiste:** Der neue Abstand wirkt ruhiger; die Labels sitzen näher an
   der Unterkante, der Indicator-Bereich bleibt frei. Keine weitere Änderung
   in diesem Ticket.

**Stopp:** Die Umgestaltung der Erholungskarte ist ein eigenes Ticket.
