"""P18: Speicherkoordinator, Zustände und genau eine logische Operation."""

from __future__ import annotations

import threading
from dataclasses import replace

import pytest
from planner_fixtures import build_plan_from_case, load_case, snapshot_for_case

from trainings_cockpit.planner import (
    ActivityId,
    ActivityReference,
    Editability,
    InputLocked,
    SaveCoordinator,
    SaveErrorKind,
    SaveState,
    WorkoutDraft,
    WriteResult,
    classify_exception,
)


def _draft(case_id: str = "F01", *, new: bool = False) -> WorkoutDraft:
    case = load_case(case_id)
    plan = build_plan_from_case(case)
    if new:
        return WorkoutDraft.new(replace(plan, remote_id=None, external_id=None, notes=None))
    return WorkoutDraft.start(plan, snapshot_for_case(case))


class Runner:
    def __init__(self, result: WriteResult | None = None) -> None:
        self.result = result or WriteResult(SaveState.SAVED, "ok", remote_id="9101")
        self.calls = []
        self.reconcile_calls = []

    def execute(self, snapshot):
        self.calls.append(snapshot)
        return self.result

    def reconcile(self, snapshot):
        self.reconcile_calls.append(snapshot)
        return self.result


class BlockingRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def execute(self, snapshot):
        self.calls.append(snapshot)
        self.started.set()
        assert self.release.wait(5)
        return self.result


def test_clean_und_dirty_werden_ohne_write_unterschieden() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")

    clean = coordinator.preview(draft, account_id="a", athlete_id="7")
    assert clean.status.state is SaveState.CLEAN
    assert runner.calls == []

    draft.current = replace(draft.current, name="Ruhiger Lauf")
    dirty = coordinator.preview(draft, account_id="a", athlete_id="7")
    assert dirty.status.state is SaveState.DIRTY
    assert dirty.snapshot is not None
    assert dirty.snapshot.payload == {"name": "Ruhiger Lauf"}
    assert runner.calls == []


def test_ungueltiger_entwurf_startet_keinen_write() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, nodes=())

    outcome = coordinator.activate(draft, account_id="a", athlete_id="7")

    assert outcome.status.state is SaveState.INVALID
    assert outcome.status.error is SaveErrorKind.BOUNDARY
    assert runner.calls == []


def test_zehn_schnelle_aktivierungen_sind_eine_operation() -> None:
    runner = BlockingRunner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Nur einmal speichern")
    outcomes: list = []
    errors: list[BaseException] = []

    def activate() -> None:
        try:
            outcomes.append(
                coordinator.activate(draft, account_id="a", athlete_id="7")
            )
        except BaseException as exc:  # noqa: BLE001 - Test soll den Threadfehler zeigen
            errors.append(exc)

    first = threading.Thread(target=activate)
    first.start()
    assert runner.started.wait(5)
    rest = [threading.Thread(target=activate) for _ in range(9)]
    for thread in rest:
        thread.start()
    for thread in rest:
        thread.join(5)
    runner.release.set()
    first.join(5)

    assert errors == []
    assert len(runner.calls) == 1
    assert len(outcomes) == 10
    operation_ids = {str(outcome.status.operation_id) for outcome in outcomes}
    assert len(operation_ids) == 1
    assert {outcome.status.state for outcome in outcomes} <= {
        SaveState.SAVING,
        SaveState.SAVED,
    }


def test_wiederholte_aktivierung_nach_erfolg_schreibt_nicht_erneut() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Einmal reicht")

    first = coordinator.activate(draft, account_id="a", athlete_id="7")
    second = coordinator.activate(draft, account_id="a", athlete_id="7")

    assert first.status.state is SaveState.SAVED
    assert second.status.state is SaveState.SAVED
    assert str(first.status.operation_id) == str(second.status.operation_id)
    assert len(runner.calls) == 1


