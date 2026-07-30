# Contributing

## Engineering expectations

Every change should improve or preserve:

- correctness through automated tests;
- observability through structured, actionable signals;
- maintainability through typed interfaces and focused modules;
- resilience through explicit timeouts, bounded work, and failure handling;
- privacy by collecting only data required for the stated purpose.

## Workflow

1. Create a focused branch.
2. Add or update tests with the implementation.
3. Run the local validation commands from the README.
4. Update relevant documentation and architectural decisions.
5. Open a pull request that explains the change, risk, and validation evidence.

Do not commit credentials, raw production logs, hostnames, usernames, IP
addresses, API tokens, or unreviewed personally identifiable information.

