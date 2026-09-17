from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from weather_coach.fixtures import demo_locations
from weather_coach.provider import (
    OpenMeteoProvider,
    WeatherProviderError,
    normalize_open_meteo_hourly,
    weather_code_label,
)


class OpenMeteoProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.location = demo_locations()[0]
        self.start_at = datetime(2026, 9, 21, 8, tzinfo=timezone.utc)
        self.end_at = datetime(2026, 9, 21, 10, tzinfo=timezone.utc)
        self.retrieved_at = datetime(2026, 9, 21, 7, 45, tzinfo=timezone.utc)
        self.payload = {
            "latitude": 40.7128,
            "longitude": -74.006,
            "timezone": "UTC",
            "hourly": {
                "time": [
                    "2026-09-21T08:00",
                    "2026-09-21T09:00",
                    "2026-09-21T10:00",
                ],
                "temperature_2m": [18.0, 18.5, 19.0],
                "apparent_temperature": [17.2, 17.8, 18.4],
                "precipitation": [0.0, 1.2, 0.4],
                "precipitation_probability": [10, 70, 30],
                "weather_code": [1, 61, 95],
            },
        }

    def test_normalizes_bounded_hourly_response(self) -> None:
        points = normalize_open_meteo_hourly(
            self.payload,
            self.location,
            retrieved_at=self.retrieved_at,
            start_at=self.start_at,
            end_at=self.end_at,
        )

        self.assertEqual(len(points), 3)
        self.assertEqual(points[0].location_id, self.location.id)
        self.assertEqual(points[0].source, "open-meteo")
        self.assertEqual(points[0].valid_at, self.start_at)
        self.assertEqual(points[1].precipitation_probability, 0.70)
        self.assertEqual(points[1].weather_code, "rain")
        self.assertEqual(points[2].weather_code, "thunderstorm")
        self.assertEqual(points[1].retrieved_at, self.retrieved_at)

    def test_build_url_uses_utc_and_expected_hourly_variables(self) -> None:
        provider = OpenMeteoProvider()
        query = parse_qs(urlparse(provider.build_url(self.location, self.start_at, self.end_at)).query)

        self.assertEqual(query["timezone"], ["UTC"])
        self.assertEqual(query["start_hour"], ["2026-09-21T08:00"])
        self.assertEqual(query["end_hour"], ["2026-09-21T10:00"])
        self.assertIn("apparent_temperature", query["hourly"][0])
        self.assertIn("weather_code", query["hourly"][0])

    def test_fetch_uses_injected_transport_and_normalizes_json(self) -> None:
        requests: list[tuple[str, float]] = []

        def fake_transport(url: str, timeout_seconds: float) -> bytes:
            requests.append((url, timeout_seconds))
            return json.dumps(self.payload).encode("utf-8")

        provider = OpenMeteoProvider(
            transport=fake_transport,
            clock=lambda: self.retrieved_at,
            timeout_seconds=3.5,
        )
        points = provider.fetch_hourly(self.location, self.start_at, self.end_at)

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][1], 3.5)
        self.assertEqual(len(points), 3)

    def test_invalid_provider_error_is_explicit(self) -> None:
        error_payload = {"error": True, "reason": "invalid coordinates"}
        with self.assertRaisesRegex(WeatherProviderError, "invalid coordinates"):
            normalize_open_meteo_hourly(
                error_payload,
                self.location,
                retrieved_at=self.retrieved_at,
            )

    def test_inconsistent_arrays_are_rejected(self) -> None:
        invalid = {"hourly": {**self.payload["hourly"], "temperature_2m": [18.0]}}
        with self.assertRaisesRegex(WeatherProviderError, "inconsistent lengths"):
            normalize_open_meteo_hourly(
                invalid,
                self.location,
                retrieved_at=self.retrieved_at,
            )

    def test_wmo_codes_are_mapped_for_decision_engine(self) -> None:
        self.assertEqual(weather_code_label(0), "clear")
        self.assertEqual(weather_code_label(66), "ice")
        self.assertEqual(weather_code_label(75), "snow")
        self.assertEqual(weather_code_label(95), "thunderstorm")
        self.assertEqual(weather_code_label(999), "wmo_999")


if __name__ == "__main__":
    unittest.main()
