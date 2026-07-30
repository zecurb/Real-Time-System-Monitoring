# Changelog

All notable changes to this project are documented here.

## [1.0.0] - 2026-07-30

### Added

- Linux telemetry collection with privacy-preserving node identity.
- Validated FastAPI ingestion with request correlation, bounded payloads, and health checks.
- Durable SQLAlchemy storage with PostgreSQL production support and SQLite development support.
- Transactional queue insertion, leased workers, retry, crash recovery, and dead-letter handling.
- Normalized time-series storage, bounded historical queries, cursor pagination, and retention cleanup.
- React and TypeScript incident console.
- Explainable anomaly detection using per-node median and MAD baselines.
- Memory and disk exhaustion forecasting with confidence, risk, backtesting, and CPU/GPU provider reporting.
- Durable incident correlation, acknowledgement, resolution, reopening, optimistic revisions, and immutable timelines.
- Dependabot, CodeQL, tagged release automation, security policy, support policy, and production-readiness checklist.

### Production boundaries

- PostgreSQL is required for multi-worker production operation.
- Production ingress must provide authentication, authorization, trusted operator identity, TLS, rate limiting, and complete request-size enforcement.
- Operators are responsible for secrets management, network isolation, capacity testing, backup, and restoration.
- The software is source-visible and proprietary; commercial use requires a written license.