"""Löschen einer geplanten Einheit gegen die Quelle.

Die Einheit wird zuerst bei intervals.icu gelöscht. Meldet die Quelle die
Einheit als nicht vorhanden, ist das kein Fehler: der lokale Bestand wird
trotzdem entfernt, damit eine extern gelöschte Planung nicht dauerhaft im
Trainingskalender stehen bleibt. Andere Quellenfehler lassen den lokalen
Bestand unangetastet; der Löschversuch kann dann wiederholt werden.

Es gibt keine zweite Identität und keinen Ersatz-Create: adressiert wird
ausschließlich die vorhandene Remote-Event-ID. Aufgezeichnete Einheiten
(`activity`) sind nicht Teil dieses Vorgangs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DeleteGateway(Protocol):
    """Die minimale Löschbrücke zum vorhandenen Event-Dienst."""

    def delete_event(self, remote_id: str) -> object: ...


@dataclass(frozen=True, slots=True)
class DeleteOutcome:
    """Was die Quelle über die Einheit gesagt hat.

    ``remote`` ist ``deleted``, wenn die Löschanfrage angenommen wurde, und
    ``missing``, wenn die Quelle die Einheit bereits nicht mehr kennt. In
    beiden Fällen darf der lokale Bestand entfernt werden.
    """

    remote: str
    message: str

    def __post_init__(self) -> None:
        if self.remote not in {"deleted", "missing"}:
            raise ValueError(f"Unbekannter Löschzustand: {self.remote!r}")

    def as_dict(self) -> dict[str, str]:
        return {"remote": self.remote, "message": self.message}


class EventDeleteService:
    """Führt genau einen Löschversuch aus und ordnet einen 404 als „weg“ ein."""

    def __init__(self, gateway: DeleteGateway) -> None:
        if not callable(getattr(gateway, "delete_event", None)):
            raise TypeError("gateway muss delete_event() anbieten.")
        self._gateway = gateway

    def delete(self, remote_id: str) -> DeleteOutcome:
        if not isinstance(remote_id, str) or not remote_id.strip():
            raise ValueError("Löschen braucht die Remote-Event-ID.")
        try:
            self._gateway.delete_event(remote_id)
        except Exception as exc:  # noqa: BLE001 - HTTP-Status ist die Einordnung
            if getattr(exc, "status_code", None) == 404:
                return DeleteOutcome(
                    "missing",
                    "Die Einheit war in intervals.icu nicht mehr vorhanden und "
                    "wurde aus dem Trainingskalender entfernt.",
                )
            raise
        return DeleteOutcome(
            "deleted",
            "Die Einheit wurde in intervals.icu und im Trainingskalender gelöscht.",
        )


__all__ = ["DeleteGateway", "DeleteOutcome", "EventDeleteService"]
