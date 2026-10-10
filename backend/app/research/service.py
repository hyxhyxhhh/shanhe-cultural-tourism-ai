"""Public-data research orchestration with an injected search provider."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Protocol, Sequence


ResearchScope = Literal["weather", "holiday", "similar_events", "public_trend"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SearchItem:
    label: str
    summary: str
    url: str
    captured_at: datetime = field(default_factory=utc_now)
    published_at: str | None = None
    site_name: str | None = None
    authority_level: str | None = None
    rank: int = 0
    provider_request_id: str = ""
    scope: ResearchScope = "public_trend"


class PublicSearchProvider(Protocol):
    async def search(self, query: str, scopes: Sequence[ResearchScope]) -> Sequence[SearchItem]:
        ...


@dataclass(frozen=True)
class ResearchResult:
    use_web_search: bool
    query: str
    scopes: tuple[ResearchScope, ...]
    source_type: str
    items: tuple[SearchItem, ...]
    warning: str | None = None

    def source_references(self) -> list[dict[str, object]]:
        if not self.items:
            return [
                {
                    "sourceType": "missing",
                    "label": "联网研究结果待补充",
                    "reasoning": self.warning or "没有可用的联网搜索结果",
                }
            ]
        references: list[dict[str, object]] = []
        for item in self.items:
            reference: dict[str, object] = {
                "sourceType": "public",
                "label": item.label,
                "url": item.url,
                "capturedAt": item.captured_at.isoformat(),
                "excerpt": item.summary,
                "rank": item.rank,
                "providerRequestId": item.provider_request_id,
                "scope": item.scope,
            }
            if item.published_at is not None:
                reference["publishedAt"] = item.published_at
            if item.site_name is not None:
                reference["siteName"] = item.site_name
            if item.authority_level is not None:
                reference["authorityLevel"] = item.authority_level
            references.append(reference)
        return references


class ResearchService:
    def __init__(self, provider: PublicSearchProvider) -> None:
        self.provider = provider

    async def run(
        self,
        *,
        query: str,
        use_web_search: bool,
        scopes: Sequence[ResearchScope],
    ) -> ResearchResult:
        if not use_web_search:
            return ResearchResult(False, query, tuple(scopes), "missing", (), "用户未启用联网搜索")
        items = tuple(await self.provider.search(query, scopes))
        return ResearchResult(True, query, tuple(scopes), "public", items)
