# Security Policy

## Reporting

Do not open a public issue for a vulnerability that could expose credentials,
private telemetry, or user data. Contact the repository owner privately.

## Data-handling principles

- Collect the minimum telemetry needed.
- Do not collect keystrokes, passwords, message contents, or authentication
  tokens.
- Treat hostnames, process arguments, IP addresses, and logs as potentially
  sensitive.
- Redact sensitive fields before events leave a monitored host.
- Keep secrets outside source control and inject them at runtime.
- Authenticate and encrypt networked telemetry before multi-host deployment.

The Phase 1 collector emits a generated node identifier by default rather than
a hostname or username.

