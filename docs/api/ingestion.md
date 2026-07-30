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

Accepted events return HTTP `202`. Invalid contracts return `422`. Requests
with a declared body larger than the configured limit return `413`. When the
bounded buffer is full, ingestion and readiness return `503`; ingestion also
returns `Retry-After: 5`.

Every response includes:

- `X-Request-ID` for correlation;
- `X-Process-Time-Ms` for server-side processing time.

Clients may supply `X-Request-ID` using 1–128 letters, numbers, dots,
underscores, or hyphens. Invalid values are replaced with a generated UUID.

## Configuration

| Variable | Default | Description |
| --- | ---: | --- |
| `RTMONITOR_BUFFER_CAPACITY` | `10000` | Maximum events held in memory |
| `RTMONITOR_MAX_REQUEST_BYTES` | `65536` | Maximum declared request size |

Both values must be positive integers. Invalid configuration prevents startup.

## Current durability boundary

The Phase 2 buffer is in memory. Events are lost if the process restarts, and
the buffer does not drain. This is intentional and must not be mistaken for
durable production storage. Phase 3 will replace it with durable transport and
consumer acknowledgements.

The application checks `Content-Length` to reject declared oversized bodies.
A production ingress proxy must also enforce request-size limits, including
chunked requests, until a streaming body-limit middleware is implemented.

