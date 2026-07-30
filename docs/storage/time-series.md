# Time-series storage

Each telemetry event produces 14 normalized samples in `metric_samples`.
PostgreSQL is the production target; SQLite remains suitable for local
single-worker development.

## Processing

```bash
alembic upgrade head
rtmonitor-worker --once
```

Migration `0003` requeues Phase 4 events already marked as processed. Run the
worker until `/v1/pipeline/status` reports `active_depth: 0` to finish the
historical backfill.

## Query protection

- Maximum time range: 31 days
- Default page size: 1000
- Maximum page size: 5000
- Ordering: observation time, then event ID
- Pagination: opaque cursor

## Retention

Preview the configured database URL before running cleanup, then prune in
bounded batches:

```bash
rtmonitor-retention --days 30 --batch-size 10000 --max-batches 10
```

Retention deletes normalized samples only. Raw telemetry events remain
available for replay and investigation.
