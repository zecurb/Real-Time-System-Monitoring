# PostgreSQL storage

PostgreSQL is the production storage target. SQLite remains available for
local development and automated durability tests.

## Local PostgreSQL with Compose

The included Compose configuration binds PostgreSQL only to loopback:

```bash
docker compose up -d postgres
docker compose ps
```

Set the development connection string:

```bash
export RTMONITOR_DATABASE_URL="postgresql+asyncpg://rtmonitor:rtmonitor-development-only@127.0.0.1:5432/rtmonitor"
```

Apply the schema and start the API:

```bash
alembic upgrade head
rtmonitor-api
```

The password in `compose.yaml` is for isolated local development only. Never
reuse it in a deployed environment. Production credentials must be injected
through a secrets manager and connections must use transport encryption.

## Local SQLite

For a lightweight test without containers:

```bash
export RTMONITOR_DATABASE_URL="sqlite+aiosqlite:///./rtmonitor.db"
alembic upgrade head
rtmonitor-api
```

The generated database and its journal files are ignored by Git.

## Operational behavior

- Readiness queries the telemetry table, so a reachable but unmigrated database
  is not reported as ready.
- Events are committed before the API returns `202`.
- Duplicate `event_id` values are acknowledged without adding another row.
- Indexed `node_id` and `observed_at` fields support future historical queries.
- The original validated event remains available as JSON for evolving analysis.

