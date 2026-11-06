"""Konflikte zwischen lokalem Basiszustand und aktuellem Remotezustand.

Der Vergleich arbeitet auf einer fachlichen Projektion, nicht auf dem kompletten
Event-JSON. Abgeleitete Remote-Felder, Abrufzeitpunkte und reine Darstellungs-
Metadaten dürfen keinen Konflikt erzeugen. Alles, was der Editor tatsächlich
beeinflusst (Name, Termin, Uhrzeit, Sport, Notizen und Aufbau), wird dagegen
ausdrücklich verglichen.

Die vorhandene intervals.icu-Strecke bietet in diesem Repository keinen
belegten ``If-Match``-/Versions-Schreibvertrag. Der Aufrufer liest deshalb
vor dem Write und vergleicht; die verbleibende Lücke zwischen diesem GET und
dem PUT ist in ``docs/trainingsplaner/KONFLIKTE.md`` dokumentiert. Es wird hier
keine atomare Garantie behauptet, die der Adapter nicht liefert.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .model import PlannedWorkout
from .remote import plan_shape


class ConflictKind(StrEnum):
    """Getrennte Konfliktursachen für Anzeige und Tests."""

    DELETED = "deleted"
    PERMISSION = "permission"
    STRUCTURE = "structure"
    METADATA = "metadata"
    IDENTITY = "identity"


#: Die minimalen Nutzeraktionen aus Abschnitt 9.8. „Eigene Fassung trotzdem
#: übernehmen“ ist bewusst nicht enthalten: Der vorhandene Adapter hat keine
#: belegte atomare Vorbedingung, also wäre das ein unkontrolliertes
#: Last-Write-Wins. Der Entwurf bleibt stattdessen als eigener Datenstand
#: erhalten.
CONFLICT_ACTIONS: tuple[str, ...] = (
    "view_remote",
    "return_to_draft",
    "discard_local_use_remote",
)

#: Felder, die den Aufbau und damit die ausführbare Struktur betreffen.
STRUCTURE_FIELDS = ("nodes",)
#: Felder, die ohne Strukturbaumänderung bearbeitbar sind.
METADATA_FIELDS = ("name", "sport", "date", "local_time", "notes", "external_id")


@dataclass(frozen=True, slots=True)
class RemoteVersion:
    """Die neuere Remote-Fassung als eigener, vom Entwurf getrennter Stand."""

    remote_id: str
    plan: PlannedWorkout | None
    writable: bool
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "remote_id", str(self.remote_id))
        if self.plan is not None and not isinstance(self.plan, PlannedWorkout):
            raise TypeError("plan muss ein PlannedWorkout oder None sein.")

    def as_dict(self) -> dict[str, Any]:
        plan = self.plan
        return {
            "remote_id": self.remote_id,
            "exists": plan is not None,
            "writable": self.writable,
            "reason": self.reason,
            "plan": None if plan is None else _plan_summary(plan),
        }


@dataclass(frozen=True, slots=True)
class ConflictAssessment:
    """Was sich geändert hat, ohne lokalen Entwurf und Remote zu vermischen."""

    kind: ConflictKind
    reason: str
    baseline: PlannedWorkout | None
    remote: PlannedWorkout | None
    changed_fields: tuple[str, ...] = ()
    actions: tuple[str, ...] = CONFLICT_ACTIONS

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConflictKind):
            object.__setattr__(self, "kind", ConflictKind(self.kind))
        object.__setattr__(self, "changed_fields", tuple(self.changed_fields))
        object.__setattr__(self, "actions", tuple(self.actions))
        if self.baseline is not None and not isinstance(self.baseline, PlannedWorkout):
            raise TypeError("baseline muss ein PlannedWorkout oder None sein.")
        if self.remote is not None and not isinstance(self.remote, PlannedWorkout):
            raise TypeError("remote muss ein PlannedWorkout oder None sein.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "reason": self.reason,
            "changed_fields": list(self.changed_fields),
            "actions": list(self.actions),
            "baseline": None if self.baseline is None else _plan_summary(self.baseline),
            "remote": None if self.remote is None else _plan_summary(self.remote),
        }


def _plan_summary(plan: PlannedWorkout) -> dict[str, Any]:
    """Fachliche Version ohne interne Knoten-IDs oder Roh-Volatilität."""
    shape = plan_shape(plan)
    return {
        "remote_id": str(plan.remote_id) if plan.remote_id is not None else None,
        "local_id": str(plan.local_id),
        "name": shape["name"],
        "sport": shape["sport"],
        "date": shape["date"],
        "local_time": shape["local_time"],
        "notes": shape["notes"],
        "editability": plan.editability.value,
        "nodes": _json_nodes(shape["nodes"]),
    }


def _json_nodes(nodes: object) -> list[Any]:
    """Die Shape ist bereits JSON-nah; Enums werden zu ihren Werten."""
    from enum import Enum

    def clean(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, tuple):
            return [clean(item) for item in value]
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            return {str(key): clean(item) for key, item in value.items()}
        return value

    return clean(nodes)  # type: ignore[return-value]


def changed_content_fields(
    baseline: PlannedWorkout,
    remote: PlannedWorkout,
) -> tuple[str, ...]:
    """Relevante Felder, die sich zwischen Basis und Remote unterscheiden."""
    before = plan_shape(baseline)
    after = plan_shape(remote)
    fields: list[str] = []
    for field in METADATA_FIELDS:
        if before.get(field) != after.get(field):
            fields.append(field)
    # Die Shape enthält die Struktur unter "nodes"; für die Anzeige ist der
    # sprechende Name "structure" hilfreicher als ein internes Feld.
    if before.get("nodes") != after.get("nodes"):
        fields.append("structure")
    return tuple(fields)


def assess_update_conflict(
    baseline: PlannedWorkout | None,
    remote: PlannedWorkout | None,
    *,
    remote_id: str,
    writable: bool = True,
    reason: str | None = None,
) -> ConflictAssessment | None:
    """Vergleicht eine Update-Basis mit dem aktuell gelesenen Remotezustand.

    ``None`` bedeutet: keine relevante Abweichung, der Write darf stattfinden.
    Eine externe Löschung und eine geänderte Schreibberechtigung werden vor
    einer Inhaltsänderung eingeordnet, damit die Oberfläche den konkreten
    Grund nennen kann.
    """
    if remote is None:
        return ConflictAssessment(
            ConflictKind.DELETED,
            "Die Einheit wurde extern gelöscht. Sie wird nicht automatisch neu angelegt.",
            baseline,
            None,
            actions=("return_to_draft", "discard_local"),
        )
    if not writable or not remote.is_metadata_editable:
        return ConflictAssessment(
            ConflictKind.PERMISSION,
            reason
            or remote.editability_reason
            or "Die Remote-Einheit ist inzwischen schreibgeschützt.",
            baseline,
            remote,
            changed_fields=("editability",),
            actions=("view_remote", "return_to_draft"),
        )
    if baseline is None:
        return None
    if (
        baseline.external_id is not None
        and remote.external_id is not None
        and baseline.external_id != remote.external_id
    ):
        return ConflictAssessment(
            ConflictKind.IDENTITY,
            "Die externe Identität der Remote-Einheit hat sich geändert.",
            baseline,
            remote,
            changed_fields=("external_id",),
            actions=("view_remote", "return_to_draft"),
        )
    fields = changed_content_fields(baseline, remote)
    if not fields:
        return None
    structural = "structure" in fields or "sport" in fields
    kind = ConflictKind.STRUCTURE if structural else ConflictKind.METADATA
    description = (
        "Der Remote-Aufbau wurde zwischenzeitlich geändert."
        if structural
        else "Name oder Termin wurden zwischenzeitlich remote geändert."
    )
    return ConflictAssessment(
        kind,
        description,
        baseline,
        remote,
        changed_fields=fields,
    )


__all__ = [
    "CONFLICT_ACTIONS",
    "ConflictAssessment",
    "ConflictKind",
    "METADATA_FIELDS",
    "RemoteVersion",
    "STRUCTURE_FIELDS",
    "assess_update_conflict",
    "changed_content_fields",
]
