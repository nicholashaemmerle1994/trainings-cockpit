"""Schreibgrenze: nur ein geplanter Workoutentwurf erreicht den Event-Adapter.

Die Typprüfung allein genügt nicht, weil Daten aus JSON, Dicts oder einem
generischen Handler zur Laufzeit jede Form annehmen können. Deshalb prüft
:func:`require_planned_draft` an der tatsächlichen Eingangsgrenze noch einmal
Typ und Inhalt. Eine Aktivitätsreferenz ist kein Plan und wird abgewiesen.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .model import Editability, PlannedWorkout, WorkoutDraft
from .validation import validate_draft


class WriteBoundaryError(TypeError):
    """Der Schreibkoordinator hat etwas anderes als einen Planentwurf erhalten."""


@runtime_checkable
class PlannedWorkoutWriter(Protocol):
    def write(self, draft: WorkoutDraft) -> Any: ...


def require_planned_draft(candidate: object) -> WorkoutDraft:
    """Akzeptiert ausschließlich einen intakten geplanten Entwurf."""
    if type(candidate) is not WorkoutDraft:
        raise WriteBoundaryError(
            "Der Schreibkoordinator akzeptiert nur einen WorkoutDraft; "
            f"erhalten: {type(candidate).__name__}."
        )
    draft = candidate
    if type(draft.current) is not PlannedWorkout:
        raise WriteBoundaryError("current muss ein geplantes Workout sein.")
    if draft.base is not None and type(draft.base) is not PlannedWorkout:
        raise WriteBoundaryError("base muss ein geplantes Workout oder None sein.")
    if draft.current.editability is Editability.READ_ONLY:
        raise WriteBoundaryError(
            "Dieser geplante Entwurf ist schreibgeschützt; "
            f"Grund: {draft.current.editability_reason or 'nicht angegeben'}."
        )
    if draft.current.remote_id is None and draft.base is not None:
        raise WriteBoundaryError("Eine Remote-Basis ohne Remote-ID ist kein gültiger Schreibfall.")
    validation = validate_draft(draft)
    if not validation.valid:
        details = "; ".join(issue.message for issue in validation.issues)
        raise WriteBoundaryError(f"Der Entwurf ist nicht speicherbar: {details}")
    return draft


class WriteCoordinator:
    """Die eine Runtime-Grenze vor dem vorhandenen Event-Adapter.

    Der übergebene Writer ist die spätere, geprüfte Adapterbrücke. Der
    Koordinator selbst führt keinen Netzwerkaufruf aus und erfindet keine
    Schreibfähigkeit.
    """

    def __init__(self, writer: PlannedWorkoutWriter) -> None:
        if not isinstance(writer, PlannedWorkoutWriter):
            raise TypeError("writer muss ein PlannedWorkoutWriter sein.")
        self._writer = writer

    def submit(self, candidate: object) -> Any:
        draft = require_planned_draft(candidate)
        return self._writer.write(draft)

    def prepare(self, candidate: object) -> WorkoutDraft:
        """Prüft die Grenze ohne zu schreiben (für spätere Vorschauen/Tests)."""
        return require_planned_draft(candidate)


# Sprechender Alias für Aufrufer, die den Vertrag ausdrücklich nennen wollen.
accepts_planned_draft = require_planned_draft
