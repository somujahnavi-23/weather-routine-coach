from __future__ import annotations

import unittest

from weather_coach.analytics import summarize_feedback


class AnalyticsTests(unittest.TestCase):
    def test_summarizes_helpfulness_and_outcome_confusion_matrix(self) -> None:
        rows = [
            {"helpful": 1, "actual_condition": "rain", "should_notify": 1},
            {"helpful": 0, "actual_condition": "clear", "should_notify": 1},
            {"helpful": 1, "actual_condition": "clear", "should_notify": 0},
            {"helpful": None, "actual_condition": "snow", "should_notify": 0},
            {"helpful": 1, "actual_condition": "unknown", "should_notify": 1},
        ]

        metrics = summarize_feedback(rows)

        self.assertEqual(metrics["feedback_count"], 5)
        self.assertEqual(metrics["helpful_response_count"], 4)
        self.assertEqual(metrics["helpful_count"], 3)
        self.assertEqual(metrics["helpful_rate"], 0.75)
        self.assertEqual(metrics["outcome_labeled_count"], 4)
        self.assertEqual(metrics["confusion"], {
            "true_positive": 1,
            "false_positive": 1,
            "true_negative": 1,
            "false_negative": 1,
        })
        self.assertEqual(metrics["outcome_accuracy"], 0.5)
        self.assertEqual(metrics["outcome_precision"], 0.5)
        self.assertEqual(metrics["outcome_recall"], 0.5)


if __name__ == "__main__":
    unittest.main()
