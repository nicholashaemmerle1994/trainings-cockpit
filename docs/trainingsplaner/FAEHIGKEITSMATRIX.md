# Fähigkeitsmatrix — finaler Stand P26/P27

**Stand:** 06.11.2026 · **Pakete:** P26/P27 · **Grundlage:** Abschnitt 8.4 des
Implementierungsplans, der tatsächliche Code und die kontrollierten
Adaptertests.

Die maschinenlesbare Fassung liegt in
`tests/fixtures/planner/capability-matrix.json`. Die Tests prüfen Statuswerte,
Vollständigkeit und den fehlenden Nachweis bei offenen beziehungsweise
gesperrten Schreibfähigkeiten.

## Statuswerte

| Status | Bedeutung |
|---|---|
| **belegt** | Der Pfad ist im Code vorhanden und durch Fixtures/Vertragstests geprüft. Beim Schreiben heißt das: Serializer plus kontrollierter Adapterrundlauf, **nicht** ein Live-Zugriff gegen intervals.icu. |
| **offen** | Der Pfad ist fachlich vorgesehen, aber nicht vollständig belegt. |
| **nicht unterstützt** | Der vorhandene Vertrag bildet den Fall ausdrücklich nicht ab; unbekannte Inhalte bleiben als Rohsnapshot/`UnsupportedNode` erhalten. |
| **gesperrt** | Die Fähigkeit ist bewusst nicht freigeschaltet, weil ein sicherer Schreib-/Rückleseweg fehlt. |

**Live-Grenze:** Es gab keinen produktiven Schreibzugriff und keinen
Live-Rundlauf gegen intervals.icu. Ohne ausdrücklich vorgesehenen Testdatensatz
und Freigabe bleibt diese Gegenprobe offen. Die Schreibspalte „belegt“ stützt
sich auf den lokalen Kontrolladapter, den Produkt-Endpunkt, die
Vorgangspersistenz und die Rückleseprüfung.

## Matrix

| Fähigkeit | Lesen | Darstellen | Bearbeiten | Rückschreiben | Beleg / verbleibende Grenze |
|---|---|---|---|---|---|
| Zeitabschnitte | belegt | belegt | belegt | **belegt** | Serializer, F01/F02, Create-/Update-Rundlauf im kontrollierten Adapter; Live-Gegenprobe offen. |
| Distanzabschnitte | belegt | belegt | belegt | **belegt** | Distanzachse, `mtr`-Serialisierung, F04; 400 Meter werden nie zu 400 Minuten. |
| Einfache Wiederholungen | belegt | belegt | belegt | **belegt** | F02-Gruppe, Rollen, Reihenfolge und Auflösen; Update-Rundlauf im kontrollierten Adapter. |
| HF-Standardzonen | belegt | belegt | belegt | **belegt** | Zonen aus dem tatsächlichen Sportprofil, `Z2 HR`; F01/F02. |
| Absolute Pace und Pacebereich | belegt | belegt | belegt | **belegt** | Explizite Einheit `/km` bzw. `/100m`, Bereichsrichtung; F02/F04/F05. |
| Watt und Wattbereich | belegt | belegt | belegt | **belegt** | Watt-Einzelwert und -Bereich; `0 W` bleibt gültig; F03. |
| `% FTP` | belegt | belegt | belegt | **belegt** | Relative Semantik bleibt beim Serialisieren erhalten; F03. |
| Leistungszonen | offen | offen | gesperrt | **gesperrt** | Der Parser liest Leistung nur als `start`/`end`; String-Zonenreferenz und Zonenmodell fehlen. Die UI bietet die Zielart nur als „nicht belegt“ an. |
| Absolute bpm-Werte | offen | offen | gesperrt | **gesperrt** | Kein eindeutiger aktueller Schreibbeleg. `150bpm` wird nicht als Textsyntax erfunden. |
| Benutzerdefinierte Zonen | offen | offen | gesperrt | **gesperrt** | Standardzonen werden gelesen; nichtnumerische String-IDs und das vollständige Zonenmodell fehlen. |
| Mehrere Ziele in einem Schritt | nicht unterstützt | nicht unterstützt | gesperrt | **nicht unterstützt** | Import bleibt als `UnsupportedNode` samt Rohsnapshot erhalten; keine Strukturbearbeitung. |
| Rampen, Lap-Taste, Spezialschritte | nicht unterstützt | nicht unterstützt | gesperrt | **nicht unterstützt** | Keine verlustbehaftete Vereinfachung; Erhalt als unbekannter Knoten mit Quellreferenz. |
| Verschachtelte Wiederholungen | offen | offen | gesperrt | **gesperrt** | Der Reader erkennt Verschachtelung und begrenzt die Editierbarkeit; der Editor öffnet eine Ebene. Kein Schreibbeleg. |
| Globale Zielpriorität | offen | offen | gesperrt | **gesperrt** | Ein Workout-weites Ziel-/Prioritätsfeld ist im vorhandenen Vertrag nicht belegt. |
| Letzte Erholung auslassen (als Gruppe) | belegt | belegt | belegt | **gesperrt** | Lokal 34 min und neun Ausführungen; das bewusste Auflösen in Einzelabschnitte ist speicherbar. Die Gruppe selbst wird vor der Payload-Erzeugung mit konkretem Grund abgelehnt, weil `EditorShapeMetadata` noch keinen lesenden Konsumenten hat. |

