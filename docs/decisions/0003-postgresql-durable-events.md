# ADR 0003: Use PostgreSQL for durable telemetry events

- Status: Accepted
- Date: 2026-07-30

## Context

The Phase 2 in-memory buffer loses events when the API restarts. The platform
needs durable acknowledgements, duplicate protection, migrations, and a path
to historical queries before time-series analysis can begin.

## Decision

Use PostgreSQL as the production system of record through SQLAlchemy's async
interface. Use `event_id` as the idempotency key, retain indexed relational
fields for common queries, and preserve the validated event in JSONB. Manage
schema changes with Alembic. Support SQLite only for local development and
isolated tests.

## Consequences

- A `202` response means the event transaction committed.
- Collector retries do not create duplicate rows.
- Readiness depends on the migrated telemetry table.
- PostgreSQL availability is now part of the ingestion service's reliability.
- High-volume decoupling still requires durable streaming in a later phase.

