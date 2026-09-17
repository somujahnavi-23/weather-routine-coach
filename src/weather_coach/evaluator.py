"""Routine occurrence orchestration around the pure decision engine."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable

from .decision_engine import evaluate_leg
from .models import (
    AlertDecision,
    DecisionType,
    ForecastPoint,
    Leg,
    Routine,
    local_occurrence,
)
from .repository import WeatherRepository


def _evaluate_one(
    routine: Routine,
    leg: Leg,
    occurrence_date: date,
    occurrence_time: time,
    forecast_points: Iterable[ForecastPoint],
) -> AlertDecision:
    occurrence_at = local_occurrence(occurrence_date, occurrence_time, routine.timezone)
    return evaluate_leg(routine, leg, occurrence_at, forecast_points)


def evaluate_routine(
    routine: Routine,
    occurrence_date: date,
    forecast_points: Iterable[ForecastPoint],
    repository: WeatherRepository | None = None,
) -> tuple[AlertDecision, ...]:
    """Evaluate all scheduled legs for a local calendar date.

    A date outside the routine's weekday set or an inactive routine produces a
    non-notifying decision so callers can still audit why nothing happened.
    """

    if not routine.active:
        decision = AlertDecision(
            routine_id=routine.id,
            leg=Leg.DEPARTURE,
            occurrence_at=local_occurrence(occurrence_date, routine.departure_time, routine.timezone),
            evaluation_key=f"inactive:{routine.id}:{occurrence_date.isoformat()}",
            decision_type=DecisionType.INACTIVE,
            should_notify=False,
            message=f"Routine '{routine.name}' is inactive.",
            reasons=("The routine is disabled.",),
            origin_forecast=None,
            destination_forecast=None,
        )
        if repository:
            repository.persist_decision(decision)
        return (decision,)

    if occurrence_date.weekday() not in routine.days_of_week:
        decision = AlertDecision(
            routine_id=routine.id,
            leg=Leg.DEPARTURE,
            occurrence_at=local_occurrence(occurrence_date, routine.departure_time, routine.timezone),
            evaluation_key=f"not-scheduled:{routine.id}:{occurrence_date.isoformat()}",
            decision_type=DecisionType.NOT_SCHEDULED,
            should_notify=False,
            message=f"Routine '{routine.name}' is not scheduled for this weekday.",
            reasons=(f"Weekday {occurrence_date.weekday()} is not configured.",),
            origin_forecast=None,
            destination_forecast=None,
        )
        if repository:
            repository.persist_decision(decision)
        return (decision,)

    points = tuple(forecast_points)
    decisions = [
        _evaluate_one(
            routine,
            Leg.DEPARTURE,
            occurrence_date,
            routine.departure_time,
            points,
        )
    ]
    if routine.return_time is not None:
        decisions.append(
            _evaluate_one(
                routine,
                Leg.RETURN,
                occurrence_date,
                routine.return_time,
                points,
            )
        )

    if repository:
        for decision in decisions:
            repository.persist_decision(decision)
    return tuple(decisions)
