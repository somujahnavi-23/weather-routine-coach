"""SQLite persistence for the deterministic milestone."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import AlertDecision, ForecastPoint, Location, Routine, utc_iso


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class WeatherRepository:
    """Small repository wrapper with explicit, testable SQL operations."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    @classmethod
    def in_memory(cls) -> "WeatherRepository":
        connection = sqlite3.connect(":memory:")
        repository = cls(connection)
        repository.initialize()
        return repository

    @classmethod
    def from_path(cls, path: str | Path) -> "WeatherRepository":
        connection = sqlite3.connect(str(path))
        repository = cls(connection)
        repository.initialize()
        return repository

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def add_user(self, user_id: str, email: str) -> None:
        self.connection.execute(
            "INSERT INTO users(id, email, created_at_utc) VALUES (?, ?, ?)",
            (user_id, email, utc_iso(now_utc())),
        )
        self.connection.commit()

    def add_location(self, location: Location) -> None:
        self.connection.execute(
            """
            INSERT INTO locations(
                id, user_id, label, latitude, longitude, timezone, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                location.id,
                location.user_id,
                location.label,
                location.latitude,
                location.longitude,
                location.timezone,
                utc_iso(now_utc()),
            ),
        )
        self.connection.commit()

    def add_routine(self, routine: Routine) -> None:
        self.connection.execute(
            """
            INSERT INTO routines(
                id, user_id, name, origin_location_id, destination_location_id,
                days_of_week, departure_local_time, return_local_time, timezone,
                travel_mode, estimated_duration_minutes, rain_probability_threshold,
                precipitation_mm_threshold, cold_apparent_temperature_c,
                pre_alert_minutes, active, created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                routine.id,
                routine.user_id,
                routine.name,
                routine.origin_location_id,
                routine.destination_location_id,
                json.dumps(routine.days_of_week),
                routine.departure_time.isoformat(),
                routine.return_time.isoformat() if routine.return_time else None,
                routine.timezone,
                routine.travel_mode.value,
                routine.estimated_duration_minutes,
                routine.rain_probability_threshold,
                routine.precipitation_mm_threshold,
                routine.cold_apparent_temperature_c,
                routine.pre_alert_minutes,
                int(routine.active),
                utc_iso(now_utc()),
            ),
        )
        self.connection.commit()

    def location(self, location_id: str, user_id: str | None = None) -> Location | None:
        query = "SELECT * FROM locations WHERE id = ?"
        parameters: tuple[object, ...] = (location_id,)
        if user_id is not None:
            query += " AND user_id = ?"
            parameters += (user_id,)
        row = self.connection.execute(query, parameters).fetchone()
        if row is None:
            return None
        return Location(
            id=row["id"],
            user_id=row["user_id"],
            label=row["label"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            timezone=row["timezone"],
        )

    def routine(self, routine_id: str, user_id: str | None = None) -> Routine | None:
        query = "SELECT * FROM routines WHERE id = ?"
        parameters: tuple[object, ...] = (routine_id,)
        if user_id is not None:
            query += " AND user_id = ?"
            parameters += (user_id,)
        row = self.connection.execute(query, parameters).fetchone()
        if row is None:
            return None
        from datetime import time
        from .models import TravelMode

        return Routine(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            origin_location_id=row["origin_location_id"],
            destination_location_id=row["destination_location_id"],
            days_of_week=tuple(json.loads(row["days_of_week"])),
            departure_time=time.fromisoformat(row["departure_local_time"]),
            return_time=time.fromisoformat(row["return_local_time"]) if row["return_local_time"] else None,
            timezone=row["timezone"],
            travel_mode=TravelMode(row["travel_mode"]),
            estimated_duration_minutes=row["estimated_duration_minutes"],
            rain_probability_threshold=row["rain_probability_threshold"],
            precipitation_mm_threshold=row["precipitation_mm_threshold"],
            cold_apparent_temperature_c=row["cold_apparent_temperature_c"],
            pre_alert_minutes=row["pre_alert_minutes"],
            active=bool(row["active"]),
        )

    def routines(self, user_id: str) -> tuple[Routine, ...]:
        rows = self.connection.execute(
            "SELECT id FROM routines WHERE user_id = ? ORDER BY created_at_utc, id",
            (user_id,),
        ).fetchall()
        return tuple(routine for row in rows if (routine := self.routine(row["id"], user_id)) is not None)

    def add_forecast_points(self, points: Iterable[ForecastPoint]) -> None:
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO forecast_points(
                location_id, valid_at_utc, source, retrieved_at_utc,
                precipitation_probability, precipitation_mm, temperature_c,
                apparent_temperature_c, weather_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    point.location_id,
                    utc_iso(point.valid_at),
                    point.source,
                    utc_iso(point.retrieved_at),
                    point.precipitation_probability,
                    point.precipitation_mm,
                    point.temperature_c,
                    point.apparent_temperature_c,
                    point.weather_code,
                )
                for point in points
            ],
        )
        self.connection.commit()

    def forecast_points(self) -> tuple[ForecastPoint, ...]:
        rows = self.connection.execute(
            "SELECT * FROM forecast_points ORDER BY valid_at_utc"
        ).fetchall()
        from datetime import datetime

        return tuple(
            ForecastPoint(
                location_id=row["location_id"],
                valid_at=datetime.fromisoformat(row["valid_at_utc"].replace("Z", "+00:00")),
                source=row["source"],
                retrieved_at=datetime.fromisoformat(row["retrieved_at_utc"].replace("Z", "+00:00")),
                precipitation_probability=row["precipitation_probability"],
                precipitation_mm=row["precipitation_mm"],
                temperature_c=row["temperature_c"],
                apparent_temperature_c=row["apparent_temperature_c"],
                weather_code=row["weather_code"],
            )
            for row in rows
        )

    def persist_decision(self, decision: AlertDecision) -> tuple[int, bool]:
        """Persist an evaluation and at most one pending alert.

        Returns ``(evaluation_id, alert_created)``. Re-running the same decision
        with the same evaluation key is safe and returns the original row.
        """

        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO evaluations(
                routine_id, leg, occurrence_at_utc, evaluation_key, decision_type,
                should_notify, message, reasons_json, evaluated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.routine_id,
                decision.leg.value,
                utc_iso(decision.occurrence_at),
                decision.evaluation_key,
                decision.decision_type.value,
                int(decision.should_notify),
                decision.message,
                json.dumps(decision.reasons),
                utc_iso(now_utc()),
            ),
        )
        row = self.connection.execute(
            "SELECT id FROM evaluations WHERE evaluation_key = ?",
            (decision.evaluation_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("evaluation was not persisted")
        evaluation_id = int(row["id"])
        alert_created = False
        if decision.should_notify:
            alert_cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO alerts(evaluation_id, status, created_at_utc)
                VALUES (?, 'pending', ?)
                """,
                (evaluation_id, utc_iso(now_utc())),
            )
            alert_created = alert_cursor.rowcount == 1
        self.connection.commit()
        return evaluation_id, alert_created

    def alert_for_user(self, alert_id: int, user_id: str) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT a.*, e.routine_id, e.leg, e.occurrence_at_utc, e.message,
                   e.reasons_json, e.decision_type, e.should_notify, r.user_id
            FROM alerts AS a
            JOIN evaluations AS e ON e.id = a.evaluation_id
            JOIN routines AS r ON r.id = e.routine_id
            WHERE a.id = ? AND r.user_id = ?
            """,
            (alert_id, user_id),
        ).fetchone()

    def enqueue_pending_notifications(self, user_id: str | None = None, *, channel: str = "test") -> int:
        if channel not in {"test", "email", "web_push"}:
            raise ValueError("unsupported notification channel")
        query = """
            SELECT a.id AS alert_id, e.routine_id, e.leg, e.occurrence_at_utc,
                   e.message, e.reasons_json, r.user_id
            FROM alerts AS a
            JOIN evaluations AS e ON e.id = a.evaluation_id
            JOIN routines AS r ON r.id = e.routine_id
            WHERE a.status = 'pending'
        """
        parameters: tuple[object, ...] = ()
        if user_id is not None:
            query += " AND r.user_id = ?"
            parameters = (user_id,)
        rows = self.connection.execute(query, parameters).fetchall()
        created_at = utc_iso(now_utc())
        inserted = 0
        for row in rows:
            payload = {
                "alert_id": row["alert_id"],
                "routine_id": row["routine_id"],
                "user_id": row["user_id"],
                "leg": row["leg"],
                "occurrence_at_utc": row["occurrence_at_utc"],
                "message": row["message"],
                "reasons": json.loads(row["reasons_json"]),
            }
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO notification_outbox(
                    alert_id, channel, payload_json, status, attempts,
                    created_at_utc, available_at_utc
                ) VALUES (?, ?, ?, 'queued', 0, ?, ?)
                """,
                (row["alert_id"], channel, json.dumps(payload, sort_keys=True), created_at, created_at),
            )
            inserted += cursor.rowcount
        self.connection.commit()
        return inserted

    def claim_next_notification(self, user_id: str | None = None) -> sqlite3.Row | None:
        query = """
            SELECT o.*, r.user_id
            FROM notification_outbox AS o
            JOIN alerts AS a ON a.id = o.alert_id
            JOIN evaluations AS e ON e.id = a.evaluation_id
            JOIN routines AS r ON r.id = e.routine_id
            WHERE o.status = 'queued' AND o.available_at_utc <= ?
        """
        parameters: tuple[object, ...] = (utc_iso(now_utc()),)
        if user_id is not None:
            query += " AND r.user_id = ?"
            parameters += (user_id,)
        query += " ORDER BY o.id LIMIT 1"
        row = self.connection.execute(query, parameters).fetchone()
        if row is None:
            return None
        cursor = self.connection.execute(
            "UPDATE notification_outbox SET status = 'processing', attempts = attempts + 1 WHERE id = ? AND status = 'queued'",
            (row["id"],),
        )
        if cursor.rowcount != 1:
            self.connection.rollback()
            return None
        self.connection.commit()
        return self.connection.execute(
            "SELECT o.*, r.user_id FROM notification_outbox AS o JOIN alerts AS a ON a.id = o.alert_id JOIN evaluations AS e ON e.id = a.evaluation_id JOIN routines AS r ON r.id = e.routine_id WHERE o.id = ?",
            (row["id"],),
        ).fetchone()

    def mark_notification_sent(self, outbox_id: int) -> bool:
        sent_at = utc_iso(now_utc())
        cursor = self.connection.execute(
            "UPDATE notification_outbox SET status = 'sent', sent_at_utc = ?, last_error = NULL WHERE id = ? AND status = 'processing'",
            (sent_at, outbox_id),
        )
        if cursor.rowcount != 1:
            self.connection.rollback()
            return False
        self.connection.execute(
            "UPDATE alerts SET status = 'delivered', sent_at_utc = ? WHERE id = (SELECT alert_id FROM notification_outbox WHERE id = ?)",
            (sent_at, outbox_id),
        )
        self.connection.commit()
        return True

    def mark_notification_failed(self, outbox_id: int, error: str, *, retry: bool = False) -> bool:
        status = "queued" if retry else "failed"
        cursor = self.connection.execute(
            "UPDATE notification_outbox SET status = ?, last_error = ? WHERE id = ? AND status = 'processing'",
            (status, error[:500], outbox_id),
        )
        if cursor.rowcount != 1:
            self.connection.rollback()
            return False
        if not retry:
            self.connection.execute(
                "UPDATE alerts SET status = 'failed' WHERE id = (SELECT alert_id FROM notification_outbox WHERE id = ?)",
                (outbox_id,),
            )
        self.connection.commit()
        return True

    def outbox_count(self, status: str | None = None) -> int:
        if status is None:
            row = self.connection.execute("SELECT COUNT(*) AS total FROM notification_outbox").fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) AS total FROM notification_outbox WHERE status = ?", (status,)
            ).fetchone()
        return int(row["total"])

    def add_feedback(
        self,
        alert_id: int,
        user_id: str,
        *,
        helpful: bool | None,
        actual_condition: str | None,
        notes: str | None,
    ) -> int:
        if self.alert_for_user(alert_id, user_id) is None:
            raise ValueError("alert was not found for this user")
        if helpful is not None and not isinstance(helpful, bool):
            raise ValueError("helpful must be true, false, or null")
        if actual_condition is not None and (not isinstance(actual_condition, str) or not actual_condition.strip()):
            raise ValueError("actual_condition must be a non-empty string or null")
        cursor = self.connection.execute(
            "INSERT INTO feedback(alert_id, helpful, actual_condition, notes, created_at_utc) VALUES (?, ?, ?, ?, ?)",
            (
                alert_id,
                None if helpful is None else int(helpful),
                actual_condition.strip().lower() if actual_condition else None,
                notes.strip() if isinstance(notes, str) and notes.strip() else None,
                utc_iso(now_utc()),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def feedback_for_user(self, user_id: str) -> tuple[sqlite3.Row, ...]:
        rows = self.connection.execute(
            """
            SELECT f.id, f.alert_id, f.helpful, f.actual_condition, f.notes,
                   e.should_notify, e.decision_type, e.routine_id, e.leg,
                   r.name AS routine_name, r.user_id
            FROM feedback AS f
            JOIN alerts AS a ON a.id = f.alert_id
            JOIN evaluations AS e ON e.id = a.evaluation_id
            JOIN routines AS r ON r.id = e.routine_id
            WHERE r.user_id = ?
              AND f.id = (SELECT MAX(f2.id) FROM feedback AS f2 WHERE f2.alert_id = f.alert_id)
            ORDER BY f.id
            """,
            (user_id,),
        ).fetchall()
        return tuple(rows)

    def count(self, table: str) -> int:
        allowed = {"evaluations", "alerts", "feedback", "forecast_points", "notification_outbox"}
        if table not in allowed:
            raise ValueError("unsupported table")
        row = self.connection.execute(f"SELECT COUNT(*) AS total FROM {table}").fetchone()
        return int(row["total"])

    def latest_evaluation(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM evaluations ORDER BY id DESC LIMIT 1"
        ).fetchone()
