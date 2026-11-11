"""P1: lokale Workout-Vorlagen und der gemeinsame Klon-Dienst."""

from __future__ import annotations

import json
import socket
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from planner_fixtures import build_plan_from_case, load_case, load_remote

from trainings_cockpit import db
from trainings_cockpit.planner import (
    TEMPLATE_SCHEMA_VERSION,
    CloneCode,
    CloneError,
    HeartRateTarget,
    NodeId,
    OpenEnd,
    RepeatNode,
    StepNode,
    TemplateCode,
    TemplateError,
    TimeEnd,
    UnsupportedNode,
    Value,
    ZoneMetric,
    ZoneTarget,
    clone_for_new_plan,
    delete_template,
    get_template,
    instantiate,
    list_templates,
    nodes_from_json,
    nodes_to_json,
    read_remote_event,
    save_from_plan,
)
from trainings_cockpit.planner.shapes import plan_shape

F01_EVENT = load_remote("simple-zone-run.json")["event"]
F02_EVENT = load_remote("repeated-intervals.json")["event"]
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=ZoneInfo("Europe/Vienna"))
LATER = datetime(2026, 11, 11, 13, 0, tzinfo=ZoneInfo("Europe/Vienna"))


def _plan(event: dict | None = None):
    return read_remote_event(
        event or F01_EVENT,
        fetched_at="2026-11-11T08:00:00+01:00",
        time_zone="Europe/Vienna",
    ).plan


def _conn(tmp_path):
    conn = db.connect(tmp_path / "cockpit.db")
    db.init_db(conn)
    return conn


def _count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608


def _save(conn, plan=None, *, name="Vorlage", account="a", athlete="x", **kwargs):
    return save_from_plan(
        conn,
        plan or _plan(),
        name=name,
        account_id=account,
        athlete_id=athlete,
        now=kwargs.pop("now", NOW),
        **kwargs,
    )


def test_init_db_creates_and_upgrades_the_template_table(tmp_path) -> None:
    conn = _conn(tmp_path)
    db.upsert_events(conn, [F01_EVENT])
    assert _count(conn, "workout_template") == 0
    db.init_db(conn)
    db.init_db(conn)
    assert db.event_by_id(conn, 9101) is not None

    conn.execute("DROP TABLE workout_template")
    conn.commit()
    db.init_db(conn)
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workout_template'"
    ).fetchone() is not None

    _save(conn)
    db.init_db(conn)
    assert _count(conn, "workout_template") == 1


def test_template_survives_source_deletion_and_restart(tmp_path) -> None:
    path = tmp_path / "cockpit.db"
    conn = db.connect(path)
    db.init_db(conn)
    db.upsert_events(conn, [F01_EVENT])
    saved = _save(conn, source_event_id="9101")
    assert db.delete_event(conn, 9101) is True
    conn.close()

    conn = db.connect(path)
    db.init_db(conn)
    loaded = get_template(
        conn, saved.template_id, account_id="a", athlete_id="x"
    )
    assert loaded is not None
    assert loaded.source_event_id == "9101"
    assert plan_shape(_template_plan(loaded)) == plan_shape(_template_plan(saved))


def _template_plan(template):
    from trainings_cockpit.planner import PlanId, PlannedWorkout

    return PlannedWorkout(
        local_id=PlanId.new(),
        name=template.name,
        sport=template.sport,
        date="2026-11-11",
        time_zone="UTC",
        nodes=template.nodes,
    )


def test_scope_and_delete_are_account_bound(tmp_path) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn)
    assert list_templates(conn, account_id="b", athlete_id="y") == []
    assert get_template(conn, saved.template_id, account_id="b", athlete_id="y") is None
    assert delete_template(
        conn, saved.template_id, account_id="b", athlete_id="y"
    ) is False
    assert get_template(
        conn, saved.template_id, account_id="a", athlete_id="x"
    ) is not None

    second = _save(conn, name="Vorlage", account="a", athlete="y")
    assert second.template_id != saved.template_id
    assert len(list_templates(conn, account_id="a", athlete_id="y")) == 1


