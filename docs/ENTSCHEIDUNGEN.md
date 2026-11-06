# Projekt- und Entscheidungslog

**Zweck:** Dieses Dokument ist die einzige Grundlage für Änderungen am Cockpit.
Erst diskutieren und hier festhalten, dann implementieren.

**Stand:** 31.10.2026

---

## 1. Arbeitsweise

1. **Erkenntnisse** werden mit Datum und Quelle als `E-xx` ergänzt. Sie sind
   beobachtet, nicht beschlossen.
2. **Offene Fragen** laufen als `F-xx` mit Optionen und einer Empfehlung.
3. Eine **Entscheidung** wird als `D-xx` festgehalten, sobald wir sie besprochen
   haben – mit Datum, Begründung und Konsequenz.
4. **Implementiert wird nur, was als `D-xx` entschieden ist.** Jede Änderung
   verweist auf die Entscheidung, aus der sie stammt.
5. Widersprüche werden nicht stillschweigend aufgelöst, sondern als neue Frage
   aufgenommen.

---

## 2. Erkenntnisse

### E-01 · Datenlage ist tragfähig (30.10.2026)

- 283 Aktivitäten von 08.01. bis 29.10.2026, 366 Wellness-Tage, 47 Kalender-Events.
- Quellen der Aktivitäten: OAUTH_CLIENT 137, Garmin 123, Wahoo 19, Zepp 4.
- Wellness: HRV 365/366, Ruhepuls 366/366, Schlaf 365/366.
- Garmin direkt: 85 Aktivitäten in 90 Tagen, FIT-Download ok, 91 Schlaf-Nächte,
  nur 3 HRV-Nächte (Uhr wird nachts nicht getragen).
- **Folge:** Erholung kommt von der Helio über Zepp, Aktivitäten sind breit verteilt.

### E-02 · Der 21-h-Plan liegt nicht in intervals.icu (30.10.2026)

- In intervals stehen 41 Workouts bis **22.11.2026**, Peak **9,5 h / 539 Load**
  (KW 46), danach Taper auf 8,4 h.
- Für 2027 ist dort nichts hinterlegt.
- Der 21-h-Peak kommt aus **Bevel**. Wir kennen weder Struktur noch Verlauf.
- **Folge:** Nicht blind übernehmen und nicht gegen einen unbekannten Plan bauen.

### E-03 · Belastung beeinflusst die Tagesform nur schwach (30.10.2026)

- Heute: Score **69** bei Frische **−14**, HRV **+9 %**, Ruhepuls **−3**, Schlaf **7,8 h**.
- Die Last hat nur 15 % Gewicht, deshalb bleibt der Score trotz negativer Frische hoch.

### E-04 · Datenqualität braucht Regeln (30.10.2026)

- HRV **255** am 09.10. (Sentinel) verzerrte Baseline und Score; wird jetzt gefiltert.
- Ruhepuls-Baseline **64** bei aktuellem Wert **57** – möglicher Quellenmix
  (Zepp/Garmin) oder unterschiedliche Definition.
- Gewicht nur an 48 von 366 Tagen; Zepp liefert kein Gewicht.
- Schlaftiefe/REM liegen in intervals nicht als Felder vor.
- **Folge:** Quellenpriorität und Plausibilitätsgrenzen müssen explizit entschieden werden.

### E-05 · Garmin-Direktzugriff funktioniert, ist aber noch nicht im Sync (30.10.2026)

- Personal API liefert Aktivitäten, FIT, Schlaf, HRV und Gewicht.
- Die App liest Aktivitäten aktuell **nur über intervals.icu**.
- Risiko: intervals.icu darf Garmin-Daten voraussichtlich bald nicht mehr ausliefern.

### E-06 · UI-Stand (30.10.2026)

- Live: **Heute**, **Trends**, **Aktivitäten**, mobil, Dark, Sync-Knopf, ein Countdown.
- Fehlt u. a.: Wochen-/Planansicht, Check-in, Plan-vs-Ist, Schlafphasen,
  Kraft-Details, Datenqualitäts-Hinweise, Export.

### E-07 · Saison 2027 ist eng (30.10.2026)

- VCM 18.04.2027 (B), IRONMAN Kärnten 13.06.2027 (A), Wörthersee 26.09.2027 (A-).
- Nur **8 Wochen** zwischen VCM und Ironman; drei Ziele in acht Monaten.
- Aktuell Fitness ≈ 53, 8-Wochen-Schnitt 7,6 h/Woche, stärkste Woche 11,8 h.

### E-08 · Der Score war nicht nachvollziehbar (30.10.2026)

- Unter „Readiness“ standen **7-Tage-Mittel** (HRV 32 ms, Ruhepuls 61), in den
  Karten daneben der **letzte Nachtwert** (39 ms, 57) – ohne Kennzeichnung.
- Der Score 69 war damit nicht erklärbar, obwohl beide Zahlen korrekt waren.
- Ursache: Das Modell rechnete mit 7-Tage-Mitteln, die Anzeige zeigte sie aber
  wie Tageswerte.

### E-09 · intervals-Fachbegriffe sind für den Nutzer bedeutungslos (30.10.2026)

- CTL, ATL, TSB, ACWR und „Load“ sind nicht verständlich.
- intervals.icu wird nur als Datenschnittstelle und Kalender genutzt.
- **Folge:** Die UI muss deutsche Begriffe und kurze Erklärungen verwenden.

### E-10 · Mobile und Homeserver (30.10.2026)

- Das Dashboard soll auf dem iPhone genutzt werden, idealerweise als App auf
  dem Home-Bildschirm.
- Ein 24/7-Homeserver ist vorhanden; dort soll es dauerhaft laufen.

### E-11 · Countdowns sind ein Kernmotivator (30.10.2026)

- Der Ironman-Countdown gefällt; gewünscht sind zusätzlich VCM und der
  Halbmarathon am 21.11.2026.

### E-12 · Atmung ist vorhanden, aber noch dünn (30.10.2026)

- `respiration` liegt an **27 von 366 Tagen** vor, davon täglich seit 30.09.2026.
- Ein Ausreißer am 26.10. mit **20,71** (plausibel 8–20) verzerrt Mittel und Streuung.
- Heute 11,11 gegen einen 30-Tage-Schnitt von 13,7 – ein klarer Ausschlag nach unten.
- **Folge:** Atmung nur bedingt gewichten (max. 5 %) und bei fehlenden Daten renormieren.

### E-14 · Bevel-Logik als Referenz (30.10.2026)

Bevel beschreibt seine Erholung so:

- Sechs Nachtsignale: Schlafwert, HRV, Ruhepuls, Atemfrequenz, SpO₂, Temperatur.
- HRV und Ruhepuls werden gegen den **eigenen 60-Tage-Durchschnitt** bewertet.
- Atemfrequenz zieht leicht nach oben oder unten; niedriges SpO₂ oder erhöhte
  Temperatur können nur nach unten ziehen.
- **Training fließt nicht direkt ein.** Belastung wirkt über die nächste Nacht
  (HRV, Ruhepuls, Schlaf). Heute 94 % („Excellent“).

### E-15 · Drei der sechs Signale fehlen uns (30.10.2026)

| Signal | Abdeckung | Anmerkung |
|---|---|---|
| HRV, Ruhepuls, Schlafdauer, Schlafscore | 30/30 Tage | vollständig |
| Atemfrequenz | 27 Tage, täglich seit 30.09. | dünn, aber aktuell |
| SpO₂ | 26/30 Tage | 99 % heute, unauffällig |
| Temperatur | **keine Daten** | `tempRestingHR`/`tempWeight` sind nur Flags |
| Schlafscore | 73 (Zepp) vs. 86 (Bevel) | Bevel rechnet seinen eigenen Score |

### E-17 · Garmin CIRQA Smart Band als Schlafquelle (30.10.2026)

- Displayloses Armband (kein Ring), **199,99 €**, bis 10 Tage Akku, Garmin Connect.
- Laut Produktseite: fortgeschrittene Schlafanalyse, Schlafcoach, Schlafrhythmus,
  Erkennung veränderter Atemmuster, Nickerchen, **HRV-Status**, **Hauttemperatur**,
  Atemfrequenz, SpO₂, Ruhepuls, Body Battery, Stress.
- Kernfunktionen ohne Abo; einzelne Coaching-Funktionen brauchen Garmin Connect+.
- **Entscheidend:** Es ist ein Garmin-Gerät. Die Daten landen in Garmin Connect,
  und genau dort holt unser Sync sie ab – inklusive Schlafphasen, die wir bei den
  drei vorhandenen Garmin-Nächten schon gesehen haben.
- **Offen:** ob die Personal API auch die Hauttemperatur ausgibt (eigener Endpunkt,
  nicht im offiziellen Client-Wrapper). Test mit einer Nacht genügt.

### E-16 · Zepp hat keine persönliche API (30.10.2026)

- **Kein Selbstbedienungs-Key** wie bei Garmin. Es gibt die **Zepp Open Platform**
  (server-seitiges OAuth, Webhooks, FIT-Dateien). Laut Partner-Dokumentation
  liefert sie Schlaf **mit Phasen** (deep/light/REM/awake), Schlafscore und
  nächtliche HRV – aber keine Tageszusammenfassungen wie Schritte oder RHR.
- Zugang ist für Apps/Unternehmen gedacht, nicht für einzelne Athleten.
- intervals.icu nutzt diesen Partnerzugang, reicht aber aktuell nur **Dauer und
  Score** weiter – keine Phasen.
- Daneben existieren **reverse-engineered** Zugänge (z. B. Vitalera: „Huami does
  not publish a developer API“, Endpunkte können sich jederzeit ändern).
  Sie brauchen Zepp-Zugangsdaten und sind für ein 24/7-System nicht tragfähig.
- Der Zepp-Score ist zudem nicht stabil: dieselbe Nacht 84 → 73.

### E-13 · Die Skala war der Grund für die Abweichung zu Bevel (30.10.2026)

- Bisher galt: Baseline = **50** Punkte, +1 SD ≈ 81, −1 SD ≈ 19.
- Ein völlig normaler Tag landete damit bei 50–60, obwohl er sich „normal“ anfühlt.
- Mit den gewünschten Änderungen (Schlafziel 7:30, Last 10 %, Atmung 10 %,
  30-Tage-Referenz) kommt heute **81,9** heraus – nicht 90–95.
- Mit einer kalibrierten Skala (Baseline = 65, ±1 SD = ±20) und
  Last 5 % / Atmung 5 % kommt heute **89,9** heraus, 30-Tage-Schnitt 75,4.
- Bevel gab heute 100; empfunden wurden 90–95.

### E-18 · Datenweg über Health Sync, Ziel Geräteunabhängigkeit (31.10.2026)

- **Neu:** Health Sync schickt Garmin- **und** Apple-Health-Daten nach
  intervals.icu. Der Schlafimport von intervals.icu ist abgeschaltet, damit
  nicht zwei Wege dieselbe Nacht schreiben. Erster Lauf: ab 01.11.2026.
- **Ziel des Athleten:** unabhängig von der Marke bleiben. Coros oder ein
  anderes Gerät muss später genauso funktionieren – ohne Umbau.
- **Folge für die Architektur:** Das Cockpit liest ausschließlich über
  intervals.icu und kennt keine Gerätemarke. Keine gerätespezifischen
  Sonderwege, kein Vendor-Score als Grundlage einer Kennzahl.
- **Risiko Doppelquelle:** Liefern Garmin und Apple Health dieselbe Nacht,
  kann ein Tag überschrieben werden. Prüfpunkt nach dem ersten Sync: ein Tag,
  drei Werte (Geräte-App, intervals.icu, Cockpit) müssen übereinstimmen.
- **Risiko Schlafscore:** Fällt der Zepp-Score weg, rechnet der Schlaf-Treiber
  nur mit der Dauer. Der Code kann das schon (`metrics.py` fällt darauf
  zurück), der Score verschiebt sich dadurch aber leicht nach unten. Zu
  beobachten, nicht zu korrigieren, solange die Datenlage wechselt.

### E-19 · felsr-Verpflegungsplaner als Referenz (31.10.2026)

Quelle: <https://felsr.com/verpflegung> (Rechenkern als offenes Skript).

- **Kohlenhydrate hängen an der Dauer, nicht am Gewicht.** Die Grenze sitzt in
  der Darmwand (SGLT1 ≈ 60 g/h Glukose, GLUT5 ≈ 30 g/h Fruktose), nicht in der
  Muskelmasse. Gewicht zählt nur für Vortag, Frühstück und danach.
- **Bänder nach Dauer** (Gramm je Stunde): < 45 min 0 · 45–75 min 22 ·
  75–120 min 45 · 2–3 h 60 · 3–4 h 75 · > 4 h 82. Empfohlen wird die **Mitte**
  des Bandes, nicht das obere Ende.
- **Deckel 90 g/h**, ab 60 g/h nur noch als Glukose-Fruktose-Mischung.
- **Trinken nie über der Schweissrate** (Hyponatriämie), Salz erst ab ~2 h.
- **Was wir übernehmen:** die Bänder, den Deckel, die Aufteilung
  Getränk/Gels, Konzentration ≤ 8 %, Wasser und Salz.
- **Was wir bewusst weglassen:** Sportart, Höhenmeter, Watt, Höhenprofil,
  Lebensmittel-Suchbaum, Tagesplanung. Das gehört in die Trainingsplanung.

### E-20 · Vor dem Sync fehlt die Nacht von heute (31.10.2026)

- intervals.icu legt den Wellness-Eintrag eines Tages erst an, wenn die Daten
  da sind. Morgens um 08:00 ist die Zeile von heute also noch leer.
- Folge im Cockpit: Der Erholungsring fiel auf den letzten Wert zurück und
  zeigte Zahlen, die Karten daneben zeigten „—“.
- Zusätzlich rechnete das Schlafdefizit die fehlende Nacht als **0 h Schlaf**
  und kam auf 7,7 h statt 0,2 h.
- Mit dem Wechsel auf Health Sync (E-18) wird das häufiger auftreten, nicht
  seltener.

### E-21 · Ahornsirup ist die eigentliche Quelle (31.10.2026)

- Der Athlet nimmt **Ahornsirup**, nicht Gels: **65,3 g Kohlenhydrate je 100 g**.
  Mit der Dichte von rund **1,33 g/ml** sind 100 ml etwa **87 g Kohlenhydrate**
  – vier Gels in einer Flasche.
- Ahornsirup ist überwiegend Saccharose. Die wird im Darm in Glukose und
  Fruktose gespalten, ungefähr 1:1 – damit sind **beide Transportwege** bedient
  und auch 90 g/h grundsätzlich erreichbar.
- Praktische Größe: **50 ml Shot = 66 g Sirup = 43 g Kohlenhydrate**, also rund
  zwei Gels. Ein 25-ml-Shot entspricht einem Gel.
- Salz rechnet die Küche in **Kochsalz**, die Literatur in **Natrium**:
  1 g Natrium ≈ **2,54 g Salz**. Aus 600 mg Natrium je Stunde werden 1,5 g Salz.
- Sirup ist konzentriert und zieht Wasser in den Darm – zu jedem Shot gehören
  ein paar Schluck Wasser.

### E-22 · Erster Praxistest: 73 g Kohlenhydrate für 17 km (31.10.2026)

- Lauf: **17 km in 1:51** (111 min), gefahren mit **73 g Kohlenhydraten**,
  das sind **112 g Sirup** oder **84 ml** – und es hat gut funktioniert.
- Das sind **39,5 g/h**, also runde 40 g/h.
- Das Modell sagte für dieselbe Einheit 35 g/h (65 g, 100 g Sirup, 75 ml).
  Die Abweichung liegt innerhalb der ausgewiesenen Spanne (30–40 g/h), aber
  am oberen Rand – und der Praxistest ist die bessere Quelle.
- Ein Datenpunkt ist kein Gesetz. Er verschiebt den Faktor für „Locker“ von
  0,75 auf 0,90; bei 2 h sind das 55 statt 45 g/h, bei 4 h 75 statt 60 g/h.

### E-23 · Milliliter und Gramm sind am Sirup nicht dasselbe (31.10.2026)

- Die Portion wurde in **ml** abgefragt. Wer 35 eingibt, meint aber seinen
  gewogenen Shot: **35 g Sirup**.
- 35 g sind bei 65,3 g Kohlenhydraten je 100 g genau **22,9 g Kohlenhydrate**.
- 35 **ml** sind dagegen 46,6 g Sirup und damit **30,4 g Kohlenhydrate** – die
  Zahl, die die Seite zeigte. Rechnerisch richtig, aber an der falschen Frage.
- Rund 12 % Unterschied, und niemand sieht es der Zahl an, weil beide „35“
  heißen.

### E-24 · Der Score war zu träge (31.10.2026)

- Nacht vom 31.10.: HRV **39 → 29 ms**, Ruhepuls **57 → 62**, Schlaf **7:59 → 6:36 h**,
  Schlafscore 71. Das Cockpit gab **73** („gut erholt“) und rutschte damit in die
  grüne Ampel. Bevel gab **51 %**, was dem Empfinden entsprach.
- Ursache sind drei Glättungen hintereinander:
  1. **60-Tage-Referenz.** Der Sommer mit anderem Rhythmus zog den Maßstab mit.
     „Üblich“ lag bei 30 ms HRV und 62,8 bpm – da ist ein Wert von 29/62 normal.
  2. **Tageswert 60 %, Wochenschnitt 40 %.** Der schlechte Tag wurde durch die
     gute Woche halbiert.
  3. **Gewichtetes Mittel.** Vier Teilscores zwischen 67 und 80 ergeben
     zwangsläufig 73; kein einzelnes Signal kann den Score wirklich senken.
- Nachgerechnet: Mit 21-Tage-Referenz, vollem Tageswert und 25 Punkten je
  Standardabweichung ergibt dieselbe Nacht **65**. Der 26.10. (HRV 22, RHR 73)
  fällt von 65 auf **40**.
- **Ehrlich dazu:** Bevels 51 lässt sich aus HRV, Ruhepuls, Schlaf und Atmung
  nicht reproduzieren. In der Durchrechnung kommt selbst die schärfste
  Kombination nicht unter 59, ohne gute Tage zu zerstören. Bevel hat
  Hauttemperatur und Schlafphasen, wir nicht.

