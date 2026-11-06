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
from datetime import date, datetime, timedelta
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

    def create_event(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


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
            return self._create(snapshot)
        return self._update(snapshot)

    def _create(self, snapshot: SaveSnapshot) -> WriteResult:
        """Legt genau eine beabsichtigte Einheit über den belegten Upsertpfad an."""
        external_id = snapshot.external_id or snapshot.payload.get("external_id")
        if not isinstance(external_id, str) or not external_id.strip():
            return WriteResult(
                SaveState.FAILED,
                "Eine Neuanlage braucht vor dem ersten Request eine stabile externe Identität.",
                error=SaveErrorKind.IDENTITY,
            )
        try:
            response = self._gateway.create_event(snapshot.payload)
        except BaseException as exc:  # noqa: BLE001 - Timeout ist ausdrücklich unklar
            classified = classify_exception(exc)
            if classified.state is SaveState.UNKNOWN:
                return WriteResult(
                    classified.state,
                    "Die Anlage könnte angekommen sein. Der Vorgang wird lesend "
                    "abgeglichen und nicht automatisch wiederholt.",
                    external_id=external_id,
                    error=classified.error,
                    reconciliation_required=True,
                )
            return WriteResult(
                classified.state,
                classified.message,
                external_id=external_id,
                error=classified.error,
                retryable=classified.retryable,
            )
        if not isinstance(response, Mapping):
            return _unverified(
                "Die Anlage wurde beantwortet, liefert aber keine prüfbare Remote-ID. "
                "Es wird keine Erfolgs-ID erfunden.",
                snapshot=snapshot,
                remote_id=None,
                error=SaveErrorKind.IDENTITY,
            )
        response_external = response.get("external_id")
        if (
            isinstance(response_external, str)
            and response_external.strip()
            and response_external != external_id
        ):
            return _unverified(
                "Die Remote-Antwort trägt eine andere externe Identität und wird "
                "nicht dieser lokalen Operation zugeordnet.",
                snapshot=snapshot,
                remote_id=None,
                error=SaveErrorKind.IDENTITY,
            )
        response_id = response.get("id")
        if response_id is None or str(response_id).strip() == "":
            return _unverified(
                "Die Anlage wurde bestätigt, aber ohne tatsächliche Remote-ID. "
                "Der Vorgang bleibt zur lesenden Zuordnung offen; es wird keine ID erfunden.",
                snapshot=snapshot,
                remote_id=None,
                error=SaveErrorKind.IDENTITY,
            )
        remote_id = str(response_id)
        try:
            raw = self._gateway.read_event(remote_id)
        except BaseException as exc:  # noqa: BLE001
            classified = classify_exception(exc)
            return _unverified(
                "Die Anlage wurde bestätigt, das Rücklesen ist aber fehlgeschlagen. "
                "Die tatsächliche Remote-ID bleibt erhalten; es wird nicht erneut angelegt.",
                snapshot=snapshot,
                remote_id=remote_id,
                error=classified.error or SaveErrorKind.ROUNDTRIP,
            )
        return self._confirm(
            snapshot,
            raw,
            remote_id,
            expected_external_id=external_id,
        )

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
        *,
        expected_external_id: str | None = None,
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
        if (
            expected_external_id is not None
            and remote.plan.external_id is not None
            and remote.plan.external_id != expected_external_id
        ):
            return _unverified(
                "Das zurückgelesene Event trägt eine andere externe Identität.",
                snapshot=snapshot,
                remote_id=remote_id,
                error=SaveErrorKind.IDENTITY,
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
        """Liest einen unklaren Vorgang; wiederholt keinen Write."""
        if snapshot.mode == "create":
            return self._reconcile_create(snapshot)
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


    def _reconcile_create(self, snapshot: SaveSnapshot) -> WriteResult:
        external_id = snapshot.external_id or snapshot.payload.get("external_id")
        if not isinstance(external_id, str) or not external_id.strip():
            return WriteResult(
                SaveState.UNKNOWN,
                "Ohne externe Identität ist die Anlage nicht lesend zuzuordnen.",
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        find = getattr(self._gateway, "find_by_external_id", None)
        if not callable(find):
            return WriteResult(
                SaveState.UNKNOWN,
                "Der Adapter kann nicht nach der externen Identität suchen; "
                "es wird nicht automatisch erneut angelegt.",
                external_id=external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        try:
            matches = list(find(external_id, str(snapshot.intended.date)))
        except BaseException as exc:  # noqa: BLE001
            classified = classify_exception(exc)
            return WriteResult(
                SaveState.UNKNOWN,
                "Die lesende Zuordnung ist noch nicht möglich.",
                external_id=external_id,
                error=classified.error or SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        if not matches:
            return WriteResult(
                SaveState.UNKNOWN,
                "Es wurde noch kein passendes Remote-Event gefunden. "
                "Der Vorgang bleibt offen; es wird nicht automatisch erneut angelegt.",
                external_id=external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        if len(matches) > 1:
            return WriteResult(
                SaveState.CONFLICT,
                "Mehrere Remote-Events tragen dieselbe externe Identität. "
                "Die Zuordnung wird nicht geraten.",
                external_id=external_id,
                error=SaveErrorKind.CONFLICT,
            )
        raw = matches[0]
        if not isinstance(raw, Mapping):
            return WriteResult(
                SaveState.UNKNOWN,
                "Der gefundene Remote-Datensatz ist nicht prüfbar.",
                external_id=external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        remote_id = raw.get("id")
        if remote_id is None or str(remote_id).strip() == "":
            return WriteResult(
                SaveState.UNKNOWN,
                "Der gefundene Datensatz trägt keine Remote-ID.",
                external_id=external_id,
                error=SaveErrorKind.RECONCILIATION,
                reconciliation_required=True,
            )
        return self._confirm(
            snapshot,
            raw,
            str(remote_id),
            expected_external_id=external_id,
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
        if not callable(getattr(client, "upsert_events", None)):
            raise TypeError("client muss upsert_events() anbieten.")
        self._client = client

    def read_event(self, remote_id: str) -> Mapping[str, Any]:
        return self._client.event(int(remote_id))

    def update_event(
        self, remote_id: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return self._client.update_event(int(remote_id), dict(payload))

    def create_event(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        rows = self._client.upsert_events([dict(payload)])
        if not isinstance(rows, list) or len(rows) != 1:
            raise GatewayError(
                "Der Upsert-Pfad hat nicht genau eine Einheit zurückgegeben."
            )
        row = rows[0]
        if not isinstance(row, Mapping):
            raise GatewayError("Der Upsert-Pfad lieferte kein Event-Objekt.")
        return row

    def find_by_external_id(
        self, external_id: str, day: str
    ) -> list[Mapping[str, Any]]:
        """Sucht lesend im belegten Kalenderbereich um den geplanten Tag."""
        if not callable(getattr(self._client, "events", None)):
            raise GatewayError("Der Client kann Events nicht lesen.")
        start = date.fromisoformat(day) - timedelta(days=7)
        end = date.fromisoformat(day) + timedelta(days=7)
        rows = self._client.events(start, end, category="WORKOUT")
        return [
            row
            for row in rows
            if isinstance(row, Mapping) and str(row.get("external_id")) == external_id
        ]


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