def test_save_rekeys_and_does_not_copy_identity(tmp_path) -> None:
    conn = _conn(tmp_path)
    source = _plan(F02_EVENT)
    saved = _save(conn, source, source_event_id="9102")

    source_ids = {str(node.id) for node in source.nodes}
    saved_ids = {str(node.id) for node in saved.nodes}
    assert source_ids.isdisjoint(saved_ids)
    assert all(node.notes is None for node in saved.nodes if isinstance(node, StepNode))
    assert all(node.source_ref is None for node in saved.nodes)

    raw = json.loads(
        conn.execute(
            "SELECT nodes_json FROM workout_template WHERE template_id = ?",
            (saved.template_id,),
        ).fetchone()[0]
    )
    assert isinstance(raw, list)
    assert all(node["id"] not in source_ids for node in raw)
    assert all(node.get("notes") is None for node in raw if node["kind"] == "step")
    assert all(node.get("source_ref") is None for node in raw)
    serialized = json.dumps(raw)
    assert "remote_id" not in serialized
    assert "external_id" not in serialized
    assert "node_id" not in serialized


def test_two_instantiations_are_independent(tmp_path) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn, _plan(F02_EVENT))
    before = plan_shape(_template_plan(saved))

    first, first_draft = instantiate(
        saved,
        target_date="2026-11-17",
        time_zone="Europe/Vienna",
        draft_id="draft:new:first",
        account_id="a",
        athlete_id="x",
    )
    second, second_draft = instantiate(
        saved,
        target_date="2026-11-17",
        time_zone="Europe/Vienna",
        draft_id="draft:new:second",
        account_id="a",
        athlete_id="x",
    )

    assert first.local_id != second.local_id
    assert first_draft.draft_id != second_draft.draft_id
    assert first_draft.operation_id != second_draft.operation_id
    first_ids = {str(node.id) for node in first.nodes}
    second_ids = {str(node.id) for node in second.nodes}
    assert first_ids.isdisjoint(second_ids)
    assert first_ids.isdisjoint({str(node.id) for node in saved.nodes})
    assert plan_shape(first) == plan_shape(second)
    assert plan_shape(_template_plan(saved)) == before
    assert first.remote_id is None and first.external_id is None
    assert first.local_time is None
    assert first_draft.current == first
    assert first_draft.draft_id.value == "draft:new:first"
    assert first.local_id.value == "plan:draft:new:first"


@pytest.mark.parametrize("case_id", ["F03", "F04"])
def test_clone_covers_supported_sport_structures(tmp_path, case_id) -> None:
    conn = _conn(tmp_path)
    plan = build_plan_from_case(load_case(case_id))
    saved = _save(conn, plan)
    first, _ = instantiate(
        saved,
        target_date="2026-11-11",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
    )
    second, _ = instantiate(
        saved,
        target_date="2026-11-11",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
    )
    assert first.sport == plan.sport
    assert plan_shape(first) == plan_shape(second)
    assert plan_shape(first) == plan_shape(_template_plan(saved))


def _rename_steps(nodes):
    out = []
    for node in nodes:
        if isinstance(node, StepNode):
            out.append(replace(node, name="Schwimmzug"))
        elif isinstance(node, RepeatNode):
            out.append(replace(node, children=_rename_steps(node.children)))
        else:
            out.append(node)
    return tuple(out)


def test_clone_covers_swim_pace_structure(tmp_path) -> None:
    conn = _conn(tmp_path)
    swim = build_plan_from_case(load_case("F05"))
    safe_swim = replace(swim, nodes=_rename_steps(swim.nodes))
    saved = _save(conn, safe_swim)
    cloned, _ = instantiate(
        saved,
        target_date="2026-11-11",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
    )
    assert cloned.sport == "Swim"
    assert plan_shape(cloned) == plan_shape(_template_plan(saved))


def test_measurement_in_step_name_is_rejected_with_concrete_code(tmp_path) -> None:
    conn = _conn(tmp_path)
    with pytest.raises(TemplateError) as info:
        _save(conn, build_plan_from_case(load_case("F05")))
    assert info.value.code is TemplateCode.SOURCE_NOT_CLONEABLE
    assert info.value.clone_code is CloneCode.SERIALIZATION_FAILED
    assert _count(conn, "workout_template") == 0


