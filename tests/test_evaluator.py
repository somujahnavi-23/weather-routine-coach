from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from weather_coach.evaluator import evaluate_routine
from weather_coach.fixtures import DEMO_DATE, demo_forecast_points, demo_routine
from weather_coach.models import DecisionType


class EvaluatorTests(unittest.TestCase):
    def test_two_legs_are_evaluated_for_scheduled_weekday(self) -> None:
        decisions = evaluate_routine(demo_routine(), DEMO_DATE, demo_forecast_points())

        self.assertEqual([decision.leg.value for decision in decisions], ["departure", "return"])
        self.assertTrue(all(decision.should_notify for decision in decisions))

    def test_unscheduled_weekday_returns_auditable_skip(self) -> None:
        decisions = evaluate_routine(demo_routine(), date(2026, 9, 20), demo_forecast_points())

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].decision_type, DecisionType.NOT_SCHEDULED)
        self.assertFalse(decisions[0].should_notify)

    def test_inactive_routine_returns_auditable_skip(self) -> None:
        routine = demo_routine()
        inactive = replace(routine, active=False)
        decisions = evaluate_routine(inactive, DEMO_DATE, demo_forecast_points())

        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].decision_type, DecisionType.INACTIVE)
        self.assertFalse(decisions[0].should_notify)


if __name__ == "__main__":
    unittest.main()
