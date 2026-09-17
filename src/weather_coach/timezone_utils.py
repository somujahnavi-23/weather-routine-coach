"""Timezone helpers with a small offline fallback for the demo environment.

Production deployments should install the ``tzdata`` package when the host
system does not provide IANA timezone files. The fallback keeps the synthetic
New York demonstration runnable in this isolated environment while preserving
DST-aware behavior for that timezone.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta, tzinfo, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class _NewYorkFallback(tzinfo):
    """DST-aware America/New_York fallback for the modern U.S. rules."""

    @staticmethod
    def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> datetime:
        first_weekday, days_in_month = monthrange(year, month)
        day = 1 + (weekday - first_weekday) % 7 + (occurrence - 1) * 7
        if day > days_in_month:
            raise ValueError("invalid weekday occurrence")
        return datetime(year, month, day, 2, 0)

    @classmethod
    def _dst_start(cls, year: int) -> datetime:
        # Second Sunday in March at 02:00 local standard time.
        return cls._nth_weekday(year, 3, 6, 2)

    @classmethod
    def _dst_end(cls, year: int) -> datetime:
        # First Sunday in November at 02:00 local daylight time.
        return cls._nth_weekday(year, 11, 6, 1)

    @classmethod
    def _is_dst_local(cls, value: datetime) -> bool:
        naive = value.replace(tzinfo=None)
        start = cls._dst_start(naive.year)
        end = cls._dst_end(naive.year)
        return start <= naive < end

    def utcoffset(self, value: datetime | None) -> timedelta:
        return timedelta(hours=-4 if value is not None and self._is_dst_local(value) else -5)

    def dst(self, value: datetime | None) -> timedelta:
        return timedelta(hours=1 if value is not None and self._is_dst_local(value) else 0)

    def tzname(self, value: datetime | None) -> str:
        return "EDT" if value is not None and self._is_dst_local(value) else "EST"


_FALLBACKS = {"America/New_York": _NewYorkFallback()}


def get_timezone(name: str) -> tzinfo:
    if name == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        fallback = _FALLBACKS.get(name)
        if fallback is not None:
            return fallback
        raise ZoneInfoNotFoundError(
            f"IANA timezone '{name}' is unavailable. Install the 'tzdata' package "
            "or use a host with system timezone data."
        ) from None
