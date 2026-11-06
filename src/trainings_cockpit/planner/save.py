"""Speicherkoordinator, Zustandsmodell und unveränderliche Schreibsnapshots.

Der Koordinator ist die eine Stelle, die einen geplanten Workoutentwurf in einen
Schreibvorgang überführt. Er verbindet Validierung, fachliche Dirty-Prüfung und
einen unveränderlichen Snapshot, bevor irgendein Adapter aufgerufen wird.

Die Zustände folgen Abschnitt 9.2 des Implementierungsplans. Ein Timeout wird
ausdrücklich nicht als "nichts gespeichert" behandelt: Er führt in ``unknown``
und bleibt bis zur Reconciliation gesperrt. Pro Einheit (Account, Athlet,
lokale Plan-ID) ist höchstens eine logische Operation aktiv; wiederholte
Aktivierungen liefern dieselbe Operation zurück, statt einen zweiten Write zu
starten.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

import httpx

from .identities import DraftId, OperationId, PlanId, RemoteEventId
from .model import PlannedWorkout, WorkoutDraft
from .primitives import require_text
from .serializer import NoWriteNeeded, PreparedWrite, SerializationError, prepare_write
from .write import WriteBoundaryError, require_planned_draft


class SaveState(StrEnum):
    """Die fachlichen Zustände aus Abschnitt 9.2, nicht ein Boolean."""

    CLEAN = "clean"
    DIRTY = "dirty"
    INVALID = "invalid"
    SAVING = "saving"
    SAVED = "saved"
    FAILED = "failed"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    SAVED_UNVERIFIED = "savedUnverified"


class SaveErrorKind(StrEnum):
    """Stabile Fehlerklassen für UI, Protokoll und Wiederholungsentscheidung."""

    BOUNDARY = "boundary"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    CONFLICT = "conflict"
    REMOTE_VALIDATION = "remote_validation"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    NETWORK = "network"
    TIMEOUT = "timeout"
    IDENTITY = "identity"
    ROUNDTRIP = "roundtrip"
    RECONCILIATION = "reconciliation"


#: Zustände, in denen keine fachliche Eingabe am Entwurf erlaubt ist. Ein
#: laufender Write könnte sonst von einer späteren Antwort überschrieben werden;
#: ein unklarer Ausgang darf nicht durch erneutes Tippen zu einem zweiten Write
#: führen.
LOCKED_STATES = frozenset(
    {SaveState.SAVING, SaveState.UNKNOWN, SaveState.SAVED_UNVERIFIED}
)


class InputLocked(RuntimeError):
    """Während eines laufenden oder unklaren Writes sind Eingaben gesperrt."""

    def __init__(self, status: SaveStatus) -> None:
        super().__init__(status.message or "Der Speichervorgang läuft.")
        self.status = status


@dataclass(frozen=True, slots=True)
class SaveStatus:
    state: SaveState
    message: str = ""
    operation_id: OperationId | None = None
    remote_id: str | None = None
    external_id: str | None = None
    error: SaveErrorKind | None = None
    retryable: bool = False
    reconciliation_required: bool = False
    conflict: Any | None = None
    persistence_error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, SaveState):
            object.__setattr__(self, "state", SaveState(self.state))
        if self.error is not None and not isinstance(self.error, SaveErrorKind):
            object.__setattr__(self, "error", SaveErrorKind(self.error))
        if self.operation_id is not None and not isinstance(self.operation_id, OperationId):
            object.__setattr__(self, "operation_id", OperationId(self.operation_id))
        for name in ("remote_id", "external_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, require_text(value, name))
        if self.persistence_error is not None:
            object.__setattr__(
                self,
                "persistence_error",
                require_text(self.persistence_error, "persistence_error"),
            )

    @property
    def locked(self) -> bool:
        return self.state in LOCKED_STATES

    def as_dict(self) -> dict[str, Any]:
        conflict = getattr(self.conflict, "as_dict", None)
        return {
            "state": self.state.value,
            "message": self.message,
            "operation_id": str(self.operation_id) if self.operation_id else None,
            "remote_id": self.remote_id,
            "external_id": self.external_id,
            "error": self.error.value if self.error else None,
            "retryable": self.retryable,
            "reconciliation_required": self.reconciliation_required,
            "locked": self.locked,
            "conflict": conflict() if callable(conflict) else None,
            "persistence_error": self.persistence_error,
        }


@dataclass(frozen=True, slots=True)
class SaveSnapshot:
    """Ein unveränderlicher Schreibauftrag samt lokaler Zuordnung.

    ``payload_json`` friert den Payload ein. Der Adapter erhält über
    :attr:`payload` jedes Mal eine frische Kopie; nachträgliche Änderungen am
    Entwurf können den laufenden Auftrag nicht mehr verändern.
    """

    operation_id: OperationId
    draft_id: DraftId
    local_id: PlanId
    remote_id: RemoteEventId | None
    account_id: str
    athlete_id: str
    mode: str
    kind: str
    payload_json: str
    workout_text: str | None
    external_id: str | None
    base_hash: str | None
    local_revision: int
    writable: bool
    writable_reason: str | None
    intended: PlannedWorkout
    base: PlannedWorkout | None
    base_notes: str | None
    created_at: str
    editor_shape: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, OperationId):
            object.__setattr__(self, "operation_id", OperationId(self.operation_id))
        if not isinstance(self.draft_id, DraftId):
            object.__setattr__(self, "draft_id", DraftId(self.draft_id))
        if not isinstance(self.local_id, PlanId):
            object.__setattr__(self, "local_id", PlanId(self.local_id))
        if self.remote_id is not None and not isinstance(self.remote_id, RemoteEventId):
            object.__setattr__(self, "remote_id", RemoteEventId(self.remote_id))
        if not isinstance(self.intended, PlannedWorkout):
            raise TypeError("intended muss ein PlannedWorkout sein.")
        if self.base is not None and not isinstance(self.base, PlannedWorkout):
            raise TypeError("base muss ein PlannedWorkout oder None sein.")
        if self.base_notes is not None:
            object.__setattr__(self, "base_notes", require_text(self.base_notes, "base_notes"))
        if self.editor_shape is not None and not isinstance(self.editor_shape, Mapping):
            raise TypeError("editor_shape muss ein Mapping oder None sein.")
        if self.editor_shape is not None:
            object.__setattr__(self, "editor_shape", dict(self.editor_shape))
        for name in ("account_id", "athlete_id"):
            object.__setattr__(self, name, require_text(getattr(self, name), name))
        if not isinstance(self.writable, bool):
            raise TypeError("writable muss ein Boolean sein.")
        if self.writable_reason is not None:
            object.__setattr__(
                self, "writable_reason", require_text(self.writable_reason, "writable_reason")
            )
        json.loads(self.payload_json)

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):  # pragma: no cover - durch __post_init__ ausgeschlossen
            raise TypeError("Der gespeicherte Payload ist kein Objekt.")
        return value

    @property
    def fingerprint(self) -> str:
        """Fachlicher Inhalt, nicht Renderzustand oder Abrufzeitpunkt."""
        material = "\n".join(
            (
                str(self.local_id),
                self.account_id,
                self.athlete_id,
                self.mode,
                self.payload_json,
            )
        )
        return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": str(self.operation_id),
            "draft_id": str(self.draft_id),
            "local_id": str(self.local_id),
            "remote_id": str(self.remote_id) if self.remote_id else None,
            "account_id": self.account_id,
            "athlete_id": self.athlete_id,
            "mode": self.mode,
            "kind": self.kind,
            "external_id": self.external_id,
            "local_revision": self.local_revision,
            "writable": self.writable,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Ergebnis eines Adapteraufrufs, noch ohne UI-Zustand."""

    state: SaveState
    message: str
    remote_id: str | None = None
    external_id: str | None = None
    error: SaveErrorKind | None = None
    retryable: bool = False
    reconciliation_required: bool = False
    confirmed: Any | None = None
    conflict: Any | None = None
    remote_raw: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, SaveState):
            object.__setattr__(self, "state", SaveState(self.state))
        if self.error is not None and not isinstance(self.error, SaveErrorKind):
            object.__setattr__(self, "error", SaveErrorKind(self.error))
        if self.remote_raw is not None and not isinstance(self.remote_raw, Mapping):
            raise TypeError("remote_raw muss ein Mapping oder None sein.")