def test_instantiate_rejects_foreign_template(tmp_path) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn, account="a", athlete="x")

    for account, athlete in (("b", "x"), ("a", "y"), (" ", " ")):
        with pytest.raises(TemplateError) as info:
            instantiate(
                saved,
                target_date="2026-11-17",
                time_zone="Europe/Vienna",
                account_id=account,
                athlete_id=athlete,
            )
        assert info.value.code is TemplateCode.SCOPE_MISMATCH

    plan, draft = instantiate(
        saved,
        target_date="2026-11-17",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
    )
    assert plan.date == "2026-11-17"
    assert draft.current == plan
    assert _count(conn, "workout_template") == 1


def test_clone_keeps_date_and_optionally_time() -> None:
    source = replace(_plan(), local_time="07:30")
    plan, draft = clone_for_new_plan(
        source,
        target_date="2026-03-29",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
        keep_time=False,
    )
    assert plan.date == "2026-03-29"
    assert plan.local_time is None
    assert draft.current == plan

    plan_with_time, _ = clone_for_new_plan(
        source,
        target_date="2026-03-29",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
        keep_time=True,
    )
    assert plan_with_time.local_time == "07:30"

    copy_plan, copy_draft = clone_for_new_plan(
        source,
        target_date="2026-03-30",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
        local_id="plan:copy:one",
        operation_id="operation:one",
    )
    assert copy_plan.local_id.value == "plan:copy:one"
    assert copy_draft.operation_id.value == "operation:one"

    with pytest.raises(CloneError) as invalid_date:
        clone_for_new_plan(
            source,
            target_date="29.03.2026",
            time_zone="Europe/Vienna",
            account_id="a",
            athlete_id="x",
        )
    assert invalid_date.value.code is CloneCode.INVALID_DATE

    with pytest.raises(CloneError) as invalid_zone:
        clone_for_new_plan(
            source,
            target_date="2026-03-29",
            time_zone="Nowhere/Zone",
            account_id="a",
            athlete_id="x",
        )
    assert invalid_zone.value.code is CloneCode.INVALID_TIME_ZONE

    with pytest.raises(CloneError) as invalid_scope:
        clone_for_new_plan(
            source,
            target_date="2026-03-29",
            time_zone="Europe/Vienna",
            account_id="",
            athlete_id="x",
        )
    assert invalid_scope.value.code is CloneCode.INVALID_IDENTITY


def test_template_name_and_sport_validation(tmp_path) -> None:
    conn = _conn(tmp_path)
    cases = [
        ("", TemplateCode.NAME_EMPTY),
        ("   ", TemplateCode.NAME_EMPTY),
        ("x" * 121, TemplateCode.NAME_TOO_LONG),
        ("Zeile\numbruch", TemplateCode.NAME_INVALID),
    ]
    for name, code in cases:
        with pytest.raises(TemplateError) as info:
            _save(conn, name=name)
        assert info.value.code is code
    assert _count(conn, "workout_template") == 0

    with pytest.raises(TemplateError) as info:
        _save(conn, replace(_plan(), sport="Other"))
    assert info.value.code is TemplateCode.SPORT_UNSUPPORTED

    with pytest.raises(TemplateError) as info:
        _save(conn, account=" ")
    assert info.value.code is TemplateCode.INVALID_SCOPE

    first = _save(conn, name="  Gleicher Name  ")
    _save(conn, name="Gleicher Name")
    assert first.name == "Gleicher Name"
    assert _count(conn, "workout_template") == 2


def _first_step(plan):
    return next(node for node in plan.nodes if isinstance(node, StepNode))


def _repeat(plan):
    return next(node for node in plan.nodes if isinstance(node, RepeatNode))


def _with_repeat(plan, **changes):
    return replace(
        plan,
        nodes=tuple(
            replace(node, **changes) if isinstance(node, RepeatNode) else node
            for node in plan.nodes
        ),
    )


