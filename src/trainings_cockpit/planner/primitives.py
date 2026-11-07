"""Lokale Datums-, Zeit- und Zeitzonenprüfungen für das Planungsmodell.

Der Planer rechnet mit lokalen Kalendertagen. Ein `LocalDate` ist deshalb ein
validiertes `YYYY-MM-DD`, kein UTC-Zeitpunkt. Die Wochenarithmetik liegt in
``dates.py``; hier stehen die Invarianten, die das Modell nicht verletzen darf.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LocalDate = str

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$")


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} muss ein nichtleerer Text sein.")
    return value.strip()


def require_local_date(value: object, field: str = "date") -> LocalDate:
    text = require_text(value, field)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} muss ein lokales Datum JJJJ-MM-TT sein.") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{field} muss die Form JJJJ-MM-TT haben, nicht {text!r}.")
    return text


def require_time_zone(value: object, field: str = "time_zone") -> str:
    text = require_text(value, field)
    try:
        ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"{field} ist keine bekannte IANA-Zeitzone: {text!r}.") from exc
    return text


def require_local_time(value: object, field: str = "local_time") -> str:
    text = require_text(value, field)
    if not _TIME_RE.match(text):
        raise ValueError(f"{field} muss HH:MM oder HH:MM:SS sein, nicht {text!r}.")
    return text


def require_timestamp(value: object, field: str = "timestamp") -> str:
    text = require_text(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} muss ein ISO-8601-Zeitpunkt sein.") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} braucht eine Zeitzone.")
    return text
