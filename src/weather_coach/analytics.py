"""Feedback and forecast-versus-outcome analytics."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Any


KNOWN_CONDITIONS = frozenset({"clear", "rain", "snow", "ice", "thunderstorm", "other", "unknown"})


def _is_adverse(condition: str | None) -> bool | None:
    if condition is None or condition == "unknown":
        return None
    return condition != "clear"


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def summarize_feedback(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return explainable feedback and binary outcome metrics.

    A labeled outcome is adverse when the user reports anything other than
    ``clear``. The model prediction is the persisted ``should_notify`` flag.
    Unknown or missing conditions are excluded from outcome metrics.
    """

    row_list = list(rows)
    helpful_values = [row["helpful"] for row in row_list if row["helpful"] is not None]
    helpful_count = sum(int(value) == 1 for value in helpful_values)

    confusion = Counter({
        "true_positive": 0,
        "false_positive": 0,
        "true_negative": 0,
        "false_negative": 0,
    })
    condition_counts: Counter[str] = Counter()
    labeled = 0
    for row in row_list:
        condition = row["actual_condition"]
        if condition:
            condition_counts[str(condition)] += 1
        actual_adverse = _is_adverse(condition)
        if actual_adverse is None:
            continue
        labeled += 1
        predicted_notify = bool(row["should_notify"])
        if predicted_notify and actual_adverse:
            confusion["true_positive"] += 1
        elif predicted_notify and not actual_adverse:
            confusion["false_positive"] += 1
        elif not predicted_notify and actual_adverse:
            confusion["false_negative"] += 1
        else:
            confusion["true_negative"] += 1

    true_positive = confusion["true_positive"]
    false_positive = confusion["false_positive"]
    true_negative = confusion["true_negative"]
    false_negative = confusion["false_negative"]
    return {
        "feedback_count": len(row_list),
        "helpful_response_count": len(helpful_values),
        "helpful_count": helpful_count,
        "helpful_rate": _rate(helpful_count, len(helpful_values)),
        "outcome_labeled_count": labeled,
        "outcome_accuracy": _rate(true_positive + true_negative, labeled),
        "outcome_precision": _rate(true_positive, true_positive + false_positive),
        "outcome_recall": _rate(true_positive, true_positive + false_negative),
        "confusion": dict(confusion),
        "actual_condition_counts": dict(sorted(condition_counts.items())),
    }
