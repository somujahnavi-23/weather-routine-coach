from __future__ import annotations

import unittest
from datetime import datetime, time, timedelta

from weather_coach.decision_engine import evaluate_leg, evaluation_key
from weather_coach.fixtures import DEMO_DATE, demo_forecast_points, demo_routine
from weather_coach.models import DecisionType, Leg, Routine, TravelMode
from weather_coach.timezone_utils import get_timezone


class DecisionEngineTests(unittest.TestCase):
    def test_rain_at_destination_triggers_explainable_notification(self) -> None:
        routine = demo_routine()
        decision = evaluate_leg(
            routine,
            Leg.DEPARTURE,
            datetime.combine(DEMO_DATE, routine.departure_time, tzinfo=get_timezone(routine.timezone)),
            demo_forecast_points(rainy=True),
        )

        self.assertTrue(decision.should_notify)
        self.assertEqual(decision.decision_type, DecisionType.NOTIFY)
        self.assertIn("rain probability", decision.message)
        self.assertGreaterEqual(len(decision.reasons), 1)

    def test_clear_forecast_produces_no_action(self) -> None:
        routine = demo_routine()
        decision = evaluate_leg(
            routine,
            Leg.DEPARTURE,
            datetime.combine(DEMO_DATE, routine.departure_time, tzinfo=get_timezone(routine.timezone)),
            demo_forecast_points(rainy=False),
        )

        self.assertFalse(decision.should_notify)
        self.assertEqual(decision.decision_type, DecisionType.NO_ACTION)
        self.assertEqual(decision.reasons, ("No configured weather rule was triggered.",))

    def test_missing_forecast_is_not_silently_treated_as_clear(self) -> None:
        routine = demo_routine()
        decision = evaluate_leg(
            routine,
            Leg.DEPARTURE,
            datetime.combine(DEMO_DATE, routine.departure_time, tzinfo=get_timezone(routine.timezone)),
            (),
        )

        self.assertFalse(decision.should_notify)
        self.assertEqual(decision.decision_type, DecisionType.DATA_UNAVAILABLE)
        self.assertIn("unavailable", decision.message)

    def test_return_leg_reverses_origin_and_destination(self) -> None:
        routine = demo_routine()
        decision = evaluate_leg(
            routine,
            Leg.RETURN,
            datetime.combine(DEMO_DATE, routine.return_time, tzinfo=get_timezone(routine.timezone)),
            demo_forecast_points(rainy=True),
        )

        self.assertTrue(decision.should_notify)
        self.assertEqual(decision.origin_forecast.location_id, routine.destination_location_id)
        self.assertEqual(decision.destination_forecast.location_id, routine.origin_location_id)

    def test_evaluation_key_is_stable(self) -> None:
        routine = demo_routine()
        occurrence = datetime.combine(DEMO_DATE, time(8), tzinfo=get_timezone(routine.timezone))
        first = evaluation_key(routine.id, Leg.DEPARTURE, occurrence)
        second = evaluation_key(routine.id, Leg.DEPARTURE, occurrence)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)

    def test_new_york_timezone_preserves_standard_and_daylight_offsets(self) -> None:
        timezone = get_timezone("America/New_York")
        winter = datetime(2026, 1, 15, 8, tzinfo=timezone)
        summer = datetime(2026, 7, 15, 8, tzinfo=timezone)

        self.assertEqual(winter.utcoffset(), timedelta(hours=-5))
        self.assertEqual(summer.utcoffset(), timedelta(hours=-4))

    def test_invalid_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Routine(
                id="bad",
                user_id="user",
                name="Bad",
                origin_location_id="a",
                destination_location_id="b",
                days_of_week=(0,),
                departure_time=time(8),
                return_time=None,
                timezone="America/New_York",
                travel_mode=TravelMode.WALK,
                estimated_duration_minutes=30,
                rain_probability_threshold=1.5,
                precipitation_mm_threshold=0.5,
                cold_apparent_temperature_c=None,
                pre_alert_minutes=30,
            )


if __name__ == "__main__":
    unittest.main()
