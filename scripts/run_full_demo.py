"""Run the complete deterministic local product-flow demonstration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weather_coach.api import WeatherApi  # noqa: E402
from weather_coach.fixtures import demo_forecast_points, demo_locations, demo_routine  # noqa: E402
from weather_coach.notifications import NotificationDispatcher, TestNotificationSink  # noqa: E402
from weather_coach.repository import WeatherRepository  # noqa: E402


class DemoProvider:
    """Provider-shaped adapter that serves the deterministic synthetic fixture."""

    def fetch_hourly(self, location, start_at, end_at):
        return tuple(point for point in demo_forecast_points() if point.location_id == location.id)


def main() -> None:
    repository = WeatherRepository.in_memory()
    repository.add_user("user-demo", "demo@example.invalid")
    for location in demo_locations():
        repository.add_location(location)

    routine = demo_routine()
    sink = TestNotificationSink()
    dispatcher = NotificationDispatcher(repository, sink)
    api = WeatherApi(repository, DemoProvider(), dispatcher)
    routine_payload = {
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

    create_status, _ = api.handle("POST", "/routines", routine_payload)
    evaluate_status, evaluate_payload = api.handle(
        "POST",
        f"/routines/{routine.id}/evaluate",
        {"user_id": routine.user_id, "occurrence_date": "2026-09-21"},
    )
    dispatch_status, dispatch_payload = api.handle(
        "POST", "/notifications/dispatch", {"user_id": routine.user_id}
    )

    alert_ids = [
        row["id"]
        for row in repository.connection.execute("SELECT id FROM alerts ORDER BY id").fetchall()
    ]
    for alert_id in alert_ids:
        api.handle(
            "POST",
            f"/alerts/{alert_id}/feedback",
            {"user_id": routine.user_id, "helpful": True, "actual_condition": "rain"},
        )
    analytics_status, analytics_payload = api.handle(
        "GET", "/analytics?user_id=user-demo"
    )

    print("Weather Routine Coach - complete local demo")
    print(f"routine_create_status={create_status} evaluation_status={evaluate_status} decisions={len(evaluate_payload['decisions'])}")
    print(f"notification_status={dispatch_status} dispatched={dispatch_payload['dispatched']} sink_messages={len(sink.messages)}")
    print(f"feedback_status={analytics_status} metrics={analytics_payload}")
    print(
        f"forecast_points={repository.count('forecast_points')} evaluations={repository.count('evaluations')} "
        f"alerts={repository.count('alerts')} outbox={repository.count('notification_outbox')} feedback={repository.count('feedback')}"
    )
    repository.close()


if __name__ == "__main__":
    main()
