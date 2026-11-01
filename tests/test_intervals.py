from __future__ import annotations

import base64
import json
from datetime import date

import httpx
import respx

from trainings_cockpit.sources.intervals import IntervalsClient

BASE = "https://intervals.icu/api/v1"


def _auth_header(key: str) -> str:
    token = base64.b64encode(f"API_KEY:{key}".encode()).decode()
    return f"Basic {token}"


@respx.mock
def test_wellness_uses_basic_auth_and_date_range() -> None:
    route = respx.get(f"{BASE}/athlete/0/wellness").mock(
        return_value=httpx.Response(200, json=[{"id": "2026-10-01", "hrv": 62}])
    )

    with IntervalsClient("secret-key") as client:
        rows = client.wellness(date(2026, 9, 1), date(2026, 10, 1))

    assert rows == [{"id": "2026-10-01", "hrv": 62}]
    request = route.calls[0].request
    assert request.headers["authorization"] == _auth_header("secret-key")
    assert request.url.params["oldest"] == "2026-09-01"
    assert request.url.params["newest"] == "2026-10-01"
    assert "Mozilla" in request.headers["user-agent"]


@respx.mock
def test_upsert_events_is_idempotent_payload() -> None:
    route = respx.post(f"{BASE}/athlete/0/events/bulk").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "external_id": "tc:spike:2026-11-01"}])
    )
    event = {
        "category": "WORKOUT",
        "start_date_local": "2026-11-01T00:00:00",
        "type": "Ride",
        "name": "Test",
        "external_id": "tc:spike:2026-11-01",
    }

    with IntervalsClient("k") as client:
        created = client.upsert_events([event])

    assert created[0]["id"] == 1
    request = route.calls[0].request
    assert request.url.params["upsert"] == "true"
    assert json.loads(request.content) == [event]


@respx.mock
def test_rate_limit_waits_and_retries() -> None:
    sleeps: list[float] = []
    route = respx.get(f"{BASE}/athlete/0/wellness").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json=[]),
        ]
    )

    with IntervalsClient("k", sleep=sleeps.append) as client:
        assert client.wellness(date(2026, 1, 1), date(2026, 1, 2)) == []

    assert sleeps == [2.0]
    assert route.call_count == 2


@respx.mock
def test_401_has_clear_message() -> None:
    respx.get(f"{BASE}/athlete/0/wellness").mock(return_value=httpx.Response(401))
    with IntervalsClient("wrong") as client:
        try:
            client.wellness(date(2026, 1, 1), date(2026, 1, 2))
        except Exception as exc:  # noqa: BLE001
            assert "401" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Fehler erwartet")
