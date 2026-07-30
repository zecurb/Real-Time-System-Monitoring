# ADR 0004: Durable leased work queue

- Status: accepted
- Date: 2026-07-30

## Context

The ingestion API must acknowledge validated telemetry quickly without running
enrichment, anomaly detection, or forecasting in the request path. A process
crash must not silently lose accepted work, and multiple worker processes must
be able to share load without intentionally processing the same event.

The project is still proving its traffic profile. Operating Kafka or Redpanda
before measuring that need would add deployment complexity without improving
the current learning milestone.

## Decision

Write the telemetry event and a queue row in one database transaction. Workers
claim bounded batches using expiring leases. PostgreSQL workers use
`FOR UPDATE SKIP LOCKED` so competing workers claim different rows. Failed work
is retried with exponential delay and moved to a dead-letter state after the
configured attempt limit.

SQLite remains supported for local development and tests, but only one worker
is supported there. PostgreSQL is required for multi-worker production use.

## Consequences

- An HTTP 202 response means both the event and its processing intent were
  durably committed.
- A crashed worker's lease expires and another worker can recover the event.
- Processing is at-least-once. Every future processor must therefore be
  idempotent.
- Queue growth and dead letters are directly observable.
- Database throughput is the present queue ceiling. A broker can replace this
  boundary later using measured capacity evidence without changing the event
  contract.
