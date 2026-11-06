"""Loader für die fachlichen Planer-Fixtures (P01) und ihre P02-Modelle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trainings_cockpit.planner import (
    DistanceEnd,
    Editability,
    HeartRateTarget,
    NoTarget,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    RestrictionCode,
    SourceSnapshot,
    StepNode,
    StepRole,
    TimeEnd,
    UnsupportedNode,
    Value,
    ValueRange,
    ZoneMetric,
    ZoneTarget,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "planner"
CASES_DIR = FIXTURE_DIR / "cases"
REMOTE_DIR = FIXTURE_DIR / "remote"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def case_paths() -> list[Path]:
    return sorted(CASES_DIR.glob("f*.json"))


def load_cases() -> list[dict[str, Any]]:
    return [load_json(path) for path in case_paths()]


def load_case(case_id: str) -> dict[str, Any]:
    for path in case_paths():
        data = load_json(path)
        if data.get("case") == case_id:
            return data
    raise FileNotFoundError(f"Fixture {case_id} fehlt in {CASES_DIR}")


def load_profiles() -> dict[str, Any]:
    return load_json(FIXTURE_DIR / "profiles.json")


def load_remote(relative_path: str) -> dict[str, Any]:
    return load_json(REMOTE_DIR / relative_path)


def load_matrix() -> dict[str, Any]:
    return load_json(FIXTURE_DIR / "capability-matrix.json")


# ------------------------------------------------------------ P02-Modelle


def build_value(raw: dict[str, Any]) -> Value | ValueRange:
    if raw["kind"] == "value":
        return Value(raw["value"])
    if raw["kind"] == "range":
        return ValueRange(raw["min"], raw["max"])
    raise ValueError(f"Unbekannte Wertart: {raw['kind']!r}")


def build_target(raw: dict[str, Any] | None):
    if raw is None or raw["kind"] == "none":
        return NoTarget()
    if raw["kind"] == "zone":
        return ZoneTarget(
            metric=ZoneMetric(raw["metric"]),
            zone_id=raw["zoneId"],
            zone_set_id=raw.get("zoneSetId"),
        )
    if raw["kind"] == "heartRate":
        return HeartRateTarget(values=build_value(raw["values"]), unit=raw.get("unit", "bpm"))
    if raw["kind"] == "power":
        return PowerTarget(unit=PowerUnit(raw["unit"]), values=build_value(raw["values"]))
    if raw["kind"] == "pace":
        return PaceTarget(unit=PaceUnit(raw["unit"]), values=build_value(raw["values"]))
    raise ValueError(f"Unbekannte Zielart: {raw['kind']!r}")


def build_end(raw: dict[str, Any]) -> TimeEnd | DistanceEnd:
    if raw["kind"] == "time":
        return TimeEnd(raw["seconds"])
    if raw["kind"] == "distance":
        return DistanceEnd(raw["metres"])
    raise ValueError(f"Unbekannte Ende-Bedingung: {raw['kind']!r}")


def build_node(raw: dict[str, Any]):
    if raw["kind"] == "step":
        return StepNode(
            id=raw["id"],
            name=raw.get("name", ""),
            end=build_end(raw["end"]),
            role=StepRole(raw.get("role", "steady")),
            target=build_target(raw.get("target")),
            notes=raw.get("notes"),
            source_ref=raw.get("sourceRef"),
        )
    if raw["kind"] == "repeat":
        return RepeatNode(
            id=raw["id"],
            name=raw.get("name", ""),
            repetitions=raw["repetitions"],
            children=tuple(build_node(child) for child in raw["children"]),
            skip_final_recovery=raw.get("skipFinalRecovery", False),
            source_ref=raw.get("sourceRef"),
        )
    if raw["kind"] == "unsupported":
        return UnsupportedNode(
            id=raw["id"],
            label=raw["label"],
            reason=raw["reason"],
            source_ref=raw["sourceRef"],
        )
    raise ValueError(f"Unbekannter Knoten: {raw['kind']!r}")


def build_plan(raw: dict[str, Any]) -> PlannedWorkout:
    return PlannedWorkout(
        local_id=raw["localId"],
        remote_id=raw.get("remoteId"),
        external_id=raw.get("externalId"),
        name=raw.get("name", ""),
        sport=raw["sport"],
        date=raw["date"],
        local_time=raw.get("localTime"),
        time_zone=raw["timeZone"],
        nodes=tuple(build_node(node) for node in raw.get("nodes", [])),
        notes=raw.get("notes"),
        editability=Editability(raw.get("editability", "full")),
        editability_reason=raw.get("editabilityReason"),
        restriction_codes=tuple(
            RestrictionCode(code) for code in raw.get("restrictionCodes", [])
        ),
    )


def build_plan_from_case(case: dict[str, Any]) -> PlannedWorkout:
    return build_plan(case["plan"])


def snapshot_for_case(case: dict[str, Any]) -> SourceSnapshot:
    remote_path = case.get("remoteFixture")
    if not remote_path:
        raise ValueError(f"{case['case']} hat kein Remote-Beispiel.")
    remote = load_remote(Path(remote_path).name)
    event = remote["event"]
    return SourceSnapshot.capture(
        remote_id=event["id"],
        raw=event,
        fetched_at="2026-11-08T09:15:00+01:00",
        remote_updated_at="2026-11-01T08:00:00Z",
        remote_version="fixture-1",
    )
