"""Produktbrücke für bestätigte Planer-Writes.

Die einzige Stelle, die den vorhandenen ``IntervalsClient`` an den
``EventWriteService`` anschließt. Tests ersetzen diese Brücke durch einen
kontrollierten Adapter; der Produktpfad wird ausschließlich über diese
Kontextgrenze aufgerufen.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from ..config import Settings
from ..sources.intervals import IntervalsClient
from .event_write import EventWriteService, IntervalsEventAdapter


@contextmanager
def event_write_service(settings: Settings) -> Iterator[EventWriteService]:
    """Öffnet den vorhandenen Client und schließt ihn nach dem Vorgang."""
    if not settings.intervals_key:
        raise RuntimeError("Kein intervals.icu-Key konfiguriert.")
    with IntervalsClient(
        settings.intervals_key,
        settings.intervals_athlete,
        settings.base_url,
    ) as client:
        yield EventWriteService(IntervalsEventAdapter(client))


__all__ = ["event_write_service"]
