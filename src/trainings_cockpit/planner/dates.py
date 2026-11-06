"""Lokale Kalenderwochen und getrennte Zeitraumverträge.

Der Planer identifiziert eine Woche durch ihr lokales Montagsdatum. Das ist ein
Kalendertag in der Athletenzeitzone, kein UTC-Zeitpunkt. Deshalb rechnet dieses
Modul ausschließlich mit :class:`datetime.date`: Eine Woche sind sieben lokale
Kalendertage, niemals ``7 * 24`` Stunden. Die Zeitzone wird validiert und für
den Tageswechsel verwendet, verschiebt aber keinen bereits lokal gelesenen Tag.

Zwei Verträge bleiben absichtlich getrennt:

* :func:`planner_week_range` beschreibt Montag bis Sonntag für den Planer.
* :func:`rolling_dashboard_range` beschreibt die letzten ``days`` Tage für die
  Dashboard-Karte, einschließlich heute.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..config import DEFAULT_TIME_ZONE
from .primitives import LocalDate, require_local_date, require_time_zone
from .projections import TrainingRange

MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


def planner_time_zone(value: str | None = None) -> str:
    """Die explizite IANA-Zeitzone des Planers (Standard: Europe/Vienna)."""
    return require_time_zone(value or DEFAULT_TIME_ZONE)


def local_today(
    time_zone: str | None = None,
    *,
    now: datetime | None = None,
) -> LocalDate:
    """Heute in der Athletenzeitzone, nicht in der Zeitzone des Servers.

    ``now`` muss eine Zeitzone tragen. Ein naiver Zeitpunkt würde wieder die
    Prozesszeitzone ins Spiel bringen und ist deshalb kein gültiger Eingang.
    """
    zone = ZoneInfo(planner_time_zone(time_zone))
    moment = now or datetime.now(zone)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("now muss einen Zeitzonenbezug tragen.")
    return moment.astimezone(zone).date().isoformat()


def start_of_planner_week(
    local_date: LocalDate,
    time_zone: str | None = None,
) -> LocalDate:
    """Montag der Woche, in der ``local_date`` liegt.

    Der Sonntag gehört zur laufenden Woche: ``weekday() == 6`` führt sechs
    Kalendertage zurück auf den Montag derselben Woche.
    """
    planner_time_zone(time_zone)
    day = date.fromisoformat(require_local_date(local_date))
    return (day - timedelta(days=day.weekday())).isoformat()


def add_calendar_days(local_date: LocalDate, count: int) -> LocalDate:
    """Addiert Kalendertage, unabhängig von Sommer- und Winterzeit."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("count muss eine ganze Zahl sein.")
    day = date.fromisoformat(require_local_date(local_date))
    return (day + timedelta(days=count)).isoformat()


def add_calendar_weeks(week_start: LocalDate, count: int) -> LocalDate:
    """Verschiebt eine Woche um ``count`` Kalenderwochen.

    Ein beliebiger Tag wird zuerst auf seinen Montag normalisiert. Damit bleibt
    die Funktion auch dann eindeutig, wenn ein Aufrufer versehentlich einen
    Sonntag übergibt.
    """
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("count muss eine ganze Zahl sein.")
    monday = start_of_planner_week(week_start)
    return add_calendar_days(monday, count * 7)


def get_week_days(week_start: LocalDate, time_zone: str | None = None) -> tuple[LocalDate, ...]:
    """Genau sieben lokale Tage, Montag bis Sonntag, aufsteigend."""
    planner_time_zone(time_zone)
    monday = start_of_planner_week(week_start)
    return tuple(add_calendar_days(monday, offset) for offset in range(7))


#: Sprechender Alias für die Planer-UI.
week_days = get_week_days


def is_date_in_week(local_date: LocalDate, week_start: LocalDate) -> bool:
    """Ob ein lokaler Tag in derselben Montag–Sonntag-Woche liegt."""
    day = require_local_date(local_date)
    monday = start_of_planner_week(week_start)
    return monday <= day <= add_calendar_days(monday, 6)


def current_planner_week(
    time_zone: str | None = None,
    *,
    now: datetime | None = None,
) -> LocalDate:
    """Die aktuelle Woche zur Laufzeit; kein fester Demotag."""
    return start_of_planner_week(local_today(time_zone, now=now), time_zone)


