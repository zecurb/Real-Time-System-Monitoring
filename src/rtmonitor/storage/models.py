"""SQLAlchemy database models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


class PipelineQueueRecord(Base):
    __tablename__ = "telemetry_pipeline_queue"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    leased_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "ix_pipeline_queue_claim",
            "status",
            "available_at",
            "lease_expires_at",
        ),
    )


class MetricSampleRecord(Base):
    __tablename__ = "metric_samples"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    labels: Mapped[dict[str, str]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "metric_name", name="uq_metric_samples_event_metric"),
        Index(
            "ix_metric_samples_node_metric_observed",
            "node_id",
            "metric_name",
            "observed_at",
            "event_id",
        ),
        Index("ix_metric_samples_observed_at", "observed_at"),
    )


class AnomalyRecord(Base):
    __tablename__ = "anomalies"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline: Mapped[float] = mapped_column(Float, nullable=False)
    dispersion: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_anomalies_node_observed", "node_id", "observed_at"),
        Index("ix_anomalies_severity_observed", "severity", "observed_at"),
    )


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    slope_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    hours_to_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    r_squared: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    backtest_error: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_forecasts_node_predicted", "node_id", "predicted_at"),
        Index("ix_forecasts_risk_predicted", "risk", "predicted_at"),
    )


class IncidentRecord(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dedup_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "severity IN ('warning', 'critical')",
            name="ck_incidents_severity",
        ),
        CheckConstraint("occurrence_count >= 0", name="ck_incidents_occurrence_count"),
        CheckConstraint("revision >= 0", name="ck_incidents_revision"),
        Index("ix_incidents_status_severity_updated", "status", "severity", "updated_at"),
        Index("ix_incidents_node_updated", "node_id", "updated_at"),
    )


class IncidentSignalRecord(Base):
    __tablename__ = "incident_signals"

    event_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("telemetry_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source IN ('anomaly', 'forecast')",
            name="ck_incident_signals_source",
        ),
        CheckConstraint(
            "severity IN ('warning', 'critical')",
            name="ck_incident_signals_severity",
        ),
        Index("ix_incident_signals_incident_observed", "incident_id", "observed_at"),
    )


class IncidentTimelineRecord(Base):
    __tablename__ = "incident_timeline"

    timeline_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    from_status: Mapped[str | None] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "action IN ('opened', 'escalated', 'acknowledged', 'resolved', 'reopened')",
            name="ck_incident_timeline_action",
        ),
        CheckConstraint(
            "from_status IS NULL OR "
            "from_status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incident_timeline_from_status",
        ),
        CheckConstraint(
            "to_status IN ('open', 'acknowledged', 'resolved')",
            name="ck_incident_timeline_to_status",
        ),
        Index("ix_incident_timeline_incident_occurred", "incident_id", "occurred_at"),
    )
