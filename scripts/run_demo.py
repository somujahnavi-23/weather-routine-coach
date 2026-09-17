"""Run the offline Milestone 1 synthetic commute evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from weather_coach.evaluator import evaluate_routine  # noqa: E402
from weather_coach.fixtures import DEMO_DATE, demo_forecast_points, demo_locations, demo_routine  # noqa: E402
from weather_coach.repository import WeatherRepository  # noqa: E402


def main() -> None:
    repository = WeatherRepository.in_memory()
    repository.add_user("user-demo", "demo@example.invalid")
    for location in demo_locations():
        repository.add_location(location)
    routine = demo_routine()
    repository.add_routine(routine)
    points = demo_forecast_points(rainy=True)
    repository.add_forecast_points(points)

    decisions = evaluate_routine(routine, DEMO_DATE, repository.forecast_points(), repository)
    print("Weather Routine Coach - Milestone 1 offline demo")
    for decision in decisions:
        print(f"[{decision.leg.value}] {decision.decision_type.value}: {decision.message}")
        for reason in decision.reasons:
            print(f"  - {reason}")
        print(f"  evaluation_key={decision.evaluation_key}")

    print(f"evaluations={repository.count('evaluations')}")
    print(f"pending_alerts={repository.count('alerts')}")
    repository.close()


if __name__ == "__main__":
    main()
