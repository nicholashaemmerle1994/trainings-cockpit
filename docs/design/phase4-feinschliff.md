# Phase 4 — Navigation und Feinschliff

**Ticket:** TB-3 · **Stand:** 05.11.2026 · **Basis:** `develop` (`03adfe7`)
**Auftrag:** [`AGENT_MIGRATION.md`](AGENT_MIGRATION.md), Phase 4 · **Design:** [`DESIGN.md`](../../DESIGN.md)
**Status:** umgesetzt, geprüft, **Stopp** — Phase 5 erst nach Freigabe

Phase 0–3 bleiben unverändert: [`PHASE0.md`](PHASE0.md), [`PHASE1.md`](PHASE1.md), [`PHASE2.md`](PHASE2.md), [`phase3-vorher-nachher.md`](phase3-vorher-nachher.md).

---

## 0. Kurzfassung

Die Navigation ist ruhig geworden: Der aktive Tab unterscheidet sich nur über türkises Icon und helles Label, die Seitenleiste hat keine gefüllte aktive Fläche mehr. Chips sind auf Touch-Geräten 44 px hoch, die Tabbar-Labels 11 px (aktiv 500), die Karten haben einheitlich 24 px (mobil 20) Innenabstand, der Desktop-Container bleibt bei 1200 px. Auf 320 px bekommt die Trainingszeile eine zweite Zeile für den Status, statt den Namen vierzeilig zu brechen. Fokusringe, Safe-Area-Abstände und das Scrollende sind geprüft.

---

## 1. Befund vorher

Aus den Vorher-Bildern (`vorher-*`) und dem Code:

1. **Aktiver Tab uneinheitlich.** Seitenleiste: gefüllte Fläche plus Inset-Linie, Icon in Textfarbe. Tabbar: Icon türkis, Label 10,5 px/400 ohne Gewicht. Der aktive Zustand war auf den zwei Flächen unterschiedlich laut.
2. **Chips zu klein.** Filter- und Dauer-Chips waren 30 px hoch; `DESIGN.md` 2.4 verlangt mobil mindestens 44 × 44.
3. **Kartenabstand uneinheitlich.** Erholung 24 px, Training/Woche/Verpflegung 20 px; mobil waren alle 20 px. Der Desktop-Container war 1360 px breit, `DESIGN.md` 3.3 nennt ca. 1080–1200.
4. **Trainingszeile bei 320 px.** Der Name brach vierzeilig, weil Status-Pille und Chevron Platz in derselben Zeile belegten.
5. **Fokus.** Nur ein Teil der interaktiven Elemente hatte einen sichtbaren `:focus-visible`-Ring (u. a. fehlten Tabbar, Trainingszeile, Modus-Karten, Icon-Knöpfe, Sync).
6. **Scrollende/Safe Areas.** Am 390er-Ende lagen 24 px zwischen letzter Karte und Tabbar; die CSS-Abstände nutzten `env(safe-area-inset-*)` bereits an Main, Tabbar, Blatt, Popup und Pull, aber nicht am Desktop-Main und an der Seitenleiste.

---

## 2. Änderungen

| Datei | Änderung |
|---|---|
| `web/src/styles.css` | Seitenleiste: aktiver Zustand transparent, Icon im Akzent; Tabbar: Label 11 px, aktiv 500, Mindesthöhe 44, Fokusring; Chips mobil 44 px und 8 px Abstand; Karten 24 px (mobil 20); Desktop-Container 1200 px; Safe-Area-Unterabstand an Main und Seitenleiste; Fokusgruppe erweitert; 320er-Trainingszeile zweizeilig mit Status darunter |
| `docs/design/screens/phase4/*.png` | 16 Bilder: Start und Scrollende bei 320/390/430, Verpflegung 390, Desktop 1440, jeweils vorher/nachher |
| `docs/design/phase4-feinschliff.md` | dieser Bericht |

