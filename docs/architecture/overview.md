# Architecture overview

## Goal

Forecast developing reliability risks from correlated metrics, logs, traces,
deployments, and privacy-preserving behavior signals while remaining operable
when dependencies fail.

## Component boundaries

1. **Collectors** gather and redact host or application telemetry.
2. **Event transport** buffers events and applies backpressure.
3. **Stream processors** validate, enrich, aggregate, and route events.
4. **Storage** separates time-series, analytical log, and configuration needs.
5. **Prediction service** trains models and serves versioned risk forecasts.
6. **Incident API and dashboard** correlate evidence for engineering teams.

## Initial reliability decisions

- Events carry a schema version and globally unique event identifier.
- Collectors do not require a GPU.
- Host identity is anonymized by default.
- Collection errors are explicit and never emitted as valid metric events.
- Continuous collection responds to termination signals for graceful shutdown.
- Processing is at-least-once, so consumers must be idempotent because
  delivery may be repeated.
- Ingestion and processing are decoupled through an atomic durable queue.
- Worker leases recover abandoned work after a process failure.

## Scaling path

Phase 4 provides bounded batches, competing workers, lease recovery, retry,
and dead-letter handling through PostgreSQL. This deliberately establishes the
delivery contract before adding a separate broker. Load tests will determine
when a Kafka-compatible transport is justified. Partitioning, consumer groups,
and retention will be added only alongside tests that demonstrate their
behavior.
