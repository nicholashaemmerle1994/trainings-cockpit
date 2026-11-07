"""Bestätigte Planer-Writes in den vorhandenen Bestand einsortieren.

Der bestätigte Remote-Datensatz ist die Quelle. Er wird über seine tatsächliche
Event-ID in die vorhandene ``event``-Tabelle geschrieben; es entsteht keine
zweite Zeile und kein zweiter Write. Der nächste Sync liest dieselbe Event-ID
und aktualisiert dieselbe Zeile. Damit bleibt eine lokal gespeicherte Änderung
nach dem Sync genau einmal mit derselben Identität sichtbar.

Diese Schicht kennt keinen HTTP-Aufruf. Sie ist bewusst kein Schreibpfad und
kann deshalb auch durch einen Read → Normalisierung → Write keine
Feedbackschleife auslösen.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .. import db


def merge_confirmed_event(
    conn: Any,
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Schreibt genau einen bestätigten Remote-Datensatz in den lokalen Bestand.

    Die vorhandene Event-ID ist die Identität. Der Aufruf ist idempotent: ein
    zweiter Aufruf mit demselben Datensatz aktualisiert dieselbe Zeile.
    """
    if not isinstance(raw, Mapping):
        raise TypeError("Ein bestätigtes Event muss ein Mapping sein.")
    remote_id = raw.get("id")
    if remote_id is None or str(remote_id).strip() == "":
        raise ValueError("Ein bestätigtes Event braucht seine tatsächliche Remote-ID.")
    db.upsert_events(conn, [dict(raw)])
    row = db.event_by_id(conn, int(remote_id))
    if row is None:  # pragma: no cover - upsert mit gültiger ID legt die Zeile an
        raise RuntimeError("Der bestätigte Datensatz wurde nicht gespeichert.")
    return {
        "event_id": int(remote_id),
        "external_id": raw.get("external_id"),
        "date": str(raw.get("start_date_local") or row.get("date") or "")[:10],
    }


def event_identity(raw: Mapping[str, Any]) -> tuple[int, str | None]:
    """Liest die tatsächliche Event-ID und die externe Identität eines Events."""
    if not isinstance(raw, Mapping):
        raise TypeError("Ein Event muss ein Mapping sein.")
    remote_id = raw.get("id")
    if remote_id is None or str(remote_id).strip() == "":
        raise ValueError("Ein Event ohne tatsächliche Remote-ID ist nicht zuordenbar.")
    external = raw.get("external_id")
    return int(remote_id), str(external) if external else None


__all__ = ["event_identity", "merge_confirmed_event"]