Kein Markup, keine Komponenten-Props, keine API-, Berechnungs-, Recovery-, DB- oder Sync-Änderung; keine neue Bibliothek.

### 2.1 Navigation

- **Seitenleiste:** `background: transparent`, Label `--text-primary`, Icon `--accent`; Hover bekommt eine leise Fläche. Kein Inset-Glow, kein breiter Halo.
- **Tabbar:** Icon 18, Label 11 px; aktiv Label 500 und Icon `--accent`, inaktiv beides `--text-muted`. Mindesthöhe 44 px; Safe-Area unten bleibt.
- `aria-current="page"` war seit Phase 2 vorhanden; der Fokusring ist jetzt auf beiden Flächen sichtbar.

### 2.2 Touchflächen

- Chips (Dauer-Voreinstellungen, Quellen, Filter) sind unter 1000 px **44 px** hoch, mit 8 px Abstand; auf Desktop bleiben sie 30 px (Mauszeiger).
- Tabbar-Buttons mindestens 44 px; die Trainingszeile bleibt 56 px.
- **Bewusst offen:** Die kleine g/ml-Umschaltung im Shot-Feld und der Slider-Thumb sind weiterhin kleiner als 44 px; sie gehören in die Zustands-/QA-Runde (Phase 5).

### 2.3 Abstände, Ränder, Scrollende

- Karten: 24 px Innenabstand ab 1001 px, 20 px darunter — Erholung, Training, Woche und Verpflegung gleich.
- Desktop-Container: max. 1200 px; die Karten bleiben bei 1440 px in der bisherigen Breite, weil die verfügbare Fläche schon darunter liegt.
- Main und Seitenleiste tragen unten `env(safe-area-inset-bottom)`; die Tabbar behält ihren unteren Safe-Area-Abstand. Am 390er-Scrollende bleiben 21 px zwischen letzter Karte und Tabbar.
- Ränder und Divider bleiben auf `--border-subtle`; Chart-Akzente (heutiger Balken, Ring, ausgewählter Modus) unverändert.

### 2.4 320 px

Unter 361 px wird die Trainingszeile zweispaltig: Icon + Name/Meta in der ersten Zeile, Status-Pille bzw. Last in der zweiten Zeile; der Chevron entfällt. Der Name bekommt die volle Breite und bricht nur noch zweizeilig, nicht vierzeilig.

---

## 3. Screenshots

Aufgenommen mit Chromium. Start und Scrollende bei **320×700**, **390×844**, **430×932**; Verpflegung bei 390×844; Desktop bei 1440×900. Vorher aus der laufenden Vorschau (Phase 3), nachher aus dem lokalen Vorschau-Build gegen dieselbe API. Die Sync-Zeit im Kopf kann sich zwischen den Aufnahmen um Minuten unterscheiden; die fachlichen Werte sind dieselben.

| Ansicht | Vorher | Nachher |
|---|---|---|
| Start 320 | [vorher-start-320.png](screens/phase4/vorher-start-320.png) | [nachher-start-320.png](screens/phase4/nachher-start-320.png) |
| Start 390 | [vorher-start-390.png](screens/phase4/vorher-start-390.png) | [nachher-start-390.png](screens/phase4/nachher-start-390.png) |
| Start 430 | [vorher-start-430.png](screens/phase4/vorher-start-430.png) | [nachher-start-430.png](screens/phase4/nachher-start-430.png) |
| Scrollende 320 | [vorher-bottom-320.png](screens/phase4/vorher-bottom-320.png) | [nachher-bottom-320.png](screens/phase4/nachher-bottom-320.png) |
| Scrollende 390 | [vorher-bottom-390.png](screens/phase4/vorher-bottom-390.png) | [nachher-bottom-390.png](screens/phase4/nachher-bottom-390.png) |
| Scrollende 430 | [vorher-bottom-430.png](screens/phase4/vorher-bottom-430.png) | [nachher-bottom-430.png](screens/phase4/nachher-bottom-430.png) |
| Verpflegung 390 | [vorher-verpflegung-390.png](screens/phase4/vorher-verpflegung-390.png) | [nachher-verpflegung-390.png](screens/phase4/nachher-verpflegung-390.png) |
| Desktop 1440 | [vorher-start-1440.png](screens/phase4/vorher-start-1440.png) | [nachher-start-1440.png](screens/phase4/nachher-start-1440.png) |

