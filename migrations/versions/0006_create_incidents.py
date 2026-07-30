"""Create correlated incidents, evidence signals, and audit timeline."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("dedup_key", sa.String(300), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("incident_id"),
        sa.UniqueConstraint("dedup_key"),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'critical')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint("occurrence_count >= 0", name="ck_incidents_occurrence_count"),
        sa.CheckConstraint("revision >= 0", name="ck_incidents_revision"),
    )
    op.create_index(
        "ix_incidents_status_severity_updated",
        "incidents",
        ["status", "severity", "updated_at"],
    )
    op.create_index("ix_incidents_node_updated", "incidents", ["node_id", "updated_at"])
    op.create_table(
        "incident_signals",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["telemetry_events.event_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("event_id", "metric_name", "source"),
        sa.CheckConstraint(
            "source IN ('anomaly', 'forecast')",
            name="ck_incident_signals_source",
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'critical')",
            name="ck_incident_signals_severity",
        ),
    )
    op.create_index(
        "ix_incident_signals_incident_observed",
        "incident_signals",
        ["incident_id", "observed_at"],
    )
    op.create_table(
        "incident_timeline",
        sa.Column("timeline_id", sa.String(36), nullable=False),
        sa.Column("incident_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["incidents.incident_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("timeline_id"),
        sa.CheckConstraint(
            "action IN ('opened', 'escalated', 'acknowledged', 'resolved', 'reopened')",
            name="ck_incident_timeline_action",
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR "
            "from_status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incident_timeline_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incident_timeline_to_status",
        ),
    )
    op.create_index(
        "ix_incident_timeline_incident_occurred",
        "incident_timeline",
        ["incident_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_incident_timeline_incident_occurred",
        table_name="incident_timeline",
    )
    op.drop_table("incident_timeline")
    op.drop_index(
        "ix_incident_signals_incident_observed",
        table_name="incident_signals",
    )
    op.drop_table("incident_signals")
    op.drop_index("ix_incidents_node_updated", table_name="incidents")
    op.drop_index("ix_incidents_status_severity_updated", table_name="incidents")
    op.drop_table("incidents")
