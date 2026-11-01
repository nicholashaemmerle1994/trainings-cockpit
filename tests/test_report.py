from __future__ import annotations

from datetime import datetime, timedelta

from trainings_cockpit.spike.report import build_report


def _wellness(days: int, end: datetime) -> list[dict]:
    rows = []
    for offset in range(days):
        day = (end - timedelta(days=offset)).date().isoformat()
        rows.append(
            {
                "id": day,
                "hrv": 60 + offset % 5,
                "restingHR": 48,
                "sleepSecs": 7 * 3600 + 1800,
                "sleepScore": 78,
            }
        )
    return rows


def test_report_marks_intervals_ok_and_garmin_missing() -> None:
    generated = datetime(2026, 10, 30, 6, 0)
    intervals = {
        "athlete": {"id": "i123", "name": "Nicholas", "timezone": "Europe/Vienna"},
        "activities": [
            {
                "start_date_local": "2026-10-01T07:00:00",
                "type": "Run",
                "icu_training_load": 50,
                "source": "GARMIN_CONNECT",
            }
        ],
        "wellness": _wellness(10, generated),
        "events": [{"category": "WORKOUT", "start_date_local": "2026-11-03T00:00:00"}],
        "sport_settings": [{"type": "Run"}],
    }

    markdown = build_report(intervals, None, None, generated)

    assert "Phase-0-Befund" in markdown
    assert "Nicholas" in markdown
    assert "| Aktivitäten | 1 |" in markdown
    assert "| Wellness-Tage | 10 |" in markdown
    assert "| HRV | 10/10 |" in markdown
    assert "- [x] intervals.icu-Key" in markdown
    assert "- [ ] Garmin-Key" in markdown
    assert "- [ ] Workout-Text wird geparst" in markdown
    assert "- [x] Zepp/Helio-Wellness" in markdown
    assert "tc fetch garmin" in markdown


def test_report_accepts_successful_push() -> None:
    generated = datetime(2026, 10, 30, 6, 0)
    push = {
        "event": {"external_id": "tc:spike:2026-11-06"},
        "verify": {
            "ok": True,
            "event_id": 99,
            "external_id": "tc:spike:2026-11-06",
            "steps": 4,
            "load": 41,
            "intensity": 72.0,
            "issues": [],
        },
    }

    markdown = build_report({}, None, push, generated)
    assert "- [x] Workout-Text wird geparst" in markdown
    assert "✅ ok" in markdown
