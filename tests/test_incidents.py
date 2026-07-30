from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from test_api import valid_event

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage import (
    IncidentConflictError,
    IncidentSignal,
    SqlAlchemyEventStore,
)


class IncidentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_incident_lifecycle_is_deduplicated_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            database_path = Path(temp_directory) / "telemetry.db"
            store = SqlAlchemyEventStore(f"sqlite+aiosqlite:///{database_path}")
            await store.create_schema_for_tests()
            observed_at = datetime(2026, 7, 30, 6, tzinfo=UTC)

            first_payload = valid_event()
            first_payload["observed_at"] = observed_at.isoformat()
            first = TelemetryEventRequest.model_validate(first_payload)
            await store.store(first)
            warning = IncidentSignal(
                event_id=str(first.event_id),
                node_id=first.node_id,
                metric_name="memory.used.percent",
                observed_at=observed_at,
                source="anomaly",
                severity="warning",
                title="Memory anomaly",
                summary="Memory deviated from its baseline",
                details={"score": 4.2},
            )

            self.assertEqual(await store.record_incident_signals([warning]), 1)
            self.assertEqual(await store.record_incident_signals([warning]), 0)
            incidents = await store.list_incidents(
                status="open",
                node_id=first.node_id,
                limit=10,
            )
            self.assertEqual(len(incidents), 1)
            incident = incidents[0]
            self.assertEqual(incident.occurrence_count, 1)
            self.assertEqual(incident.revision, 1)
            self.assertEqual(incident.severity, "warning")

            critical = IncidentSignal(
                event_id=str(first.event_id),
                node_id=first.node_id,
                metric_name="memory.used.percent",
                observed_at=observed_at,
                source="forecast",
                severity="critical",
                title="Memory exhaustion risk",
                summary="Memory is forecast to cross its threshold",
                details={"hours_to_threshold": 1.5},
            )
            self.assertEqual(await store.record_incident_signals([critical]), 1)
            incident = (
                await store.list_incidents(
                    status="open",
                    node_id=first.node_id,
                    limit=10,
                )
            )[0]
            self.assertEqual(incident.occurrence_count, 2)
            self.assertEqual(incident.severity, "critical")
            self.assertEqual(incident.revision, 2)

            acknowledged = await store.transition_incident(
                incident_id=incident.incident_id,
                action="acknowledge",
                actor="on-call",
                note="Investigating memory pressure",
                expected_revision=2,
            )
            self.assertEqual(acknowledged.status, "acknowledged")
            self.assertEqual(acknowledged.owner, "on-call")
            self.assertEqual(acknowledged.revision, 3)
            with self.assertRaises(IncidentConflictError):
                await store.transition_incident(
                    incident_id=incident.incident_id,
                    action="resolve",
                    actor="on-call",
                    note="Scaled the service",
                    expected_revision=2,
                )

            resolved = await store.transition_incident(
                incident_id=incident.incident_id,
                action="resolve",
                actor="on-call",
                note="Scaled the service",
                expected_revision=3,
            )
            self.assertEqual(resolved.status, "resolved")
            self.assertEqual(resolved.revision, 4)

            second_payload = valid_event()
            second_payload["event_id"] = "24d6a69e-e40a-42a1-9b45-549d8a949d59"
            second_payload["observed_at"] = (observed_at + timedelta(minutes=5)).isoformat()
            second = TelemetryEventRequest.model_validate(second_payload)
            await store.store(second)
            reopened_signal = IncidentSignal(
                event_id=str(second.event_id),
                node_id=second.node_id,
                metric_name="memory.used.percent",
                observed_at=second.observed_at,
                source="anomaly",
                severity="critical",
                title="Memory anomaly returned",
                summary="Memory pressure returned after resolution",
                details={"score": 9.0},
            )
            self.assertEqual(await store.record_incident_signals([reopened_signal]), 1)
            reopened = (
                await store.list_incidents(
                    status="open",
                    node_id=first.node_id,
                    limit=10,
                )
            )[0]
            self.assertEqual(reopened.status, "open")
            self.assertIsNone(reopened.owner)
            self.assertEqual(reopened.occurrence_count, 3)
            self.assertEqual(reopened.revision, 5)

            timeline = await store.incident_timeline(
                incident_id=incident.incident_id,
                limit=20,
            )
            self.assertEqual(
                [event.action for event in timeline],
                ["opened", "escalated", "acknowledged", "resolved", "reopened"],
            )
            await store.close()


if __name__ == "__main__":
    unittest.main()
