"""Domain models for Milestone 1.

The models intentionally use only the Python standard library so the decision
engine can be tested without a web framework or external service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import Iterable

from .timezone_utils import get_timezone


class TravelMode(StrEnum):
    WALK = "walk"
    DRIVE = "drive"
    TRANSIT = "transit"


class Leg(StrEnum):
    DEPARTURE = "departure"
    RETURN = "return"


class DecisionType(StrEnum):
    NOTIFY = "notify"
    NO_ACTION = "no_action"
    DATA_UNAVAILABLE = "data_unavailable"
    INACTIVE = "inactive"
    NOT_SCHEDULED = "not_scheduled"


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    user_id: str
    label: str
    latitude: float
    longitude: float
    timezone: str

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        get_timezone(self.timezone)


@dataclass(frozen=True, slots=True)
class Routine:
    id: str
    user_id: str
    name: str
    origin_location_id: str
    destination_location_id: str
    days_of_week: tuple[int, ...]
    departure_time: time
    return_time: time | None
    timezone: str
    travel_mode: TravelMode
    estimated_duration_minutes: int
    rain_probability_threshold: float
    precipitation_mm_threshold: float
    cold_apparent_temperature_c: float | None
    pre_alert_minutes: int
    active: bool = True

    def __post_init__(self) -> None:
        if not self.days_of_week or any(day < 0 or day > 6 for day in self.days_of_week):
            raise ValueError("days_of_week must contain ISO weekday values from 0 to 6")
        if tuple(sorted(set(self.days_of_week))) != self.days_of_week:
            raise ValueError("days_of_week must be sorted and unique")
        if not 0 <= self.rain_probability_threshold <= 1:
            raise ValueError("rain probability threshold must be between 0 and 1")
        if self.precipitation_mm_threshold < 0:
            raise ValueError("precipitation threshold cannot be negative")
        if self.estimated_duration_minutes <= 0:
            raise ValueError("estimated duration must be positive")
        if self.pre_alert_minutes < 0:
            raise ValueError("pre-alert minutes cannot be negative")
        get_timezone(self.timezone)


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    location_id: str
    valid_at: datetime
    source: str
    retrieved_at: datetime
    precipitation_probability: float
    precipitation_mm: float
    temperature_c: float
    apparent_temperature_c: float
    weather_code: str

    def __post_init__(self) -> None:
        if self.valid_at.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise ValueError("forecast timestamps must be timezone-aware")
        if not 0 <= self.precipitation_probability <= 1:
            raise ValueError("precipitation probability must be between 0 and 1")
        if self.precipitation_mm < 0:
            raise ValueError("precipitation cannot be negative")


@dataclass(frozen=True, slots=True)
class AlertDecision:
    routine_id: str
    leg: Leg
    occurrence_at: datetime
    evaluation_key: str
    decision_type: DecisionType
    should_notify: bool
    message: str
    reasons: tuple[str, ...]
    origin_forecast: ForecastPoint | None
    destination_forecast: ForecastPoint | None

    def __post_init__(self) -> None:
        if self.occurrence_at.tzinfo is None:
            raise ValueError("occurrence timestamp must be timezone-aware")
        if self.should_notify != (self.decision_type == DecisionType.NOTIFY):
            raise ValueError("should_notify must match decision_type")


def ensure_aware(value: datetime, timezone: str) -> datetime:
    """Return a timezone-aware datetime in the requested IANA timezone."""

    zone = get_timezone(timezone)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def utc_iso(value: datetime) -> str:
    """Serialize an aware datetime in UTC for persistence and stable keys."""

    if value.tzinfo is None:
        raise ValueError("UTC serialization requires an aware datetime")
    return value.astimezone(get_timezone("UTC")).isoformat().replace("+00:00", "Z")


def local_occurrence(date_value: date, local_time: time, timezone: str) -> datetime:
    """Build a local scheduled timestamp using a named timezone."""

    return datetime.combine(date_value, local_time, tzinfo=get_timezone(timezone))


def normalize_days(days: Iterable[int]) -> tuple[int, ...]:
    """Return sorted, unique ISO weekday values."""

    result = tuple(sorted(set(days)))
    if not result or any(day < 0 or day > 6 for day in result):
        raise ValueError("days must contain ISO weekday values from 0 to 6")
    return result
