#!/usr/bin/env python3
"""Schreibt die Aktivitäten aus dem Cockpit als Notizen ins Sport-Gehirn.

Liest die lokale SQLite-Datenbank des Cockpits und legt je Aktivität eine Datei
in ``training/`` an. Vorhandene ``quelle_id`` werden übersprungen, ein zweiter
Lauf legt also nichts doppelt an.

    python3 tools/vault_import.py --vault ~/Documents/Sport-Gehirn --monate 12
    python3 tools/vault_import.py --vault ~/Documents/Sport-Gehirn --trocken
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[1]
DB = PROJEKT / "data" / "cockpit.db"

SPORTART = {
    "Run": "lauf",
    "VirtualRun": "lauf",
    "TrailRun": "trail",
    "Ride": "rad",
    "VirtualRide": "rad",
    "EBikeRide": "rad",
    "Swim": "schwimmen",
    "OpenWaterSwim": "schwimmen",
    "WeightTraining": "kraft",
    "Workout": "sonstiges",
    "HighIntensityIntervalTraining": "sonstiges",
    "Transition": "sonstiges",
    "Walk": "wandern",
    "Hike": "wandern",
}
SPORT_LABEL = {
    "lauf": "Lauf",
    "trail": "Trail",
    "rad": "Rad",
    "schwimmen": "Schwimmen",
    "kraft": "Kraft",
    "wandern": "Wandern",
    "sonstiges": "Einheit",
}
#: Quellen, die als Garmin-Aufzeichnung gelten. Alles andere wird als manuell
#: geführt, weil die Vorlage nur garmin, strava und manuell kennt.
GARMIN_QUELLEN = {"GARMIN_CONNECT", "OAUTH_CLIENT"}
GARMIN_GERAETE = {"garmin", "health sync", " strava"}


def slug(text: str, laenge: int = 42) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:laenge].strip("-") or "einheit"


def zahl(wert: float | None, stellen: int = 2) -> str:
    if wert is None:
        return ""
    gerundet = round(float(wert), stellen)
    if gerundet == int(gerundet):
        return str(int(gerundet))
    return f"{gerundet:.{stellen}f}".rstrip("0").rstrip(".")


def pace(meter: float | None, sekunden: float | None) -> str:
    if not meter or not sekunden or meter <= 0 or sekunden <= 0:
        return ""
    pro_km = sekunden / (meter / 1000)
    minuten, rest = divmod(round(pro_km), 60)
    return f"{minuten}:{rest:02d}"


def vorhandene_ids(vault: Path) -> set[str]:
    ids: set[str] = set()
    for datei in (vault / "training").glob("*.md"):
        text = datei.read_text(encoding="utf-8", errors="replace")
        treffer = re.search(r'^quelle_id:[ \t]*"?([^"\n]*)"?', text, re.MULTILINE)
        if treffer and treffer.group(1).strip():
            ids.add(treffer.group(1).strip())
    return ids


def note(befehl: sqlite3.Row) -> tuple[str, dict[str, str]]:
    raw = json.loads(befehl["raw"] or "{}")
    sport = SPORTART.get(befehl["sport"], "sonstiges")
    start = befehl["start_local"] or f"{befehl['date']}T00:00:00"
    uhrzeit = start[11:16] if len(start) > 15 else ""
    meter = befehl["distance_m"]
    sekunden = befehl["moving_s"] or befehl["duration_s"]
    hf = befehl["avg_hr"]
    hfmax = befehl["max_hr"]
    hm = befehl["elevation_m"]
    geraet = (raw.get("device_name") or "").strip()
    quelle_raw = raw.get("source") or ""

    quelle = "garmin"
    if quelle_raw not in GARMIN_QUELLEN and not any(
        g in geraet.lower() for g in GARMIN_GERAETE
    ):
        quelle = "manuell"

    felder = {
        "type": "training",
        "datum": befehl["date"],
        "uhrzeit": uhrzeit,
        "sportart": sport,
        "titel": befehl["name"] or SPORT_LABEL[sport],
        "distanz_km": zahl(meter / 1000 if meter else None),
        "dauer_min": zahl(sekunden / 60 if sekunden else None, 1),
        "pace_min_km": pace(meter, sekunden) if sport in ("lauf", "trail") else "",
        "hf_avg_bpm": zahl(hf, 0),
        "hf_max_bpm": zahl(hfmax, 0),
        "hoehenmeter_m": zahl(hm, 0) if hm and hm > 0 else "",
        "schuh": "",
        "quelle": quelle,
        "quelle_id": str(raw.get("id") or befehl["source_id"]),
        "gefuehl": "",
    }

    zeilen = [f"# {felder['titel']}", ""]
    teile = [SPORT_LABEL[sport], befehl["date"]]
    if uhrzeit:
        teile.append(uhrzeit)
    if geraet:
        teile.append(f"aufgezeichnet mit {geraet}")
    elif quelle_raw:
        teile.append(f"Quelle {quelle_raw}")
    zeilen.append(" · ".join(teile) + ".")
    if sport == "sonstiges" and befehl["sport"] == "Workout":
        zeilen.append("Atemübung, keine Ausdauereinheit.")
    inhalt = "\n".join(zeilen) + "\n"
    return inhalt, felder


def kopf(felder: dict[str, str]) -> str:
    zeilen = ["---"]
    for key, wert in felder.items():
        if wert == "":
            zeilen.append(f"{key}:")
        elif re.fullmatch(r"[0-9]+([.,][0-9]+)?", str(wert)):
            zeilen.append(f"{key}: {wert}")
        else:
            sicher = str(wert).replace('"', "'")
            zeilen.append(f'{key}: "{sicher}"')
    zeilen.append("---")
    return "\n".join(zeilen) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default="~/Documents/Sport-Gehirn")
    parser.add_argument("--monate", type=int, default=12)
    parser.add_argument("--trocken", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    ziel = vault / "training"
    if not ziel.is_dir():
        print(f"Kein training/ unter {vault}")
        return 1

    seit = (date.today() - timedelta(days=args.monate * 30)).isoformat()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    befehle = conn.execute(
        "SELECT * FROM activity WHERE date >= ? ORDER BY start_local", (seit,)
    ).fetchall()

    bekannt = vorhandene_ids(vault)
    angelegt = 0
    uebersprungen = 0
    for befehl in befehle:
        inhalt, felder = note(befehl)
        if felder["quelle_id"] in bekannt:
            uebersprungen += 1
            continue
        stamm = f"{felder['datum']}-{felder['sportart']}-{slug(felder['titel'])}"
        datei = ziel / f"{stamm}.md"
        nummer = 2
        while datei.exists():
            datei = ziel / f"{stamm}-{nummer}.md"
            nummer += 1
        if not args.trocken:
            datei.write_text(kopf(felder) + "\n" + inhalt, encoding="utf-8")
        bekannt.add(felder["quelle_id"])
        angelegt += 1

    print(f"angelegt: {angelegt}, übersprungen: {uebersprungen}, gelesen: {len(befehle)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
