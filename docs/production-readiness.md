# Production-readiness checklist

Release: `v1.0.0`

## Build and quality

- [x] Python linting passes with Ruff.
- [x] Strict Python type checking passes with mypy.
- [x] Python unit and integration tests pass.
- [x] Frontend TypeScript checks pass.
- [x] Frontend tests pass.
- [x] Production frontend build succeeds.
- [x] Nix flake evaluation succeeds.
- [x] CI runs on pull requests and `main`.

## Security and supply chain

- [x] Security reporting and deployment responsibilities are documented.
- [x] Dependabot covers Python, npm, and GitHub Actions.
- [x] CodeQL analyzes Python and JavaScript/TypeScript.
- [x] Workflow permissions are explicitly scoped.
- [x] Secret and sensitive-data handling rules are documented.
- [x] Authentication and authorization requirements are documented for production ingress.

## Reliability and operations

- [x] Health and readiness endpoints are available.
- [x] PostgreSQL is documented as the multi-worker production target.
- [x] Ingestion and queue insertion are transactional and idempotent.
- [x] Worker leases, retries, dead-letter handling, and crash recovery are implemented.
- [x] Historical queries and retention work are bounded.
- [x] Incident lifecycle changes use optimistic revisions and immutable timelines.
- [x] CPU fallback keeps prediction available without a compatible GPU.
- [x] Incident-response procedures are documented.
- [x] Backup, restoration, TLS, secrets, ingress limits, and network isolation are operator requirements.

## Release management

- [x] Project version is `1.0.0`.
- [x] Tagged releases rerun validation and publish build artifacts.
- [x] Changelog and support policy are present.
- [x] Release scope and known production boundaries are documented.

## Known boundaries

Version 1.0.0 is production-oriented reference software, not a hosted managed service. Operators remain responsible for identity, authorization, TLS termination, secrets management, rate limiting, capacity testing for their workload, database backup and restoration, network policy, compliance controls, and alert delivery integrations.