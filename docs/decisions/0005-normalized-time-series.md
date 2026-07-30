# ADR 0005: Normalized metric samples

- Status: accepted
- Date: 2026-07-30

## Context

Raw JSON events preserve the complete telemetry contract but are inefficient
for repeated historical queries and future time-window analysis. Processing is
at-least-once, so rebuilding projections must not create duplicate points.

## Decision

Store one row per event and metric. Use `(event_id, metric_name)` as the
primary key and index `(node_id, metric_name, observed_at, event_id)` for
ordered range access. Workers use database-native conflict-safe bulk inserts.

Query endpoints enforce a 31-day maximum window, a 5000-point page limit, and
opaque cursor pagination ordered by `(observed_at, event_id)`.

Raw telemetry remains the source of truth. Migration `0003` requeues
previously processed events so the new projection is backfilled by the normal
worker path.

## Consequences

- Retried work cannot duplicate metric points.
- Historical reads avoid JSON extraction and offset pagination.
- Metric values use floating-point representation suitable for forecasting.
- Disk samples preserve the monitored path as a label.
- Retention can prune projections without deleting the raw source event.
- Aggregation and compression remain later, measurement-driven optimizations.