@pytest.mark.parametrize(
    ("mutate", "clone_code"),
    [
        (lambda plan: replace(plan, nodes=()), CloneCode.EMPTY_STRUCTURE),
        (lambda plan: replace(plan, notes="Notiz"), CloneCode.NOTES),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    replace(_first_step(plan), notes="Schrittnotiz"),
                    *plan.nodes[1:],
                ),
            ),
            CloneCode.NOTES,
        ),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    replace(_first_step(plan), end=OpenEnd()),
                    *plan.nodes[1:],
                ),
            ),
            CloneCode.OPEN_END,
        ),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    replace(
                        _first_step(plan),
                        target=HeartRateTarget(values=Value(150)),
                    ),
                    *plan.nodes[1:],
                ),
            ),
            CloneCode.ABSOLUTE_HR,
        ),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    replace(
                        _first_step(plan),
                        target=ZoneTarget(
                            metric=ZoneMetric.POWER,
                            zone_id="power-2",
                        ),
                    ),
                    *plan.nodes[1:],
                ),
            ),
            CloneCode.POWER_ZONE,
        ),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    UnsupportedNode(
                        id=NodeId.new(),
                        label="Spezial",
                        reason="Nicht abbildbar",
                        source_ref="/special",
                    ),
                ),
            ),
            CloneCode.UNSUPPORTED_NODE,
        ),
        (
            lambda plan: _with_repeat(plan, children=()),
            CloneCode.EMPTY_REPEAT,
        ),
        (
            lambda plan: _with_repeat(plan, skip_final_recovery=True),
            CloneCode.SKIP_FINAL_RECOVERY,
        ),
        (
            lambda plan: _with_repeat(
                plan,
                children=(
                    _nested_repeat_child(),
                    _repeat(plan).children[1],
                ),
            ),
            CloneCode.NESTED_REPEAT,
        ),
        (
            lambda plan: replace(
                plan,
                nodes=(
                    replace(_first_step(plan), name="5 min"),
                    *plan.nodes[1:],
                ),
            ),
            CloneCode.SERIALIZATION_FAILED,
        ),
    ],
)
def test_clone_rejects_unsupported_structures_with_stable_codes(
    tmp_path, mutate, clone_code
) -> None:
    conn = _conn(tmp_path)
    plan = mutate(_plan(F02_EVENT))
    with pytest.raises(TemplateError) as info:
        _save(conn, plan)
    assert info.value.code is TemplateCode.SOURCE_NOT_CLONEABLE
    assert info.value.clone_code is clone_code
    assert _count(conn, "workout_template") == 0


def _nested_repeat_child() -> RepeatNode:
    return RepeatNode(
        id=NodeId.new(),
        name="Kind",
        repetitions=2,
        children=(
            StepNode(
                id=NodeId.new(),
                name="Schritt",
                end=OpenEnd(),
            ),
        ),
    )


def test_list_summary_and_order(tmp_path) -> None:
    conn = _conn(tmp_path)
    first = _save(conn, _plan(F01_EVENT), name="Lauf", now=NOW)
    second = _save(conn, _plan(F02_EVENT), name="Intervalle", now=LATER)

    summaries = list_templates(conn, account_id="a", athlete_id="x")
    assert [item.template_id for item in summaries] == [
        second.template_id,
        first.template_id,
    ]
    by_id = {item.template_id: item for item in summaries}
    assert by_id[first.template_id].known_seconds == 2700
    assert by_id[first.template_id].executions == 1
    assert by_id[first.template_id].available is True
    assert by_id[second.template_id].known_seconds == 2160
    assert by_id[second.template_id].executions == 10


def test_corrupt_and_unknown_schema_rows_are_visible(tmp_path) -> None:
    conn = _conn(tmp_path)
    corrupt = _save(conn, name="Defekt")
    unknown = _save(conn, name="Neu")
    conn.execute(
        "UPDATE workout_template SET nodes_json = ? WHERE template_id = ?",
        ("{", corrupt.template_id),
    )
    conn.execute(
        "UPDATE workout_template SET schema_version = ? WHERE template_id = ?",
        (TEMPLATE_SCHEMA_VERSION + 1, unknown.template_id),
    )
    conn.commit()

    with pytest.raises(TemplateError) as corrupt_error:
        get_template(conn, corrupt.template_id, account_id="a", athlete_id="x")
    assert corrupt_error.value.code is TemplateCode.CORRUPT

    with pytest.raises(TemplateError) as schema_error:
        get_template(conn, unknown.template_id, account_id="a", athlete_id="x")
    assert schema_error.value.code is TemplateCode.SCHEMA_UNSUPPORTED

    summaries = list_templates(conn, account_id="a", athlete_id="x")
    by_id = {item.template_id: item for item in summaries}
    assert by_id[corrupt.template_id].available is False
    assert by_id[corrupt.template_id].error_code == TemplateCode.CORRUPT.value
    assert by_id[unknown.template_id].available is False
    assert (
        by_id[unknown.template_id].error_code
        == TemplateCode.SCHEMA_UNSUPPORTED.value
    )


