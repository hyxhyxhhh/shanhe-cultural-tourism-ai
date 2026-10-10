"""Explicit per-scope evidence selection without changing stored search text."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy import select

from backend.models import SourceReference


RESEARCH_SCOPES = ("weather", "holiday", "similar_events", "public_trend")


class RawPublicEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    label: str = Field(min_length=1, max_length=300)
    url: HttpUrl
    captured_at: datetime = Field(alias="capturedAt")
    excerpt: str = Field(min_length=1)
    rank: int = Field(ge=0, strict=True)
    scope: Literal["weather", "holiday", "similar_events", "public_trend"]
    provider_request_id: str = Field(alias="providerRequestId", min_length=1, max_length=300)
    published_at: str | None = Field(default=None, alias="publishedAt", min_length=1, max_length=100)
    site_name: str | None = Field(default=None, alias="siteName", min_length=1, max_length=300)
    authority_level: Literal["very_high", "high", "normal"] | None = Field(
        default=None, alias="authorityLevel"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_nulls(cls, value):
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("public search evidence fields must be omitted instead of null")
        return value

    @model_validator(mode="after")
    def validate_evidence(self):
        if not self.label.strip() or not self.excerpt.strip():
            raise ValueError("public search evidence label and excerpt must not be blank")
        if self.captured_at.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone")
        return self


def load_public_evidence(session, activity_id: UUID) -> list[dict[str, object]]:
    references = session.scalars(
        select(SourceReference)
        .where(
            SourceReference.activity_id == activity_id,
            SourceReference.step_no == 2,
            SourceReference.source_type == "public",
        )
        .order_by(SourceReference.captured_at, SourceReference.id)
    ).all()
    evidence = []
    for reference in references:
        item = {
            "label": reference.label,
            "url": reference.url,
            "capturedAt": reference.captured_at.isoformat() if reference.captured_at is not None else None,
            "excerpt": reference.excerpt,
            "rank": reference.rank,
            "scope": reference.scope,
            "providerRequestId": reference.provider_request_id,
        }
        for field, attr in (
            ("publishedAt", "published_at"), ("siteName", "site_name"),
            ("authorityLevel", "authority_level"),
        ):
            value = getattr(reference, attr)
            if value is not None:
                item[field] = value
        evidence.append(item)
    return evidence


def select_public_evidence(evidence: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    # Validate every source before selection so a bad rank/scope is never skipped.
    for source in evidence:
        RawPublicEvidence.model_validate(source)
    selected = []
    for scope in RESEARCH_SCOPES:
        # Python's stable sort preserves the persisted capturedAt/id order for ties.
        ranked = sorted((source for source in evidence if source["scope"] == scope), key=lambda source: source["rank"])
        selected.extend(ranked)

    return selected, {
        "totalCount": len(evidence),
        "selectedCount": len(selected),
        "omittedCount": 0,
        "selected": [dict(source) for source in selected],
        "omitted": [],
    }
