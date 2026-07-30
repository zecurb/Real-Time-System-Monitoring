# Incident console

## Development

Run the API and worker first. In a third shell:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

## Operator workflow

1. Confirm the header reports `Systems ready`.
2. Check active queue, retry, and dead-letter counts.
3. Select a monitored node.
4. Select a metric and a one-, six-, or 24-hour window.
5. Hover or focus the historical chart points for exact timestamps and values.
6. If the degraded banner appears, preserve the last-known view and investigate
   API readiness before trusting freshness.

## Production build

```bash
cd frontend
npm ci
npm run check
npm test
npm run build
```

Serve `frontend/dist` as static content. Route `/health` and `/v1` to the
FastAPI service on the same public origin. Do not expose the Vite development
server as a production service.

## Failure behavior

- Requests are aborted when a selection changes.
- A failed refresh does not blank the last-known dashboard state.
- An explicit alert states that live data is interrupted.
- Empty time windows display an intentional empty state.
- Retry and dead-letter counts receive warning emphasis.
