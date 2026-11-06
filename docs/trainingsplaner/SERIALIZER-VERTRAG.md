# Serializer-Vertrag P17

**Stand:** 06.11.2026  
**Modul:** `src/trainings_cockpit/planner/serializer.py`  
**Grenze:** `WorkoutDraft` → `PreparedWrite`; kein Netzwerkaufruf, kein
produktives Schreiben.

## 1. Welche Remote-Felder der Editor kontrolliert

| Feld | Create | Update | Bedingung |
|---|---|---|---|
| `category` | ja, immer `WORKOUT` | nein | nur Neuanlage |
| `type` | ja, aktuelle Sportart | nein | Sportart bestehender Einheiten ist gesperrt |
| `name` | ja | nur bei Namensänderung | Event-Name, nie Workout-Syntax |
| `start_date_local` | ja | nur bei Terminänderung | lokales Datum, vorhandene Uhrzeit bleibt erhalten |
| `description` | ja, kanonischer Workouttext | nur bei Strukturänderung | reine Name-/Datumsänderung lässt den Text unangetastet |
| `external_id` | ja, stabil aus lokaler Plan-ID, Account und Athlet | nein | nur Neuanlage; Update lässt die vorhandene Identität unberührt |

Nicht kontrolliert und beim Update nicht überschrieben: `id`, `external_id`,
`workout_doc`, `moving_time`, `distance`, `icu_training_load`,
`icu_intensity`, Event-`notes` und fremde Schlüssel. Daraus berechnete
Remote-Felder werden nie selbst erzeugt. `PreparedWrite.payload` enthält
ausschließlich die oben genannten Felder; interne Knoten-IDs, Demo-IDs und
lokale Projektionen bleiben draußen.

## 2. Modi

- **`create`** — `base is None`, keine Remote-ID. Payload mit `category`,
  `type`, `name`, `start_date_local`, `description` und `external_id`. Die
  externe Identität ist deterministisch aus lokaler Plan-ID, Account und
  Athlet abgeleitet; derselbe Entwurf erzeugt bei einem Retry dieselbe ID,
  zwei getrennte Entwürfe bleiben getrennt.
- **`metadata`** — bestehende Remote-ID, nur `name` und/oder
  `start_date_local` geändert. `description` fehlt im Payload; der vorhandene
  Workouttext bleibt byte-for-byte erhalten.
- **`structure`** — bestehende Remote-ID, `nodes` geändert. Payload enthält
  zusätzlich `description`; `name`/`start_date_local` nur, wenn sie sich
  ebenfalls geändert haben.
- **`NoWriteNeeded`** — keine fachliche Änderung; kein Payload.

## 3. Workouttext

Der Serializer erzeugt aus dem geprüften Modell:

- Einzelabschnitte mit Zeit (`45m`, `1h30m`, `30s`) oder Distanz (`400mtr`,
  nie `400m`).
- HF-Zonen als `Z2 HR`, Pace-Zonen als `Z2 Pace`; Leistungszonen sind gesperrt.
- Pace als `5:30/km Pace` beziehungsweise `2:00/100m Pace`; die Referenzstrecke
  ist immer ausgeschrieben.
- Watt als `160-170w`, `% FTP` als `90%`, `0w` bleibt ein gültiger Wert.
- Einfache Wiederholungen als `4x`-Block mit Gruppenname, sofern er sicher ist.
- Rollen als `intensity=warmup`, `intensity=active`, `intensity=rest`,
  `intensity=cooldown`. `steady` bleibt ohne Tag.

## 4. Bewusst abgelehnt

Vor der Payload-Erzeugung mit konkretem Grund abgelehnt werden:

- leere Aufbauten, leere Wiederholungsgruppen, offene Enden,
- `UnsupportedNode` und unbekannte Dokumentinhalte,
- absolute bpm-Ziele (kein belegter Schreibvertrag),
- Leistungszonen und benutzerdefinierte Zonen,
- verschachtelte Wiederholungen und `skip_final_recovery`,
- Schrittnotizen und Workout-Dokumentnotizen bei Strukturänderungen,
- nicht ganzzahlige Sekunden/Meter, die das Format nicht verlustfrei trägt,
- Schrittnamen mit Zeilenumbruch, reserviertem Konstrukt oder einer
  Zeit-/Distanz-/Paceangabe, die der Parser als Feld lesen würde,
- Aktivitätsreferenzen, Listenprojektionen, fremde Objekte und jede gleiche
  numerische ID, die den Objekttyp wechseln würde.

Event-`notes` bleiben bei Metadatenänderungen erhalten, weil `description`
nicht im Payload steht. Stehen Notizen dagegen im `workout_doc`, wird eine
Strukturänderung abgelehnt, statt sie still zu verlieren.

## 5. Nachweis

`tests/test_planner_serializer.py` prüft F01–F07, die Syntaxfallen aus
Abschnitt 8 (Meter/Minuten, Pace-Referenz, Rollen, relative Ziele,
Wiederholungen, Erhaltung), die Typgrenze und die Abwesenheit von Node-,
Demo- und berechneten Remote-Feldern.
