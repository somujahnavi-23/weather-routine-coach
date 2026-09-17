# Milestone 1 implementation notes

## Goal

Prove the domain and reliability core before adding external services.

## Decision model

A routine contains:

- A local IANA timezone
- Origin and destination locations
- Scheduled weekdays
- Departure and optional return time
- Estimated travel duration
- Travel mode
- Rain probability threshold
- Precipitation threshold
- Optional feels-like cold threshold
- Alert lead time

Each leg evaluates a forecast point at the departure location and a forecast point at the estimated arrival location. A notification is created if any configured rule is triggered.

## Decision states

- `notify`: at least one configured rule triggered
- `no_action`: forecasts were available and no rule triggered
- `data_unavailable`: a required forecast point was missing
- `inactive`: routine was disabled
- `not_scheduled`: the date was outside the selected weekday set

Skipped decisions are still recorded conceptually so the future product can distinguish “nothing happened because conditions were clear” from “nothing happened because the scheduler failed.”

## Idempotency

The evaluation key is derived from:

```text
routine ID + leg + scheduled occurrence in UTC
```

The database enforces uniqueness on that key. Alerts are created only for notifying decisions and are linked one-to-one with evaluations.

## Current limitations

- Forecast points are supplied by fixtures.
- Estimated duration is fixed per routine.
- No road-network routing or intermediate route points.
- No live provider or API retry layer.
- No authentication.
- No browser push or email delivery.
- SQLite is appropriate for the prototype, not automatically for production scale.
- No user-facing web interface yet.

## Next design checkpoint

Before Milestone 2, review the provider adapter contract and decide whether the first live provider should be Open-Meteo alone or Open-Meteo plus NWS alert ingestion for U.S. severe-weather notices.
