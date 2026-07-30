"""Create explainable anomaly findings."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anomalies",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("baseline", sa.Float(), nullable=False),
        sa.Column("dispersion", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["telemetry_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "metric_name"),
    )
    op.create_index(
        "ix_anomalies_node_observed",
        "anomalies",
        ["node_id", "observed_at"],
    )
    op.create_index(
        "ix_anomalies_severity_observed",
        "anomalies",
        ["severity", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_anomalies_severity_observed", table_name="anomalies")
    op.drop_index("ix_anomalies_node_observed", table_name="anomalies")
    op.drop_table("anomalies")
