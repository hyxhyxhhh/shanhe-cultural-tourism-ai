"""Persistent annual-to-single boundaries, idempotency and ownership."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from types import SimpleNamespace
import unittest
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.activities import create_activity
from backend.activity_api import get_activity_db_session
from backend.annual_activity_api import router
from backend.annual_activity_models import AnnualPlanItemActivity
from backend.auth import require_session
from backend.db import SessionLocal, engine
from backend.models import Activity
from backend.test_annual_planning import ANNUAL_INPUT, ANNUAL_OUTPUT


def annual_parent(db, owner):
    brief = {**ANNUAL_INPUT, "location": "四季景区", "budgetMin": 100000.0, "budgetMax": 200000.0, "knownConstraints": "基础设施可复用，夜游须独立审批"}
    activity = create_activity(title="年度总策划", idea=brief["idea"], created_by=str(owner), input_data=brief, session=db)
    activity.status = "running"
    activity.steps[2].status = "confirmed"
    activity.steps[2].output_json = deepcopy(ANNUAL_OUTPUT)
    db.commit()
    return activity


class AnnualChildActivityTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        self.user = SimpleNamespace(user_id=uuid4())
        self.parent = annual_parent(self.db, self.user.user_id)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: self.user
        app.dependency_overrides[get_activity_db_session] = lambda: self.db
        self.client = TestClient(app)
        self.url = f"/api/activities/{self.parent.id}/plan-items/spring/activity"

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def _post(self, **body):
        return self.client.post(self.url, json={"version": self.parent.steps[2].version, **body})

    def test_child_has_independent_draft_steps_and_no_annual_budget_or_dates(self):
        parent_input = deepcopy(self.parent.input)
        parent_output = deepcopy(self.parent.steps[2].output_json)
        response = self._post()
        self.assertEqual(response.status_code, 201, response.text)
        child = response.json()
        self.assertEqual(child["title"], "春季花事")
        self.assertEqual(child["input"]["planningMode"], "single")
        self.assertEqual(child["input"]["location"], "四季景区")
        self.assertEqual(child["input"]["targetAudience"], "家庭游客")
        self.assertIn("三月至四月", child["input"]["idea"])
        self.assertIn(ANNUAL_OUTPUT["annualNarrative"], child["input"]["idea"])
        self.assertIn("200000.0", child["input"]["knownConstraints"])
        for key in ("budgetMin", "budgetMax", "plannedStartAt", "plannedEndAt", "annualPeriod", "annualGoals", "plannedEventCount"):
            self.assertNotIn(key, child["input"])
        self.assertEqual([step["status"] for step in child["steps"]], ["draft"] + ["locked"] * 8)
        self.assertTrue(all(not step["outputJson"] for step in child["steps"]))
        self.assertEqual(child["steps"][0]["inputJson"], child["input"])
        self.assertEqual(self.parent.input, parent_input)
        self.assertEqual(self.parent.steps[2].output_json, parent_output)
        stored_child = self.db.get(Activity, UUID(child["id"]))
        stored_child.input = {**stored_child.input, "idea": "单独修改活动创意"}
        self.db.commit()
        repeated = self._post()
        self.assertEqual(repeated.status_code, 201, repeated.text)
        self.assertEqual(repeated.json()["id"], child["id"])
        self.assertEqual(repeated.json()["input"]["idea"], "单独修改活动创意")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AnnualPlanItemActivity).where(AnnualPlanItemActivity.annual_activity_id == self.parent.id)), 1)
        self.assertEqual(self.parent.input, parent_input)

    def test_owner_authentication_and_version_boundaries(self):
        self.user.user_id = uuid4()
        self.assertEqual(self._post().status_code, 404)
        self.user.user_id = UUID(self.parent.created_by)
        stale = self._post(version=9)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "VERSION_CONFLICT")
        self.parent.steps[2].status = "review"
        self.db.commit()
        unconfirmed = self._post()
        self.assertEqual(unconfirmed.status_code, 409)
        self.assertEqual(unconfirmed.json()["detail"]["code"], "ANNUAL_PLAN_NOT_CONFIRMED")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AnnualPlanItemActivity).where(AnnualPlanItemActivity.annual_activity_id == self.parent.id)), 0)
        unauthenticated_app = FastAPI()
        unauthenticated_app.include_router(router)
        with TestClient(unauthenticated_app) as client:
            self.assertEqual(client.post(self.url, json={"version": 1}).status_code, 401)

    def test_changed_source_does_not_overwrite_existing_child(self):
        child_response = self._post()
        self.assertEqual(child_response.status_code, 201, child_response.text)
        child = child_response.json()
        self.parent.steps[2].version += 1
        output = deepcopy(self.parent.steps[2].output_json)
        output["eventBriefs"][0]["themeDirection"] = "新的主题方向"
        self.parent.steps[2].output_json = output
        self.db.commit()
        rejected = self._post()
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(rejected.json()["detail"]["code"], "PLAN_ITEM_SOURCE_CHANGED")
        self.assertEqual(self.db.get(Activity, UUID(child["id"])).input, child["input"])

    def test_unknown_event_wrong_mode_and_invalid_request_are_explicit(self):
        unknown = self.client.post(self.url.replace("spring", "missing-event"), json={"version": 1})
        self.assertEqual(unknown.status_code, 404)
        for body in ({"version": True}, {"version": "1"}, {"version": 1, "copyResearch": True}):
            self.assertEqual(self.client.post(self.url, json=body).status_code, 422)
        self.parent.input = {"idea": "单场策划", "planningMode": "single"}
        self.db.commit()
        wrong_mode = self._post()
        self.assertEqual(wrong_mode.status_code, 409)
        self.assertEqual(wrong_mode.json()["detail"]["code"], "ANNUAL_PLAN_REQUIRED")


class AnnualChildConcurrencyTests(unittest.TestCase):
    def test_parallel_creations_share_one_child_and_one_link(self):
        owner = uuid4()
        with SessionLocal() as db:
            parent = annual_parent(db, owner)
            parent_id = parent.id
        barrier = Barrier(2)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(user_id=owner)

        def request_child():
            with TestClient(app) as client:
                barrier.wait(timeout=10)
                response = client.post(f"/api/activities/{parent_id}/plan-items/spring/activity", json={"version": 1})
                self.assertEqual(response.status_code, 201, response.text)
                return response.json()["id"]

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(lambda _index: request_child(), range(2)))
            self.assertEqual(responses[0], responses[1])
            with SessionLocal() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(AnnualPlanItemActivity).where(AnnualPlanItemActivity.annual_activity_id == parent_id)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(Activity).where(Activity.created_by == str(owner))), 2)
        finally:
            with SessionLocal.begin() as db:
                db.execute(delete(Activity).where(Activity.created_by == str(owner)))


if __name__ == "__main__":
    unittest.main()
