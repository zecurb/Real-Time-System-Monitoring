# Durable pipeline worker

The worker separates ingestion latency from downstream processing. The API
stores each telemetry event and queue record atomically, then returns HTTP 202.

## Run

Apply migrations once:

```bash
alembic upgrade head
```

Start a continuous worker:

```bash
rtmonitor-worker
```

Process one batch:

```bash
rtmonitor-worker --once
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `RTMONITOR_WORKER_BATCH_SIZE` | `100` | Maximum events claimed per poll |
| `RTMONITOR_WORKER_LEASE_SECONDS` | `30` | Time before abandoned work is reclaimable |
| `RTMONITOR_WORKER_POLL_SECONDS` | `2` | Idle polling interval |
| `RTMONITOR_WORKER_MAX_ATTEMPTS` | `5` | Attempts before dead-lettering |
| `RTMONITOR_WORKER_RETRY_BASE_SECONDS` | `5` | Exponential retry base delay |

For multi-worker execution, use PostgreSQL. SQLite is intentionally limited to
one worker because it cannot provide PostgreSQL's row-level
`SKIP LOCKED` behavior.
