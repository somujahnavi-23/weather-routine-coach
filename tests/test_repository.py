from __future__ import annotations

import unittest

from weather_coach.fixtures import DEMO_DATE, demo_forecast_points, demo_locations, demo_routine
from weather_coach.repository import WeatherRepository


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = WeatherRepository.in_memory()
        self.repository.add_user("user-demo", "demo@example.invalid")
        for location in demo_locations():
            self.repository.add_location(location)
        self.routine = demo_routine()
        self.repository.add_routine(self.routine)

    def tearDown(self) -> None:
        self.repository.close()

    def test_schema_and_forecast_round_trip(self) -> None:
        points = demo_forecast_points()
        self.repository.add_forecast_points(points)
        restored = self.repository.forecast_points()

        self.assertEqual(len(restored), len(points))
        self.assertEqual(restored[0].location_id, points[0].location_id)
        self.assertEqual(restored[0].valid_at, points[0].valid_at)

    def test_duplicate_decision_creates_one_evaluation_and_one_alert(self) -> None:
        from weather_coach.evaluator import evaluate_routine

        self.repository.add_forecast_points(demo_forecast_points(rainy=True))
        points = self.repository.forecast_points()
        first = evaluate_routine(self.routine, DEMO_DATE, points, self.repository)
        second = evaluate_routine(self.routine, DEMO_DATE, points, self.repository)

        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)
        self.assertEqual(self.repository.count("evaluations"), 2)
        self.assertEqual(self.repository.count("alerts"), 2)

        rows = self.repository.connection.execute(
            "SELECT evaluation_key, COUNT(*) AS total FROM evaluations GROUP BY evaluation_key"
        ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(row["total"] == 1 for row in rows))

    def test_non_notification_is_recorded_without_alert(self) -> None:
        from weather_coach.evaluator import evaluate_routine

        self.repository.add_forecast_points(demo_forecast_points(rainy=False))
        evaluate_routine(self.routine, DEMO_DATE, self.repository.forecast_points(), self.repository)

        self.assertEqual(self.repository.count("evaluations"), 2)
        self.assertEqual(self.repository.count("alerts"), 0)


if __name__ == "__main__":
    unittest.main()