def planner_week_range(
    week_start: LocalDate,
    time_zone: str | None = None,
) -> TrainingRange:
    """Der Planervertrag: Montag bis Sonntag, inklusive lokaler Grenzen."""
    zone = planner_time_zone(time_zone)
    monday = start_of_planner_week(week_start, zone)
    return TrainingRange(monday, add_calendar_days(monday, 6), zone)


def rolling_dashboard_range(
    today: LocalDate,
    days: int = 7,
    time_zone: str | None = None,
) -> TrainingRange:
    """Der Dashboardvertrag: heute plus die ``days - 1`` Tage davor.

    Diese Grenzen sind absichtlich nicht die Kalenderwoche und werden auch
    nicht von einer im Planer gewählten Woche beeinflusst.
    """
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days muss eine positive ganze Zahl sein.")
    zone = planner_time_zone(time_zone)
    end = require_local_date(today)
    return TrainingRange(add_calendar_days(end, -(days - 1)), end, zone)


def parse_week_parameter(
    value: str | None,
    time_zone: str | None = None,
    *,
    now: datetime | None = None,
) -> LocalDate:
    """API-Parameter ``week`` als lokaler Montag.

    Ein leerer Parameter bedeutet „aktuelle Woche“. Jeder nichtleere Wert muss
    ein lokales ``JJJJ-MM-TT`` sein; ein beliebiger Tag derselben Woche wird auf
    seinen Montag normalisiert. Die UI-Zeitquelle wird nicht mit dem Parameter
    vermischt: Ohne Wert entscheidet :func:`current_planner_week`, mit Wert nur
    der validierte lokale Tag.
    """
    zone = planner_time_zone(time_zone)
    if value is None or not value.strip():
        return current_planner_week(zone, now=now)
    return start_of_planner_week(require_local_date(value, "week"), zone)


def format_day(local_date: LocalDate) -> str:
    """Zum Beispiel ``9. November`` (ohne Jahr)."""
    day = date.fromisoformat(require_local_date(local_date))
    return f"{day.day}. {MONTHS[day.month - 1]}"


def format_day_with_year(local_date: LocalDate) -> str:
    """Zum Beispiel ``9. November 2026``."""
    day = date.fromisoformat(require_local_date(local_date))
    return f"{format_day(local_date)} {day.year}"


def completion_text(local_date: LocalDate) -> str:
    """Der kurze Erledigt-Hinweis am ursprünglichen Plantermin."""
    return f"Erledigt am {format_day(local_date)}"


def week_label(week_start: LocalDate) -> str:
    """Deutsche Wochenbeschriftung für Monats- und Jahresgrenzen.

    * gleicher Monat: ``2.–8. November 2026``
    * Monatswechsel: ``30. November – 6. Dezember 2026``
    * Jahreswechsel: ``28. Dezember 2026 – 3. Januar 2027``
    """
    monday = date.fromisoformat(start_of_planner_week(week_start))
    sunday = monday + timedelta(days=6)
    start_month = MONTHS[monday.month - 1]
    end_month = MONTHS[sunday.month - 1]
    if monday.year != sunday.year:
        return (
            f"{monday.day}. {start_month} {monday.year} – "
            f"{sunday.day}. {end_month} {sunday.year}"
        )
    if monday.month != sunday.month:
        return f"{monday.day}. {start_month} – {sunday.day}. {end_month} {monday.year}"
    return f"{monday.day}.–{sunday.day}. {start_month} {monday.year}"


def reschedule_plan(plan: object, new_date: LocalDate):
    """Verschiebt einen Plan auf einen lokalen Tag und behält seine Uhrzeit.

    Die lokale Uhrzeit ist kein UTC-Zeitpunkt. Sie wird unverändert
    übernommen; nur das Kalenderdatum ändert sich. Remote- und Knoten-IDs
    bleiben ebenfalls erhalten.
    """
    target = require_local_date(new_date)
    move = getattr(plan, "reschedule", None)
    if move is None:
        raise TypeError("plan muss ein PlannedWorkout mit reschedule() sein.")
    return move(target)


__all__ = [
    "MONTHS",
    "add_calendar_days",
    "add_calendar_weeks",
    "completion_text",
    "current_planner_week",
    "format_day",
    "format_day_with_year",
    "get_week_days",
    "is_date_in_week",
    "local_today",
    "parse_week_parameter",
    "planner_time_zone",
    "planner_week_range",
    "reschedule_plan",
    "rolling_dashboard_range",
    "start_of_planner_week",
    "week_days",
    "week_label",
]
