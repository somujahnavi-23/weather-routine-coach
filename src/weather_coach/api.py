"""Dependency-free JSON API core for routine management and evaluation.

The request dispatcher is framework-neutral so it can be tested without a web
framework. A later deployment can mount the same methods behind FastAPI or
another HTTP framework without changing the domain rules.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from .analytics import KNOWN_CONDITIONS, summarize_feedback
from .evaluator import evaluate_routine
from .models import DecisionType, Location, Routine, TravelMode, local_occurrence, utc_iso
from .notifications import NotificationDispatcher
from .provider import OpenMeteoProvider
from .repository import WeatherRepository


class ApiError(ValueError):
    """A client-safe API validation error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _require_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, f"'{field}' must be a non-empty string.")
    return value.strip()


def _optional_float(payload: Mapping[str, Any], field: str, default: float | None) -> float | None:
    value = payload.get(field, default)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ApiError(400, f"'{field}' must be numeric.")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, f"'{field}' must be numeric.") from exc


def _required_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool):
        raise ApiError(400, f"'{field}' must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, f"'{field}' must be an integer.") from exc


def _routine_dict(routine: Routine) -> dict[str, Any]:
    return {
        "id": routine.id,
        "user_id": routine.user_id,
        "name": routine.name,
        "origin_location_id": routine.origin_location_id,
        "destination_location_id": routine.destination_location_id,
        "days_of_week": list(routine.days_of_week),
        "departure_time": routine.departure_time.isoformat(),
        "return_time": routine.return_time.isoformat() if routine.return_time else None,
        "timezone": routine.timezone,
        "travel_mode": routine.travel_mode.value,
        "estimated_duration_minutes": routine.estimated_duration_minutes,
        "rain_probability_threshold": routine.rain_probability_threshold,
        "precipitation_mm_threshold": routine.precipitation_mm_threshold,
        "cold_apparent_temperature_c": routine.cold_apparent_temperature_c,
        "pre_alert_minutes": routine.pre_alert_minutes,
        "active": routine.active,
    }


def _decision_dict(decision: Any) -> dict[str, Any]:
    return {
        "routine_id": decision.routine_id,
        "leg": decision.leg.value,
        "occurrence_at": utc_iso(decision.occurrence_at),
        "evaluation_key": decision.evaluation_key,
        "decision_type": decision.decision_type.value,
        "should_notify": decision.should_notify,
        "message": decision.message,
        "reasons": list(decision.reasons),
    }


def _parse_date(payload: Mapping[str, Any], field: str = "occurrence_date") -> date:
    value = _require_string(payload, field)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(400, f"'{field}' must use YYYY-MM-DD format.") from exc


class WeatherApi:
    """Small request dispatcher for local routine management and evaluation."""

    def __init__(
        self,
        repository: WeatherRepository,
        provider: OpenMeteoProvider | None = None,
        dispatcher: NotificationDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.dispatcher = dispatcher

    def handle(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Return ``(status_code, JSON-ready payload)`` for one request."""

        try:
            return self._handle(method.upper(), path, body or {})
        except ApiError as exc:
            return exc.status_code, {"error": exc.message}

    def _handle(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any],
    ) -> tuple[int, dict[str, Any]]:
        parsed = urlsplit(path)
        route = tuple(part for part in parsed.path.split("/") if part)
        query = parse_qs(parsed.query)

        if method == "GET" and route == ("health",):
            return 200, {"status": "ok", "version": "0.5.0"}

        if method == "GET" and route == ("routines",):
            user_id_values = query.get("user_id", [])
            if not user_id_values or not user_id_values[0].strip():
                raise ApiError(400, "user_id query parameter is required.")
            routines = self.repository.routines(user_id_values[0].strip())
            return 200, {"routines": [_routine_dict(routine) for routine in routines]}

        if method == "POST" and route == ("routines",):
            routine = self._create_routine(body)
            if self.repository.location(routine.origin_location_id, routine.user_id) is None:
                raise ApiError(404, "origin location was not found for this user.")
            if self.repository.location(routine.destination_location_id, routine.user_id) is None:
                raise ApiError(404, "destination location was not found for this user.")
            self.repository.add_routine(routine)
            return 201, {"routine": _routine_dict(routine)}

        if method == "POST" and len(route) == 3 and route[0] == "routines" and route[2] == "evaluate":
            return self._evaluate(route[1], body)

        if method == "POST" and route == ("notifications", "enqueue"):
            if self.dispatcher is None:
                raise ApiError(503, "a notification dispatcher is required.")
            user_id = _require_string(body, "user_id") if "user_id" in body else None
            channel = body.get("channel", "test")
            if not isinstance(channel, str):
                raise ApiError(400, "channel must be a string.")
            created = self.dispatcher.enqueue(user_id, channel=channel)
            return 200, {"enqueued": created}

        if method == "POST" and route == ("notifications", "dispatch"):
            if self.dispatcher is None:
                raise ApiError(503, "a notification dispatcher is required.")
            user_id = _require_string(body, "user_id") if "user_id" in body else None
            results = self.dispatcher.dispatch_all(user_id)
            return 200, {
                "dispatched": len(results),
                "results": [
                    {
                        "outbox_id": result.outbox_id,
                        "alert_id": result.alert_id,
                        "status": result.status,
                        "attempts": result.attempts,
                        "error": result.error,
                    }
                    for result in results
                ],
            }

        if method == "POST" and len(route) == 3 and route[0] == "alerts" and route[2] == "feedback":
            return self._feedback(route[1], body)

        if method == "GET" and route == ("analytics",):
            user_id_values = query.get("user_id", [])
            if not user_id_values or not user_id_values[0].strip():
                raise ApiError(400, "user_id query parameter is required.")
            return 200, summarize_feedback(self.repository.feedback_for_user(user_id_values[0].strip()))

        raise ApiError(404, "route not found.")

    def _create_routine(self, payload: Mapping[str, Any]) -> Routine:
        user_id = _require_string(payload, "user_id")
        name = _require_string(payload, "name")
        days = payload.get("days_of_week")
        if not isinstance(days, list) or not days or any(isinstance(day, bool) for day in days):
            raise ApiError(400, "days_of_week must be a non-empty list of integers.")
        try:
            normalized_days = tuple(sorted(set(int(day) for day in days)))
        except (TypeError, ValueError) as exc:
            raise ApiError(400, "days_of_week must be a non-empty list of integers.") from exc
        if any(day < 0 or day > 6 for day in normalized_days):
            raise ApiError(400, "days_of_week values must be between 0 and 6.")

        try:
            departure_time = time.fromisoformat(_require_string(payload, "departure_time"))
            return_value = payload.get("return_time")
            return_time = time.fromisoformat(return_value) if return_value else None
            travel_mode = TravelMode(_require_string(payload, "travel_mode"))
        except (ValueError, TypeError) as exc:
            raise ApiError(400, "time and travel_mode values are invalid.") from exc

        rain_probability_threshold = _optional_float(payload, "rain_probability_threshold", 0.4)
        precipitation_mm_threshold = _optional_float(payload, "precipitation_mm_threshold", 0.5)
        if rain_probability_threshold is None or precipitation_mm_threshold is None:
            raise ApiError(400, "rain_probability_threshold and precipitation_mm_threshold are required.")

        try:
            routine = Routine(
                id=str(payload.get("id") or f"routine-{uuid4().hex}"),
                user_id=user_id,
                name=name,
                origin_location_id=_require_string(payload, "origin_location_id"),
                destination_location_id=_require_string(payload, "destination_location_id"),
                days_of_week=normalized_days,
                departure_time=departure_time,
                return_time=return_time,
                timezone=_require_string(payload, "timezone"),
                travel_mode=travel_mode,
                estimated_duration_minutes=_required_int(payload, "estimated_duration_minutes"),
                rain_probability_threshold=rain_probability_threshold,
                precipitation_mm_threshold=precipitation_mm_threshold,
                cold_apparent_temperature_c=_optional_float(payload, "cold_apparent_temperature_c", None),
                pre_alert_minutes=_required_int(payload, "pre_alert_minutes"),
                active=bool(payload.get("active", True)),
            )
        except (TypeError, ValueError) as exc:
            raise ApiError(400, f"invalid routine: {exc}") from exc
        return routine

    def _feedback(self, alert_id_value: str, payload: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            alert_id = int(alert_id_value)
        except ValueError as exc:
            raise ApiError(400, "alert ID must be an integer.") from exc
        user_id = _require_string(payload, "user_id")
        helpful = payload.get("helpful")
        if helpful is not None and not isinstance(helpful, bool):
            raise ApiError(400, "helpful must be true, false, or null.")
        actual_condition = payload.get("actual_condition")
        if actual_condition is not None:
            if not isinstance(actual_condition, str) or actual_condition.strip().lower() not in KNOWN_CONDITIONS:
                raise ApiError(400, "actual_condition must be a supported weather condition.")
            actual_condition = actual_condition.strip().lower()
        notes = payload.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ApiError(400, "notes must be a string or null.")
        try:
            feedback_id = self.repository.add_feedback(
                alert_id,
                user_id,
                helpful=helpful,
                actual_condition=actual_condition,
                notes=notes,
            )
        except ValueError as exc:
            raise ApiError(404 if "not found" in str(exc) else 400, str(exc)) from exc
        return 201, {"feedback_id": feedback_id, "alert_id": alert_id}

    def _evaluate(self, routine_id: str, payload: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        user_id = _require_string(payload, "user_id")
        routine = self.repository.routine(routine_id, user_id)
        if routine is None:
            raise ApiError(404, "routine was not found for this user.")
        occurrence_date = _parse_date(payload)
        if self.provider is None:
            raise ApiError(503, "a weather provider is required for evaluation.")
        origin = self.repository.location(routine.origin_location_id, user_id)
        destination = self.repository.location(routine.destination_location_id, user_id)
        if origin is None or destination is None:
            raise ApiError(500, "routine locations are not available.")

        local_start = local_occurrence(occurrence_date, routine.departure_time, routine.timezone)
        end_time = routine.return_time or routine.departure_time
        local_end = local_occurrence(occurrence_date, end_time, routine.timezone) + timedelta(
            minutes=routine.estimated_duration_minutes
        )
        origin_points = self.provider.fetch_hourly(origin, local_start, local_end)
        destination_points = self.provider.fetch_hourly(destination, local_start, local_end)
        forecast_points = origin_points + destination_points
        self.repository.add_forecast_points(forecast_points)
        decisions = evaluate_routine(routine, occurrence_date, forecast_points, self.repository)
        return 200, {
            "routine_id": routine.id,
            "occurrence_date": occurrence_date.isoformat(),
            "decisions": [_decision_dict(decision) for decision in decisions],
            "notification_count": sum(
                decision.decision_type == DecisionType.NOTIFY for decision in decisions
            ),
        }


def json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize an API response for an HTTP adapter."""

    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