### E-25 · intervals.icu hat keine Schlafphasen (31.10.2026)

- Geprüft im Wellness-Objekt der API (`GET /api/v1/athlete/0/wellness`) am
  Beispieltag 31.10.: Felder sind `sleepSecs`, `sleepScore`, `sleepQuality`
  (1–4), `avgSleepingHR` (leer), `hrv`, `hrvSDNN`, `restingHR`, `respiration`,
  `spO2`, `steps`, `weight`, `bodyFat`.
- In der API-Beschreibung kommen **`deepSleep`, `remSleep`, `sleepStart` und
  `temperature` kein einziges Mal vor**; es gibt auch keinen `/sleep`-Endpunkt.
- Das ist keine Momentaufnahme, sondern die Struktur: intervals.icu speichert
  Schlaf nur als **Dauer, Score und grobe Qualität**. Phasen, Wachzeiten,
  Einschlafzeit und Hauttemperatur haben dort keinen Platz.
- Phasen entstehen schon bei der Quelle: die **Garmin Personal API** liefert
  `deepSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds` sowie Start und
  Ende – unser Client liest das bereits. Bei 91 abgerufenen Nächten hatten aber
  nur 3 echte Phasen, weil die Uhr nachts nicht getragen wird.
- **Health Sync kann die Lücke nicht schließen:** Was intervals nicht speichern
  kann, kommt dort auch nicht an. Phasen brauchen einen direkten Weg von Garmin
  (oder einem Gerät, das sie nach Garmin Connect schreibt).

### E-26 · Bevel-Abgleich als Kalibrierquelle (31.10.2026)

- Zwei gemeinsame Punkte reichen nicht zum Justieren: 30.10. lagen wir bei 93
  (Bevel ~94), 31.10. bei 65 (Bevel 51). Auf der guten Seite stimmt es, auf der
  schlechten nicht.
- Bei zwei Punkten ist jede Anpassung Raten. Mit sieben Paaren lässt sich die
  Abweichung rechnen statt schätzen.
- Der eigene Score wird deshalb von Hand eingetragen (Feld auf „Heute“) und in
  `wellness.readiness_vendor` gespeichert – die Spalte war unbenutzt, weil
  intervals für diesen Athleten kein `readiness` liefert.
- Nebenbei beobachtet: Ein Sync um 18:12 schrieb `sleepScore` als NULL, obwohl
  intervals um 19:02 wieder 71 lieferte. Der Upsert überschreibt mit NULL; ein
  erneuter Sync korrigiert es. `readiness_vendor` ist dagegen per COALESCE
  geschützt, damit der eingetragene Wert einen Sync überlebt.
- **hrvSDNN wird nicht verwendet:** an 18 von 61 Tagen fehlt der Wert, und der
  Athlet hat dafür keine verlässliche Quelle. Ein Signal, das manchmal da ist,
  macht den Score unvergleichbar.

### E-27 · Dieselbe Einheit kommt doppelt an (31.10.2026)

- Der Vault-Import schrieb 295 Einheiten. In den Wochen standen **8 davon doppelt**,
  zusammen **124 km**, also rund 5 % des Jahres.
- Ursache: dieselbe Aufzeichnung kommt über zwei Wege in intervals.icu — von
  Garmin Connect und von Health Sync, gelegentlich zusätzlich von Wahoo oder
  Zepp. Unterschiedliche IDs, gleicher Verlauf.
- Genau das war das Risiko aus E-18 beim Umstieg. Es trifft jetzt beide Seiten:
  den Vault und die Datenbank.
- **Erkennung über den Verlauf, nicht über die ID:** gleiche Sportart, Start
  innerhalb von fünf Minuten, Dauer ± 2 min, Distanz ± 400 m. Der Startzeitpunkt
  ist der scharfe Filter: zwei Atemübungen am selben Tag um 05:47 und 22:32 sind
  zwei Einheiten, auch wenn beide 5,5 Minuten dauern.
- Bei Gleichstand bleibt Garmin Connect, weil die Uhr Höhenmeter und Puls selbst
  misst. Danach entscheidet die vollständigere, dann die längere Aufzeichnung.
- Nach der Bereinigung: 287 Einheiten, Woche 44 statt 15 nur noch 12 Einheiten
  und 48,9 statt 69,5 Rad-Kilometer.

### E-28 · Der Vault doppelte die Datenbank (31.10.2026)

- Nach dem Import lagen 287 Einheiten-Notizen und 43 Wochen-Notizen im Vault —
  1,1 MB, die es in der Cockpit-Datenbank schon gab, nur älter.
- Für jede Zahl hätte der Vault gepflegt werden müssen; ohne Syncthing vom
  Server aus war das nur von Hand möglich.
- Was die Datenbank **nicht** kann: Ziele, Zielzeiten, Rennergebnisse,
  Beschwerden, was geholfen hat, Coaching-Regeln, die Worte des Athleten.
- Folge: Der Vault behält die Urteils-Ebene, die Zahlen bleiben im Cockpit.

### E-29 · Die Oberfläche liest sich als Vorlage, nicht als Werkzeug (01.11.2026)

Prüfung der drei Seiten gegen die Slop-Liste von *unslop* (Screenshots in
`data/screens/audit-*.png`):

- **Flächen:** zwei Radial-Washes im Seitenhintergrund (grün und blau); jede der
  vier Kennzahlenkarten hat ihren eigenen Farbschein (violett, blau, orange,
  türkis); Aktiv-Modus und Navigationszeile tragen Verlauf mit Glühen; der
  Regler ist ein Grünverlauf; Notizkasten mit farbigem Linksbalken.
- **Kennzahlen:** alle vier Karten haben eine Sparkline — genau das, was eine
  Karte zur Dekoration macht. Die Zahl ist nicht mehr das Größte.
- **Schrift:** 20 verschiedene Größen, Großbuchstaben-Labels mit weitem
  Abstand auf jeder Seite (`VERPFLEGUNG`, `DAUER`, `WORAUS`, `GETRÄNK`,
  `BELASTUNG` in jeder Zeile der Aktivitätenliste), Fettungen bis 700.
- **Icons:** die Sportart-Icons tragen fünf verschiedene Farbtöne, jede Einheit
  eine andere Farbe.
