# Weather Routine Coach

Milestones 1-5 of a privacy-conscious, explainable weather decision assistant for recurring commutes and short trips.

## Current milestone

The current implementation includes:

- A SQLite schema for users, locations, routines, forecast snapshots, evaluations, alerts, and feedback.
- A standard-library Python domain model.
- A rule-based decision engine for rain, precipitation, cold, and severe-weather conditions.
- Stable evaluation keys and database uniqueness constraints for duplicate prevention.
- An Open-Meteo provider adapter with UTC-bounded requests, response validation, WMO weather-code normalization, and explicit provider errors.
- A dependency-free JSON API core for health checks, routine creation/listing, and provider-backed evaluations.
- A durable notification outbox with idempotent enqueueing and an in-memory test delivery sink.
- Feedback capture and forecast-versus-outcome analytics with helpfulness and confusion-matrix metrics.
- Synthetic forecast fixtures with no real addresses, credentials, or API keys.
- Unit and integration tests using Python's built-in `unittest` module.

It does **not** yet include authentication, a web UI, push notifications, or AI-generated recommendations. Live API calls are supported by the adapter but are kept out of automated tests and the default demo.

## Requirements

- Python 3.11 or newer
- No third-party packages are required; the adapter uses Python's standard library

Python 3.13 was used for the local verification run.

## Run the tests

From this directory:

```powershell
python run_tests.py
```

## Run the deterministic demo

```powershell
python scripts/run_demo.py
```

The demo creates an in-memory database, evaluates a synthetic weekday commute, and prints the explainable alert decision. It never contacts a weather provider.

## Run the complete local flow

```powershell
python scripts/run_full_demo.py
```

The complete demo exercises routine creation, provider-shaped forecast retrieval, explainable evaluation, idempotent notification dispatch through an in-memory sink, feedback capture, and forecast-versus-outcome analytics. It uses only synthetic data.

## Project layout

```text
src/weather_coach/
  decision_engine.py  Pure rule-based evaluation logic
  evaluator.py        Routine occurrence and persistence orchestration
  fixtures.py         Synthetic locations, routines, and forecast points
  models.py           Domain dataclasses and validation
  provider.py         Open-Meteo HTTP adapter and forecast normalization
  api.py              Dependency-free JSON API core
  analytics.py        Feedback and forecast-outcome metrics
  notifications.py    Durable outbox and test delivery sink
  repository.py       SQLite persistence and idempotent alert creation
  schema.sql          Database schema
scripts/run_demo.py   Offline decision-engine demonstration
scripts/run_full_demo.py Complete local product-flow demonstration
 tests/               Standard-library unit and integration tests
```

## Design principles

1. Store forecast timestamps in UTC and retain the user's IANA timezone for recurring local schedules.
2. Evaluate deterministic rules before considering any AI or language model feature.
3. Persist the forecast snapshot and reasons behind every decision.
4. Treat scheduler retries as normal and make evaluation keys idempotent.
5. Keep location handling minimal. The fixtures use synthetic coordinates and labels.
6. Do not commit `.env` files, API keys, passwords, tokens, addresses, or personal data.

## Production hardening still needed

- Authentication and authorization.
- FastAPI mounting when a dependency-installable environment is available.
- Real email or web-push delivery adapters.
- Web UI and deployment.
- Retry backoff, rate limiting, caching, observability, and provider fallback.

Any live API, hosted service, or GitHub push will be reviewed separately before use.
