"""Trainings-Cockpit CLI — Phase 0."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from . import __version__, db, dedupe, metrics
from . import streams as streams_mod
from . import sync as sync_mod
from .config import PROJECT_ROOT, Settings, mask
from .security import is_world_readable
from .sources.garmin import GarminUnavailable, actor_rows, fetch_garmin
from .sources.intervals import IntervalsClient, IntervalsError
from .spike import dump, workout
from .spike import report as report_mod

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tc",
        description="Trainings- und Recovery-Cockpit (Phase 0: Datenzugang prüfen)",
    )
    parser.add_argument("--version", action="version", version=f"tc {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Konfiguration und Keys prüfen")
    doctor.add_argument("--online", action="store_true", help="Keys live testen")

    fetch = sub.add_parser("fetch", help="Rohdaten von intervals.icu und/oder Garmin holen")
    fetch.add_argument("source", choices=["intervals", "garmin", "all"])
    fetch.add_argument("--days", type=int, default=90, help="Vergangenheit in Tagen (Default 90)")
    fetch.add_argument("--fit", action="store_true", help="Garmin: FIT-Download testen")

    push = sub.add_parser("push-test", help="Test-Workout nach intervals.icu pushen und prüfen")
    push.add_argument("--date", help="Datum YYYY-MM-DD (Default: in 7 Tagen)")
    push.add_argument("--sport", default="Ride", help="intervals-Sportname (Default: Ride)")
    push.add_argument("--delete", action="store_true", help="Event nach der Prüfung löschen")
    push.add_argument("--dry-run", action="store_true", help="Nur Payload zeigen")

    rep = sub.add_parser("report", help="Phase-0-Befund erzeugen")
    rep.add_argument("--date", help="Dump-Tag YYYY-MM-DD (Default: neuester intervals-Dump)")

    syn = sub.add_parser("sync", help="Daten von intervals.icu in die lokale DB laden")
    syn.add_argument("--days", type=int, default=365, help="Vergangenheit in Tagen")

    wch = sub.add_parser("woche", help="Wochenübersicht aus der Datenbank")
    wch.add_argument("--wochen", type=int, default=6, help="Anzahl Wochen (Default 6)")

    dup = sub.add_parser("dedupe", help="Doppelt aufgezeichnete Einheiten aus der DB entfernen")
    dup.add_argument("--dry-run", action="store_true", help="Nur zeigen, nichts löschen")

    gar = sub.add_parser("garmin", help="Läufe und Schwimmen direkt aus der Garmin-Personal-API laden")
    gar.add_argument("--days", type=int, default=365, help="Vergangenheit in Tagen")

    strm = sub.add_parser("streams", help="Verläufe der letzten Tage aus der Aufzeichnung holen")
    strm.add_argument("--days", type=int, default=14, help="Vergangenheit in Tagen (Default 14)")

    base = sub.add_parser("baseline", help="Referenz der Nachtsignale: Stand, Neustart, aus")
    base.add_argument("--start", help="Erste Nacht mit dem neuen Sensor (JJJJ-MM-TT)")
    base.add_argument("--off", action="store_true", help="Neustart-Marke entfernen")

    srv = sub.add_parser("serve", help="Dashboard starten")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)
    settings = Settings.load()

    try:
        if args.command == "doctor":
            return _doctor(settings, args.online)
        if args.command == "fetch":
            return _fetch(settings, args.source, args.days, args.fit)
        if args.command == "push-test":
            return _push_test(settings, args)
        if args.command == "report":
            return _report(settings, args.date)
        if args.command == "sync":
            return _sync(settings, args.days)
        if args.command == "woche":
            return _woche(settings, args.wochen)
        if args.command == "dedupe":
            return _dedupe(settings, args.dry_run)
        if args.command == "garmin":
            return _garmin(settings, args.days)
        if args.command == "streams":
            return _streams(settings, args.days)
        if args.command == "baseline":
            return _baseline(settings, args)
        if args.command == "serve":
            return _serve(settings, args)
    except IntervalsError as exc:
        console.print(f"[red]intervals.icu:[/red] {exc}")
        return 2
    except GarminUnavailable as exc:
        console.print(f"[red]Garmin:[/red] {exc}")
        return 2
    return 0


# ------------------------------------------------------------------ garmin


def _garmin(settings: Settings, days: int) -> int:
    """Nur Aktivitäten holen — Wellness kommt über intervals bzw. den Sync."""
    if not settings.garmin_key:
        console.print("[red]Kein GARMIN_PERSONAL_API_KEY gesetzt.[/red]")
        return 2

    today = date.today()
    oldest = today - timedelta(days=max(days, 1))
    cache = settings.ensure_data_dir() / "garmin" / "bearer-token.json"
    cache.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Garmin[/bold] · Läufe und Schwimmen · {oldest} … {today}")
    result = fetch_garmin(
        settings.garmin_key,
        oldest,
        today,
        only_activities=True,
        token_cache=cache,
    )
    rows = actor_rows(result)
    if not rows:
        console.print("[yellow]Keine Läufe oder Schwimmen im Zeitraum.[/yellow]")
        return 1

    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        neu = db.upsert_activities(conn, rows, mapped=True)
        weg = sync_mod.dubletten_entfernen(conn)
    finally:
        conn.close()

    console.print(
        f"  {neu} Einheiten geschrieben · {weg} Dubletten entfernt"
        + (f" · Fehler: {', '.join(sorted(result.errors))}" if result.errors else "")
    )
    return 0


# ---------------------------------------------------------------- baseline


def _baseline(settings: Settings, args: argparse.Namespace) -> int:
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)

        if args.off:
            db.set_wellness_epoch(conn, None)
            console.print("Neustart-Marke entfernt — die Referenz nutzt wieder die ganze Historie.")
            return 0

        if args.start:
            try:
                epoch = date.fromisoformat(args.start)
            except ValueError:
                console.print("[red]Datum muss JJJJ-MM-TT sein.[/red]")
                return 2
            db.set_wellness_epoch(conn, epoch)
            console.print(
                f"Referenz beginnt am {epoch.strftime('%d.%m.%Y')}. "
                f"Ab {metrics.REFERENCE_MIN_NIGHTS} Nächten im 60-Tage-Fenster entsteht ein Wert."
            )
            return 0

        epoch = db.wellness_epoch(conn)
        if epoch is None:
            console.print("Keine Neustart-Marke gesetzt — Referenz läuft über die ganze Historie.")
            return 0

        nights = conn.execute(
            "SELECT COUNT(*) FROM wellness WHERE date >= ? "
            "AND (hrv IS NOT NULL OR rhr IS NOT NULL OR sleep_s IS NOT NULL "
            "OR respiration IS NOT NULL)",
            (epoch.isoformat(),),
        ).fetchone()[0]
        state = (
            "Referenz wird aufgebaut"
            if nights < metrics.REFERENCE_MIN_NIGHTS
            else "Referenz steht"
        )
        console.print(
            f"Seit {epoch.strftime('%d.%m.%Y')}: {nights} Nächte mit Signal, "
            f"Fenster {metrics.REFERENCE_DAYS} Tage. {state}."
        )
        return 0
    finally:
        conn.close()


# ------------------------------------------------------------------ doctor


def _doctor(settings: Settings, online: bool) -> int:
    console.print(Panel.fit(f"Trainings-Cockpit {__version__} · Konfiguration", style="bold"))

    env_file = PROJECT_ROOT / ".env"
    env_exists = env_file.exists()
    env_private = env_exists and not is_world_readable(env_file)
    checks: list[tuple[str, bool, str]] = [
        ("Python >= 3.12", sys.version_info >= (3, 12), sys.version.split()[0]),
        (".env vorhanden", env_exists, ".env" if env_exists else "cp .env.example .env"),
        (
            ".env nur für dich lesbar",
            (not env_exists) or env_private,
            "chmod 600 .env" if env_exists and not env_private else ("ok" if env_exists else "—"),
        ),
        ("intervals.icu-Key", bool(settings.intervals_key), mask(settings.intervals_key)),
        ("Garmin-Key", bool(settings.garmin_key), mask(settings.garmin_key)),
    ]

    try:
        settings.ensure_data_dir()
        probe = settings.data_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        writable = True
        target = str(settings.data_dir)
    except OSError as exc:
        writable = False
        target = str(exc)
    checks.append(("Datenverzeichnis schreibbar", writable, target))

    if online:
        checks.append(("intervals.icu online", *_online_intervals(settings)))
        checks.append(("Garmin online", *_online_garmin(settings)))

    table = Table(box=None, show_header=False, padding=(0, 1))
    for label, ok, detail in checks:
        mark = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(mark, label, f"[dim]{detail}[/dim]")
    console.print(table)

    required = [bool(settings.intervals_key), writable]
    return 0 if all(required) else 1


def _client(settings: Settings) -> IntervalsClient:
    return IntervalsClient(
        settings.intervals_key or "",
        settings.intervals_athlete,
        settings.base_url,
    )


def _online_intervals(settings: Settings) -> tuple[bool, str]:
    if not settings.intervals_key:
        return False, "kein Key"
    try:
        with _client(settings) as client:
            athlete = client.athlete()
        return True, f"{athlete.get('name', '—')} (ID {athlete.get('id', '—')})"
    except IntervalsError as exc:
        return False, str(exc)[:120]


def _online_garmin(settings: Settings) -> tuple[bool, str]:
    if not settings.garmin_key:
        return False, "kein Key"
    try:
        from garmin_personal_api import (  # noqa: PLC0415
            GarminPersonalApiClient,
            PersonalApiAuthenticator,
        )

        cache = settings.data_dir / "garmin" / "bearer-token.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        with PersonalApiAuthenticator(bearer_token_cache_file=cache) as auth:
            token = auth.obtain_token(settings.garmin_key)
        with GarminPersonalApiClient(token.access_token) as client:
            profile = client.get_user_profile_settings()
        name = (profile or {}).get("displayName") or (profile or {}).get("fullName") or "ok"
        return True, str(name)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]


# ------------------------------------------------------------------- fetch


def _fetch(settings: Settings, source: str, days: int, fit: bool) -> int:
    today = date.today()
    oldest = today - timedelta(days=max(days, 1))
    ok = True

    if source in ("intervals", "all"):
        ok = _fetch_intervals(settings, oldest, today) and ok
    if source in ("garmin", "all"):
        ok = _fetch_garmin(settings, oldest, today, fit) and ok
    return 0 if ok else 1


def _fetch_intervals(settings: Settings, oldest: date, today: date) -> bool:
    if not settings.intervals_key:
        console.print("[red]Kein INTERVALS_API_KEY gesetzt.[/red]")
        return False

    console.print(f"[bold]intervals.icu[/bold] · {oldest} … {today}")
    events_until = today + timedelta(days=365)

    with _client(settings) as client:
        athlete = client.athlete()
        activities = client.activities(oldest, today)
        wellness = client.wellness(oldest, today)
        events = client.events(oldest, events_until)
        sports = client.sport_settings()

    target = dump.dump_dir(settings.data_dir, "intervals", today)
    dump.write_json(target / "athlete.json", athlete)
    dump.write_json(target / "activities.json", activities)
    dump.write_json(target / "wellness.json", wellness)
    dump.write_json(target / "events.json", events)
    dump.write_json(target / "sport-settings.json", sports)
    dump.write_json(
        target / "meta.json",
        {
            "source": "intervals.icu",
            "fetched_at": dump.now().isoformat(),
            "oldest": oldest.isoformat(),
            "newest": today.isoformat(),
            "events_until": events_until.isoformat(),
            "counts": {
                "activities": len(activities),
                "wellness": len(wellness),
                "events": len(events),
                "sport_settings": len(sports),
            },
        },
    )

    console.print(
        f"  Aktivitäten [bold]{len(activities)}[/bold] · "
        f"Wellness [bold]{len(wellness)}[/bold] · "
        f"Events [bold]{len(events)}[/bold] · "
        f"Sport-Settings [bold]{len(sports)}[/bold]"
    )
    console.print(f"  → [dim]{target}[/dim]")
    return True


def _fetch_garmin(settings: Settings, oldest: date, today: date, fit: bool) -> bool:
    if not settings.garmin_key:
        console.print("[red]Kein GARMIN_PERSONAL_API_KEY gesetzt.[/red]")
        return False

    console.print(f"[bold]Garmin[/bold] · {oldest} … {today}")
    cache = settings.ensure_data_dir() / "garmin" / "bearer-token.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    result = fetch_garmin(
        settings.garmin_key,
        oldest,
        today,
        download_fit=fit,
        token_cache=cache,
    )

    target = dump.dump_dir(settings.data_dir, "garmin", today)
    payload = asdict(result)
    dump.write_json(target / "profile.json", payload["profile"])
    dump.write_json(target / "activities.json", payload["activities"])
    dump.write_json(target / "sleep.json", payload["sleep"])
    dump.write_json(target / "hrv.json", payload["hrv"])
    dump.write_json(target / "weight.json", payload["weight"])
    dump.write_json(
        target / "meta.json",
        {
            "source": "garmin",
            "fetched_at": dump.now().isoformat(),
            "fit_zip_bytes": payload["fit_zip_bytes"],
            "fit_activity_id": payload["fit_activity_id"],
            "errors": payload["errors"],
        },
    )

    console.print(
        f"  Aktivitäten [bold]{len(payload['activities'])}[/bold] · "
        f"Schlaf [bold]{len(payload['sleep'])}[/bold] · "
        f"HRV [bold]{len(payload['hrv'])}[/bold] · "
        f"Gewicht [bold]{len(payload['weight'])}[/bold]"
    )
    if result.errors:
        for name, message in result.errors.items():
            console.print(f"  [yellow]![/yellow] {name}: {message}")
    console.print(f"  → [dim]{target}[/dim]")
    return not result.errors


# --------------------------------------------------------------- push-test


def _push_test(settings: Settings, args: argparse.Namespace) -> int:
    day = date.fromisoformat(args.date) if args.date else date.today() + timedelta(days=7)
    event = workout.build_test_event(day, sport=args.sport)

    if args.dry_run:
        console.print_json(json.dumps(event, ensure_ascii=False))
        return 0

    if not settings.intervals_key:
        console.print("[red]Kein INTERVALS_API_KEY gesetzt.[/red]")
        return 2

    console.print(f"[bold]Push-Test[/bold] · {day} · {args.sport}")
    with _client(settings) as client:
        created = client.upsert_events([event])
        if not created:
            console.print("[red]intervals.icu hat kein Event zurückgegeben.[/red]")
            return 1
        event_id = created[0].get("id")
        if event_id is None:
            console.print("[red]Event ohne ID zurückgegeben.[/red]")
            return 1
        fresh = client.event(int(event_id))
        verify = workout.verify_event(fresh, event["external_id"])
        if args.delete:
            client.delete_events([{"id": int(event_id)}])

    target = settings.ensure_data_dir() / "raw" / "push"
    dump.write_json(
        target / f"{date.today().isoformat()}.json",
        {"event_date": day.isoformat(), "event": event, "verify": verify},
    )

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_row("Event-ID", str(verify["event_id"]))
    table.add_row("Typ", str(verify["type"]))
    table.add_row("Schritte", str(verify["steps"]))
    table.add_row("Trainingslast", str(verify["load"]))
    table.add_row("Intensität", str(verify["intensity"]))
    table.add_row("Ergebnis", "[green]ok[/green]" if verify["ok"] else "[red]fehlgeschlagen[/red]")
    console.print(table)
    for issue in verify["issues"]:
        console.print(f"  [red]![/red] {issue}")
    if args.delete:
        console.print("  [dim]Event wieder gelöscht.[/dim]")
    return 0 if verify["ok"] else 1


# ------------------------------------------------------------------ report


def _report(settings: Settings, day_arg: str | None) -> int:
    if day_arg:
        day = date.fromisoformat(day_arg)
    else:
        day = dump.latest_day(settings.data_dir, "intervals") or date.today()

    intervals_dir = settings.data_dir / "raw" / "intervals" / day.isoformat()
    garmin_dir = settings.data_dir / "raw" / "garmin" / day.isoformat()

    intervals: dict[str, Any] | None = None
    if intervals_dir.exists():
        intervals = {
            "athlete": dump.read_json(intervals_dir / "athlete.json"),
            "activities": dump.read_json(intervals_dir / "activities.json") or [],
            "wellness": dump.read_json(intervals_dir / "wellness.json") or [],
            "events": dump.read_json(intervals_dir / "events.json") or [],
            "sport_settings": dump.read_json(intervals_dir / "sport-settings.json") or [],
        }

    garmin: dict[str, Any] | None = None
    if garmin_dir.exists():
        meta = dump.read_json(garmin_dir / "meta.json") or {}
        garmin = {
            "profile": dump.read_json(garmin_dir / "profile.json"),
            "activities": dump.read_json(garmin_dir / "activities.json") or [],
            "sleep": dump.read_json(garmin_dir / "sleep.json") or [],
            "hrv": dump.read_json(garmin_dir / "hrv.json") or [],
            "weight": dump.read_json(garmin_dir / "weight.json") or [],
            "fit_zip_bytes": meta.get("fit_zip_bytes", 0),
            "fit_activity_id": meta.get("fit_activity_id"),
            "errors": meta.get("errors") or {},
        }

    push_file = settings.data_dir / "raw" / "push" / f"{day.isoformat()}.json"
    if not push_file.exists():
        candidates = sorted((settings.data_dir / "raw" / "push").glob("*.json"))
        push_file = candidates[-1] if candidates else push_file
    push = dump.read_json(push_file)

    markdown = report_mod.build_report(intervals, garmin, push, dump.now())
    path = dump.report_path(settings.data_dir, day)
    path.write_text(markdown, encoding="utf-8")

    console.print(Markdown(markdown))
    console.print(f"\n[dim]Gespeichert: {path}[/dim]")
    return 0


# -------------------------------------------------------------------- sync


def _woche(settings: Settings, wochen: int) -> int:
    from rich.table import Table

    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        zeilen = metrics.build_weeks(conn, wochen)
        if not zeilen:
            console.print("Keine Einheiten in der Datenbank.")
            return 0
        tabelle = Table(title=f"Letzte {len(zeilen)} Wochen")
        spalten = (
            "Woche", "von", "Lauf km", "Rad km", "sonst min",
            "Einheiten", "Stunden", "längster Lauf",
        )
        for spalte in spalten:
            tabelle.add_column(spalte, justify="right" if spalte != "Woche" else "left")
        for z in zeilen:
            tabelle.add_row(
                z["kw"], z["von"], f"{z['lauf_km']:.1f}", f"{z['rad_km']:.1f}",
                str(z["sonst_min"]), str(z["einheiten"]), f"{z['dauer_h']:.1f}",
                f"{z['langer_lauf_km']:.1f}",
            )
        console.print(tabelle)
        return 0
    finally:
        conn.close()


def _dedupe(settings: Settings, dry_run: bool) -> int:
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        rows = dedupe.aus_datenbank(conn)
        paare = dedupe.paare(rows)
        if not paare:
            console.print("Keine Dubletten gefunden.")
            return 0
        for gewinner, verlierer in paare:
            console.print(
                f"[yellow]doppelt[/yellow] {str(verlierer.get('start_date_local'))[:16]} "
                f"{verlierer.get('type')}: {verlierer.get('name')} "
                f"({verlierer.get('source')}) → bleibt: {gewinner.get('source')}"
            )
        if dry_run:
            console.print(f"{len(paare)} Paare, nichts gelöscht (--dry-run).")
            return 0
        weg = [str(v.get("id")) for _, v in paare if v.get("id")]
        entfernt = db.delete_activities(conn, weg)
        console.print(f"{entfernt} Einheiten entfernt.")
        return 0
    finally:
        conn.close()


def _sync(settings: Settings, days: int) -> int:
    console.print(f"[bold]Sync[/bold] · intervals.icu · {days} Tage")
    result = sync_mod.sync(settings, days=days)
    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_row("Athlet", str(result["athlete"]))
    table.add_row("Zeitraum", " … ".join(result["range"]))
    table.add_row("Aktivitäten", str(result["activities"]))
    table.add_row("Wellness-Tage", str(result["wellness"]))
    table.add_row("Events", str(result["events"]))
    table.add_row("Verläufe", str(result.get("streams", 0)))
    table.add_row("Datenbank", str(settings.db_path))
    console.print(table)
    return 0


def _streams(settings: Settings, days: int) -> int:
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        zahlen = streams_mod.fetch_missing(conn, settings, days=days)
    finally:
        conn.close()

    table = Table(box=None, show_header=False, padding=(0, 1))
    table.add_row("Neu", str(zahlen["neu"]))
    table.add_row("Ohne Sekundenwerte", str(zahlen["leer"]))
    table.add_row("Fehler", str(zahlen["fehler"]))
    console.print(table)
    return 0


# ------------------------------------------------------------------- serve


def _serve(settings: Settings, args: argparse.Namespace) -> int:
    import uvicorn  # noqa: PLC0415

    sync_mod.ensure_db(settings)
    url = f"http://{args.host}:{args.port}"
    console.print(f"[bold]Dashboard[/bold] → [link={url}]{url}[/link]")
    uvicorn.run(
        "trainings_cockpit.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
