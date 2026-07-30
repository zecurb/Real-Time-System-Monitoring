"""SQLAlchemy-backed telemetry event store."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import and_, case, delete, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.sql import Executable

from rtmonitor.anomaly import MINIMUM_DISPERSION, SCORABLE_METRICS, robust_anomaly_score
from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.execution import resolve_execution_provider
from rtmonitor.forecast import FORECAST_THRESHOLDS, ForecastPoint, forecast_threshold
from rtmonitor.metrics import metric_values
from rtmonitor.storage.base import (
    Anomaly,
    Forecast,
    Incident,
    IncidentConflictError,
    IncidentNotFoundError,
    IncidentSignal,
    IncidentTimelineEvent,
    InvalidIncidentTransitionError,
    MetricSample,
    NodeSummary,
    QueueLease,
    QueueStats,
    QueueStatus,
    StoreResult,
)
from rtmonitor.storage.models import (
    AnomalyRecord,
    Base,
    ForecastRecord,
    IncidentRecord,
    IncidentSignalRecord,
    IncidentTimelineRecord,
    MetricSampleRecord,
    PipelineQueueRecord,
    TelemetryRecord,
)

FORECAST_HISTORY_LIMIT = 2048


class StorageUnavailableError(RuntimeError):
    """Raised when an event cannot be durably committed."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _incident(record: IncidentRecord) -> Incident:
    return Incident(
        incident_id=record.incident_id,
        node_id=record.node_id,
        metric_name=record.metric_name,
        status=cast(Literal["open", "acknowledged", "resolved"], record.status),
        severity=cast(Literal["warning", "critical"], record.severity),
        title=record.title,
        summary=record.summary,
        occurrence_count=record.occurrence_count,
        first_seen=_utc(record.first_seen),
        last_seen=_utc(record.last_seen),
        owner=record.owner,
        acknowledged_at=(
            _utc(record.acknowledged_at) if record.acknowledged_at is not None else None
        ),
        resolved_at=_utc(record.resolved_at) if record.resolved_at is not None else None,
        resolution_note=record.resolution_note,
        revision=record.revision,
        updated_at=_utc(record.updated_at),
    )


