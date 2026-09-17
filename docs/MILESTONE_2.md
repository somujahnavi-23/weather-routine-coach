# Milestone 2 implementation notes

## Goal

Add a live-provider boundary without coupling the explainable decision engine to an external API. The adapter fetches hourly data from Open-Meteo and normalizes it into the existing `ForecastPoint` model.

## Provider contract

`OpenMeteoProvider.fetch_hourly(location, start_at, end_at)`:

- Accepts one domain `Location` and an aware datetime window.
- Converts the request window to UTC.
- Requests only the hourly variables needed by the decision engine.
- Returns normalized `ForecastPoint` values for the requested inclusive window.
- Preserves the domain location ID rather than trusting a provider grid-cell ID.
- Records the retrieval timestamp in UTC.

The default transport uses Python's standard-library `urllib`. Tests inject a fake transport, so the suite never contacts a live service.

## Open-Meteo normalization

The adapter requests:

- `temperature_2m`
- `apparent_temperature`
- `precipitation`
- `precipitation_probability`
- `weather_code`

Open-Meteo returns precipitation probability as a percentage. The adapter converts it to the domain's 0.0-1.0 fraction. It maps WMO weather codes to the domain vocabulary, including `rain`, `snow`, `ice`, and `thunderstorm` for downstream explainable rules.

## Failure behavior

The adapter raises `WeatherProviderError` for:

- HTTP or transport failures
- Invalid JSON
- Provider error responses
- Missing hourly fields
- Inconsistent hourly array lengths
- Null or invalid numeric values
- Invalid precipitation probabilities or amounts

This keeps provider failures distinguishable from a valid clear forecast. The evaluator can continue to represent unavailable data explicitly rather than silently treating it as safe weather.

## Privacy and reliability boundaries

- Only the stored latitude and longitude for the requested location are sent to the provider.
- Synthetic fixture coordinates remain the default demo data.
- No user email, routine name, address label, credentials, or API key is included in the request.
- The adapter does not persist raw provider JSON; callers persist normalized forecast snapshots through the existing repository.
- No retry policy is added yet. A future service layer should add bounded retries, backoff, rate-limit handling, and provider observability.

## Verification

`tests/test_provider.py` verifies URL construction, UTC windows, normalization, probability conversion, WMO mappings, injected transport behavior, and explicit malformed-response errors.

## Remaining limitations

- The project still has no user-facing interface or notification delivery.
- Open-Meteo is the first provider; there is no fallback provider.
- Forecast retrieval is per location rather than a multi-location batch request.
- No caching or freshness policy is implemented at the provider boundary.
- No production deployment or live smoke test is performed by the default test runner.
