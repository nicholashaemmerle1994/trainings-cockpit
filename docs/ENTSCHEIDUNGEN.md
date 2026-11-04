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

| D-35 | 01.11.2026 | **Mobil ist die Referenz, nicht der Notfall.** Jeder Bildschirm wird zuerst auf 390 × 844 gebaut und dort geprüft; der breite Schirm ist die Erweiterung. Kein Layout, das auf dem Handy scrollt, um zwei Spalten zu retten, keine Fläche, die nur mit Maus funktioniert, Tap-Ziele mindestens 40 px hoch, Bedienung mit dem Daumen im unteren Drittel. | Das Cockpit wird fast immer am iPhone benutzt, oft in der Hand, oft vor oder nach dem Training. Ein Entwurf, der am Rechner entsteht und dann schrumpft, trägt dort nicht. | Entwürfe als Handy-Mockup, Prüfung bei 390 px vor jedem Commit, `Mobile-first` als erster Punkt in `UI-REGELN.md`. |
| D-36 | 01.11.2026 | **Die Startseite zeigt das Training.** „Frische“ als Kennzahl, das Diagramm „Belastung & Frische“ und die Liste „Letzte Aktivitäten“ verlassen die Startseite. An ihre Stelle tritt die Karte **Training** mit den Einheiten von heute und morgen; jede Zeile öffnet die Einheit. Erholung, Treiber, Schlaf/HRV/Ruhepuls, Bevel-Abgleich und die Wochenkarte bleiben. | Rückblick beantwortet die Morgenfrage nicht. Die Zahlen bleiben in der Datenbank und in der Wochenkarte; die Liste der Einheiten lebt auf der Seite Aktivitäten weiter. | Neue Felder `sessions` in `/api/overview`, neue Karte in `Today.tsx`, `LoadChart` und `ActivityTable`-Nutzung auf „Heute“ entfallen. |
| D-37 | 01.11.2026 | **Die Einheit ist ein Blatt mit Profil** (Variante 2 aus dem Mockup): geplanter Verlauf zuerst, darunter Dauer · Distanz · Last, Aufbau, Verpflegung, bei erledigten Einheiten „Geplant · gemacht“. Dauer und Distanz stehen beide, das Ziel der Einheit führt; der fehlende Wert bekommt ein **≈** und wird aus dem eigenen Median der letzten 90 Tage geschätzt (Rad 24 km/h, Lauf 8,6 km/h, Schwimmen 2,6 km/h). Kohlenhydrate erst ab 60 Minuten, aus `fuel.py`. Kein Coach-Text, keine Empfehlung. | Der Athlet will sehen, was die Einheit verlangt, nicht was jemand dazu meint. Die Schätzung ist aus dem eigenen Fahrtenbuch abgeleitet und damit nachprüfbar; erfundene Zahlen sind verboten. | Neue Tabelle `event` mit `raw` (Schritte, Zonen), neues Modul `plan.py`, `GET /api/session/{id}`, Overlay `SessionSheet` mit `SessionProfile`. |