class SqlAlchemyEventStore:
    def __init__(self, database_url: str, *, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or create_async_engine(
            database_url,
            pool_pre_ping=True,
        )
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def store(self, event: TelemetryEventRequest) -> StoreResult:
        now = datetime.now(UTC)
        record = TelemetryRecord(
            event_id=str(event.event_id),
            schema_version=event.schema_version,
            node_id=event.node_id,
            observed_at=event.observed_at,
            received_at=now,
            payload=event.model_dump(mode="json"),
        )
        queue_record = PipelineQueueRecord(
            event_id=str(event.event_id),
            status=QueueStatus.PENDING,
            attempts=0,
            available_at=now,
            created_at=now,
            updated_at=now,
        )
        async with self._sessions() as session:
            session.add_all((record, queue_record))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return StoreResult.DUPLICATE
            except SQLAlchemyError as exc:
                await session.rollback()
                raise StorageUnavailableError("telemetry storage failed") from exc
        return StoreResult.CREATED

    async def count(self) -> int:
        async with self._sessions() as session:
            result = await session.scalar(select(func.count()).select_from(TelemetryRecord))
            return int(result or 0)

    async def queue_depth(self) -> int:
        active_statuses = (
            QueueStatus.PENDING,
            QueueStatus.PROCESSING,
            QueueStatus.RETRY,
        )
        async with self._sessions() as session:
            result = await session.scalar(
                select(func.count())
                .select_from(PipelineQueueRecord)
                .where(PipelineQueueRecord.status.in_(active_statuses))
            )
            return int(result or 0)

    async def queue_stats(self) -> QueueStats:
        counts = {status.value: 0 for status in QueueStatus}
        async with self._sessions() as session:
            rows = (
                await session.execute(
                    select(PipelineQueueRecord.status, func.count()).group_by(
                        PipelineQueueRecord.status
                    )
                )
            ).all()
        for status, count in rows:
            counts[str(status)] = int(count)
        return QueueStats(
            pending=counts[QueueStatus.PENDING],
            processing=counts[QueueStatus.PROCESSING],
            retry=counts[QueueStatus.RETRY],
            processed=counts[QueueStatus.PROCESSED],
            dead_letter=counts[QueueStatus.DEAD_LETTER],
        )

    async def claim(
        self,
        *,
        worker_id: str,
        batch_size: int,
        lease_seconds: int,
    ) -> list[QueueLease]:
        now = datetime.now(UTC)
        claimable = or_(
            and_(
                PipelineQueueRecord.status.in_((QueueStatus.PENDING, QueueStatus.RETRY)),
                PipelineQueueRecord.available_at <= now,
            ),
            and_(
                PipelineQueueRecord.status == QueueStatus.PROCESSING,
                PipelineQueueRecord.lease_expires_at <= now,
            ),
        )
        async with self._sessions() as session:
            statement = (
                select(PipelineQueueRecord, TelemetryRecord.payload)
                .join(TelemetryRecord, TelemetryRecord.event_id == PipelineQueueRecord.event_id)
                .where(claimable)
                .order_by(PipelineQueueRecord.available_at, PipelineQueueRecord.event_id)
                .limit(batch_size)
            )
            if self._engine.dialect.name == "postgresql":
                statement = statement.with_for_update(skip_locked=True, of=PipelineQueueRecord)

            rows = (await session.execute(statement)).all()
            leases: list[QueueLease] = []
            lease_expires_at = now + timedelta(seconds=lease_seconds)
            for queue_record, payload in rows:
                queue_record.status = QueueStatus.PROCESSING
                queue_record.attempts += 1
                queue_record.leased_by = worker_id
                queue_record.lease_expires_at = lease_expires_at
                queue_record.updated_at = now
                leases.append(
                    QueueLease(
                        event_id=queue_record.event_id,
                        payload=dict(payload),
                        attempt=queue_record.attempts,
                    )
                )
            try:
                await session.commit()
            except SQLAlchemyError as exc:
                await session.rollback()
                raise StorageUnavailableError("queue claim failed") from exc
            return leases

    async def complete(self, *, event_id: str, worker_id: str) -> bool:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            result = await session.execute(
                update(PipelineQueueRecord)
                .where(
                    PipelineQueueRecord.event_id == event_id,
                    PipelineQueueRecord.status == QueueStatus.PROCESSING,
                    PipelineQueueRecord.leased_by == worker_id,
                )
                .values(
                    status=QueueStatus.PROCESSED,
                    processed_at=now,
                    lease_expires_at=None,
                    leased_by=None,
                    last_error=None,
                    updated_at=now,
                )
                .returning(PipelineQueueRecord.event_id)
            )
            await session.commit()
            return result.scalar_one_or_none() is not None

    async def fail(
        self,
        *,
        event_id: str,
        worker_id: str,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> QueueStatus | None:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            record = await session.scalar(
                select(PipelineQueueRecord).where(
                    PipelineQueueRecord.event_id == event_id,
                    PipelineQueueRecord.status == QueueStatus.PROCESSING,
                    PipelineQueueRecord.leased_by == worker_id,
                )
            )
            if record is None:
                return None
            if record.attempts >= max_attempts:
                record.status = QueueStatus.DEAD_LETTER
                record.available_at = now
            else:
                record.status = QueueStatus.RETRY
                record.available_at = now + timedelta(seconds=retry_delay_seconds)
            record.lease_expires_at = None
            record.leased_by = None
            record.last_error = error[:2048]
            record.updated_at = now
            await session.commit()
            return QueueStatus(record.status)

    async def queue_status(self, event_id: str) -> QueueStatus | None:
        async with self._sessions() as session:
            value = await session.scalar(
                select(PipelineQueueRecord.status).where(PipelineQueueRecord.event_id == event_id)
            )
            return QueueStatus(value) if value is not None else None

    async def write_metric_samples(self, payload: dict[str, object]) -> int:
        event = TelemetryEventRequest.model_validate(payload)
        metrics = event.metrics
        values = metric_values(event)
        event_id = str(event.event_id)
        now = datetime.now(UTC)
        rows = [
            {
                "event_id": event_id,
                "node_id": event.node_id,
                "metric_name": metric_name,
                "observed_at": event.observed_at,
                "value": value,
                "labels": ({"path": metrics.disk.path} if metric_name.startswith("disk.") else {}),
                "created_at": now,
            }
            for metric_name, value in values.items()
        ]
        statement: Executable
        if self._engine.dialect.name == "postgresql":
            statement = (
                postgresql_insert(MetricSampleRecord)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
            )
        elif self._engine.dialect.name == "sqlite":
            statement = (
                sqlite_insert(MetricSampleRecord)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
            )
        else:
            raise StorageUnavailableError("unsupported metric storage dialect")
        async with self._sessions() as session:
            try:
                await session.execute(statement)
                await session.commit()
            except SQLAlchemyError as exc:
                await session.rollback()
                raise StorageUnavailableError("metric sample write failed") from exc
        return len(rows)

    async def process_telemetry(self, payload: dict[str, object]) -> None:
        """Normalize telemetry and persist derived risk signals idempotently."""
        event = TelemetryEventRequest.model_validate(payload)
        await self.write_metric_samples(payload)
        values = metric_values(event)
        provider = resolve_execution_provider()
        forecasts: list[dict[str, object]] = []
        incident_signals: list[IncidentSignal] = []
        for metric_name, threshold in FORECAST_THRESHOLDS.items():
            history = await self.query_recent_metric_samples(
                node_id=event.node_id,
                metric_name=metric_name,
                start=event.observed_at - timedelta(days=7),
                end=event.observed_at + timedelta(microseconds=1),
                limit=FORECAST_HISTORY_LIMIT,
            )
            forecast_result = forecast_threshold(
                [
                    ForecastPoint(sample.observed_at, sample.value)
                    for sample in history
                ],
                threshold=threshold,
                provider=provider,
            )
            if forecast_result is not None:
                forecasts.append(
                    {
                        "event_id": str(event.event_id),
                        "node_id": event.node_id,
                        "metric_name": metric_name,
                        "observed_at": event.observed_at,
                        "current_value": forecast_result.current_value,
                        "threshold": forecast_result.threshold,
                        "slope_per_hour": forecast_result.slope_per_hour,
                        "hours_to_threshold": forecast_result.hours_to_threshold,
                        "predicted_at": forecast_result.predicted_at,
                        "r_squared": forecast_result.r_squared,
                        "confidence": forecast_result.confidence,
                        "risk": forecast_result.risk,
                        "sample_count": forecast_result.sample_count,
                        "backtest_error": forecast_result.backtest_error,
                        "provider": forecast_result.provider,
                        "fallback_reason": forecast_result.fallback_reason,
                        "created_at": datetime.now(UTC),
                    }
                )
                if forecast_result.risk in {"warning", "critical"}:
                    incident_signals.append(
                        IncidentSignal(
                            event_id=str(event.event_id),
                            node_id=event.node_id,
                            metric_name=metric_name,
                            observed_at=event.observed_at,
                            source="forecast",
                            severity=cast(
                                Literal["warning", "critical"],
                                forecast_result.risk,
                            ),
                            title=f"{metric_name} exhaustion risk on {event.node_id}",
                            summary=(
                                f"Expected to cross {forecast_result.threshold:.1f} "
                                f"in {forecast_result.hours_to_threshold:.1f} hours"
                            ),
                            details={
                                "current_value": forecast_result.current_value,
                                "threshold": forecast_result.threshold,
                                "hours_to_threshold": forecast_result.hours_to_threshold,
                                "r_squared": forecast_result.r_squared,
                                "provider": forecast_result.provider,
                            },
                        )
                    )
        if forecasts:
            forecast_insert: Executable
            if self._engine.dialect.name == "postgresql":
                forecast_insert = (
                    postgresql_insert(ForecastRecord)
                    .values(forecasts)
                    .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
                )
            elif self._engine.dialect.name == "sqlite":
                forecast_insert = (
                    sqlite_insert(ForecastRecord)
                    .values(forecasts)
                    .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
                )
            else:
                raise StorageUnavailableError("unsupported forecast storage dialect")
            async with self._sessions() as session:
                try:
                    await session.execute(forecast_insert)
                    await session.commit()
                except SQLAlchemyError as exc:
                    await session.rollback()
                    raise StorageUnavailableError("forecast write failed") from exc
        findings: list[dict[str, object]] = []
        for metric_name in SCORABLE_METRICS:
            history = await self.query_recent_metric_samples(
                node_id=event.node_id,
                metric_name=metric_name,
                start=event.observed_at - timedelta(days=7),
                end=event.observed_at,
                limit=120,
            )
            anomaly_result = robust_anomaly_score(
                values[metric_name],
                [sample.value for sample in history],
                minimum_dispersion=MINIMUM_DISPERSION[metric_name],
            )
            if anomaly_result is None:
                continue
            findings.append(
                {
                    "event_id": str(event.event_id),
                    "node_id": event.node_id,
                    "metric_name": metric_name,
                    "observed_at": event.observed_at,
                    "value": values[metric_name],
                    "baseline": anomaly_result.baseline,
                    "dispersion": anomaly_result.dispersion,
                    "score": anomaly_result.score,
                    "severity": anomaly_result.severity,
                    "sample_count": anomaly_result.sample_count,
                    "created_at": datetime.now(UTC),
                }
            )
            incident_signals.append(
                IncidentSignal(
                    event_id=str(event.event_id),
                    node_id=event.node_id,
                    metric_name=metric_name,
                    observed_at=event.observed_at,
                    source="anomaly",
                    severity=cast(
                        Literal["warning", "critical"],
                        anomaly_result.severity,
                    ),
                    title=f"{metric_name} anomaly on {event.node_id}",
                    summary=(
                        f"Observed {values[metric_name]:.2f} against "
                        f"{anomaly_result.baseline:.2f} baseline"
                    ),
                    details={
                        "value": values[metric_name],
                        "baseline": anomaly_result.baseline,
                        "dispersion": anomaly_result.dispersion,
                        "score": anomaly_result.score,
                    },
                )
            )
        if findings:
            statement: Executable
            if self._engine.dialect.name == "postgresql":
                statement = (
                    postgresql_insert(AnomalyRecord)
                    .values(findings)
                    .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
                )
            elif self._engine.dialect.name == "sqlite":
                statement = (
                    sqlite_insert(AnomalyRecord)
                    .values(findings)
                    .on_conflict_do_nothing(index_elements=["event_id", "metric_name"])
                )
            else:
                raise StorageUnavailableError("unsupported anomaly storage dialect")
            async with self._sessions() as session:
                try:
                    await session.execute(statement)
                    await session.commit()
                except SQLAlchemyError as exc:
                    await session.rollback()
                    raise StorageUnavailableError("anomaly write failed") from exc
        if incident_signals:
            await self.record_incident_signals(incident_signals)

    async def record_incident_signals(self, signals: list[IncidentSignal]) -> int:
        """Group risk evidence into durable, deduplicated incidents."""
        inserted_signals = 0
        async with self._sessions() as session:
            try:
                for signal in signals:
                    now = datetime.now(UTC)
                    dedup_key = f"{signal.node_id}|{signal.metric_name}"
                    incident_id = str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"rtmonitor://incident/{dedup_key}",
                        )
                    )
                    incident_values = {
                        "incident_id": incident_id,
                        "dedup_key": dedup_key,
                        "node_id": signal.node_id,
                        "metric_name": signal.metric_name,
                        "status": "open",
                        "severity": signal.severity,
                        "title": signal.title,
                        "summary": signal.summary,
                        "occurrence_count": 0,
                        "first_seen": signal.observed_at,
                        "last_seen": signal.observed_at,
                        "revision": 0,
                        "created_at": now,
                        "updated_at": now,
                    }
                    if self._engine.dialect.name == "postgresql":
                        incident_insert: Executable = (
                            postgresql_insert(IncidentRecord)
                            .values(incident_values)
                            .on_conflict_do_nothing(index_elements=["dedup_key"])
                        )
                        signal_insert: Executable = (
                            postgresql_insert(IncidentSignalRecord)
                            .values(
                                event_id=signal.event_id,
                                metric_name=signal.metric_name,
                                source=signal.source,
                                incident_id=incident_id,
                                observed_at=signal.observed_at,
                                severity=signal.severity,
                                details=signal.details,
                                created_at=now,
                            )
                            .on_conflict_do_nothing(
                                index_elements=["event_id", "metric_name", "source"]
                            )
                            .returning(IncidentSignalRecord.event_id)
                        )
                    elif self._engine.dialect.name == "sqlite":
                        incident_insert = (
                            sqlite_insert(IncidentRecord)
                            .values(incident_values)
                            .on_conflict_do_nothing(index_elements=["dedup_key"])
                        )
                        signal_insert = (
                            sqlite_insert(IncidentSignalRecord)
                            .values(
                                event_id=signal.event_id,
                                metric_name=signal.metric_name,
                                source=signal.source,
                                incident_id=incident_id,
                                observed_at=signal.observed_at,
                                severity=signal.severity,
                                details=signal.details,
                                created_at=now,
                            )
                            .on_conflict_do_nothing(
                                index_elements=["event_id", "metric_name", "source"]
                            )
                            .returning(IncidentSignalRecord.event_id)
                        )
                    else:
                        raise StorageUnavailableError(
                            "unsupported incident storage dialect"
                        )
                    await session.execute(incident_insert)
                    inserted = await session.scalar(signal_insert)
                    if inserted is None:
                        continue

                    incident_statement = select(IncidentRecord).where(
                        IncidentRecord.incident_id == incident_id
                    )
                    if self._engine.dialect.name == "postgresql":
                        incident_statement = incident_statement.with_for_update()
                    incident = await session.scalar(incident_statement)
                    if incident is None:
                        raise StorageUnavailableError(
                            "incident disappeared while recording signal"
                        )

                    previous_status = incident.status
                    timeline_action: str | None = None
                    timeline_from: str | None = previous_status
                    if incident.occurrence_count == 0:
                        timeline_action = "opened"
                        timeline_from = None
                    elif incident.status == "resolved":
                        incident.status = "open"
                        incident.owner = None
                        incident.acknowledged_at = None
                        incident.resolved_at = None
                        incident.resolution_note = None
                        timeline_action = "reopened"
                    elif incident.severity == "warning" and signal.severity == "critical":
                        timeline_action = "escalated"

                    if signal.severity == "critical":
                        incident.severity = "critical"
                    incident.title = signal.title
                    incident.summary = signal.summary
                    incident.occurrence_count += 1
                    incident.last_seen = max(
                        _utc(incident.last_seen),
                        _utc(signal.observed_at),
                    )
                    incident.revision += 1
                    incident.updated_at = now
                    inserted_signals += 1

                    if timeline_action is not None:
                        session.add(
                            IncidentTimelineRecord(
                                timeline_id=str(uuid.uuid4()),
                                incident_id=incident.incident_id,
                                action=timeline_action,
                                actor="rtmonitor-worker",
                                note=signal.summary,
                                from_status=timeline_from,
                                to_status=incident.status,
                                occurred_at=now,
                            )
                        )
                await session.commit()
            except SQLAlchemyError as exc:
                await session.rollback()
                raise StorageUnavailableError("incident signal write failed") from exc
        return inserted_signals

    async def query_metric_samples(
        self,
        *,
        node_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int,
        cursor: tuple[datetime, str] | None = None,
    ) -> list[MetricSample]:
        statement = (
            select(MetricSampleRecord)
            .where(
                MetricSampleRecord.node_id == node_id,
                MetricSampleRecord.metric_name == metric_name,
                MetricSampleRecord.observed_at >= start,
                MetricSampleRecord.observed_at < end,
            )
            .order_by(MetricSampleRecord.observed_at, MetricSampleRecord.event_id)
            .limit(limit)
        )
        if cursor is not None:
            statement = statement.where(
                tuple_(MetricSampleRecord.observed_at, MetricSampleRecord.event_id) > cursor
            )
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return [
            MetricSample(
                event_id=record.event_id,
                node_id=record.node_id,
                metric_name=record.metric_name,
                observed_at=_utc(record.observed_at),
                value=record.value,
                labels=dict(record.labels),
            )
            for record in records
        ]

    async def query_recent_metric_samples(
        self,
        *,
        node_id: str,
        metric_name: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[MetricSample]:
        """Return the newest bounded window in chronological order."""
        statement = (
            select(MetricSampleRecord)
            .where(
                MetricSampleRecord.node_id == node_id,
                MetricSampleRecord.metric_name == metric_name,
                MetricSampleRecord.observed_at >= start,
                MetricSampleRecord.observed_at < end,
            )
            .order_by(
                MetricSampleRecord.observed_at.desc(),
                MetricSampleRecord.event_id.desc(),
            )
            .limit(limit)
        )
        async with self._sessions() as session:
            records = list((await session.scalars(statement)).all())
        records.reverse()
        return [
            MetricSample(
                event_id=record.event_id,
                node_id=record.node_id,
                metric_name=record.metric_name,
                observed_at=_utc(record.observed_at),
                value=record.value,
                labels=dict(record.labels),
            )
            for record in records
        ]

    async def list_nodes(self, *, limit: int) -> list[NodeSummary]:
        statement = (
            select(
                TelemetryRecord.node_id,
                func.max(TelemetryRecord.observed_at),
                func.count(),
            )
            .group_by(TelemetryRecord.node_id)
            .order_by(func.max(TelemetryRecord.observed_at).desc())
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()
        return [
            NodeSummary(
                node_id=node_id,
                last_seen=_utc(last_seen),
                event_count=int(event_count),
            )
            for node_id, last_seen, event_count in rows
        ]

    async def list_anomalies(
        self,
        *,
        node_id: str | None,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[Anomaly]:
        statement = (
            select(AnomalyRecord)
            .where(
                AnomalyRecord.observed_at >= start,
                AnomalyRecord.observed_at < end,
            )
            .order_by(AnomalyRecord.observed_at.desc(), AnomalyRecord.metric_name)
            .limit(limit)
        )
        if node_id is not None:
            statement = statement.where(AnomalyRecord.node_id == node_id)
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return [
            Anomaly(
                event_id=record.event_id,
                node_id=record.node_id,
                metric_name=record.metric_name,
                observed_at=_utc(record.observed_at),
                value=record.value,
                baseline=record.baseline,
                dispersion=record.dispersion,
                score=record.score,
                severity=cast(Literal["warning", "critical"], record.severity),
                sample_count=record.sample_count,
            )
            for record in records
        ]

    async def list_forecasts(
        self, *, node_id: str | None, limit: int
    ) -> list[Forecast]:
        latest = select(
            ForecastRecord.node_id.label("node_id"),
            ForecastRecord.metric_name.label("metric_name"),
            func.max(ForecastRecord.observed_at).label("observed_at"),
        )
        if node_id is not None:
            latest = latest.where(ForecastRecord.node_id == node_id)
        latest_subquery = latest.group_by(
            ForecastRecord.node_id,
            ForecastRecord.metric_name,
        ).subquery()
        statement = (
            select(ForecastRecord)
            .join(
                latest_subquery,
                and_(
                    ForecastRecord.node_id == latest_subquery.c.node_id,
                    ForecastRecord.metric_name == latest_subquery.c.metric_name,
                    ForecastRecord.observed_at == latest_subquery.c.observed_at,
                ),
            )
            .order_by(ForecastRecord.hours_to_threshold, ForecastRecord.metric_name)
            .limit(limit)
        )
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return [
            Forecast(
                event_id=record.event_id,
                node_id=record.node_id,
                metric_name=record.metric_name,
                observed_at=_utc(record.observed_at),
                current_value=record.current_value,
                threshold=record.threshold,
                slope_per_hour=record.slope_per_hour,
                hours_to_threshold=record.hours_to_threshold,
                predicted_at=_utc(record.predicted_at),
                r_squared=record.r_squared,
                confidence=cast(Literal["medium", "high"], record.confidence),
                risk=cast(Literal["watch", "warning", "critical"], record.risk),
                sample_count=record.sample_count,
                backtest_error=record.backtest_error,
                provider=cast(Literal["cpu", "gpu"], record.provider),
                fallback_reason=record.fallback_reason,
            )
            for record in records
        ]

    async def list_incidents(
        self,
        *,
        status: Literal["open", "acknowledged", "resolved"] | None,
        node_id: str | None,
        limit: int,
    ) -> list[Incident]:
        status_order = case(
            (IncidentRecord.status == "open", 0),
            (IncidentRecord.status == "acknowledged", 1),
            else_=2,
        )
        severity_order = case((IncidentRecord.severity == "critical", 0), else_=1)
        statement = select(IncidentRecord)
        if status is not None:
            statement = statement.where(IncidentRecord.status == status)
        if node_id is not None:
            statement = statement.where(IncidentRecord.node_id == node_id)
        statement = statement.order_by(
            status_order,
            severity_order,
            IncidentRecord.updated_at.desc(),
        ).limit(limit)
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
        return [_incident(record) for record in records]

    async def incident_timeline(
        self,
        *,
        incident_id: str,
        limit: int,
    ) -> list[IncidentTimelineEvent]:
        statement = (
            select(IncidentTimelineRecord)
            .where(IncidentTimelineRecord.incident_id == incident_id)
            .order_by(
                IncidentTimelineRecord.occurred_at,
                IncidentTimelineRecord.timeline_id,
            )
            .limit(limit)
        )
        async with self._sessions() as session:
            records = (await session.scalars(statement)).all()
            if not records:
                exists = await session.scalar(
                    select(IncidentRecord.incident_id).where(
                        IncidentRecord.incident_id == incident_id
                    )
                )
                if exists is None:
                    raise IncidentNotFoundError(incident_id)
        return [
            IncidentTimelineEvent(
                timeline_id=record.timeline_id,
                incident_id=record.incident_id,
                action=cast(
                    Literal[
                        "opened",
                        "escalated",
                        "acknowledged",
                        "resolved",
                        "reopened",
                    ],
                    record.action,
                ),
                actor=record.actor,
                note=record.note,
                from_status=cast(
                    Literal["open", "acknowledged", "resolved"] | None,
                    record.from_status,
                ),
                to_status=cast(
                    Literal["open", "acknowledged", "resolved"],
                    record.to_status,
                ),
                occurred_at=_utc(record.occurred_at),
            )
            for record in records
        ]

    async def transition_incident(
        self,
        *,
        incident_id: str,
        action: Literal["acknowledge", "resolve"],
        actor: str,
        note: str | None,
        expected_revision: int,
    ) -> Incident:
        now = datetime.now(UTC)
        async with self._sessions() as session:
            try:
                statement = select(IncidentRecord).where(
                    IncidentRecord.incident_id == incident_id
                )
                if self._engine.dialect.name == "postgresql":
                    statement = statement.with_for_update()
                record = await session.scalar(statement)
                if record is None:
                    raise IncidentNotFoundError(incident_id)
                if record.revision != expected_revision:
                    raise IncidentConflictError(
                        f"expected revision {expected_revision}, "
                        f"current revision is {record.revision}"
                    )

                from_status = record.status
                timeline_action: Literal["acknowledged", "resolved"]
                if action == "acknowledge":
                    if record.status == "resolved":
                        raise InvalidIncidentTransitionError(
                            "resolved incidents cannot be acknowledged"
                        )
                    if record.status == "acknowledged":
                        return _incident(record)
                    record.status = "acknowledged"
                    record.owner = actor
                    record.acknowledged_at = now
                    timeline_action = "acknowledged"
                else:
                    resolution_note = (note or "").strip()
                    if len(resolution_note) < 3:
                        raise InvalidIncidentTransitionError(
                            "resolution note must contain at least 3 characters"
                        )
                    if record.status == "resolved":
                        return _incident(record)
                    record.status = "resolved"
                    record.owner = actor
                    record.resolved_at = now
                    record.resolution_note = resolution_note
                    timeline_action = "resolved"

                record.revision += 1
                record.updated_at = now
                session.add(
                    IncidentTimelineRecord(
                        timeline_id=str(uuid.uuid4()),
                        incident_id=record.incident_id,
                        action=timeline_action,
                        actor=actor,
                        note=note,
                        from_status=from_status,
                        to_status=record.status,
                        occurred_at=now,
                    )
                )
                await session.commit()
                return _incident(record)
            except (
                IncidentConflictError,
                IncidentNotFoundError,
                InvalidIncidentTransitionError,
            ):
                await session.rollback()
                raise
            except SQLAlchemyError as exc:
                await session.rollback()
                raise StorageUnavailableError("incident transition failed") from exc

    async def prune_metric_samples(self, *, before: datetime, batch_size: int) -> int:
        async with self._sessions() as session:
            keys = (
                await session.execute(
                    select(MetricSampleRecord.event_id, MetricSampleRecord.metric_name)
                    .where(MetricSampleRecord.observed_at < before)
                    .order_by(MetricSampleRecord.observed_at)
                    .limit(batch_size)
                )
            ).all()
            if not keys:
                return 0
            result = await session.scalars(
                delete(MetricSampleRecord)
                .where(
                    tuple_(
                        MetricSampleRecord.event_id,
                        MetricSampleRecord.metric_name,
                    ).in_(keys)
                )
                .returning(MetricSampleRecord.metric_name)
            )
            deleted = len(result.all())
            await session.commit()
            return deleted

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(select(func.count()).select_from(TelemetryRecord).limit(1))
        except SQLAlchemyError:
            return False
        return True

    async def create_schema_for_tests(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()
