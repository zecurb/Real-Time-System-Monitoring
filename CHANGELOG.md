# Changelog

All notable changes to this project are documented here.

## [1.1.0] - 2026-08-02

### Added

- Self-contained Windows desktop executable built with PyInstaller.
- Native Windows telemetry collection for load, CPU count, memory, disk, network, uptime, and process count.
- Automatic local database initialization and Alembic migrations.
- Automatic local telemetry ingestion and background analysis processing.
- Bundled React incident console served from the desktop executable.
- Windows packaging CI with executable smoke testing and local node discovery.
- SHA-256 checksum generation and tagged-release asset publishing.
- Public GitHub Pages product website with direct Windows downloads.
- Subtle GitHub profile-image watermark in the product site and incident console.

### Distribution boundaries

- The initial Windows executable is not Authenticode-signed and may trigger an unrecognized publisher warning.
- The desktop distribution uses local SQLite and one background worker; PostgreSQL remains the production target for multi-worker deployments.
- The executable binds only to loopback by default and is intended for local desktop evaluation.

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
