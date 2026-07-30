# Anomaly detection

The worker normalizes every telemetry event and evaluates six operational
signals: load averages, process count, memory utilization, and disk
utilization. It compares the current value with up to 120 prior samples from
the same node and metric over seven days.

Query recent findings:

```bash
curl --get http://127.0.0.1:8000/v1/anomalies \
  --data-urlencode "start=2026-07-30T00:00:00+00:00" \
  --data-urlencode "end=2026-07-31T00:00:00+00:00" |
  jq .
```

An empty list can mean the system is healthy or that fewer than five baseline
samples exist. Operators should use the returned baseline, dispersion, score,
and sample count when judging a finding.

The stored dispersion is the greater of the measured MAD and a conservative
metric-specific noise floor. This keeps changes such as one additional process
or sub-percentage memory movement from becoming false critical findings.
