"""Reliable notification outbox and test-only delivery primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .repository import WeatherRepository


class NotificationSink(Protocol):
    """Destination contract used by the outbox dispatcher."""

    def send(self, payload: dict[str, Any]) -> None:
        """Deliver one notification payload or raise an exception."""


@dataclass(frozen=True, slots=True)
class DispatchResult:
    outbox_id: int
    alert_id: int
    status: str
    attempts: int
    error: str | None = None


class TestNotificationSink:
    """In-memory sink for deterministic tests and the local demo."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def send(self, payload: dict[str, Any]) -> None:
        self.messages.append(dict(payload))


class NotificationDispatcher:
    """Enqueue pending alerts and deliver them through an injected sink."""

    def __init__(self, repository: WeatherRepository, sink: NotificationSink) -> None:
        self.repository = repository
        self.sink = sink

    def enqueue(self, user_id: str | None = None, *, channel: str = "test") -> int:
        return self.repository.enqueue_pending_notifications(user_id, channel=channel)

    def dispatch_one(self, user_id: str | None = None) -> DispatchResult | None:
        row = self.repository.claim_next_notification(user_id)
        if row is None:
            return None
        outbox_id = int(row["id"])
        alert_id = int(row["alert_id"])
        attempts = int(row["attempts"])
        try:
            payload = json.loads(row["payload_json"])
            if not isinstance(payload, dict):
                raise ValueError("outbox payload must be a JSON object")
            self.sink.send(payload)
        except Exception as exc:  # delivery adapters must convert failures to durable state
            error = f"{type(exc).__name__}: {exc}"
            self.repository.mark_notification_failed(outbox_id, error)
            return DispatchResult(outbox_id, alert_id, "failed", attempts, error)

        self.repository.mark_notification_sent(outbox_id)
        return DispatchResult(outbox_id, alert_id, "sent", attempts)

    def dispatch_all(self, user_id: str | None = None, *, max_items: int = 100) -> tuple[DispatchResult, ...]:
        if max_items <= 0:
            raise ValueError("max_items must be positive")
        results: list[DispatchResult] = []
        self.enqueue(user_id)
        while len(results) < max_items:
            result = self.dispatch_one(user_id)
            if result is None:
                break
            results.append(result)
        return tuple(results)
