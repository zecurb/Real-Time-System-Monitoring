# Incident response

## Triage

1. Confirm `/health/ready` reports available storage and the dashboard is fresh.
2. Review critical open incidents before warnings.
3. Check the node, metric, occurrence count, latest evidence, and related
   anomaly or forecast details.
4. Acknowledge the incident with your operator identity before mitigation.

## Mitigation

Use the least disruptive reversible action that addresses the evidence. Check
historical metrics, pipeline backlog, host logs, deployments, and dependency
health. Do not treat a forecast as proof of failure; validate the trend and its
confidence first.

## Resolution

Resolve only after the metric is stable and the mitigation has been verified.
Write a specific resolution note describing what changed. If another operator
updated the incident, refresh after the revision conflict and reassess rather
than retrying blindly.

New evidence reopens a resolved incident automatically. Treat reopening as a
failed or incomplete mitigation and review the preserved timeline.

## Escalation

Escalate when impact grows, the evidence becomes critical, the incident spans
multiple nodes, or the responder lacks access to mitigate it. Preserve event
IDs, timestamps, and operator actions for the post-incident review.
