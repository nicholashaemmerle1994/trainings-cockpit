"""Adapterbrücke für bestätigte Event-Writes — Update und Rückleseprüfung.

Der Dienst führt keinen eigenen HTTP-Aufruf aus. Er arbeitet gegen ein
schmales Gateway, das im Produkt später der vorhandene ``IntervalsClient``
ist und in den P18/P19-Tests der kontrollierte Testadapter. Dadurch bleibt der
Produktivschreibweg gesperrt, während Payload, Event-ID, Rücklesen und
Rundlauf nach Abschnitt 8.8 nachweisbar sind.

Ein Update verwendet ausschließlich die ursprüngliche Remote-Event-ID. Ein
404 wird nie zu einem Create. Nur nach bestätigtem Rücklesen und semantisch
gleichem Ablauf werden Werte als bestätigt übernommen.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from .model import (
    DistanceEnd,
    NoTarget,
    PaceTarget,
    PlannedWorkout,
    PowerTarget,
    RepeatNode,
    StepNode,
    TimeEnd,
    UnsupportedNode,
    Value,
    WorkoutNode,
    ZoneTarget,
)
from .remote import read_remote_event
from .save import (
    SaveErrorKind,
    SaveSnapshot,
    SaveState,
    WriteResult,
    classify_exception,
)


class GatewayError(RuntimeError):
    """Ein Fehler des Event-Gateways mit optionalem HTTP-Status."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GatewayNotFound(GatewayError):
    def __init__(self, remote_id: str) -> None:
        super().__init__(
            f"Remote-Event {remote_id} wurde nicht gefunden.",
            status_code=404,
        )


