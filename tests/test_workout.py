from __future__ import annotations

from datetime import date

from trainings_cockpit.spike.workout import (
    TEST_DURATION_SECONDS,
    build_test_event,
    verify_event,
)


def test_build_test_event_shape() -> None:
    event = build_test_event(date(2027, 1, 12), sport="Run")
    assert event["category"] == "WORKOUT"
    assert event["start_date_local"] == "2027-01-12T00:00:00"
    assert event["type"] == "Run"
    assert event["external_id"] == "tc:spike:2027-01-12"
    assert event["moving_time"] == TEST_DURATION_SECONDS
    assert "3x" in event["description"]


def test_verify_event_ok() -> None:
    event = {
        "id": 42,
        "external_id": "tc:spike:2027-01-12",
        "type": "Ride",
        "workout_doc": {"steps": [{"duration": 900}]},
        "icu_training_load": 38,
        "icu_intensity": 71.5,
    }
    result = verify_event(event, "tc:spike:2027-01-12")
    assert result["ok"] is True
    assert result["steps"] == 1
    assert result["issues"] == []


def test_verify_event_detects_missing_parse() -> None:
    event = {
        "id": 42,
        "external_id": "tc:spike:2027-01-12",
        "workout_doc": {},
        "icu_training_load": None,
    }
    result = verify_event(event, "tc:spike:2027-01-12")
    assert result["ok"] is False
    assert len(result["issues"]) == 2
