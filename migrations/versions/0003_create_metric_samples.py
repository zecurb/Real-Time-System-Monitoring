"""Create normalized time-series metric samples."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    labels_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "metric_samples",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("metric_name", sa.String(length=128), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("labels", labels_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["telemetry_events.event_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "metric_name"),
        sa.UniqueConstraint(
            "event_id",
            "metric_name",
            name="uq_metric_samples_event_metric",
        ),
    )
    op.create_index(
        "ix_metric_samples_node_metric_observed",
        "metric_samples",
        ["node_id", "metric_name", "observed_at", "event_id"],
    )
    op.create_index(
        "ix_metric_samples_observed_at",
        "metric_samples",
        ["observed_at"],
    )

    pipeline_queue = sa.table(
        "telemetry_pipeline_queue",
        sa.column("status", sa.String(length=24)),
        sa.column("attempts", sa.Integer()),
        sa.column("available_at", sa.DateTime(timezone=True)),
        sa.column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.column("leased_by", sa.String(length=128)),
        sa.column("last_error", sa.Text()),
        sa.column("processed_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        pipeline_queue.update()
        .where(pipeline_queue.c.status == "processed")
        .values(
            status="pending",
            attempts=0,
            available_at=sa.func.now(),
            lease_expires_at=None,
            leased_by=None,
            last_error=None,
            processed_at=None,
            updated_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    op.drop_index("ix_metric_samples_observed_at", table_name="metric_samples")
    op.drop_index("ix_metric_samples_node_metric_observed", table_name="metric_samples")
    op.drop_table("metric_samples")
