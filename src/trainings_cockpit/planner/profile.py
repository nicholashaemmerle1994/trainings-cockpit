"""Reine Graphprojektion aus der zentralen Ausführungsfolge.

Der Trainingsverlauf zeigt ausschließlich geplante Vorgaben. Er entsteht aus
:func:`derive_execution_sequence` und :func:`calculate_known_totals` — nicht aus
einer zweiten Interpretation von Wiederholungen und nicht aus aufgezeichneten
Messreihen.

Die Projektion liefert nur Daten: Achse, Blöcke und getrennte Zielspuren. Die
Oberfläche entscheidet über Pixel, Farben und Beschriftungsgrößen. Numerische
Einheiten werden nie auf eine gemeinsame, unbeschriftete Skala gelegt.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .model import (
    DistanceEnd,
    HeartRateTarget,
    NoTarget,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    StepEnd,
    StepRole,
    StepTarget,
    TimeEnd,
    Value,
    ValueRange,
    ZoneTarget,
)
from .validation import (
    Execution,
    ExecutionCompression,
    calculate_known_totals,
    derive_execution_sequence,
    format_distance,
    format_duration,
    format_pace,
    format_target,
    format_target_label,
    format_totals,
)

#: Eine feste Reihenfolge macht die Spuren über Öffnen und Auswahl stabil.
_METRIC_ORDER = {
    "heartRate": 0,
    "pace": 1,
    "power": 2,
    "none": 3,
}

@dataclass(frozen=True, slots=True)
class _Block:
    """Ein gezeichneter Block: eine Ausführung oder eine benannte Verdichtung."""

    kind: str
    position: int
    node_id: str
    group_id: str | None
    repeat_group_ids: tuple[str, ...]
    repetition_index: int | None
    repetition_path: tuple[int, ...]
    name: str
    role: str
    end_kind: str | None
    seconds: float | None
    metres: float | None
    target: StepTarget | None
    target_key: str | None
    target_text: str
    extent_text: str
    omitted_executions: int = 0
    omitted_repetitions: int = 0
    reason: str | None = None


def _target_key(target: StepTarget | None) -> str | None:
    if target is None or isinstance(target, NoTarget):
        return "none:none"
    if isinstance(target, ZoneTarget):
        return f"{target.metric.value}:zone"
    if isinstance(target, HeartRateTarget):
        return "heartRate:bpm"
    if isinstance(target, PowerTarget):
        unit = "watts" if target.unit is PowerUnit.WATTS else "percentFtp"
        return f"power:{unit}"
    if isinstance(target, PaceTarget):
        unit = "secondsPerKm" if target.unit is PaceUnit.SECONDS_PER_KM else "secondsPer100m"
        return f"pace:{unit}"
    return None


def _target_text(target: StepTarget | None) -> str:
    return format_target_label(target)


def _end_values(end: StepEnd) -> tuple[str, float | None, float | None]:
    if isinstance(end, TimeEnd):
        return "time", end.seconds, None
    if isinstance(end, DistanceEnd):
        return "distance", None, end.metres
    return "open", None, None


def _end_text(end: StepEnd) -> str:
    if isinstance(end, TimeEnd):
        return format_duration(end.seconds)
    if isinstance(end, DistanceEnd):
        return format_distance(end.metres)
    return "Ende offen"


def _zone_number(zone_id: str) -> int | None:
    tail = zone_id.rsplit("-", 1)[-1]
    try:
        number = int(tail)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _zone_profile(zone_profiles: Mapping[str, Any] | None, sport: str) -> Mapping[str, Any] | None:
    if not zone_profiles:
        return None
    direct = zone_profiles.get(sport)
    if isinstance(direct, Mapping):
        return direct
    from ..plan import sport_family

    family = sport_family(sport)
    for key, value in zone_profiles.items():
        if sport_family(str(key)) == family and isinstance(value, Mapping):
            return value
    return None


def _zone_absolute(
    zone_id: str,
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> tuple[float | None, float | None]:
    """Nur für die Beschriftung aufgelöste bpm-Grenzen, nie als neue Vorgabe."""
    number = _zone_number(zone_id)
    if number is None:
        return None, None
    entry = _zone_profile(zone_profiles, sport)
    if not entry:
        return None, None
    zones = entry.get("zones")
    max_hr = entry.get("max_hr")
    if not isinstance(zones, list) or number > len(zones):
        return None, None
    try:
        high = float(zones[number - 1])
        low = (
            float(zones[number - 2])
            if number >= 2
            else float(round(float(max_hr or zones[0]) * 0.5))
        )
    except (TypeError, ValueError):
        return None, None
    return low, high


def _zone_label(
    target: ZoneTarget,
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> tuple[str, float | None, float | None]:
    label = format_target(target)
    low, high = _zone_absolute(target.zone_id, sport, zone_profiles)
    if low is not None and high is not None:
        label = f"{label} · {low:.0f}–{high:.0f} bpm"
    return label, low, high


def _target_data(
    target: StepTarget | None,
    *,
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if target is None:
        return {"kind": "missing", "text": "Wert fehlt", "values": None}
    if isinstance(target, NoTarget):
        return {"kind": "none", "text": "Ohne Ziel", "values": None}
    if isinstance(target, ZoneTarget):
        label, low, high = _zone_label(target, sport, zone_profiles)
        number = _zone_number(target.zone_id)
        return {
            "kind": "zone",
            "metric": target.metric.value,
            "zone_id": target.zone_id,
            "zone_set_id": target.zone_set_id,
            "text": label,
            "values": None,
            "zone_level": number,
            "absolute_low": low,
            "absolute_high": high,
        }
    if isinstance(target, HeartRateTarget):
        values = _value_pair(target.values)
        return {
            "kind": "heartRate",
            "metric": "heartRate",
            "unit": "bpm",
            "text": format_target(target),
            "values": values,
        }
    if isinstance(target, PowerTarget):
        unit = "watts" if target.unit is PowerUnit.WATTS else "percentFtp"
        return {
            "kind": "power",
            "metric": "power",
            "unit": unit,
            "text": format_target(target),
            "values": _value_pair(target.values),
        }
    if isinstance(target, PaceTarget):
        unit = "secondsPerKm" if target.unit is PaceUnit.SECONDS_PER_KM else "secondsPer100m"
        return {
            "kind": "pace",
            "metric": "pace",
            "unit": unit,
            "text": format_target(target),
            "values": _value_pair(target.values),
        }
    return {"kind": "none", "text": "Ohne Ziel", "values": None}


def _value_pair(values: Value | ValueRange) -> dict[str, float | str]:
    if isinstance(values, Value):
        return {
            "kind": "value",
            "value": float(values.value),
            "min": float(values.value),
            "max": float(values.value),
        }
    return {"kind": "range", "min": float(values.min), "max": float(values.max)}


def _blocks(
    executions: tuple[Execution, ...],
    compressions: tuple[ExecutionCompression, ...],
    *,
    total_seconds: float,
    total_metres: float,
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> list[_Block]:
    by_position: dict[int, list[ExecutionCompression]] = {}
    for compression in compressions:
        by_position.setdefault(compression.first_position, []).append(compression)

    expanded_seconds = sum(
        float(execution.end.seconds)
        for execution in executions
        if isinstance(execution.end, TimeEnd)
    )
    expanded_metres = sum(
        float(execution.end.metres)
        for execution in executions
        if isinstance(execution.end, DistanceEnd)
    )
    remaining_seconds = max(0.0, float(total_seconds) - expanded_seconds)
    remaining_metres = max(0.0, float(total_metres) - expanded_metres)

    blocks: list[_Block] = []
    for index in range(len(executions) + 1):
        for compression in by_position.get(index, []):
            seconds = remaining_seconds if remaining_seconds > 0 else None
            metres = remaining_metres if remaining_metres > 0 else None
            remaining_seconds = 0.0
            remaining_metres = 0.0
            omitted = compression.omitted_executions
            blocks.append(
                _Block(
                    kind="compression",
                    position=len(blocks),
                    node_id=str(compression.node_id),
                    group_id=(
                        str(compression.parent_group_id)
                        if compression.parent_group_id is not None
                        else None
                    ),
                    repeat_group_ids=(),
                    repetition_index=None,
                    repetition_path=(),
                    name=f"{omitted} Ausführungen komprimiert",
                    role="compression",
                    end_kind="time" if seconds is not None else (
                        "distance" if metres is not None else None
                    ),
                    seconds=seconds,
                    metres=metres,
                    target=None,
                    target_key=None,
                    target_text="",
                    extent_text=(
                        format_duration(seconds)
                        if seconds is not None
                        else format_distance(metres)
                        if metres is not None
                        else "Summe bleibt erhalten"
                    ),
                    omitted_executions=omitted,
                    omitted_repetitions=compression.omitted_repetitions,
                    reason=compression.reason,
                )
            )
        if index >= len(executions):
            continue
        execution = executions[index]
        end_kind, seconds, metres = _end_values(execution.end)
        blocks.append(
            _Block(
                kind="execution",
                position=len(blocks),
                node_id=str(execution.node_id),
                group_id=str(execution.group_id) if execution.group_id is not None else None,
                repeat_group_ids=tuple(str(value) for value in execution.repeat_group_ids),
                repetition_index=execution.repetition_index,
                repetition_path=tuple(execution.repetition_path),
                name=execution.name or _role_label(execution.role),
                role=execution.role.value,
                end_kind=end_kind,
                seconds=seconds,
                metres=metres,
                target=execution.target,
                target_key=_target_key(execution.target),
                target_text=_target_text(execution.target),
                extent_text=_end_text(execution.end),
            )
        )
    return blocks


def _role_label(role: StepRole) -> str:
    return {
        StepRole.WARMUP: "Einlaufen",
        StepRole.WORK: "Belastung",
        StepRole.RECOVERY: "Erholung",
        StepRole.COOLDOWN: "Auslaufen",
        StepRole.STEADY: "Abschnitt",
    }.get(role, "Abschnitt")


def _axis_mode(blocks: list[_Block], known_unknown: bool) -> str:
    if known_unknown or not blocks:
        return "schematic"
    kinds = {
        block.end_kind
        for block in blocks
        if block.kind == "execution" and block.end_kind is not None
    }
    if kinds == {"time"}:
        return "time"
    if kinds == {"distance"}:
        return "distance"
    return "schematic"


def _axis(
    mode: str,
    blocks: list[_Block],
    *,
    total_seconds: float,
    total_metres: float,
    total_executions: int,
) -> dict[str, Any]:
    if mode == "time":
        total = float(total_seconds) or sum(block.seconds or 0 for block in blocks)
        return {
            "mode": "time",
            "label": "Zeit",
            "unit": "min",
            "total": total,
            "total_text": format_duration(total),
            "ticks": _time_ticks(total),
        }
    if mode == "distance":
        total = float(total_metres) or sum(block.metres or 0 for block in blocks)
        return {
            "mode": "distance",
            "label": "Distanz",
            "unit": "km" if total >= 1000 else "m",
            "total": total,
            "total_text": format_distance(total),
            "ticks": _distance_ticks(total),
        }
    if total_executions > len(blocks):
        total_text = f"{len(blocks)} Blöcke · {total_executions} Ausführungen"
    else:
        total_text = f"{len(blocks)} Abschnitte"
    return {
        "mode": "schematic",
        "label": "Abschnitte · schematisch",
        "unit": "",
        "total": len(blocks),
        "total_text": total_text,
        "ticks": [],
    }


def _time_ticks(total: float) -> list[dict[str, Any]]:
    if total <= 0:
        return []
    fractions = (0.0, 0.5, 1.0)
    return [
        {"at": fraction, "label": f"{round(total * fraction / 60)}"}
        for fraction in fractions
    ]


def _distance_ticks(total: float) -> list[dict[str, Any]]:
    if total <= 0:
        return []
    fractions = (0.0, 0.5, 1.0)
    if total >= 1000:
        labels = [f"{total * fraction / 1000:.1f}".replace(".", ",") for fraction in fractions]
    else:
        labels = [f"{round(total * fraction)}" for fraction in fractions]
    return [
        {"at": fraction, "label": label}
        for fraction, label in zip(fractions, labels, strict=True)
    ]


def _segment_layout(
    mode: str,
    blocks: list[_Block],
    *,
    total_seconds: float,
    total_metres: float,
) -> list[dict[str, Any]]:
    layouts: list[dict[str, Any]] = []
    if mode == "time":
        total = float(total_seconds) or sum(block.seconds or 0 for block in blocks) or 1.0
        cumulative = 0.0
        for block in blocks:
            start = cumulative
            cumulative += block.seconds or 0.0
            layouts.append(
                {
                    "start": start,
                    "end": cumulative,
                    "start_fraction": start / total,
                    "width_fraction": (cumulative - start) / total,
                }
            )
        return layouts
    if mode == "distance":
        total = float(total_metres) or sum(block.metres or 0 for block in blocks) or 1.0
        cumulative = 0.0
        for block in blocks:
            start = cumulative
            cumulative += block.metres or 0.0
            layouts.append(
                {
                    "start": start,
                    "end": cumulative,
                    "start_fraction": start / total,
                    "width_fraction": (cumulative - start) / total,
                }
            )
        return layouts
    count = len(blocks) or 1
    for index in range(len(blocks)):
        layouts.append(
            {
                "start": index,
                "end": index + 1,
                "start_fraction": index / count,
                "width_fraction": 1 / count,
            }
        )
    return layouts


def _serialize_segment(
    block: _Block,
    layout: Mapping[str, Any],
    *,
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "kind": block.kind,
        "position": block.position,
        "node_id": block.node_id,
        "group_id": block.group_id,
        "repeat_group_ids": list(block.repeat_group_ids),
        "repetition_index": block.repetition_index,
        "repetition_path": list(block.repetition_path),
        "name": block.name,
        "role": block.role,
        "end_kind": block.end_kind,
        "seconds": block.seconds,
        "metres": block.metres,
        "extent_text": block.extent_text,
        "target_key": block.target_key,
        "target_text": block.target_text,
        "target": (
            _target_data(block.target, sport=sport, zone_profiles=zone_profiles)
            if block.target is not None
            else None
        ),
        "omitted_executions": block.omitted_executions,
        "omitted_repetitions": block.omitted_repetitions,
        "reason": block.reason,
        "start": layout["start"],
        "end": layout["end"],
        "start_fraction": layout["start_fraction"],
        "width_fraction": layout["width_fraction"],
    }


def _track_key_parts(key: str) -> tuple[str, str]:
    parts = key.split(":", 2)
    metric = parts[0] if parts else "none"
    if len(parts) > 1 and parts[1] == "zone":
        return metric, "zone"
    unit = parts[2] if len(parts) > 2 else (parts[1] if len(parts) > 1 else "none")
    return metric, unit


def _track_label(metric: str, unit: str) -> str:
    if metric == "heartRate" and unit == "zone":
        return "Herzfrequenz · Zonen"
    if metric == "pace" and unit == "zone":
        return "Pace · Zonen"
    if metric == "power" and unit == "zone":
        return "Leistung · Zonen"
    if metric == "heartRate":
        return "Herzfrequenz · bpm"
    if metric == "pace":
        return "Pace · min/km" if unit == "secondsPerKm" else "Pace · /100 m"
    if metric == "power":
        return "Leistung · W" if unit == "watts" else "Leistung · % FTP"
    return "Ohne Ziel"


def _track_short(metric: str, unit: str) -> str:
    if metric == "heartRate":
        return "HF"
    if metric == "pace":
        return "Pace"
    if metric == "power":
        return "W" if unit == "watts" else "% FTP"
    return "Ohne Ziel"


def _numeric_domain(low: float, high: float, unit: str) -> dict[str, Any]:
    if not math.isfinite(low) or not math.isfinite(high):
        return {}
    if low == high:
        pad = max(1.0, abs(low) * 0.1)
        low -= pad
        high += pad
    else:
        pad = (high - low) * 0.12
        low -= pad
        high += pad
    if unit in {"bpm", "W", "% FTP"}:
        low = max(0.0, low)
    return {"min": low, "max": high, "direction": "higher-up"}


def _tracks(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracks: dict[str, dict[str, Any]] = {}
    for segment in segments:
        key = segment.get("target_key")
        if not key:
            continue
        metric, unit = _track_key_parts(str(key))
        track = tracks.setdefault(
            str(key),
            {
                "key": str(key),
                "metric": metric,
                "unit": unit,
                "label": _track_label(metric, unit),
                "short": _track_short(metric, unit),
                "kind": "zone" if unit == "zone" else (
                    "none" if metric == "none" else "numeric"
                ),
                "segments": [],
                "zone_ids": [],
            },
        )
        if segment["kind"] == "compression":
            continue
        track["segments"].append(segment)
        target = segment.get("target") or {}
        if target.get("kind") == "zone" and target.get("zone_id") not in track["zone_ids"]:
            track["zone_ids"].append(target.get("zone_id"))

    result: list[dict[str, Any]] = []
    for track in tracks.values():
        metric = track["metric"]
        unit = track["unit"]
        if track["kind"] == "numeric":
            values: list[Mapping[str, Any]] = []
            for segment in track["segments"]:
                raw = (segment.get("target") or {}).get("values")
                if isinstance(raw, Mapping):
                    values.append(raw)
            lows = [float(value["min"]) for value in values if "min" in value]
            highs = [float(value["max"]) for value in values if "max" in value]
            if lows and highs:
                track["domain"] = _numeric_domain(min(lows), max(highs), unit)
                track["ticks"] = _numeric_ticks(track["domain"], unit)
                track["direction"] = "faster-up" if metric == "pace" else "higher-up"
            else:
                track["domain"] = {}
                track["ticks"] = []
        elif track["kind"] == "zone":
            zones: list[dict[str, Any]] = []
            seen: set[str] = set()
            for segment in track["segments"]:
                target = segment.get("target") or {}
                zone_id = str(target.get("zone_id") or "")
                if zone_id in seen:
                    continue
                seen.add(zone_id)
                level = target.get("zone_level")
                if not isinstance(level, int):
                    level = len(zones) + 1
                zones.append(
                    {
                        "zone_id": zone_id,
                        "label": str(target.get("text") or "").split(" · ")[0],
                        "level": level,
                        "absolute_low": target.get("absolute_low"),
                        "absolute_high": target.get("absolute_high"),
                    }
                )
            zones.sort(key=lambda zone: (int(zone["level"]), str(zone["zone_id"])))
            track["zones"] = zones
        result.append(track)

    result.sort(key=lambda track: (_METRIC_ORDER.get(track["metric"], 9), track["key"]))
    return result


def _numeric_ticks(domain: Mapping[str, Any], unit: str) -> list[dict[str, Any]]:
    low = float(domain.get("min", 0))
    high = float(domain.get("max", 0))
    if high <= low:
        return []
    values = (low, (low + high) / 2, high)
    if unit == "secondsPerKm":
        labels = [format_pace(value, PaceUnit.SECONDS_PER_KM).split(" ")[0] for value in values]
    elif unit == "secondsPer100m":
        labels = [format_pace(value, PaceUnit.SECONDS_PER_100M).split(" ")[0] for value in values]
    elif unit == "bpm":
        labels = [f"{round(value)}" for value in values]
    elif unit == "W":
        labels = [f"{round(value)}" for value in values]
    else:
        labels = [f"{value:.1f}".replace(".", ",") for value in values]
    fractions = (0.0, 0.5, 1.0)
    return [
        {"at": fraction, "value": value, "label": label}
        for fraction, value, label in zip(fractions, values, labels, strict=True)
    ]


def _repetition_groups(plan: PlannedWorkout) -> list[dict[str, Any]]:
    from .model import RepeatNode, iter_nodes

    groups: list[dict[str, Any]] = []
    for node in iter_nodes(plan.nodes):
        if isinstance(node, RepeatNode):
            groups.append(
                {
                    "node_id": str(node.id),
                    "name": node.name,
                    "repetitions": node.repetitions,
                    "skip_final_recovery": node.skip_final_recovery,
                }
            )
    return groups


def _text_alternative(
    plan: PlannedWorkout,
    totals: Any,
    tracks: list[dict[str, Any]],
    sequence: Any,
) -> str:
    parts = [
        f"Geplanter Trainingsverlauf für {plan.name or 'diese Einheit'}.",
        format_totals_text(totals),
        f"{sequence.total_executions} geplante "
        f"{'Ausführung' if sequence.total_executions == 1 else 'Ausführungen'}.",
    ]
    if tracks:
        parts.append("Getrennte Spuren: " + ", ".join(track["label"] for track in tracks) + ".")
    else:
        parts.append("Keine Zielspur vorhanden.")
    if sequence.compressions:
        parts.append(
            "Große Wiederholungsmengen sind sichtbar komprimiert; "
            "die Summe bleibt erhalten."
        )
    return " ".join(parts)


def format_totals_text(totals: Any) -> str:
    return format_totals(totals).rstrip(".") + "."


def build_workout_profile_data(
    plan: PlannedWorkout,
    *,
    zone_profiles: Mapping[str, Any] | None = None,
    max_executions: int = 500,
) -> dict[str, Any]:
    """Graphdaten aus der einen zentralen Ausführungsfolge.

    ``max_executions`` begrenzt nur die Zahl gezeichneter Segmente. Die
    Gesamtsummen stammen aus :func:`calculate_known_totals` und werden durch
    die Kompression nicht verändert.
    """
    sequence = derive_execution_sequence(plan, max_executions=max_executions)
    totals = calculate_known_totals(plan)
    blocks = _blocks(
        sequence.executions,
        sequence.compressions,
        total_seconds=totals.duration_seconds,
        total_metres=totals.distance_metres,
        sport=plan.sport,
        zone_profiles=zone_profiles,
    )
    mode = _axis_mode(blocks, totals.has_unknown)
    axis = _axis(
        mode,
        blocks,
        total_seconds=totals.duration_seconds,
        total_metres=totals.distance_metres,
        total_executions=sequence.total_executions,
    )
    layouts = list(
        _segment_layout(
            mode,
            blocks,
            total_seconds=totals.duration_seconds,
            total_metres=totals.distance_metres,
        )
    )
    segments = [
        _serialize_segment(
            block,
            layout,
            sport=plan.sport,
            zone_profiles=zone_profiles,
        )
        for block, layout in zip(blocks, layouts, strict=True)
    ]
    tracks = _tracks(segments)
    return {
        "axis": axis,
        "segments": segments,
        "tracks": tracks,
        "totals": {
            "seconds": totals.duration_seconds,
            "metres": totals.distance_metres,
            "executions": totals.executions,
            "total_executions": sequence.total_executions,
            "has_unknown": totals.has_unknown,
            "first_end": totals.first_end,
            "text": format_totals_text(totals),
            "compressed_executions": sum(
                compression.omitted_executions for compression in sequence.compressions
            ),
        },
        "repetition_groups": _repetition_groups(plan),
        "compressions": [
            {
                "node_id": str(compression.node_id),
                "parent_group_id": (
                    str(compression.parent_group_id)
                    if compression.parent_group_id is not None
                    else None
                ),
                "first_position": compression.first_position,
                "omitted_executions": compression.omitted_executions,
                "omitted_repetitions": compression.omitted_repetitions,
                "reason": compression.reason,
            }
            for compression in sequence.compressions
        ],
        "text_alternative": _text_alternative(plan, totals, tracks, sequence),
    }


def heart_rate_zone_options(
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Die tatsächlich vorhandenen HF-Zonen einer Sportart.

    Es werden keine Zonen aus einer allgemeinen Formel ergänzt. Fehlt das
    Profil, bleibt die Liste leer; die Oberfläche kann dann nur „Ohne Ziel“
    anbieten und eine importierte Referenz als unbekannt markieren.
    """
    entry = _zone_profile(zone_profiles, sport)
    if not entry:
        return {
            "sport": sport,
            "available": False,
            "zone_set_id": None,
            "max_hr": None,
            "zones": [],
        }
    raw_zones = entry.get("zones")
    max_hr = entry.get("max_hr")
    if not isinstance(raw_zones, list) or not raw_zones:
        return {
            "sport": sport,
            "available": False,
            "zone_set_id": None,
            "max_hr": float(max_hr) if isinstance(max_hr, (int, float)) else None,
            "zones": [],
        }
    try:
        boundaries = [float(value) for value in raw_zones]
    except (TypeError, ValueError):
        return {
            "sport": sport,
            "available": False,
            "zone_set_id": None,
            "max_hr": None,
            "zones": [],
        }
    try:
        max_value = float(max_hr) if max_hr is not None else boundaries[-1]
    except (TypeError, ValueError):
        max_value = boundaries[-1]
    from .remote import _sport_slug

    zone_set_id = f"{_sport_slug(sport)}-hr"
    zones: list[dict[str, Any]] = []
    for index, high in enumerate(boundaries, start=1):
        low = boundaries[index - 2] if index >= 2 else round(max_value * 0.5, 1)
        zones.append(
            {
                "id": f"{zone_set_id}-{index}",
                "label": f"Zone {index}",
                "level": index,
                "low": low,
                "high": high,
            }
        )
    return {
        "sport": sport,
        "available": True,
        "zone_set_id": zone_set_id,
        "max_hr": max_value,
        "zones": zones,
    }


__all__ = ["build_workout_profile_data", "heart_rate_zone_options"]