**Auffälligkeiten:**
- 320: Trainingszeile jetzt zweizeilig mit Status darunter; kein horizontales Scrollen.
- 390/430: Der aktive Tab ist nur noch über Icon-Farbe und Labelgewicht unterscheidbar; keine Fläche, kein Glow.
- Verpflegung 390: Chips 44 px, zwei Reihen für die Dauer; die Karte wird dadurch höher, bleibt aber ohne Überlauf.
- Scrollende 390: 21 px Luft über der Tabbar; die letzte Zeile „Belastungsverhältnis" ist vollständig sichtbar.
- Desktop: Seitenleiste ohne aktive Fläche, Icon türkis; Karten 24 px; der Container bleibt bei 1440 px in der bisherigen Breite.

---

## 4. Build und Tests

| Prüfung | Ergebnis |
|---|---|
| `cd web && npm run build` (stabil) | grün, 52 Module, 1,64 s; CSS 31,44 kB, JS 265,01 kB |
| `VITE_APP_VARIANT=preview npm run build` (für die Bilder) | grün, 52 Module, 1,53 s; CSS 31,44 kB, JS 265,23 kB |
| `UV_CACHE_DIR=.uv-cache uv run pytest` | **135 passed**, 1 Warnung, 6,02 s |
| QA 320/390/430/1440 | kein horizontaler Überlauf; Tabbar aktiv 11 px/500, min. 44 px; Sidebar aktiv transparent + Akzent-Icon; Karten 20/24 px; Chips 44 px/8 px; Scrollende 21 px; keine Konsolen-/Seitenfehler |

Die Prüfung lief über den lokalen Vorschau-Build und die echte Vorschau-API. Klickpfade (Heute/Verpflegung, Blätter) sind unverändert; die Navigation wurde in beiden Flächen geprüft.

---

## 5. Offene Punkte und Risiken

1. **Safe Areas am echten iPhone.** Headless-Chromium liefert `env(safe-area-inset-*) = 0`; die CSS-Abstände sind gesetzt, aber Notch/Dynamic Island und der Home-Indicator lassen sich hier nicht rendern. Sichtprüfung auf dem Gerät in Phase 5.
2. **Kleine Touchflächen.** g/ml-Umschaltung und Slider-Thumb sind weiterhin unter 44 px; ebenso der 40-px-`.btn` (derzeit ungenutzt). Phase 5.
3. **Score-Zustand.** Die Referenzzeile im Ring kann bei langem Text über den Ring laufen (Phase-3-Befund); ohne Score-Daten nicht erreichbar, Phase 5.
4. **Chips 44 px.** Die Verpflegungsseite wird dadurch höher; das ist der Preis der Touchfläche und bewusst.
5. **`--band-low: #e8925f`** aus Phase 1 ist weiterhin nicht separat abgenommen.
6. **Splash-Retry-Knopf.** Er nutzt `sync-btn`, für den es keine Gestaltung gibt (vorbestehend, nicht Teil dieser Phase).
7. **Screenshot-Zeit.** Die Sync-Zeit im Kopf unterscheidet sich zwischen vorher/nachher; die fachlichen Werte sind identisch.

---

## 6. Nächster kleiner Schritt

**Phase 5 — Qualitätsprüfung und Dokumentation:** alle Zustände (Laden, leer, Fehler, Teilwerte, Sync alt, Offline), Kontrast, `prefers-reduced-motion`, Tastatur/Screenreader, 320/390/430 px und iPhone-Safe-Areas, finale Screenshots. Erst nach menschlicher Freigabe; keine automatische Folgephase.
