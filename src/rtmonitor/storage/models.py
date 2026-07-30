"""SQLAlchemy database models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TelemetryRecord(Base):
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_telemetry_events_node_observed", "node_id", "observed_at"),
        Index("ix_telemetry_events_observed_at", "observed_at"),
    )
