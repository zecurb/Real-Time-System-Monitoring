# ADR 0009: Durable incident workflows

## Status

Accepted.

## Context

Anomalies and forecasts are evidence, not an operator workflow. Repeated worker
delivery must not create duplicate incidents or inflate counts, while multiple
operators must not silently overwrite each other's decisions.

## Decision

Correlate warning and critical evidence by node and metric. Give every incident
a deterministic identifier, and deduplicate its evidence by event, metric, and
source. Persist lifecycle state separately from an append-only timeline.

Use row locks on PostgreSQL and a monotonically increasing revision for
acknowledgement and resolution. Reject stale revisions with a conflict. Reopen
a resolved incident when new evidence arrives while preserving its history.

## Consequences

- Worker retries are idempotent at both evidence and incident levels.
- Operators get visible ownership, resolution notes, and an audit trail.
- Correlation is intentionally narrow; cross-metric and cross-node grouping
  requires a later, separately evaluated model.
- The API actor is only an audit label until deployment authentication and
  authorization derive a trusted identity at the service boundary.
