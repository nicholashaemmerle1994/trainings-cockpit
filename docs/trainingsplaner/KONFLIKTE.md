# Konflikte und externe Änderungen — P21

**Stand:** 06.11.2026 · **Paket:** P21 · **Grundlage:** Abschnitt 9.8 des
Implementierungsplans, Fall F10.

## 1. Vergleichsprojektion

Der Vergleich arbeitet nicht auf dem kompletten Event-JSON. Abgeleitete
Remote-Felder, Abrufzeitpunkte, interne Knoten-IDs, lokale Plan-IDs und reine
Darstellungs-Metadaten erzeugen keinen Konflikt. Verglichen werden ausschließlich
die fachlich bearbeitbaren Inhalte:

| Feld | Bedeutung |
|---|---|
| `name` | Name der geplanten Einheit |
| `sport` | Sportart; eine Änderung wird wie eine Strukturänderung behandelt |
| `date`, `local_time` | lokaler Termin und Uhrzeit |
| `notes` | tatsächlich vorhandene Remote-Notizen |
| `structure` | Reihenfolge, Gruppen, Rollen, Ende-Bedingungen und Ziele |

Die Normalisierung liegt gemeinsam in `planner/shapes.py` und wird von
Konfliktvergleich und Rundlaufprüfung verwendet. Notizen werden mit den im
Basissnapshot tatsächlich vorhandenen Remote-Notizen verglichen
(`SaveSnapshot.base_notes`), nicht mit einer rein lokalen Fixture-Notiz.

Rollen werden so gelesen, wie der Serializer sie schreibt: Ein
`intensity`-Tag ist maßgeblich; für `steady` leitet `role_from_name` dieselbe
Rolle aus dem Abschnittsnamen ab, die der Leseadapter sieht (D-98). Namen sind
damit nur dort Rollenbeleg, wo die Quelle keinen Tag liefert.

## 2. Vorhandene atomare Vorbedingung

Der vorhandene `IntervalsClient.update_event()` sendet ein normales
`PUT /athlete/{id}/events/{eventId}`. Ein `If-Match`, eine Versionsnummer oder
ein anderer vom Server geprüfter SchreibVergleich ist im Repository **nicht
belegt** und wird deshalb nicht verwendet und nicht versprochen.

Der Produktpfad liest daher unmittelbar vor dem Write:

1. aktuelles Remote-Event über die ursprüngliche Event-ID lesen,
2. externe Löschung (404) und Schreibrecht zuerst einordnen,
3. relevante Inhalte mit der Basis vergleichen,
4. bei Abweichung den Write blockieren und den Konflikt zurückgeben,
5. sonst denselben Payload an dieselbe Event-ID senden.

**Restlücke:** Zwischen diesem GET und dem PUT kann eine weitere externe
Änderung eintreffen. Ohne serverseitige Vorbedingung ist das nicht vollständig
auszuschließen. Der Vorabvergleich reduziert das Risiko, ersetzt aber keine
atomare Konkurrenzsicherung. Ein 409/412 der Quelle wird zusätzlich als Konflikt
behandelt.

## 3. Getrennte Konfliktursachen

| Art | Auslöser | Verhalten |
|---|---|---|
| `deleted` | Remote-Read liefert 404 | Konflikt, kein Create, Entwurf bleibt |
| `permission` | Remote meldet `read_only`, oder ein Struktur-Write trifft eine nur metadaten-editierbare Einheit | Konflikt, kein Write |
| `structure` | Remote-Aufbau, Sportart oder Zielstruktur weicht ab | Konflikt, keine generische Baumverschmelzung |
| `metadata` | nur Name, Termin, Uhrzeit oder Notizen weichen ab | Konflikt, keine automatische Übernahme |
| `identity` | externe Identität der Remote-Einheit weicht ab | Konflikt, keine Zuordnung |

Eine externe Löschung wird nie als Auftrag zur Wiederanlage verstanden. Ein
fehlgeschlagenes Update fällt nie in einen Create zurück. Ein Konflikt bewahrt
den lokalen Entwurf und die neuere Remote-Fassung als getrennte Datenstände.

## 4. Minimale Nutzeraktionen

Die Konfliktantwort trägt genau die drei Wege aus Abschnitt 9.8:

- `view_remote` — aktuelle Remoteversion ansehen,
- `return_to_draft` — zum eigenen Entwurf zurückkehren,
- `discard_local_use_remote` — eigene Änderungen bewusst verwerfen und die
  Remoteversion übernehmen.

„Eigene Fassung trotzdem übernehmen“ ist bewusst **nicht** enthalten: Ohne
belegte atomare Vorbedingung wäre das ein unkontrolliertes Last-Write-Wins.

## 5. F10-Nachweis

`tests/test_planner_conflicts.py` prüft mit dem F10-Szenario:

- externe Struktur- und Namensänderung vor dem lokalen Speichern führen zu
  `conflict`/`structure`;
- der lokale Entwurf bleibt mit seinen 30 Minuten erhalten, die Remote-Fassung
  mit 25 Minuten bleibt separat lesbar;
- es gibt keinen Update- und keinen Create-Aufruf;
- externe Löschung, Berechtigungsänderung und Metadatenänderung werden getrennt
  erkannt;
- ein Lesefehler vor dem Write wird nicht als bestätigter oder erfundener
  Konflikt ausgegeben.
