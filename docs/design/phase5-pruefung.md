# Phase 5 — Qualitätsprüfung und Dokumentation

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Basis:** `develop` (`24f831d`)
**Auftrag:** [`AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 5 · **Design:** [`DESIGN.md`](../../DESIGN.md)
**Status:** geprüft, dokumentiert, **Stopp** — die Migration ist damit abgeschlossen.

Phase 0–4 bleiben unverändert: [`PHASE0.md`](PHASE0.md), [`PHASE1.md`](PHASE1.md), [`PHASE2.md`](PHASE2.md), [`phase3-vorher-nachher.md`](phase3-vorher-nachher.md), [`phase4-feinschliff.md`](phase4-feinschliff.md).

---

## 0. Kurzfassung

Die UI-Migration ist im geprüften Umfang **bestanden**: Navigation, Touchflächen, Textkontrast, `prefers-reduced-motion`, Safe Areas (emuliert), Build und Tests sind in Ordnung. Der Referenzaufbau, „kein Workout" und der API-Fehlerzustand sind vorhanden.

**Vier Punkte bleiben offen:** ein echter „veralteter Sync" ist mit der aktuellen Datenquelle nicht darstellbar, der Fehlertext im Banner/Splash ist technisch („Failed to fetch") und der Banner hat keine Wiederholen-Aktion, der leere/teilbefüllte Bestand zeigt einen erklärenden Widerspruch, und der neutrale Diagrammbalken liegt unter 3:1. Diese Punkte sind Datenquellen-, Text- oder Designsystem-Themen; es wurden **keine** API-, Berechnungs-, Recovery-, DB- oder Sync-Änderungen vorgenommen.

---

## 1. Prüfumfang und Methode

- **Build/Ansicht:** lokaler Vorschau-Build (`VITE_APP_VARIANT=preview`) über einen Proxy auf die echte Vorschau-API (`8101`), damit dieselben Daten wie in der laufenden Vorschau gelten.
- **Leerer/teilbefüllter Bestand:** lokale DB über `uv run tc serve --port 8123`; echte API, keine erfundenen Werte.
- **Laden/Fehler:** echte Requests über Puppeteer verzögert bzw. abgebrochen; keine Mockdaten im Produkt.
- **Safe Areas:** Chromium-CDP `Emulation.setSafeAreaInsetsOverride` mit iPhone-14-Werten (47 px oben, 34 px unten); echtes Gerät nicht verfügbar.
- **Screenshots:** 320×700, 390×844, 430×932; Desktop 1440×900; Zustandsbilder bei 390 bzw. 1440. Chromium, `CHROME_PATH=/usr/bin/chromium`.

---

## 2. Checkliste

| Punkt | Ergebnis | Fundstelle / Datei |
|---|---|---|
| **Laden** | **bestanden mit Hinweis:** Splash mit Marke, Titel, „Daten werden geladen…"; kein Karten-Skelett, aber auch kein Layoutsprung, weil die Seite erst nach der Antwort gerendert wird. | `web/src/App.tsx` (`Splash`), `screens/phase5/state-laden-390.png` |
| **Kein Workout** | **bestanden:** „Nichts geplant", „Für heute steht nichts im Plan."; morgen wird gezeigt, wenn bekannt. | `web/src/pages/Today.tsx` (`TrainingCard`), `screens/phase5/bottom-390.png` |
| **Fehlende API-Werte** | **bestanden (Anzeige):** fehlende Nachtwerte werden als „—" gerendert; der leere Bestand zeigt „Keine Daten". | `web/src/pages/Today.tsx` (Nacht-Grid), `screens/phase5/state-leer-390.png` |
| **Sensorreferenz im Aufbau** | **bestanden:** `score = null`, „Referenz wird aufgebaut", „2 von 21 Nächten", neutraler Ring ohne Score. | `web/src/components/RecoveryDial.tsx`, `web/src/pages/Today.tsx`, `screens/phase5/start-390.png` |
| **Veralteter Sync** | **nicht bestanden / offen:** Die UI zeigt nur `HH:MM`; `generated_at` ist der Erzeugungszeitpunkt der Antwort (`metrics.py`), nicht der letzte erfolgreiche Sync. Ein Alter oder eine Warnung ist nicht darstellbar. | `src/trainings_cockpit/metrics.py`, `web/src/pages/Today.tsx`, `web/src/components/Sidebar.tsx` |
| **API-Fehler** | **teilweise:** Splash-Fehler mit gestaltetem „Erneut versuchen" (44 px); Banner nach Sync-Fehler. Der Text ist technisch („Failed to fetch"), der Banner hat keine Wiederholen-Aktion. | `web/src/App.tsx`, `web/src/styles.css` (`.banner`, `.sync-btn`), `screens/phase5/state-fehler-390.png`, `screens/phase5/state-sync-fehler-1440.png` |
| **Leer** | **teilweise:** keine Einheiten, „Keine Daten", Nullwerte; kein globaler Empty-State mit Handlung. Im lokalen Bestand stehen Nachtwerte, während die Erklärung HRV/Ruhepuls als fehlend nennt (bekannter Widerspruch aus der Baseline-Logik). | `web/src/pages/Today.tsx`, `screens/phase5/state-leer-390.png` |
| **Touchflächen ≥ 40 px** | **bestanden:** Tabbar 49, Chips 44, Eingabefelder/Labels 44–62, Slider 44, g/ml-Umschaltung 44, Sidebar-Navigation/Sync 44, Trainingszeile 56, Wochenzeile 44, Retry 44. Kein sichtbares interaktives Element < 40 px bei 390 px (Heute und Verpflegung). | `web/src/styles.css`, Messung 390 px; `screens/phase5/verpflegung-390.png`, `screens/phase5/verpflegung-ahornsirup-390.png` |
| **Kontrast** | **bestanden (Text):** 17,04 / 8,97 / 5,62 / 5,07 / 11,60 / 11,23 / 6,68 / 10,70 / 10,60:1 (Tabelle in 4). **Offen:** neutraler Diagrammbalken 2,42:1 (Grafik, nicht Text). | `web/src/styles.css`, Messung; `screens/phase5/start-390.png` |
| **prefers-reduced-motion** | **bestanden:** globale Regel; gemessene Dauer 0,01 ms für Seiten-Eintritt, Ring-Transition, Skeleton, Sheet-Loading und Popup. | `web/src/styles.css` (globaler Block am Ende) |
| **Navigation / Bottom-Tabs** | **bestanden:** 320/390/430, aktiver Tab nur Akzent-Icon + helles Label, `aria-current="page"`, Fokusring, gleiche Icons; Desktop-Seitenleiste ruhig. | `web/src/App.tsx`, `web/src/components/Sidebar.tsx`, `web/src/styles.css`, `screens/phase5/start-320/390/430.png`, `nav-320/390/430.png` |
| **Safe Areas iPhone** | **bestanden (emuliert):** oben 47 px, unten 34 px; Main oben 67 px, unten 122 px, Tabbar unten 42 px; Blatt oben 57 px, unten 62 px. Echtes Gerät nicht verfügbar. | CDP-Messung, `web/src/styles.css` (`env(...)`), `screens/phase5/safearea-390.png` |
| **Browser-Back / direkte URLs** | **offen:** kein Router; der Tab liegt im Speicher, ein Neuladen führt auf „Heute". Bewusste Architektur (Phase 0), nicht geändert. | `web/src/App.tsx` (`useState<Tab>`) |
| **Offline** | **offen / nicht vorhanden:** kein Offline-Zustand mit letztem bestätigten Stand; `DESIGN.md` 5 nennt ihn. | `web/src/App.tsx`, `web/src/api.ts` |
| **Build** | **bestanden:** stabil 52 Module, CSS 32,47 kB, JS 265,01 kB, 1,50 s; Vorschau 32,47 kB / 265,23 kB, 1,53 s. | `npm run build` |
| **Tests** | **bestanden:** 135 passed, 1 Warnung, 5,99 s. | `uv run pytest` |

---

## 3. Screenshots

Alle unter `docs/design/screens/phase5/`. Die Start-/Navigationsbilder stammen aus dem Vorschau-Build (Plakette „Vorschau"), die Zustandsbilder aus demselben Build.

### 3.1 Startseite und Navigation (final)

| Ansicht | 320 px | 390 px | 430 px |
|---|---|---|---|
| Startseite | [start-320.png](screens/phase5/start-320.png) | [start-390.png](screens/phase5/start-390.png) | [start-430.png](screens/phase5/start-430.png) |
| Navigation | [nav-320.png](screens/phase5/nav-320.png) | [nav-390.png](screens/phase5/nav-390.png) | [nav-430.png](screens/phase5/nav-430.png) |

Zusätzlich: [Scrollende 390](screens/phase5/bottom-390.png), [Safe Area 390](screens/phase5/safearea-390.png), [Verpflegung 390](screens/phase5/verpflegung-390.png), [Verpflegung mit Ahornsirup 390](screens/phase5/verpflegung-ahornsirup-390.png).

### 3.2 Zustände

| Zustand | Bild |
|---|---|
| Laden (echter Request verzögert) | [state-laden-390.png](screens/phase5/state-laden-390.png) |
| API-Fehler beim ersten Laden | [state-fehler-390.png](screens/phase5/state-fehler-390.png) |
| Sync-Fehler (Banner, Desktop) | [state-sync-fehler-1440.png](screens/phase5/state-sync-fehler-1440.png) |
| Leer/teilbefüllt (lokale DB) | [state-leer-390.png](screens/phase5/state-leer-390.png) |
| Sensorreferenz (normaler Bestand) | [start-390.png](screens/phase5/start-390.png) |
| Kein Workout / Scrollende | [bottom-390.png](screens/phase5/bottom-390.png) |

---

## 4. Kontrast (gemessen)

| Paar | Verhältnis |
|---|---|
| Text primär auf Karte | 17,04:1 |
| Text sekundär auf Karte | 8,97:1 |
| Text gedämpft auf Karte | 5,62:1 |
| Text gedämpft auf Seitenhintergrund | 6,18:1 |
| Text primär auf erhöhter Fläche | 15,38:1 |
| Text gedämpft auf erhöhter Fläche | 5,07:1 |
| Text sekundär auf erhöhter Fläche | 8,10:1 |
| Akzent auf Seitenhintergrund | 11,60:1 |
| Text auf Akzent | 11,23:1 |
| Negativ / Warnung / Positiv auf Karte | 6,68 / 10,70 / 10,60:1 |
| **Diagramm neutral auf Karte** | **2,42:1** |

Text erfüllt durchgehend WCAG AA. Der neutrale Balken liegt als Informationsgrafik unter 3:1; die Balken tragen zusätzlich Tageslabels und die Summenzeilen die Werte. Als offener Punkt vermerkt (siehe 6).

---

## 5. Touchflächen (gemessen)

| Element | Höhe |
|---|---|
| Bottom-Tabbar-Button | 49 px |
| Chip (Filter, Dauer, Quelle) | 44 px |
| Eingabefeld/Label in Verpflegung | 44–46 px |
| Slider (Trefferfläche) | 44 px (sichtbare Spur 2 px) |
| g/ml-Umschaltung | 44 px |
| Shot-Feld mit Umschaltung | 62 px |
| Sidebar-Navigation / Sync | 44 px |
| Trainingszeile | 56 px |
| Wochenzeile (Button) | 44 px |
| Retry im Fehler-Splash | 44 px |

Gemessen bei 390 px (Heute und Verpflegung) und 1440 px (Sidebar). Auf Desktop bleiben die Chips 30 px, weil dort Mauszeiger statt Touch gilt; das ist die bewusste Ausnahme.

---

## 6. Änderungen in Phase 5

| Datei | Änderung |
|---|---|
| `web/src/styles.css` | Touchflächen: Sidebar-Navigation/Sync 44 px, Eingabefelder/Shot-Feld/g/ml/Slider/Retry 44 px; Tabbar-Label auf `--text-micro` (12 px); sichtbarer Fokus für Sync und Felder (`:focus-within`/`:focus-visible`); globaler `prefers-reduced-motion`-Block; `.sync-btn` gestaltet |
| `DESIGN.md` | In 3.2 die Desktop-Variante der Navigation ergänzt (dieselbe Liste, dieselben Icons, ruhige Seitenleiste); keine Regel geändert |
| `docs/design/screens/phase5/*.png` | 14 finale und Zustandsbilder |
| `docs/design/phase5-pruefung.md` | dieser Bericht |

**Keine** API-, Berechnungs-, Recovery-, Datenbank- oder Sync-Änderung; kein Markup, keine neue Abhängigkeit.

---

## 7. Offene Risiken

1. **Veralteter Sync** ist mit `generated_at` (Erzeugungszeitpunkt, `metrics.py`) nicht erkennbar. Die UI zeigt „Zuletzt synchronisiert HH:MM" und suggeriert Aktualität. Eine echte Alter-/Stale-Anzeige braucht einen letzten erfolgreichen Sync-Zeitpunkt aus der Datenschicht.
2. **Fehlertext** ist bei Netzwerkfehlern technisch („Failed to fetch"); der Banner nach Sync-Fehler hat keine Wiederholen-Aktion. Der Splash-Fehler hat einen Retry.
3. **Leer/teilbefüllt:** Im lokalen Bestand nennt die Erklärung HRV/Ruhepuls als fehlend, obwohl beide als Nachtwerte sichtbar sind (Baseline-/Wording-Logik). Kein globaler Empty-State mit Handlung.
4. **Diagramm-Kontrast:** `--chart-neutral` erreicht 2,42:1 auf der Karte; als Grafik unter 3:1. Textlabels und Summen tragen die Information.
5. **Browser-Back/direkte URLs** sind ohne Router nicht abgebildet; ein Neuladen führt auf „Heute". Bekannte Architekturentscheidung, nicht Teil der UI-Migration.
6. **Offline** ist nicht behandelt; `DESIGN.md` 5 nennt den Zustand.
7. **Score-Zustand** ist mit echten Daten nicht prüfbar (die Vorschau hat keine 21 Nächte). Die bekannte Referenzzeilen-Überlänge im Ring bleibt offen.
8. **`--band-low: #e8925f`** aus Phase 1 ist weiterhin nicht separat abgenommen.
9. **Echtes iPhone/Safari** wurde nicht geprüft; Safe Areas sind per CDP emuliert, der Home-Indicator/Notch nicht real.

---

## 8. Was nicht geprüft werden konnte

- echtes iPhone/Notch/Dynamic Island (nur CDP-Safe-Area-Emulation),
- ein echter Score nach 21 Nächten,
- echter Garmin-/intervals-Sync (keine Schlüssel),
- Docker-/Homeserver-Deploy (macht das Board),
- Offline-Verhalten,
- Browser-Back/direkte URLs (kein Router vorhanden).

---

## 9. Fazit

Die sichtbare Migration ist im geprüften UI-Umfang abgeschlossen: einheitliche Tokens, gemeinsame Bausteine, Startseite nach Referenz, ruhige Navigation, 44-px-Touchflächen, Safe Areas und reduzierte Bewegung. Die verbleibenden Punkte liegen außerhalb einer reinen UI-Änderung (Sync-Zeitstempel, Fehlertexte, Empty-Wording, Diagramm-Token) und sind als offene Risiken dokumentiert.

**Danach STOPP — keine Folgephase.**
