"""Create the durable telemetry processing queue."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_pipeline_queue",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leased_by", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["telemetry_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_pipeline_queue_claim",
        "telemetry_pipeline_queue",
        ["status", "available_at", "lease_expires_at"],
    )

    telemetry_events = sa.table(
        "telemetry_events",
        sa.column("event_id", sa.String(length=36)),
        sa.column("received_at", sa.DateTime(timezone=True)),
    )
    pipeline_queue = sa.table(
        "telemetry_pipeline_queue",
        sa.column("event_id", sa.String(length=36)),
        sa.column("status", sa.String(length=24)),
        sa.column("attempts", sa.Integer()),
        sa.column("available_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        pipeline_queue.insert().from_select(
            [
                "event_id",
                "status",
                "attempts",
                "available_at",
                "created_at",
                "updated_at",
            ],
            sa.select(
                telemetry_events.c.event_id,
                sa.literal("pending"),
                sa.literal(0),
                telemetry_events.c.received_at,
                telemetry_events.c.received_at,
                telemetry_events.c.received_at,
            ),
        )
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_queue_claim", table_name="telemetry_pipeline_queue")
    op.drop_table("telemetry_pipeline_queue")
