# Runbook: collector is not emitting telemetry

## Symptoms

- No JSON events appear on standard output.
- The process exits with status 1.
- A structured error appears on standard error.

## Checks

1. Confirm the host is Linux and `/proc` is mounted.
2. Run `rtmonitor --once` and capture standard error.
3. Verify the service account can read `/proc/loadavg`, `/proc/uptime`,
   `/proc/meminfo`, and `/proc/net/dev`.
4. Confirm the configured disk path exists.
5. Check whether the service was terminated intentionally.

## Recovery

Restore access to the required kernel interfaces and restart the collector.
Do not bypass access controls or run the process as root solely to hide a
permissions problem.

