"""SQLAlchemy-backed telemetry event store."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from rtmonitor.api.contracts import TelemetryEventRequest
from rtmonitor.storage.base import StoreResult
from rtmonitor.storage.models import Base, TelemetryRecord


class StorageUnavailableError(RuntimeError):
    """Raised when an event cannot be durably committed."""


class SqlAlchemyEventStore:
    def __init__(self, database_url: str, *, engine: AsyncEngine | None = None) -> None:
        self._engine = engine or create_async_engine(
            database_url,
            pool_pre_ping=True,
        )
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    async def store(self, event: TelemetryEventRequest) -> StoreResult:
        record = TelemetryRecord(
            event_id=str(event.event_id),
            schema_version=event.schema_version,
            node_id=event.node_id,
            observed_at=event.observed_at,
            received_at=datetime.now(UTC),
            payload=event.model_dump(mode="json"),
        )
        async with self._sessions() as session:
            session.add(record)
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

    async def ping(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(
                    select(func.count()).select_from(TelemetryRecord).limit(1)
                )
        except SQLAlchemyError:
            return False
        return True

    async def create_schema_for_tests(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()