def _step(node_id: str, name: str, seconds: int = 600) -> StepNode:
    return StepNode(id=NodeId(node_id), name=name, end=TimeEnd(seconds))


def _set_nodes(conn, template_id: str, nodes) -> None:
    conn.execute(
        "UPDATE workout_template SET nodes_json = ? WHERE template_id = ?",
        (json.dumps(nodes_to_json(nodes)), template_id),
    )
    conn.commit()


@pytest.mark.parametrize(
    "nodes",
    [
        (),
        (_step("node:dup", "Erster"), _step("node:dup", "Zweiter")),
        (
            StepNode(
                id=NodeId("node:open"),
                name="Offen",
                end=OpenEnd(),
            ),
        ),
        (
            UnsupportedNode(
                id=NodeId("node:special"),
                label="Spezial",
                reason="Nicht abbildbar",
                source_ref="/special",
            ),
        ),
    ],
    ids=["leer", "doppelte-id", "offenes-ende", "unbekannter-knoten"],
)
def test_semantically_broken_nodes_are_corrupt(tmp_path, nodes) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn)
    _set_nodes(conn, saved.template_id, nodes)

    with pytest.raises(TemplateError) as info:
        get_template(conn, saved.template_id, account_id="a", athlete_id="x")
    assert info.value.code is TemplateCode.CORRUPT

    summaries = list_templates(conn, account_id="a", athlete_id="x")
    assert len(summaries) == 1
    assert summaries[0].available is False
    assert summaries[0].error_code == TemplateCode.CORRUPT.value


def test_unsupported_sport_in_stored_template_is_corrupt(tmp_path) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn)
    conn.execute(
        "UPDATE workout_template SET sport = ? WHERE template_id = ?",
        ("Other", saved.template_id),
    )
    conn.commit()

    with pytest.raises(TemplateError) as info:
        get_template(conn, saved.template_id, account_id="a", athlete_id="x")
    assert info.value.code is TemplateCode.CORRUPT

    summaries = list_templates(conn, account_id="a", athlete_id="x")
    assert len(summaries) == 1
    assert summaries[0].available is False
    assert summaries[0].error_code == TemplateCode.CORRUPT.value


def test_delete_template_leaves_events_alone(tmp_path) -> None:
    conn = _conn(tmp_path)
    db.upsert_events(conn, [F01_EVENT])
    saved = _save(conn, source_event_id="9101")
    assert delete_template(
        conn, saved.template_id, account_id="a", athlete_id="x"
    ) is True
    assert get_template(conn, saved.template_id, account_id="a", athlete_id="x") is None
    assert db.event_by_id(conn, 9101) is not None
    assert delete_template(
        conn, saved.template_id, account_id="a", athlete_id="x"
    ) is False


def test_node_codec_is_the_operations_codec(tmp_path) -> None:
    conn = _conn(tmp_path)
    saved = _save(conn, _plan(F02_EVENT))
    raw = json.loads(
        conn.execute(
            "SELECT nodes_json FROM workout_template WHERE template_id = ?",
            (saved.template_id,),
        ).fetchone()[0]
    )
    assert raw[0]["kind"] == "step"
    assert "id" in raw[0]
    assert "node_id" not in raw[0]
    assert raw[0]["notes"] is None
    assert raw[0]["source_ref"] is None
    assert nodes_to_json(nodes_from_json(raw)) == raw


def test_no_network_and_no_event_or_operation_writes(tmp_path, monkeypatch) -> None:
    conn = _conn(tmp_path)

    def deny(*_args, **_kwargs):
        raise AssertionError("Netzwerkzugriff im P1-Pfad")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)

    before_events = _count(conn, "event")
    before_operations = _count(conn, "planner_operation")
    saved = _save(conn)
    list_templates(conn, account_id="a", athlete_id="x")
    assert get_template(conn, saved.template_id, account_id="a", athlete_id="x")
    instantiate(
        saved,
        target_date="2026-11-17",
        time_zone="Europe/Vienna",
        account_id="a",
        athlete_id="x",
    )
    assert _count(conn, "event") == before_events
    assert _count(conn, "planner_operation") == before_operations
    assert _count(conn, "workout_template") == 1
