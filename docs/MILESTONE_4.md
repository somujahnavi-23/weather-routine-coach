# Milestone 4 implementation notes

## Goal

Deliver notifications reliably without sending real email, push notifications, or personal data during local development.

## Outbox design

Each pending alert can create at most one `notification_outbox` row because `alert_id` is unique. The outbox stores:

- Channel (`test`, `email`, or `web_push`)
- JSON notification payload
- Queue status
- Attempt count
- Availability and sent timestamps
- Last delivery error

The dispatcher claims queued work, increments attempts, sends through an injected sink, and durably marks the outbox and related alert as sent or failed.

## Idempotency and failure behavior

- Re-enqueueing the same pending alert creates zero duplicate outbox rows.
- A successful delivery marks the outbox `sent` and the alert `delivered`.
- A sink exception marks the outbox `failed`, the alert `failed`, and stores a bounded error message.
- The default test sink stores messages in memory and performs no external delivery.

## API routes

- `POST /notifications/enqueue`
- `POST /notifications/dispatch`

Both routes support optional user scoping. A production adapter should add authentication, retry backoff, rate limits, and provider-specific delivery guarantees.
