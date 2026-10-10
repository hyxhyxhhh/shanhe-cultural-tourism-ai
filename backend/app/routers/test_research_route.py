"""Route-level tests for canonical research persistence and explicit errors."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import get_db_session, require_session
from backend.activity_steps import StepDomainError, confirm_step
from backend.models import Activity, ActivityStep, SourceReference
from backend.app.research.service import SearchItem
from backend.app.research.volcengine import SearchProviderError

from .research import router

_SCOPE_LABELS = {"weather": "天气", "holiday": "节假日", "similar_events": "同类活动", "public_trend": "公共趋势"}


class _FakeDb:
    def __init__(self, activity: Activity) -> None:
        self.activity = activity
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    def scalar(self, _statement):
        return self.activity

    def scalars(self, _statement):
        sources = [value for value in self.added if isinstance(value, SourceReference)]
        return SimpleNamespace(all=lambda: sources)

    def execute(self, _statement):
        return None

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added.extend(list(values))

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _SuccessProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, _query, scopes):
        self.calls += 1
        return tuple(
            SearchItem(
                label=f"{_SCOPE_LABELS[scope]}来源",
                summary="公开摘要",
                url=f"https://example.com/{scope}",
                captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                published_at="2026-09-20",
                site_name="示例站点",
                authority_level="high",
                rank=index,
                provider_request_id=f"request-{scope}",
                scope=scope,
            )
            for index, scope in enumerate(scopes)
        )


class _LongEvidenceProvider(_SuccessProvider):
    async def search(self, _query, scopes):
        self.calls += 1
        return tuple(
            SearchItem(
                label=f"{_SCOPE_LABELS[scope]}来源",
                summary="原" * length,
                url=f"https://example.com/{scope}",
                captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                published_at="2026-09-20",
                site_name="示例站点",
                authority_level="high",
                rank=index,
                provider_request_id=f"request-{scope}",
                scope=scope,
            )
            for index, (scope, length) in enumerate(zip(scopes, (3260, 3973, 4128)))
        )


class _FailingProvider:
    async def search(self, _query, _scopes):
        raise SearchProviderError(
            "SEARCH_RATE_LIMITED",
            "联网搜索请求超过频率限制",
            status_code=429,
            provider_request_id="rate-request",
        )


def _activity() -> Activity:
    activity_id = uuid4()
    activity = Activity(
        id=activity_id,
        title="北京文旅活动",
        status="running",
        current_step=2,
        input={"idea": "北京文旅活动"},
        search_enabled=True,
        created_by="user-1",
    )
    activity.steps = [
        ActivityStep(
            id=uuid4(),
            activity_id=activity_id,
            step_no=1,
            step_key="brief",
            status="confirmed",
            input_json={},
            output_json={"standardizedBrief": {"objective": "活动"}, "missingFields": []},
            version=2,
        ),
        ActivityStep(
            id=uuid4(),
            activity_id=activity_id,
            step_no=2,
            step_key="research",
            status="draft",
            input_json={"useWebSearch": True},
            output_json={},
            version=1,
        ),
    ]
    return activity


class ResearchRouteTests(unittest.TestCase):
    def _client(self, provider):
        activity = _activity()
        db = _FakeDb(activity)
        app = FastAPI()
        app.state.research_provider = provider
        app.include_router(router)
        app.dependency_overrides[get_db_session] = lambda: db
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(user_id="user-1")
        return TestClient(app), activity, db

    def test_selection_is_read_only_persistent_and_contains_all_full_evidence(self):
        client, activity, db = self._client(_SuccessProvider())
        db.added = [SourceReference(
            id=uuid4(), activity_id=activity.id, step_no=2, source_type="public",
            label=f"Source {rank}", url=f"https://example.com/{rank}",
            captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc), excerpt="Full" * 1000,
            rank=rank, scope="weather", provider_request_id="request-1",
            published_at="2026-09-20", site_name="原始站点", authority_level="high",
        ) for rank in reversed(range(10))]
        first = client.get(f"/api/activities/{activity.id}/research/selection")
        second = client.get(f"/api/activities/{activity.id}/research/selection")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["selectedCount"], 10)
        self.assertEqual(first.json()["omittedCount"], 0)
        self.assertEqual([item["rank"] for item in first.json()["selected"]], list(range(10)))
        self.assertFalse(db.committed)
        self.assertFalse(db.rolled_back)
        self.assertEqual(len(db.added), 10)
        self.assertEqual(len(db.added[0].excerpt), 4000)
        for entry in [*first.json()["selected"], *first.json()["omitted"]]:
            self.assertEqual(entry["excerpt"], "Full" * 1000)
            self.assertEqual(entry["capturedAt"], "2026-09-24T00:00:00+00:00")
            self.assertEqual(entry["providerRequestId"], "request-1")
            self.assertEqual(entry["publishedAt"], "2026-09-20")
            self.assertEqual(entry["siteName"], "原始站点")
            self.assertEqual(entry["authorityLevel"], "high")
        self.assertEqual(len([*first.json()["selected"], *first.json()["omitted"]]), 10)
        self.assertEqual(first.json()["omitted"], [])

    def test_selection_rejects_invalid_persisted_source(self):
        client, activity, db = self._client(_SuccessProvider())
        db.added = [SourceReference(
            id=uuid4(), activity_id=activity.id, step_no=2, source_type="public",
            label="Invalid", url="https://example.com/", excerpt="Original",
            captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc), rank=None,
            scope="weather", provider_request_id="request-1",
        )]
        response = client.get(f"/api/activities/{activity.id}/research/selection")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["detail"]["code"], "PERSISTED_STEP_OUTPUT_INVALID")
        self.assertFalse(db.committed)

    def test_success_keeps_step_two_as_draft_and_persists_full_sources(self) -> None:
        client, activity, db = self._client(_SuccessProvider())
        response = client.post(
            f"/api/activities/{activity.id}/research",
            json={
                "version": 1,
                "useWebSearch": True,
                "queryScope": ["weather", "holiday"],
                "query": "北京文旅活动",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(activity.steps[1].version, 2)
        self.assertEqual(activity.steps[1].status, "draft")
        self.assertEqual(activity.steps[1].output_json, {})
        sources = [value for value in db.added if isinstance(value, SourceReference)]
        self.assertEqual(len(sources), 2)
        first_source = sources[0]
        self.assertEqual(first_source.source_type, "public")
        self.assertEqual(first_source.excerpt, "公开摘要")
        self.assertEqual(first_source.published_at, "2026-09-20")
        self.assertEqual(first_source.site_name, "示例站点")
        self.assertEqual(first_source.authority_level, "high")
        self.assertEqual(first_source.rank, 0)
        self.assertEqual(first_source.provider_request_id, "request-weather")
        self.assertEqual(first_source.scope, "weather")
        self.assertEqual(len(response.json()["sourceReferences"]), 2)
        self.assertTrue(db.committed)
        self.assertFalse(db.rolled_back)

    def test_long_evidence_research_clears_old_analysis_without_truncating_sources(self) -> None:
        provider = _LongEvidenceProvider()
        client, activity, db = self._client(provider)
        step = activity.steps[1]
        step.status = "review"
        step.output_json = {"summary": "旧研判", "findings": ["旧发现"]}
        response = client.post(
            f"/api/activities/{activity.id}/research",
            json={
                "version": 1,
                "useWebSearch": True,
                "queryScope": ["weather", "holiday", "similar_events"],
                "query": "广阳岛年总活动规划 重庆市广阳岛；具体可用区域待运营方确认",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(step.version, 2)
        self.assertEqual(step.status, "draft")
        self.assertEqual(step.output_json, {})
        sources = [value for value in db.added if isinstance(value, SourceReference)]
        self.assertEqual([len(source.excerpt) for source in sources], [3260, 3973, 4128])
        for source, item, reference in zip(
            sources, response.json()["items"], response.json()["sourceReferences"]
        ):
            self.assertEqual(source.excerpt, item["summary"])
            self.assertEqual(source.excerpt, reference["excerpt"])
            self.assertEqual(source.url, reference["url"])
            self.assertEqual(source.provider_request_id, reference["providerRequestId"])
        self.assertTrue(db.committed)
        with self.assertRaises(StepDomainError) as raised:
            confirm_step(
                activity=activity, step=step, expected_version=2,
                actor="user-1", comment=None, session=db,
            )
        self.assertEqual(raised.exception.code, "STEP_NOT_CONFIRMABLE")

    def test_search_preconditions_reject_before_calling_provider(self) -> None:
        cases = (
            ("version", "VERSION_CONFLICT"),
            ("brief", "PREVIOUS_STEP_NOT_CONFIRMED"),
            ("search", "WEB_SEARCH_NOT_ENABLED"),
            ("confirmed", "STEP_REOPEN_REQUIRED"),
        )
        for condition, error_code in cases:
            with self.subTest(condition=condition):
                provider = _SuccessProvider()
                client, activity, db = self._client(provider)
                if condition == "brief":
                    activity.steps[0].status = "review"
                elif condition == "search":
                    activity.search_enabled = False
                elif condition == "confirmed":
                    activity.steps[1].status = "confirmed"
                response = client.post(
                    f"/api/activities/{activity.id}/research",
                    json={
                        "version": 2 if condition == "version" else 1,
                        "useWebSearch": True, "queryScope": ["weather"], "query": "活动",
                    },
                )
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(response.json()["detail"]["code"], error_code)
                self.assertEqual(provider.calls, 0)
                self.assertEqual(activity.steps[1].version, 1)
                self.assertFalse(db.committed)
                self.assertTrue(db.rolled_back)

    def test_inaccessible_activity_does_not_search(self) -> None:
        provider = _SuccessProvider()
        client, activity, db = self._client(provider)
        db.activity = None
        response = client.post(
            f"/api/activities/{activity.id}/research",
            json={"version": 1, "useWebSearch": True, "queryScope": ["weather"], "query": "活动"},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(provider.calls, 0)
        self.assertFalse(db.committed)

    def test_provider_error_is_non_success_and_does_not_change_version(self) -> None:
        client, activity, db = self._client(_FailingProvider())
        response = client.post(
            f"/api/activities/{activity.id}/research",
            json={
                "version": 1,
                "useWebSearch": True,
                "queryScope": ["weather"],
                "query": "北京文旅活动",
            },
        )
        self.assertEqual(response.status_code, 429, response.text)
        self.assertEqual(response.json()["detail"]["code"], "SEARCH_RATE_LIMITED")
        self.assertEqual(response.json()["detail"]["requestId"], "rate-request")
        self.assertEqual(activity.steps[1].version, 1)
        self.assertFalse(db.committed)
        self.assertTrue(db.rolled_back)


if __name__ == "__main__":
    unittest.main()
