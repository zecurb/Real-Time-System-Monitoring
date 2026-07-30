"""SQLAlchemy-backed telemetry event store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import and_, delete, func, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.sql import Executable

from rtmonitor.anomaly import MINIMUM_DISPERSION, SCORABLE_METRICS, robust_anomaly_score
from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.metrics import metric_values
from rtmonitor.storage.base import (
    Anomaly,
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
    MetricSampleRecord,
    PipelineQueueRecord,
    TelemetryRecord,
)


class StorageUnavailableError(RuntimeError):
    """Raised when an event cannot be durably committed."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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
        """Normalize telemetry and persist explainable anomaly findings idempotently."""
        event = TelemetryEventRequest.model_validate(payload)
        await self.write_metric_samples(payload)
        values = metric_values(event)
        findings: list[dict[str, object]] = []
        for metric_name in SCORABLE_METRICS:
            history = await self.query_metric_samples(
                node_id=event.node_id,
                metric_name=metric_name,
                start=event.observed_at - timedelta(days=7),
                end=event.observed_at,
                limit=120,
            )
            result = robust_anomaly_score(
                values[metric_name],
                [sample.value for sample in history],
                minimum_dispersion=MINIMUM_DISPERSION[metric_name],
            )
            if result is None:
                continue
            findings.append(
                {
                    "event_id": str(event.event_id),
                    "node_id": event.node_id,
                    "metric_name": metric_name,
                    "observed_at": event.observed_at,
                    "value": values[metric_name],
                    "baseline": result.baseline,
                    "dispersion": result.dispersion,
                    "score": result.score,
                    "severity": result.severity,
                    "sample_count": result.sample_count,
                    "created_at": datetime.now(UTC),
                }
            )
        if not findings:
            return
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
