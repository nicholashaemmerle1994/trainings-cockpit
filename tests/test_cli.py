from __future__ import annotations

from datetime import date, timedelta

from trainings_cockpit import cli, db


def _night(day: date) -> dict:
    return {
        "id": day.isoformat(),
        "hrv": 30,
        "restingHR": 56,
        "sleepSecs": 8 * 3600,
        "awakeSleepSeconds": 20 * 60,
        "respiration": 14,
    }


def test_baseline_zaehlt_nur_das_60_tage_fenster(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))
    conn = db.connect(tmp_path / "cockpit.db")
    db.init_db(conn)
    old = date.today() - timedelta(days=100)
    db.upsert_wellness(conn, [_night(old + timedelta(days=index)) for index in range(6)])
    db.set_wellness_epoch(conn, old)
    conn.close()

    assert cli.main(["baseline"]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "0 Nächte mit Signal" in out
    assert "Referenz wird aufgebaut" in out

    conn = db.connect(tmp_path / "cockpit.db")
    recent = date.today() - timedelta(days=5)
    db.upsert_wellness(conn, [_night(recent + timedelta(days=index)) for index in range(6)])
    conn.close()

    assert cli.main(["baseline"]) == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "6 Nächte mit Signal" in out
    assert "Referenz steht" in out