- **Text:** Begrüßung als Überschrift („Servus, Nicholas"), Untertitel im
  Plauderton („Was die andere App sagt – sieben Tage reichen zum Justieren").
- **Abstände:** elf Werte außerhalb des 4-px-Rasters (18, 22, 26, 15, 11, 9, 7,
  6, 5), Karten mit unterschiedlichem Innenabstand.
- **Aktivitäten:** 287 Zeilen in einer Liste, 18.900 px hoch, ohne Gruppierung;
  „BELASTUNG" wiederholt sich in jeder Zeile.
- **Diagramm:** drei Farbtöne (grün, amber, grau) mit Flächenverläufen, zwei
  davon konkurrieren um die Aufmerksamkeit; keine Hierarchie.
- **Vorlagenprobe:** dunkelgrau, Mintgrün, Inter, Karten mit Schein — das könnte
  jede Fitness-App sein. Es sagt nichts über Kärnten, Ironman oder Morgenlicht.

### E-30 · Vier Quellen, eine Tür (01.11.2026)

Stand der Rohdaten in der Datenbank (287 Einheiten, 01.11.2026):

| Quelle in `activity.raw` | Einheiten | Gerät |
|---|---|---|
| Health Sync (`OAUTH_CLIENT`) | 139 | Health Sync |
| Garmin Connect | 125 | fenix 7 Pro, Venu Sq |
| Wahoo | 19 | WAHOO_FITNESS App |
| Zepp / Amazfit | 4 | Helio Strap, Watch |
| Rouvy, Sufferfest | 5 | virtuelle Ausfahrten |

- **Last liegt für alle 287 Einheiten vor**, auch für die 42 Kraft-Einheiten
  (Ø 28). Krafttraining fällt also nicht aus Fitness und Müdigkeit heraus.
- **Wellness, letzte 60 Tage:** HRV 60 von 61, Ruhepuls 61, Schlaf 60,
  Schlafscore 59, **Atmung nur 27**. Komplette Nächte: **27 von 61**.
  Nach D-26 heißt das: an 34 Tagen entsteht kein Erholungswert — nicht weil die
  Nacht schlecht war, sondern weil die Atmung fehlt.
- **Dubletten:** keine offenen (`tc dedupe --dry-run` sauber). Die Erkennung
  hängt am Verlauf, nicht an der Quelle: Garmin Connect schlägt Health Sync,
  bei Gleichstand entscheidet die Zahl der Felder, dann die Dauer.

Die Konsequenz: Ein Band, das jede Nacht HRV, Ruhepuls, Schlaf **und Atmung**
liefert, ist die eigentliche Lücke. Fehlt die Atmung weiter, ändert das Band an
der Trefferquote nichts.

### E-31 · Garmin filtert, was bei intervals ankommt (01.11.2026)

Seit Ende September 2026 schickt Garmin Partnern nicht mehr die Datei, die das
Gerät aufgezeichnet hat: die Aufzeichnung bleibt, Garmins eigene Kennzahlen
(Training Effect, Recovery Time, VO₂max, Stamina, Performance Condition) fehlen.
Der offizielle Wellness-Sync liefert außerdem **kein `respiration`** — genau das
Feld, an dem bei uns 34 von 61 Nächten scheitern (E-30).

Ein Selbstbau-Projekt löst beides über Garmins Personal API und schreibt die
fehlenden Wellness-Werte nach intervals
([garmin-intervals-bridge](https://github.com/futureweb/garmin-intervals-bridge)).
Für uns zählt: die Lücke ist bekannt, sie liegt bei Garmin und nicht bei uns —
und sie ist über die Personal API schließbar, für die im Cockpit schon ein
Client liegt (`sources/garmin.py`).

### E-32 · Die Startseite zeigte Messung, nicht Vorhaben (01.11.2026)

Der Athlet öffnet das Cockpit morgens mit einer Frage: *was steht heute an?* Die
Startseite antwortete mit Frische, einem 90-Tage-Diagramm und der Liste der
letzten Einheiten — alles Rückblick. Das Vorhaben lag zwei Bildschirme weiter
unten als „Geplant“ in einer Nebenspalte, und der Plan selbst (Schritte,
Leistungsbereiche, Verpflegung) war im Cockpit gar nicht zu sehen.

Der Plan liegt vollständig in intervals.icu: 47 Ereignisse, je mit
`moving_time`, `icu_training_load`, `description` und `workout_doc` (Schritte mit
Leistung, HF-Bereich oder Distanz, dazu `zoneTimes`). Er wird beim Sync schon
abgerufen und weggeworfen. Es fehlt also keine Quelle, nur die Anzeige.

### E-33 · Garmin zieht die Grenze zwischen Lesen und Schreiben (01.11.2026)

Am 9. Oktober 2026 schrieb der Betreiber von intervals.icu in seinem Forum, Garmin
habe die Bedingungen im Entwicklerportal geändert, ohne Ankündigung; „It is likely
that we will have to block access to Garmin data via the API soon". Drei Tage
später stellte Intervals Pro, ein Coaching-Dienst auf Basis von intervals.icu,
den Betrieb ein ([watchesreviewed](https://watchesreviewed.com/garmin-api-terms-third-party-apps/)).

Der Kern ist **Ziffer 5.1(o)** des Garmin-Connect-Developer-Program-Agreement:
kein eigener API-Zugang, über den ein Lizenznehmer **Endnutzerdaten an Dritte**
weitergibt, die Garmin nicht schriftlich freigegeben hat. Der Wortlaut ist seit
2023 unverändert — neu ist, dass Garmin ihn durchsetzt. Damit ist die Kette
„Garmin → intervals.icu → fremde App" gemeint: genau der Weg, über den das
Cockpit seine Läufe und Schwimmeinheiten bis D-33 aus intervals geholt hat.

Was das **nicht** berührt, ist die Gegenrichtung. Ein Workout, das intervals an
Garmin schickt, ist kein Garmin-Datenabfluss an Dritte — deshalb laufen die
geplanten Einheiten weiter auf die Uhr, auch während activities und wellness
über intervals versiegen. Selbst hochgeladene FIT-Dateien sind nach Einschätzung
von intervals ebenfalls unkritisch, weil sie nicht über die Partner-API kamen.

Am 21. Oktober 2026 hat Garmin das Programm wieder geöffnet, in drei Stufen
([DC Rainmaker](https://www.dcrainmaker.com/2026/10/garmin-connect-api-revamps-connect-developer.html),
[Momentum](https://www.themomentum.ai/blog/garmin-connect-developer-program-reopens)):

- **Personal** — eigene Daten lesen, Key in Sekunden, keine Schreibrechte
  (das ist unser Zugang, D-33).
- **Starter** — bis 1.000 Nutzer, kostenlos, Freigabe praktisch sofort, und
  darin enthalten: **Courses & Training API**, also Routen und strukturierte
  Workouts auf Garmin-Geräte schieben.
- **Enterprise** — Historie, Support, mehr als 1.000 Nutzer, kostenpflichtig:
  1.000 Dollar Einstieg (auf die Nutzungsrechnung angerechnet), Preis je aktivem
  Nutzer, **Abrechnung ab 1. April 2027**. Bestehende Partner rutschen ohne
  Einstiegsgebühr automatisch hinein.

Dazu kommt die zweite Baustelle, die wir schon in E-31 gemessen haben: seit Ende
September 2026 filtert Garmin eigene Kennzahlen aus den FIT-Dateien, die es
Partnern gibt (Stamina, Recovery Time, VO₂max, Performance Condition, Training
Effect, Sweat Loss).

Für uns heißt das: **kein Enddatum für den Workout-Versand.** Es gibt kein
Datum, an dem intervals keine Workouts mehr senden darf; das einzige Datum im
Raum ist der 1. April 2027, ab dem Garmin von Partnern Geld je aktivem Nutzer
verlangt. intervals.icu ist ein Ein-Mann-Projekt mit Spendenmodell — ob es sich
das leisten will, ist die eigentliche offene Frage, nicht die Technik. Ein
eigener **Starter**-Zugang (kostenlos, 1.000 Nutzer, Training API) wäre die
Versicherung: dann schiebt das Cockpit selbst, ohne intervals dazwischen.

---

### E-34 · Der Athlet sah die Doppelte, das Cockpit nicht (02.11.2026)

Bevel zeigte für die letzten sieben Tage andere Stunden als das Cockpit. Der
Verdacht des Athleten war präzise: **die Long Ride vom 1. November liegt zweimal
in der Datenbank.**

| Aufzeichnung | Start | bewegt | gesamt | Strecke | Last |
|---|---|---|---|---|---|
| `i204257493` „Long Ride" (WAHOO) | 08:05:03 | 9.796 s | 10.007 s | 73,7 km | 154 |
| `i204634552` „Morning Virtual Ride" (Health Sync) | 08:05:03 | 7.320 s | 10.007 s | 77,0 km | 112 |

Dieselbe Uhr, dieselbe Aufzeichnung, zwei Wege in intervals. Die Regel aus D-23
verlangt **Dauer ± 2 min und Distanz ± 400 m** — hier weichen beide ab (41
Minuten, 3,4 km), also blieb das Paar stehen. Die Wochenkarte zählte 15,1 statt
13,1 Stunden.

Der zweite blinde Fleck liegt quer über die Quellen: 18 Einheiten liegen als
intervals- **und** als Garmin-Aufzeichnung vor (April bis Oktober, vor allem
Schwimmen). Dort stimmt die Strecke, aber die Bewegungszeit nicht — Garmin zieht
Pausen anders ab (23.10.: 2.050 m, 3.024 s gegen 2.542 s). Auch das fiel durch.

- Was beim Wiederveröffentlichen **gleich bleibt**, ist die Uhr der Aufzeichnung:
  `elapsed_time` steht in beiden Zeilen der Long Ride auf 10.007 s. Bewegungszeit
  und Strecke rechnet jede Plattform neu, die Gesamtzeit nicht.
- Die Erkennung braucht deshalb zwei Wege statt einer Und-Verknüpfung: gleicher
  Start **und** (gleiche Gesamtzeit **oder** gleiche Strecke bei ähnlicher Dauer).
- Der Athlet liest die Zahl am Telefon. Eine Stunde zu viel ist schlimmer als eine
  fehlende, weil sie eine ganze Woche falsch aussehen lässt.

---

## 3. Entscheidungen

| ID | Datum | Entscheidung | Begründung | Konsequenz |
|---|---|---|---|---|
| D-01 | 30.10.2026 | **Bevel wird schrittweise abgelöst** (Option B). Bevel bleibt vorerst Planungsquelle, das Cockpit liefert Analyse und Vergleich. | Kein Bruch mitten in der Saison; wir lernen erst, was Bevel macht. | Plan-vs-Ist und Vergleich werden ausgebaut, bevor eigene Pläne kommen. |
| D-02 | 30.10.2026 | **Kernnutzen:** Erholung, Plan vs. Ist, eigene Planung, Langzeitentwicklung – plus **Wirkungsanalyse** (welche Einheiten bringen etwas, welche ersetzen). | Der Nutzer will nicht nur Zahlen, sondern Entscheidungen. | Wirkungsanalyse wird eigene Etappe (nicht Teil der UI-Klarheit). |
| D-03 | 30.10.2026 | **„Readiness“ heißt künftig „Erholung“ (Recovery).** Der Wert beschreibt, wie gut der Körper heute erholt ist. | Der alte Begriff war mehrdeutig. | API, UI und Texte werden umbenannt. |
| D-04 | 30.10.2026 | **Erholung nutzt Ruhepuls, HRV, Schlaf und zu einem Teil die Belastung.** Farben und Ampel bleiben. | Entspricht dem körperlichen Empfinden; die Farben funktionieren. | Modell bleibt viergeteilt, Gewichte werden sichtbar. |
| D-05 | 30.10.2026 | **Jede Erholungsanzeige erklärt sich in einem Satz.** Tageswert, 7-Tage-Schnitt und Baseline werden getrennt ausgewiesen. | Der Score muss ohne Fachwissen nachvollziehbar sein. | Erklärungstext + drei Zahlen pro Treiber. |
| D-06 | 30.10.2026 | **Keine intervals-Fachbegriffe in der UI.** Übersetzung: CTL = **Fitness**, ATL = **Müdigkeit**, TSB = **Frische**, ACWR = **Belastungsverhältnis**, Load = **Belastung**. | Nutzer kennt die Begriffe nicht und will sie nicht lernen. | Alle Labels und Legenden werden ersetzt, mit kurzer Erklärung. |
| D-07 | 30.10.2026 | **Drei Countdowns:** Ironman 13.06.2027, VCM 18.04.2027, Halbmarathon 21.11.2026. | Countdown motiviert und ordnet die Saison. | Ziele werden konfigurierbar, nicht hart im Code. |
| D-08 | 30.10.2026 | **Mobile-first für iPhone als Home-Screen-App (PWA)**, Betrieb auf dem 24/7-Homeserver per Docker. | Nutzung findet oft am Handy statt. | Manifest, Apple-Icons, Installationsanleitung, Docker-Deployment. |
| D-09 | 30.10.2026 | **Nächste UI-Bausteine nach der Klarheit:** Morgen-Check-in, Schlafdetails, Datenqualität. | Diese drei wurden als nächste Priorität genannt. | Etappe 3. |
| D-10 | 30.10.2026 | **Recovery-Modell:** Tageswert 60 %, 7-Tage-Schnitt 40 %. | Die letzte Nacht soll zählen, aber nicht jede Schwankung den Score kippen. | Sichtbar als „Heute / Schnitt / Baseline“. |
| D-11 | 30.10.2026 | **Check-in + zweiter Wert „Gefühl“** (Modell und Empfinden getrennt). | Der Nutzer will beides sehen. | Etappe 3, nicht Teil der jetzigen Änderung. |
| D-12 | 30.10.2026 | **Erholung nach Bevel-Logik (P1):** HRV 35 %, Ruhepuls 20 %, Schlaf 30 % (50 % Dauer gegen 7:30 h, 50 % Schlafscore), Atmung 5 %, SpO₂ 5 % (nur Abzug), **keine Belastung im Score**, 60-Tage-Referenz, Skala `68 + 20·z`. Temperatur fehlt und wird renormiert. | Trifft Bevel (94) und das Empfinden (90–95); Bevels Logik ist nachvollziehbar. | Belastung wirkt nur über die nächste Nacht; die UI erklärt das. |
| D-13 | 31.10.2026 | **Der Tab „Trends“ entfällt vorerst.** Die Seite bleibt im Code liegen, wird aber nicht mehr verlinkt. | Viele Kennzahlen werden aktuell nicht gebraucht; jede zusätzliche Seite kostet Pflege. | Navigation: Heute · Verpflegung · Aktivitäten. Rückkehr ist ein Einzeiler. |
| D-14 | 31.10.2026 | **Verpflegungsrechner mit zwei Modi:** „Locker“ (Long Run, Zone 2) und „Wettkampf“. Kohlenhydrate je Stunde aus dem Dauerband × Faktor (0,75 bzw. 1,10), Deckel 90 g/h, ab 60 g/h Warnung auf Mischung. Ausgabe: g/h, Gesamtmenge, Getränk, Gels, Wasser, Salz, Zeitplan, Drumherum. | Zwei Modi decken den Alltag ab; mehr Regler verwässern die Antwort auf „wie viel nehme ich mit“. | Eigene Seite im Cockpit, Rechnung im Backend (`fuel.py`), testbar. |
| D-15 | 31.10.2026 | **Fehlt die Nacht von heute, zeigt das Cockpit den letzten Stand** statt „—“: Karten, Ring und Erklärung nutzen dieselbe Nacht. Im Kopf steht dann „Nacht vom 30. Oktober“. Das Schlafdefizit zählt nur vorhandene Nächte. | Ein leerer Bildschirm neben einem vollen Ring ist ein Widerspruch; eine fehlende Nacht ist keine schlaflose Nacht. | Neues Feld `as_of` in `/api/overview`, Fallback auf den letzten Wert mit Daten. |
| D-16 | 31.10.2026 | **Der Rechner kennt zwei Quellen:** „Gels & Pulver“ (Getränk plus Gels) und **„Ahornsirup“** (Sirup-Shots plus Wasser). Bei Sirup kommen alle Kohlenhydrate aus den Shots, die Flasche trägt nur Wasser. Die Shotgröße ist einstellbar (Standard 50 ml). Ausgegeben wird Sirup in ml und g, Kohlenhydrate je Shot und **Salz je Shot in Gramm**. | Der Athlet mischt selbst; Gramm Kohlenhydrate helfen ihm nicht, Milliliter Sirup und Gramm Salz schon. | Neue Felder `syrup` und `sources`, Salz zusätzlich in Gramm. |
| D-17 | 31.10.2026 | **Wasser steht nicht im Verpflegungsplan.** Der Athlet trinkt Wasser ohne Kohlenhydrate und nimmt den Sirup als Gel-Ersatz. Der Zeitplan enthält deshalb nur die Shots; Wasser bleibt als Menge und Hinweis stehen. Passt die gewählte Shotgröße schlecht zur Stundenmenge, schlägt die Seite eine passendere vor („Mit 25-ml-Shots passt es besser: 3 Shots à 22 g statt 1 à 43 g“). | Ein Zeitplan, in dem „Flasche 1“ zwischen den Shots steht, ist eine Anweisung, die niemand befolgt. Und eine einzelne 43-g-Portion für einen Lauf von 1:51 ist keine Lösung, sondern eine Rundung. | `_schedule` ohne Wasser, Feld `syrup.suggestion`. |
| D-18 | 31.10.2026 | **„Locker“ wird auf Faktor 0,90 kalibriert** (vorher 0,75): 40 g/h bei 90 min, 55 bei 2 h, 75 bei 4 h. Anlass ist der erste Praxistest (E-22): 73 g in 1:51 traf 40 g/h, nicht 35. | Der eigene Lauf schlägt die Literatur, solange keine Gegenbeispiele vorliegen. | Bei 1:51 sagt der Rechner jetzt 75 g und 85 ml Sirup statt 65 g und 75 ml. Rücknahme ist eine Zahl. |
| D-19 | 31.10.2026 | **Die Shotgröße hat eine Einheit:** Gramm (Standard) oder Milliliter, umschaltbar. Angezeigt wird immer die gewählte Einheit, gerechnet wird in Millilitern (Dichte 1,33 g/ml). Die Kohlenhydrate pro Portion stehen zusätzlich in Gramm. | Wer den Sirup wiegt, denkt in Gramm; wer ihn in eine Flasche füllt, in Millilitern. Die Einheit darf nicht geraten werden müssen. | Feld `unit`, `shot_g`, `amount`; Standard 35 g. |
| D-20 | 31.10.2026 | **Erholung reagiert jetzt auf die Nacht:** Referenz **21 Tage** statt 60, **Tageswert zählt voll** (kein 40-%-Wochenschnitt mehr in der Rechnung), Skala `68 + 25·z` statt `68 + 20·z`. Schlaf wird nicht mehr durch das 7-Tage-Mittel gerettet. | Ein guter Monat darf eine schlechte Nacht nicht verdecken; der Score soll dem Befinden folgen. | Heute 73 → 65, 26.10. 65 → 40, gute Nächte bleiben bei 92–94. Die Lücke zu Bevel (51) bleibt und braucht Temperatur oder Check-in. |
| D-21 | 31.10.2026 | **hrvSDNN fliegt raus.** Nur HRV (rMSSD) zählt. | Keine verlässliche Quelle, 18 von 61 Tagen leer. | Kein Schema-Umbau, keine neue Kennzahl. |
| D-22 | 31.10.2026 | **Bevel-Abgleich im Cockpit:** Auf „Heute“ wird Bevels Score eingetragen, das Cockpit zeigt beide Zahlen und die Differenz. Nach sieben Tagen wird das Modell an den Paaren kalibriert. | Die zweite App ist der einzige verfügbare Maßstab; raten auf einen Punkt wäre schlechter. | Neue Karte auf „Heute“, `POST /api/vendor-score`, Feld `readiness_vendor`. |
| D-23 | 31.10.2026 | **Dubletten werden automatisch erkannt und entfernt:** in `sync` vor dem Schreiben, plus `tc dedupe` für den Bestand. Kriterium ist der Verlauf (Sportart, Start ± 5 min, Dauer ± 2 min, Distanz ± 400 m), nicht die ID. | Zwei Quellen für dieselbe Einheit sind der Normalfall geworden, nicht die Ausnahme. | 8 Einheiten aus der DB entfernt (295 → 287), Vault neu geschrieben, Sync prüft bei jedem Lauf. |
| D-24 | 31.10.2026 | **Der Vault wird schlank.** Keine Einheiten- und Wochen-Notizen mehr; er hält nur noch Ziele, Rennen, Beschwerden, Schuhe, Erkenntnisse und Coaching-Regeln. Wochenzahlen liefert `tc woche` aus der Datenbank. Kein Syncthing, keine Vault-Kopie auf dem Server. | Zwei Speicher für dieselbe Zahl laufen auseinander. Der Vault soll sagen, was wichtig ist, nicht was am Dienstag passiert ist. | 287 + 43 Dateien entfernt, `CLAUDE.md` und `start.md` umgeschrieben, `tc woche` neu. |
| D-25 | 01.11.2026 | **Mobile-Korrekturen und Stille Signale.** (a) Atmung fällt aus Treiberliste und Erklärung, bleibt aber mit 5 % im Score. (b) Fehlt ein Wert von heute, markiert die Oberfläche ihn („gestern") und die Erklärung sagt es. (c) Sync-Knopf sitzt auf dem Handy im Kopf der Seite; Countdowns stehen dort untereinander; die Kopfzeile bekommt `env(safe-area-inset-top)`. | Der Ring war am iPhone unter der Statusleiste abgeschnitten, der Sync-Knopf nur in der Sidebar erreichbar, die Countdowns liefen aus dem Bild, und die HRV von gestern sah aus wie die von heute. | Zonen unverändert, nur Darstellung. |
| D-26 | 01.11.2026 | **Erholung nur aus vollständigen Daten von heute.** Ein Score entsteht erst, wenn HRV, Ruhepuls, Schlaf **und** Atmung von heute vorliegen. Fehlt eines, gibt es keinen Score: „Keine Daten“, und die Erklärung nennt das fehlende Signal. Kein Teilwert, keine Renormierung, kein Wert von gestern. **D-15 und die Renormierung aus D-12 sind damit aufgehoben.** | Ein halber Wert sieht aus wie ein ganzer. Der Athlet will den Zustand von heute oder gar keine Zahl. | Rückfall auf `values[-1]` und Renormierung entfernt; `REQUIRED_SIGNALS` erzwingt alle vier. |
| D-27 | 01.11.2026 | **Eingabefelder sind mindestens 16 px groß.** Alle Text- und Zahlenfelder bekommen `font-size: 16px`, unabhängig von der Schrift der Karte drumherum; die Felder bleiben schmal und rechtsbündig. Dazu `inputmode` (Zahlen- statt Buchstabentastatur) und `enterkeyhint="done"`: „Fertig" speichert und schließt die Tastatur. | Safari auf dem iPhone zoomt beim Fokussieren in jedes Feld unter 16 px hinein und wieder heraus erst beim Neuladen — die Seite stand dann schief, der Kopf war weg, die Tastatur schnitt den Rest ab. | Globale Regel in `styles.css` statt Einzelfeld-Flicken; `maximum-scale=1` bleibt verboten, weil es Zoom für alle abschaltet. |
| D-28 | 01.11.2026 | **Die Oberfläche folgt `unslop`** (Damir Sokolovsky, [github.com/heydamir/unslop](https://github.com/heydamir/unslop), CC BY 4.0). Die gekürzte Fassung steht in [`UI-REGELN.md`](UI-REGELN.md) und gilt für jede künftige Oberflächenarbeit: erst prüfen, dann fünf Zeilen Richtung, dann neun Durchgänge in fester Reihenfolge. | Der Bildschirm liest sich als Vorlage: Farbschein auf jeder Karte, Sparklines statt Zahlen, Großbuchstaben-Labels, fünf Iconfarben, Begrüßung als Überschrift (E-29). Der Athlet sieht die Seite täglich und will ein Werkzeug, kein Template. | Kein Umbau ohne Richtung und Freigabe; die alte Optik wird über die neun Durchgänge ersetzt, Abschnitte und Reihenfolge bleiben. Nennung des Urhebers bleibt in jeder Kopie. |
| D-29 | 01.11.2026 | **Richtung B+ ist umgesetzt.** Kühle Tinten-Rampe (#08090f, #11141c, #1a1e28), ein Akzent Wörthersee-Teal (#3f9e8f), Farbe sonst nur als Befund. Instrument Serif für Titel und Countdown-Zahlen, Plex Sans für Text, Plex Mono für alles Zählbare. Fünf Charakter-Momente: die Uhr als Instrument mit Zonenring und Referenzmarke auf den 21-Tage-Schnitt, Skalen in den Treiberzeilen, Laststreifen der sieben Tage, Tagesstriche unter dem Diagramm, Aktivitäten als Tabelle. | Ohne die fünf Momente war die kühle Fassung (B) sauber, aber beliebig; die Serif und die Instrumente geben dem Trainingsbuch eine eigene Stimme, ohne in Slop zurückzufallen. | Schriften selbst gehostet (5 × woff2, 97 kB), recharts entfernt: Bündel 638 → 251 kB. Kennzahlen ohne Sparkline, Großbuchstaben-Labels ersetzt, Abstände auf dem 4-px-Raster, Verpflegung zweispaltig, Aktivitätenliste lädt in 40er-Schritten nach. |
| D-30 | 01.11.2026 | **Die Quelle bleibt austauschbar.** Garmin CIRQA (Nacht), Bevel (Kraft) und Wahoo (Rad) ändern keinen Code: alle drei landen über Health Sync bzw. intervals.icu in derselben Tabelle. Die Dubletten-Regel bleibt (Garmin Connect vor Health Sync, dann Feldzahl, dann Dauer). | Ein Gerät, das nur eine Quelle hinzufügt, darf kein Umbau sein. Der Athlet wechselt die Uhr, nicht das Cockpit. | Nach dem ersten Sync mit dem Band wird geprüft: Atmung je Nacht, HRV als rMSSD (D-21), Schlafscore, keine neuen Dubletten. Bleibt die Atmung lückenhaft, bleibt es bei „Keine Daten“ (D-26). |
| D-31 | 01.11.2026 | **Nach einem Sensorwechsel beginnt die Referenz neu.** Ein Datum (`wellness_epoch`) markiert die erste Nacht mit dem neuen Gerät. Ab dort zählen nur noch Nächte dieses Sensors in die 21-Tage-Referenz. Die ersten **7 Nächte** ergeben keinen Wert („Referenz wird aufgebaut“), von 8 bis 21 steht sie „im Aufbau“, danach ist sie normal. Die Historie bleibt in der Datenbank. | Ein anderes Gerät misst anders: HRV und Ruhepuls verschieben sich systematisch, nicht zufällig. Alte und neue Nächte in einer Referenz zeigen zwei Wochen lang eine Erholung, die es nicht gibt. | Neues Feld `reference` in `/api/overview`, `tc baseline --start JJJJ-MM-TT` (und `--off`), Anzeige in Uhr und Untertitel. Gilt für das CIRQA-Band, das am 4. November 2026 kommt. |
| D-32 | 01.11.2026 | **Die bessere Aufzeichnung gewinnt, die Last bleibt bei intervals.** Von einer Einheit, die mehrfach ankommt, bleibt die aussagekräftigere: Garmin Connect vor Health Sync, dann die vollständigere, dann die längere. Die Trainingslast wird **nicht** selbst gerechnet: Garmins `activityTrainingLoad` liegt im Median 2,64× über intervals' Last (Spanne 0,29–8,64 über 66 Paare) und würde Fitness und Müdigkeit unbrauchbar machen. | Ein zweites Lastmaß würde die Historie unvergleichbar machen; die Aufzeichnung selbst darf trotzdem die bessere sein. | Läufe und Schwimmen kommen künftig als Garmin-Aufzeichnung, Kraft und Rad aus intervals (Bevel, Wahoo). Health Sync verliert die Berechtigung; Strava bleibt außen vor, weil es keine Zusatzinformation liefert, die intervals nicht schon hat. |
| D-33 | 01.11.2026 | **Läufe und Schwimmen kommen über Garmins Personal API, Kraft und Rad über intervals.** Garmin hat bei intervals keine Berechtigung mehr, also liefert nur die Personal API die Aufzeichnung. Weil dort keine intervals-Last mehr entsteht, rechnet das Cockpit sie selbst: `Last = Stunden × Faktor × (Puls/160)²`, Faktor 75 für Läufe, 70 für Schwimmen — kalibriert an der historischen intervals-Last (R² = 0,974 über 37 Läufe). Garmins eigene `activityTrainingLoad` wird **nicht** übernommen. | Ein zweites Lastmaß würde Fitness und Müdigkeit unvergleichbar machen; die kalibrierte Formel trifft die alte Skala. | Neues Modul `load.py`, Garmin-Aktivitäten in `sources/garmin.py`, Sync schreibt beide Quellen und räumt Dubletten (Garmin schlägt Health Sync). Erster Lauf: 17 Läufe/Schwimmen direkt, Wochenstunden sinken um die Pausen, die Health Sync mitzählte. |
| D-49 | 03.11.2026 | **Aktivitäten kommen von Strava, der Plan bleibt bei intervals.** *(Ausgesetzt am 03.11.2026: Strava verlangt für eine API-App ein Abo von 11,99 $ im Monat. Bis auf Weiteres bleiben Rad und Kraft bei intervals; der fertige Client ist seit 04.11.2026 als lokaler Tag `archive/strava-ist-quelle` gesichert, den Branch gibt es nicht mehr.)* Der Sync liest von intervals nur noch `athlete`, `wellness`, `events` und `sport-settings`; abgeschlossene Einheiten kommen aus **Strava** (Rad, Kraft) und der **Garmin-Personal-API** (Läufe, Schwimmen). Es gibt **keinen stillen Rückfall auf intervals**, wenn Strava fehlt: dann fehlen Rad und Kraft sichtbar, und das Sync-Log sagt `strava=aus`. Zugangsdaten (Client-ID, Secret, Refresh-Token) liegen in der Einstellung `strava_auth` in der Datenbank, nicht in `.env` — der Refresh-Token wechselt, eine Datei im Container wäre der schlechtere Ort. Die **Last** rechnet das Cockpit selbst: aus Leistung, wenn Strava welche hat (`TSS = Stunden × (NP/FTP)² × 100`), sonst aus Puls mit derselben Formel wie bei Garmin (D-33), Faktoren an den alten intervals-Lasten kalibriert: Kraft 52 (n = 42), Rad 65 (n = 12), Rad indoor 72 (n = 41). | Strava hat die Einheiten aus Wahoo und Bevel mit mehr Feldern und ohne Health Sync dazwischen; intervals hat als Aktivitätsquelle ohnehin keine Berechtigung mehr für Garmin (E-31). Der Plan dagegen braucht intervals: dort liegen die strukturierten Workouts, und dorthin wird später auch geschrieben (D-45/D-46). Ein Rückfall wäre bequem, würde aber eine falsche Quelle monatelang verstecken. | Neues Modul `sources/strava.py` (OAuth mit Refresh-Token, Paginierung, Mapping), `tc strava-auth` für die einmalige Freigabe, `load.power_load`/`load.value_for`, `plan.ftp_from` als einzige Stelle, die drinnen und draußen unterscheidet. Bereits gespeicherte intervals-Zeilen bleiben stehen — Historie wird nicht umgeschrieben. |
| D-48 | 03.11.2026 | **Bewertung nach der Einheit: RPE und Gefühl.** Wo Garmin die Einheit aufgezeichnet hat, kommen beide Werte von dort (`directWorkoutRpe / 10`, `directWorkoutFeel / 25`) — sie stehen im Detail-Call (`get_activity`), nicht in der Aktivitätenliste. Wo das Gerät schweigt (Wahoo, Bevel über Strava), fragt das Einheiten-Blatt einmal ab, mit derselben Skala: **RPE 1–10**, **Gefühl 1–5**. Gespeichert wird `rpe`, `feel` und `rpe_source` (`garmin` oder `athlet`). **RPE fließt nicht in die Erholung ein** (D-26): das ist ein Urteil über die Einheit, keine Messung des Körpers — ausgewertet wird es später in der Wirkungsanalyse. | Der Athlet will seine Einheiten bewerten, und die zweite App fragt bereits danach. Garmins Skala ist geschenkt und bleibt über die Zeit konstant; sie zu übernehmen ist billiger und vergleichbarer als eine eigene. | Garmin-Detail-Call je Einheit (ein Aufruf, nicht in der Liste), neue Spalten an `activity`, ein Blatt-Abschnitt „Wie war's?". RPE wird in der Wirkungsanalyse gegen Last und Puls gestellt, nicht im Score. |
| D-47 | 03.11.2026 | **Bearbeitet wird im Text, nicht in einem Formular.** Das Blatt „Bearbeiten" zeigt Name, Sport, Datum, Indoor-Schalter und ein Textfeld mit dem Aufbau in der Schreibweise von intervals („Aufwaermen / - 10m 33-54%", „Hauptteil 3x" mit eingerückten Wiederholungen). Beim Tippen übersetzt ein Parser den Text in Schritte und zeigt **sofort** das Profil mit Achse in Watt bzw. bpm, Dauer und Last. Beim Speichern geht das strukturierte `workout_doc` an intervals, der eingetippte Text bleibt bei uns gespeichert und wird beim nächsten Öffnen angezeigt. Bewusst weggelassen: CHO/h, Sub Type, Tags, Last, Normalized/Average/Work, SS — intervals rechnet das selbst. „Indoor" bleibt, weil es über die FTP entscheidet (185 statt 195 W). | Der Athlet tippt seine Einheiten ohnehin als Text in intervals; ein Formularbaukasten wäre mehr Klicks für dasselbe Ergebnis. Der Text ist die kürzeste Beschreibung dessen, was auf die Uhr soll, und die Vorschau zeigt sofort, ob es ankommt. | Neues Modul `plan_text.py` (Text → Schritte, mit Zeilennummern in Fehlermeldungen), `PATCH /api/event/{id}`, Push über die intervals-Schreib-API, `event.text` als eigene Spalte. Erst nach dem lesenden Wochen-Tab. |
| D-46 | 03.11.2026 | **Verschieben wird zweimal gebaut, einmal behalten.** Zwei Feature-Branches gegen dieselbe Schnittstelle: `feature/woche-verschieben-ziehen` (Long-Press, ziehen, Zieltages-Hervorhebung) und `feature/woche-verschieben-tippen` (Zeile antippen → „Verschieben" → Zieltag → OK). Entschieden wird nach drei Maßen: Fehlgriffe, Sekunden bis erledigt, Verhalten bei 390 px. Der Gewinner geht nach `main`, der Verlierer bleibt als Branch liegen. | Auf dem Handy ist Ziehen unzuverlässig und Tippen langweilig, aber präzise. Statt zu raten, wird beides einmal gebaut — der Aufwand ist klein, weil die Woche in beiden Fällen dieselbe ist. | Zwei Branches, ein Merge. Bis zur Entscheidung kein Schreibpfad in `main`. |
| D-50 | 03.11.2026 | **Die Nächte kommen von Garmin.** Ab 4. November 2026 liefert die Garmin-Personal-API die Nachtsignale: Schlaf (`get_daily_sleep_summaries` — Dauer, Score, Nachtatmung), HRV (`get_daily_hrv_summaries` — `lastNightAvg`), Ruhepuls und Tagesatmung (`get_daily_summaries` — `heartRate.restingValue`, `respiration.avgValue`) und Gewicht. intervals liefert nur noch Plan und Sport-Einstellungen, vorerst auch die Aktivitäten für Rad und Kraft. Zwei Regeln sichern den Wechsel: der Sync schreibt Nächte **nur ab dem Sensorwechsel** (`wellness_epoch`), weil sonst beim Jahresimport alte intervals-Werte unter die neuen rutschten; und ein fehlender Wert **löscht keinen gespeicherten** mehr (`COALESCE`), weil die drei Endpunkte je Nacht unterschiedlich schnell liefern. Die Referenz beginnt neu: `tc baseline --start 2026-11-04`. | Mit dem CIRQA-Band ist Garmin der Sensor, der nachts misst — Health Sync fällt als Zwischenstation weg. Zwei Quellen für dieselbe Nacht wären genau der Fehler, den wir bei den Aktivitäten schon hatten (E-34): unterschiedliche Geräte, unterschiedliche Maßstäbe, gemischte Referenz. | `garmin.wellness_rows()` übersetzt drei Endpunkte in eine Zeile je Tag (in der Form, die `db.map_wellness` schon versteht), `_seit_epoche()` schneidet am Sensorwechsel, `upsert_wellness` überschreibt nur noch mit Werten. Sechs neue Tests. Erwartung: erste Bewertung, wenn sieben Nächte des Bandes da sind (D-31), also ab dem 11. November. |
| D-51 | 03.11.2026 | **Der erste Erholungswert kommt mit vollständiger Referenz.** `REFERENCE_MIN_NIGHTS` steigt von 7 auf 21, also auf `BASELINE_DAYS`. Bis dahin steht „Referenz wird aufgebaut, x von 21 Nächten" und kein Wert; der Zwischenzustand „Referenz im Aufbau" entfällt. **Hebt die 7-Nächte-Schwelle aus D-31 auf** — die Neustart-Marke selbst bleibt. | An den eigenen 368 Nächten gerechnet: mit sieben Nächten ist der Mittelwert der HRV um **±4,0 Score-Punkte** unsicher, mit 21 um ±2,3, mit 30 um ±1,9. Der Sprung liegt zwischen 7 und 21, nicht bei 30. Wichtiger als die Statistik: die Referenz lernt, was in diesen Wochen trainiert wird — in einer Aufbauwoche gemessen ist „üblich" zu hoch, und danach sieht jede ruhige Woche nach Übertraining aus. Die Trainingslehre setzt dieselben vier Wochen an. | Erster Wert am **24.11.2026** (21 Nächte ab dem 04.11.). `tc baseline` kennt nur noch „wird aufgebaut" und „steht". Danach eine Woche gegen Bevel vergleichen. |
| D-52 | 03.11.2026 | **Der Bevel-Wert wird im Vergleichsfenster eingetragen.** In der Erholungskarte steht während des Referenzaufbaus und eine Woche darüber hinaus (`nights < minimum + 7`) eine stille Zeile „Bevel" mit Zahlenfeld. Sie speichert beim Verlassen des Feldes („Fertig" schließt es, D-27), zeigt bei vorhandenem eigenem Score die Differenz („Cockpit 91 · Bevel 67 · −24 Punkte") und verschwindet danach von selbst. Das Feld zählt **nicht** in den Score (D-26); es ist der Maßstab, an dem das Modell gemessen wird. | Ab dem 24.11. gibt es den ersten eigenen Wert; eine Woche Vergleich danach ist die Kalibrierung, die D-22 vorgesehen hat, aber D-38 hatte das Eingabefeld mit der Karte entfernt. Zwei Paare reichten damals nicht — jetzt werden täglich Paare gesammelt, ohne dass ein Formular auf der Seite bleibt. | Neues Feld `vendor_prompt` in `/api/overview` (Regel im Backend, nicht im Browser), Komponente `VendorScore`, `POST /api/vendor-score` wie gehabt. Nebenbei: die 16-px-Regel aus D-27 war beim Aufräumen von D-38 verschwunden und gilt jetzt wieder für alle Zahlenfelder — auch für die im Verpflegungsrechner, die zuletzt unter 16 px lagen. |
| D-45 | 03.11.2026 | **Ein neuer Tab „Woche" zeigt den Plan.** Navigation: Heute · Woche · Verpflegung. Inhalt: sieben Tage untereinander (heute zuerst), je Tag die geplanten Einheiten mit ihren Kennzahlen, Tippen öffnet das bekannte Einheiten-Blatt. Kein Ziehen, kein Bearbeiten im ersten Schritt — der Tab liest nur und schreibt nichts. | Der Blick nach vorn fehlt bisher: die Tageskarte zeigt heute und morgen, der Plan reicht weiter. Die Woche ist die Frage „was kommt?", und sie kommt vor jeder Bearbeitung — erst sehen, dann ändern. | Neue Seite `pages/Week.tsx`, `GET /api/week/plan`, dritter Eintrag in Tableiste und Sidebar. Schreibpfad folgt in D-46/D-47. |
| D-40 | 01.11.2026 | **Herzfrequenz steht in Schlägen, nicht in Prozent.** Der Plan nennt HF-Ziele als Prozent der Maximalfrequenz oder als Zone; angezeigt wird der Bereich in bpm („133–142 bpm"), die Achse des Profils läuft in bpm. Grundlage sind `max_hr` und `hr_zones` je Sportart aus den Einstellungen von intervals, die der Sync als `hr_profile` ablegt. Zonen kommen aus den Zonengrenzen, Prozente aus `max_hr × p/100`; die untere Grenze von Zone 1 ist die halbe Maximalfrequenz, weil intervals sie nicht führt. Dasselbe für die Leistung: `% FTP` wird zu Watt über die FTP aus denselben Einstellungen (195 W draußen, 185 W auf dem Ergometer bei `Virtual*`). | „70–75 %" muss man im Kopf umrechnen, „133–142 bpm" steht so auf der Uhr. Der Athlet liest die Einheit morgens am Telefon, nicht am Rechner mit Taschenrechner. | Neue Einstellung `sport_profile` (aus `/api/athlete/{id}/sport-settings`), `plan.py` übersetzt vor der Anzeige. Fehlt das Profil, bleibt es beim Prozentwert — der Plan verliert nichts, die Anzeige bleibt nur ungenauer. |
| D-41 | 02.11.2026 | **Eine Einheit ist doppelt, wenn der Start doppelt ist.** Gleiche Sportart und Start innerhalb von fünf Minuten **und** mindestens eine übereinstimmende Spur: gleiche Gesamtzeit (± 5 min), gleiche Bewegungszeit (± 2 min, bei langen Einheiten ± 20 %) oder gleiche Strecke (± 400 m) bei ähnlicher Dauer. Die Auswahl passiert **vor** dem Schreiben, über beide Quellen hinweg; gespeicherte Dubletten räumt weiter `tc dedupe` und jeder Sync. Der Gewinner bleibt wie in D-32, mit einer Präzisierung: **Personal API vor Garmin Connect**, danach die vollständigere, dann die längere Aufzeichnung. | Die alte Regel verlangte Dauer **und** Strecke — dadurch stand die Long Ride vom 1. November doppelt in der Woche (15,1 statt 13,1 Stunden), weil Wahoo und Health Sync Strecke und Pausenzeit unterschiedlich rechnen. Die Gesamtzeit ist der einzige Wert, den keine Plattform neu berechnet. Die Personal API gibt die Bewegungszeit des Geräts weiter, während intervals sie bei der Zeile über Garmin Connect einmal als Gesamtzeit übernommen hat (250 m in 43 Minuten, April). | `dedupe.py` prüft drei Spuren statt einer Und-Verknüpfung, `sync.py` entdoppelt intervals- und Garmin-Zeilen gemeinsam vor dem Schreiben, 18 gespeicherte Paare werden entfernt. |
| D-44 | 02.11.2026 | **Atem- und Entspannungsübungen sind kein Training.** Die Sportarten `Workout` und `Transition` bleiben in der Datenbank, zählen aber nirgends als Einheit: nicht auf der Tageskarte, nicht in „Letzte 7 Tage", nicht im Umfang, nicht in der Wochenübersicht (`tc woche`). Gefiltert wird in der Abfrage (`db.training_between`), nicht beim Schreiben — die Aufzeichnung ist echt, nur ihr Trainingswert nicht. | Zwei „Entsp. u. konzentr."-Einträge mit 6 Minuten und Last 0 standen als Einheit zwischen echtem Training, seit D-43 auch als „Zusätzlich" auf der Tageskarte. Der Athlet will seine Einheiten sehen, nicht seine Atemübungen. | Neue Abfrage `training_between`, vier Aufrufstellen (`build_overview`, `build_weeks`, `plan.unplanned`, `/api/week`), Woche 27.10.–02.11.: 15 → 13 Einheiten, 13 h 03 min → 12 h 52 min. |
| D-43 | 02.11.2026 | **Die Tageskarte zeigt auch, was dazukam.** Unter den geplanten Einheiten von heute stehen die erledigten, die in keinem Plan standen (Beispiel: das Krafttraining am Morgen). Zuordnung wie bei „Erledigt": jede geplante Einheit nimmt sich ihre Aufzeichnung, was übrig bleibt, ist dazugekommen — eine Aufzeichnung wird nur einmal vergeben. Die Zeile trägt rechts **„Zusätzlich"** und öffnet nicht den Plan, sondern die Zusammenfassung der Aufzeichnung (D-42). Kopfzeile und Anzahl zählen beides zusammen. | Die Karte hieß „Training", zeigte aber nur den Plan. Die Einheit fehlte am Ort der Tagesfrage, obwohl sie in der Wochensumme stand — der Athlet musste zwei Blätter vergleichen, um zu sehen, was er heute gemacht hat. | Neues Feld `unplanned` in `/api/overview`, `plan.unplanned()` und `plan.done_row()`, `TrainingCard` mit zweiter Zeilenart, `UnitSheet` auch von der Karte aus. |
| D-42 | 02.11.2026 | **Der Wochenumfang öffnet die Einheiten.** Ein Tipp auf „Umfang" oder „Einheiten" in der Wochenkarte öffnet ein Blatt „Letzte 7 Tage": oben die Summe mit Zeitraum, darunter die Einheiten nach Tag gruppiert (Symbol, Name, Dauer · Distanz, Last). Jede Zeile öffnet die Einheit in einem zweiten Blatt — dieselbe Form wie beim Plan, aber mit dem, was die Aufzeichnung hergibt: **Zeit in den Zonen** als stehender Balken, Dauer · Distanz · Last als drei Zellen, darunter Puls, Tempo, Höhenmeter, Intensität, Kalorien, Quelle. Kein Verlaufsprofil: die Aufzeichnung liegt ohne Sekundenwerte in der Datenbank, ein gezeichneter Verlauf wäre erfunden (D-37: keine erfundenen Zahlen). Der Zurück-Pfeil führt zur Liste. | Die Wochenkarte sagte bisher nur eine Summe; die Frage „womit?" blieb offen und die Antwort lag in der Datenbank. Dieselbe Bewegung wie bei den geplanten Einheiten: erst die Liste, dann die Einheit — ohne die Seite zu verlassen. | Neues `GET /api/week` und `GET /api/unit/{row_id}`, Blätter `WeekSheet` und `UnitSheet`, gemeinsamer Rahmen `Sheet`, `Today.tsx` reicht Klick und Auswahl durch. |
| D-38 | 01.11.2026 | **Die Startseite hat sieben Zeilen:** Datum mit letztem Sync, Ziele, Erholung, Training, letzte 7 Tage. Die drei Kennzahlenkarten (Schlaf, HRV, Ruhepuls) entfallen, weil die Erholungskarte dieselben Werte als Treiberzeile zeigt und darunter in einem Satz erklärt. Der Knopf „Aktualisieren" fällt aus dem Kopf: am Handy zieht man, am Rechner steht er in der Seitenleiste. Der **Bevel-Abgleich** verschwindet ebenfalls. | Die Karten wiederholten, was die Treiberzeile schon sagte, und schoben das Training unter den Bildschirmrand. Der Bevel-Abgleich war für die Kalibrierung gedacht (D-22): dafür liegen **zwei** Paare vor, und nach dem Sensorwechsel am 4. November (D-31) würde die Referenz zwei Geräte mischen. Die Frage, für die er gedacht war, ist inzwischen anders beantwortet. | `Today.tsx` ohne Kennzahlen und ohne Bevel-Formular, `StatCard` entfällt, `Sidebar` bekommt den Sync-Knopf. Das Feld `readiness_vendor` und `POST /api/vendor-score` bleiben im Backend — die zwei Paare gehen nicht verloren, eine Rückkehr wäre eine Karte. |
| D-39 | 01.11.2026 | **Der Tab „Aktivitäten" entfällt vorerst.** Die Seite bleibt im Code liegen und wird nicht mehr verlinkt; Navigation ist Heute und Verpflegung. | Der Athlet plant und liest seine Einheiten künftig auf „Heute"; die Liste ist für später gedacht, wenn eigene Planung und Wirkungsanalyse kommen. Ein leerer Tab kostet nur Pflege. | `Tab` kennt nur noch `today` und `fuel`, die Tableiste hat zwei Einträge. `pages/Activities.tsx` bleibt unangetastet. |
| D-59 | 05.11.2026 | **`DESIGN.md` ist das verbindliche Designsystem.** Das Premium-Redesign vom 05.11.2026 liegt als `DESIGN.md` im Projekt-Root; Referenzgrafik und Arbeitsauftrag liegen unter `docs/design/`. `docs/UI-REGELN.md` (unslop) ist damit ersetzt, bleibt aber als Herkunftsnachweis stehen — CC BY 4.0 verlangt Name und Link. Die Migration läuft in Phasen nach `docs/design/AGENT_MIGRATION.md`: jede Phase ein Ticket, nach jeder Phase Stopp und Abnahme. | Zwei Regelwerke nebeneinander wären eine Einladung, das falsche zu lesen. Das neue Designsystem ist die einzige Quelle für Oberflächenarbeit; die alte Datei bleibt aus Lizenzgründen erhalten, nicht als Alternative. | `DESIGN.md`, `docs/design/AGENT_MIGRATION.md`, `docs/design/cockpit-premium-reference.png`; `AGENTS.md` und `README.md` zeigen auf `DESIGN.md`. Die Migration beginnt mit Phase 0 (Audit, keine Codeänderung). |
| D-60 | 05.11.2026 | **Der Score-Demo-Zustand lebt nur in der Vorschau.** `?demo=recovery` ersetzt im Vorschau-Bau (`VITE_APP_VARIANT=preview`) die Anzeigedaten der Erholung: Score 82, Band „Gut", HRV 62 ms / Ruhepuls 46 bpm / Schlaf 6:50 h, „Nacht vom …". Neben der Plakette „Vorschau" steht das Abzeichen „Demo". Der stabile Bau enthält den Zweig nicht; `isPreview` ist eine Build-Konstante, der Rest wird wegoptimiert. Keine API-, Berechnungs-, Recovery- oder Typänderung. | Ohne echten 21-Nächte-Score ist die Erholungskarte im Score-Zustand nicht beurteilbar; die Referenzzahl 82 darf aber nie für echt gehalten werden. Deshalb nur in der Vorschau, nur mit ausdrücklichem Parameter und mit sichtbarem Abzeichen. | `web/src/demo.ts`, `web/src/components/Brand.tsx` (`DemoTag`), `web/src/App.tsx`, `web/src/components/Sidebar.tsx`, `web/src/styles.css` (`.brand-tag.demo`, Tab-Leiste); Bilder und Bericht unter `docs/design/screens/demo/` und `docs/design/demo-vergleich.md`. |
| D-58 | 05.11.2026 | **Ohne Erholungswert bleiben die Nachtwerte sichtbar.** Fehlt der Score, weil die Referenz noch aufgebaut wird (D-31/D-51) oder ein Pflichtsignal fehlt (D-26), zeigt die Erholungskarte an der Stelle der Treiberzeile die drei Werte der letzten Nacht: HRV, Ruhepuls und Schlafdauer. Sie sind reine Anzeige, kein Teilwert und keine Hochrechnung; ein fehlender Wert steht als „—". Sobald ein Score existiert, erscheint wieder die volle Treiberzeile — die Werte stehen nie doppelt. | In der Kalibrierungsphase war die Karte leer: ohne Score fehlen die Treiberzeilen, obwohl HRV, Ruhepuls und Schlaf in der API liegen. Der Athlet will morgens trotzdem sehen, was die Nacht gemessen hat. | `Today.tsx` zeigt bei leerer Treiberliste den Block `night`, `styles.css` ergänzt `.night`; D-38 bleibt sonst unberührt (keine neuen Kennzahlenkarten, keine Duplikate bei vorhandenem Score). |

| D-35 | 01.11.2026 | **Mobil ist die Referenz, nicht der Notfall.** Jeder Bildschirm wird zuerst auf 390 × 844 gebaut und dort geprüft; der breite Schirm ist die Erweiterung. Kein Layout, das auf dem Handy scrollt, um zwei Spalten zu retten, keine Fläche, die nur mit Maus funktioniert, Tap-Ziele mindestens 40 px hoch, Bedienung mit dem Daumen im unteren Drittel. | Das Cockpit wird fast immer am iPhone benutzt, oft in der Hand, oft vor oder nach dem Training. Ein Entwurf, der am Rechner entsteht und dann schrumpft, trägt dort nicht. | Entwürfe als Handy-Mockup, Prüfung bei 390 px vor jedem Commit, `Mobile-first` als erster Punkt in `UI-REGELN.md`. |
| D-36 | 01.11.2026 | **Die Startseite zeigt das Training.** „Frische“ als Kennzahl, das Diagramm „Belastung & Frische“ und die Liste „Letzte Aktivitäten“ verlassen die Startseite. An ihre Stelle tritt die Karte **Training** mit den Einheiten von heute und morgen; jede Zeile öffnet die Einheit. Erholung, Treiber, Schlaf/HRV/Ruhepuls, Bevel-Abgleich und die Wochenkarte bleiben. | Rückblick beantwortet die Morgenfrage nicht. Die Zahlen bleiben in der Datenbank und in der Wochenkarte; die Liste der Einheiten lebt auf der Seite Aktivitäten weiter. | Neue Felder `sessions` in `/api/overview`, neue Karte in `Today.tsx`, `LoadChart` und `ActivityTable`-Nutzung auf „Heute“ entfallen. |
| D-37 | 01.11.2026 | **Die Einheit ist ein Blatt mit Profil** (Variante 2 aus dem Mockup): geplanter Verlauf zuerst, darunter Dauer · Distanz · Last, Aufbau, Verpflegung, bei erledigten Einheiten „Geplant · gemacht“. Dauer und Distanz stehen beide, das Ziel der Einheit führt; der fehlende Wert bekommt ein **≈** und wird aus dem eigenen Median der letzten 90 Tage geschätzt (Rad 24 km/h, Lauf 8,6 km/h, Schwimmen 2,6 km/h). Kohlenhydrate erst ab 60 Minuten, aus `fuel.py`. Kein Coach-Text, keine Empfehlung. | Der Athlet will sehen, was die Einheit verlangt, nicht was jemand dazu meint. Die Schätzung ist aus dem eigenen Fahrtenbuch abgeleitet und damit nachprüfbar; erfundene Zahlen sind verboten. | Neue Tabelle `event` mit `raw` (Schritte, Zonen), neues Modul `plan.py`, `GET /api/session/{id}`, Overlay `SessionSheet` mit `SessionProfile`. |

| D-55 | 04.11.2026 | **`develop` ist die Integrationsstrecke, `main` die Abnahme.** Jedes Ticket arbeitet auf einem Feature-Branch von `main`; freigegeben wird nach `develop`, und `develop` läuft auf dem Homeserver als eigene Vorschau-Instanz (Port 8101, eigenes Image, eigene Kopie der Datenbank). Nach `main` kommt ein Stand erst nach der Abnahme am Handy und im Browser. | Bisher gab es nur `main`: jede Änderung war sofort produktiv, ohne Zwischenstufe zum Ansehen. Getestet wurde damit am Produktivstand — ein Fehler war sofort sichtbar, aber nicht mehr rückholbar. | Branch `develop`, `docker-compose.develop.yml`, `docs/DEPLOY-DEVELOP.md`, Tailscale-Serve auf Port 8443; `AGENTS.md` im Repo hält die Regeln für Menschen und Agenten fest. |
| D-57 | 05.11.2026 | **Der Release ist ein Knopf im Board, kein Cherry-Pick.** `develop` bleibt die Integrationsstrecke, `main` die Abnahme. Ein Release merged `develop` nach `main` (`--no-ff`), setzt den nächsten fortlaufenden Tag (`v0.1.0`, dann `v0.2.0`, `v0.3.0` …), pusht beides und rollt die Produktion (8100) über `tools/deploy-main.sh` aus; danach zieht `develop` auf `main` nach. Vorbedingung: `main` hat keine Commits, die `develop` nicht kennt — sonst verweigert das Board und verlangt erst den Merge `main` → `develop`. | Cherry-Picks entstehen nur, wenn die beiden Linien auseinanderlaufen. Mit dieser Regel ist jedes Release ein Merge ohne Konflikt und ein Hotfix ein Branch plus zwei Merges. Der Knopf sitzt dort, wo die Historie am frischesten ist — im Arbeitsbaum auf dem Server — und ist vom Handy erreichbar. | Aktion `release` im Ticket-Board mit Vorschau der Commits, Sperre bei laufenden Agenten und Verlauf der letzten Releases; `tools/deploy-main.sh`; Abschnitt „Release“ in `docs/DEPLOY.md`. Die Entscheidungstabelle wächst ab jetzt nur noch auf `develop`; `main` bekommt sie beim nächsten Release mit. |
| D-56 | 05.11.2026 | **Die Vorschau trägt ein eigenes Logo.** Gebaut wird sie mit `VITE_APP_VARIANT=preview`; nur `docker-compose.develop.yml` setzt den Wert. Dann ist der Ring neben „Cockpit“ offen und im Akzent, daneben steht die Plakette „Vorschau“; auf dem Handy, wo die Seitenleiste fehlt, stehen Marke und Plakette oben im Inhalt. Titel, Favicon, Manifest und Startbildschirm-Icon („Cockpit Vorschau“, offener Ring mit V) sind ebenfalls unterschieden. Der stabile Bau bleibt unverändert. | Beide Instanzen sahen bisher gleich aus; am Handy waren weder Seitenleiste noch Logo sichtbar, also war vor dem Öffnen nicht zu erkennen, welche App man antippt. Die Vorschau ist zum Testen da (D-55) und muss als solche erkennbar sein, bevor ein Fehler für den Produktivstand gehalten wird. | `VITE_APP_VARIANT` als Build-Argument in `docker-compose.develop.yml`, `web/src/variant.ts`, `web/src/components/Brand.tsx`, `web/public/manifest-vorschau.webmanifest`, `web/public/icons/vorschau*`; `web/scripts/icons.mjs` erzeugt beide Icon-Sätze. |
| D-54 | 04.11.2026 | **Der Sync spiegelt die Aktivitätenliste von intervals.** Für den gesyncten Zeitraum gilt: was intervals nicht mehr führt, verschwindet auch aus dem Cockpit — und zwar **vor** der Dublettenprüfung. Bisher blieb eine dort gelöschte Zeile einfach stehen; weil die Prüfung die beiden Aufzeichnungen vergleicht, hielt sie die tote Wahoo-Zeile für die bessere und entfernte die lebende Health-Sync-Zeile. Ergebnis: eine Einheit, deren Sekundenwerte niemand mehr liefern kann. | Zwei Zeilen aus derselben Fahrt, eine davon in intervals gelöscht: die Woche zeigte die tote, die lebende fehlte, und der Verlauf war leer (D-53). Die Quelle ist die Wahrheit, nicht unser Bestand. | `db.delete_unlisted` je Sync über den gesyncten Zeitraum, Verläufe verschwinden mit ihrer Zeile (Fremdschlüssel), das Sync-Log nennt `verwaist=n`. Nichts außerhalb des gesyncten Zeitraums wird angefasst. |
| D-53 | 04.11.2026 | **Jede erledigte Einheit zeigt ihren Verlauf — aus der Aufzeichnung selbst.** Die Sekundenwerte kommen mit dem Sync in die Datenbank: für Einheiten aus intervals über `/activity/{id}/streams`, für Einheiten aus Garmin aus dem FIT der Originalaufzeichnung (`download_activity`, gelesen mit `fitparse`). Abgelegt wird je Einheit **eine** Reihe mit Zeit, Leistung, Puls, Tempo und Strecke in 5-Sekunden-Mitteln — feiner als jeder Bildschirm, gröber als die Aufzeichnung. Geholt wird beim Sync nur für die **letzten 14 Tage** und nur, was fehlt; ein Verlauf, den die Quelle nicht hat, wird nicht erfunden (D-37). Gezeichnet wird im Einheiten-Blatt: **Rad die Leistung** mit FTP-Linie, **Lauf das Tempo** (Achse umgedreht, schneller ist oben), **der Puls als zweite, ruhigere Linie** in beiden Fällen; Schwimmen und Kraft zeigen nur den Puls. Ausgeliefert werden höchstens 180 Punkte. **Hebt den Halbsatz aus D-42 auf** („kein Verlaufsprofil") — er entstand aus der Not: damals lagen keine Sekundenwerte in der Datenbank. | Ein Durchschnitt beantwortet die Frage nach der Einheit nicht: ob die drei Blöcke eines 3 × 10 min standen oder der erste zu hart war und der dritte einbrach, sieht man nur im Verlauf. Die Aufzeichnung gibt es, sie wurde nur nie abgeholt — und für Läufe liegt sie bei Garmin, für Rad und Kraft bei intervals. | Neue Tabelle `activity_stream`, Modul `streams.py`, `IntervalsClient.streams`, Feld `series` in `GET /api/unit/{row_id}` und im Ist-Teil von `GET /api/session/{id}`, Komponente `WorkoutChart` in `UnitSheet` und `SessionSheet`. Neue Abhängigkeit `fitparse`. |
| D-34 | 01.11.2026 | **Fitness und Müdigkeit rechnet das Cockpit selbst.** Bisher wurden die Tageswerte `ctl`/`atl` aus intervals übernommen. Seit die Läufe über die Personal API kommen, kennt intervals diese Einheiten nicht mehr — seine Form würde ab dem Sensorwechsel systematisch zu niedrig stehen. Ab jetzt zählt die eigene Rechnung (EWMA 42/7 Tage) über die eigenen Aktivitäten. | Ein Wert, der auf einem fremden, unvollständigen Datensatz beruht, ist schlimmer als eine eigene Rechnung, die man erklären kann. | `daily_days` ignoriert die übernommenen Werte; die Last kommt aus `load.py` (Garmin) bzw. intervals (Kraft, Rad). |
| D-61 | 05.11.2026 | **Die Erholung hat eine fünfte Stufe.** `BANDS` unterscheidet ab 85 „Sehr gut erholt" (`green-top`, eigener Ton `#7ef0c0`), 70–84 „Gut erholt", 50–69 „Solide", 35–49 „Erholungsbedarf" und 0–34 „Ruhetag". Der Score selbst, die Gewichte und die Referenz bleiben unverändert; das Band wird beim Lesen aus dem Score zugeordnet, nichts wird nachträglich umgerechnet. | 70 und 90 lagen bisher im selben grünen Band, obwohl sie sich deutlich unterscheiden. Eine Schwelle bei 80 würde zu oft getroffen und wäre kein eigener Zustand. | `metrics.BANDS` und `BAND_SENTENCES` („Du bist heute sehr gut erholt."), `Band`-Union, `BAND_COLORS` (`var(--band-top)`), Token `--band-top: #7ef0c0`; Grenzen 85/70/50/35/0 in `tests/test_metrics.py`. |
| D-62 | 05.11.2026 | **Das Band gehört zu der Zahl, die auf dem Ring steht.** `compute_recovery` bildet das Band aus dem gerundeten Score, also aus demselben Wert, den die Oberfläche zeigt. Vorher klassifizierte `_band` den Rohwert: Ein Rohwert von 84,63 stand als „85" auf dem Ring, trug aber „Gut erholt". | Die Oberfläche zeigt keine Nachkommastellen. Ein Band, das zu einer anderen Zahl gehört als der sichtbaren, wäre an jeder Grenze ein Widerspruch — besonders an der neuen 85er-Schwelle. | `_score_band` in `metrics.py`, Test `test_band_uses_displayed_score`; die Grenztests auf `_band` bleiben unverändert. |
| D-63 | 05.11.2026 | **Die Erholungskarte trägt den einzigen kräftigen Verlauf.** Bewusste Ausnahme von DESIGN.md 2.2: Nur die Erholungskarte bekommt einen Türkis-Verlauf von 28 % Deckkraft oben, der nach unten ausläuft; nur ihr Ring erhält einen dezenten inneren Schein. Dafür eigene Tokens `--recovery-wash`, `--recovery-wash-end`, `--recovery-ring-glow`; `--accent-wash` bleibt unverändert, alle anderen Karten bleiben neutral. Mit Score ist die Karte mobil (≤ 1000 px) zweispaltig: links Score mit „/ 100", gefüllte Türkis-Plakette, „Nacht vom …" und die Referenzzeile, rechts ein ca. 150-px-Ring mit Puls-Icon und Marker für den Referenzschnitt; darunter eine Trennlinie und HRV, Ruhepuls, Schlaf als drei Spalten mit Delta zur eigenen Baseline. Ohne Score bleibt der zentrierte Ring samt „Referenz wird aufgebaut" unverändert. Die Deltas rechnen aus den vorhandenen Feldern `today` und `baseline`/`average` der Erholungskomponenten (HRV Prozent, Ruhepuls bpm, Schlaf Minuten); kein neues API-Feld, keine erfundene Zahl. | Die Referenz zeigt die Karte als einziges farbiges Element; Neon, Schein auf allen Karten und bunte Kacheln bleiben verboten. Die bisherige Referenzzeile lief mobil unter dem Ring durch; mit der linken Spalte bleibt sie frei davon. | `web/src/pages/Today.tsx`, `web/src/components/RecoveryDial.tsx`, `web/src/components/icons.tsx` (`IconPulse`), `web/src/components/ui.tsx` und `web/src/styles.css` (`badge--accent`, Recovery-Tokens, Mobilraster), `docs/design/recovery-vergleich.md`. |
| D-64 | 05.11.2026 | **Die Erholungskarte trägt einen lokalen Lichtschein, keine Türkisfläche.** Ersetzt den flächigen Verlauf aus D-63: Die Karte bekommt die fast schwarze, leicht kühle Basis `--recovery-surface: #080d11` und darüber einen schwachen radialen Lichtschein oben (`--recovery-glow` in Teal mit 36 % Alpha, `--recovery-glow-soft` mit 8 %, transparent ab 72 % des Radius). Der Schein liegt auf einer eigenen dekorativen Ebene (`.recovery::before`) hinter dem Inhalt; nur ihre Deckkraft wird über `--recovery-glow-opacity: 0.5` reduziert, Karte und Inhalte bleiben voll deckend. Der Ring behält `--accent` und `--recovery-ring-glow`. Layout, Maße, Abstände, Radien, Typografie, Inhalte und Zustände bleiben unverändert; Statusplakette, andere Karten und Navigation bleiben unangetastet (Schritt 2 folgt). | Die Karte wirkte durch den 28-%-Verlauf über die ganze obere Fläche türkis statt dunkel. Die Referenz zeigt einen lokalen Lichtschein auf nahezu schwarzer Fläche; DESIGN.md 2.2 erlaubt nur ein sehr schwaches Ton-in-Ton-Spiel und keine großflächigen Farbwolken. | `web/src/styles.css` (`--recovery-surface`, `--recovery-glow`, `--recovery-glow-soft`, `--recovery-glow-opacity`, `.recovery`, `.recovery::before`), `docs/design/recovery-dunkel.md`. |
| D-65 | 05.11.2026 | **Der Ringstrich der Erholungskarte wird von 6 auf 8 Einheiten verstärkt.** Im viewBox 220 wächst die dargestellte Strichbreite bei 390 px dadurch von 4,0 auf 5,4 px (mit Score, Ring 148 px) und von 5,1 auf 6,8 px (ohne Score, Ring 186 px). `SIZE` 220, `RING` 92, Farben, der Ring-Schein `--recovery-ring-glow`, die Referenzmarker, `strokeLinecap` und das Layout bleiben unverändert; beide Zustände hängen an derselben Konstante. | Der Ring wirkte im abgestimmten Zustand zu dünn; gefragt war „ein wenig kräftiger", nicht ein neuer Ring. Die 8 halten den filigranen Charakter und machen den Bogen auf dem iPhone besser lesbar. | `STROKE` in `web/src/components/RecoveryDial.tsx`; Nachweis `docs/design/ring-dicker.md` und `docs/design/screens/ring-dicker/`. |
| D-66 | 05.11.2026 | **Karten, Statuslabels und Navigation folgen der dunklen Fläche.** Schritt 2 aus D-64: Die Kartenrampe liegt auf nahezu schwarzem, leicht kühlem Anthrazit — `--bg-surface: #0b1318`, `--bg-surface-raised: #0e181e`, `--bg-surface-interactive: #121f26`; `--recovery-surface: #080d11` bleibt der dunkelste Bezug, der Seitenhintergrund `--bg-app: #05090d` bleibt dunkler als die Karten. Die Konturen werden neutraler (`--border-subtle: #1c272e`, `--border-strong: #2a373f`). Kein Kartenverlauf, kein Schein außer auf der Erholungskarte, keine farbige Kartenfüllung. Statuslabels tragen überall 12 % ihrer Statusfarbe; das Erholungsband mappt auf `--band-top`/`--band-good`/`--band-mid`/`--band-low`/`--band-bad` (neue Töne `--band-top-soft`, `--band-low-soft`), die gefüllte Akzentpille entfällt. In der Navigation bleiben türkises Icon und helle 500er-Beschriftung, inaktiv `--text-muted`; keine Fläche, kein Balken, kein Halo. Die gewählte Verpflegungsart behält die Akzentkontur, bekommt aber eine neutrale Fläche. Layout, Maße, Abstände, Radien, Schriftgrößen und Markup bleiben unverändert (mit Score 350 × 431,39 px bei 390 px Breite). | Die übrigen Karten lagen noch auf dem alten petrolblauen Ton (#0d171d/#102229) und konkurrierten mit der Erholungskarte; die gefüllte „Gut"-Pille war der letzte vollflächig leuchtende Status und widersprach der gedämpften Statusregel. Ein neutraler Kartenrahmen lässt Ring und Kennzahlen die Hierarchie tragen. | `web/src/styles.css` (Tokens, `.nav`, `.mode-option.active`, `.badge--band-*`, `.badge--accent` entfällt), `web/src/pages/Today.tsx` (`BAND_TONES`), `web/src/components/ui.tsx` (`BadgeTone`), `DESIGN.md` (Abschnitte 5, 6, 10), Nachweis `docs/design/karten-status-navigation.md` und `docs/design/screens/karten-status-navigation/`. |
| D-67 | 05.11.2026 | **Positives Statuslabel und positive Trendtexte teilen denselben semantischen Text-Token.** Das „Gut"-Label der Erholungskarte bezieht seine Schriftfarbe direkt aus `--positive` statt über `--band-good`; der Alias `--band-good: var(--positive)` bleibt für die Skala bestehen. Das Label ergänzt lediglich eine dunkle, gedämpfte Fläche (`--positive-soft`, 12 %). Fläche, Höhe, Rundung, Innenabstand, Typografie, Position, andere Statuszustände und andere Komponenten bleiben unverändert; kein Glow, kein Verlauf, keine Umrandung, keine reduzierte Deckkraft. | Zwei Namen für denselben Wert sind eine stille Kopplung: Der Alias hätte sich lösen können, ohne dass die Gleichheit der positiven Textstellen sichtbar wird. Der Text soll am semantischen Token hängen, die Band-Skala bleibt für die Zuordnung. | `web/src/styles.css` (`.badge--band-good`), `DESIGN.md` Abschnitt 5, Nachweis `docs/design/recovery-label.md` und `docs/design/screens/recovery-label/`. |
| D-68 | 06.11.2026 | **Der Trainingsplaner ersetzt die Sieben-Tage-Liste und den geplanten Wochen-Tab.** Die bisherige `WeekSheet`-Liste (D-42) wird zum Kalenderwochenplaner umgebaut und ist danach keine eigene rollierende Ansicht mehr. Die Dashboard-Zeilen **Umfang** und **Einheiten** öffnen beide dieselbe bisherige Liste und verlieren daher beide Link, Klick-/Tastaturhandler, Chevron und Aktionsfokus; die Karte behält ihre rollierende Kennzahl. Der Planer bekommt einen eigenen Haupttab. Der in D-45 beschlossene Tab „Woche“ und `GET /api/week/plan` werden nicht zusätzlich gebaut. Der Bestand hat heute keine URL-Route für die Liste; eine Kompatibilitätsweiterleitung wird erst mit der neuen Planerroute in P07 angelegt. | Die Integrationsentscheidung des Implementierungsplans v1.6 löst D-42 und D-45 ab. Zwei Einstiege in dieselbe Liste wären nach dem Umbau zwei Wege in den Planer, obwohl der Planer nur über seinen Tab erreichbar sein soll. | `web/src/pages/Today.tsx` (`weekOpen`, beide `MetricRow`-`onClick`), `web/src/components/WeekSheet.tsx`, `web/src/tabs.ts`, `web/src/App.tsx`; P07 setzt Tab und Route um. |
| D-69 | 06.11.2026 | **Das Planungsmodell liegt als eigenes, UI-unabhängiges Paket `trainings_cockpit.planner` vor.** Es trennt typisierte Knoten-, Plan-, Aktivitäts-, Entwurfs- und Vorgangs-IDs; Zonenreferenzen tragen String-IDs und ein Zonenmodell; Zeit und Distanz sind kanonisch in Sekunden und Metern; unbekannte Inhalte bleiben als `UnsupportedNode` mit Quellreferenz erhalten. Der Schreibkoordinator akzeptiert an der Runtime-Grenze ausschließlich einen `WorkoutDraft` mit geplantem `PlannedWorkout`, nie eine `ActivityReference`, ein Dict oder ein `PlannedWorkout` ohne Entwurf. | Die vorhandenen Dict-Modelle in `plan.py` verlieren Ende-Bedingung, zusätzliche Ziele und Identitäten; das Frontend hat noch keinen Planer-Typ. Eine Aktivität darf über keinen generischen Handler in den Event-Schreibpfad gelangen, und ein gleicher numerischer Wert für Plan und Aktivität darf nicht denselben Cache-Key erzeugen. Das Modell ist die gemeinsame Grundlage für P04/P05 und die spätere UI, nicht ein neues Remote-Schema. | `src/trainings_cockpit/planner/` (`identities.py`, `model.py`, `projections.py`, `write.py`, `primitives.py`), `tests/test_planner_model.py`; keine Datenbankmigration, kein Netzwerkaufruf, kein neuer API-Endpunkt. P04 bildet `workout_doc` auf dieses Modell ab, P05 ergänzt die gemeinsame Validierung. |
| D-70 | 06.11.2026 | **Der Planer rechnet in einer expliziten Athletenzeitzone, standardmäßig `Europe/Vienna`.** Eine Woche ist das lokale Montagsdatum und sieben Kalendertage; die Zeitzone (`TC_TIME_ZONE`, Standard aus der bestehenden Compose-Konfiguration) dient nur dem lokalen „heute“ und wird nicht als UTC-Verschiebung auf lokale Tage angewendet. Der rollierende Dashboard-Zeitraum (heute plus sechs Tage) und die Planerwoche (Montag bis Sonntag) sind zwei getrennte `TrainingRange`-Verträge; keine Oberfläche leitet den einen aus dem anderen ab. | Der Server läuft in Compose mit `TZ=Europe/Vienna`, lokal aber gegebenenfalls anders; der Browser hat wieder eine eigene Zone. Ohne explizite Zone würde ein Sonntag am UTC-Rand verschwinden oder „diese Woche“ von der Laufzeitumgebung abhängen. Ein fester Demotag und ein stiller Rückfall auf die Prozesszeitzone sind keine belastbare Grundlage für Kalenderwochen. | `src/trainings_cockpit/planner/dates.py`, `primitives.py`, `config.py` (`DEFAULT_TIME_ZONE`, `Settings.time_zone`), `.env.example`; P03-Tests für Sonntag, Monats-/Jahreswechsel und beide Zeitumstellungen. |
| D-71 | 06.11.2026 | **Planungsdetails und Trainingsverlauf sind reine Leseansichten mit getrennten Identitäten.** Eine Planung öffnet über ihre Event-ID, eine Aufzeichnung über die vorhandene lokale Aktivitätszeile (`row_id`). Die URL trägt die gewählte Woche und optional `plan` beziehungsweise `einheit`; „Plan ansehen“ ergänzt den Planbezug, ohne die Aktivitätsansicht zu ersetzen. Graphdaten entstehen serverseitig aus derselben `derive_execution_sequence`/`calculate_known_totals` wie Summen und spätere Validierung. Getrennte Zielspuren verhindern eine gemeinsame HF-/Watt-Skala; Kompression großer Wiederholungsmengen ändert nur die Darstellung, nie die Summe. | P08/P09 brauchen nachvollziehbare Rückwege und dürfen Öffnen oder Auswählen nicht als Speichern deuten. Eine zweite Graphinterpretation im Frontend würde Wiederholungen, letzte Erholung und gemischte Umfänge anders zählen als die Fachlogik. Die bestehende gemessene Aktivitätskurve bleibt unangetastet; nur die Planungsansicht zeigt Vorgaben. | `src/trainings_cockpit/planner/profile.py`, `details.py`, `api.py` (`/api/planner/plan/{id}`), `web/src/components/PlanSheet.tsx`, `web/src/routing.ts`, `web/src/pages/Planner.tsx`, `web/src/components/UnitSheet.tsx`; P08/P09-Tests. |
| D-72 | 06.11.2026 | **Der Inline-Editor arbeitet auf einem lokalen Entwurf, dessen Feldpuffer die Oberfläche hält und der Server fachlich projiziert.** Basisplan und Source-Snapshot bleiben unverändert; der Entwurf trägt Rohtext je Knoten-ID und Feldpfad. `POST /api/planner/plan/{id}/draft` baut daraus einen `WorkoutDraft`, validiert ihn mit `validate_draft` und liefert Detail, Summen, Diagramm und Feldfehler aus derselben `derive_execution_sequence`/`calculate_known_totals`. Ein unvollständiges Ende wird nur im Entwurf als `OpenEnd` geführt und in Diagramm/Summe als offen markiert; gespeichert werden kann es nicht. Auswahl und aufgeklappter Block bleiben reiner UI-Zustand und zählen nicht als Dirty. Absolute bpm bleiben lokal modellierbar, sind aber ohne belegten Adapter-Schreibvertrag nicht als synchronisierbares Feld freigeschaltet. | Eine zweite Parser- oder Graphlogik im Browser würde unfertige Werte, Wiederholungen und Distanzen anders deuten als die Fachlogik. Der lokale Endpunkt liest nur die bereits gespeicherte Basis und schreibt nichts; damit bleiben Bearbeiten und Verwerfen ohne Remote-Folge, und der Entwurf kann einen späteren Hintergrund-Read nicht überschreiben. | `src/trainings_cockpit/planner/model.py` (`OpenEnd`), `drafts.py`, `details.py`, `validation.py`, `profile.py`, `api.py` (`/api/planner/plan/{id}/draft`), `web/src/plannerDraft.ts`, `web/src/components/PlanSheet.tsx`, `PlanEditor.tsx`, `tests/test_planner_drafts.py`; P10–P12. |
| D-75 | 06.11.2026 | **Der Serializer ist eine eigene fachliche Grenze und erzeugt nur geprüfte Schreibfelder.** `prepare_write(WorkoutDraft)` unterscheidet `create`, `metadata` und `structure`; `NoWriteNeeded` beendet unveränderte Entwürfe ohne Payload. Bei reinen Name-/Datumsänderungen fehlt `description` im Payload, damit der vorhandene Workouttext unverändert bleibt. Strukturänderungen erzeugen einen kanonischen Text mit `mtr` für Meter, expliziter Pace-Referenz (`/km`, `/100m`), relativen Zielen und `intensity=`-Rollen. Nicht belegte Fälle — absolute bpm, Leistungszonen, benutzerdefinierte Zonen, verschachtelte Wiederholungen, `skip_final_recovery`, Workout-Dokumentnotizen, Schrittnotizen, ungenaue Bruchteile und reservierte Namen — werden vor der Payload-Erzeugung abgelehnt. Aktivitätsreferenzen, Listenprojektionen und fremde Objekte scheitern an der exakten `WorkoutDraft`-Typgrenze; eine gleiche numerische Plan-/Aktivitäts-ID erlaubt keinen Typwechsel. Das Modul führt keinen Netzwerkaufruf aus. | Ohne isolierten Serializer würden UI, Sync und Payload-Logik dieselben Regeln unterschiedlich auslegen; insbesondere könnten 400 Meter als 400 Minuten enden oder ein reiner Namenswurf den Workouttext überschreiben. Die Ablehnung nicht belegter Fälle ist ehrlicher als eine Heuristik, die fremde Inhalte verliert. | `src/trainings_cockpit/planner/serializer.py`, `remote.py` (Rollen aus `intensity`), `__init__.py`, `docs/trainingsplaner/SERIALIZER-VERTRAG.md`, `tests/test_planner_serializer.py`; P17. |
| D-76 | 06.11.2026 | **Der Speicherkoordinator führt genau eine logische Operation pro geplanter Einheit.** Die Zustände `clean`, `dirty`, `invalid`, `saving`, `saved`, `failed`, `conflict`, `unknown` und `savedUnverified` bleiben getrennt; `unknown` ist kein „nichts gespeichert“. Vor dem Adapteraufruf entsteht aus Validierung, fachlicher Dirty-Prüfung und `PreparedWrite` ein unveränderlicher `SaveSnapshot` mit Vorgangs-ID, Entwurfsrevision, Account, Athlet und Ziel-Identität. Zehn schnelle Aktivierungen desselben Inhalts teilen eine Operation; nach einem bestätigten Write antwortet derselbe Snapshot aus dem gespeicherten Status, ohne erneut zu schreiben. `SAVING`, `UNKNOWN` und `SAVED_UNVERIFIED` sperren fachliche Eingaben. Timeout und HTTP 5xx werden als unklar klassifiziert; 401/403, 404, 409/412, 400/422 und 429 erhalten eigene Fehlerklassen. Ein 404 führt nie in einen Create. | Ohne eine zentrale Grenze würden Doppeltap, Enter plus Klick und mehrere Handler mehrere Creates oder Updates auslösen. Ein Boolean `isSaving` würde Timeout, bestätigten Erfolg und ungeprüften Erfolg vermischen; gerade nach einem verlorenen Timeout darf die UI keinen zweiten Write anbieten. Die unveränderliche Zuordnung verhindert, dass eine spätere Antwort neuere Eingaben überschreibt. | `src/trainings_cockpit/planner/save.py`, `serializer.py` (stabile externe Identität im Create-Payload), `identities.py` (`stable_external_id`), `__init__.py`, `tests/test_planner_save.py`; P18. |
| D-77 | 06.11.2026 | **Ein Update adressiert die ursprüngliche Remote-Event-ID und wird erst nach bestätigtem Rücklesen übernommen.** `EventWriteService` prüft Schreibberechtigung und Editierbarkeit, übergibt den `PreparedWrite`-Payload an genau diese ID und verwirft eine Antwort mit fremder Event-ID. Bei Struktur- und Metadatenänderungen wird das Event zurückgelesen; `verify_roundtrip` vergleicht Name, Sport, Termin, Uhrzeit, erhaltene Remote-Notizen, Anzahl, Reihenfolge, Gruppensemantik, Rollen, Ende-Bedingungen, Zielarten, Einheiten und Werte. Erst dann entsteht `saved` mit bestätigten Werten. Ein fehlgeschlagenes Rücklesen ist `savedUnverified`, kein Fehler und kein neuer Write. Ein 404 bleibt `failed`/`not_found` und löst nie einen Create aus. Ein optionaler Preflight-Hook blockiert bei Konflikt vor dem Schreiben; die vollständige Konfliktsicherung folgt in P21. Der Produkt-Endpunkt bleibt gesperrt. | Ohne feste Event-ID könnte ein Update eine neue Einheit erzeugen oder die falsche überschreiben. Ohne Rücklesen wäre ein HTTP-Erfolg keine Bestätigung des fachlichen Aufbaus; gerade gemischte Ziele und Rollen sind nur nach dem erneuten Einlesen prüfbar. Ein 404 als Create-Fallback würde eine extern gelöschte Planung still wiederherstellen. | `src/trainings_cockpit/planner/event_write.py`, `sources/intervals.py` (`update_event`), `planner/save.py` (`base_notes`), `tests/test_planner_update.py`, `tests/test_intervals.py`; P19. |
| D-78 | 06.11.2026 | **Eine Neuanlage erhält vor dem ersten Request eine stabile lokale und externe Identität und übernimmt nur die tatsächliche Remote-ID.** `stable_external_id` leitet die `external_id` deterministisch aus Account, Athlet und lokaler Plan-ID ab; der Create-Payload nutzt den belegten Bulk-Upsert des vorhandenen Clients. Eine Antwort wird nur übernommen, wenn ihre externe Identität zur lokalen Operation passt. Die Remote-ID stammt aus der Antwort und wird durch Rücklesen bestätigt; fehlt sie, bleibt der Vorgang `savedUnverified` ohne erfundene ID. Ein Timeout ergibt `unknown`; `reconcile` sucht ausschließlich lesend über `external_id` plus geplanten Tag, führt mehrere Treffer als Konflikt und wiederholt keinen Create. Neue Pläne tragen keine Aktivitätsbeziehung; die externe ID ist weder Abschluss- noch Matchingbeleg. | Zwei gleichnamige Einheiten am selben Tag sind fachlich zulässig und dürfen nicht über Name/Datum verschmelzen. Eine bei jedem Versuch neu erzeugte externe ID würde aus einem Retry eine zweite Einheit machen; eine erfundene Erfolgs-ID würde eine nicht bestätigte Remote-Einheit vortäuschen. Die lesende Suche nach einem unklaren Create verhindert die Doppelanlage, ohne einen zweiten Write zu riskieren. | `src/trainings_cockpit/planner/event_write.py` (`create_event`, `_reconcile_create`, `IntervalsEventAdapter`), `identities.py` (`stable_external_id`), `serializer.py` (Create-Payload), `tests/test_planner_create.py`; P20. |
| D-74 | 06.11.2026 | **Der Tages-Plus legt einen lokalen Neuen-Entwurf an, kein Remote-Event.** `POST /api/planner/draft/new` baut aus Tagesdatum, Sportart (`Run`/`Ride`/`Swim`), optionalem Namen und einer der drei Startformen (`simple`, `repeat`, `empty`) ein `PlannedWorkout` ohne `remote_id` und ohne `SourceSnapshot`. Die lokale Identität ist deterministisch `plan:draft:<draft_id>`; Startwerte sind 45 Minuten mit HF-Zone 2 nur bei vorhandenem Sportprofil (sonst „Ohne Ziel“) beziehungsweise vier Wiederholungen mit je zwei Minuten Belastung/Erholung oder ein leerer Aufbau. „Weiter“ öffnet denselben `PlanSheet`-Editor im Entwurfsmodus; Abbrechen schließt ohne Schreibvorgang. „Name & Termin“ ist auch für neue Entwürfe vorhanden; eine Datumsänderung verschiebt den lokalen Termin und erhält eine vorhandene lokale Uhrzeit. Bestehende Einheiten behalten ihre Remote-ID und ihre Sportart. | Ein Create-Request beim bloßen Öffnen würde leere oder verworfene Events hinterlassen. Die Trennung von lokaler Plan-ID und Remote-ID verhindert, dass ein Entwurf versehentlich als bestehendes Event adressiert wird. Die Startform ist eine lokale Vorlage, keine zusätzliche Intervals-Vorlagenbibliothek. | `src/trainings_cockpit/planner/drafts.py`, `details.py`, `api.py` (`/api/planner/draft/new`), `web/src/components/AddWorkoutSheet.tsx`, `PlanSheet.tsx`, `web/src/pages/Planner.tsx`, `web/src/plannerDraft.ts`, `web/src/api.ts`, `web/src/types.ts`, `web/src/styles.css`, `tests/test_planner_drafts.py`; P16. |
| D-73 | 06.11.2026 | **Zielbeschriftung und Zielpuffer haben je eine gemeinsame Quelle; Aufbauänderungen bleiben lokale Entwurfsmutationen.** Serverseitig ergänzt `format_target_label` die Zielart genau einmal vor `format_target`; Detailzeile und Diagrammsegment lesen denselben Text. Pace- und Watt-Ziele werden über die vorhandenen Feldpuffer je Knoten-ID und Feldpfad bearbeitet; ein unfertiger oder ungültiger Zielwert setzt im Entwurf bewusst `NoTarget`, statt den alten gültigen Wert derselben Einheit stehen zu lassen. Einzelabschnitte, Verschieben, Entfernen und das Auflösen von Wiederholungsgruppen ändern ausschließlich den lokalen Entwurfsbaum; Knoten-IDs bleiben beim Verschieben stabil, neue Knoten und aufgelöste Kopien erhalten neue IDs. Ein einstufiger Undo-Snapshot hält Knoten, Feldpuffer, Endarten, Zieleditoren und Auswahl; die nächste fachliche Änderung verwirft ihn. Die Fähigkeitsmatrix bleibt bindend: Leistungszonen und absolute bpm sind nicht freigeschaltet. | Ohne eine gemeinsame Beschriftung driften Kopfzeile, Graph und Fehlertext auseinander; ohne zentrale Feldpuffer könnte ein alter Pacewert nach einem Zielwechsel unsichtbar weiter validieren. Das Auflösen darf Ablauf und Summe nicht verändern und keine gemeinsame Kind-ID weiterverwenden. Ein Undo, das zwischenzeitliche Eingaben wiederherstellt, würde spätere Änderungen löschen; deshalb genau eine Ebene und kontrolliertes Verwerfen. | `src/trainings_cockpit/planner/validation.py` (`format_target_label`), `details.py`, `profile.py`, `drafts.py`, `web/src/plannerDraft.ts`, `web/src/components/PlanEditor.tsx`, `PlanSheet.tsx`, `web/src/types.ts`, `tests/test_planner_drafts.py`; P13–P15. |
| D-81 | 06.11.2026 | **Der Planer-Leseadapter trennt berechnete Dokumentfelder von echtem unbekannten Inhalt und liest Distanzvorgaben ohne Quellenangabe als Distanz.** `workout_doc` trägt bei intervals zusätzlich von der Quelle berechnete Summen (`distance`, `duration`, `zoneTimes`, `strain_score`, `average_watts`, `normalized_power`, `variability_index`, `polarization_index`, `locales`, `options`); sie begrenzen die Editierbarkeit nicht mehr und bleiben im Roh-Snapshot. Auf Schritt-Ebene gilt: Liegen `distance` und `duration` ohne `duration_source`/`distance_source` vor, ist die Distanz die Ende-Bedingung und die Dauer die berechnete Schätzung; Zeitvorgaben liefern nur `duration`. Explizite Quellen (`estimated`, `distance`) behalten ihre bisherige Bedeutung. | Jede normale Einheit fiel sonst auf `metadataOnly` („Unbekannte Dokumentfelder“), und ein Distanz-Create meldete trotz erfolgreichem Write einen Rundlauf-Konflikt, weil intervals bei Distanzvorgaben keine Quelle setzt. Die Trennung verhindert, dass berechnete Totals als verlorener Inhalt gelten, ohne echte unbekannte Felder stillschweigend zu akzeptieren. | `src/trainings_cockpit/planner/remote.py` (`_DERIVED_DOC_FIELDS`, `_parse_end`), `tests/test_planner_remote.py`, `tests/test_planner_create.py` (`RealIntervalsFormGateway`). |
| D-82 | 06.11.2026 | **„Diese Woche“ ist ein Zustandstext, kein Navigationsziel.** Der Planer zeigt den Text nur, wenn die angezeigte Woche die aktuelle ist; in jeder anderen Woche bleibt die Zeile unter dem Wochenkopf leer. Es gibt keinen Ein-Klick-Rücksprung zur aktuellen Woche mehr; die Navigation läuft über die beiden Pfeile. Ein späterer Rücksprung müsste ein eigenes, anders beschriftetes Element sein, nicht dieser Text. | Die QA-Rückmeldung war eindeutig: Der Text stand bei jeder Woche und soll nur die aktuelle Woche bestätigen. Ein Knopf, der bei jeder Woche sichtbar ist, verletzt genau das; ein zusätzliches Rücksprung-Element würde die ruhige Wochennavigation wieder mit einer dritten Aktion füllen. Der Implementierungsplan wird an diesen drei Stellen nachgezogen. | `web/src/pages/Planner.tsx` (`WeekNavigator`), `web/src/styles.css` (`.planner-week-current`), `docs/trainingsplaner/TRAININGSPLANER_IMPLEMENTIERUNGSPLAN.md`. |
| D-83 | 06.11.2026 | **Das Distanzfeld im Planer rechnet nur in Kilometern.** Eine Zahl ohne Einheit bedeutet Kilometer, `km` ist erlaubt, eine Meterangabe wird mit klarer Meldung abgewiesen. Gespeicherte Distanzen erscheinen im Feld als km-Wert, intern bleibt Meter die kanonische Einheit. | Das Feld zeigte `1,5 km` als Beispiel, las eine nackte `1,5` aber als 1,5 Meter — zwei Deutungen für dieselbe Eingabe. Ein Standard ist eindeutig, ohne die Anzeige der gespeicherten Meter zu ändern. | `src/trainings_cockpit/planner/validation.py` (`parse_distance`), `web/src/plannerDraft.ts` (`endSeed`), `web/src/components/PlanEditor.tsx` (Label, Hinweis), `tests/test_planner_validation.py`, `tests/test_planner_drafts.py`; TB-15. |
| D-84 | 06.11.2026 | **Eine geplante Einheit wird über ihre Remote-Event-ID gelöscht; ein 404 der Quelle blockiert das Löschen nicht.** `DELETE /api/planner/plan/{event_id}` liest die lokale Planung, sendet genau einen `bulk-delete` an intervals.icu und entfernt danach die `event`-Zeile. Kennt intervals die ID nicht mehr (404), gilt die Einheit als bereits gelöscht und verschwindet trotzdem aus dem Trainingskalender. Andere Quellenfehler lassen die lokale Zeile stehen und werden als Fehler gezeigt, damit kein Löschvorgang unbemerkt nur halb ausgeführt wird. Eine zugehörige Aufzeichnung (`activity`) bleibt bestehen. Im Blatt „Geplante Einheit“ steht die Aktion als ruhender Abschnitt am Ende; sie öffnet eine Bestätigung und schreibt erst mit „Endgültig löschen“. Neue, noch nicht gespeicherte Entwürfe haben kein Löschziel. Zusätzlich spiegelt der Sync die Event-Liste: was intervals im gelesenen Zeitraum nicht mehr führt, wird lokal entfernt — dieselbe Regel wie bei den Aktivitäten (D-54). | Ohne Löschen ließe sich ein versehentlich angelegter Plan nur noch in intervals.icu entfernen, und eine dort gelöschte Einheit bliebe als toter Kalendereintrag stehen. Der 404-Sonderfall ist genau der im Ticket genannte Fall „nicht auffindbar“: er darf nicht wie ein Konflikt behandelt werden, sonst wäre die tote Zeile nicht mehr loszuwerden. Ein Delete vor der lokalen Entfernung hält den Bestand ehrlich, ein lokales Vorpreschen bei Netzfehlern würde eine remote noch vorhandene Einheit verstecken. | `src/trainings_cockpit/planner/delete.py`, `event_write.py` (`IntervalsEventAdapter.delete_event`), `service.py`, `api.py` (`DELETE /api/planner/plan/{event_id}`), `db.py` (`delete_event`, `delete_unlisted_events`), `sync.py`, `web/src/components/PlanSheet.tsx`, `web/src/pages/Planner.tsx`, `web/src/api.ts`, `web/src/types.ts`, `web/src/styles.css`, `tests/test_planner_delete.py`, `tests/test_sync.py`; TB-16. |

---

## 4. Abgeleitete Anforderungen

| ID | Aus | Anforderung | Akzeptanz | Status |
|---|---|---|---|---|
| A-01 | D-03, D-05 | Erholungskarte zeigt Score, Klartext-Erklärung und je Treiber **heute / Schnitt / üblich**. | 39 ms / 32 / 29 ist sichtbar; ein Satz erklärt den Score. | ✅ |
| A-02 | D-06 | Keine CTL/ATL/TSB/ACWR-Begriffe in der UI; deutsche Labels mit Kurzerklärung. | Kein sichtbarer Fachbegriff; „Fitness“, „Müdigkeit“, „Frische“, „Belastungsverhältnis“. | ✅ |
| A-03 | D-07 | Drei Countdowns, mobil scrollbar. | Ironman, VCM, HM mit Tagen; Ziele konfigurierbar. | ✅ |
| A-04 | D-08 | PWA-Manifest, Apple-Touch-Icon, Installationshinweis. | „Zum Home-Bildschirm“ funktioniert auf dem iPhone. | ✅ |
| A-05 | D-08 | Docker-Deployment für den Homeserver dokumentiert. | `docker compose up -d` und Backup-Anleitung. | ✅ Doku (auf dem Server ungetestet) |
| A-06 | D-10 | Modell nutzt Tageswert und 7-Tage-Schnitt, Erklärung nennt beides. | Score reagiert auf die letzte Nacht, bleibt aber stabil. | ✅ |
| A-07 | D-09 | Morgen-Check-in (Energie, Muskeln, Stress) und Abend-RPE. | Etappe 3. | ⏳ |
| A-08 | D-09 | Schlafdetails (Phasen, Konsistenz), soweit Daten vorhanden. | Etappe 3. | ⏳ |
| A-09 | D-09 | Datenqualität sichtbar (Abdeckung, Alter, Ausreißer). | Etappe 3. | ⏳ |
| A-10 | D-02 | Wirkungsanalyse: welche Einheiten bringen etwas, welche ersetzen. | Etappe 4. | ⏳ |
| A-11 | D-01 | Bevel-Plan importieren und Plan vs. Ist vergleichen. | Etappe 4. | ⏳ |
| A-12 | D-12 | Erholung nutzt HRV, Ruhepuls, Schlaf, Atmung, SpO₂; Temperatur wird ergänzt, sobald Daten da sind. | Treiber zeigen heute / Schnitt / üblich. | ✅ |
| A-13 | D-12 | Keine Belastung im Erholungswert; ein Hinweis erklärt den Zusammenhang. | „Belastung fließt nicht direkt in die Erholung“ ist sichtbar. | ✅ |
| A-14 | D-12 | Skala 68 + 20·z, 60-Tage-Referenz, Schlafziel 7:30. | Normaler Tag ≈ 68, heutiger Wert 92. | ✅ |
| A-15 | E-18 | Das Cockpit kennt keine Gerätemarke; alle Daten kommen über intervals.icu. | Coros oder anderes Gerät funktioniert ohne Codeänderung. | ✅ |
| A-16 | D-13 | Navigation zeigt Heute, Verpflegung, Aktivitäten. | Kein „Trends“-Eintrag mehr sichtbar. | ✅ |
| A-17 | D-14 | Verpflegungsseite: Modus, Dauer, Gewicht, Temperatur; Ausgabe g/h, Gesamt, Getränk, Gels, Wasser, Salz, Zeitplan, Vortag/Frühstück/danach. | Für 4 h Wettkampf kommen 90 g/h und 8 Gels heraus; für 2 h locker 45 g/h. | ✅ |
| A-18 | D-14 | Ab 60 g/h weist die Seite auf Glukose-Fruktose-Mischung hin. | Hinweis sichtbar, sobald die Rate über 60 liegt. | ✅ |
| A-19 | D-15 | Karten, Ring und Erklärung nutzen dieselbe Nacht; Kopfzeile nennt das Datum der Nacht, wenn es nicht heute ist. | Bei fehlender Nacht von heute steht „Nacht vom 30. Oktober“ und überall 7:59 h. | ✅ |
| A-20 | D-16 | Verpflegungsseite schaltet zwischen Gels und Ahornsirup um; bei Sirup stehen ml je Stunde, Shotgröße, Kohlenhydrate und Salz je Shot sowie die Gesamtmenge. | Für 4 h Wettkampf: 415 ml Sirup, 8 Shots à 50 ml, 0,74 g Salz pro Shot. | ✅ |
| A-21 | D-17 | Zeitplan bei Ahornsirup enthält nur Shots. Unpassende Shotgröße führt zu einem Vorschlag. | Bei 1:51 locker und 50 ml steht ein Shot; die Seite schlägt 25 ml mit drei Shots vor. | ✅ |
| A-22 | D-18 | „Locker“ folgt dem eigenen Praxistest, nicht dem Literaturfaktor. | 1:51 locker ergibt 40 g/h, 75 g gesamt, 85 ml Sirup. | ✅ |
| A-23 | D-19 | Shotgröße in g oder ml eingebbar, Ausgabe in derselben Einheit. | 35 g ergeben 23 g Kohlenhydrate; 35 ml ergeben 30 g. | ✅ |
| A-24 | D-20 | Erholung nutzt 21-Tage-Referenz, vollen Tageswert und 25 Punkte je SD. | Schlechte Nacht 31.10. fällt in die gelbe Ampel, 26.10. in die orange. | ✅ |
| A-25 | D-22 | Bevels Score lässt sich auf „Heute“ eintragen und überlebt einen Sync; beide Werte stehen nebeneinander. | 30.10. wir 93 / Bevel 94, 31.10. wir 65 / Bevel 51 sind sichtbar. | ✅ |
| A-26 | D-21 | Kein hrvSDNN in Modell oder Oberfläche. | Nur HRV (rMSSD) erscheint. | ✅ |
| A-27 | D-24 | Der Vault enthält keine Zahlen-Notizen; Wochen kommen aus `tc woche`. | Vault liest sich in ~8 KB; `tc woche` liefert KW 41–44 mit denselben Zahlen wie vorher die Notizen. | ✅ |
| A-28 | D-27 | Eingabefelder sind mindestens 16 px groß, öffnen die Zahlentastatur und schließen sie mit „Fertig“. | Fokus auf „Bevel heute" verändert die Seitenbreite nicht; die Schrift im Feld misst 16 px. | ✅ || A-28 | D-27 | Eingabefelder sind mindestens 16 px groß, öffnen die Zahlentastatur und schließen sie mit „Fertig“. | Fokus auf „Bevel heute" verändert die Seitenbreite nicht; die Schrift im Feld misst 16 px. | ✅ |
| A-29 | D-29 | Oberfläche folgt der Richtung B+: Tinten-Rampe, ein Teal-Akzent, Serif für Titel und Countdowns, Mono für Zahlen, Universalschrift Plex Sans. | Kein Farbschein und keine Sparkline mehr sichtbar; die Uhr trägt Zonenring und Referenzmarke; Aktivitäten stehen als Tabelle; Bündel unter 260 kB. | ✅ |

---

## 5. Etappen

| Etappe | Inhalt | Status |
|---|---|---|
| 0 | Datenzugang, Push-Kanal, Befund | ✅ abgeschlossen |
| 1 | Dashboard: Heute, Trends, Aktivitäten | ✅ abgeschlossen |
| 2 | **Klarheit:** Erholung statt Readiness, Erklärung, deutsche Begriffe, drei Countdowns, PWA | ✅ abgeschlossen |
| 2b | **Bevel-Modell:** 60-Tage-Referenz, Schlaf 50/50, Atmung, SpO₂-Abzug, keine Last | ✅ abgeschlossen |
| 2c | **Verpflegung:** Kohlenhydratrechner mit zwei Modi, Zeitplan, Herrichten | ✅ abgeschlossen |
| 3 | Check-in, Schlafdetails, Datenqualität, Plan vs. Ist | ⏳ |
| 4 | Wirkungsanalyse, Bevel-Ablösung, eigene Planung | ⏳ |

---

## 6. Nicht-Ziele (vorerst)

- Kein Multi-User, keine Cloud.
- Keine automatische Planänderung ohne Freigabe.
- Keine medizinische Diagnose.
- Kein Ersatz für intervals.icu als Kalender und Geräte-Sync.
- Keine intervals-Fachbegriffe in der Oberfläche.

---

## 7. Log

| Datum | Änderung |
|---|---|
| 30.10.2026 | Dokument angelegt, E-01 bis E-07, F-01 bis F-09 |
| 30.10.2026 | Diskussion: D-01 bis D-11, E-08 bis E-11, A-01 bis A-11, Etappen 2–4 |
| 30.10.2026 | Etappe 2 umgesetzt: Erholung mit Tageswert/Schnitt/üblich, Klartext-Erklärung, deutsche Begriffe, drei Countdowns, PWA, Deployment-Doku |
| 30.10.2026 | E-12, E-13 und F-10 (Kalibrierung) mit Vergleichsrechnung aufgenommen; Entscheidung offen |
| 30.10.2026 | Bevel-Logik dokumentiert (E-14, E-15), Pakete P1–P4 in F-11 gerechnet |
| 30.10.2026 | D-12 entschieden und umgesetzt: P1 (Bevel-Logik), Etappe 2b abgeschlossen |
| 30.10.2026 | E-16 (Zepp-API) und F-12 (Schlafscore/Phasen) aufgenommen; Entscheidung offen |
| 30.10.2026 | E-17 (CIRQA Smart Band) und F-13 (Test) aufgenommen; Entscheidung offen |
| 31.10.2026 | E-18 (Health Sync, Geräteunabhängigkeit) und E-19 (felsr als Referenz) aufgenommen |
| 31.10.2026 | D-13 (Trends entfällt) und D-14 (Verpflegungsrechner) entschieden und umgesetzt, Etappe 2c |
| 31.10.2026 | E-20 und D-15: fehlende Nacht von heute zeigt den letzten Stand, Schlafdefizit ignoriert Lücken |
| 31.10.2026 | E-21 und D-16: Ahornsirup als Quelle, Salz je Shot in Gramm |
| 31.10.2026 | D-17: Wasser fliegt aus dem Zeitplan, Shotgröße bekommt einen Vorschlag |
| 31.10.2026 | E-22 und D-18: erster Praxistest (73 g in 1:51) kalibriert „Locker“ auf 0,90 |
| 31.10.2026 | E-23 und D-19: Shotgröße in Gramm oder Milliliter, Standard Gramm |
| 31.10.2026 | E-24 und D-20: Erholung auf 21-Tage-Referenz, voller Tageswert, 25 Punkte je SD |
| 31.10.2026 | E-25: intervals.icu kann keine Schlafphasen liefern – geprüft an API und Schema |
| 31.10.2026 | E-26, D-21 und D-22: hrvSDNN verworfen, Bevel-Abgleich gebaut, sieben Tage sammeln |
| 31.10.2026 | E-27 und D-23: 8 Dubletten aus Garmin + Health Sync entfernt, Prüfung in Sync und als `tc dedupe` |
| 31.10.2026 | Cockpit läuft auf dem Homeserver (Docker, Port 8100, Cron 07:00), Sync lädt nur noch 19 Felder statt 40 |
| 31.10.2026 | E-28 und D-24: Vault auf die Urteils-Ebene reduziert, 330 Notizen entfernt, `tc woche` ersetzt die Wochen-Notizen |
| 01.11.2026 | D-25: Atmung aus der Anzeige, „gestern"-Marker für alte Werte, Sync-Knopf im mobilen Kopf, Safe-Area, Countdowns untereinander |
| 01.11.2026 | D-26 hebt D-15 und die Renormierung auf: Score nur bei vollständigen Daten von heute, sonst „Keine Daten" |
| 01.11.2026 | D-27: Eingabefelder auf 16 px gegen den Safari-Zoom, Zahlentastatur und „Fertig" schließt sie; geprüft bei 390 px Breite (keine horizontale Ausdehnung) |
| 01.11.2026 | E-29 und D-28: Oberflächenprüfung gegen *unslop* (12 Funde), Regeln als `UI-REGELN.md` festgeschrieben, ab jetzt verbindlich |
| 01.11.2026 | E-30 und D-30: Quellenlandkarte (Health Sync, Garmin, Wahoo, Zepp), Atmung nur an 27 von 61 Nächten, Quelle bleibt austauschbar |
| 01.11.2026 | D-34: Fitness und Müdigkeit aus eigener Rechnung, 365 Tage Läufe und Schwimmen aus Garmin nachgeladen (93 Einheiten) |
| 01.11.2026 | D-33: Läufe und Schwimmen direkt aus der Garmin-Personal-API, Last selbst gerechnet (R² 0,974) |
| 01.11.2026 | E-31, D-31 und D-32: Garmin filtert Kennzahlen, Referenz-Neustart beim Sensorwechsel gebaut, Last bleibt bei intervals |
| 01.11.2026 | D-40: HF-Ziele in Schlägen, Leistungsziele in Watt — Zonen, Maximalfrequenz und FTP kommen aus intervals |
| 01.11.2026 | D-38 und D-39: Startseite auf sieben Zeilen gekürzt, Kennzahlenkarten und Bevel-Abgleich raus, Aktivitäten-Tab vorerst abgehängt |
| D-80 | 06.11.2026 | **Der abgehängte Aktivitäten-Tab wird nach dem Planer-Umbau entfernt.** `pages/Activities.tsx`, `components/ActivityTable.tsx`, der zugehörige Client-Vertrag und die reine Listen-CSS entfallen. Der Planer ist der einzige Listenmodus; Aktivitätsdetails, Messreihen, Zonen, Quellen und Sportarten bleiben in `UnitSheet` erhalten, ebenso die Dashboard-Auswahl `WeekStrip`/`MetricRow`. | D-39 hielt die Seite nur für einen späteren eigenen Listenmodus vor. Mit P07/P27 ist der Kalenderwochen-Planer diese Liste; die alte Seite war über keinen Tab und keine Route erreichbar und hätte nur eine zweite, ungetestete Datenhaltung suggeriert. | `web/src/pages/Activities.tsx`, `web/src/components/ActivityTable.tsx`, `web/src/api.ts`, `web/src/types.ts`, `web/src/styles.css`; P27. |
| 01.11.2026 | E-33: Garmin-Programm in drei Stufen, Ziffer 5.1(o) trifft den Datenabfluss, nicht den Workout-Versand, Abrechnung ab 01.04.2027 |
| 01.11.2026 | E-32 und D-35 bis D-37: Startseite zeigt das Training, Einheit als Blatt mit Profil, Mobil-first verbindlich |
| 01.11.2026 | D-29: Richtung B+ gebaut und auf dem Server — neue Rampe, Serif/Mono-Schriften selbst gehostet, Instrument-Uhr, Wochenstreifen, Tabellen, recharts entfernt |
| 02.11.2026 | D-42: Wochenumfang öffnet die Liste der letzten 7 Tage, jede Einheit öffnet ihre Zusammenfassung mit Zeit in den Zonen |
| 02.11.2026 | D-43: Die Tageskarte zeigt auch Einheiten ohne Plan („Zusätzlich"), Zuordnung über `plan.matches` |
| 02.11.2026 | D-44: Atem- und Entspannungsübungen fliegen aus Karte, Wochenliste und Umfang (13 statt 15 Einheiten) |
| 03.11.2026 | D-45 bis D-48: Wochen-Tab, Verschieben in zwei Branches, Text-Editor, RPE und Gefühl — beschlossen, noch nicht gebaut |
| 03.11.2026 | D-49: Aktivitäten von Strava statt intervals, Last selbst gerechnet (Kraft 52, Rad 65/72), intervals liefert nur noch Plan und Nachtsignale |
| 03.11.2026 | D-49 ausgesetzt: Strava verlangt für die API ein Abo; Rad und Kraft bleiben vorerst bei intervals |
| 03.11.2026 | D-50: Nächte kommen ab 04.11. aus Garmin (CIRQA), Sync schreibt nur ab dem Sensorwechsel, Referenz neu |
| 03.11.2026 | D-51: erster Wert erst mit vollständiger 21-Tage-Referenz (vier Punkte Unsicherheit statt zwei), Rechenweg an 368 eigenen Nächten geprüft |
| 03.11.2026 | Cron auf dem Server entfernt: der Sync läuft nur noch, wenn der Athlet ihn im Cockpit auslöst |
| 03.11.2026 | D-52: Bevel-Feld für das Vergleichsfenster (bis 30.11.), 16-px-Regel aus D-27 wiederhergestellt |
| 04.11.2026 | D-53: Leistung, Puls und Tempo als Verlauf aus der Aufzeichnung (intervals-Streams, Garmin-FIT), im Blatt der erledigten Einheit gezeichnet |
| 04.11.2026 | D-54: der Sync entfernt Einheiten, die intervals im gesyncten Zeitraum nicht mehr führt — sonst verdrängt eine tote Zeile die lebende Aufzeichnung |
| 04.11.2026 | D-55: develop als Integrationsstrecke und Vorschau-Instanz auf dem Server (8101, Tailscale-HTTPS), Arbeitsregeln in AGENTS.md |
| 05.11.2026 | D-56: Vorschau-Bau trägt offenen Akzent-Ring, Plakette „Vorschau“, eigenen Titel, Manifest und Startbildschirm-Icon |
| 02.11.2026 | E-34 und D-41: Long Ride doppelt in der Woche (Wahoo + Health Sync), Erkennung über Gesamtzeit, Bewegungszeit oder Strecke, 18 Paare entfernt |
| 04.11.2026 | Branches aufgeräumt: `feature/leistungsgraphen` (vollständig in `main`) und `feature/strava-ist-quelle` (D-49 ausgesetzt, Inhalt als Tag `archive/strava-ist-quelle` gesichert) gelöscht, lokal und auf GitHub |
| 05.11.2026 | D-58: ohne Erholungswert zeigt die Karte HRV, Ruhepuls und Schlaf der letzten Nacht — Anzeige, kein Teilwert |
| 05.11.2026 | D-60: Score-Demo-Zustand nur im Vorschau-Bau unter `?demo=recovery`, mit Abzeichen „Demo"; der stabile Bau enthält den Zweig nicht |
| 05.11.2026 | D-61: fünfte Erholungsstufe ab 85 (`green-top`, #7ef0c0), Grenzen 85/70/50/35/0 |
| 05.11.2026 | D-62: Band aus dem angezeigten (gerundeten) Score, damit 85 auch „Sehr gut erholt" trägt |
| 05.11.2026 | D-63: Erholungskarte mit eigenem Türkis-Verlauf und dezentem Ring-Schein; mobil zweispaltiger Score, Nachtwerte dreispaltig mit Baseline-Delta |
| 05.11.2026 | D-64: Erholungskarte auf nahezu schwarzer Basis mit lokalem radialem Lichtschein statt flächigem Türkis-Verlauf; nur die dekorative Ebene ist gedimmt |
| 05.11.2026 | D-65: Ringstrich der Erholungskarte von 6 auf 8 Einheiten (4,0 → 5,4 px mit Score, 5,1 → 6,8 px ohne); Radius, Farben und Schein unverändert |
| 05.11.2026 | D-66: Kartenrampe auf nahezu schwarzes Anthrazit (#0b1318/#0e181e/#121f26), Erholung bleibt dunkelster Bezug (#080d11); Statuslabels gedämpft aus der Band-Skala, gefüllte Akzentpille entfällt; Navigation nur Icon + Label ohne Fläche |
| 05.11.2026 | D-67: positives Statuslabel und positive Trendtexte lesen denselben semantischen Text-Token `--positive`; der Band-Alias bleibt für die Skala, das Label behält die 12-%-Fläche |
| 06.11.2026 | D-68: Trainingsplaner ersetzt die Sieben-Tage-Liste und den geplanten Wochen-Tab; „Umfang“ und „Einheiten“ verlieren beide die Navigation, der Planer bekommt einen eigenen Haupttab |
| 06.11.2026 | D-69: Planungsmodell als eigenes UI-unabhängiges Paket `trainings_cockpit.planner`; typisierte Identitäten, kanonische Einheiten, `UnsupportedNode` mit Quellreferenz und Schreibgrenze nur für `WorkoutDraft` |
| 06.11.2026 | D-70: Planerzeitzone explizit (`Europe/Vienna`, `TC_TIME_ZONE`); Planerwoche Montag–Sonntag und rollierendes Dashboard-Fenster bleiben getrennte Zeitraumverträge |
| 06.11.2026 | D-71: Planungsdetails und Trainingsverlauf als reine Leseansichten; Plan-Event-ID und Aktivitätszeile getrennt, Graphdaten aus der gemeinsamen Ausführungsfolge, getrennte Zielspuren |
| 06.11.2026 | D-72: lokaler Inline-Entwurf mit Feldpuffern je Knoten-ID/Feldpfad, serverseitiger Draft-Projektion ohne Remote-Schreiben; `OpenEnd` markiert unfertige Enden in Graph und Summe, absolute bpm bleiben hinter dem Adapter-Gate |
| 06.11.2026 | D-73: gemeinsame Zielbeschriftung und Zielpuffer, lokale Aufbauänderungen mit stabilen IDs und einstufigem Undo; Leistungszonen und absolute bpm bleiben gesperrt |
| 06.11.2026 | D-74: Tages-Plus legt einen lokalen Neuen-Entwurf ohne Remote-ID an; Sportart nur als Text-Dropdown, drei vertikale Startformen, derselbe Inline-Editor und „Name & Termin“ auch für neue Entwürfe |
| 06.11.2026 | D-75: isolierter Serializer mit Create-/Metadaten-/Strukturmodus, unverändertem Workouttext bei Name/Datum, expliziten Einheiten und Rollen sowie harter Typ- und Erhaltungsgrenze; kein produktives Schreiben |
| 06.11.2026 | D-76: Speicherkoordinator mit neun getrennten Zuständen, genau einer Operation pro Einheit, unveränderlichem Snapshot, Eingabesperre und differenzierter Fehlerklassifikation; Timeout bleibt `unknown`, 404 wird nie Create |
| 06.11.2026 | D-77: Update über die ursprüngliche Event-ID mit Berechtigungsprüfung, Rücklesen und semantischem Rundlauf; fremde Antwort-ID und 404 werden nicht zu Create, unbestätigte Werte bleiben `savedUnverified` |
| 06.11.2026 | D-78: Neuanlage mit stabiler externer Identität aus Account/Athlet/lokaler Plan-ID, tatsächlicher Remote-ID aus der Antwort und lesender Reconciliation nach unklarem Create; kein automatischer Retry, keine erfundene Aktivitätsbeziehung |
| 06.11.2026 | D-79: Produkt-Speichern über `…/save` mit Vorabvergleich gegen die Basis (Löschung, Berechtigung und Struktur als getrennte Konflikte), dauerhafter Vorgangszuordnung in SQLite über Reload, bestätigter Übernahme über die tatsächliche Event-ID und einer gemeinsamen Revision für Woche, Details, Dashboard und Vorschau; ohne belegte atomare Vorbedingung keine Last-Write-Wins-Aktion, sondern die drei Konfliktwege aus 9.8 |
| 06.11.2026 | D-80: abgehängten Aktivitäten-Tab entfernt; Planer ist der einzige Listenmodus, Aktivitätsdetails und Dashboard-Selektoren bleiben erhalten |
| 06.11.2026 | D-81: Planer liest berechnete `workout_doc`-Summen als nicht einschränkend und Distanz plus berechnete Dauer ohne Quelle als Distanz; die Dokumentfelder-Warnung und der falsche Rundlauf-Konflikt entfallen |
| 06.11.2026 | D-82: „Diese Woche“ ist ein Zustandstext nur für die aktuelle Woche; in anderen Wochen entfällt die Zeile, der Rücksprung läuft bewusst nicht mehr über diesen Text |
| 06.11.2026 | D-83: Distanzfeld im Planer rechnet nur in Kilometern; Zahl ohne Einheit = km, Meterangaben werden abgewiesen, Feldanzeige in km |
| 06.11.2026 | D-84: geplante Einheiten per `DELETE /api/planner/plan/{id}` löschen; Remote-Delete zuerst, 404 entfernt trotzdem lokal, andere Quellenfehler lassen die Zeile stehen; Sync entfernt nicht mehr geführte Events |
| 06.11.2026 | Planer-QA: Terminfeld ist auf die Maße des Namensfelds begrenzt (WebKit-Härtung, lokal in Blink geprüft); „Diese Woche“ steht nur in der aktuellen Woche, sonst entfällt die Zeile ganz |