## Schreibweg, der tatsächlich existiert

- `POST /api/planner/plan/{event_id}/save` — bestätigtes Update über die
  ursprüngliche Event-ID.
- `POST /api/planner/draft/save` — bestätigte Neuanlage über den vorhandenen
  Bulk-Upsert mit stabiler `external_id`.
- `GET /api/planner/plan/{event_id}/remote` — aktuelle Remoteversion lesen und
  lokal einsortieren; kein Event-Write.
- `GET /api/planner/operations` und
  `POST /api/planner/operations/{id}/reconcile` — offene Vorgänge und lesender
  Abgleich. Ein bestätigter Reconcile wird lokal einsortiert (P26-Fix); ein 404
  der bekannten Remote-ID ohne externen Treffer beendet den Vorgang endgültig
  als `failed` (D-86).
- Update und Create prüfen den zurückgelesenen Aufbau semantisch. Ein
  fehlgeschlagenes Rücklesen bleibt `savedUnverified`; es gibt keinen
  automatischen zweiten Write.

## Verbleibende Einschränkungen

- **Skip-Gruppe:** „Letzte Erholung auslassen“ ist als Gruppe nicht
  serialisierbar. Die sichere Alternative ist das Auflösen in
  Einzelabschnitte. Der Metadatenweg aus Abschnitt 8.10 ist vorbereitet
  gespeichert, aber noch nicht beim Lesen angebunden.
- **Live-Rundlauf:** Alle Schreibbelege stammen aus kontrollierten Adaptern.
  Eine echte intervals.icu-Gegenprobe mit einem dafür vorgesehenen
  Testdatensatz und Freigabe steht aus.
- **Plan-/Aktivitätsbeziehung:** Seit D-85 führt `plan_link` manuell bestätigte
  und ausdrücklich getrennte Paare dauerhaft. Die Wochenanzeige verbindet eine
  Planung und eine Aufzeichnung automatisch nur, wenn sie am selben Tag
  dieselbe Sportart (bekannte Varianten zusammengefasst) haben und die einzigen
  offenen Einheiten sind; automatische Paare werden beim Lesen berechnet und
  nicht gespeichert. Mehrdeutige Fälle ordnet der Athlet im Einheiten-Blatt zu.
  Ein Link erzeugt keinen Event-Write.
- **Konflikte:** Der Vorab-GET und der PUT sind keine atomare Vorbedingung.
  Die Restlücke ist in `KONFLIKTE.md` dokumentiert.
- **Ältere Wochen/Pagination:** Die intervals-Abfrage nutzt einen
  Datumsbereich und keine Seiten-/Cursor-Schleife. Bei Events ist `limit`
  nicht gesetzt (API: „default is all“); eine serverseitige Kappung könnte die
  aktuelle Implementierung nicht erkennen. Garmin lädt Aktivitäten in
  100er-Seiten bis maximal 1000. Die historische Verfügbarkeit endet dort, wo
  der lokale Sync sie hinterlässt (Standard: Rückstand seit dem letzten Lauf,
  Erstlauf 365 Tage, API maximal 730 Tage; Events zusätzlich 365 Tage voraus).
- **Geräteübertragung:** Ein gespeicherter Plan belegt nur den Write nach
  intervals.icu, nicht die Übertragung auf ein Gerät.

## Bezug

- Fachmodell und Identitäten: `src/trainings_cockpit/planner/`.
- Serializer: `src/trainings_cockpit/planner/serializer.py`,
  `docs/trainingsplaner/SERIALIZER-VERTRAG.md`.
- Sync/Konflikte: `docs/trainingsplaner/SYNC.md`,
  `docs/trainingsplaner/KONFLIKTE.md`, `docs/trainingsplaner/VORGAENGE.md`.
- Abnahme: `docs/training-planner-progress.md` (P26/P27) und
  `docs/trainingsplaner/UEBERGABE.md`.
