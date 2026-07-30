# ADR 0001: Begin with a CPU-first Linux collector

- Status: Accepted
- Date: 2026-07-30

## Context

The target home-lab includes two computers without working GPUs. Telemetry
collection should also remain lightweight enough to run on ordinary production
hosts without competing with monitored workloads.

## Decision

The initial collector uses Python 3.12 and Linux kernel interfaces under
`/proc`. It has no runtime dependencies and no GPU requirement.

## Consequences

- Deployment is small and portable across Linux hosts.
- The implementation exposes how Linux reports resource data.
- Windows and macOS require separate collector adapters later.
- Advanced model training may run on separate hardware, but inference must
  retain a CPU-compatible baseline.

