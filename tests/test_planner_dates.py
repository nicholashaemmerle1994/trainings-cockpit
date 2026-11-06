"""P03: lokale Kalenderwochen, Zeitraumverträge und Datumsverschiebung."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from planner_fixtures import build_plan_from_case, load_case

from trainings_cockpit.planner import (
    add_calendar_days,
    add_calendar_weeks,
    completion_text,
    current_planner_week,
    format_day,
    get_week_days,
    is_date_in_week,
    local_today,
    parse_week_parameter,
    planner_week_range,
    reschedule_plan,
    rolling_dashboard_range,
    start_of_planner_week,
    week_label,
)

VIENNA = "Europe/Vienna"


def test_sonntag_gehoert_zur_angezeigten_woche() -> None:
    monday = start_of_planner_week("2026-11-01", VIENNA)

    assert monday == "2026-10-26"
    assert get_week_days(monday) == (
        "2026-10-26",
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
        "2026-10-30",
        "2026-10-31",
        "2026-11-01",
    )
    assert is_date_in_week("2026-11-01", monday) is True
    assert is_date_in_week("2026-11-02", monday) is False
    assert start_of_planner_week("2026-11-02", VIENNA) == "2026-11-02"


def test_jahreswechsel_verschiebt_keinen_tag() -> None:
    monday = start_of_planner_week("2027-01-01", VIENNA)

    assert monday == "2026-12-28"
    assert get_week_days(monday)[-1] == "2027-01-03"
    assert add_calendar_weeks(monday, 1) == "2027-01-04"
    assert add_calendar_weeks("2026-12-28", -1) == "2026-12-21"
    assert add_calendar_days("2026-12-31", 1) == "2027-01-01"


def test_beide_zeitumstellungen_halten_sieben_lokale_tage() -> None:
    zone = ZoneInfo(VIENNA)
    cases = [
        # Sommerzeit beginnt am Sonntag, 29.03.2026 (23-Stunden-Tag, +02:00).
        ("2026-03-23", "2026-03-29", 2),
        # Winterzeit beginnt am Sonntag, 25.10.2026 (25-Stunden-Tag, +01:00).
        ("2026-10-19", "2026-10-25", 1),
    ]

    for monday, sunday, expected_offset in cases:
        days = get_week_days(monday, VIENNA)
        assert len(days) == 7
        assert days[0] == monday
        assert days[-1] == sunday
        # Der lokale Kalendertag bleibt auch am Umstellungstag derselbe.
        for day in days:
            local_noon = datetime.fromisoformat(f"{day}T12:00:00").replace(tzinfo=zone)
            assert local_noon.astimezone(zone).date().isoformat() == day
        assert datetime.fromisoformat(f"{sunday}T12:00:00").replace(
            tzinfo=zone
        ).utcoffset().total_seconds() == expected_offset * 3600


def test_f08_kalendergrenzen_liefern_die_fixture_wochen() -> None:
    case = load_case("F08")

    for week in case["weeks"]:
        assert get_week_days(week["from"], case["timeZone"]) == tuple(
            add_calendar_days(week["from"], offset) for offset in range(7)
        )
        assert start_of_planner_week(week["to"], case["timeZone"]) == week["from"]


def test_wochenbeschriftung_fuer_monat_und_jahreswechsel() -> None:
    assert week_label("2026-11-02") == "2.–8. November 2026"
    assert week_label("2026-10-26") == "26. Oktober – 1. November 2026"
    assert week_label("2026-12-28") == "28. Dezember 2026 – 3. Januar 2027"
    assert format_day("2026-11-09") == "9. November"
    assert completion_text("2026-11-09") == "Erledigt am 9. November"


def test_dashboard_und_planer_sind_getrennte_zeitraumvertraege() -> None:
    dashboard = rolling_dashboard_range("2026-11-06", 7, VIENNA)
    planner = planner_week_range("2026-11-02", VIENNA)
    fixture = load_case("F11")["expected"]

    assert (dashboard.start_date, dashboard.end_date) == (
        fixture["dashboard"]["from"],
        fixture["dashboard"]["to"],
    )
    assert (planner.start_date, planner.end_date) == (
        fixture["planner"]["from"],
        fixture["planner"]["to"],
    )
    assert dashboard.key != planner.key
    assert dashboard.contains("2026-10-31") is True
    assert planner.contains("2026-10-31") is False
    assert planner.contains("2026-11-08") is True


def test_f13_planwoche_und_aktivitaetswoche_bleiben_getrennt() -> None:
    case = load_case("F13")
    plan_day = case["plans"][0]["date"]
    activity_day = case["activities"][0]["date"]

    plan_week = planner_week_range(start_of_planner_week(plan_day, VIENNA), VIENNA)
    activity_week = planner_week_range(start_of_planner_week(activity_day, VIENNA), VIENNA)

    assert plan_week.start_date == case["weeks"][0]["from"]
    assert plan_week.end_date == case["weeks"][0]["to"]
    assert activity_week.start_date == case["weeks"][1]["from"]
    assert activity_week.end_date == case["weeks"][1]["to"]
    assert plan_week.contains(activity_day) is False
    assert activity_week.contains(activity_day) is True


def test_aktuelle_woche_kommt_aus_der_laufzeit_und_zeitzone() -> None:
    # 23:30 UTC ist in Wien bereits der nächste lokale Kalendertag.
    moment = datetime.fromisoformat("2026-11-01T23:30:00+00:00")
    assert local_today(VIENNA, now=moment) == "2026-11-02"
    assert current_planner_week(VIENNA, now=moment) == "2026-11-02"
    later = datetime.fromisoformat("2027-02-10T12:00:00+01:00")
    assert current_planner_week(VIENNA, now=later) == "2027-02-08"

    with pytest.raises(ValueError):
        local_today(VIENNA, now=datetime(2026, 11, 1, 12, 0))


def test_api_wochenparameter_ist_ein_lokales_datum() -> None:
    now = datetime.fromisoformat("2026-11-06T12:00:00+01:00")

    assert parse_week_parameter(None, VIENNA, now=now) == "2026-11-02"
    assert parse_week_parameter("", VIENNA, now=now) == "2026-11-02"
    assert parse_week_parameter("2026-11-08", VIENNA, now=now) == "2026-11-02"
    assert parse_week_parameter("2026-12-31", VIENNA, now=now) == "2026-12-28"
    with pytest.raises(ValueError):
        parse_week_parameter("2026-02-30", VIENNA, now=now)
    with pytest.raises(ValueError):
        parse_week_parameter("2026-11-02T09:00:00", VIENNA, now=now)


def test_verschieben_behaelt_uhrzeit_remote_id_und_knoten_ids() -> None:
    plan = replace(
        build_plan_from_case(load_case("F01")),
        date="2026-11-08",
        local_time="18:30",
    )
    node_ids = [node.id for node in plan.nodes]

    moved = reschedule_plan(plan, "2027-01-04")

    assert moved.date == "2027-01-04"
    assert moved.local_time == "18:30"
    assert moved.time_zone == "Europe/Vienna"
    assert moved.remote_id == plan.remote_id
    assert [node.id for node in moved.nodes] == node_ids
