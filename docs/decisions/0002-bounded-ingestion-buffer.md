# ADR 0002: Refuse telemetry when the ingestion buffer is full

- Status: Accepted
- Date: 2026-07-30

## Context

An unbounded queue can consume all available memory during a traffic spike or
downstream failure. Silently discarding events would hide data loss from
collectors and operators.

## Decision

Phase 2 uses a bounded, thread-safe in-memory buffer. When full, ingestion
returns HTTP `503` with `Retry-After`, and readiness reports `not_ready`.

## Consequences

- Memory use is bounded.
- Backpressure is explicit to clients and load balancers.
- Collectors will eventually need bounded retry queues with jitter.
- Events are not durable until the streaming transport phase.