@dataclass(frozen=True, slots=True)
class SaveOutcome:
    status: SaveStatus
    snapshot: SaveSnapshot | None = None
    confirmed: Any | None = None


@dataclass(frozen=True, slots=True)
class SaveOperation:
    snapshot: SaveSnapshot
    key: str
    started_at: str


class SaveRunner(Protocol):
    """Die Adapterbrücke; implementiert in ``event_write`` und in Tests."""

    def execute(self, snapshot: SaveSnapshot) -> WriteResult: ...

    def reconcile(self, snapshot: SaveSnapshot) -> WriteResult: ...


class OperationRecorder(Protocol):
    """Dauerhafte Vorgangszuordnung; implementiert in ``operations``."""

    def save(self, snapshot: SaveSnapshot, state: SaveState) -> None: ...

    def update(
        self,
        snapshot: SaveSnapshot,
        state: SaveState,
        *,
        confirmed: bool = False,
        remote_id: str | None = None,
        external_id: str | None = None,
    ) -> None: ...

    def open_operations(
        self, *, account_id: str, athlete_id: str
    ) -> list[Any]: ...


def plan_key(*, account_id: str, athlete_id: str, local_id: PlanId | str) -> str:
    """Ein Schlüssel pro Account, Athlet und geplanter Einheit."""
    return (
        f"plan:{require_text(account_id, 'account_id')}:"
        f"{require_text(athlete_id, 'athlete_id')}:{require_text(str(local_id), 'local_id')}"
    )


