# Planer-Fixtures

Diese Dateien sind **Testdaten**, keine Produktivtrainings und keine
Trainingsempfehlungen. Namen, IDs, Zeiten und Leistungswerte sind erfunden.
Die Fixtures hängen nicht von zufälligen aktuellen Nutzertrainings ab und
enthalten keine Zugangsdaten.

## Aufbau

| Pfad | Zweck |
|---|---|
| `cases/f01…f15-*.json` | Fachliche Fälle aus Abschnitt 11 des Implementierungsplans. |
| `remote/*.json` | Anonymisierte Remote-Beispiele für einfache Einheit, Wiederholung, Distanzabschnitt und unbekannten Inhalt. |
| `profiles.json` | Synthetische Sportprofile mit expliziten HF-, Pace- und Leistungszonen. |
| `capability-matrix.json` | Maschinenlesbare Fähigkeitsmatrix aus Abschnitt 8.4. |

## Regeln

- `case` entspricht dem Fall aus dem Plan (`F01` … `F15`).
- `kind` benennt die Datenart; nicht jeder Fall ist ein einzelnes Workout.
- `expected` ist die fachliche Erwartung. Neue Fälle müssen diese Erwartung
  ausdrücklich tragen, nicht nur Rohdaten ablegen.
- `sourceRef` zeigt auf die Stelle im erhaltenen Remote-Rohdatenbaum. Die
  Referenz ist kein Schreibfeld.
- Zonen-IDs sind Strings. Der sichtbare Name (`Z2`, `Sweetspot`) ist nicht die
  Identität.
- Unbekannte Inhalte bleiben im Rohsnapshot und werden als
  `UnsupportedNode` abgebildet; sie werden nicht stillschweigend entfernt.
- Ein `remoteFixture: null` bedeutet: Der Fall ist fachlich beschrieben, aber
  es gibt (noch) kein anonymisiertes Remote-Beispiel dafür. Das ist kein
  Beweis einer Adapterfähigkeit.

## Bezug

- Fachmodell und Identitäten: P02, `trainings_cockpit.planner`.
- Remote-Adapter: P04; erst dort entsteht die Abbildung von
  `workout_doc.steps` auf dieses Modell.
- Fähigkeitsmatrix: `docs/trainingsplaner/FAEHIGKEITSMATRIX.md`.
