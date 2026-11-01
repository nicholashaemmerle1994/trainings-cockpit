"""Trainingslast, wenn intervals sie nicht rechnen kann.

Kraft und Rad kommen weiter über intervals, dort rechnet intervals die Last
(TSS aus Leistung, hrTSS aus Puls). Läufe und Schwimmen kommen direkt von
Garmin — dort gibt es keine intervals-Last mehr.

Garmins eigene Last (`activityTrainingLoad`) ist kein Ersatz: sie liegt im
Median 2,64× über der von intervals und streut von 0,29 bis 8,64 (66 Paare,
01.11.2026). Deshalb wird sie nicht übernommen, sondern eine eigene Formel an
der bisherigen Last kalibriert:

    Last = Stunden × Faktor × (Puls / 160)²

Der Faktor ist je Sportart so gewählt, dass die Formel die historische
intervals-Last trifft — für Läufe mit R² = 0,974 über 37 Paare, für Schwimmen
mit demselben Aufbau. Damit bleiben Fitness und Müdigkeit über den Wechsel
hinweg vergleichbar.
"""

from __future__ import annotations

#: Puls, bei dem die Formel den Faktor genau erreicht.
REFERENCE_HR = 160.0
#: Faktor je Sportart, kalibriert an der bisherigen intervals-Last.
FACTORS = {
    "Run": 75.0,
    "VirtualRun": 75.0,
    "Swim": 70.0,
    "OpenWaterSwim": 70.0,
}
DEFAULT_FACTOR = 70.0
#: Plausible Grenzen, damit ein Ausreißer im Puls nicht die Last verzerrt.
HR_RANGE = (60.0, 220.0)


def compute_load(sport: str, duration_s: float | None, avg_hr: float | None) -> float | None:
    """Last in intervals-Skala, oder None wenn Puls oder Dauer fehlen."""
    if not duration_s or not avg_hr:
        return None
    low, high = HR_RANGE
    if not low <= avg_hr <= high:
        return None
    hours = duration_s / 3600.0
    factor = FACTORS.get(sport, DEFAULT_FACTOR)
    return round(hours * factor * (avg_hr / REFERENCE_HR) ** 2, 1)
