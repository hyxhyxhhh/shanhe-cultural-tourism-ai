"""Explicit links from confirmed annual event briefs to independent activities."""

from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db import Base


class AnnualPlanItemActivity(Base):
    __tablename__ = "annual_plan_item_activities"
    __table_args__ = (
        UniqueConstraint("annual_activity_id", "event_id", name="uq_annual_plan_item_activity_source"),
        UniqueConstraint("child_activity_id", name="uq_annual_plan_item_activity_child"),
        CheckConstraint("source_step_version >= 1", name="ck_annual_plan_item_activity_version"),
        CheckConstraint("annual_activity_id <> child_activity_id", name="ck_annual_plan_item_activity_distinct"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    annual_activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(80), nullable=False)
    child_activity_id: Mapped[UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    source_step_version: Mapped[int] = mapped_column(Integer, nullable=False)
