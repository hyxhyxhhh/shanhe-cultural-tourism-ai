from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.activity_api import ActivityDTO, ActivityStepDTO, get_activity_db_session, get_model_provider, router
from backend.app.research.service import SearchItem
from backend.app.routers.research import router as research_router
from backend.auth import get_db_session, require_session
from backend.db import SessionLocal, engine
from backend.models import Activity, ActivityStep, STEP_KEYS
from backend.model_catalog import require_allowed_models
from backend.test_activity_steps import FakeProvider, generate_research_test


class _SearchProvider:
    async def search(self, _query, scopes):
        return tuple(
            SearchItem(
                label="Public evidence report",
                summary="Public evidence excerpt",
                url=f"https://example.com/{scope}",
                captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
                rank=index,
                provider_request_id=f"request-{scope}",
                scope=scope,
            )
            for index, scope in enumerate(scopes)
        )


class ActivityApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with SessionLocal() as session:
            cls.initial_activity_count = session.scalar(select(func.count()).select_from(Activity))

    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.current_user = SimpleNamespace(
            user_id=uuid4(),
            account="owner@example.test",
            display_name="Owner",
            role_id="planner",
        )
        app = FastAPI()
        app.state.research_provider = _SearchProvider()
        app.include_router(router)
        app.include_router(research_router)
        app.dependency_overrides[require_session] = lambda: self.current_user
        app.dependency_overrides[get_activity_db_session] = lambda: self.db
        app.dependency_overrides[get_db_session] = lambda: self.db
        self.model_provider = FakeProvider()
        app.dependency_overrides[get_model_provider] = lambda: self.model_provider
        app.dependency_overrides[require_allowed_models] = lambda: ("selected-model",)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()
        with SessionLocal() as session:
            final_count = session.scalar(select(func.count()).select_from(Activity))
        self.assertEqual(final_count, self.initial_activity_count)

    def _create_activity(self) -> dict:
        response = self.client.post(
            "/api/activities",
            json={
                "title": "  2026 Riverside Festival  ",
                "input": {
                    "idea": "  Build an evening market  ",
                    "budgetMin": 10000,
                    "budgetMax": 50000,
                },
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_list_and_owner_isolation(self) -> None:
        created = self._create_activity()

        self.assertEqual(created["title"], "2026 Riverside Festival")
        self.assertEqual(created["createdBy"], str(self.current_user.user_id))
        self.assertEqual(created["input"]["idea"], "Build an evening market")
        self.assertEqual([step["stepKey"] for step in created["steps"]], list(STEP_KEYS))
        self.assertEqual([step["status"] for step in created["steps"]], ["draft"] + ["locked"] * 8)
        self.assertEqual(created["steps"][0]["inputJson"], created["input"])
        self.assertEqual(created["steps"][1]["inputJson"], {"useWebSearch": False})
        self.assertNotIn("location", created["input"])

        listed = self.client.get("/api/activities")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([item["id"] for item in listed.json()], [created["id"]])

        self.current_user.user_id = uuid4()
        hidden = self.client.get(f"/api/activities/{created['id']}")
        self.assertEqual(hidden.status_code, 404)
        self.assertEqual(hidden.json(), {"detail": "Activity not found"})

    def test_pause_resume_archive_and_default_archive_filter(self) -> None:
        created = self._create_activity()
        activity_url = f"/api/activities/{created['id']}"

        paused = self.client.post(f"{activity_url}/pause")
        self.assertEqual(paused.status_code, 200, paused.text)
        self.assertEqual(paused.json()["status"], "paused")

        invalid = self.client.patch(activity_url, json={"status": "draft"})
        self.assertEqual(invalid.status_code, 409, invalid.text)

        resumed = self.client.patch(activity_url, json={"status": "running"})
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.assertEqual(resumed.json()["status"], "running")

        archived = self.client.post(f"{activity_url}/archive")
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["status"], "archived")
        self.assertEqual(self.client.get("/api/activities").json(), [])
        self.assertEqual(len(self.client.get("/api/activities?includeArchived=true").json()), 1)

        rejected_edit = self.client.patch(activity_url, json={"title": "Changed"})
        self.assertEqual(rejected_edit.status_code, 409, rejected_edit.text)

    def test_request_validation_rejects_invalid_fields(self) -> None:
        invalid_range = self.client.post(
            "/api/activities",
            json={
                "title": "Event",
                "input": {"idea": "Idea", "budgetMin": 20, "budgetMax": 10},
            },
        )
        self.assertEqual(invalid_range.status_code, 422)

        explicit_null = self.client.post(
            "/api/activities",
            json={
                "title": "Event",
                "input": {"idea": "Idea", "location": None},
            },
        )
        self.assertEqual(explicit_null.status_code, 422)

        injected_owner = self.client.post(
            "/api/activities",
            json={
                "title": "Event",
                "input": {"idea": "Idea"},
                "createdBy": "attacker@example.test",
            },
        )
        self.assertEqual(injected_owner.status_code, 422)

        empty_patch = self.client.patch("/api/activities/00000000-0000-0000-0000-000000000000", json={})
        self.assertEqual(empty_patch.status_code, 422)

        null_title = self.client.patch(
            "/api/activities/00000000-0000-0000-0000-000000000000",
            json={"title": None},
        )
        self.assertEqual(null_title.status_code, 422)

    def test_activity_patch_rejects_step_owned_fields(self) -> None:
        created = self._create_activity()
        for payload in (
            {"input": {"idea": "Bypass"}},
            {"searchEnabled": True},
            {"title": "Allowed field mixed with bypass", "searchEnabled": True},
        ):
            response = self.client.patch(f"/api/activities/{created['id']}", json=payload)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(response.json()["detail"][0]["type"], "extra_forbidden")

    def test_response_dtos_reject_unknown_workflow_metadata(self) -> None:
        created = self._create_activity()
        step_payload = dict(created["steps"][0])
        step_payload["status"] = "unknown"
        with self.assertRaises(ValidationError):
            ActivityStepDTO.model_validate(step_payload)

        activity_payload = dict(created)
        activity_payload["status"] = "unknown"
        with self.assertRaises(ValidationError):
            ActivityDTO.model_validate(activity_payload)

    def test_persisted_public_research_is_readable_from_activity_and_step_routes(self) -> None:
        created = self._create_activity()
        activity_id = created["id"]
        saved_brief = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={
                "version": created["steps"][0]["version"],
                "outputJson": {
                    "standardizedBrief": {"objective": "Plan the riverside event"},
                    "missingFields": [],
                },
            },
        )
        self.assertEqual(saved_brief.status_code, 200, saved_brief.text)
        confirmed_brief = self.client.post(
            f"/api/activities/{activity_id}/steps/1/confirm",
            json={"version": saved_brief.json()["version"]},
        )
        self.assertEqual(confirmed_brief.status_code, 200, confirmed_brief.text)
        research_step = self.client.get(f"/api/activities/{activity_id}/steps/2")
        self.assertEqual(research_step.status_code, 200, research_step.text)
        enabled = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={
                "version": research_step.json()["version"],
                "inputJson": {"useWebSearch": True},
            },
        )
        self.assertEqual(enabled.status_code, 200, enabled.text)

        researched = self.client.post(
            f"/api/activities/{activity_id}/research",
            json={
                "version": enabled.json()["version"],
                "useWebSearch": True,
                "queryScope": ["public_trend"],
                "query": "Riverside cultural event",
            },
        )
        self.assertEqual(researched.status_code, 200, researched.text)

        step_after_search = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual(step_after_search["outputJson"], {})
        self.model_provider.output = {
            "summary": "Public evidence informs event planning",
            "findings": ["Public trend evidence requires local verification"],
            "sources": [{"sourceType": "public", "label": "Public evidence report",
                         "url": "https://example.com/public_trend",
                         "capturedAt": "2026-09-24T00:00:00+00:00",
                         "rank": 0, "providerRequestId": "request-public_trend", "scope": "public_trend",
                         "excerpt": "Public evidence excerpt"}],
            "risks": [],
        }
        generated = generate_research_test(self.client, activity_id, step_after_search["version"])
        self.assertEqual(generated.status_code, 200, generated.text)

        activity_response = self.client.get(f"/api/activities/{activity_id}")
        step_response = self.client.get(f"/api/activities/{activity_id}/steps/2")
        steps_response = self.client.get(f"/api/activities/{activity_id}/steps")
        self.assertEqual(activity_response.status_code, 200, activity_response.text)
        self.assertEqual(step_response.status_code, 200, step_response.text)
        self.assertEqual(steps_response.status_code, 200, steps_response.text)
        self.assertEqual(
            activity_response.json()["steps"][1]["outputJson"]["sources"][0]["sourceType"],
            "public",
        )
        self.assertEqual(step_response.json()["outputJson"]["sources"][0]["sourceType"], "public")
        self.assertEqual(steps_response.json()[1]["outputJson"]["sources"][0]["sourceType"], "public")

        disabled = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={
                "version": step_response.json()["version"],
                "inputJson": {"useWebSearch": False},
            },
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertEqual(disabled.json()["status"], "needs_review")
        self.assertEqual(disabled.json()["inputJson"], {"useWebSearch": False})
        self.assertEqual(disabled.json()["outputJson"]["sources"][0]["sourceType"], "public")
        activity_response = self.client.get(f"/api/activities/{activity_id}")
        step_response = self.client.get(f"/api/activities/{activity_id}/steps/2")
        steps_response = self.client.get(f"/api/activities/{activity_id}/steps")
        self.assertEqual(activity_response.status_code, 200, activity_response.text)
        self.assertEqual(step_response.status_code, 200, step_response.text)
        self.assertEqual(steps_response.status_code, 200, steps_response.text)
        self.assertEqual(
            activity_response.json()["steps"][1]["outputJson"]["sources"][0]["sourceType"],
            "public",
        )
        self.assertEqual(step_response.json()["outputJson"]["sources"][0]["sourceType"], "public")
        self.assertEqual(steps_response.json()[1]["outputJson"]["sources"][0]["sourceType"], "public")

    def test_malformed_persisted_public_research_is_rejected(self) -> None:
        created = self._create_activity()
        activity_id = created["id"]
        activity = self.db.get(Activity, activity_id)
        step = self.db.scalar(
            select(ActivityStep).where(
                ActivityStep.activity_id == activity.id,
                ActivityStep.step_no == 2,
            )
        )
        step.output_json = {
            "summary": "Invalid persisted public evidence",
            "findings": [],
            "sources": [
                {
                    "sourceType": "public",
                    "label": "Public source",
                    "url": "https://example.com/source",
                    "capturedAt": "2026-09-24T12:00:00+00:00",
                }
            ],
            "risks": [],
        }
        self.db.flush()

        response = self.client.get(f"/api/activities/{activity_id}")

        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"]["code"], "PERSISTED_STEP_OUTPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
