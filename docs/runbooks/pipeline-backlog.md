# Pipeline backlog runbook

Use this runbook when `active_depth` grows continuously, retries increase, or
dead-letter events appear.

## Inspect

```bash
curl --fail --silent http://127.0.0.1:8000/v1/pipeline/status | jq .
```

Confirm the API storage readiness:

```bash
curl --fail --silent http://127.0.0.1:8000/health/ready | jq .
```

Review structured worker logs for `pipeline_failed`, the event ID, attempt
number, and outcome.

## Respond

1. If workers are absent, start `rtmonitor-worker`.
2. If PostgreSQL is unavailable, restore it before increasing worker count.
3. If retries are increasing, fix the processor error before scaling workers.
4. If only pending depth is rising and PostgreSQL is healthy, add worker
   processes gradually and monitor database saturation.
5. Preserve dead-letter rows for investigation. Do not silently delete them.

## Recovery behavior

Stopping a worker does not discard its claimed events. After
`RTMONITOR_WORKER_LEASE_SECONDS`, another worker can reclaim them. Processing
is at-least-once, so processors must make repeated execution safe.
