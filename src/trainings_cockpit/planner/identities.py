"""Typisierte Identitäten für Planung, Aufzeichnung, Entwurf und Vorgang.

Eine numerische ID allein reicht nicht: Plan `123` und Aktivität `123` sind
verschiedene Objekte. Deshalb tragen alle Referenzen ihren Objekttyp und den
Account-/Athletenkontext. `NodeId` ist davon getrennt und bleibt über
Bearbeiten, Einklappen und Verschieben stabil.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from .primitives import require_text


class IdentityError(ValueError):
    """Eine Identität ist leer, falsch typisiert oder nicht eindeutig."""


class ObjectKind(StrEnum):
    PLAN = "plan"
    ACTIVITY = "activity"
    DRAFT = "draft"
    OPERATION = "operation"
    RELATIONSHIP = "relationship"
    NODE = "node"


class _TypedId:
    """Gemeinsame Basis: Gleichheit nur innerhalb derselben ID-Klasse."""

    __slots__ = ("value",)
    kind: ClassVar[ObjectKind]

    def __init__(self, value: str | int) -> None:
        text = str(value).strip()
        if not text:
            raise IdentityError(f"{type(self).__name__} darf nicht leer sein.")
        object.__setattr__(self, "value", text)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} ist unveränderlich.")

    def __copy__(self) -> _TypedId:
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> _TypedId:
        del memo
        return self

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.value == other.value  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self.value))

    def __lt__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.value < other.value  # type: ignore[attr-defined]

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value!r})"

    @classmethod
    def new(cls) -> _TypedId:
        return cls(f"{cls.kind.value}:{uuid.uuid4().hex}")

    def as_context(self, *, account_id: str, athlete_id: str) -> IdentityContext:
        return IdentityContext(
            object_kind=self.kind,
            value=self.value,
            account_id=account_id,
            athlete_id=athlete_id,
        )


class PlanId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.PLAN


class RemoteEventId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.PLAN


class ActivityId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.ACTIVITY


class DraftId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.DRAFT


class OperationId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.OPERATION


class RelationshipId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.RELATIONSHIP


class NodeId(_TypedId):
    __slots__ = ()
    kind = ObjectKind.NODE


@dataclass(frozen=True, slots=True)
class IdentityContext:
    """Typ, Account, Athlet und ID gemeinsam — der Cache-/Routingkontext."""

    object_kind: ObjectKind
    value: str
    account_id: str
    athlete_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.object_kind, ObjectKind):
            raise IdentityError("object_kind muss ein ObjectKind sein.")
        object.__setattr__(self, "value", require_text(self.value, "value"))
        object.__setattr__(self, "account_id", require_text(self.account_id, "account_id"))
        object.__setattr__(self, "athlete_id", require_text(self.athlete_id, "athlete_id"))

    @property
    def cache_key(self) -> str:
        return f"{self.object_kind.value}:{self.account_id}:{self.athlete_id}:{self.value}"


def stable_external_id(
    local_id: PlanId | str,
    *,
    account_id: str,
    athlete_id: str,
) -> str:
    """Stabile App-Identität für den belegten Upsert-Pfad.

    Sie gehört zur beabsichtigten Einheit und zum Account/Athleten, nicht zu
    einem einzelnen HTTP-Versuch. Ein Retry desselben Entwurfs erzeugt deshalb
    dieselbe externe ID; zwei bewusst getrennte Entwürfe behalten zwei IDs.
    """
    local = local_id if isinstance(local_id, PlanId) else PlanId(local_id)
    return (
        "tc:planner:"
        f"{require_text(account_id, 'account_id')}:"
        f"{require_text(athlete_id, 'athlete_id')}:{local.value}"
    )


@dataclass(frozen=True, slots=True)
class SourceActivityRef:
    """Ein Quellabbild derselben kanonischen Aktivität."""

    source: str
    source_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(self, "source_id", require_text(self.source_id, "source_id"))

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"


@dataclass(frozen=True, slots=True)
class PlanReference:
    plan_id: PlanId
    account_id: str
    athlete_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.plan_id, PlanId):
            object.__setattr__(self, "plan_id", PlanId(self.plan_id))
        object.__setattr__(self, "account_id", require_text(self.account_id, "account_id"))
        object.__setattr__(self, "athlete_id", require_text(self.athlete_id, "athlete_id"))

    @property
    def identity(self) -> IdentityContext:
        return self.plan_id.as_context(account_id=self.account_id, athlete_id=self.athlete_id)

    @property
    def key(self) -> str:
        return self.identity.cache_key


@dataclass(frozen=True, slots=True)
class ActivityReference:
    """Verweis auf die vorhandene **kanonische** Aktivität, nie auf einen Plan."""

    activity_id: ActivityId
    account_id: str
    athlete_id: str
    source_refs: tuple[SourceActivityRef, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.activity_id, ActivityId):
            object.__setattr__(self, "activity_id", ActivityId(self.activity_id))
        object.__setattr__(self, "account_id", require_text(self.account_id, "account_id"))
        object.__setattr__(self, "athlete_id", require_text(self.athlete_id, "athlete_id"))
        refs = tuple(self.source_refs)
        if any(not isinstance(ref, SourceActivityRef) for ref in refs):
            raise IdentityError("source_refs dürfen nur SourceActivityRef enthalten.")
        if len({ref.key for ref in refs}) != len(refs):
            raise IdentityError("source_refs enthalten ein doppeltes Quellabbild.")
        object.__setattr__(self, "source_refs", refs)

    @property
    def identity(self) -> IdentityContext:
        return self.activity_id.as_context(account_id=self.account_id, athlete_id=self.athlete_id)

    @property
    def key(self) -> str:
        return self.identity.cache_key
