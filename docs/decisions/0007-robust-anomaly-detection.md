# ADR 0007: Robust CPU-based anomaly detection

## Status

Accepted.

## Decision

Score selected non-cumulative metrics against their recent per-node history with
a median and median absolute deviation (MAD) baseline. Detection starts after
five prior samples. A robust absolute z-score of 3.5 or greater is a warning;
7.0 or greater is critical.

Each finding stores the measured value, baseline, dispersion, score, severity,
and baseline sample count. Event and metric form an idempotency key.

## Why

Median/MAD scoring is inexpensive on CPUs, understandable during incidents,
resistant to individual spikes, deterministic in tests, and useful before a
large labeled failure dataset exists. Cumulative counters and uptime are
excluded until a later phase converts them to rates.

## Consequences

- No GPU or external machine-learning runtime is required.
- New nodes have an intentional warm-up period.
- Findings explain why they were emitted.
- Seasonality and multivariate relationships remain future improvements.
