"""Phase-0-Befund: Datenabdeckung, Lücken, Go/No-Go."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

DATE_KEYS = (
    "id",
    "calendarDate",
    "calendar_date",
    "date",
    "start_date_local",
    "startTimeLocal",
    "sleepStartTimestampGMT",
)

WELLNESS_FIELDS = (
    ("hrv", "HRV"),
    ("restingHR", "Ruhepuls"),
    ("sleepSecs", "Schlafdauer"),
    ("sleepScore", "Schlafscore"),
    ("readiness", "Readiness (vendor)"),
    ("weight", "Gewicht"),
)


def build_report(
    intervals: dict[str, Any] | None,
    garmin: dict[str, Any] | None,
    push: dict[str, Any] | None,
    generated: datetime,
) -> str:
    intervals = intervals or {}
    activities = intervals.get("activities") or []
    wellness = intervals.get("wellness") or []
    events = intervals.get("events") or []
    sports = intervals.get("sport_settings") or []

    lines: list[str] = []
    add = lines.append

    add(f"# Phase-0-Befund — {generated.date().isoformat()}")
    add("")
    add(f"Erstellt: {generated.strftime('%Y-%m-%d %H:%M %Z')}")
    athlete = intervals.get("athlete") or {}
    if athlete:
        add(
            f"Athlet: {athlete.get('name') or '—'} "
            f"(ID {athlete.get('id', '—')}, {athlete.get('timezone', '—')})"
        )
    add("")

    # ---------------------------------------------------------------- intervals
    add("## intervals.icu")
    add("")
    first, last = _span(activities)
    add("| Datensatz | Anzahl | Zeitraum |")
    add("|---|---:|---|")
    add(f"| Aktivitäten | {len(activities)} | {_range(first, last)} |")
    w_first, w_last = _span(wellness)
    add(f"| Wellness-Tage | {len(wellness)} | {_range(w_first, w_last)} |")
    add(f"| Kalender-Events | {len(events)} | — |")
    add(f"| Sport-Settings | {len(sports)} | — |")
    add("")

    if activities:
        add("**Aktivitäten nach Sport:** " + _counter_text(activities, "type"))
        loads = _coverage(activities, "icu_training_load")
        add(f"**Trainingslast vorhanden:** {loads[0]}/{loads[1]}")
        add(f"**Quellen:** {_counter_text(activities, 'source')}")
        add("")

    if wellness:
        add("| Wellness-Feld | Abdeckung |")
        add("|---|---:|")
        for field, label in WELLNESS_FIELDS:
            have, total = _coverage(wellness, field)
            add(f"| {label} | {have}/{total} |")
        add("")

    workout_events = [e for e in events if e.get("category") == "WORKOUT"]
    if events:
        add(f"**Geplante Workouts im Kalender:** {len(workout_events)}")
        add("")

    # ------------------------------------------------------------------ Garmin
    add("## Garmin Personal API")
    add("")
    if not garmin:
        add("_Kein Garmin-Dump vorhanden._")
        add("")
    else:
        g_acts = garmin.get("activities") or []
        g_sleep = garmin.get("sleep") or []
        g_hrv = garmin.get("hrv") or []
        g_weight = garmin.get("weight") or []
        add("| Datensatz | Anzahl |")
        add("|---|---:|")
        add(f"| Profil | {'ok' if garmin.get('profile') else 'fehlt'} |")
        add(f"| Aktivitäten | {len(g_acts)} |")
        add(f"| Schlaf-Nächte | {len(g_sleep)} |")
        add(f"| HRV-Nächte | {len(g_hrv)} |")
        add(f"| Gewichtseinträge | {len(g_weight)} |")
        add(f"| FIT-Download | {_fit_text(garmin)} |")
        add("")
        errors = garmin.get("errors") or {}
        if errors:
            add("**Fehler je Endpunkt:**")
            for name, message in errors.items():
                add(f"- `{name}`: {message}")
            add("")

    # ------------------------------------------------------------------ Abgleich
    add("## Abgleich")
    add("")
    icu_days = {d for d in (_date_of(a) for a in activities) if d}
    gar_days = {d for d in (_date_of(a) for a in (garmin or {}).get("activities") or []) if d}
    overlap = sorted(icu_days & gar_days)
    add(f"- Tage mit Aktivität in beiden Quellen: **{len(overlap)}**")
    if overlap:
        add(f"  - {', '.join(d.isoformat() for d in overlap[-5:])}")
    add(f"- Letzter intervals-Aktivitätstag: {max(icu_days).isoformat() if icu_days else '—'}")
    last_wellness = _last_date(wellness)
    add(f"- Letzter Wellness-Tag: {last_wellness.isoformat() if last_wellness else '—'}")
    if last_wellness:
        add(f"- Datenalter Wellness: {(generated.date() - last_wellness).days} Tage")
    add("")

    # -------------------------------------------------------------------- Push
    add("## Workout-Push")
    add("")
    if not push:
        add("_Nicht getestet._")
        add("")
    else:
        verify = push.get("verify") or {}
        add(f"- Event-ID: {verify.get('event_id')}")
        add(f"- external_id: `{verify.get('external_id')}`")
        add(f"- Geparste Schritte: {verify.get('steps')}")
        add(f"- Trainingslast: {verify.get('load')}")
        add(f"- Intensität: {verify.get('intensity')}")
        add(f"- Ergebnis: {'✅ ok' if verify.get('ok') else '❌ fehlgeschlagen'}")
        for issue in verify.get("issues") or []:
            add(f"  - {issue}")
        add("")

    # --------------------------------------------------------------- Checkliste
    add("## Checkliste")
    add("")
    zepp = _zepp_ready(wellness, generated.date())
    checks = [
        ("intervals.icu-Key gültig und Daten sichtbar", bool(activities or wellness)),
        (
            "Garmin-Key gültig, Aktivitäten abrufbar",
            bool(garmin)
            and bool((garmin or {}).get("activities"))
            and "activities" not in ((garmin or {}).get("errors") or {}),
        ),
        ("Garmin-FIT-Download funktioniert", bool((garmin or {}).get("fit_zip_bytes"))),
        (
            "Workout-Text wird geparst (workout_doc + Last)",
            bool((push or {}).get("verify", {}).get("ok")),
        ),
        ("Zepp/Helio-Wellness kommt an (Schlaf + HRV)", zepp),
        ("Kalender-Events lesbar", bool(events) or bool(intervals)),
    ]
    for label, ok in checks:
        add(f"- [{'x' if ok else ' '}] {label}")
    add("")

    add("## Nächster Schritt")
    add("")
    if not garmin:
        add("- Garmin-Key anlegen und `tc fetch garmin --days 30 --fit` ausführen.")
    if not (push or {}).get("verify", {}).get("ok"):
        add("- `tc push-test` ausführen und Ergebnis prüfen.")
    if not zepp:
        add("- Zepp-Sync prüfen: Helio in der Zepp-App synchronisieren, intervals.icu öffnen.")
    add("- Befund mit den Entscheidungen aus `docs/KONZEPT.md` abgleichen, dann Phase 1 starten.")
    add("")

    return "\n".join(lines)


# ------------------------------------------------------------------- Helfer


def _coverage(rows: Iterable[dict[str, Any]], field: str) -> tuple[int, int]:
    total = 0
    have = 0
    for row in rows:
        total += 1
        value = row.get(field)
        if value not in (None, "", [], {}):
            have += 1
    return have, total


def _counter_text(rows: Iterable[dict[str, Any]], field: str) -> str:
    counter = Counter(str(row.get(field) or "unbekannt") for row in rows)
    if not counter:
        return "—"
    return ", ".join(f"{name} {count}" for name, count in counter.most_common())


def _date_of(row: dict[str, Any]) -> date | None:
    for key in DATE_KEYS:
        raw = row.get(key)
        if not raw:
            continue
        if isinstance(raw, (int, float)):
            try:
                return datetime.fromtimestamp(raw / 1000 if raw > 1e11 else raw).date()
            except (OverflowError, OSError, ValueError):
                continue
        text = str(raw)
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            continue
    return None


def _span(rows: Iterable[dict[str, Any]]) -> tuple[date | None, date | None]:
    days = [d for d in (_date_of(row) for row in rows) if d]
    if not days:
        return None, None
    return min(days), max(days)


def _last_date(rows: Iterable[dict[str, Any]]) -> date | None:
    days = [d for d in (_date_of(row) for row in rows) if d]
    return max(days) if days else None


def _range(first: date | None, last: date | None) -> str:
    if not first or not last:
        return "—"
    return f"{first.isoformat()} … {last.isoformat()}"


def _fit_text(garmin: dict[str, Any]) -> str:
    size = garmin.get("fit_zip_bytes") or 0
    if not size:
        return "nicht getestet"
    return f"{size / 1024:.0f} KB (Aktivität {garmin.get('fit_activity_id')})"


def _zepp_ready(wellness: list[dict[str, Any]], today: date) -> bool:
    window_start = today - timedelta(days=21)
    recent = [w for w in wellness if (d := _date_of(w)) and d >= window_start]
    if not recent:
        return False
    sleep, _ = _coverage(recent, "sleepSecs")
    hrv, _ = _coverage(recent, "hrv")
    return sleep >= 7 and hrv >= 7
