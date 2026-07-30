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
- Normalized metric samples use `(event_id, metric_name)` uniqueness so
  at-least-once processing cannot duplicate time-series points.
- Historical queries are bounded by time window and page size.

## Scaling path

Phase 4 provides bounded batches, competing workers, lease recovery, retry,
and dead-letter handling through PostgreSQL. This deliberately establishes the
delivery contract before adding a separate broker. Load tests will determine
when a Kafka-compatible transport is justified. Partitioning, consumer groups,
and retention will be added only alongside tests that demonstrate their
behavior.

## Time-series boundary

The Phase 5 worker converts each schema `1.0` telemetry event into 14
normalized metric samples. PostgreSQL indexes samples by node, metric,
observation time, and event ID. This supports stable cursor pagination and
future time-window features without scanning JSON event payloads.

Raw events remain the source of truth. Normalized samples are a reproducible
projection, which allows migration `0003` to requeue previously processed
events for backfill.

## Incident console boundary

The dashboard is a React and TypeScript single-page application. It discovers
nodes and metric metadata from the API, queries bounded historical windows,
and refreshes operational state every five seconds. Failed refreshes preserve
last-known data and display an explicit degraded-state banner.

The frontend uses no third-party charting library. Its responsive SVG chart
keeps the production bundle small and provides an accessible image label and
point-level tooltips. Development uses Vite's same-origin proxy. Production
deployments serve the compiled static assets behind the same reverse proxy as
the API.

## Anomaly-detection boundary

The Phase 7 worker scores selected non-cumulative metrics after normalization.
Each node and metric receives its own median/MAD baseline over up to 120 prior
samples from seven days. Findings use `(event_id, metric_name)` uniqueness, so
worker retries cannot duplicate an anomaly.

The detector intentionally runs inside the durable leased processing path. A
failed analysis therefore uses the existing retry and dead-letter contract.
The dashboard reads bounded findings from `/v1/anomalies`; it does not perform
or reinterpret scoring in the browser.

## Forecasting and hardware boundary

The Phase 8 worker forecasts memory and disk exhaustion from the newest 2,048
samples in a bounded seven-day window. A least-squares trend must have at least
six samples, span at least five minutes, and pass an R² quality gate before the
system persists a threshold crossing. Each record includes its slope, horizon,
confidence, risk, one-step backtest error, and actual execution provider.

CPU execution is always available and remains the automatic fallback for the
two hosts without working GPUs. If an operator installs a compatible CuPy build
and a CUDA device passes runtime detection, regression arrays execute on the
GPU. Provider resolution and computation failures remain observable through
`/v1/runtime` and forecast metadata. The collector and durable pipeline never
require a GPU.

## Incident lifecycle boundary

Phase 9 correlates warning and critical anomaly or forecast evidence by
`(node_id, metric_name)`. Evidence is independently deduplicated by
`(event_id, metric_name, source)`, so at-least-once worker retries cannot
inflate occurrence counts. Critical evidence escalates an existing warning;
new evidence reopens a resolved incident.

Operators acknowledge and resolve incidents through revision-checked API
commands. Every automatic and operator transition appends an immutable
timeline record. PostgreSQL row locks serialize production updates, while the
revision field rejects stale browser actions and makes conflicts explicit.
