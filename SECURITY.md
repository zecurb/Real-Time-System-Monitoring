# Security Policy

## Supported version

Security fixes are applied to the latest release on `main`. Version `1.0.x` is the currently supported release line.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting feature for this repository and include:

- the affected component and version;
- reproduction steps or a proof of concept;
- the expected security impact;
- any suggested mitigation.

Reports will be acknowledged as soon as practical. Valid reports are investigated privately and disclosed after a patch is available.

## Data-handling principles

- Collect only telemetry required for the stated reliability purpose.
- Do not collect keystrokes, passwords, message contents, or authentication tokens.
- Treat hostnames, process arguments, IP addresses, logs, and identifiers as sensitive.
- Redact sensitive fields before events leave a monitored host.
- Keep secrets outside source control and inject them at runtime.

## Production deployment responsibilities

Operators must:

- authenticate and authorize incident mutation endpoints at the ingress layer;
- derive trusted operator identity instead of accepting an untrusted actor string;
- store credentials in a secrets manager;
- require encrypted network connections;
- restrict database and API network exposure;
- enforce request-size and rate limits at the reverse proxy;
- keep dependencies and base images patched;
- back up PostgreSQL and test restoration;
- enable secret scanning, push protection, Dependabot, and branch protection.

Never commit production credentials, raw production logs, private hostnames, IP addresses, tokens, or unreviewed personal information.