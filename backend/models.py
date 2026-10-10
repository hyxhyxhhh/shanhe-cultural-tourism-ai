from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'running', 'paused', 'completed', 'failed', 'archived')",
            name="ck_activities_status",
        ),
        CheckConstraint("current_step BETWEEN 1 AND 9", name="ck_activities_current_step"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    search_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    steps: Mapped[list["ActivityStep"]] = relationship(back_populates="activity", cascade="all, delete-orphan")


class ActivityStep(Base):
    __tablename__ = "activity_steps"
    __table_args__ = (
        UniqueConstraint("activity_id", "step_no", name="uq_activity_steps_activity_step_no"),
        CheckConstraint("step_no BETWEEN 1 AND 9", name="ck_activity_steps_step_no"),
        CheckConstraint(
            "step_key IN ('brief', 'research', 'theme', 'content_space', 'budget', 'promotion', 'execution_plan', 'channel_business', 'review')",
            name="ck_activity_steps_step_key",
        ),
        CheckConstraint(
            "status IN ('locked', 'draft', 'generating', 'review', 'confirmed', 'needs_review', 'failed')",
            name="ck_activity_steps_status",
        ),
        CheckConstraint("version >= 1", name="ck_activity_steps_version"),
        CheckConstraint(
            "(step_no = 1 AND step_key = 'brief') OR "
            "(step_no = 2 AND step_key = 'research') OR "
            "(step_no = 3 AND step_key = 'theme') OR "
            "(step_no = 4 AND step_key = 'content_space') OR "
            "(step_no = 5 AND step_key = 'budget') OR "
            "(step_no = 6 AND step_key = 'promotion') OR "
            "(step_no = 7 AND step_key = 'execution_plan') OR "
            "(step_no = 8 AND step_key = 'channel_business') OR "
            "(step_no = 9 AND step_key = 'review')",
            name="ck_activity_steps_step_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_by: Mapped[str | None] = mapped_column(String(200))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    activity: Mapped[Activity] = relationship(back_populates="steps")


class ActivityStepVersion(Base):
    __tablename__ = "activity_step_versions"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "step_no",
            "version",
            name="uq_activity_step_versions_activity_step_version",
        ),
        Index("ix_activity_step_versions_activity_step", "activity_id", "step_no"),
        CheckConstraint("step_no BETWEEN 1 AND 9", name="ck_activity_step_versions_step_no"),
        CheckConstraint("version >= 1", name="ck_activity_step_versions_version"),
        CheckConstraint(
            "status IN ('locked', 'draft', 'generating', 'review', 'confirmed', 'needs_review', 'failed')",
            name="ck_activity_step_versions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    change_type: Mapped[str] = mapped_column(String(40), nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ActivityStepConfirmation(Base):
    __tablename__ = "activity_step_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "step_no",
            "version",
            name="uq_activity_step_confirmations_activity_step_version",
        ),
        ForeignKeyConstraint(
            ["activity_id", "step_no", "version"],
            [
                "activity_step_versions.activity_id",
                "activity_step_versions.step_no",
                "activity_step_versions.version",
            ],
            name="fk_activity_step_confirmations_version",
            ondelete="CASCADE",
        ),
        Index("ix_activity_step_confirmations_activity_step", "activity_id", "step_no"),
        CheckConstraint("step_no BETWEEN 1 AND 9", name="ck_activity_step_confirmations_step_no"),
        CheckConstraint("version >= 1", name="ck_activity_step_confirmations_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        UniqueConstraint("generation_id", name="uq_model_runs_generation_id"),
        Index("ix_model_runs_activity_step", "activity_id", "step_no"),
        Index("ix_model_runs_status", "status"),
        CheckConstraint("step_no BETWEEN 1 AND 9", name="ck_model_runs_step_no"),
        CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_model_runs_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="ccode")
    model: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None] = mapped_column(String(300))
    error_code: Mapped[str | None] = mapped_column(String(80))
    scope_progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    planning_progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


STEP_KEYS = (
    "brief",
    "research",
    "theme",
    "content_space",
    "budget",
    "promotion",
    "execution_plan",
    "channel_business",
    "review",
)


class SourceReference(Base):
    __tablename__ = "source_references"
    __table_args__ = (
        CheckConstraint(
            "authority_level IS NULL OR authority_level IN ('very_high', 'high', 'normal')",
            name="ck_source_references_authority_level",
        ),
        CheckConstraint("rank IS NULL OR rank >= 0", name="ck_source_references_rank"),
        CheckConstraint(
            "scope IS NULL OR scope IN ('weather', 'holiday', 'similar_events', 'public_trend')",
            name="ck_source_references_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    file_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    url: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    excerpt: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(200))
    site_name: Mapped[str | None] = mapped_column(String(300))
    authority_level: Mapped[str | None] = mapped_column(String(24))
    rank: Mapped[int | None] = mapped_column(Integer)
    provider_request_id: Mapped[str | None] = mapped_column(String(300))
    scope: Mapped[str | None] = mapped_column(String(40))


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecutionTask(Base):
    __tablename__ = "execution_tasks"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "source_step_version",
            "source_task_index",
            name="uq_execution_tasks_generated_source",
        ),
        CheckConstraint(
            "(source_step_version IS NULL AND source_task_index IS NULL) OR "
            "(source_step_version >= 1 AND source_task_index >= 0)",
            name="ck_execution_tasks_generated_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(200))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_confirmation")
    attachment_file_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_step_version: Mapped[int | None] = mapped_column(Integer)
    source_task_index: Mapped[int | None] = mapped_column(Integer)


class DeliverableArtifact(Base):
    __tablename__ = "deliverable_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "filename",
            "version",
            name="uq_deliverable_artifacts_activity_filename_version",
        ),
        Index("ix_deliverable_artifacts_activity", "activity_id", "created_at"),
        CheckConstraint("version >= 1", name="ck_deliverable_artifacts_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
