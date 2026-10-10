"""Exercise long planning streams against genuinely independent DB sessions."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.activities import create_activity
from backend.activity_api import get_model_provider, router
from backend.activity_steps import get_owned_activity, reopen_step
from backend.auth import require_session
from backend.db import SessionLocal
from backend.model_catalog import require_allowed_models
from backend.models import Activity, ActivityStepVersion, ModelRun
from backend.test_activity_steps import STEP_TWO_OUTPUT
from backend.test_annual_planning import ANNUAL_INPUT, ANNUAL_OUTPUT
from backend.test_planning_stream import PlanningProvider, parse_events


class PlanningIndependentSessionTests(unittest.TestCase):
    def setUp(self):
        self.owner = uuid4()
        with SessionLocal() as db:
            activity = create_activity(title="独立事务年度生成竞争测试", idea=ANNUAL_INPUT["idea"], input_data=ANNUAL_INPUT, created_by=str(self.owner), session=db)
            self.activity_id = activity.id
            activity.status = "running"
            activity.current_step = 3
            activity.steps[0].status = "confirmed"
            activity.steps[0].output_json = {"standardizedBrief": {"objective": ANNUAL_INPUT["idea"], **{key: value for key, value in ANNUAL_INPUT.items() if key != "idea"}}, "missingFields": []}
            research = activity.steps[1]
            research.status = "confirmed"
            research.version = 2
            research.output_json = deepcopy(STEP_TWO_OUTPUT)
            db.add(ActivityStepVersion(activity_id=activity.id, step_no=2, version=2, input_json={"useWebSearch": False}, output_json=deepcopy(STEP_TWO_OUTPUT), status="review", changed_by=str(self.owner), change_type="generated"))
            activity.steps[2].status = "review"
            activity.steps[2].output_json = deepcopy(ANNUAL_OUTPUT)
            db.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(user_id=self.owner)
        app.dependency_overrides[require_allowed_models] = lambda: ("selected-model",)
        self.provider = PlanningProvider()
        app.dependency_overrides[get_model_provider] = lambda: self.provider
        # Deliberately do not override the database dependency. Every request
        # receives a fresh session, unlike shared-session integration fixtures.
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        with SessionLocal.begin() as db:
            db.execute(delete(Activity).where(Activity.created_by == str(self.owner)))

    def test_upstream_reopen_from_another_session_stops_units_and_preserves_output(self):
        def supersede(_key):
            with SessionLocal() as external:
                activity = get_owned_activity(activity_id=self.activity_id, owner_id=str(self.owner), session=external, lock=True)
                brief = activity.steps[0]
                reopen_step(activity=activity, step=brief, expected_version=brief.version, actor=str(self.owner), comment=None, session=external)
                external.commit()

        self.provider.on_call = supersede
        response = self.client.post(f"/api/activities/{self.activity_id}/steps/3/generate/stream", json={"version": 1, "model": "selected-model"})
        self.assertEqual(response.status_code, 200, response.text)
        events = parse_events(response.text)
        self.assertEqual(events[-1][0], "planning_failed", events)
        self.assertEqual(events[-1][1]["errorCode"], "GENERATION_SUPERSEDED")
        self.assertEqual(len(self.provider.calls), 1, "A superseded model run must never call another event unit")
        with SessionLocal() as verify:
            activity = get_owned_activity(activity_id=self.activity_id, owner_id=str(self.owner), session=verify)
            step = activity.steps[2]
            self.assertEqual(step.status, "needs_review", "Old model completion must not replace the upstream invalidation")
            self.assertEqual(step.output_json, ANNUAL_OUTPUT, "The existing draft must remain intact when generation is superseded")
            run = verify.scalar(select(ModelRun).where(ModelRun.generation_id == UUID(events[-1][1]["generationId"])))
            self.assertEqual((run.status, run.error_code, run.prompt_tokens), ("failed", "GENERATION_SUPERSEDED", 100))
            self.assertEqual([unit["status"] for unit in run.planning_progress["units"]], ["failed", "cancelled", "cancelled"])
            self.assertEqual(run.planning_progress["units"][0]["providerRequestId"], "planning-3-annual")


if __name__ == "__main__":
    unittest.main()