class GatewayConflict(GatewayError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class EventGateway(Protocol):
    """Die minimale Schreib-/Lesebrücke zum vorhandenen Event-Dienst."""

    def read_event(self, remote_id: str) -> Mapping[str, Any]: ...

    def update_event(
        self, remote_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RoundtripCheck:
    valid: bool
    reason: str | None = None


def _num(value: float) -> float:
    return round(float(value), 6)


def _target_shape(target: Any) -> tuple[Any, ...]:
    if isinstance(target, NoTarget):
        return ("none",)
    if isinstance(target, ZoneTarget):
        return ("zone", target.metric.value, target.zone_id)
    if isinstance(target, PowerTarget):
        values = target.values
        if isinstance(values, Value):
            return ("power", target.unit.value, "value", _num(values.value))
        return ("power", target.unit.value, "range", _num(values.min), _num(values.max))
    if isinstance(target, PaceTarget):
        values = target.values
        if isinstance(values, Value):
            return ("pace", target.unit.value, "value", _num(values.value))
        return ("pace", target.unit.value, "range", _num(values.min), _num(values.max))
    # Absolute bpm und andere nicht serialisierbare Ziele sind kein
    # bestätigter Schreibfall; der Vergleich meldet sie ausdrücklich.
    return ("unsupported", type(target).__name__)


def _node_shape(node: WorkoutNode) -> tuple[Any, ...]:
    if isinstance(node, UnsupportedNode):
        return ("unsupported", node.source_ref)
    if isinstance(node, StepNode):
        end = node.end
        if isinstance(end, TimeEnd):
            end_shape = ("time", _num(end.seconds))
        elif isinstance(end, DistanceEnd):
            end_shape = ("distance", _num(end.metres))
        else:
            end_shape = ("open",)
        return (
            "step",
            node.name,
            node.role.value,
            end_shape,
            _target_shape(node.target),
            node.notes,
        )
    if isinstance(node, RepeatNode):
        return (
            "repeat",
            node.name,
            node.repetitions,
            node.skip_final_recovery,
            tuple(_node_shape(child) for child in node.children),
        )
    raise TypeError(f"Unbekannter Knoten: {type(node).__name__}")


def plan_shape(plan: PlannedWorkout) -> dict[str, Any]:
    """Vergleichsprojektion ohne Renderzustand, lokale IDs oder Abrufzeiten."""
    return {
        "name": plan.name,
        "sport": plan.sport,
        "date": plan.date,
        "local_time": plan.local_time,
        "notes": plan.notes,
        "nodes": tuple(_node_shape(node) for node in plan.nodes),
    }


_NOT_GIVEN = object()


def verify_roundtrip(
    intended: PlannedWorkout,
    actual: PlannedWorkout,
    *,
    expected_notes: str | None | object = _NOT_GIVEN,
) -> RoundtripCheck:
    """Prüft den fachlichen Rundlauf aus Abschnitt 8.8.

    Interne Knoten-IDs, die lokale Plan-ID und die Remote-ID sind keine
    fachlichen Unterschiede. Anzahl, Reihenfolge, Gruppensemantik, Rollen,
    Ende-Bedingungen, Zielarten, Einheiten und Werte müssen übereinstimmen.
    ``expected_notes`` erlaubt dem Aufrufer, die tatsächlich vorhandenen
    Remote-Notizen der Basis zu prüfen, statt eine rein lokale Notiz zu
    verlangen.
    """
    expected = plan_shape(intended)
    received = plan_shape(actual)
    if expected_notes is not _NOT_GIVEN:
        expected = {**expected, "notes": expected_notes}
    for field in ("name", "sport", "date", "local_time", "notes"):
        if expected[field] != received[field]:
            return RoundtripCheck(
                False,
                f"{field} weicht nach dem Rücklesen ab "
                f"({expected[field]!r} statt {received[field]!r}).",
            )
    if expected["nodes"] != received["nodes"]:
        return RoundtripCheck(
            False,
            "Der zurückgelesene Aufbau entspricht nicht dem beabsichtigten Ablauf.",
        )
    return RoundtripCheck(True)


def _remote_base_notes(snapshot: SaveSnapshot) -> str | None:
    """Die Notizen, die im Remote-Basiszustand tatsächlich vorhanden waren."""
    if snapshot.mode == "create":
        return snapshot.intended.notes
    return snapshot.base_notes


def _unverified(
    message: str,
    *,
    snapshot: SaveSnapshot,
    remote_id: str | None = None,
    error: SaveErrorKind = SaveErrorKind.ROUNDTRIP,
) -> WriteResult:
    return WriteResult(
        SaveState.SAVED_UNVERIFIED,
        message,
        remote_id=remote_id,
        external_id=snapshot.external_id,
        error=error,
        reconciliation_required=True,
    )


class EventWriteService:
    """Führt Update-Writes gegen das Gateway aus und liest das Ergebnis nach."""

    def __init__(
        self,
        gateway: EventGateway,
        *,
        preflight: Callable[[SaveSnapshot], None] | None = None,
    ) -> None:
        if not callable(getattr(gateway, "read_event", None)):
            raise TypeError("gateway muss read_event() anbieten.")
        if not callable(getattr(gateway, "update_event", None)):
            raise TypeError("gateway muss update_event() anbieten.")
        self._gateway = gateway
        self._preflight = preflight

    def execute(self, snapshot: SaveSnapshot) -> WriteResult:
        if not isinstance(snapshot, SaveSnapshot):
            raise TypeError("execute akzeptiert nur einen SaveSnapshot.")
        if not snapshot.writable:
            return WriteResult(
                SaveState.FAILED,
                snapshot.writable_reason
                or "Für diese Einheit fehlt die Schreibberechtigung.",
                error=SaveErrorKind.PERMISSION,
            )
        if not snapshot.intended.is_metadata_editable:
            return WriteResult(
                SaveState.FAILED,
                snapshot.intended.editability_reason
                or "Diese Planung ist remote nicht editierbar.",
                error=SaveErrorKind.PERMISSION,
            )
        if snapshot.mode == "create":
            return WriteResult(
                SaveState.FAILED,
                "Die Neuanlage wird erst in P20 angeschlossen.",
                error=SaveErrorKind.IDENTITY,
            )
        return self._update(snapshot)

    def _update(self, snapshot: SaveSnapshot) -> WriteResult:
        remote_id = str(snapshot.remote_id) if snapshot.remote_id is not None else None
        if remote_id is None:
            return WriteResult(
                SaveState.FAILED,
                "Ein Update braucht die ursprüngliche Remote-Event-ID.",
                error=SaveErrorKind.IDENTITY,
            )
        try:
            if self._preflight is not None:
                self._preflight(snapshot)
            response = self._gateway.update_event(remote_id, snapshot.payload)
        except BaseException as exc:  # noqa: BLE001 - Klassifikation ist Teil des Vertrags
            return classify_exception(exc)

        if not isinstance(response, Mapping):
            return _unverified(
                "Der Write wurde beantwortet, aber die Antwort ist nicht prüfbar. "
                "Die Event-ID bleibt erhalten; es wird nichts neu angelegt.",
                snapshot=snapshot,
                remote_id=remote_id,
            )
        response_id = response.get("id")
        if response_id is not None and str(response_id) != remote_id:
            return WriteResult(
                SaveState.FAILED,
                "Die Remote-Antwort gehört zu einer anderen Event-ID. "
                "Es wird weder übernommen noch neu angelegt.",
                remote_id=remote_id,
                external_id=snapshot.external_id,
                error=SaveErrorKind.IDENTITY,
            )

        try:
            raw = self._gateway.read_event(remote_id)
        except BaseException as exc:  # noqa: BLE001
            classified = classify_exception(exc)
            return _unverified(
                "Der Write wurde bestätigt, das Rücklesen ist aber fehlgeschlagen. "
                "Die Event-ID bleibt erhalten; es wird nicht erneut geschrieben.",
                snapshot=snapshot,
                remote_id=remote_id,
                error=classified.error or SaveErrorKind.ROUNDTRIP,
            )
        return self._confirm(snapshot, raw, remote_id)

    def _confirm(
        self,
        snapshot: SaveSnapshot,
        raw: Mapping[str, Any],
        remote_id: str,
    ) -> WriteResult:
        try:
            remote = read_remote_event(
                raw,
                fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                time_zone=snapshot.intended.time_zone,
                account_id=snapshot.account_id,
                athlete_id=snapshot.athlete_id,
            )
        except (TypeError, ValueError) as exc:
            return _unverified(
                f"Das Rücklesen ist nicht als geplantes Workout lesbar: {exc}",
                snapshot=snapshot,
                remote_id=remote_id,
            )
        check = verify_roundtrip(
            snapshot.intended,
            remote.plan,
            expected_notes=_remote_base_notes(snapshot),
        )
        if not check.valid:
            return _unverified(
                f"Der Write wurde bestätigt, aber der Rundlauf weicht ab: {check.reason}",
                snapshot=snapshot,
                remote_id=remote_id,
            )
        return WriteResult(
            SaveState.SAVED,
            "In intervals.icu gespeichert und zurückgelesen.",
            remote_id=remote_id,
            external_id=snapshot.external_id,
            confirmed=remote.plan,
        )

    def reconcile(self, snapshot: SaveSnapshot) -> WriteResult:
        """Liest einen unklaren Update-Vorgang; wiederholt keinen Write."""
        remote_id = str(snapshot.remote_id) if snapshot.remote_id is not None else None
        if remote_id is None:
            return WriteResult(
                SaveState.UNKNOWN,
                "Ohne Remote-ID ist kein lesender Abgleich möglich.",
                external_id=snapshot.external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        try:
            raw = self._gateway.read_event(remote_id)
        except BaseException as exc:  # noqa: BLE001
            classified = classify_exception(exc)
            return WriteResult(
                SaveState.UNKNOWN,
                "Der offene Vorgang konnte noch nicht abgeglichen werden.",
                remote_id=remote_id,
                external_id=snapshot.external_id,
                error=classified.error or SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        try:
            remote = read_remote_event(
                raw,
                fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                time_zone=snapshot.intended.time_zone,
                account_id=snapshot.account_id,
                athlete_id=snapshot.athlete_id,
            )
        except (TypeError, ValueError) as exc:
            return WriteResult(
                SaveState.UNKNOWN,
                f"Der Remote-Inhalt ist noch nicht prüfbar: {exc}",
                remote_id=remote_id,
                external_id=snapshot.external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        if verify_roundtrip(
            snapshot.intended,
            remote.plan,
            expected_notes=_remote_base_notes(snapshot),
        ).valid:
            return WriteResult(
                SaveState.SAVED,
                "Der offene Vorgang ist bestätigt.",
                remote_id=remote_id,
                external_id=snapshot.external_id,
                confirmed=remote.plan,
            )
        if snapshot.base is not None and verify_roundtrip(
            snapshot.base,
            remote.plan,
            expected_notes=_remote_base_notes(snapshot),
        ).valid:
            return WriteResult(
                SaveState.UNKNOWN,
                "Remote steht weiterhin auf dem Basiszustand. Der Vorgang bleibt offen.",
                remote_id=remote_id,
                external_id=snapshot.external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        return WriteResult(
            SaveState.CONFLICT,
            "Remote weicht sowohl von der Basis als auch vom beabsichtigten Ergebnis ab.",
            remote_id=remote_id,
            external_id=snapshot.external_id,
            error=SaveErrorKind.CONFLICT,
        )


class IntervalsEventAdapter:
    """Dünne Brücke auf den vorhandenen ``IntervalsClient``.

    Der Adapter wird nicht von einem Produkt-Endpunkt aufgerufen. Er belegt
    den Update-Vertrag mit der bestehenden Clientklasse; produktives Schreiben
    bleibt bis zur Konfliktsicherung in P21/P22 gesperrt.
    """

    def __init__(self, client: Any) -> None:
        if not callable(getattr(client, "event", None)):
            raise TypeError("client muss event() anbieten.")
        if not callable(getattr(client, "update_event", None)):
            raise TypeError("client muss update_event() anbieten.")
        self._client = client

    def read_event(self, remote_id: str) -> Mapping[str, Any]:
        return self._client.event(int(remote_id))

    def update_event(
        self, remote_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return self._client.update_event(int(remote_id), dict(payload))


__all__ = [
    "EventGateway",
    "EventWriteService",
    "GatewayConflict",
    "GatewayError",
    "GatewayNotFound",
    "IntervalsEventAdapter",
    "RoundtripCheck",
    "plan_shape",
    "verify_roundtrip",
]