def test_snapshot_und_payload_sind_unveraenderlich() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Eingefroren")

    coordinator.activate(draft, account_id="a", athlete_id="7")
    snapshot = runner.calls[0]
    assert snapshot.intended.name == "Eingefroren"
    assert snapshot.payload == {"name": "Eingefroren"}

    draft.current = replace(draft.current, name="Nachträglich")
    assert snapshot.intended.name == "Eingefroren"
    assert snapshot.payload == {"name": "Eingefroren"}


def test_fehler_laesst_entwurf_bestehen_und_erlaubt_erneuten_versuch() -> None:
    runner = Runner(
        WriteResult(
            SaveState.FAILED,
            "Remote nicht erreichbar",
            error=SaveErrorKind.NETWORK,
            retryable=True,
        )
    )
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Bleibt lokal")

    first = coordinator.activate(draft, account_id="a", athlete_id="7")
    second = coordinator.activate(draft, account_id="a", athlete_id="7")

    assert first.status.state is SaveState.FAILED
    assert draft.current.name == "Bleibt lokal"
    assert len(runner.calls) == 2
    assert str(first.status.operation_id) == str(second.status.operation_id)


def test_unklarer_ausgang_sperrt_eingaben_und_startet_keinen_zweiten_write() -> None:
    runner = Runner(
        WriteResult(
            SaveState.UNKNOWN,
            "Antwort verloren",
            error=SaveErrorKind.TIMEOUT,
            reconciliation_required=True,
        )
    )
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Unklar")

    first = coordinator.activate(draft, account_id="a", athlete_id="7")
    second = coordinator.activate(draft, account_id="a", athlete_id="7")

    assert first.status.state is SaveState.UNKNOWN
    assert first.status.locked is True
    assert second.status.state is SaveState.UNKNOWN
    assert len(runner.calls) == 1
    with pytest.raises(InputLocked):
        coordinator.ensure_editable(draft, account_id="a", athlete_id="7")


def test_nur_geplante_workoutentwuerfe_starten_einen_write() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    activity = ActivityReference(ActivityId("9101"), "a", "7")

    outcome = coordinator.activate(activity, account_id="a", athlete_id="7")

    assert outcome.status.state is SaveState.INVALID
    assert outcome.status.error is SaveErrorKind.BOUNDARY
    assert runner.calls == []


def test_pro_einheit_und_account_getrennte_operationen() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Getrennt")

    first = coordinator.activate(draft, account_id="a", athlete_id="7")
    second = coordinator.activate(draft, account_id="b", athlete_id="7")

    assert len(runner.calls) == 2
    assert first.status.state is SaveState.SAVED
    assert second.status.state is SaveState.SAVED
    assert str(first.status.operation_id) == str(second.status.operation_id)


def test_klassifikation_unterscheidet_timeout_von_bestaetigtem_fehler() -> None:
    timeout = classify_exception(TimeoutError("zu spät"))
    assert timeout.state is SaveState.UNKNOWN
    assert timeout.reconciliation_required is True

    class HttpError(RuntimeError):
        status_code = 404

    missing = classify_exception(HttpError("weg"))
    assert missing.state is SaveState.FAILED
    assert missing.error is SaveErrorKind.NOT_FOUND


def test_metadaten_only_und_read_only_werden_respektiert() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(
        draft.current,
        editability=Editability.READ_ONLY,
        editability_reason="Remote gesperrt",
    )

    outcome = coordinator.activate(draft, account_id="a", athlete_id="7")
    assert outcome.status.state is SaveState.INVALID
    assert runner.calls == []


def test_status_traegt_vorgang_und_lokale_zuordnung() -> None:
    runner = Runner()
    coordinator = SaveCoordinator(runner)
    draft = _draft("F01")
    draft.current = replace(draft.current, name="Zuordnung")

    outcome = coordinator.activate(draft, account_id="acct", athlete_id="ath")
    snapshot = outcome.snapshot
    assert snapshot is not None
    assert snapshot.account_id == "acct"
    assert snapshot.athlete_id == "ath"
    assert str(snapshot.local_id) == "plan:f01"
    assert str(snapshot.operation_id) == str(draft.operation_id)
    assert outcome.status.operation_id == draft.operation_id