def classify_exception(exc: BaseException) -> WriteResult:
    """Ordnet Adapterfehler einer stabilen Klasse und einem Zustand zu.

    Entscheidend ist die Unterscheidung zwischen "sicher nicht geschrieben"
    und "könnte geschrieben worden sein". Nur die erste Gruppe darf einen
    erneuten Write anbieten. HTTP 5xx und Timeouts bleiben unklar, weil ein
    Commit vor der Fehlerantwort stattgefunden haben kann.
    """
    status = getattr(exc, "status_code", None)
    message = str(exc) or type(exc).__name__
    conflict = getattr(exc, "conflict", None)
    if isinstance(exc, (TimeoutError, ConnectionError, httpx.TimeoutException)):
        return WriteResult(
            SaveState.UNKNOWN,
            "Der Speicherstatus ist unklar: Die Antwort ging verloren. "
            "Der Entwurf bleibt erhalten und wird abgeglichen, nicht blind wiederholt.",
            error=SaveErrorKind.TIMEOUT,
            retryable=False,
            reconciliation_required=True,
        )
    if status == 401 or status == 403:
        return WriteResult(
            SaveState.FAILED,
            "Keine Schreibberechtigung für diese Einheit. Es wurde nichts geändert.",
            error=SaveErrorKind.PERMISSION,
        )
    if status == 404:
        return WriteResult(
            SaveState.FAILED,
            "Die Einheit existiert remote nicht mehr. Es wird nichts neu angelegt.",
            error=SaveErrorKind.NOT_FOUND,
            conflict=conflict,
        )
    if status in (409, 412):
        return WriteResult(
            SaveState.CONFLICT,
            "Die Remote-Einheit wurde zwischenzeitlich geändert. "
            "Der lokale Entwurf bleibt erhalten.",
            error=SaveErrorKind.CONFLICT,
            conflict=conflict,
        )
    if status in (400, 422):
        return WriteResult(
            SaveState.FAILED,
            f"Die Remote-Quelle hat den Payload abgelehnt: {message[:240]}",
            error=SaveErrorKind.REMOTE_VALIDATION,
        )
    if status == 429:
        return WriteResult(
            SaveState.FAILED,
            "Die Remote-Quelle begrenzt gerade die Anfragen. Bitte später erneut versuchen.",
            error=SaveErrorKind.RATE_LIMIT,
            retryable=True,
        )
    if isinstance(status, int) and status >= 500:
        return WriteResult(
            SaveState.UNKNOWN,
            "Die Remote-Quelle meldet einen Serverfehler. Ob der Write angekommen ist, "
            "ist unklar; der Vorgang wird abgeglichen.",
            error=SaveErrorKind.SERVER,
            retryable=False,
            reconciliation_required=True,
        )
    if isinstance(exc, (ValueError, TypeError)):
        return WriteResult(
            SaveState.INVALID,
            f"Der Entwurf ist nicht speicherbar: {message[:240]}",
            error=SaveErrorKind.VALIDATION,
        )
    return WriteResult(
        SaveState.UNKNOWN,
        "Der Speicherstatus ist unklar. Der Entwurf bleibt erhalten.",
        error=SaveErrorKind.NETWORK,
        retryable=False,
        reconciliation_required=True,
    )


