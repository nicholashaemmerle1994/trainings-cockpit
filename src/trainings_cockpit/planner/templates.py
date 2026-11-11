"""Lokale Workout-Vorlagen als unabhängige Momentaufnahmen.

Eine Vorlage ist kein intervals-Event und keine zweite Vorlagenbibliothek bei
der Quelle. Sie liegt ausschließlich in der lokalen SQLite-Datenbank, trägt
Account-/Athleten-Scope und speichert den kanonischen, unterstützten Aufbau als
JSON. Jede Verwendung erzeugt über :mod:`planner.clone` neue Identitäten.

Die Tabelle hat bewusst keinen Fremdschlüssel auf ``event``: Das Löschen der
Quellplanung darf eine Vorlage nicht entfernen.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from .clone import CloneCode, CloneError, clone_for_new_plan
from .drafts import SUPPORTED_NEW_SPORTS
from .model import Editability, PlanId, PlannedWorkout, WorkoutDraft, WorkoutNode
from .operations import nodes_from_json, nodes_to_json
from .validation import calculate_known_totals

TEMPLATE_SCHEMA_VERSION = 1
TEMPLATE_NAME_MAX = 120


class TemplateCode(StrEnum):
    """Stabile Fehlercodes der Vorlagen-Grenze."""

    NAME_EMPTY = "name_empty"
    NAME_TOO_LONG = "name_too_long"
    NAME_INVALID = "name_invalid"
    INVALID_SCOPE = "invalid_scope"
    SPORT_UNSUPPORTED = "sport_unsupported"
    SOURCE_NOT_CLONEABLE = "source_not_cloneable"
    SCHEMA_UNSUPPORTED = "schema_unsupported"
    CORRUPT = "corrupt"
    NOT_FOUND = "not_found"


class TemplateError(ValueError):
    """Eine Vorlage ist ungültig, nicht lesbar oder nicht klonbar."""

    def __init__(
        self,
        code: TemplateCode,
        reason: str,
        *,
        clone_code: CloneCode | None = None,
    ) -> None:
        if not isinstance(code, TemplateCode):
            raise TypeError("code muss ein TemplateCode sein.")
        if clone_code is not None and not isinstance(clone_code, CloneCode):
            raise TypeError("clone_code muss ein CloneCode oder None sein.")
        text = str(reason or "").strip()
        if not text:
            text = "Die Vorlage konnte nicht verarbeitet werden."
        super().__init__(text)
        self.code = code
        self.reason = text
        self.clone_code = clone_code


class TemplateNotFound(TemplateError):
    """Eine Vorlage existiert nicht im aktuellen Account-/Athleten-Scope."""

    def __init__(self, reason: str = "Vorlage nicht gefunden.") -> None:
        super().__init__(TemplateCode.NOT_FOUND, reason)


@dataclass(frozen=True, slots=True)
class WorkoutTemplate:
    template_id: str
    account_id: str
    athlete_id: str
    name: str
    sport: str
    schema_version: int
    nodes: tuple[WorkoutNode, ...]
    created_at: str
    updated_at: str
    source_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class TemplateSummary:
    """Leichte Listenform; Knoten bleiben der Detailabfrage vorbehalten."""

    template_id: str
    name: str
    sport: str
    schema_version: int
    updated_at: str
    known_seconds: int | None
    known_metres: int | None
    executions: int | None
    has_unknown: bool
    available: bool = True
    error_code: str | None = None


_SCHEMA_VERSION = TEMPLATE_SCHEMA_VERSION
_SELECT_COLUMNS = (
    "template_id, account_id, athlete_id, name, sport, schema_version, "
    "nodes_json, created_at, updated_at, source_event_id"
)


def _timestamp(now: datetime | None) -> str:
    moment = now if now is not None else datetime.now().astimezone()
    if not isinstance(moment, datetime):
        raise TypeError("now muss ein datetime sein.")
    return moment.isoformat(timespec="seconds")


def _validate_name(name: object) -> str:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise TemplateError(TemplateCode.NAME_EMPTY, "Die Vorlage braucht einen Namen.")
    if len(cleaned) > TEMPLATE_NAME_MAX:
        raise TemplateError(
            TemplateCode.NAME_TOO_LONG,
            f"Der Vorlagenname darf höchstens {TEMPLATE_NAME_MAX} Zeichen haben.",
        )
    if any(marker in cleaned for marker in ("\n", "\r", "\t")):
        raise TemplateError(
            TemplateCode.NAME_INVALID,
            "Der Vorlagenname darf keine Zeilenumbrüche oder Tabulatoren enthalten.",
        )
    return cleaned


def _row_to_template(row: Mapping[str, Any]) -> WorkoutTemplate:
    try:
        schema_version = int(row["schema_version"])
    except (TypeError, ValueError) as exc:
        raise TemplateError(
            TemplateCode.CORRUPT,
            "Die Vorlage trägt keine gültige Schema-Version.",
        ) from exc
    if schema_version != _SCHEMA_VERSION:
        raise TemplateError(
            TemplateCode.SCHEMA_UNSUPPORTED,
            f"Vorlagen-Schema {schema_version} wird nicht unterstützt.",
        )
    raw_nodes = row["nodes_json"]
    try:
        parsed = json.loads(raw_nodes)
    except (TypeError, ValueError) as exc:
        raise TemplateError(
            TemplateCode.CORRUPT,
            "Der gespeicherte Vorlagenaufbau ist kein gültiges JSON.",
        ) from exc
    if not isinstance(parsed, list):
        raise TemplateError(
            TemplateCode.CORRUPT,
            "Der gespeicherte Vorlagenaufbau ist keine Knotenliste.",
        )
    try:
        nodes = nodes_from_json(parsed)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise TemplateError(
            TemplateCode.CORRUPT,
            "Der gespeicherte Vorlagenaufbau ist nicht lesbar.",
        ) from exc
    return WorkoutTemplate(
        template_id=str(row["template_id"]),
        account_id=str(row["account_id"]),
        athlete_id=str(row["athlete_id"]),
        name=str(row["name"]),
        sport=str(row["sport"]),
        schema_version=schema_version,
        nodes=nodes,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        source_event_id=(
            None if row["source_event_id"] is None else str(row["source_event_id"])
        ),
    )


def _summary(template: WorkoutTemplate) -> TemplateSummary:
    totals = calculate_known_totals(template.nodes)
    return TemplateSummary(
        template_id=template.template_id,
        name=template.name,
        sport=template.sport,
        schema_version=template.schema_version,
        updated_at=template.updated_at,
        known_seconds=(
            int(round(totals.duration_seconds))
            if totals.duration_seconds > 0
            else None
        ),
        known_metres=(
            int(round(totals.distance_metres))
            if totals.distance_metres > 0
            else None
        ),
        executions=totals.executions,
        has_unknown=totals.has_unknown,
        available=True,
    )


def _invalid_summary(row: Mapping[str, Any], error: TemplateError) -> TemplateSummary:
    try:
        schema_version = int(row["schema_version"])
    except (TypeError, ValueError):
        schema_version = 0
    return TemplateSummary(
        template_id=str(row["template_id"]),
        name=str(row["name"]),
        sport=str(row["sport"]),
        schema_version=schema_version,
        updated_at=str(row["updated_at"]),
        known_seconds=None,
        known_metres=None,
        executions=None,
        has_unknown=True,
        available=False,
        error_code=error.code.value,
    )


def save_from_plan(
    conn: Any,
    plan: PlannedWorkout,
    *,
    name: object,
    account_id: str,
    athlete_id: str,
    source_event_id: object | None = None,
    now: datetime | None = None,
) -> WorkoutTemplate:
    """Speichert einen bestätigten, unterstützten Aufbau rein lokal.

    Die Quelle wird nicht verändert. Nicht klonbare Strukturen werden mit
    einem stabilen Code abgelehnt; es entsteht in diesem Fall keine Zeile.
    """
    if not isinstance(plan, PlannedWorkout):
        raise TypeError("plan muss ein PlannedWorkout sein.")
    account = str(account_id or "").strip()
    athlete = str(athlete_id or "").strip()
    if not account or not athlete:
        raise TemplateError(
            TemplateCode.INVALID_SCOPE,
            "Eine Vorlage braucht Account und Athlet.",
        )
    cleaned_name = _validate_name(name)
    if plan.sport not in SUPPORTED_NEW_SPORTS:
        raise TemplateError(
            TemplateCode.SPORT_UNSUPPORTED,
            "Vorlagen werden nur für Laufen, Radfahren und Schwimmen angeboten.",
        )

    try:
        cloned, _draft = clone_for_new_plan(
            plan,
            target_date=plan.date,
            time_zone=plan.time_zone,
            account_id=account,
            athlete_id=athlete,
            keep_time=False,
        )
    except CloneError as exc:
        raise TemplateError(
            TemplateCode.SOURCE_NOT_CLONEABLE,
            exc.reason,
            clone_code=exc.code,
        ) from exc

    source = None
    if source_event_id is not None:
        source = str(source_event_id).strip() or None
    stamp = _timestamp(now)
    template_id = f"tpl:{uuid.uuid4().hex}"
    nodes_json = json.dumps(
        nodes_to_json(cloned.nodes),
        ensure_ascii=False,
        sort_keys=True,
    )
    conn.execute(
        """
        INSERT INTO workout_template (
            template_id, account_id, athlete_id, name, sport, schema_version,
            nodes_json, created_at, updated_at, source_event_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            template_id,
            account,
            athlete,
            cleaned_name,
            plan.sport,
            _SCHEMA_VERSION,
            nodes_json,
            stamp,
            stamp,
            source,
        ),
    )
    conn.commit()
    return WorkoutTemplate(
        template_id=template_id,
        account_id=account,
        athlete_id=athlete,
        name=cleaned_name,
        sport=plan.sport,
        schema_version=_SCHEMA_VERSION,
        nodes=cloned.nodes,
        created_at=stamp,
        updated_at=stamp,
        source_event_id=source,
    )


