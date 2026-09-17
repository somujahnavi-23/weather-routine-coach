# Milestone 3 implementation notes

## Goal

Expose routine management and provider-backed evaluation through a small JSON API boundary while keeping the domain engine independent from any web framework.

## API routes

The framework-neutral `WeatherApi.handle(method, path, body)` dispatcher supports:

- `GET /health` for a versioned health response.
- `GET /routines?user_id=...` for a user's routines.
- `POST /routines` to validate and persist a routine linked to existing user locations.
- `POST /routines/{routine_id}/evaluate` to fetch both routine locations, persist normalized forecast snapshots, evaluate the scheduled date, and return explainable decisions.

The dispatcher returns a status code and JSON-ready payload. `json_bytes` provides deterministic serialization for a future HTTP framework adapter.

## Design choice

FastAPI and Pydantic are not installed in the isolated environment, and the environment cannot install packages from the network. This milestone therefore implements the tested API core with Python's standard library rather than adding an untested dependency. The core can later be mounted behind FastAPI without changing the provider, evaluator, repository, or decision engine contracts.

## Safety behavior

- Routine reads and evaluations require a user ID and scope database lookups to that user.
- Routine creation verifies both origin and destination belong to the user.
- Invalid dates, times, travel modes, thresholds, and missing fields return client-safe 400 responses.
- Missing routines return 404 responses.
- Evaluation without a configured provider returns 503 rather than pretending the weather is clear.
- Provider-backed evaluations persist forecast snapshots and the existing idempotent decisions and alerts.

## Verification

`tests/test_api.py` covers health checks, routine creation, routine listing, provider-backed evaluation, user scoping requirements, missing-provider handling, and invalid input handling. The full suite remains standard-library-only.

## Remaining limitations

- No authentication or authorization layer exists yet.
- No actual web server is started by the project scripts.
- FastAPI integration is deferred until a dependency-installable environment is available or the dependency is explicitly approved.
- No notification delivery or web UI exists yet.
