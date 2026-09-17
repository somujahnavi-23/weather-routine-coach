from __future__ import annotations

import unittest

from weather_coach.api import WeatherApi
from weather_coach.fixtures import demo_forecast_points, demo_locations, demo_routine
from weather_coach.notifications import NotificationDispatcher, TestNotificationSink
from weather_coach.repository import WeatherRepository


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_hourly(self, location, start_at, end_at):
        self.calls.append(location.id)
        return tuple(point for point in demo_forecast_points() if point.location_id == location.id)


class WeatherApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = WeatherRepository.in_memory()
        self.repository.add_user("user-demo", "demo@example.invalid")
        for location in demo_locations():
            self.repository.add_location(location)
        self.provider = FakeProvider()
        self.sink = TestNotificationSink()
        self.dispatcher = NotificationDispatcher(self.repository, self.sink)
        self.api = WeatherApi(self.repository, self.provider, self.dispatcher)

    def tearDown(self) -> None:
        self.repository.close()

    def test_health_route_is_available(self) -> None:
        status, payload = self.api.handle("GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_create_and_list_routine(self) -> None:
        routine = demo_routine()
        payload = {
            "id": routine.id,
            "user_id": routine.user_id,
            "name": routine.name,
            "origin_location_id": routine.origin_location_id,
            "destination_location_id": routine.destination_location_id,
            "days_of_week": list(routine.days_of_week),
            "departure_time": routine.departure_time.isoformat(),
            "return_time": routine.return_time.isoformat(),
            "timezone": routine.timezone,
            "travel_mode": routine.travel_mode.value,
            "estimated_duration_minutes": routine.estimated_duration_minutes,
            "rain_probability_threshold": routine.rain_probability_threshold,
            "precipitation_mm_threshold": routine.precipitation_mm_threshold,
            "cold_apparent_temperature_c": routine.cold_apparent_temperature_c,
            "pre_alert_minutes": routine.pre_alert_minutes,
        }

        create_status, create_payload = self.api.handle("POST", "/routines", payload)
        list_status, list_payload = self.api.handle("GET", "/routines?user_id=user-demo")

        self.assertEqual(create_status, 201)
        self.assertEqual(create_payload["routine"]["id"], routine.id)
        self.assertEqual(list_status, 200)
        self.assertEqual(len(list_payload["routines"]), 1)

    def test_evaluate_route_fetches_both_locations_and_persists_decisions(self) -> None:
        routine = demo_routine()
        self.repository.add_routine(routine)

        status, payload = self.api.handle(
            "POST",
            f"/routines/{routine.id}/evaluate",
            {"user_id": routine.user_id, "occurrence_date": "2026-09-21"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(len(self.provider.calls), 2)
        self.assertEqual(payload["notification_count"], 2)
        self.assertEqual(len(payload["decisions"]), 2)
        self.assertEqual(self.repository.count("evaluations"), 2)
        self.assertEqual(self.repository.count("alerts"), 2)

    def test_missing_user_is_rejected_without_leaking_routines(self) -> None:
        status, payload = self.api.handle("GET", "/routines")

        self.assertEqual(status, 400)
        self.assertIn("user_id", payload["error"])

    def test_notification_feedback_and_analytics_routes(self) -> None:
        routine = demo_routine()
        self.repository.add_routine(routine)
        self.api.handle(
            "POST",
            f"/routines/{routine.id}/evaluate",
            {"user_id": routine.user_id, "occurrence_date": "2026-09-21"},
        )

        enqueue_status, enqueue_payload = self.api.handle(
            "POST", "/notifications/enqueue", {"user_id": "user-demo"}
        )
        dispatch_status, dispatch_payload = self.api.handle(
            "POST", "/notifications/dispatch", {"user_id": "user-demo"}
        )
        alert_id = self.repository.connection.execute("SELECT id FROM alerts ORDER BY id LIMIT 1").fetchone()["id"]
        feedback_status, feedback_payload = self.api.handle(
            "POST",
            f"/alerts/{alert_id}/feedback",
            {"user_id": "user-demo", "helpful": True, "actual_condition": "rain"},
        )
        analytics_status, analytics_payload = self.api.handle(
            "GET", "/analytics?user_id=user-demo"
        )

        self.assertEqual(enqueue_status, 200)
        self.assertEqual(enqueue_payload["enqueued"], 2)
        self.assertEqual(dispatch_status, 200)
        self.assertEqual(dispatch_payload["dispatched"], 2)
        self.assertEqual(len(self.sink.messages), 2)
        self.assertEqual(feedback_status, 201)
        self.assertEqual(feedback_payload["alert_id"], alert_id)
        self.assertEqual(analytics_status, 200)
        self.assertEqual(analytics_payload["feedback_count"], 1)
        self.assertEqual(analytics_payload["helpful_rate"], 1.0)
        self.assertEqual(analytics_payload["outcome_accuracy"], 1.0)

    def test_missing_provider_is_reported_as_service_unavailable(self) -> None:
        api_without_provider = WeatherApi(self.repository)
        routine = demo_routine()
        self.repository.add_routine(routine)

        status, payload = api_without_provider.handle(
            "POST",
            f"/routines/{routine.id}/evaluate",
            {"user_id": routine.user_id, "occurrence_date": "2026-09-21"},
        )

        self.assertEqual(status, 503)
        self.assertIn("weather provider", payload["error"])

    def test_invalid_routine_threshold_returns_client_error(self) -> None:
        status, payload = self.api.handle(
            "POST",
            "/routines",
            {
                "user_id": "user-demo",
                "name": "Bad routine",
                "origin_location_id": "loc-home-demo",
                "destination_location_id": "loc-work-demo",
                "days_of_week": [0],
                "departure_time": "08:00",
                "return_time": None,
                "timezone": "America/New_York",
                "travel_mode": "walk",
                "estimated_duration_minutes": 30,
                "rain_probability_threshold": None,
                "precipitation_mm_threshold": 0.5,
                "pre_alert_minutes": 30,
            },
        )

        self.assertEqual(status, 400)
        self.assertIn("threshold", payload["error"])


if __name__ == "__main__":
    unittest.main()
