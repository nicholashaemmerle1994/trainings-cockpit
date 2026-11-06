# Fähigkeitsmatrix — vorhandener Intervals-Adapter

**Stand:** 06.11.2026 · **Paket:** P01 · **Grundlage:** Abschnitt 8.4 des
Implementierungsplans und der tatsächliche Code auf `feature/trainingsplaner`.

Die maschinenlesbare Fassung liegt in
`tests/fixtures/planner/capability-matrix.json`; die Tests prüfen Statuswerte,
Vollständigkeit und den fehlenden Nachweis bei jeder offenen Schreibfähigkeit.
„Darstellen“ bedeutet hier **nicht** automatisch „sicher speicherbar“.

## Befund des vorhandenen Adapters

| Befund | Beleg | Status |
|---|---|---|
| Kalender-Events lesen | `IntervalsClient.events()` → `GET /athlete/{id}/events`; `db.upsert_events()` erhält das Roh-JSON in `event.raw` | belegt |
| `workout_doc` lesen | `plan.parse_workout()` liest `workout_doc.steps`, klappt Wiederholungen auf, wählt aber genau ein Ziel und verliert die Ende-Bedingung als Typ | offen |
| Produkt-Schreibweg | Kein API-Mutationsendpunkt, kein Serializer, kein gezieltes Update, keine Konflikterkennung; `tc push-test` ist nur ein CLI-Test über Bulk-Upsert | offen |
| Gezieltes Event-Update | `PUT /athlete/{id}/events/{eventId}` ist dokumentiert, im Client aber nicht implementiert | offen |
| Plan-/Aktivitätsbeziehung | Keine explizite Beziehung; `plan.matches()` ist eine Heuristik ohne Abschlussnachweis | offen |
| Kanonische Mehrquellen-Aktivität | Dedupe löscht den Verlierer; keine dauerhafte Zuordnung mehrerer Quell-IDs | offen |

## Matrix

| Fähigkeit | Lesen | Darstellen | Bearbeiten | Rückschreiben | Fehlender Nachweis (Schreiben/Editieren) |
|---|---|---|---|---|---|
| Zeitabschnitte | belegt | belegt | offen | offen | Gezieltes Event-Update und Serializer-Rundlauf für Dauer fehlen. |
| Distanzabschnitte | belegt | offen | offen | offen | Meter als Distanz schreiben und zurücklesen; vorhandene Diagrammachse ist zeitbasiert. |
| Einfache Wiederholungen | belegt | belegt | offen | offen | Rundlauf für Anzahl, Reihenfolge und Gruppensemantik fehlt. |
| HF-Standardzonen | belegt | belegt | offen | offen | Schreibbeleg für Zonenreferenz samt Zonenmodell fehlt. |
| Absolute Pace und Pacebereich | belegt | offen | offen | offen | Explizite Einheit `/km` bzw. `/100m` und passende Anzeige fehlen. |
| Watt und Wattbereich | belegt | belegt | offen | offen | Schreib-/Rücklesebeleg für Wattbereich und die gültige Vorgabe `0 W` fehlt. |
| % FTP | belegt | belegt | offen | offen | Beleg, dass relative Semantik beim Schreiben erhalten bleibt, fehlt. |
| Leistungszonen | offen | offen | offen | offen | Parser kennt nur `start/end`; Leistungszonen-Ziel mit String-ID und Zonenmodell fehlt. |
| Absolute bpm-Werte | offen | offen | offen | offen | Kein eindeutiger aktueller Schreibbeleg; vorhandener Parser deutet `hr` ohne Zonenkennung als Prozent. |
| Benutzerdefinierte Zonen | offen | offen | offen | offen | Ganzzahl-Zonen im Parser; nichtnumerische String-IDs und Zonenmodell fehlen. |
| Mehrere Ziele in einem Schritt | nicht unterstützt | nicht unterstützt | offen | nicht unterstützt | Parser wählt genau ein Ziel (Leistung → HF → Pace); Rohsnapshot erhält den Rest, Strukturbearbeitung bleibt gesperrt. |
| Rampen, Lap-Taste, Spezialschritte | nicht unterstützt | nicht unterstützt | offen | nicht unterstützt | Werden ignoriert; P04 muss sie als unbekannte Knoten mit Quellreferenz erhalten. |
| Verschachtelte Wiederholungen | offen | offen | offen | offen | Stille Kappung bei Tiefe 4 und 30 Wiederholungen; Schreibbeleg für verschachtelte Gruppen fehlt. |
| Globale Zielpriorität | offen | offen | offen | offen | Konkretes Workout-weites Ziel-/Prioritätsfeld und zulässige Werte sind nicht belegt. |

## Konsequenz für P02

Das in P02 ergänzte Planungsmodell kann diese Fälle **darstellen** und
unbekannte Inhalte als `UnsupportedNode` mit Quellreferenz erhalten. Es
behauptet keine Schreibfähigkeit. Der Schreibkoordinator nimmt ausschließlich
einen geplanten `WorkoutDraft` an; eine Aktivitätsreferenz oder ein
generisches „Training speichern“ erreicht den Event-Schreibpfad nicht.

Offene Schreibfähigkeiten bleiben bis zu ihrem jeweiligen Rundlaufnachweis
gesperrt. Insbesondere absolute bpm-Ziele, benutzerdefinierte Zonen,
Leistungszonen, verschachtelte Wiederholungen und die globale Zielpriorität
dürfen nicht durch eine erfundene Text- oder JSON-Syntax freigeschaltet werden.
