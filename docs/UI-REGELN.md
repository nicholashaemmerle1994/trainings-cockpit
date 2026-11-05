# Oberfläche — wie hier gestaltet wird

> **Ersetzt am 05.11.2026 durch [`DESIGN.md`](../DESIGN.md) (D-59).**
> Diese Datei bleibt als Herkunftsnachweis stehen — die Regeln sind aus
> *unslop* übernommen, und die Lizenz (CC BY 4.0) verlangt, dass Name und
> Link bleiben. Verbindlich für neue Arbeit ist `DESIGN.md`.


Diese Datei gilt für jede Arbeit an einer Oberfläche im Cockpit: Dashboard,
Verpflegungsseite, Aktivitätenliste, später Plan und PWA.

Die Regeln sind übernommen aus **unslop** von Damir Sokolovsky
([github.com/heydamir/unslop](https://github.com/heydamir/unslop),
[x.com/heydamir](https://x.com/heydamir)), Lizenz CC BY 4.0. Der Name und die
Herkunft bleiben in jeder Kopie und Anpassung stehen — das verlangt die Lizenz.
Was hier steht, ist die auf dieses Projekt gekürzte Fassung; im Zweifel gilt das
Original.

## Der Kern in einem Satz

Ein Bildschirm hat **ein helles Element**, das die Farbe und die Sorgfalt trägt.
Alles andere — Navigation, Karten, Rahmen, Labels — bleibt ruhig. Reichtum gehört
in den Inhalt, nicht in die Bedienelemente.

## Mobil zuerst

Entworfen wird auf **390 × 844**, geprüft wird dort, und erst danach auf dem
breiten Schirm. Das Handy ist der Ort, an dem das Cockpit benutzt wird; der
Rechner zeigt dasselbe größer, nicht anders.

- Zuerst der Bildschirm, den man mit einer Hand erreicht: Kopf oben, Handlung
  im unteren Drittel, nichts Wichtiges unter der Tableiste.
- Tap-Ziele mindestens 40 px hoch, 8 px Abstand zwischen zweien.
- Zwei Spalten nur, wenn sie bei 390 px noch zwei Spalten sind — sonst stapeln.
- Keine Fläche, die nur mit der Maus funktioniert (Hover, Zeiger, Rechtsklick).
- Vor dem Umbau ein Handy-Mockup; der breite Schirm kommt danach und ohne neue
  Entscheidung.

## Ablauf

1. **Ansehen.** Bildschirm im Browser rendern und einen Screenshot beurteilen,
   nicht den Code. `node web/scripts/audit-shots.mjs <url>` macht Desktop und Handy.
2. **Prüfen.** Jeden Fund aus der Liste unten mit Fundort notieren, eine Zeile je
   Fund. Die Liste ist der Prüfstein, nicht das Gedächtnis.
3. **Einordnen.** Viel Slop → ganzer Durchlauf. Wenig Slop → nur die Funde
   beheben, Palette, Schrift und Layout behalten. Kein Slop → sagen und höchstens
   zwei, drei kleine Vorschläge machen.
4. **Richtung schreiben und anhalten.** Fünf Zeilen (siehe unten). Erst fragen,
   dann bauen — eine geänderte Richtung heißt alles neu. Nur überspringen, wenn
   ausdrücklich „mach einfach" gesagt wurde.
5. **Neun Durchgänge, in dieser Reihenfolge.** Abstand zuerst, weil danach alles
   anders liest. Text vor Schrift und Layout, weil die Länge die Größe entscheidet.
   Bild und Bewegung zuletzt, weil sie zu einem Bildschirm passen sollen, der ohne
   sie schon funktioniert. Einen Durchgang über den ganzen Bildschirm fertig
   machen, bevor der nächste beginnt.
6. **Prüfen.** Neu rendern, mit der Fundliste vergleichen. Was noch steht, wird
   behoben. Höchstens drei Renderdurchläufe je Auftrag.
7. **Berichten.** Richtung, ein paar Zeilen je Durchgang, was noch offen ist.

## Richtung — fünf Zeilen, vor dem ersten Handgriff

- **Produkt.** Was es tut und für wen, in einem schlichten Satz.
- **Charakter.** Zwei, drei konkrete Wörter, etwa `nüchtern, genau, ein bisschen
  alpin`. Verboten: clean, modern, sleek, minimal, premium — das beschreibt jede
  Vorlage.
- **Welt.** Ort oder Material, zu dem das Produkt gehört. Ein Notizbuch liegt bei
  Papier und Tinte, ein Messgerät bei Instrumenten und Nachtschicht, ein
  Trainingsbuch bei Bahn, See und frühem Licht. Die Welt bestimmt den Ton der
  Grautöne, den Akzent und das Bild.
- **Momente.** Ein, zwei Stellen, an denen der Bildschirm reich werden darf:
  ein Instrument, ein sorgfältig gezeichneter Graph, ein Objekt aus der Welt.
- **Signatur.** Ein kleines Detail, das nur dieses Produkt hat, konsequent
  verwendet. Ein lebender Punkt für ein Überwachungswerkzeug, Tasten für ein
  Entwicklerwerkzeug, eine Route für eine Lieferung. Eines, nicht fünf.

## Die neun Durchgänge

### 1. Abstand
Alles auf dem 4-px-Raster: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64. 2 px ist für
Nudges in kleinen Bedienelementen erlaubt, ein ungerader Wert, der genau
zentriert, bleibt. Gleiches Ding, gleiche Größe: alle Zeilen einer Liste ein
Abstand, alle Karten einer Reihe ein Innenabstand. Abstand zeigt Gruppierung:
innen kleiner als zwischen Gruppen. Dinge stehen auf einer Linie — Icons in einer
Spalte, Zahlen rechtsbündig in einer Spalte. Dichte: Seitenrand 24–32, Karten
20–24, kompakte Panels 16. Navigation ist der dichteste Teil: Zeilen 32–36 hoch,
2–4 dazwischen, Abschnitts-Label 24 darüber und 8 darunter.

### 2. Farbe
Eine neutrale Rampe, leicht in Richtung der Welt getönt. Hintergrund, Flächen,
Rahmen und Text kommen alle aus dieser Rampe. In Apps bleibt die Fläche neutral —
ein Hintergrund, der orange, braun, blau oder grün liest, ist zu weit gegangen.
Drei Textrollen: primär, sekundär, gedämpft. Nicht zehn Fast-Gleiches. Im Rahmen
**ein** Akzent, sparsam: die eine Aktion, die Auswahl, die eine Zahl, die zählt.
Nur in den Momenten darf Farbe reich werden. Keine Farbverläufe über Flächen,
kein Gradient-Text, kein farbiger Schein, keine farbigen Schatten, keine Radial-
Washes, keine Neonrahmen. Rahmen sind Haarlinien: Textfarbe bei 6–10 % Deckung.
Tiefe kommt auf dunklem Grund aus Flächenstufen und Haarlinien, nicht aus Schatten.
Ein Verlauf ist nur als kleiner Tonwechsel **innerhalb** einer Neutralfarbe
erlaubt, nie von einem Farbton zum anderen. Akzent mit Text darauf braucht 4,5:1.

### 3. Icons
Ein Satz (lucide), eine Größe (16 oder 18), ein Strich (1,5), eine Farbe — die
der Textrolle. Icons bekommen nie eigene Farben. Gleiche Boxbreite in jeder
Zeile, fester Abstand zum Label (8 oder 10). Emoji verschwinden. Icons, die nichts
erklären, fallen weg.

### 4. Text
Überschriften sagen, was das Produkt für wen tut, in schlichten Worten. Keine
Begrüßung (`Servus, Nicholas`), kein Ausrufezeichen. Kurze Labels: `Suche`, nicht
`Suche alles...`. Eine Änderung nennt ihren Bezug: `+12 % gegenüber August`. Kein
Punkt am Ende von Überschrift, Label, Knopf, Bildunterschrift — nur ganze Sätze
behalten ihn. Keine Werbewörter. Erfundene Zahlen sehen echt aus. Badges wie
`NEU` entfallen oder werden zu leiser Schrift.

### 5. Schrift
Eine Familie für die Oberfläche, höchstens eine Partnerin (Mono für Zahlen und
Meta, Display nur für große Überschriften). Wenige Größen aus einer Skala, zwei
Gewichte (400 und 500, 600 selten). Hierarchie über Größe und Farbe, nicht über
Fettung. **Sentence case** — `Navigation`, nicht `NAVIGATION`. Kein negativer
Buchstabenabstand bei kleiner Schrift. Zahlen mit `tabular-nums` und **einem**
Format auf dem ganzen Bildschirm. Keine Kursive.

### 6. Layout
Abschnitte und ihre Reihenfolge bleiben. Echte App-Proportionen: Leiste 240–280,
Inhalt fließend, höchstens 1440–1600 breit, Seite so lang wie ihr Inhalt. Keine
schmale zentrierte Spalte. Ein primärer und höchstens ein sekundärer Handlung.
Erster Bildschirm als Ganzes komponiert, ohne totes Band. Auf dem Handy stapelt
sich alles in Leserichtung, dichte Vorschauen werden einfacher statt
heruntergezoomt, nichts unter 11 px.

### 7. Details
Radius nach Größe, verschachtelt: innen = außen − Abstand, nie unter 4.
Bedienelemente 8–10, Karten 12–16, Panels 14–20. Nicht alles ist eine Pille.
Zähler und Meta werden leise Schrift, oft Mono und gedämpft. Diagramme stehen auf
gedämpftem Raster mit gedämpften Mono-Labels; **ein** Akzent je Diagramm — das,
was zählt, bekommt ihn, der Rest bleibt in Neutralstufen. Ein Hauptdiagramm ist
deutlich das größte; alles andere, was Daten zeigt, ist kleiner und andersartig.
Kennzahlenkarten sind **Zahl, Label, Veränderung** — keine Sparkline, keine
Mini-Balken, kein Icon als Füllung. Karten gleicher Breite mit gleichem Inhalt
lesen als Vorlage; dem Raster einen Rhythmus geben. Der aktive Zustand ist eine
kleine Flächenstufe mit Haarlinien-Highlight, kein Verlauf mit Schein. Fokusring
für Tastatur bleibt sichtbar.

### 8. Bild
Füllende Dekoration fällt weg: glänzende Blobs, Orbs, Nebel, schwebende Würfel,
leuchtende Raster. Dashboards brauchen fast nie ein erzeugtes Bild — ihre Momente
kommen aus dem Produkt selbst: ein sorgfältig gezeichnetes Diagramm, schön
gesetzte Zahlen, echte Inhalte, ein Zustand, der lebt.

### 9. Bewegung
Keine Schleife ohne Grund, kein Pulsieren, kein Schweben, kein `transition-all`,
kein `hover:scale` auf Karten. Bewegung nur, wo sie etwas erklärt. Eine Kurve für
alles: `cubic-bezier(0.22, 1, 0.36, 1)`. 120–180 ms für Feedback, 160–220 ms für
Menüs, 300–500 ms für Eintritte, Staffelung 40–60 ms, höchstens sechs Elemente.
Nur Farbe, Fläche, Rahmen, Deckkraft und Transform animieren — nie Breite, Höhe,
`top` oder `left`. Ein Eintritt beim Laden, kurz und mit kleinem Versatz.

## Nie

- Das Produkt umbenennen oder sein Wesen ändern.
- Entfernte Dekoration durch neue ersetzen (Glas, Korn, Neon, Bento-Raster).
- Funktionen, Behauptungen oder Daten erfinden.
- Für jedes Produkt dieselbe Optik auspacken — die Richtung entscheidet Palette,
  Schrift und Bild, nicht die Gewohnheit.
- Einen guten Bildschirm ändern, nur damit er anders aussieht.

## Prüfliste

- [ ] Richtung steht und jeder Durchgang folgt ihr
- [ ] Jeder Abstand auf dem 4-px-Raster, gleiche Dinge gleich groß
- [ ] Icons, Labels und Zahlen je in einer Spalte
- [ ] Eine getönte Neutralrampe, drei Textrollen, ein Akzent mit genug Kontrast
- [ ] Keine Farbverläufe über Flächen, kein Gradient-Text, kein Schein, keine Blobs
- [ ] Kein Emoji in der Oberfläche
- [ ] Ein Icon-Satz, eine Größe, ein Strich
- [ ] Gewichte 400 bis 600, keine Großbuchstaben-Labels, keine Kursive
- [ ] Keine Ausrufezeichen, keine Punkte an kurzen Texten, keine Begrüßung
- [ ] Zahlen in einem Format, tabellarisch
- [ ] Verschachtelte Radien gehen auf
- [ ] Kennzahlenkarten ohne Sparkline
- [ ] Bei 390 px geprüft: nichts abgeschnitten, nichts zu klein
- [ ] Erster Bildschirm als Ganzes, kein totes Band
- [ ] Keine Schleifenbewegung, eine Kurve, keine Layout-Animation
- [ ] Vorlagenprobe: Würde der Bildschirm auch zu einem anderen Produkt passen?
    Wenn ja, Richtung in Text, Bild und Signatur härter ziehen.

## Hier im Projekt

- Regeln: diese Datei. Umsetzung: `web/src/styles.css`, Komponenten in
  `web/src/components/`.
- Entscheidungen und Richtung: `docs/ENTSCHEIDUNGEN.md` (Abschnitt 3, ab D-28).
- Prüfbilder: `data/screens/`.
