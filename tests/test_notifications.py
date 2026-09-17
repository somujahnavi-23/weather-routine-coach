from __future__ import annotations

import unittest

from weather_coach.evaluator import evaluate_routine
from weather_coach.fixtures import DEMO_DATE, demo_forecast_points, demo_locations, demo_routine
from weather_coach.notifications import NotificationDispatcher, TestNotificationSink
from weather_coach.repository import WeatherRepository


class FailingSink:
    def send(self, payload):
        raise RuntimeError("test delivery failure")


class NotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = WeatherRepository.in_memory()
        self.repository.add_user("user-demo", "demo@example.invalid")
        for location in demo_locations():
            self.repository.add_location(location)
        self.routine = demo_routine()
        self.repository.add_routine(self.routine)
        evaluate_routine(
            self.routine,
            DEMO_DATE,
            demo_forecast_points(),
            self.repository,
        )

    def tearDown(self) -> None:
        self.repository.close()

    def test_outbox_is_idempotent_and_dispatches_pending_alerts(self) -> None:
        sink = TestNotificationSink()
        dispatcher = NotificationDispatcher(self.repository, sink)

        self.assertEqual(dispatcher.enqueue("user-demo"), 2)
        self.assertEqual(dispatcher.enqueue("user-demo"), 0)
        results = dispatcher.dispatch_all("user-demo")
        second_pass = dispatcher.dispatch_all("user-demo")

        self.assertEqual([result.status for result in results], ["sent", "sent"])
        self.assertEqual(second_pass, ())
        self.assertEqual(len(sink.messages), 2)
        self.assertEqual(self.repository.outbox_count("sent"), 2)
        delivered = self.repository.connection.execute(
            "SELECT COUNT(*) AS total FROM alerts WHERE status = 'delivered'"
        ).fetchone()["total"]
        self.assertEqual(delivered, 2)

    def test_delivery_failure_is_durable_and_alert_is_failed(self) -> None:
        dispatcher = NotificationDispatcher(self.repository, FailingSink())
        dispatcher.enqueue("user-demo")
        result = dispatcher.dispatch_one("user-demo")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, "failed")
        self.assertIn("test delivery failure", result.error)
        self.assertEqual(self.repository.outbox_count("failed"), 1)
        failed = self.repository.connection.execute(
            "SELECT COUNT(*) AS total FROM alerts WHERE status = 'failed'"
        ).fetchone()["total"]
        self.assertEqual(failed, 1)


if __name__ == "__main__":
    unittest.main()
