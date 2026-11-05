# AGENT_MIGRATION.md — Bestehendes Dashboard auf das Premium-Design umstellen

> **Beilagen:** `DESIGN.md` und `cockpit-premium-reference.png`  
> **Mission:** Visuelle Modernisierung des bestehenden Cockpit-Dashboards — **keine** fachliche Neuentwicklung.

## So arbeitest du mit diesem Auftrag

1. Lege `DESIGN.md` ins Projekt-Root, ggf. die Referenzgrafik unter `docs/design/cockpit-premium-reference.png` ab.
2. Weise dem Coding-Agenten dieses Dokument als **verbindlichen Arbeitsauftrag** zu.
3. **Wichtig:** Er soll **nicht** alles in einem Schritt refaktorieren, sondern **nach jeder Phase stoppen** und eine kurze Review/Abnahme abwarten.
4. Verwende die grafische Referenz zur optischen Orientierung, **nicht** als Quelle von App-Daten oder Fachlogik.

## Fertiger Arbeitsauftrag für den Coding-Agenten

Du bist mein Frontend-/UI-Implementierungsagent. Deine Aufgabe ist, mein **bestehendes** Trainings-/Recovery-Cockpit visuell an `DESIGN.md` und `cockpit-premium-reference.png` anzupassen.

### Harte Vorgaben

- **UI/UX only.** Kein Verändern von API-Endpunkten, Berechnungen, Recovery-Logik, Intervals/Garmin-Datenintegration, Datenbank, Auth, Trainingsplanung oder Synchronisationsverhalten.
- Bestehendes Framework, Komponentenarchitektur und Routing beibehalten. Kein unnötiger Rewrite, keine neue Bibliothek ohne begründete Freigabe.
- Kein Hardcoding von Werten aus der Referenzgrafik. Der Referenzscreen ist ein **Mockup**.
- **Wichtig für Recovery:** Solange der Sensor 2 von 21 Referenznächten hat und noch kein Score berechnet werden kann, muss die UI weiterhin **„Referenz wird aufgebaut“** zeigen. Die **82/100** in der Referenzgrafik ist ausschließlich eine optische Beispielzahl und darf nicht im Produkt erscheinen.
- Der bestehende Datenstand, auch Empty/Partial/Error/Loading/Offline, ist fachlich korrekt zu bewahren.
- Türkis etwas satter, Kontrast höher, große Zahlen präziser, Karten mit subtiler Tiefe; **keine Emojis**, **kein starker Glow** am ausgewählten Tab.
- Kleine, reviewbare Änderungen. Nach **jeder Phase** stoppen und meine Zustimmung abwarten. Keine automatischen Folgephasen.

### Phase 0 — Audit, noch NICHT implementieren

Untersuche die existierenden Dateien und stelle mir einen kurzen Bericht bereit:

- Verwendeter Tech-Stack, Stylingansatz (CSS Modules, Tailwind, global CSS, etc.) und Navigationsstruktur.
- Welche Komponenten bereits wiederverwendbar sind und welche Styles derzeit dupliziert werden.
- Wo die Screens **Header, Wettkampf-Countdown, Erholung, Training, Letzte 7 Tage, Bottom Tabs** liegen.
- Welche Zustände die bestehenden Screens behandeln, insbesondere unvollständige Sensordaten.
- Konkreter Migrationsplan in kleinen Phasen; betroffene Dateien und Risiken.

**Dann STOPP: keine Codeänderung vor meiner Freigabe.**

### Phase 1 — Tokens und Basis-Styles

Nur zentrale Farb-, Typografie-, Spacing-, Border- und Radius-Tokens einführen/vereinheitlichen; bestehende Styles auf Tokens umstellen, soweit ohne Layout-Umbau möglich. Dark Mode ist die Hauptvariante. Den vorhandenen Look funktional bewahren, keine Datenlogik anfassen.

Liefere: Diff-Zusammenfassung, Screenshots vorher/nachher und Build-/Testergebnis. **Dann STOPP.**

### Phase 2 — Gemeinsame UI-Bausteine

`DashboardCard`, `MetricRow`, `StatusBadge`, `ScreenHeader`, `WorkoutPreview`, Navigation/Icon-Style und ggf. Charts konsolidieren, ohne alles zu abstrahieren. Bestehendes Verhalten muss gleich bleiben.

Liefere: betroffene Komponenten, Beispielansichten, eventuelle Regressionen und Tests. **Dann STOPP.**

### Phase 3 — Cockpit-Startseite

Die bestehenden Abschnitte in Reihenfolge überarbeiten: Header/Countdown → Erholung → Training → Letzte 7 Tage. Bitte in der Implementierung gerne **nur einen Abschnitt pro Freigabeschritt** behandeln, falls das Projekt größere Komponenten besitzt.

Designvergleich gegen Referenz, aber fachliche Daten nicht austauschen. Besonders: Recovery-Baseline-Status korrekt erhalten, keine erfundene 82.

Liefere je Abschnitt: kurze Erklärung, Screenshot und Diff. **Nach jedem Abschnitt STOPP.**

### Phase 4 — Navigation und Feinschliff

Bottom-Tabbar mit einheitlichen Outline-Icons; aktiver Tab: türkis und minimaler Highlight-Effekt, praktisch kein Hue/Glow. Ränder, Dividers, Chart-Akzent und Spacing final harmonisieren. iPhone Safe Areas und Scrollenden prüfen.

Liefere: Screenshots bei 320/390/430 px, optional Desktop, mit dokumentierten Auffälligkeiten. **Dann STOPP.**

### Phase 5 — Qualitätsprüfung und Dokumentation

Prüfe sämtliche vorhandenen Zustände (Loading, kein Workout, fehlende API-Werte, Sensorreferenz, Sync alt, API-Fehler), Touchflächen, Kontrast, `prefers-reduced-motion`, Navigation und Build/Tests. Erfasse **nur** bei tatsächlicher Notwendigkeit Ergänzungen in `DESIGN.md`.

Liefere: Checkliste, verbleibende Risiken, Tests, finale Screenshots. **Dann STOPP.**

### Format für jedes Phasen-Review

1. **Ziel / tatsächlich geändert** (kurz)
2. **Geänderte Dateien**
3. **Vorher/Nachher** (Screenshots, wenn möglich)
4. **Datenlogik unverändert?** (explizit bestätigen oder Abweichungen benennen)
5. **Build/Tests** (welche liefen, Ergebnis)
6. **Offene Punkte / Risiken**
7. **Nächster kleiner Schritt** — nur vorschlagen, **nicht** selbständig ausführen

## Abnahmekriterien

- Es bleibt **deine bestehende App**; primär Farben, Oberflächen, Abstände, Schrift, Icons, Visualisierung und Hervorhebungen werden verbessert.
- Ein neuer Feature-Screen kann sich mit denselben Tokens und Basiskomponenten integrieren.
- Nur echter aktueller Tab wird hervorgehoben; Akzent/Glow bleiben zurückhaltend.
- Kein fachlicher Verlust, keine neuen Mockdaten in produktiven UI-Komponenten.
- Änderungen sind über Diffs und Screenshots nachvollziehbar.