| D-55 | 04.11.2026 | **`develop` ist die Integrationsstrecke, `main` die Abnahme.** Jedes Ticket arbeitet auf einem Feature-Branch von `main`; freigegeben wird nach `develop`, und `develop` läuft auf dem Homeserver als eigene Vorschau-Instanz (Port 8101, eigenes Image, eigene Kopie der Datenbank). Nach `main` kommt ein Stand erst nach der Abnahme am Handy und im Browser. | Bisher gab es nur `main`: jede Änderung war sofort produktiv, ohne Zwischenstufe zum Ansehen. Getestet wurde damit am Produktivstand — ein Fehler war sofort sichtbar, aber nicht mehr rückholbar. | Branch `develop`, `docker-compose.develop.yml`, `docs/DEPLOY-DEVELOP.md`, Tailscale-Serve auf Port 8443; `AGENTS.md` im Repo hält die Regeln für Menschen und Agenten fest. |
| D-54 | 04.11.2026 | **Der Sync spiegelt die Aktivitätenliste von intervals.** Für den gesyncten Zeitraum gilt: was intervals nicht mehr führt, verschwindet auch aus dem Cockpit — und zwar **vor** der Dublettenprüfung. Bisher blieb eine dort gelöschte Zeile einfach stehen; weil die Prüfung die beiden Aufzeichnungen vergleicht, hielt sie die tote Wahoo-Zeile für die bessere und entfernte die lebende Health-Sync-Zeile. Ergebnis: eine Einheit, deren Sekundenwerte niemand mehr liefern kann. | Zwei Zeilen aus derselben Fahrt, eine davon in intervals gelöscht: die Woche zeigte die tote, die lebende fehlte, und der Verlauf war leer (D-53). Die Quelle ist die Wahrheit, nicht unser Bestand. | `db.delete_unlisted` je Sync über den gesyncten Zeitraum, Verläufe verschwinden mit ihrer Zeile (Fremdschlüssel), das Sync-Log nennt `verwaist=n`. Nichts außerhalb des gesyncten Zeitraums wird angefasst. |
| D-53 | 04.11.2026 | **Jede erledigte Einheit zeigt ihren Verlauf — aus der Aufzeichnung selbst.** Die Sekundenwerte kommen mit dem Sync in die Datenbank: für Einheiten aus intervals über `/activity/{id}/streams`, für Einheiten aus Garmin aus dem FIT der Originalaufzeichnung (`download_activity`, gelesen mit `fitparse`). Abgelegt wird je Einheit **eine** Reihe mit Zeit, Leistung, Puls, Tempo und Strecke in 5-Sekunden-Mitteln — feiner als jeder Bildschirm, gröber als die Aufzeichnung. Geholt wird beim Sync nur für die **letzten 14 Tage** und nur, was fehlt; ein Verlauf, den die Quelle nicht hat, wird nicht erfunden (D-37). Gezeichnet wird im Einheiten-Blatt: **Rad die Leistung** mit FTP-Linie, **Lauf das Tempo** (Achse umgedreht, schneller ist oben), **der Puls als zweite, ruhigere Linie** in beiden Fällen; Schwimmen und Kraft zeigen nur den Puls. Ausgeliefert werden höchstens 180 Punkte. **Hebt den Halbsatz aus D-42 auf** („kein Verlaufsprofil") — er entstand aus der Not: damals lagen keine Sekundenwerte in der Datenbank. | Ein Durchschnitt beantwortet die Frage nach der Einheit nicht: ob die drei Blöcke eines 3 × 10 min standen oder der erste zu hart war und der dritte einbrach, sieht man nur im Verlauf. Die Aufzeichnung gibt es, sie wurde nur nie abgeholt — und für Läufe liegt sie bei Garmin, für Rad und Kraft bei intervals. | Neue Tabelle `activity_stream`, Modul `streams.py`, `IntervalsClient.streams`, Feld `series` in `GET /api/unit/{row_id}` und im Ist-Teil von `GET /api/session/{id}`, Komponente `WorkoutChart` in `UnitSheet` und `SessionSheet`. Neue Abhängigkeit `fitparse`. |
| D-34 | 01.11.2026 | **Fitness und Müdigkeit rechnet das Cockpit selbst.** Bisher wurden die Tageswerte `ctl`/`atl` aus intervals übernommen. Seit die Läufe über die Personal API kommen, kennt intervals diese Einheiten nicht mehr — seine Form würde ab dem Sensorwechsel systematisch zu niedrig stehen. Ab jetzt zählt die eigene Rechnung (EWMA 42/7 Tage) über die eigenen Aktivitäten. | Ein Wert, der auf einem fremden, unvollständigen Datensatz beruht, ist schlimmer als eine eigene Rechnung, die man erklären kann. | `daily_days` ignoriert die übernommenen Werte; die Last kommt aus `load.py` (Garmin) bzw. intervals (Kraft, Rad). |

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
| 02.11.2026 | E-34 und D-41: Long Ride doppelt in der Woche (Wahoo + Health Sync), Erkennung über Gesamtzeit, Bewegungszeit oder Strecke, 18 Paare entfernt |
| 04.11.2026 | Branches aufgeräumt: `feature/leistungsgraphen` (vollständig in `main`) und `feature/strava-ist-quelle` (D-49 ausgesetzt, Inhalt als Tag `archive/strava-ist-quelle` gesichert) gelöscht, lokal und auf GitHub |
