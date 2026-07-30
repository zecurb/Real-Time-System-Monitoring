# Time-series backfill runbook

Use this runbook after migration `0003` or whenever normalized samples must be
reconstructed from raw telemetry.

1. Apply migrations with `alembic upgrade head`.
2. Check `/v1/pipeline/status`; migrated processed events should be pending.
3. Start `rtmonitor-worker`.
4. Watch `active_depth` decrease and `processed` increase.
5. Query a known node and metric for the expected time range.
6. Stop only after the queue reaches zero or document the remaining backlog.

Conflict-safe inserts make replay idempotent. Do not delete raw telemetry to
force a replay.
