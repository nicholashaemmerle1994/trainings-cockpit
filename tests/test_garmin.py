from __future__ import annotations

from trainings_cockpit.sources.garmin import GarminDump, _as_list, _try


def test_as_list_unwraps_nested_list() -> None:
    assert _as_list([1, 2]) == [1, 2]
    assert _as_list({"sleepSummaries": [{"date": "2026-10-01"}]}) == [{"date": "2026-10-01"}]
    assert _as_list({"value": 3}) == [{"value": 3}]


def test_try_extends_lists_and_records_errors() -> None:
    dump = GarminDump()
    _try(dump, "sleep", lambda: {"sleepSummaries": [{"n": 1}]})
    _try(dump, "sleep", lambda: [{"n": 2}])
    assert dump.sleep == [{"n": 1}, {"n": 2}]

    _try(dump, "profile", lambda: {"displayName": "Nicholas"})
    assert dump.profile == {"displayName": "Nicholas"}

    def boom() -> None:
        raise RuntimeError("endpoint down")

    _try(dump, "hrv", boom)
    assert "endpoint down" in dump.errors["hrv"]
