"""PostgreSQL repository for generated deliverables."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.deliverables.generator import DeliverableFile
from backend.app.deliverables.service import DeliverableRecord
from backend.models import Activity, DeliverableArtifact


class SqlAlchemyDeliverableRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    async def save_batch(
        self, activity_id: str, files: Sequence[DeliverableFile]
    ) -> Sequence[DeliverableRecord]:
        return await asyncio.to_thread(self._save_batch, activity_id, tuple(files))

    async def list(self, activity_id: str) -> Sequence[DeliverableRecord]:
        return await asyncio.to_thread(self._list, activity_id)

    async def read(self, record: DeliverableRecord) -> bytes:
        return await asyncio.to_thread(self._read, record)

    def _save_batch(
        self, activity_id: str, files: tuple[DeliverableFile, ...]
    ) -> tuple[DeliverableRecord, ...]:
        activity_uuid = UUID(activity_id)
        if not files:
            raise ValueError("at least one deliverable file is required")
        filenames = [file.filename for file in files]
        if len(filenames) != len(set(filenames)):
            raise ValueError("deliverable filenames must be unique within a generation batch")

        with self._session_factory() as session, session.begin():
            locked_activity = session.scalar(
                select(Activity.id).where(Activity.id == activity_uuid).with_for_update()
            )
            if locked_activity is None:
                raise ValueError("activity does not exist")

            rows: list[DeliverableArtifact] = []
            for file in files:
                current_version = session.scalar(
                    select(func.max(DeliverableArtifact.version)).where(
                        DeliverableArtifact.activity_id == activity_uuid,
                        DeliverableArtifact.filename == file.filename,
                    )
                )
                version = (current_version or 0) + 1
                artifact_id = uuid4()
                row = DeliverableArtifact(
                    id=artifact_id,
                    activity_id=activity_uuid,
                    filename=file.filename,
                    content_type=file.content_type,
                    storage_key=(
                        f"activities/{activity_id}/deliverables/"
                        f"{file.filename}.v{version}.{artifact_id}"
                    ),
                    version=version,
                    content=file.content,
                )
                session.add(row)
                rows.append(row)
            session.flush()
            for row in rows:
                session.refresh(row)
            return tuple(self._record(row) for row in rows)

    def _list(self, activity_id: str) -> tuple[DeliverableRecord, ...]:
        activity_uuid = UUID(activity_id)
        with self._session_factory() as session:
            rows = session.scalars(
                select(DeliverableArtifact)
                .where(DeliverableArtifact.activity_id == activity_uuid)
                .order_by(
                    DeliverableArtifact.filename,
                    DeliverableArtifact.version.desc(),
                )
            ).all()
            return tuple(self._record(row) for row in rows)

    def _read(self, record: DeliverableRecord) -> bytes:
        with self._session_factory() as session:
            row = session.scalar(
                select(DeliverableArtifact).where(
                    DeliverableArtifact.id == UUID(record.id),
                    DeliverableArtifact.activity_id == UUID(record.activity_id),
                    DeliverableArtifact.storage_key == record.storage_key,
                )
            )
            if row is None:
                raise FileNotFoundError(record.storage_key)
            return bytes(row.content)

    @staticmethod
    def _record(row: DeliverableArtifact) -> DeliverableRecord:
        return DeliverableRecord(
            id=str(row.id),
            activity_id=str(row.activity_id),
            filename=row.filename,
            content_type=row.content_type,
            storage_key=row.storage_key,
            version=row.version,
            created_at=row.created_at,
        )
