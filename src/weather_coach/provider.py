"""Open-Meteo forecast adapter with explicit normalization and error handling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import ForecastPoint, Location


DEFAULT_OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


class WeatherProviderError(RuntimeError):
    """Raised when a weather provider cannot return a valid forecast."""


def _http_get(url: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "weather-routine-coach/0.2",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _as_float(value: Any, field: str, index: int) -> float:
    if value is None or isinstance(value, bool):
        raise WeatherProviderError(f"Open-Meteo field '{field}' is null at index {index}.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise WeatherProviderError(
            f"Open-Meteo field '{field}' is not numeric at index {index}."
        ) from exc


def _as_int(value: Any, field: str, index: int) -> int:
    if value is None or isinstance(value, bool):
        raise WeatherProviderError(f"Open-Meteo field '{field}' is null at index {index}.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise WeatherProviderError(
            f"Open-Meteo field '{field}' is not an integer at index {index}."
        ) from exc


def _parse_utc_timestamp(value: Any, index: int) -> datetime:
    if not isinstance(value, str):
        raise WeatherProviderError(f"Open-Meteo timestamp is invalid at index {index}.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WeatherProviderError(
            f"Open-Meteo timestamp is invalid at index {index}: {value!r}."
        ) from exc
    if parsed.tzinfo is None:
        # The adapter requests timezone=UTC, whose hourly values are ISO strings
        # without an explicit suffix.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def weather_code_label(code: int) -> str:
    """Map an Open-Meteo WMO weather code to the domain vocabulary."""

    if code == 0:
        return "clear"
    if code in {1, 2, 3}:
        return "cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57}:
        return "ice" if code in {56, 57} else "drizzle"
    if code in {61, 63, 65, 80, 81, 82}:
        return "rain" if code in {61, 63, 65} else "showers"
    if code in {66, 67}:
        return "ice"
    if code in {71, 73, 75, 77}:
        return "snow"
    if code in {85, 86}:
        return "snow_showers"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return f"wmo_{code}"


def _validate_hourly_arrays(hourly: Mapping[str, Any]) -> int:
    required_fields = (
        "time",
        "temperature_2m",
        "apparent_temperature",
        "precipitation",
        "precipitation_probability",
        "weather_code",
    )
    missing = [field for field in required_fields if field not in hourly]
    if missing:
        raise WeatherProviderError(
            "Open-Meteo response is missing hourly fields: " + ", ".join(missing) + "."
        )

    lengths: dict[str, int] = {}
    for field in required_fields:
        values = hourly[field]
        if not isinstance(values, list):
            raise WeatherProviderError(f"Open-Meteo hourly field '{field}' must be a list.")
        lengths[field] = len(values)
    if len(set(lengths.values())) != 1:
        raise WeatherProviderError(
            "Open-Meteo hourly fields have inconsistent lengths: "
            + ", ".join(f"{field}={length}" for field, length in lengths.items())
            + "."
        )
    return lengths["time"]


def normalize_open_meteo_hourly(
    payload: Mapping[str, Any],
    location: Location,
    *,
    retrieved_at: datetime,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> tuple[ForecastPoint, ...]:
    """Normalize an Open-Meteo hourly response into domain forecast points."""

    if payload.get("error") is True:
        reason = payload.get("reason", "unknown provider error")
        raise WeatherProviderError(f"Open-Meteo returned an error: {reason}")
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping):
        raise WeatherProviderError("Open-Meteo response does not contain an hourly object.")

    total = _validate_hourly_arrays(hourly)
    retrieved_utc = retrieved_at.astimezone(timezone.utc) if retrieved_at.tzinfo else retrieved_at.replace(tzinfo=timezone.utc)
    if (start_at is None) != (end_at is None):
        raise ValueError("start_at and end_at must be provided together")
    if start_at is not None and (start_at.tzinfo is None or end_at is None or end_at.tzinfo is None):
        raise ValueError("forecast window timestamps must be timezone-aware")
    start_utc = start_at.astimezone(timezone.utc) if start_at else None
    end_utc = end_at.astimezone(timezone.utc) if end_at else None
    if start_utc and end_utc and end_utc < start_utc:
        raise ValueError("end_at must not be earlier than start_at")

    points: list[ForecastPoint] = []
    for index in range(total):
        valid_at = _parse_utc_timestamp(hourly["time"][index], index)
        if start_utc and valid_at < start_utc:
            continue
        if end_utc and valid_at > end_utc:
            continue

        precipitation_probability_percent = _as_float(
            hourly["precipitation_probability"][index], "precipitation_probability", index
        )
        if not 0 <= precipitation_probability_percent <= 100:
            raise WeatherProviderError(
                "Open-Meteo precipitation probability must be between 0 and 100 "
                f"at index {index}."
            )
        precipitation_mm = _as_float(hourly["precipitation"][index], "precipitation", index)
        if precipitation_mm < 0:
            raise WeatherProviderError(
                f"Open-Meteo precipitation cannot be negative at index {index}."
            )

        weather_code = _as_int(hourly["weather_code"][index], "weather_code", index)
        points.append(
            ForecastPoint(
                location_id=location.id,
                valid_at=valid_at,
                source="open-meteo",
                retrieved_at=retrieved_utc,
                precipitation_probability=precipitation_probability_percent / 100,
                precipitation_mm=precipitation_mm,
                temperature_c=_as_float(hourly["temperature_2m"][index], "temperature_2m", index),
                apparent_temperature_c=_as_float(
                    hourly["apparent_temperature"][index], "apparent_temperature", index
                ),
                weather_code=weather_code_label(weather_code),
            )
        )
    return tuple(points)


class OpenMeteoProvider:
    """Fetch and normalize hourly forecasts from Open-Meteo."""

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_OPEN_METEO_ENDPOINT,
        timeout_seconds: float = 10.0,
        transport: Callable[[str, float], bytes] = _http_get,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.clock = clock

    def build_url(self, location: Location, start_at: datetime, end_at: datetime) -> str:
        if start_at.tzinfo is None or end_at.tzinfo is None:
            raise ValueError("forecast window timestamps must be timezone-aware")
        start_utc = start_at.astimezone(timezone.utc)
        end_utc = end_at.astimezone(timezone.utc)
        if end_utc < start_utc:
            raise ValueError("end_at must not be earlier than start_at")
        params = {
            "latitude": f"{location.latitude:.6f}",
            "longitude": f"{location.longitude:.6f}",
            "hourly": "temperature_2m,apparent_temperature,precipitation,precipitation_probability,weather_code",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "timezone": "UTC",
            "start_hour": start_utc.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end_utc.strftime("%Y-%m-%dT%H:%M"),
        }
        return f"{self.endpoint}?{urlencode(params)}"

    def fetch_hourly(
        self,
        location: Location,
        start_at: datetime,
        end_at: datetime,
    ) -> tuple[ForecastPoint, ...]:
        """Fetch a bounded UTC window for one location."""

        url = self.build_url(location, start_at, end_at)
        try:
            raw_payload = self.transport(url, self.timeout_seconds)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise WeatherProviderError(f"Open-Meteo request failed: {exc}") from exc
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WeatherProviderError("Open-Meteo returned invalid JSON.") from exc
        if not isinstance(payload, Mapping):
            raise WeatherProviderError("Open-Meteo response must be a JSON object.")
        return normalize_open_meteo_hourly(
            payload,
            location,
            retrieved_at=self.clock(),
            start_at=start_at,
            end_at=end_at,
        )
