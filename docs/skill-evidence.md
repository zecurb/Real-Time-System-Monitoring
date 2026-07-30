# Skill evidence ledger

Resume skills move through: **introduced**, **practiced**, **demonstrated**, and
**validated**. Only demonstrated or validated skills may become resume claims.

| Skill | Status | Current evidence | Next validation |
| --- | --- | --- | --- |
| Python | Demonstrated | Typed collector, API, durable worker, anomaly engine, configuration, and 26-test suite pass lint and strict typing | Independently extend a processor |
| Linux telemetry | Practiced | `/proc` metrics collection and anonymized node identity are implemented | Explain and run on NixOS hosts |
| API development | Demonstrated | Validated FastAPI ingestion contract, health/status endpoints, and failure tests | Independently modify an endpoint |
| React and TypeScript | Practiced | Typed incident console, API client, state/effect handling, responsive SVG chart, degraded states, and component tests | Independently modify and explain dashboard behavior |
| Frontend engineering | Practiced | Responsive layout, accessible controls, production build, locked dependencies, proxy configuration, and zero-vulnerability audit | Browser accessibility and performance audit |
| Observability | Practiced | Correlation IDs, structured request logs, timing headers, and health checks | Add service metrics and traces |
| Maintainable systems | Demonstrated | Application factory, typed boundaries, configuration, tests, four ADRs, and operational runbooks | Perform a peer-style design review |
| SQL and databases | Demonstrated | Composite keys, covering indexes, conflict-safe bulk writes, migrations, retention, and bounded historical queries pass tests | Explain query plans and benchmark PostgreSQL |
| Durable storage | Practiced | Restart persistence and idempotent event ingestion tests | Validate PostgreSQL backup and recovery |
| Resilient infrastructure | Practiced | Storage-aware readiness, idempotency, graceful shutdown, and failure responses | PostgreSQL dependency failure and recovery tests |
| Distributed systems | Practiced | Atomic enqueue, at-least-once delivery, competing workers, leases, retries, dead letters, and recovery tests | Multi-node PostgreSQL load and failure testing |
| Time-series analysis | Demonstrated | Normalized series, bounded range queries, stable cursors, retention, historical backfill, and robust per-node baselines | Add seasonality and forecasting |
| Machine learning | Practiced | CPU-based robust anomaly scoring, cold-start policy, explainable scores, severity thresholds, and deterministic evaluation tests | Train and evaluate a forecasting model |
## Phase 7: explainable anomaly detection

- Implemented robust time-series baselines with median absolute deviation.
- Integrated idempotent anomaly analysis into an at-least-once worker.
- Added durable findings, bounded query APIs, severity classification, tests,
  and an operational dashboard feed.
- Designed the analysis for CPU-only machines and documented cold-start and
  cumulative-counter limitations.