class SaveCoordinator:
    """Genau eine aktive Operation pro geplanter Einheit."""

    def __init__(
        self,
        runner: SaveRunner,
        *,
        recorder: OperationRecorder | None = None,
    ) -> None:
        if not callable(getattr(runner, "execute", None)):
            raise TypeError("runner muss ein SaveRunner mit execute() sein.")
        self._runner = runner
        self._recorder = recorder
        self._lock = threading.RLock()
        self._active: dict[str, SaveOperation] = {}
        self._status: dict[str, SaveStatus] = {}
        self._last_saved: dict[str, tuple[str, SaveStatus]] = {}
        self._reconciling: set[str] = set()

    # ------------------------------------------------------------ Zustand
    def status_for(
        self,
        candidate: object,
        *,
        account_id: str,
        athlete_id: str,
    ) -> SaveStatus | None:
        draft = self._draft(candidate)
        key = plan_key(
            account_id=account_id,
            athlete_id=athlete_id,
            local_id=draft.current.local_id,
        )
        with self._lock:
            return self._status.get(key)

    def active_operation(self, operation_id: OperationId | str) -> SaveOperation | None:
        wanted = str(operation_id)
        with self._lock:
            for operation in self._active.values():
                if str(operation.snapshot.operation_id) == wanted:
                    return operation
        return None

    def ensure_editable(
        self,
        candidate: object,
        *,
        account_id: str,
        athlete_id: str,
    ) -> None:
        """Sperrt fachliche Eingaben während eines laufenden/unklaren Writes."""
        status = self.status_for(
            candidate, account_id=account_id, athlete_id=athlete_id
        )
        if status is not None and status.locked:
            raise InputLocked(status)

    # ------------------------------------------------------------ Prüfung
    def preview(
        self,
        candidate: object,
        *,
        account_id: str,
        athlete_id: str,
        writable: bool = True,
        writable_reason: str | None = None,
    ) -> SaveOutcome:
        """Dirty-/Validierungszustand, ohne einen Write zu starten."""
        status, snapshot = self._prepare(
            candidate,
            account_id=account_id,
            athlete_id=athlete_id,
            writable=writable,
            writable_reason=writable_reason,
        )
        return SaveOutcome(status, snapshot)

    def _draft(self, candidate: object) -> WorkoutDraft:
        return require_planned_draft(candidate)

    def _prepare(
        self,
        candidate: object,
        *,
        account_id: str,
        athlete_id: str,
        writable: bool,
        writable_reason: str | None,
    ) -> tuple[SaveStatus, SaveSnapshot | None]:
        account = require_text(account_id, "account_id")
        athlete = require_text(athlete_id, "athlete_id")
        try:
            draft = require_planned_draft(candidate)
        except WriteBoundaryError as exc:
            return (
                SaveStatus(
                    SaveState.INVALID,
                    str(exc),
                    error=SaveErrorKind.BOUNDARY,
                ),
                None,
            )

        try:
            prepared = prepare_write(
                draft, account_id=account, athlete_id=athlete
            )
        except NoWriteNeeded:
            return (
                SaveStatus(
                    SaveState.CLEAN,
                    "Keine Änderungen",
                    external_id=draft.current.external_id,
                ),
                None,
            )
        except SerializationError as exc:
            return (
                SaveStatus(
                    SaveState.INVALID,
                    str(exc),
                    error=SaveErrorKind.VALIDATION,
                ),
                None,
            )
        except (TypeError, ValueError) as exc:
            return (
                SaveStatus(
                    SaveState.INVALID,
                    f"Der Entwurf ist nicht speicherbar: {exc}",
                    error=SaveErrorKind.VALIDATION,
                ),
                None,
            )

        snapshot = self._snapshot(
            draft,
            prepared,
            account_id=account,
            athlete_id=athlete,
            writable=writable,
            writable_reason=writable_reason,
        )
        return (
            SaveStatus(
                SaveState.DIRTY,
                "Ungespeicherte Änderungen",
                operation_id=snapshot.operation_id,
                remote_id=snapshot.remote_id.value if snapshot.remote_id else None,
                external_id=snapshot.external_id,
            ),
            snapshot,
        )

    def _snapshot(
        self,
        draft: WorkoutDraft,
        prepared: PreparedWrite,
        *,
        account_id: str,
        athlete_id: str,
        writable: bool,
        writable_reason: str | None,
    ) -> SaveSnapshot:
        if not isinstance(writable, bool):
            raise TypeError("writable muss ein Boolean sein.")
        source = draft.base_source
        base_notes: str | None = None
        if source is not None and isinstance(source.raw, Mapping):
            raw_doc = source.raw.get("workout_doc")
            doc_notes = raw_doc.get("notes") if isinstance(raw_doc, Mapping) else None
            if isinstance(doc_notes, str) and doc_notes.strip():
                base_notes = doc_notes
            elif isinstance(source.raw.get("notes"), str) and source.raw["notes"].strip():
                base_notes = source.raw["notes"]
        elif draft.base is not None:
            base_notes = draft.base.notes
        return SaveSnapshot(
            operation_id=draft.operation_id,
            draft_id=draft.draft_id,
            local_id=draft.current.local_id,
            remote_id=draft.current.remote_id,
            account_id=account_id,
            athlete_id=athlete_id,
            mode=prepared.mode,
            kind=prepared.kind,
            payload_json=json.dumps(
                prepared.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ),
            workout_text=prepared.workout_text,
            external_id=prepared.external_id,
            base_hash=source.relevant_content_hash if source is not None else None,
            local_revision=draft.local_revision,
            writable=writable,
            writable_reason=writable_reason,
            intended=draft.current,
            base=draft.base,
            base_notes=base_notes,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    # ------------------------------------------------------------ Aktivierung
    def activate(
        self,
        candidate: object,
        *,
        account_id: str,
        athlete_id: str,
        writable: bool = True,
        writable_reason: str | None = None,
    ) -> SaveOutcome:
        """Startet höchstens eine logische Operation pro Einheit.

        Zehn gleichzeitige oder unmittelbar aufeinanderfolgende Aktivierungen
        mit demselben Inhalt teilen sich diese Operation. Nach einem
        bestätigten Write liefert derselbe Snapshot den gespeicherten Zustand
        zurück, ohne einen zweiten Adapteraufruf auszulösen.
        """
        account = require_text(account_id, "account_id")
        athlete = require_text(athlete_id, "athlete_id")
        status, snapshot = self._prepare(
            candidate,
            account_id=account,
            athlete_id=athlete,
            writable=writable,
            writable_reason=writable_reason,
        )
        if snapshot is None or status.state is not SaveState.DIRTY:
            return SaveOutcome(status, snapshot)

        key = plan_key(account_id=account, athlete_id=athlete, local_id=snapshot.local_id)
        persistence_error = self._record(snapshot, SaveState.SAVING)
        if persistence_error is not None:
            return SaveOutcome(
                SaveStatus(
                    SaveState.FAILED,
                    "Der Vorgang konnte vor dem Senden nicht gesichert werden. "
                    "Es wurde nichts an die Remote-Quelle gesendet.",
                    operation_id=snapshot.operation_id,
                    remote_id=snapshot.remote_id.value if snapshot.remote_id else None,
                    external_id=snapshot.external_id,
                    error=SaveErrorKind.RECONCILIATION,
                    persistence_error=persistence_error,
                ),
                snapshot,
            )
        with self._lock:
            active = self._active.get(key)
            if active is not None:
                return SaveOutcome(self._status[key], active.snapshot, None)
            cached = self._last_saved.get(key)
            if cached is not None and cached[0] == snapshot.fingerprint:
                return SaveOutcome(cached[1], snapshot, None)
            saving = SaveStatus(
                SaveState.SAVING,
                "Wird gespeichert …",
                operation_id=snapshot.operation_id,
                remote_id=snapshot.remote_id.value if snapshot.remote_id else None,
                external_id=snapshot.external_id,
            )
            self._status[key] = saving
            operation = SaveOperation(
                snapshot=snapshot,
                key=key,
                started_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            )
            self._active[key] = operation

        try:
            result = self._runner.execute(snapshot)
            if not isinstance(result, WriteResult):
                raise TypeError("Der SaveRunner muss ein WriteResult liefern.")
        except BaseException as exc:  # noqa: BLE001 - jede Adapterstörung wird klassifiziert
            result = classify_exception(exc)

        return self._finish(operation, result)

    def _record(
        self,
        snapshot: SaveSnapshot,
        state: SaveState,
        *,
        confirmed: bool = False,
        remote_id: str | None = None,
        external_id: str | None = None,
    ) -> str | None:
        """Schreibt den Vorgang; ein Persistenzfehler ersetzt kein Remote-Ergebnis."""
        if self._recorder is None:
            return None
        try:
            if state is SaveState.SAVING:
                self._recorder.save(snapshot, state)
            else:
                self._recorder.update(
                    snapshot,
                    state,
                    confirmed=confirmed,
                    remote_id=remote_id,
                    external_id=external_id,
                )
        except Exception as exc:  # noqa: BLE001 - Persistenz darf den Write nicht wiederholen
            return f"Der lokale Vorgangsnachweis konnte nicht gespeichert werden: {exc}"
        return None

    def _finish(self, operation: SaveOperation, result: WriteResult) -> SaveOutcome:
        snapshot = operation.snapshot
        persistence_error = self._record(
            snapshot,
            result.state,
            confirmed=result.state is SaveState.SAVED,
            remote_id=result.remote_id or (
                str(snapshot.remote_id) if snapshot.remote_id is not None else None
            ),
            external_id=result.external_id or snapshot.external_id,
        )
        message = result.message
        if persistence_error is not None:
            message = f"{message} {persistence_error}"
        status = SaveStatus(
            result.state,
            message,
            operation_id=snapshot.operation_id,
            remote_id=result.remote_id,
            external_id=result.external_id or snapshot.external_id,
            error=result.error,
            retryable=result.retryable,
            reconciliation_required=result.reconciliation_required,
            conflict=result.conflict,
            persistence_error=persistence_error,
        )
        with self._lock:
            self._status[operation.key] = status
            if result.state in (SaveState.FAILED, SaveState.CONFLICT):
                self._active.pop(operation.key, None)
            elif result.state is SaveState.SAVED:
                self._active.pop(operation.key, None)
                self._last_saved[operation.key] = (snapshot.fingerprint, status)
            elif result.state is SaveState.SAVED_UNVERIFIED:
                # Kein zweiter Create: Der Vorgang bleibt bis zur Prüfung offen.
                self._last_saved[operation.key] = (snapshot.fingerprint, status)
            else:
                # SAVING/UNKNOWN bleiben aktiv und damit gesperrt.
                pass
        return SaveOutcome(status, snapshot, result.confirmed)

    # ------------------------------------------------------------ Wiederaufnahme
    def restore_open(self, *, account_id: str, athlete_id: str) -> list[SaveOutcome]:
        """Findet offene Vorgänge nach Reload/Neustart wieder.

        Ein beim Absturz zurückgelassener ``saving``-Zustand beweist keinen
        Fehlschlag; er wird zu ``unknown`` und bleibt bis zum lesenden Abgleich
        gesperrt. ``savedUnverified`` behält seine Remote-ID.
        """
        if self._recorder is None:
            return []
        outcomes: list[SaveOutcome] = []
        for stored in self._recorder.open_operations(
            account_id=account_id, athlete_id=athlete_id
        ):
            snapshot = stored.snapshot
            key = plan_key(
                account_id=snapshot.account_id,
                athlete_id=snapshot.athlete_id,
                local_id=snapshot.local_id,
            )
            state = SaveState(stored.state)
            if state is SaveState.SAVING:
                state = SaveState.UNKNOWN
                message = (
                    "Der Vorgang wurde beim letzten Lauf unterbrochen. "
                    "Der Speicherstatus wird lesend geprüft; es wird nichts blind wiederholt."
                )
                error = SaveErrorKind.TIMEOUT
            elif state is SaveState.SAVED_UNVERIFIED:
                message = (
                    "Der Write wurde bestätigt, die Darstellung ist aber noch nicht "
                    "nachgeprüft. Die Remote-ID bleibt erhalten; es wird nicht erneut angelegt."
                )
                error = SaveErrorKind.ROUNDTRIP
            else:
                message = "Der Speicherstatus ist unklar. Der Vorgang wird lesend abgeglichen."
                error = SaveErrorKind.RECONCILIATION
            status = SaveStatus(
                state,
                message,
                operation_id=snapshot.operation_id,
                remote_id=str(snapshot.remote_id) if snapshot.remote_id is not None else None,
                external_id=snapshot.external_id,
                error=error,
                reconciliation_required=True,
                persistence_error=None,
            )
            with self._lock:
                self._active[key] = SaveOperation(
                    snapshot=snapshot,
                    key=key,
                    started_at=snapshot.created_at,
                )
                self._status[key] = status
            outcomes.append(SaveOutcome(status, snapshot))
        return outcomes

    # ------------------------------------------------------------ Reconciliation
    def reconcile(self, operation_id: OperationId | str) -> SaveOutcome:
        """Prüft einen unklaren Vorgang lesend; wiederholt keinen Write."""
        wanted = str(operation_id)
        with self._lock:
            operation = next(
                (
                    item
                    for item in self._active.values()
                    if str(item.snapshot.operation_id) == wanted
                ),
                None,
            )
            if operation is None:
                for status in self._status.values():
                    if status.operation_id is not None and str(status.operation_id) == wanted:
                        return SaveOutcome(status, None, None)
                raise KeyError(f"Vorgang {wanted!r} ist nicht offen.")
            if operation.key in self._reconciling:
                return SaveOutcome(self._status[operation.key], operation.snapshot, None)
            self._reconciling.add(operation.key)

        try:
            reconcile = getattr(self._runner, "reconcile", None)
            if not callable(reconcile):
                result = WriteResult(
                    SaveState.UNKNOWN,
                    "Der Adapter kann diesen Vorgang nicht lesend abgleichen.",
                    external_id=operation.snapshot.external_id,
                    error=SaveErrorKind.RECONCILIATION,
                    reconciliation_required=True,
                )
            else:
                result = reconcile(operation.snapshot)
                if not isinstance(result, WriteResult):
                    raise TypeError("reconcile muss ein WriteResult liefern.")
        except BaseException as exc:  # noqa: BLE001
            result = classify_exception(exc)
        finally:
            with self._lock:
                self._reconciling.discard(operation.key)

        if result.state in (SaveState.SAVED, SaveState.FAILED, SaveState.CONFLICT):
            with self._lock:
                self._active.pop(operation.key, None)
        return self._finish(operation, result)


__all__ = [
    "InputLocked",
    "OperationRecorder",
    "LOCKED_STATES",
    "SaveCoordinator",
    "SaveErrorKind",
    "SaveOperation",
    "SaveOutcome",
    "SaveRunner",
    "SaveSnapshot",
    "SaveState",
    "SaveStatus",
    "WriteResult",
    "classify_exception",
    "plan_key",
]
