# Laufplaner: Algorithmus, Paces und Periodisierung

**Status:** Planung. Nichts davon ist in der App umgesetzt, angebunden oder
gemergt.
**Stand:** 07.11.2026
**Branch:** `planung/laufplaner-algorithmus`
**Zweck:** Entscheidungsgrundlage, ob und wie ein eigener Laufplaner gebaut
wird — und was von Runna übertragbar ist.

---

## 0. Kurzfassung

Runna ist kein KI-Planer. Es ist eine **regelbasierte Coach-Engine** mit einer
kleinen Zahl von Eingaben. Das ist die wichtigste Erkenntnis, weil sie den
Nachbau entzaubert: Die Qualität kommt nicht aus einem geheimen Modell, sondern
aus vier Entscheidungen.

1. **Eine aktuelle Leistung, nicht die Wunschzeit.** Runna leitet alle Paces aus
   *einer* aktuellen Wettkampfzeit ab (5 km, 10 km oder Halbmarathon). Es gibt
   bewusst kein Zielzeit-Feature: „Runna does not train you to a specific goal
   time." Die aktuelle Leistung schützt vor einem Plan, der den Athleten
   überfordert.
2. **Paces sind Zonen, keine Punkte.** Locker, Marathon, Schwelle, Intervall,
   Repetition — jede Zone hat ein Band. Easy Runs sind gesprächig, nicht
   sekundengenau.
3. **Anpassung ist ereignisgetrieben und braucht Zustimmung.** Nach einer
   Qualitätseinheit kann Runna eine Pace-Empfehlung zeigen. Sie entsteht erst,
   wenn mehrere Signale in dieselbe Richtung zeigen, und sie wird erst nach
   Bestätigung wirksam. Easy Runs allein lösen nie eine Pace-Änderung aus.
4. **Periodisierung ist konservativ.** Build-Build-Deload, lange Läufe wachsen
   separat, Taper 2–3 Wochen (Halbmarathon und länger: 3), 80/20 als Leitlinie.
   Deloads werden in der App nicht als solche beschriftet.

Was wir **nicht** wissen: die genauen Formeln, die Breite der Zonen, die
internen Schwellen für „Trend erkannt", die exakten Volumenregeln. Runna
veröffentlicht nur Anker, keine Algorithmen. Der Nachbau ist deshalb eine
Rekonstruktion aus öffentlichen Aussagen plus Trainingslehre — keine Kopie.

Die Empfehlung für das Cockpit:

- **Deterministischer Kern in Python.** VDOT, Paces, Periodisierung, Volumen,
  Guardrails. Kein LLM in der Zahlenlogik.
- **DeepSeek nur für Text und Absicht.** Erklärungen, Wochenrückblick,
  natürlichsprachige Verschiebungen. Nie für Pace-Berechnung oder Schreiben.
- **Vorschlag statt Autopilot.** Der Plan wird erzeugt, geprüft, freigegeben und
  erst dann als Event über den vorhandenen Schreibpfad nach intervals.icu
  gelegt.
- **Erst der Lauf, dann der Ironman.** Ein Laufplan für einen Ironmarathon ist
  kein Marathonplan. Er braucht ein Lastbudget aus Rad und Schwimmen.

---

## 1. Auftrag und Nicht-Ziele

**Auftrag:** Ein Algorithmus, der aus Zielrennen, aktueller Fitness und
verfügbaren Tagen einen laufspezifischen, periodisierten Plan erzeugt, die
Paces erklärt und Anpassungen vorschlägt.

**Nicht-Ziele in dieser Stufe:**

- Keine Änderung an `develop`, keine API, keine Datenbankmigration, keine UI.
- Kein automatisches Schreiben nach intervals.icu.
- Kein Ersatz für Arzt, Physio oder Trainer.
- Kein Multi-Sport-Planer. Der Ironman-Lauf ist zunächst ein Laufplan mit
  Lastkorridor, kein vollständiger Triathlon-Plan.
- Keine Zielzeit als Trainingsvorgabe.

**Warum die Trennung wichtig ist:** Ein Trainingsplan ist ein Versprechen über
Wochen. Ein Algorithmus, der Paces aus einer Wunschzeit ableitet, produziert
plausible Zahlen für ein Ziel, das der Körper vielleicht nicht hergibt. Runna
macht das bewusst nicht. Das Cockpit sollte es genauso machen.

---

## 2. Was Runna öffentlich erkennen lässt

Quellenlage: Runna-Hilfeseiten, App-Store-Beschreibung, Interviews und
Presseberichte. Die genauen Formeln sind nicht öffentlich. Ich trenne deshalb
durchgehend:

- **BELEGT** — durch eine Quelle direkt gedeckt.
- **PLAUSIBEL** — aus öffentlichen Ankern und Trainingslehre rekonstruiert.
- **UNBEKANNT** — Runna sagt es nicht, und ich rate nicht.

### 2.1 Onboarding: wenige Eingaben, eine Referenz

Runna fragt beim Anlegen eines Plans nach:

- Plan-Typ und Distanz (5 km, 10 km, Halbmarathon, Marathon),
- Erfahrungsstufe (Beginner, Intermediate, Advanced, Elite),
- aktuellem Wochenumfang und längstem Lauf,
- Anzahl der Läufe pro Woche und Trainingstagen,
- Renndatum und Planlänge (8–26 Wochen),
- **einer aktuellen Wettkampfzeit** (5 km, 10 km oder Halbmarathon).

Das ist belegt. Nicht belegt ist, ob Runna zusätzlich die Strava-Historie
automatisch als Fitnessquelle nutzt. Die Hilfe sagt an anderer Stelle, dass
Pace-Analysen nur auf den in der App aufgezeichneten Läufen beruhen; freie
Läufe und manuelle Uploads fallen heraus. Das spricht dafür, dass die
Wettkampfzeit die primäre Referenz ist und die Historie höchstens den Startwert
plausibilisiert.

**Wichtig:** Es gibt kein Feld „Zielzeit". Runna trainiert nicht auf eine
Wunschzeit. Die Pace kommt aus der aktuellen Leistung; das Ziel ist ein
Ergebnis, keine Vorgabe.

### 2.2 Paces: eine Zahl strahlt auf alle Distanzen

Alle Trainingspaces werden aus derselben Referenz abgeleitet. Öffentlich belegt
sind nur grobe Anker:

| Zone | Öffentlicher Anker |
|---|---|
| Intervall | etwa Schwellentempo oder 5–10-km-Renntempo |
| Tempo | etwa 10-km- bis Halbmarathon-Renntempo |
| Easy | „conversational", ohne Zahl |
| Long Run | oft ohne Pace-Ziel |

Runna nennt die Einheiten „Interval" und „Tempo"; „Schwelle" ist dort ein
physiologischer Begriff, kein Sessionname. Für den Nachbau ist die Bezeichnung
egal, die Zone nicht.

Die genaue Formel, die Zonenbreiten und die Offsets sind **UNBEKANNT**. Es gibt
keine öffentliche VDOT-, Riegel- oder Critical-Speed-Rechnung von Runna.

Was sich daraus rekonstruieren lässt: Runna arbeitet mit einem
leistungsäquivalenten Modell. Eine 5-km-Zeit wird auf 10 km, Halbmarathon und
Marathon umgerechnet; daraus entstehen die Zonen. Das ist genau das, was VDOT
leistet. Ob Runna intern VDOT, eine eigene Tabelle oder eine andere
Äquivalenzformel nutzt, ist offen — für den Nachbau ist VDOT die
transparenteste Wahl.

### 2.3 Anpassung: Ereignis, Trend, Zustimmung

Das ist der Teil, der die Eingangsfrage trifft: „Easy Paces werden passend
schneller — erkennt der Algorithmus das, oder plant er es ein?"

Runna macht **beides**, aber in einer klaren Reihenfolge:

1. **Erkennen:** Nach einer Speed-Einheit analysiert Runna die App-eigene
   Aufzeichnung. Aus Dauer, Distanz und Tempo entsteht ein Fitness-Signal.
