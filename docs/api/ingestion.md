# Telemetry ingestion API

## Run locally

After installing the project with development dependencies:

```bash
rtmonitor-api
```

The service binds to `127.0.0.1:8000` by default. Interactive API documentation
is available at `http://127.0.0.1:8000/docs`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health/live` | Confirms the process can serve requests |
| `GET` | `/health/ready` | Confirms the service can accept another event |
| `POST` | `/v1/telemetry` | Validates and accepts a schema `1.0` event |

Accepted and duplicate events return HTTP `202`. Invalid contracts return `422`. Requests
with a declared body larger than the configured limit return `413`. When the
database is unavailable or has not been migrated, readiness and ingestion
return `503`; ingestion also returns `Retry-After: 5`.

Every response includes:

- `X-Request-ID` for correlation;
- `X-Process-Time-Ms` for server-side processing time.

Clients may supply `X-Request-ID` using 1–128 letters, numbers, dots,
underscores, or hyphens. Invalid values are replaced with a generated UUID.

## Configuration

| Variable | Default | Description |
| --- | ---: | --- |
| `RTMONITOR_DATABASE_URL` | `sqlite+aiosqlite:///./rtmonitor.db` | SQLAlchemy database URL |
| `RTMONITOR_MAX_REQUEST_BYTES` | `65536` | Maximum declared request size |

The request limit must be a positive integer. Invalid configuration prevents
startup.

## Durability and idempotency

The API commits an event before returning `202`. `event_id` is the primary key,
so retrying an already committed event returns `status: duplicate` without
creating another record. Database schema changes are applied with:

```bash
alembic upgrade head
```

SQLite is supported for local development and tests. PostgreSQL is the
production target. Durable storage does not yet provide the high-throughput
stream buffering planned for the next distributed pipeline phase.

The application checks `Content-Length` to reject declared oversized bodies.
A production ingress proxy must also enforce request-size limits, including
chunked requests, until a streaming body-limit middleware is implemented.

See the [storage guide](../storage/postgresql.md) for PostgreSQL startup and
migration commands.

