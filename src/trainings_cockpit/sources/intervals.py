"""Client für die intervals.icu REST-API.

Dokumentation: https://intervals.icu/api-docs.html
Authentifizierung: HTTP Basic, Benutzername "API_KEY", Passwort = API-Key.
Die Athleten-ID "0" steht für den Athleten, dem der Key gehört.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class IntervalsError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


#: Felder, die der Sync ablegt oder später auswertet (Zonen, Gear, Quelle).
ACTIVITY_FIELDS = ",".join(
    [
        "id",
        "start_date_local",
        "type",
        "name",
        "distance",
        "moving_time",
        "elapsed_time",
        "average_heartrate",
        "max_heartrate",
        "total_elevation_gain",
        "icu_training_load",
        "icu_intensity",
        "icu_hr_zone_times",
        "icu_lap_count",
        "average_cadence",
        "decoupling",
        "source",
        "device_name",
        "gear",
    ]
)


class IntervalsClient:
    def __init__(
        self,
        api_key: str,
        athlete_id: str = "0",
        base_url: str = "https://intervals.icu/api/v1",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise IntervalsError("Kein intervals.icu API-Key konfiguriert.")
        self.athlete_id = athlete_id or "0"
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=httpx.BasicAuth("API_KEY", api_key),
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    # ------------------------------------------------------------------ HTTP

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        retries: int = 2,
    ) -> Any:
        last_error: IntervalsError | None = None
        for attempt in range(retries + 1):
            response = self._client.request(method, path, params=params, json=json)
            if response.status_code == 429:
                wait = _retry_after_seconds(response, default=60)
                last_error = IntervalsError(
                    f"Rate Limit erreicht ({method} {path}). "
                    f"Warte {wait:.0f} s und versuche es erneut.",
                    status_code=429,
                )
                if attempt < retries:
                    self._sleep(min(wait, 120))
                    continue
                raise last_error
            if response.status_code == 401:
                raise IntervalsError(
                    "intervals.icu lehnt den API-Key ab (401). "
                    "Key in Settings → Developer prüfen.",
                    status_code=401,
                )
            if response.status_code == 403:
                raise IntervalsError(
                    f"Kein Zugriff (403) auf {path}. Athleten-ID prüfen.",
                    status_code=403,
                )
            if response.status_code >= 400:
                raise IntervalsError(
                    f"{method} {path} → HTTP {response.status_code}: "
                    f"{response.text[:300]}",
                    status_code=response.status_code,
                )
            if not response.content:
                return None
            return response.json()
        raise last_error or IntervalsError("Unbekannter Fehler")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> IntervalsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -------------------------------------------------------------- Endpunkte

    def athlete(self) -> dict[str, Any]:
        return self._request("GET", f"/athlete/{self.athlete_id}")

    def activities(self, oldest: date, newest: date) -> list[dict[str, Any]]:
        # Ohne fields liefert intervals je Einheit rund 40 Felder (Kadenz,
        # Wetter, Bodenkontakt, Vertikalverhältnis …). Ein Jahr sind dann 1,3 MB
        # statt 100 KB. Hier steht nur, was wir wirklich ablegen oder auswerten.
        return self._request(
            "GET",
            f"/athlete/{self.athlete_id}/activities",
            params={
                "oldest": oldest.isoformat(),
                "newest": newest.isoformat(),
                "fields": ACTIVITY_FIELDS,
            },
        )

    def wellness(self, oldest: date, newest: date) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/athlete/{self.athlete_id}/wellness",
            params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
        )

    def events(
        self,
        oldest: date,
        newest: date,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "oldest": oldest.isoformat(),
            "newest": newest.isoformat(),
        }
        if category:
            params["category"] = category
        return self._request("GET", f"/athlete/{self.athlete_id}/events", params=params)

    def event(self, event_id: int) -> dict[str, Any]:
        return self._request("GET", f"/athlete/{self.athlete_id}/events/{event_id}")

    def update_event(self, event_id: int, event: dict[str, Any]) -> dict[str, Any]:
        """Aktualisiert genau ein bestehendes Event über seine Event-ID.

        Ein 404 wird als :class:`IntervalsError` mit ``status_code=404``
        weitergereicht; der Aufrufer legt daraus kein neues Event an.
        """
        return self._request(
            "PUT",
            f"/athlete/{self.athlete_id}/events/{event_id}",
            json=event,
        )

    def sport_settings(self) -> list[dict[str, Any]]:
        return self._request("GET", f"/athlete/{self.athlete_id}/sport-settings")

    def activity(self, activity_id: str, intervals: bool = True) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/activity/{activity_id}",
            params={"intervals": str(intervals).lower()},
        )

    def streams(self, activity_id: str) -> list[dict[str, Any]]:
        """Sekundenwerte einer Einheit — Sekunde für Sekunde, wie aufgezeichnet.

        Nicht jede Einheit hat welche: was ohne Aufzeichnung in intervals landete,
        liefert eine leere Liste. Das ist kein Fehler, sondern ein Befund.
        """
        payload = self._request("GET", f"/activity/{activity_id}/streams")
        return payload if isinstance(payload, list) else []

    def upsert_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Idempotentes Anlegen/Aktualisieren über external_id."""
        return self._request(
            "POST",
            f"/athlete/{self.athlete_id}/events/bulk",
            params={"upsert": "true"},
            json=events,
        )

    def delete_events(self, refs: list[dict[str, Any]]) -> int:
        return self._request(
            "PUT",
            f"/athlete/{self.athlete_id}/events/bulk-delete",
            json=refs,
        )

    def create_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/athlete/{self.athlete_id}/events",
            json=event,
        )


def date_range(days: int, today: date | None = None) -> tuple[date, date]:
    end = today or date.today()
    return end - timedelta(days=max(days, 1)), end


def _retry_after_seconds(response: httpx.Response, default: float = 60.0) -> float:
    raw = response.headers.get("Retry-After")
    if not raw:
        return default
    try:
        return max(float(raw), 1.0)
    except ValueError:
        return default
