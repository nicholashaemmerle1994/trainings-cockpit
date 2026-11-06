from __future__ import annotations

import pytest

from trainings_cockpit import db
from trainings_cockpit.planner.links import (
    LINKED,
    MANUAL,
    SEPARATED,
    LinkError,
    link_unit,
    resolve_relationships,
    separate_unit,
)


def _plan(event_id: int, day: str, sport: str = "Run") -> dict:
    return {"id": event_id, "date": day, "sport": sport, "name": f"Plan {event_id}"}


def _activity(row_id: int, day: str, sport: str = "Run") -> dict:
    return {"id": row_id, "date": day, "sport": sport, "name": f"Einheit {row_id}"}


def _link(event_id: int, activity_id: int, state: str = LINKED, source: str = MANUAL) -> dict:
    return {
        "event_id": event_id,
        "activity_id": activity_id,
        "state": state,
        "source": source,
    }


def _connection(tmp_path):
    conn = db.connect(tmp_path / "cockpit.db")
    db.init_db(conn)
    return conn


def _seed_unit(
    conn, source_id: str, day: str, sport: str, minutes: int = 60
) -> int:
    db.upsert_activities(
        conn,
        [
            {
                "id": source_id,
                "start_date_local": f"{day}T07:00:00",
                "type": sport,
                "name": source_id,
                "moving_time": minutes * 60,
            }
        ],
    )
    row = conn.execute(
        "SELECT id FROM activity WHERE source_id = ?", (source_id,)
    ).fetchone()
    return int(row["id"])


def _seed_event(
    conn, event_id: int, day: str, sport: str, minutes: int = 60
) -> None:
    db.upsert_events(
        conn,
        [
            {
                "id": event_id,
                "start_date_local": f"{day}T00:00:00",
                "type": sport,
                "category": "WORKOUT",
                "name": f"Plan {event_id}",
                "moving_time": minutes * 60,
            }
        ],
    )


def test_eindeutige_paarung_am_selben_tag_wird_automatisch_verknuepft() -> None:
    relationships, issues = resolve_relationships(
        [_plan(1, "2026-11-04")], [_activity(11, "2026-11-04")], []
    )

    assert issues == []
    assert len(relationships) == 1
    relationship = relationships[0]
    assert relationship.is_complete
    assert relationship.plan.plan_id.value == "plan:event:1"
    assert [activity.activity_id.value for activity in relationship.activities] == ["11"]
    assert relationship.relationship_id.value == "auto:1:11"


def test_zwei_aufzeichnungen_am_selben_tag_bleiben_getrennt() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04")],
        [_activity(11, "2026-11-04"), _activity(12, "2026-11-04")],
        [],
    )

    assert relationships == []


def test_zwei_planungen_am_selben_tag_bleiben_getrennt() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04"), _plan(2, "2026-11-04")],
        [_activity(11, "2026-11-04")],
        [],
    )

    assert relationships == []


def test_verschiedene_sportfamilien_werden_nicht_gepaart() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04", "Run")],
        [_activity(11, "2026-11-04", "Ride")],
        [],
    )

    assert relationships == []


def test_persistente_verknuepfung_gewinnt_auch_bei_mehreren_kandidaten() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04")],
        [_activity(11, "2026-11-04"), _activity(12, "2026-11-04")],
        [_link(1, 12)],
    )

    assert len(relationships) == 1
    assert relationships[0].relationship_id.value == "link:1:12"
    assert [activity.activity_id.value for activity in relationships[0].activities] == [
        "12"
    ]


def test_getrennte_paarung_wird_nicht_automatisch_wiederhergestellt() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04")],
        [_activity(11, "2026-11-04")],
        [_link(1, 11, state=SEPARATED)],
    )

    assert relationships == []


def test_persistente_verknuepfung_blockiert_die_andere_seite() -> None:
    relationships, _ = resolve_relationships(
        [_plan(1, "2026-11-04")],
        [_activity(11, "2026-11-04"), _activity(12, "2026-11-04")],
        [_link(1, 12)],
    )

    assert [relationship.relationship_id.value for relationship in relationships] == [
        "link:1:12"
    ]


def test_neue_verknuepfung_loest_die_alte_derselben_einheit(tmp_path) -> None:
    conn = _connection(tmp_path)
    try:
        _seed_event(conn, 1, "2026-11-04", "Run")
        first = _seed_unit(conn, "a", "2026-11-04", "Run")
        second = _seed_unit(conn, "b", "2026-11-04", "Run")
        db.set_plan_link(
            conn,
            account_id="default",
            athlete_id="default",
            event_id=1,
            activity_id=first,
            source=MANUAL,
        )
        db.set_plan_link(
            conn,
            account_id="default",
            athlete_id="default",
            event_id=1,
            activity_id=second,
            source=MANUAL,
        )
        links = db.plan_links(conn, account_id="default", athlete_id="default")
        assert len(links) == 1
        assert links[0]["event_id"] == 1
        assert links[0]["activity_id"] == second
        assert links[0]["state"] == LINKED
    finally:
        conn.close()


def test_fremdschluessel_entfernt_die_verknuepfung_mit_der_aufzeichnung(
    tmp_path,
) -> None:
    conn = _connection(tmp_path)
    try:
        _seed_event(conn, 1, "2026-11-04", "Run")
        row = _seed_unit(conn, "a", "2026-11-04", "Run")
        db.set_plan_link(
            conn,
            account_id="default",
            athlete_id="default",
            event_id=1,
            activity_id=row,
            source=MANUAL,
        )
        conn.execute("DELETE FROM activity WHERE id = ?", (row,))
        conn.commit()
        assert db.plan_links(conn, account_id="default", athlete_id="default") == []
    finally:
        conn.close()


def test_domaene_verknuepft_und_trennt(tmp_path) -> None:
    conn = _connection(tmp_path)
    try:
        _seed_event(conn, 1, "2026-11-04", "Run")
        row = _seed_unit(conn, "a", "2026-11-04", "Run")

        link_unit(
            conn,
            row,
            1,
            account_id="default",
            athlete_id="default",
            time_zone="Europe/Vienna",
        )
        links = db.plan_links(conn, account_id="default", athlete_id="default")
        assert [(link["state"], link["source"]) for link in links] == [(LINKED, MANUAL)]

        separate_unit(
            conn,
            row,
            1,
            account_id="default",
            athlete_id="default",
            time_zone="Europe/Vienna",
        )
        links = db.plan_links(conn, account_id="default", athlete_id="default")
        assert [(link["state"], link["source"]) for link in links] == [
            (SEPARATED, MANUAL)
        ]
    finally:
        conn.close()


def test_kreuzwoche_und_nicht_trainings_einheit_werden_abgewiesen(tmp_path) -> None:
    conn = _connection(tmp_path)
    try:
        _seed_event(conn, 1, "2026-11-04", "Run")
        row = _seed_unit(conn, "a", "2026-11-11", "Run")
        with pytest.raises(LinkError, match="derselben Woche"):
            link_unit(
                conn,
                row,
                1,
                account_id="default",
                athlete_id="default",
                time_zone="Europe/Vienna",
            )

        _seed_event(conn, 2, "2026-11-04", "Run")
        breath = _seed_unit(conn, "b", "2026-11-04", "Workout")
        with pytest.raises(LinkError, match="Trainingseinheit"):
            link_unit(
                conn,
                breath,
                2,
                account_id="default",
                athlete_id="default",
                time_zone="Europe/Vienna",
            )
    finally:
        conn.close()
