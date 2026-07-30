"""Create durable resource forecasts."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecasts",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("slope_per_hour", sa.Float(), nullable=False),
        sa.Column("hours_to_threshold", sa.Float(), nullable=False),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("r_squared", sa.Float(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("risk", sa.String(16), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("backtest_error", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("fallback_reason", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["telemetry_events.event_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", "metric_name"),
    )
    op.create_index("ix_forecasts_node_predicted", "forecasts", ["node_id", "predicted_at"])
    op.create_index("ix_forecasts_risk_predicted", "forecasts", ["risk", "predicted_at"])


def downgrade() -> None:
    op.drop_index("ix_forecasts_risk_predicted", table_name="forecasts")
    op.drop_index("ix_forecasts_node_predicted", table_name="forecasts")
    op.drop_table("forecasts")
