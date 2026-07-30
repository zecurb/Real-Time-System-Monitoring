"""Create durable telemetry events table."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    payload_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "telemetry_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", payload_type, nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_telemetry_events_node_observed",
        "telemetry_events",
        ["node_id", "observed_at"],
    )
    op.create_index(
        "ix_telemetry_events_observed_at",
        "telemetry_events",
        ["observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_events_observed_at", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_node_observed", table_name="telemetry_events")
    op.drop_table("telemetry_events")

