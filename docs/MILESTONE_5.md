# Milestone 5 implementation notes

## Goal

Capture user feedback and measure whether the deterministic notification decision aligned with the reported weather outcome.

## Feedback model

Feedback is associated with an alert and scoped through the owning user's routine. It can record:

- Whether the alert was helpful
- Reported condition: `clear`, `rain`, `snow`, `ice`, `thunderstorm`, `other`, or `unknown`
- Optional notes

If feedback is submitted more than once for an alert, analytics uses the latest feedback row for that alert.

## Metrics

The analytics summary returns:

- Feedback count
- Helpful-response count and helpful rate
- Labeled outcome count
- Outcome accuracy, precision, and recall
- True-positive, false-positive, true-negative, and false-negative counts
- Reported condition counts

For binary outcome metrics, `clear` means no adverse weather action was needed. Any other known condition except `unknown` is treated as adverse weather. Missing or unknown conditions are excluded from outcome metrics.

## API routes

- `POST /alerts/{alert_id}/feedback`
- `GET /analytics?user_id=...`

The API validates supported conditions and prevents a user from submitting feedback for another user's alert.

## Limitations

These metrics are user-reported evaluation signals, not ground-truth meteorological verification. A future version can store forecast-versus-observation values, route-level conditions, and time-window tolerances for more rigorous calibration analysis.
