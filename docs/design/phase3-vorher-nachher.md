# Phase 3 — Cockpit-Startseite: vorher/nachher

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Basis:** `develop` (`3539a89`)
**Auftrag:** [`AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 3 · **Design:** [`DESIGN.md`](../../DESIGN.md)
**Status:** umgesetzt, geprüft, **Stopp** — Phase 4 erst nach Freigabe

Phase 0–2 bleiben unverändert: [`PHASE0.md`](PHASE0.md), [`PHASE1.md`](PHASE1.md), [`PHASE2.md`](PHASE2.md).

---

## 0. Kurzfassung

Alle vier Abschnitte der Startseite sind in einem Zug überarbeitet: Header/Countdown, Erholung, Training, Letzte 7 Tage. Die Countdown-Zahlen sind jetzt System-UI (die letzte Serif-Abweichung außer dem Datum ist damit geschlossen). Die Erholungskarte zeigt ohne Score ein neutrales Ringgerüst mit dem echten Referenzfortschritt (2 von 21 Nächten) und die Nachtwerte in drei Spalten. Training und Wochenkarte folgen der Referenz mit ruhigen Flächen, klaren Zahlen und ohne neue Daten.

**Keine Datenlogik geändert. Keine Mockwerte. „Referenz wird aufgebaut" bleibt.**

---

## 1. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `web/src/components/RecoveryDial.tsx` | Ring vereinfacht: neutrale Spur, Fortschritt (Score oder Referenzaufbau), kein Zonen-Regenbogen und keine 60 Ticks; `baselineProgress` als neuer Darstellungswert |
| `web/src/components/WorkoutPreview.tsx` | Chevron als Klick-Hinweis; Zeile bleibt dieselbe Komponente |
| `web/src/pages/Today.tsx` | Countdown-/Kopfbereich unverändert im Aufbau; Erholungskarte mit horizontalem Nacht-Grid und `baselineProgress`; sonst gleiche Daten und Klickpfade |
| `web/src/styles.css` | Countdown-Zahlen System-UI; Erholungskarte mit dezentem Verlauf und Schatten; Nacht-Grid; Trainingszeile als erhöhte Fläche; Wochenbalken höher, mit Verlauf und größeren Labels; Serif nur noch am Datum; `--accent-wash`; veraltete Band-Aliase entfernt; der Kommentar der abgeleiteten Tokens ist zählfrei |
| `docs/design/screens/phase3/*.png` | 16 Bilder: vier Abschnitte × 390/1440 × vorher/nachher |
| `docs/design/phase3-vorher-nachher.md` | dieser Bericht |

Nicht geändert: `src/` (API, `metrics.py`, `fuel.py`, `sync.py`, DB), `web/src/api.ts`, `web/src/types.ts`, Navigation, Routing, Framework, Abhängigkeiten.

---

## 2. Vorher/Nachher

**Aufnahme:** Vorher aus der laufenden Vorschau `http://127.0.0.1:8101` (Phase 2). Nachher aus dem lokalen Vorschau-Build (`VITE_APP_VARIANT=preview`) über einen lokalen Proxy auf dieselbe Vorschau-API, weil die laufende Instanz den neuen Code erst nach dem Deploy zeigt. Die fachlichen Werte sind dieselben; die Uhrzeit im Kopf ist der Erzeugungszeitpunkt der Antwort und kann sich zwischen den Aufnahmen um Minuten unterscheiden. Die Bilder sind Abschnittsausschnitte bei Viewport 390×844 bzw. 1440×900; die fixierte Tab-Leiste wurde für die Ausschnitte ausgeblendet.

### 2.1 Header und Countdowns

| | 390 px | 1440 px |
|---|---|---|
| Vorher | [vorher-header-countdown-390.png](screens/phase3/vorher-header-countdown-390.png) | [vorher-header-countdown-1440.png](screens/phase3/vorher-header-countdown-1440.png) |
| Nachher | [nachher-header-countdown-390.png](screens/phase3/nachher-header-countdown-390.png) | [nachher-header-countdown-1440.png](screens/phase3/nachher-header-countdown-1440.png) |

**Was sich geändert hat:** Die Countdown-Zahlen stehen in System-UI (26/600) statt in Serif; das Datum bleibt der einzige serife Moment. Die drei Spalten und ihre Trennlinien bleiben, die Namen brechen weiterhin sauber um.

### 2.2 Erholung

| | 390 px | 1440 px |
|---|---|---|
| Vorher | [vorher-erholung-390.png](screens/phase3/vorher-erholung-390.png) | [vorher-erholung-1440.png](screens/phase3/vorher-erholung-1440.png) |
| Nachher | [nachher-erholung-390.png](screens/phase3/nachher-erholung-390.png) | [nachher-erholung-1440.png](screens/phase3/nachher-erholung-1440.png) |

**Was sich geändert hat:** Der Ring ist ruhig geworden: keine farbigen Zonenbögen und keine 60 Ticks mehr, sondern eine neutrale Spur plus Fortschritt. Ohne Score zeigt der Fortschritt den echten Referenzaufbau (`2 von 21 Nächten`, neutrale Farbe), in der Mitte stehen „—", „Referenz wird aufgebaut" und die Nächte. Die Nachtwerte (HRV, Ruhepuls, Schlaf) stehen in drei Spalten mit getrennten Einheiten; die Karte bekommt einen sehr dezenten Verlauf und Schatten. Mit Score nutzt der Ring den Akzent, die Referenzmarke bleibt, die Bandfarbe sitzt am Label.

### 2.3 Training

| | 390 px | 1440 px |
|---|---|---|
| Vorher | [vorher-training-390.png](screens/phase3/vorher-training-390.png) | [vorher-training-1440.png](screens/phase3/vorher-training-1440.png) |
| Nachher | [nachher-training-390.png](screens/phase3/nachher-training-390.png) | [nachher-training-1440.png](screens/phase3/nachher-training-1440.png) |

**Was sich geändert hat:** Die Vorschau ist jetzt eine erhöhte Zeile mit Akzent-Iconfläche, Namen, Meta, Status-Pille und Chevron; der Leerzustand „Für heute steht nichts im Plan." und der Morgen-Hinweis bleiben unverändert. Bei 390 px bricht der lange Einheitenname zweizeilig — ohne Überlauf.

### 2.4 Letzte 7 Tage

| | 390 px | 1440 px |
|---|---|---|
| Vorher | [vorher-letzte-7-tage-390.png](screens/phase3/vorher-letzte-7-tage-390.png) | [vorher-letzte-7-tage-1440.png](screens/phase3/vorher-letzte-7-tage-1440.png) |
| Nachher | [nachher-letzte-7-tage-390.png](screens/phase3/nachher-letzte-7-tage-390.png) | [nachher-letzte-7-tage-1440.png](screens/phase3/nachher-letzte-7-tage-1440.png) |

**Was sich geändert hat:** Die Balken sind höher (84 px), haben einen sanften Verlauf und größere, besser lesbare Tageslabels; der heutige Tag bleibt der Akzentbalken, der höchste Tag bleibt neutral hervorgehoben. Die Summenzeilen (Umfang, Belastung, Einheiten, Belastungsverhältnis) und ihre Werte sind unverändert.

---

## 3. Datenlogik und Zustände

**Unverändert.** Keine Änderung an API, Berechnungen, Recovery, Datenbank oder Sync. Der kritische Zustand bleibt:

- `recovery.score = null`, Label „Referenz wird aufgebaut",
- `reference.nights = 2`, `minimum = 21`,
- Ring ohne Score, neutrale Fortschrittsanzeige, keine erfundene Zahl,
- Nachtwerte nur, wenn vorhanden; fehlende Werte bleiben „—".

Der Score-Zweig ist im Code erhalten (Akzentring, Referenzmarke, Treibertabelle, Erklärsatz, Bevel-Zeile). Er ist in dieser Runde **nicht visuell geprüft**, weil die Vorschau keinen Score liefert; die Vorschau zeigt ausschließlich den Referenzaufbau.

Geprüft (Chromium, lokaler Vorschau-Build gegen die echte API):

- 320/390/430 px: kein horizontaler Überlauf, Nacht-Grid bleibt innerhalb der Karte.
- Trainingszeile → `SessionSheet`, Escape schließt; Wochenblatt/Einheitenblatt weiterhin erreichbar.
- Countdown `sans`, Datum `serif`; Wochenbalken 84 px; Chevron/Badge vorhanden.
- Keine Konsolen- oder Seitenfehler.

---

## 4. Build und Tests

| Prüfung | Ergebnis |
|---|---|
| `cd web && npm run build` (stabil) | grün, 52 Module, 1,57 s; CSS 30,77 kB, JS 265,01 kB |
| `VITE_APP_VARIANT=preview npm run build` (für die Bilder) | grün, 52 Module, 1,51 s; CSS 30,77 kB, JS 265,23 kB |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **135 passed**, 1 Warnung, 6,13 s |
| Sichtprüfung | vier Abschnitte bei 390/1440, zusätzlich 320/430 auf Überlauf |

---

## 5. Offene Punkte und Risiken

1. **Score-Zustand nicht visuell geprüft.** Die Vorschau hat nur den Referenzaufbau. Der Code-Zweig ist unverändert vorhanden, aber die Ring-/Treiber-Darstellung mit echtem Score braucht die Prüfung, sobald Daten vorliegen.
2. **Ring ohne Zonenbögen.** Die alte „Instrument"-Idee mit vier farbigen Zonen ist bewusst entfallen; der Ring ist jetzt neutral plus Fortschritt. Das entspricht der Referenz und `DESIGN.md` 4.4 (kein grüner „fertiger" Ring ohne Score). Falls die Zonen als Produktidentität zurückkommen sollen, ist das eine eigene Designentscheidung.
3. **Anordnung der Erholungskarte.** Die Karte bleibt beim bewährten Ring links, Werte rechts (mobil untereinander); die Referenz zeigt den Score links und den Ring rechts. Ohne Score gibt es keinen Score-Block, die Nachtwerte sind der zweite Schwerpunkt. Eine gespiegelte Anordnung wäre eine eigene Layoutentscheidung.
4. **Trainingszeile bei 390 px.** Der lange Name bricht zweizeilig; das ist bei 320 px ebenso, aber ohne Überlauf. Kürzere Namen bleiben einzeilig.
5. **`--band-low: #e8925f`** aus Phase 1 ist weiterhin nicht separat abgenommen; der Ring nutzt sie nicht mehr, sie bleibt für spätere Statusflächen.
6. **Serif-Abweichung geschlossen.** `.cd-n` ist jetzt System-UI; `var(--serif)` steht nur noch am Datum. Der Punkt 8.9 aus `PHASE1.md` ist damit erledigt.
7. **Uhrzeit im Kopf.** Die Screenshots unterscheiden sich in der Sync-Zeit, weil die API den Erzeugungszeitpunkt liefert; die fachlichen Werte sind identisch. Das ist kein Datenunterschied, aber beim Bildvergleich sichtbar.
8. **Geteilte Trainingszeile.** Die neue erhöhte Zeile wirkt auch im Wochenblatt, weil `WorkoutPreview` und `.train-row` geteilt sind. Dort geprüft: 12 Zeilen, Last und Chevron, kein Überlauf; keine Funktionsänderung.
9. **Screenshot-Ausschnitte.** Die Bilder sind Abschnittsausschnitte, keine Vollbilder der ganzen Seite; die Viewports waren 390×844 und 1440×900. Die fixierte Tab-Leiste wurde für die Ausschnitte ausgeblendet.

---

## 6. Nächster kleiner Schritt

**Phase 4 — Navigation und Feinschliff:** Bottom-Tabbar/Seitenleiste, Touchflächen, Safe Areas, Fokus, 320/390/430 px. Erst nach menschlicher Freigabe; keine automatische Folgephase.