def list_templates(
    conn: Any,
    *,
    account_id: str,
    athlete_id: str,
) -> list[TemplateSummary]:
    """Leichte, scope-gebundene Liste; defekte Zeilen bleiben sichtbar."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM workout_template "  # noqa: S608 - feste Spalten
        "WHERE account_id = ? AND athlete_id = ? "
        "ORDER BY updated_at DESC, template_id",
        (account_id, athlete_id),
    ).fetchall()
    out: list[TemplateSummary] = []
    for row in rows:
        try:
            out.append(_summary(_row_to_template(row)))
        except TemplateError as exc:
            out.append(_invalid_summary(row, exc))
    return out


def get_template(
    conn: Any,
    template_id: str,
    *,
    account_id: str,
    athlete_id: str,
) -> WorkoutTemplate | None:
    """Eine Vorlage im aktuellen Scope; fremde IDs liefern ``None``."""
    row = conn.execute(
        f"SELECT {_SELECT_COLUMNS} FROM workout_template "  # noqa: S608 - feste Spalten
        "WHERE template_id = ? AND account_id = ? AND athlete_id = ?",
        (template_id, account_id, athlete_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_template(row)


def delete_template(
    conn: Any,
    template_id: str,
    *,
    account_id: str,
    athlete_id: str,
) -> bool:
    """Entfernt nur die lokale Vorlage; Pläne und Events bleiben bestehen."""
    cursor = conn.execute(
        "DELETE FROM workout_template "
        "WHERE template_id = ? AND account_id = ? AND athlete_id = ?",
        (template_id, account_id, athlete_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def instantiate(
    template: WorkoutTemplate,
    *,
    target_date: object,
    time_zone: object,
    draft_id: str | None = None,
    account_id: str,
    athlete_id: str,
) -> tuple[PlannedWorkout, WorkoutDraft]:
    """Bereitet einen neuen lokalen Entwurf aus der Vorlage vor.

    Kein DB- und kein Netzwerkzugriff. Der Aufrufer öffnet daraus den
    bestehenden Editor; gespeichert wird erst über den vorhandenen Save-Pfad.
    """
    if not isinstance(template, WorkoutTemplate):
        raise TypeError("template muss eine WorkoutTemplate sein.")
    source = PlannedWorkout(
        local_id=PlanId.new(),
        remote_id=None,
        external_id=None,
        name=template.name,
        sport=template.sport,
        date="2000-01-01",
        time_zone="UTC",
        nodes=template.nodes,
        notes=None,
        editability=Editability.FULL,
    )
    try:
        return clone_for_new_plan(
            source,
            target_date=target_date,
            time_zone=time_zone,
            account_id=account_id,
            athlete_id=athlete_id,
            keep_time=False,
            draft_id=draft_id,
        )
    except CloneError as exc:
        raise TemplateError(
            TemplateCode.SOURCE_NOT_CLONEABLE,
            exc.reason,
            clone_code=exc.code,
        ) from exc


__all__ = [
    "TEMPLATE_NAME_MAX",
    "TEMPLATE_SCHEMA_VERSION",
    "TemplateCode",
    "TemplateError",
    "TemplateNotFound",
    "TemplateSummary",
    "WorkoutTemplate",
    "delete_template",
    "get_template",
    "instantiate",
    "list_templates",
    "save_from_plan",
]