2. **Trend prüfen:** Eine einzelne gute Einheit reicht nicht. Die Empfehlung
   entsteht erst, wenn mehrere Speed-Einheiten in dieselbe Richtung zeigen.
3. **Vorschlagen:** Der Athlet sieht eine Empfehlung mit alter und neuer Pace.
   Nichts ändert sich automatisch.
4. **Annehmen:** Erst nach Bestätigung werden **alle Zielpaces im restlichen
   Plan** neu berechnet — nicht nur die eine Einheit.

Belegt ist außerdem:

- Es gibt **keinen festen Rhythmus** (nicht „alle vier Wochen"). Die Analyse
  hängt an den Einheiten, nicht am Kalender.
- **Easy Runs lösen keine Pace-Änderung aus.** Sie sind zu variabel (Hitze,
  Untergrund, Ermüdung) und kein sauberer Leistungstest.
- **RPE-Läufe fallen aus der Pace-Analyse.** RPE ist ein Anzeigemodus, kein
  Feedback-Kanal für die Pace.
- Manuell kann der Athlet eine Pace um etwa 15–30 s/km anpassen; das ist eine
  Korrektur, keine automatische Logik.

Das ist ein sehr gutes Muster: **Der Athlet behält die Kontrolle, der
Algorithmus liefert die Begründung.** Genau so sollte es im Cockpit laufen.

### 2.4 Plananpassung bei verpassten Einheiten

Runna verschiebt, löscht nicht:

- Einheiten lassen sich um ±1 Woche verschieben.
- Es gibt einen Lauf pro Tag.
- Nach mehr als drei verpassten Einheiten oder einer vollen Woche bietet Runna
  ein **Plan Realignment** an — typischerweise montags. Die Optionen: verpasste
  Einheiten überspringen, nach hinten schieben, den Plan verlängern, ihn auf
  dasselbe Enddatum neu bauen oder unverändert weiterlaufen. Die Entscheidung
  ist irreversibel; das Pop-up erscheint nur, wenn die Einheit nicht
  ausdrücklich als „skip" markiert wurde.
- „Not Feeling 100%" deckt bis zu 14 Tage ab, mit vier Stufen und drei
  Rückkehrgeschwindigkeiten.
- Holiday Mode (3–21 Tage) verschiebt Deloads; die Planlänge bleibt.
- Hitzeanpassung greift ab etwa 20 °C gefühlter Temperatur.

**UNBEKANNT:** die genaue Realignment-Formel, wie stark Volumen und Intensität
dabei zurückgehen, und ob das Renndatum dabei immer unverändert bleibt.

### 2.5 Periodisierung: Build, Build, Deload

Öffentlich belegt:

- Pläne sind 8–26 Wochen lang; Minimum für Halbmarathon 12, für Marathon 16.
- Rhythmus: **Build–Build–Deload**, Deloads alle 4–5 Wochen. In der App werden
  Deloads **nicht als Deload beschriftet** — die Woche ist einfach leichter.
- Der Wochenumfang hat eine mileage-abhängige Obergrenze.
- Der lange Lauf wächst separat um etwa 10–15 % pro Woche.
- Marathon-Peak: etwa 32 km langer Lauf, idealerweise zweimal.
- Halbmarathon-Longruns: etwa 75–80 % der Renndistanz, also rund 16–17 km.
- Taper: **3 Wochen** für Halbmarathon und länger bzw. Pläne ab 10 Wochen,
  sonst 2 Wochen.
- 80/20 ist Leitlinie, keine harte Regel: Bei 5–7 Läufen pro Woche sind 4–5
  locker und 2–3 hart; bei 2–3 Läufen eher 60:40. Warm-up und Cool-down zählen
  nicht zu den 20 %.

**UNBEKANNT:** Ob Runna intern „Base", „Build" und „Peak" als benannte Phasen
führt. Die App zeigt vor allem Wochen und einen Taper; die Phasenlabels sind
unsere Rekonstruktion, nicht Runnas Vokabular.

### 2.6 KI: nein, die Pläne sind nicht LLM-generiert

Das ist für die DeepSeek-Frage zentral:

> „We don't use AI to generate training plans." — Runna-Sprecher, in einem
> Runner's-World-Artikel.

Das Help-Center nennt die Pläne „coach-built, rules-based". LLMs werden nur für
**Workout Briefings** (vor dem Lauf) und **Workout Insights** (nach dem Lauf)
eingesetzt; diese Texte „will not impact your training plan".

Die Lehre: Ein LLM kann den Plan erklären, aber es soll ihn nicht rechnen. Das
deckt sich mit D3 im Cockpit („Regelkern deterministisch, LLM nur für Text").

### 2.7 Kritik und Grenzen

Runna ist nicht unumstritten:

- Physiotherapeuten berichteten gegenüber WSJ/futurezone von mehreren
  Runna-Verletzungsfällen pro Woche; der Vorwurf: Umfang und Intensität steigen
  zu schnell, der Audio-Coach drängt („zu langsam").
- Runner's World kritisierte, dass die Mileage ab Woche 3 zu hoch sei.
- the5krunner beschreibt Überlastungsmuster, hält aber fest: Es gibt keine
  vergleichende, peer-reviewte Studie, die belegt, dass Runna-Athleten sich
  häufiger verletzen.

Die Gegenmaßnahmen („Not Feeling 100%", Hitzeanpassung, Realignment) sind
Reaktionen auf genau diese Kritik. Für den Nachbau heißt das: **Die
Progressionsregeln sind der riskanteste Teil, nicht die Paces.** Ein Plan, der
mathematisch schön steigt, aber die Belastbarkeit nicht kennt, ist schlechter
als ein langsamerer Plan.

**UNBEKANNT / nicht geprüft:** Reddit, Trustpilot und marathonhandbook waren
aus dem Recherchenetz nicht erreichbar. Die Kritik stützt sich auf Presse und
Fachseiten, nicht auf eine systematische Nutzerbefragung.

### 2.8 Belegt, plausibel, unbekannt — die Tabelle

| Aussage | Status |
|---|---|
| Ein aktueller Wettkampfwert speist alle Paces | BELEGT |
| Kein Zielzeit-Feature | BELEGT |
| Paces werden nach Trend und mit Zustimmung neu berechnet | BELEGT |
| Easy Runs lösen keine Pace-Änderung aus | BELEGT |
| RPE-Läufe zählen nicht in die Pace-Analyse | BELEGT |
| Build–Build–Deload, Deload alle 4–5 Wochen | BELEGT |
| Taper 2–3 Wochen, Marathon-Peak ca. 32 km | BELEGT |
| 80/20 als Leitlinie | BELEGT |
| Pläne sind regelbasiert, nicht LLM-generiert | BELEGT |
| Genaue Pace-Formel, Zonenbreiten, Trendschwellen | UNBEKANNT |
| Base/Build/Peak als interne Phasen | UNBEKANNT |
| Automatische Strava-Historie als Fitnessquelle | UNBEKANNT |

---

## 3. Was wir übernehmen — und was nicht

**Übernehmen:**

1. **Eine aktuelle Referenz, nicht die Wunschzeit.** Das ist der wichtigste
   Schutz gegen Überlastung.
2. **Pace-Zonen statt Punkte.** Ein Band ist im Gelände robuster als eine Zahl.
3. **Ereignisgetriebene Updates mit Zustimmung.** Kein Kalenderzwang, keine
   stille Änderung.
4. **Nur Qualitätseinheiten als Pace-Signal.** Easy Runs und RPE-Läufe zählen
   nicht.
5. **Build–Build–Deload und ein ehrlicher Taper.**
6. **Verschieben statt löschen.** Ein verpasster Lauf ist kein Grund, den Plan
   umzuschreiben.
7. **Ein Lauf pro Tag**, mindestens 48 Stunden zwischen harten Reizen.

**Nicht übernehmen:**

- Die undurchsichtige Formel. Wir rechnen mit VDOT und dokumentieren jeden
  Schritt.
- Das ungelabelte Deload. Wir zeigen „leichte Woche" und warum.
- Die aggressive Volumenprogression, die in der Kritik steht. Wir deckeln
  stärker und prüfen die Belastbarkeit.
- Automatisches Realignment ohne Erklärung. Wir zeigen den Diff und fragen.
- RPE als Pace-Signal. RPE bleibt Steuerung für Belastung und Erholung.

**Besser machen:**

- **Transparenz:** Jede Pace hat eine Herleitung (VDOT, Zone, Band).
- **Eigene Daten:** intervals.icu, Aktivitäten, Erholung — nicht nur App-Läufe.
- **Ironman-Kontext:** Der Laufplan bekommt ein Lastbudget aus Rad und
  Schwimmen; er ist kein Inselplan.
- **HF als Deckel:** Pace führt, Herzfrequenz begrenzt. Bei Hitze, Wind und
  Müdigkeit gewinnt die HF.
- **Kein Autopilot:** Der Plan ist ein Vorschlag, jede Änderung braucht einen
  Klick.

---

## 4. Der Algorithmus

### 4.1 Pipeline

```
Ziel (Distanz, Datum, Priorität)
  + Athlet (aktuelle Leistung, Wochenumfang, Tage, Erfahrung)
  + Umgebung (Hitze, Höhe, Last aus Rad/Schwimmen)
        │
        ▼
1. Fitness-Snapshot (VDOT + Konfidenz + Evidenz)
        │
        ▼
2. Paces (E / M / T / I / R als Bänder)
        │
        ▼
3. Phasen (Base → Build → Peak → Taper), rückwärts vom Renndatum
        │
        ▼
4. Wochenvolumen + Long Run + Qualitätsanzahl
        │
        ▼
5. Tage belegen (Long Run, Qualität, locker; Abstände prüfen)
        │
        ▼
6. Einheiten aus der Bibliothek füllen
        │
        ▼
7. Guardrails prüfen (Rampe, Long-Run-Anteil, 48 h, Taper)
        │
        ▼
8. Vorschau → Freigabe → vorhandener Event-Schreibpfad
```

Der Kern ist deterministisch: gleiche Eingabe, gleicher Plan. Das ist die
Voraussetzung für Tests, Erklärbarkeit und Vertrauen.

### 4.2 Fitness: VDOT

VDOT ist Jack Daniels' Schätzung des VO₂max aus einer Rennleistung. Zwei
Formeln reichen:

```
VO₂(v) = -4,60 + 0,182258·v + 0,000104·v²        (v in m/min)

Anteil(t) = 0,8
          + 0,1894393·e^(-0,012778·t)
          + 0,2989558·e^(-0,1932605·t)            (t in min)

VDOT = VO₂(v) / Anteil(t)
```

Für eine Rennzeit: `v = Distanz / (Dauer in Minuten)`, `t = Dauer in
Minuten`; beide Formeln einsetzen. Für die Umkehrung („welche Zeit entspricht VDOT X auf Distanz Y?")
gibt es keine bequeme geschlossene Form; eine Bisektion über die Zeit ist
ausreichend und stabil.

**Warum VDOT und nicht Riegel allein?**

- VDOT liefert nicht nur Zeiten, sondern auch die Trainingszonen. Riegel liefert
  nur eine Zeitäquivalenz.
- VDOT ist gegen die Daniels-Tabelle prüfbar. Für VDOT 40 ergibt die Rechnung
  exakt die bekannten Werte: 5 km 24:06, 10 km 50:01, HM 1:50:54, Marathon
  3:49:37; E 6:14–6:53, M 5:29, T 5:05, I 4:41, R 4:24.
- Riegel bleibt als **zweite Meinung** nützlich, besonders für die Umrechnung
  zwischen Halbmarathon und Marathon.

**Grenzen von VDOT:**

- Es braucht eine echte, aktuelle Maximalleistung. Ein Easy Run ist keine.
- Kurze Distanzen (5 km) überschätzen die Ausdauer für den Marathon; lange
  Distanzen unterschätzen die 5-km-Fähigkeit.
- Hitze, Höhe, Trail und Wind verzerren die Äquivalenz. Ein Rennen bei 25 °C
  ist keine Laborleistung.
- Der VDOT ist ein Modell, kein Messwert. Deshalb: Konfidenz und Evidenz
  anzeigen, nicht eine Zahl als Wahrheit.

**Alternative, die wir nicht brauchen:** Critical Speed aus zwei Zeitfahrten.
Für einen Hobbysportler ist eine Rennzeit robuster und einfacher. Critical
Speed bleibt eine Option für später, wenn keine Rennzeit vorliegt.

### 4.3 Welche Daten zählen

| Quelle | Zählt als Pace-Signal? | Gewicht | Begründung |
|---|---|---|---|
| Rennen (5 km–HM) | ja | 1,0 | maximale, saubere Leistung |
| Time Trial (z. B. 5 km) | ja | 0,9 | kontrolliert, aber kein Rennstress |
| Qualitätseinheit (T-block ≥ 20 min) | ja, mit Abschlag | 0,6 | Training, kein Rennen: 3–5 % Zeitaufschlag |
| Intervall (I, ≥ 3 min) | ja, mit Abschlag | 0,6 | 1–2 % Zeitaufschlag |
| Renntempo-Block (≥ 3 km) | ja, mit Abschlag | 0,5 | je nach Länge |
| Easy Run | **nein** | — | zu variabel (Hitze, Untergrund, HF-Drift) |
| Long Run ohne Qualitätsblock | **nein** | — | kein Maximalreiz |
| RPE allein | **nein** | — | subjektiv, kein Leistungsmaß |

**Wichtig:** Ein Easy Run kann trotzdem ein Warnsignal sein. Wenn dieselbe Pace
bei 10 bpm höherer HF oder RPE 7 statt 3 liegt, ist das ein Erholungsproblem,
kein Fitnessgewinn. Das gehört in die Auto-Regulation, nicht in die
Pace-Berechnung.

### 4.4 Die Update-Regel

Das ist das Herzstück. Sie muss drei Dinge gleichzeitig leisten: Verbesserung
erkennen, Rauschen ignorieren, den Athleten nicht überraschen.

**Eingang:** aktueller VDOT (Prior), neue Signale, Datum, Phase.

**Regeln:**

1. **Nur frische Signale.** Maximal 90 Tage alt; Gewicht halbiert sich alle 28
   Tage.
2. **Nur Qualität.** Easy Runs und RPE-Läufe werden verworfen.
3. **Ein Signal reicht nicht.** Für eine Änderung braucht es mindestens zwei
   unabhängige Signale in dieselbe Richtung — oder ein Rennen.
4. **Robuster Median.** Der gewichtete Median der Signal-VDOTs verhindert, dass
   ein Ausreißer den Plan kippt.
5. **Schrumpfung zum Prior.** Der neue Wert wird zum alten Wert gezogen; ein
   guter Tag allein bewegt wenig.
6. **Deckel pro Update.** ±0,5 bis ±1,0 VDOT-Punkte, bei einem Rennen ±2,0.
   Das entspricht grob 5–15 s/km in der Easy-Pace.
7. **Mindestschwelle.** Erst ab etwa 0,3 VDOT-Punkten (rund 2–4 s/km) wird
   überhaupt ein Vorschlag gezeigt.
8. **Taper-Freeze.** In den letzten 10–14 Tagen vor dem A-Rennen wird nichts
   neu berechnet. Ein Pace-Update mitten im Taper ist Gift.
9. **Freigabe.** Der Vorschlag zeigt alt → neu, Evidenz und Begründung. Erst
   nach „Übernehmen" werden alle **zukünftigen** Paces neu berechnet; die
   laufende Woche und die Vergangenheit bleiben.
10. **Protokoll.** Jede Änderung wird mit Datum, Einheit, Distanz, Zeit,
    Quelle, altem und neuem VDOT gespeichert.

**Pseudocode:**

```
signals = frische_qualitaetssignale(letzte 90 Tage)
if phase == taper or phase == race_week:
    return keine_aenderung
if not signals:
    return keine_aenderung

race = any(s.source == "race" for s in signals)
if not race and len(signals) < 2:
    return keine_aenderung
# Zwei Signale reichen nur, wenn sie in dieselbe Richtung zeigen.
if not race and not gleiche_richtung(signals):
    return keine_aenderung

kandidaten = [vdot(s) for s in signals]
beobachtet = gewichteter_median(kandidaten, gewichte)
if prior is None:
    neu = beobachtet
else:
    neu = (prior * 1.5 + beobachtet * sum(gewichte)) / (1.5 + sum(gewichte))
    neu = clamp(neu, prior - max_step, prior + max_step)

if abs(neu - prior) < 0.3:
    return keine_aenderung

return vorschlag(alt=prior, neu=neu, evidenz=signals)
```

**Das Beispiel, das die Eingangsfrage beantwortet:**

- VDOT 34 → 37 (drei Punkte) verschiebt die Easy-Pace von 7:00–7:55 auf
  6:32–7:25, also rund 30 s/km nach unten. Die Schwelle geht von 5:47 auf 5:25
  (22 s/km), das Intervall von 5:20 auf 4:59 (21 s/km).
- Ein einzelner guter Tempolauf mit +2 VDOT reicht **nicht**. Erst wenn ein
  zweiter Qualitätsreiz oder ein Rennen dasselbe zeigt, entsteht ein Vorschlag.
- Läuft der Athlet Easy weiter bei 6:30, obwohl das Band 7:00–7:55 sagt, wird
  er **nicht** dafür belohnt. Das ist der Unterschied zwischen „schnell laufen"
  und „schneller geworden sein".

### 4.5 Paces: die Zonen

Die Zonen sind Anteile des VDOT. Die Tabelle ist gegen Daniels kalibriert; die
Bänder sind bewusst nicht breiter als nötig.

| Zone | Anteil VDOT | Kanonisch | Bedeutung |
|---|---|---|---|
| E (Easy) | 60–70 % | 65 % | locker, aerob, gesprächig |
| M (Marathon) | 78–82 % | 80 % | Marathon-Renntempo |
| T (Threshold) | 86–90 % | 88 % | Schwelle, „comfortably hard" |
| I (Interval) | 96–100 % | 97,5 % | VO₂max, 3–5 min |
| R (Repetition) | 104–108 % | 105 % | Schnelligkeit, 200–400 m |

Beispiele (min/km, schnell–langsam):

| VDOT | E | M | T | I | R |
|---|---|---|---|---|---|
| 34 | 7:00–7:55 | 6:15 | 5:47 | 5:20 | 5:02 |
| 37 | 6:32–7:25 | 5:50 | 5:25 | 4:59 | 4:42 |
| 40 | 6:14–6:53 | 5:29 | 5:05 | 4:41 | 4:24 |

**Regeln für die Anwendung:**

- **Easy** ist ein Band, kein Punkt. Der Athlet darf am langsamen Ende laufen.
  Die HF deckelt: etwa 75 % der Maximalfrequenz, sofern bekannt.
- **Tempo/Schwelle** wird als Zeit dosiert (20–40 min am Stück oder 3–4 ×
  8 min), nicht als Distanz. 20–40 min sind der Reiz; die Pace ist das
  Ergebnis.
- **Intervall** 3–5 min pro Wiederholung, 2 min Trabpause. Die Wiederholungen
  sollen gleich bleiben; die letzte nicht schneller als die erste.
- **Repetition** 200–400 m, volle Erholung. Kein Ausdauerreiz.
- **Renntempo** wird aus der aktuellen Leistung genommen, nicht aus der
  Zielzeit.
- **Runden:** Paces auf 5 s/km runden. Eine Sekunde ist im Gelände keine
  Information.
- **Hitze:** ab etwa 20 °C gefühlt 5–10 s/km langsamer oder HF-Deckel; die
  Pace ist dann eine Folge, nicht das Ziel.
- **Höhe/Trail:** VDOT aus einem flachen Rennen gilt nicht unverändert. Die
  Engine sollte einen Gelände-/Höhenfaktor kennen oder die Pace bewusst
  freigeben.

### 4.6 Zielzeit vs. aktuelle Leistung

Das ist die wichtigste Designentscheidung, und sie folgt Runna:

- **Der Plan trainiert die aktuelle Leistung.** Die Paces kommen aus dem
  aktuellen VDOT.
- **Die Zielzeit ist ein Ergebnis, keine Vorgabe.** Sie steht im Plan als
  „Ziel" und als Lücke, nicht als Pace-Ziel.
- **Wenn das Ziel mehr als 10 s/km schneller ist als die aktuelle Prognose**,
  zeigt die Engine einen Hinweis: „Ziel 5:36/km, aktuelle Prognose 6:02/km.
  Das Ziel ist 26 s/km schneller; der Plan trainiert auf die aktuelle Leistung.
  Entweder das Ziel anpassen oder den Aufbau verlängern."
- **Renntempo-Einheiten** laufen auf der aktuellen Renntempo-Pace. Erst wenn
  ein Rennen oder ein Time Trial die Fitness bestätigt, verschiebt sich das
  Ziel.
- **Am Renntag** darf der Athlet schneller starten, wenn die letzten Wochen
  besser liefen. Der Plan zwingt ihn nicht.

Das ist unbequem, aber ehrlich. Ein Plan, der eine Wunschzeit einprogrammiert,
produziert genau die Überlastung, die Runna vorgeworfen wird.

### 4.7 Periodisierung

Die Phasen werden **rückwärts** vom Renndatum gelegt. Die genauen Längen sind
eine Designentscheidung, keine Runna-Spezifikation.

| Phase | Halbmarathon | Marathon | 5/10 km | Fokus |
|---|---|---|---|---|
| Base | 4–6 Wochen | 6–8 | 3–4 | aerobe Basis, Sehnen, Laufökonomie, Steigerungen |
| Build | 4–5 | 6–8 | 3–4 | Schwelle und VO₂max, Umfang steigt |
| Peak | 2–3 | 3–4 | 1–2 | Renntempo, spezifische Blöcke, Umfang hält |
| Taper | 3 (2 bei kurzen Plänen) | 3 | 2 | Umfang runter, Intensität halten |

**Wochenvolumen:**

- Start = aktueller 4-Wochen-Schnitt, nicht der Wunsch.
- Steigerung maximal 8–10 % pro Woche; nach einer Pause 5 %.
- Jede vierte Woche Deload: −35 % Volumen, keine neue Intensität.
- Peak deckeln: HM 60–75 km, Marathon 80–95 km, 5/10 km 50–65 km — abhängig
  von Erfahrung und Vorgeschichte.
- Nach drei Aufbauwochen folgt eine leichtere; das ist die 3:1-Regel, die auch
  im Cockpit-Konzept steht.

**Long Run:**

- 25–35 % des Wochenumfangs, nicht mehr.
- HM: bis 16–17 km (75–80 % der Renndistanz); Marathon: bis 32–35 km;
  5/10 km: 12–16 km.
- Zeitdeckel: Marathon 3 h, HM 2 h, IM-Lauf 2–2,5 h.
- In Build/Peak einen Renntempo-Block einbauen (z. B. 2 × 5 km HM-Pace), aber
  nicht jede Woche.

**Qualität:**

- Base: 1 Reiz (Fartlek oder Steigerungen), keine harte Intervalleinheit.
- Build: 2 Reize, mindestens 48 h Abstand.
- Peak: 2 Reize, davon einer rennspezifisch.
- Taper: 1 kurzer Reiz, keine neue Intensität.
- Deload: höchstens 1 kurzer Fartlek.
- Bei 3 Läufen/Woche: maximal 1 Qualität; bei 2 Läufen: 0.

**80/20:**

- Nach Zeit, nicht nach Distanz.
- Locker (Z1–Z2) ≥ 80 %, moderat (Z3) < 10 %, hart (Z4–Z5) < 10 %.
- Bei 2–3 Läufen pro Woche ist 80/20 schwer erreichbar; dann gilt eher 60:40
  locker:hart — das ist auch Runnas öffentliche Leitlinie.
- Die Verteilung wird pro Woche geprüft, nicht pro Einheit.

**Taper:**

- HM und länger bzw. Pläne ab 10 Wochen: 3 Wochen; 10 km und kürzer:
  2 Wochen.
- Volumen −40 bis −60 %, Intensität bleibt (kurze Reps, kurze Renntempo-Blöcke).
- Letzter langer Lauf: 14–18 Tage vor dem Rennen.
- Keine neue Übung, keine neuen Schuhe, kein Krafttest.
- Rennwoche: Rennen, ein Shakeout mit Steigerungen, zwei lockere Läufe. Keine
  Qualität, kein Long Run.

**Ironman-Lauf (Ausnahme):**

- Kein Marathonplan. 3 Läufe/Woche, 30–45 km, langer Lauf 90–120 min.
- Ein Qualitätsreiz (Schwelle oder Renntempo), ein lockerer Lauf, ein
  Koppellauf nach dem Rad.
- Der Laufplan bekommt ein **Lastbudget** aus Rad und Schwimmen. Wenn die
  Radwoche hart ist, fällt zuerst die Laufqualität, nicht der lange Lauf.
- Peak nicht über 2–2,5 h, weil die Gesamtbelastung zählt.

### 4.8 Session-Bibliothek

Jede Einheit hat einen Zweck, eine Struktur und eine Pace-Zone. Die Bibliothek
ist klein und wiederholbar:

| Typ | Struktur | Zone | Zweck |
|---|---|---|---|
| Locker | 30–60 min am Stück | E | aerobe Basis, Erholung |
| Locker + Steigerungen | 40 min + 4 × 20 s | E/R | Laufökonomie, Beine wecken |
| Long Run | 60–150 min | E | Ausdauer, Fettstoffwechsel, psychische Härte |
| Long Run + Renntempo | 90–150 min, 20–35 min Renntempo | E + M/HM | spezifische Ermüdung |
| Fartlek | 15 min WU + 6 × 1 min flott/1 min locker + 10 min CD | E/I | Schnelligkeit ohne Druck |
| Tempolauf | 15 min WU + 20–40 min T + 10 min CD | E/T | Schwelle am Stück |
| Schwellenintervalle | 15 min WU + 3–4 × 8 min T (2 min TP) + 10 min CD | E/T | mehr Schwellenzeit |
| VO₂max-Intervalle | 15 min WU + 4–5 × 3 min I (2 min TP) + 10 min CD | E/I | VO₂max |
| Repetition | 15 min WU + 8 × 200 m R (200 m TP) + 10 min CD | E/R | Ökonomie, Schnelligkeit |
| Renntempo | 15 min WU + 2–3 × 3–5 km Renntempo (3 min TP) + 10 min CD | E/M | Renntempo üben |
| Shakeout | 20 min + 4 × 20 s | E/R | Beine wecken |
| Wettkampf | Renndistanz | Renntempo | Abliefern |

**Dosierung:** Qualität wird über Zeit dosiert, nicht über Distanz. Ein
Tempolauf ist 20–40 min T, egal ob die Woche 30 oder 50 km hat. Die Easy Runs
absorbieren die Differenz. Das ist physiologisch sinnvoller als „8 km Tempo",
weil 8 km bei einem schnellen Athleten 30 min und bei einem langsamen 50 min
bedeuten.

### 4.9 Auto-Regulation

Drei Ebenen, jede mit anderem Zeitmaß:

**Täglich (Erholung):**

| Erholung | Anpassung |
|---|---|
| ≥ 70 | Plan wie geplant |
| 50–69 | Intensität raus, Volumen −20 % |
| 35–49 | nur locker oder Ruhetag |
| < 35 / krank | Ruhetag, Einheit verschieben |

**Wöchentlich (Compliance):**

- Eine verpasste Easy-Einheit: ignorieren.
- Eine verpasste Qualität: nicht nachholen, nicht stapeln; die nächste Woche
  bleibt im Rahmen.
- Zwei verpasste Qualitäten oder eine ganze Woche: Realignment vorschlagen —
  Phasen verschieben, Renndatum halten, Volumen nicht nachholen.
- RPE auf Easy zwei Wochen > 5: Easy-Band langsamer oder Erholung prüfen.
- RPE auf Qualität zwei Wochen < 6 bei gleichzeitig niedriger HF: möglicher
  Fitnessgewinn, aber erst nach dem üblichen Signalverfahren.
- ACWR > 1,5: Warnung, kein automatischer Eingriff.

**Pace/Fitness (ereignisgetrieben):**

- Nur nach Qualitätseinheiten oder Rennen.
- Zwei Signale in dieselbe Richtung oder ein Rennen.
- Vorschlag, keine automatische Änderung.
- Taper-Freeze.

**Hitze:**

- Ab etwa 20 °C gefühlt: Pace 5–10 s/km langsamer oder HF-Deckel.
- Keine VDOT-Anpassung nach einem heißen Lauf; Hitze ist kein Fitnesssignal.

**Krankheit:**

- Nur oberhalb des Halses (Schnupfen): locker und kurz.
- Fieber, Husten, Brust: Pause, kein Plan.
- Nach Krankheit: Wiedereinstieg mit 50–70 % des letzten Umfangs, keine
  Qualität in der ersten Woche.

**Schmerz:**

- Schmerz, der beim Laufen schlimmer wird: aufhören.
- Schmerz, der nach dem Einlaufen verschwindet: beobachten, dokumentieren.
- Kein Algorithmus ersetzt eine Untersuchung.

### 4.10 Guardrails (hart)

Diese Regeln sind nicht verhandelbar. Wenn eine Einheit sie verletzt, wird sie
gekürzt oder gestrichen — nicht der Guardrail.

- Wochenvolumen +≤ 10 % gegenüber der letzten normalen Woche; nach Pause +≤ 5 %.
- Long Run ≤ 35 % des Wochenumfangs und ≤ Zeitdeckel.
- Maximal 2 Qualitätseinheiten, ≥ 48 h Abstand.
- Keine Qualität an aufeinanderfolgenden Tagen.
- Deload jede 4. Woche, −35 %.
- Taper −40 bis −60 %, Intensität halten, kein neuer Reiz.
- Keine Qualität bei Erholung < 50.
- Keine neue Intensität in der Rennwoche.
- Schmerz, der schlimmer wird: stoppen.
- Keine Planänderung ohne Freigabe.

---

## 5. Datenmodell und Schnittstellen

Heute hat das Cockpit `activity`, `event`, `wellness`, `setting` und den
Planer-Schreibpfad (`planner/serializer.py`, `planner/event_write.py`). Der
Laufplaner braucht vier zusätzliche Konzepte, muss aber nicht sofort neue
Tabellen anlegen.

**Vorschlag für die persistente Form:**

```sql
plan(id, goal_id, created_at, status, engine_version, input_json)
plan_week(id, plan_id, week_index, start_date, phase, is_deload,
          target_km, long_run_km, quality_sessions)
plan_session(id, plan_week_id, date, kind, name, purpose,
             structure_json, distance_m, duration_s,
             pace_low_s, pace_high_s, event_id, status)
fitness_snapshot(id, date, vdot, confidence, source, evidence_json)
fitness_signal(id, date, source, distance_m, time_s, vdot,
               weight, activity_id, note)
```

**Minimalvariante:** Plan als JSON in `setting` speichern, nur die freigegebenen
Einheiten als `event`. Das reicht für einen Prototyp, verliert aber die
Versionierung und die Evidenz. Für „Planung" ist die JSON-Variante okay; für
den Betrieb sind Tabellen besser.

**API-Skizze (nicht gebaut):**

| Endpunkt | Zweck | Schreibt? |
|---|---|---|
| `POST /api/planning/preview` | Plan aus Eingaben erzeugen | nein |
| `GET /api/planning/fitness` | VDOT, Konfidenz, Paces, Evidenz | nein |
| `POST /api/planning/fitness/accept` | Pace-Update übernehmen | nein (nur Snapshot) |
| `POST /api/planning/apply` | freigegebenen Plan als Events schreiben | ja, über `event_write` |
| `GET /api/planning/plan/{id}` | Plan lesen | nein |
| `POST /api/planning/adapt` | Wochenanpassung vorschlagen | nein |

**Anbindung an den vorhandenen Planer:**

- Der Generator erzeugt `PlannedWorkout`-Strukturen, keine rohen Dicts.
- Der vorhandene `serializer.prepare_write` erzeugt den Workout-Text.
- `EventWriteService` schreibt und liest zurück; `external_id` bleibt
  `tc:<woche>:<datum>:<session>:<rev>`.
- Die Oberfläche zeigt den Plan als „Vorschlag", bis er freigegeben ist.
- Kein zweiter Schreibpfad, keine neue Remote-Logik.

**CLI-Skizze:**

```
tc plan preview --goal HM --date 2026-11-21 --vdot 34 --days 4 --json
tc plan apply --file plan.json          # später, nur nach Freigabe
tc fitness                              # VDOT, Paces, Evidenz
```

---

## 6. Integration in die PWA

Die App ist eine React/Vite-PWA mit FastAPI und SQLite; der Planer schreibt
Events nach intervals.icu. Der Laufplaner sollte **kein neuer Tab** sein,
sondern eine Erweiterung des Planers. Sonst wächst die Navigation, ohne dass
eine neue Aufgabe entsteht.

**Nutzerfluss:**

1. Im Planer: „Plan erstellen".
2. Assistent (Blatt): Zielrennen aus der Config, Datum, aktuelle Wettkampfzeit
   (oder „keine — Time Trial vorschlagen"), aktueller Wochenumfang, Tage,
   Long-Run-Tag, Einschränkungen (Reise, Hitze, Krankheit).
3. Vorschau: 4 Wochen, Wochenumfang, Schlüsseleinheiten, Paces, Hinweise
   (Ziel-Lücke, Planlänge, Konfidenz).
4. Freigeben: Diff anzeigen, „Übernehmen" schreibt die Events.
5. Im Alltag: „Heute" zeigt die Einheit mit Pace; eine kleine Karte zeigt VDOT
   und die letzte Aktualisierung.
6. Nach einer Qualitätseinheit: Banner „Pace-Update verfügbar"; Tippen öffnet
   ein Blatt mit alt → neu und Evidenz.
7. Wochenrückblick: Compliance, verpasste Einheiten, ein Vorschlag.

**Komponenten (Vorschlag, nicht gebaut):**

- `PlanWizard.tsx` — Eingaben, Validierung.
- `PlanPreview.tsx` — Wochenliste, Summen, Hinweise.
- `FitnessCard.tsx` — VDOT, Paces, Konfidenz; klein, auf „Heute" oder im
  Planer.
- `PaceUpdateSheet.tsx` — alt/neu, Evidenz, Übernehmen.
- `PlanDiff.tsx` — was sich ändert, bevor geschrieben wird.

**Design:**

- `DESIGN.md` gilt. Dunkle Fläche, ein Akzent, Sentence case, 4-px-Raster.
- Keine neue Chart-Bibliothek. Wochenbalken und Pace-Bänder mit den
  vorhandenen Komponenten.
- Keine Sparkline in der Fitness-Karte; eine Zahl, ein Satz, ein Link.
- Der Plan ist ein Vorschlag, kein Zustand. „Vorschlag" muss sichtbar sein.

**Rollout:**

| Stufe | Inhalt | Schreibt? |
|---|---|---|
| 0 | CLI/Notebook, Pläne für vergangene Rennen nachrechnen | nein |
| 1 | `preview`-Endpunkt + Assistent, nur Anzeige | nein |
| 2 | Freigabe + Schreiben über `event_write`, Testkalender | ja, nach Klick |
| 3 | Auto-Regulation als Vorschlag, Wochenrückblick | nein |
| 4 | Ironman-Lastbudget, Koppelläufe, Multi-Sport | später |

**Abnahme:** Erst wenn Stufe 1 vier Wochen lang mit echten Daten plausibel
aussieht, wird Stufe 2 gebaut. Kein Big Bang.

---

## 7. DeepSeek API

Der DeepSeek-Zugang ist nützlich — aber nicht für die Zahlen. Die Trennung ist
dieselbe wie bei Runna und im Cockpit (D3):

- **Regelkern:** VDOT, Paces, Periodisierung, Volumen, Guardrails. Python,
  deterministisch, testbar.
- **LLM:** Sprache, Absicht, Zusammenfassung. Keine Pace-Berechnung, keine
  Planänderung, kein Schreiben.

### 7.1 Wofür DeepSeek gut ist

1. **Einheit erklären.** „Warum 3 × 8 min Schwelle und nicht 5 × 5 min?" —
   aus einem JSON mit Einheit, Phase, Pace, Athletenkontext. Zwei bis drei
   Sätze, keine erfundenen Zahlen.
2. **Absicht parsen.** „Ich kann Dienstag nicht, verschiebe den Tempolauf auf
   Mittwoch" → JSON `{action: "move", session_id, to: "2026-11-11"}`. Die
   Engine validiert und führt aus.
3. **Wochenrückblick.** Compliance, verpasste Einheiten, ein Vorschlag. Der
   Vorschlag wird von der Engine geprüft, nicht vom LLM.
4. **Onboarding-Dialog.** Fehlende Angaben erfragen (aktueller Test, Tage,
   Long-Run-Tag), Antworten strukturiert speichern.
5. **Plan-Diff erklären.** „Diese Woche 42 km statt 38, weil der Long Run
   wächst; die Qualität bleibt gleich."

### 7.2 Wofür DeepSeek nicht gut ist

- Pace aus einer Zielzeit rechnen.
- VDOT schätzen oder Updaten.
- Periodisierung, Volumen, Taper entscheiden.
- Den Plan direkt schreiben.
- Medizinische Diagnosen oder Verletzungsrat.
- Rohdaten aus HRV, Schlaf, Gesundheitsdaten interpretieren.

### 7.3 Technik

- OpenAI-kompatible API: `https://api.deepseek.com`, Modell `deepseek-chat`
  (V3) für Text und Intent, `deepseek-reasoner` (R1) nur für schwierige
  Erklärungen.
- `response_format={"type": "json_object"}` für strukturierte Aufgaben.
- Key in `.env` als `DEEPSEEK_API_KEY`, `chmod 600`, nie im Repo.
- Timeout 10–20 s, ein Retry, dann deterministischer Fallback-Text.
- Token-Logging, aber keine Rohdaten in den Logs.
- Kosten: Eine Erklärung sind wenige hundert Token; das ist im Betrieb
  vernachlässigbar. Der Aufwand liegt in der Validierung, nicht im Preis.

### 7.4 Guardrails

- **Fakten-JSON statt Prosa:** Das LLM bekommt nur die Zahlen, die es verwenden
  darf. Der Systemprompt sagt: „Du bist Erklärer, nicht Rechner. Verwende
  ausschließlich die Zahlen aus dem JSON. Wenn eine Zahl fehlt, sage das."
- **Schema-Validierung:** Antwort als JSON mit festem Schema; bei Verstoß
  verwerfen und neu versuchen.
- **Zahlen-Check:** Jede Zahl im Text muss im Fakten-JSON vorkommen; sonst
  Antwort ablehnen.
- **Aktions-Whitelist:** Nur `move`, `skip`, `shorten`, `swap`, `explain`.
  Alles andere wird abgelehnt.
- **Keine Schreibrechte:** Das LLM bekommt keinen Datenbank- oder
  intervals-Zugriff. Es liefert Text oder eine Absicht; die Engine handelt.
- **Datenschutz:** Nur aggregierte Trainingsdaten (Distanz, Pace, Phase,
  Erholungsband), keine Roh-HRV, kein Schlaf, keine Gesundheitsdiagnosen.
- **Offline-Fallback:** Ohne Key funktioniert der Planer mit Vorlagen.

### 7.5 Beispiel: Systemprompt

```
Du bist der Coach-Text des Trainings-Cockpits. Du erklärst eine geplante
Einheit. Du rechnest nicht. Du verwendest ausschließlich die Zahlen aus dem
JSON. Wenn eine Zahl fehlt, sagst du das. Antworte auf Deutsch, in zwei bis
drei Sätzen, ohne Werbung, ohne Ausrufezeichen.

JSON: {"session": {...}, "phase": "build", "athlete": {...}}
```

### 7.6 Beispiel: Intent-Schema

```json
{
  "action": "move",
  "session_id": "2026-11-10-tempo",
  "to": "2026-11-11",
  "reason": "Dienstag beruflich verhindert"
}
```

Die Engine prüft: Ist die Einheit vorhanden? Ist der Zieltag frei? Bleibt der
48-h-Abstand? Ist es dieselbe Woche? Wenn nein, wird der Vorschlag abgelehnt
und erklärt.

---

## 8. Durchgerechnet: Nicholas

Die folgenden Zahlen sind aus dem Vault und der Cockpit-Datenbank, nicht
erfunden. Sie zeigen, wo der Algorithmus hakt — und warum die Planung vor der
Umsetzung richtig ist.

### 8.1 Die Evidenz ist widersprüchlich

| Quelle | Zeit | VDOT | HM-Prognose |
|---|---|---|---|
| 5 km | 27:50 | 33,7 | 2:07 |
| 10 km | 58:19 | 33,4 | 2:08 |
| Halbmarathon | 2:23:12 | 29,5 | 2:23 |
| Runna-Prognose | 1:58 | 37,2 | 1:58 |
| Garmin-Prognose | 2:10 | ~33,2 | 2:10 |

Die 5-km- und 10-km-Zeiten passen zueinander (VDOT 33,4–33,7). Der
Halbmarathon von 2:23:12 fällt deutlich heraus (VDOT 29,5) — entweder ist er
alt, kein Maximalversuch, oder die Bedingungen waren schlecht. Runna sagt
1:58, also VDOT 37,2; das sind 3,5 Punkte über den 5-/10-km-Werten. Das ist
möglich, wenn die Bestzeiten älter sind und die Fitness seitdem gestiegen ist.
Es ist nicht möglich, wenn die 5-km-Zeit aktuell ist: 1:58 ist fast dasselbe
Tempo wie 27:50 auf 5 km — das hält man nicht über 21 km.

**Die wichtigste offene Frage ist deshalb nicht der Algorithmus, sondern das
Datum der Bestzeiten.** Ohne aktuellen Test ist jede Pace-Rechnung eine
Extrapolation.

### 8.2 Was die Trainingsdaten sagen

Die letzten Läufe (aus der Cockpit-DB):

- 31.10.: 17,0 km in 1:52 → 6:34/km, HF 151.
- 02.11.: 10,1 km in 69 min → 6:50/km, HF 147.
- 28.10.: 8,1 km „Tempo" in 51 min → 6:18/km, HF 151.

Das sind lockere bis moderate Pace. Für VDOT 34 liegt das Easy-Band bei
7:00–7:55; 6:34 ist schneller als das schnelle Ende. Für VDOT 37 liegt das
Band bei 6:32–7:25; 6:34 ist gerade am schnellen Rand. Das ist ein Hinweis
darauf, dass entweder die Fitness über VDOT 34 liegt oder die Easy Runs zu
schnell gelaufen werden. Die HF von 147–151 bei 6:34–6:50 spricht eher für
„kontrolliert moderat" als für „hart"; ohne Maximalpuls ist die Einordnung
aber unsicher.

### 8.3 Der Halbmarathon am 21.11.2026

Der Plan für die letzten zwei Wochen ist **kein Aufbauplan**, sondern ein
Taper:

- Woche 1: Volumen −30 bis −40 %, ein kurzer Renntempo-Block (2 × 2 km),
  sonst locker.
- Woche 2: Renntempo nur als Shakeout, keine Qualität, kein Long Run.
- Rennen: Zielpace aus der aktuellen Leistung, nicht aus 1:58.

Die Rechnung sagt aus den 5-/10-km-Zeiten 2:07–2:08; Runna sagt 1:58. Beides
sind Modelle, keine Messungen; die Wahrheit steht am 21.11. auf der Straße.
Der Plan sollte **keine** 1:58-Pace einprogrammieren, sondern die aktuelle Pace
als Grundlage nehmen und das Ziel als Kür markieren. Nach dem Rennen ist der
VDOT-Prior sauber kalibriert.

### 8.4 Ironman 2027

Der Ironman-Lauf ist kein Marathonplan. Für Kärnten 2027:

- 3 Läufe/Woche, 30–45 km, langer Lauf 90–120 min.
- Ein Qualitätsreiz (Schwelle oder Renntempo), ein lockerer Lauf, ein
  Koppellauf nach dem Rad.
- Peak 2–2,5 h, kein 32-km-Long-Run.
- Der Laufplan bekommt ein Lastbudget aus Rad und Schwimmen; in harten
  Radwochen fällt die Laufqualität, nicht der lange Lauf.
- Der laufspezifische Block beginnt etwa 24 Wochen vor dem Rennen, nicht
  jetzt. Bis dahin: Basis, Kraft, Technik.

### 8.5 Was der Algorithmus daraus lernt

- **Nicht** aus einem einzelnen Long Run auf die Fitness schließen.
- **Nicht** die undatierten Bestzeiten als aktuell behandeln.
- **Ja** den Halbmarathon als Kalibrierungsrennen nutzen.
- **Ja** die Easy-Pace-Deckelung ernst nehmen: 6:34 bei VDOT 34 ist zu schnell,
  auch wenn es sich gut anfühlt.
- **Ja** die Zielzeit von der Trainingspace trennen.

---

## 9. Test- und Abnahmestrategie

Ein Planer, der Zahlen produziert, muss beweisen, dass die Zahlen stimmen.

**Unit-Tests:**

- VDOT-Formel gegen bekannte Daniels-Punkte (VDOT 40 → 5 km 24:06, 10 km
  50:01, HM 1:50:54, M 3:49:37).
- Paces monoton: E > M > T > I > R (langsamer nach schneller).
- Phasenlängen summieren sich zur Gesamtwoche.
- Volumenrampe ≤ 10 %, Deload −35 %, Taper −40 bis −60 %.
- Long Run ≤ 35 %, Qualität ≤ 2, ≥ 48 h Abstand.
- Race Week enthält das Rennen, keine Qualität, keinen Long Run.
- Keine Einheit vor dem Start oder nach dem Rennen.
- Update-Regel: ein Signal ändert nichts; zwei Signale ändern; ein Rennen
  ändert; Taper friert ein.

**Golden Plans:**

- 16 Wochen Halbmarathon, VDOT 40, 4 Tage.
- 20 Wochen Marathon, VDOT 45, 5 Tage.
- 12 Wochen 10 km, VDOT 35, 3 Tage.
- 2 Wochen Taper, VDOT 34, 4 Tage.
- 8 Wochen Halbmarathon (zu kurz) → Warnung, gestauchte Phasen.

**Property-Tests:**

- Für jede Woche: `target_km` innerhalb [10, peak].
- Für jede Einheit: Dauer > 0, Distanz > 0.
- Für jeden Plan: Renndatum enthalten, Summe der Wochen > 0.
- Für jede Pace: `low <= high`.

**Shadow Mode:**

- Für ein vergangenes Rennen einen Plan erzeugen und mit dem tatsächlichen
  Training (Runna/Bevel/intervals) vergleichen — nur lesen, nichts schreiben.
- Abweichungen erklären: Warum war Runna schneller/langsamer, warum mehr/weniger
  Umfang?

**Menschliche Abnahme:**

- Vier Wochen Vorschau, keine Schreibzugriffe.
- Ein Testkalender in intervals.icu, ausdrücklich freigegeben.
- Erst dann Produktion.

---

## 10. Offene Entscheidungen

Diese Punkte sind **Vorschläge**, nicht beschlossen. Sie gehören in
`docs/ENTSCHEIDUNGEN.md`, sobald die Planung steht.

| Vorschlag | Inhalt |
|---|---|
| D-82 | Laufplaner bleibt vorerst Planung; kein Code in `develop`, kein UI. |
| D-83 | Paces kommen aus der aktuellen Leistung, nicht aus der Zielzeit. |
| D-84 | Regelkern deterministisch; DeepSeek nur für Text und Absicht. |
| D-85 | Pace-Updates nur aus Qualitätseinheiten, zwei Signale, Freigabe. |
| D-86 | Plan ist ein Vorschlag; Schreiben nur über den vorhandenen Event-Pfad. |
| D-87 | Ironman-Laufplan bekommt ein Lastbudget, keine Insel. |

**Offene Fragen an den Athleten:**

1. Wann wurden 5 km (27:50) und 10 km (58:19) gelaufen? Sind das aktuelle
   Bestzeiten oder alte?
2. Gibt es einen aktuellen Time Trial außer dem Halbmarathon am 21.11.?
3. Maximalpuls: liegt er vor? Ohne ihn bleibt die HF ein grober Deckel.
4. Welche Tage und wie viele Läufe pro Woche sind realistisch?
5. Welcher Tag ist der Long-Run-Tag?
6. Wie viele Läufe pro Woche soll der Ironman-Block haben, und an welchen Tagen
   liegen Rad/Schwimmen?
7. Soll der Plan in der App gespeichert werden, oder reichen die Events in
   intervals.icu?
8. Soll DeepSeek überhaupt eingesetzt werden, oder erstmal nur Vorlagen?

---

## 11. Quellen

**Runna (öffentlich, Help-Center und Presse):**

- Kein Zielzeit-Feature: [Adjusting your estimated race time and pace targets](https://support.runna.com/en/articles/6205998-adjusting-your-estimated-race-time-and-pace-targets)
- Aktuelle Fitness als Referenz: [How Runna builds your plan around your current fitness](https://support.runna.com/en/articles/15231838-how-does-runna-build-your-training-plan-around-your-current-fitness)
- Pace-Anker, Tempo vs. Intervall: [What's the difference between a tempo and interval session](https://support.runna.com/en/articles/13848642-what-s-the-difference-between-a-tempo-and-interval-running-session)
- Pace Insights: [What are Pace Insight recommendations and how do they work](https://support.runna.com/en/articles/10854865-what-are-pace-insight-recommendations-and-how-do-they-work)
- Plan Realignment: [How to use the Plan Realignment feature](https://support.runna.com/en/articles/10026375-how-to-use-the-plan-realignment-feature)
- „Not Feeling 100%": [Adjusting your plan around minor aches and pains](https://support.runna.com/en/articles/13225357-adjusting-your-plan-around-minor-aches-and-pains)
- Holiday Mode: [How to adjust your plan around holidays](https://support.runna.com/en/articles/10225691-how-to-adjust-your-plan-around-holidays)
- Hitze: [How does Runna adapt my workouts for heat and humidity](https://support.runna.com/en/articles/15647483-how-does-runna-adapt-my-workouts-for-heat-and-humidity)
- Taper: [How does Runna build recovery into your training plan](https://support.runna.com/en/articles/15272605-how-does-runna-build-recovery-into-your-training-plan)
- Planlängen und Minima: [How to create a training plan in Runna](https://support.runna.com/en/articles/15443877-how-to-create-a-training-plan-in-runna)
- 80/20: [80/20 training principle](https://support.runna.com/en/articles/9551650-80-20-training-principle)
- Long Runs: [Understanding the long runs in your Runna plan](https://support.runna.com/en/articles/9357249-understanding-the-long-runs-in-your-runna-plan)
- Mileage: [How Runna calculates your mileage](https://support.runna.com/en/articles/14666572-how-runna-calculates-your-mileage-and-how-to-adjust-it)
- RPE: [What is RPE](https://support.runna.com/en/articles/6967043-what-is-rpe)
- Workout Insights: [What are Workout Insights](https://support.runna.com/en/articles/10494265-what-are-workout-insights)
- Workout Briefings: [What are Workout Briefings](https://support.runna.com/en/articles/13169751-what-are-workout-briefings)
- „We don't use AI to generate training plans": [Runner's World — Runna app review](https://www.runnersworld.com/training/a69110486/runna-app-review-i-tried-it/)
- Kritik: [futurezone](https://futurezone.at/apps/runna-lauf-app-hobbysportler-training-verletzung-ueberbelastung/403129952),
  [the5krunner (Archiv)](http://web.archive.org/web/20260221182456/https://the5krunner.com/2026/02/21/runna-ai-marathon-training-injury/)

Nicht selbst geprüft und deshalb nur als Link: der dedizierte Artikel
[How to use Not Feeling 100%](https://support.runna.com/en/articles/13531498-how-to-use-not-feeling-100).
Reddit, Trustpilot und marathonhandbook waren aus dem Recherchenetz nicht
erreichbar; die Kritik stützt sich auf Presse und Fachseiten, nicht auf eine
systematische Nutzerbefragung.

**Trainingslehre:**

- Daniels, J. *Daniels' Running Formula.* 4. Auflage. Human Kinetics, 2021.
  (VDOT, E/M/T/I/R, Formeln.)
- Riegel, P. S. „Athletic records and human endurance." *American Scientist*
  69.3 (1981): 285–290.
- Bosquet, L., Montpetit, J., Arvisais, D., Mujika, I. „Effects of tapering on
  performance: a meta-analysis." *Medicine & Science in Sports & Exercise*
  39.8 (2007): 1358–1365.
- Seiler, S. „What is best practice for training intensity and duration
  distribution in endurance athletes?" *International Journal of Sports
  Physiology and Performance* 5.3 (2010): 276–291.
- Gabbett, T. J. „The training-injury prevention paradox: should athletes be
  training smarter and harder?" *British Journal of Sports Medicine* 50.5
  (2016): 273–280.
- Kiviniemi, A. M., Hautala, A. J., Kinnunen, H., Tulppo, M. P. „Endurance
  training guided individually by daily heart rate variability measurements."
  *European Journal of Applied Physiology* 101.6 (2007): 743–751.
- Plews, D. J., Laursen, P. B., Stanley, J., Kilding, A. E., Buchheit, M.
  „Training adaptation and heart rate variability in elite endurance athletes:
  opening the door to effective monitoring." *Sports Medicine* 43.9 (2013):
  773–781.
- Fitzgerald, M. *80/20 Running.* New American Library, 2014.
- Friel, J. *The Triathlete's Training Bible.* 3. Auflage. VeloPress, 2009.

**Eigene Daten:**

- `Sport-Gehirn/profil.md` (Bestzeiten, Zonen, Ziel).
- `Sport-Gehirn/rennen/rennen-ironman-kaernten-2027.md`,
  `rennen-halbmarathon-2026.md`.
- `trainings-cockpit/data/cockpit.db` (Aktivitäten, Wellness; nur aggregiert
  gelesen).

---

## 12. Was als Nächstes zu tun ist

1. **Entscheiden, ob überhaupt gebaut wird.** Die Planung ist bewusst kein
   Auftrag.
2. **Die offenen Fragen beantworten** (Datum der Bestzeiten, Max-HF, Tage,
   Long-Run-Tag, Ironman-Laufumfang).
3. **Den 21.11. als Kalibrierung nutzen.** Danach steht ein belastbarer VDOT.
4. **Erst dann** einen Prototyp außerhalb der App bauen (Notebook/CLI), mit
   Golden Tests und Shadow Mode.
5. **Erst danach** über API, UI und Schreiben nach intervals.icu sprechen.

Bis dahin gilt: Dieses Dokument ist die Grundlage, nicht der Plan.
