"""Explainable, deterministic weather decision rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Iterable

from .models import (
    AlertDecision,
    DecisionType,
    ForecastPoint,
    Leg,
    Routine,
    ensure_aware,
    utc_iso,
)


SEVERE_WEATHER_CODES = frozenset(
    {
        "thunderstorm",
        "tornado",
        "hurricane",
        "blizzard",
        "ice",
    }
)


def evaluation_key(routine_id: str, leg: Leg, occurrence_at: datetime) -> str:
    """Create a stable key that makes scheduler retries safe."""

    raw = f"{routine_id}|{leg.value}|{utc_iso(occurrence_at)}"
    return sha256(raw.encode("utf-8")).hexdigest()[:32]


def closest_forecast(
    points: Iterable[ForecastPoint],
    location_id: str,
    target_at: datetime,
    *,
    max_distance: timedelta = timedelta(hours=2),
) -> ForecastPoint | None:
    """Choose the closest forecast point for a location and target time."""

    candidates = [
        point
        for point in points
        if point.location_id == location_id and abs(point.valid_at - target_at) <= max_distance
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda point: abs(point.valid_at - target_at))


def _format_percent(value: float) -> str:
    return f"{round(value * 100):.0f}%"


def evaluate_leg(
    routine: Routine,
    leg: Leg,
    occurrence_at: datetime,
    forecast_points: Iterable[ForecastPoint],
) -> AlertDecision:
    """Evaluate one commute leg using origin and destination hourly forecasts."""

    local_occurrence_at = ensure_aware(occurrence_at, routine.timezone)
    if leg == Leg.DEPARTURE:
        origin_id = routine.origin_location_id
        destination_id = routine.destination_location_id
    else:
        origin_id = routine.destination_location_id
        destination_id = routine.origin_location_id

    arrival_at = local_occurrence_at + timedelta(minutes=routine.estimated_duration_minutes)
    point_list = tuple(forecast_points)
    origin_forecast = closest_forecast(point_list, origin_id, local_occurrence_at)
    destination_forecast = closest_forecast(point_list, destination_id, arrival_at)
    key = evaluation_key(routine.id, leg, local_occurrence_at)

    if origin_forecast is None or destination_forecast is None:
        missing = []
        if origin_forecast is None:
            missing.append("departure location")
        if destination_forecast is None:
            missing.append("arrival location")
        return AlertDecision(
            routine_id=routine.id,
            leg=leg,
            occurrence_at=local_occurrence_at,
            evaluation_key=key,
            decision_type=DecisionType.DATA_UNAVAILABLE,
            should_notify=False,
            message="Weather data is unavailable for " + " and ".join(missing) + ".",
            reasons=("A required forecast point was not available within the evaluation window.",),
            origin_forecast=origin_forecast,
            destination_forecast=destination_forecast,
        )

    reasons: list[str] = []
    forecast_pair = (
        ("departure location", origin_forecast),
        ("arrival location", destination_forecast),
    )

    for label, point in forecast_pair:
        if point.precipitation_probability >= routine.rain_probability_threshold:
            reasons.append(
                f"{_format_percent(point.precipitation_probability)} rain probability at the {label} "
                f"meets the {_format_percent(routine.rain_probability_threshold)} threshold."
            )
        if point.precipitation_mm >= routine.precipitation_mm_threshold and point.precipitation_mm > 0:
            reasons.append(
                f"{point.precipitation_mm:.1f} mm precipitation is forecast at the {label}, "
                f"meeting the {routine.precipitation_mm_threshold:.1f} mm threshold."
            )
        if routine.cold_apparent_temperature_c is not None and (
            point.apparent_temperature_c <= routine.cold_apparent_temperature_c
        ):
            reasons.append(
                f"Feels-like temperature at the {label} is {point.apparent_temperature_c:.1f}°C, "
                f"at or below the {routine.cold_apparent_temperature_c:.1f}°C cold threshold."
            )
        if point.weather_code in SEVERE_WEATHER_CODES:
            reasons.append(f"Severe weather code '{point.weather_code}' is forecast at the {label}.")

    if not reasons:
        return AlertDecision(
            routine_id=routine.id,
            leg=leg,
            occurrence_at=local_occurrence_at,
            evaluation_key=key,
            decision_type=DecisionType.NO_ACTION,
            should_notify=False,
            message="No weather action is needed for this routine window.",
            reasons=("No configured weather rule was triggered.",),
            origin_forecast=origin_forecast,
            destination_forecast=destination_forecast,
        )

    forecasts = (origin_forecast, destination_forecast)
    rain_triggered = any(
        point.precipitation_probability >= routine.rain_probability_threshold
        or point.precipitation_mm >= routine.precipitation_mm_threshold
        for point in forecasts
    )
    cold_triggered = routine.cold_apparent_temperature_c is not None and any(
        point.apparent_temperature_c <= routine.cold_apparent_temperature_c
        for point in forecasts
    )
    if rain_triggered and cold_triggered:
        action = "carry an umbrella or rain layer and dress warmly"
    elif rain_triggered:
        action = "carry an umbrella or rain layer"
    elif cold_triggered:
        action = "dress warmly"
    else:
        action = "check the route before leaving"

    leg_label = "outbound" if leg == Leg.DEPARTURE else "return"
    message = f"{routine.name} {leg_label}: {action}. " + " ".join(reasons)
    return AlertDecision(
        routine_id=routine.id,
        leg=leg,
        occurrence_at=local_occurrence_at,
        evaluation_key=key,
        decision_type=DecisionType.NOTIFY,
        should_notify=True,
        message=message,
        reasons=tuple(reasons),
        origin_forecast=origin_forecast,
        destination_forecast=destination_forecast,
    )
