"""Synthetic data used by tests and the offline demo.

All labels, coordinates, IDs, and email values are fictional.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from .models import ForecastPoint, Location, Routine, TravelMode
from .timezone_utils import get_timezone


DEMO_TIMEZONE = "America/New_York"
DEMO_DATE = date(2026, 9, 21)  # Monday


def demo_locations() -> tuple[Location, Location]:
    return (
        Location("loc-home-demo", "user-demo", "Synthetic Home", 40.7128, -74.0060, DEMO_TIMEZONE),
        Location("loc-work-demo", "user-demo", "Synthetic Work", 40.7306, -73.9866, DEMO_TIMEZONE),
    )


def demo_routine() -> Routine:
    return Routine(
        id="routine-demo-commute",
        user_id="user-demo",
        name="Weekday commute",
        origin_location_id="loc-home-demo",
        destination_location_id="loc-work-demo",
        days_of_week=(0, 1, 2, 3, 4),
        departure_time=time(8, 0),
        return_time=time(17, 0),
        timezone=DEMO_TIMEZONE,
        travel_mode=TravelMode.WALK,
        estimated_duration_minutes=30,
        rain_probability_threshold=0.40,
        precipitation_mm_threshold=0.5,
        cold_apparent_temperature_c=5.0,
        pre_alert_minutes=30,
    )


def demo_forecast_points(*, rainy: bool = True) -> tuple[ForecastPoint, ...]:
    zone = get_timezone(DEMO_TIMEZONE)
    retrieved_at = datetime(2026, 9, 20, 12, 0, tzinfo=zone)
    windows = (
        (time(8, 0), "loc-home-demo"),
        (time(8, 30), "loc-work-demo"),
        (time(17, 0), "loc-work-demo"),
        (time(17, 30), "loc-home-demo"),
    )
    points: list[ForecastPoint] = []
    for local_time, location_id in windows:
        valid_at = datetime.combine(DEMO_DATE, local_time, tzinfo=zone)
        points.append(
            ForecastPoint(
                location_id=location_id,
                valid_at=valid_at,
                source="synthetic-fixture",
                retrieved_at=retrieved_at,
                precipitation_probability=0.70 if rainy else 0.10,
                precipitation_mm=1.4 if rainy else 0.0,
                temperature_c=12.0 if rainy else 20.0,
                apparent_temperature_c=10.0 if rainy else 20.0,
                weather_code="rain" if rainy else "clear",
            )
        )
    return tuple(points)
