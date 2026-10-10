from copy import deepcopy
from dataclasses import replace
import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.activity_api import get_model_provider
from backend.activity_steps import StepDomainError
from backend.auth import require_session
from backend.ccode_provider import CcodeTimeoutError, ModelResult
from backend.models import ModelRun
from backend.planning_api import stream_planning_generation
from backend.test_annual_planning import ANNUAL_INPUT, ANNUAL_OUTPUT
import backend.test_activity_steps as activity_tests


def generated_architecture():
    output = deepcopy(ANNUAL_OUTPUT)
    for index, event in enumerate(output["eventBriefs"], 1):
        event["id"] = f"event-{index}"
    return output


def parse_events(text):
    events = []
    for frame in text.split("\n\n"):
        if frame:
            name, data = frame.split("\n", 1)
            events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


class PlanningProvider:
    def __init__(self):
        self.calls = []
        self.fail_key = None
        self.on_call = None

    def generate(self, messages, *, model, metadata):
        self.calls.append((messages, metadata))
        key = metadata["planning_unit"]
        step_no = metadata["step_no"]
        if self.on_call:
            self.on_call(key)
        if key == self.fail_key:
            raise CcodeTimeoutError()
        architecture = generated_architecture()
        if step_no == 3:
            if key == "annual":
                output = {"annualNarrative": architecture["annualNarrative"], "eventSeeds": [
                    {field: value for field, value in event.items() if field not in {"sharedAssets", "highlights"}}
                    for event in architecture["eventBriefs"]]}
            else:
                event = next(item for item in architecture["eventBriefs"] if item["id"] == key)
                output = {field: event[field] for field in ("sharedAssets", "highlights")}
        elif step_no == 5:
            output = deepcopy(activity_tests.STEP_FIVE_OUTPUT)
            output.pop("totalAmount")
            for item in output["items"]:
                item.pop("subtotal")
                item.update(quantity=3.0, unitPrice=0.1)
                item["item"] = "共享导视费用" if key == "annual" else "当前活动专属费用"
        elif step_no == 9:
            context = json.loads(messages[1].content.split("\n", 1)[1])
            output = {"conclusions": ["基于已记录指标形成复盘"], "improvements": ["优化下一次活动"]} if "actualMetrics" in context else deepcopy(activity_tests.STEP_NINE_OUTPUT)
        else:
            output = deepcopy(activity_tests.valid_step_output(step_no))
        return ModelResult(text=json.dumps(output), model=model, provider_request_id=f"planning-{step_no}-{key}",
                           prompt_tokens=100, completion_tokens=20, total_tokens=120, duration_ms=25)


class PlanningStreamTests(unittest.TestCase):
    tracked_models = activity_tests.ActivityStepApiIntegrationTests.tracked_models
    setUp = activity_tests.ActivityStepApiIntegrationTests.setUp
    tearDown = activity_tests.ActivityStepApiIntegrationTests.tearDown
    _save_output = activity_tests.ActivityStepApiIntegrationTests._save_output
    _confirm = activity_tests.ActivityStepApiIntegrationTests._confirm

    @classmethod
    def setUpClass(cls):
        activity_tests.ActivityStepApiIntegrationTests.setUpClass.__func__(cls)

    def _prepare(self):
        created = self.client.post("/api/activities", json={"title": "年度规划流测试", "input": ANNUAL_INPUT})
        self.assertEqual(created.status_code, 201, created.text)
        activity_id = created.json()["id"]
        brief = {"standardizedBrief": {"objective": ANNUAL_INPUT["idea"], **{key: value for key, value in ANNUAL_INPUT.items() if key != "idea"}}, "missingFields": []}
        saved = self._save_output(activity_id, 1, 1, brief)
        self._confirm(activity_id, 1, saved["version"])
        saved = self._save_output(activity_id, 2, 2)
        self._confirm(activity_id, 2, saved["version"])
        provider = PlanningProvider()
        self.client.app.dependency_overrides[get_model_provider] = lambda: provider
        return activity_id, provider

    def _stream(self, activity_id, step_no, version=None):
        if version is None:
            version = self.client.get(f"/api/activities/{activity_id}/steps/{step_no}").json()["version"]
        response = self.client.post(f"/api/activities/{activity_id}/steps/{step_no}/generate/stream", json={"version": version, "model": "selected-model"})
        self.assertEqual(response.status_code, 200, response.text)
        return parse_events(response.text)

    def _complete_through(self, activity_id, last_step):
        for step_no in range(3, last_step + 1):
            events = self._stream(activity_id, step_no)
            self.assertEqual(events[-1][0], "planning_completed", events)
            self._confirm(activity_id, step_no, events[-1][1]["step"]["version"])

    def test_architecture_and_per_event_details_generate_sequentially_with_progress(self):
        activity_id, provider = self._prepare()
        provider.on_call = lambda _key: self.assertFalse(self.db.in_transaction())
        events = self._stream(activity_id, 3)
        self.assertEqual(events[-1][0], "planning_completed", events)
        final = events[-1][1]
        self.assertEqual(final["step"]["outputJson"], generated_architecture())
        self.assertEqual([metadata["planning_unit"] for _, metadata in provider.calls], ["annual", "event-1", "event-2"])
        self.assertEqual([payload["completedUnits"] for name, payload in events if name == "planning_progress"], [0, 0, 1, 1, 2, 2, 3])
        for index, (messages, _) in enumerate(provider.calls):
            context = json.loads(messages[1].content.split("\n", 1)[1])
            self.assertEqual(context["confirmedPreviousSteps"][0]["stepNo"], 1)
            self.assertEqual(set(context["requiredJsonSchema"]["properties"]), {"annualNarrative", "eventSeeds"} if index == 0 else {"sharedAssets", "highlights"})
            if index:
                self.assertNotIn("eventBriefs", context)
                self.assertNotIn("eventSeeds", context)
        run = self.db.scalar(select(ModelRun).where(ModelRun.generation_id == UUID(final["generationId"])))
        self.assertEqual((run.prompt_tokens, run.duration_ms, run.provider_request_id), (300, 75, None))
        progress = self.client.get(f"/api/activities/{activity_id}/steps/3/generate/progress")
        self.assertEqual(progress.json()["progress"]["status"], "completed")
        self.assertNotIn("providerRequestId", progress.text)

    def test_later_steps_use_only_current_event_and_shared_constraints_and_exact_budget(self):
        activity_id, provider = self._prepare()
        self._complete_through(activity_id, 3)
        provider.calls.clear()
        events = self._stream(activity_id, 4)
        self.assertEqual(events[-1][0], "planning_completed", events)
        output = events[-1][1]["step"]["outputJson"]
        self.assertEqual([item["eventId"] for item in output["eventPlans"]], ["event-1", "event-2"])
        for messages, metadata in provider.calls[1:]:
            context = json.loads(messages[1].content.split("\n", 1)[1])
            self.assertNotIn("eventBriefs", context)
            self.assertEqual(context["currentEventBrief"]["id"], metadata["planning_unit"])
            self.assertEqual(context["currentAnnualPlan"], output["annualPlan"])
        self._confirm(activity_id, 4, events[-1][1]["step"]["version"])
        provider.calls.clear()
        events = self._stream(activity_id, 5)
        self.assertEqual(events[-1][0], "planning_completed", events)
        budget = events[-1][1]["step"]["outputJson"]
        subtotal = 0.3 * len(activity_tests.STEP_FIVE_OUTPUT["items"])
        self.assertEqual(budget["annualPlan"]["totalAmount"], subtotal)
        self.assertEqual(budget["annualTotalAmount"], 0.9)
        for messages, metadata in provider.calls:
            context = json.loads(messages[1].content.split("\n", 1)[1])
            self.assertNotIn("totalAmount", context["requiredJsonSchema"]["properties"])
            if metadata["planning_unit"] != "annual":
                self.assertEqual(context["annualConstraints"][0]["stepNo"], 4)
                self.assertNotIn("eventPlans", context)

    def test_second_unit_failure_keeps_old_output_stops_later_units_and_can_retry(self):
        activity_id, provider = self._prepare()
        previous = self._stream(activity_id, 3)[-1][1]["step"]
        provider.calls.clear()
        provider.fail_key = "event-1"
        events = self._stream(activity_id, 3, previous["version"])
        final = events[-1][1]
        self.assertEqual(events[-1][0], "planning_failed")
        self.assertEqual(final["errorCode"], "PROVIDER_TIMEOUT")
        self.assertEqual([unit["status"] for unit in final["units"]], ["completed", "failed", "cancelled"])
        self.assertEqual(len(provider.calls), 2)
        saved = self.client.get(f"/api/activities/{activity_id}/steps/3").json()
        self.assertEqual((saved["status"], saved["outputJson"]), ("failed", previous["outputJson"]))
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/steps/3/generate/progress").json()["progress"], final)
        provider.fail_key = None
        self.assertEqual(self._stream(activity_id, 3, saved["version"])[-1][0], "planning_completed")

    def test_merge_failure_after_completed_units_does_not_replace_draft(self):
        activity_id, _provider = self._prepare()
        with patch("backend.planning_api.merge_planning_outputs", side_effect=StepDomainError("INVALID_MODEL_RESPONSE", "invalid merge")):
            events = self._stream(activity_id, 3)
        self.assertEqual(events[-1][0], "planning_failed")
        self.assertEqual(events[-1][1]["completedUnits"], 3)
        self.assertEqual(events[-1][1]["status"], "failed")
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/steps/3").json()["outputJson"], {})

    def test_validation_logs_current_unit_shape_without_response_values(self):
        activity_id, provider = self._prepare()
        original_generate = provider.generate
        def invalid_response(messages, *, model, metadata):
            result = original_generate(messages, model=model, metadata=metadata)
            if metadata["planning_unit"] == "event-1":
                return replace(result, text=json.dumps({"sharedAssets": [{"private_payload": "sensitive-response-content"}], "highlights": ["自然体验亮点"]}))
            return result
        provider.generate = invalid_response
        with self.assertLogs("backend.planning_api", level="WARNING") as captured:
            events = self._stream(activity_id, 3)
        self.assertEqual(events[-1][0], "planning_failed")
        logs = "\n".join(captured.output)
        diagnostic = json.loads(logs.split("activity_planning_generation_validation_failed ", 1)[1])
        self.assertEqual(diagnostic["unit"], "event-1")
        self.assertEqual(diagnostic["stage"], "schema_validation")
        self.assertEqual(diagnostic["errors"], [{"path": ["sharedAssets", 0], "type": "string_type"}])
        self.assertNotIn("sensitive-response-content", logs)
        self.assertNotIn("private_payload", logs)
        self.assertEqual(len(provider.calls), 2)

    def test_disconnect_stops_after_current_unit_and_retains_completed_audit(self):
        activity_id, provider = self._prepare()
        async def consume():
            request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
            response = stream_planning_generation(UUID(activity_id), 3, SimpleNamespace(version=2, model="selected-model"), request, self.current_user, self.db, provider, ("selected-model",))
            iterator = response.body_iterator
            await anext(iterator)
            await anext(iterator)
            await anext(iterator)
            await iterator.aclose()
        asyncio.run(consume())
        self.assertEqual(len(provider.calls), 1)
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == UUID(activity_id), ModelRun.step_no == 3))
        self.assertEqual((run.status, run.error_code, run.prompt_tokens), ("failed", "GENERATION_INTERRUPTED", 100))
        self.assertEqual([unit["status"] for unit in run.planning_progress["units"]], ["completed", "cancelled", "cancelled"])

    def test_upstream_change_supersedes_and_retains_provider_audit(self):
        activity_id, provider = self._prepare()
        def supersede(_key):
            step = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
            response = self.client.post(f"/api/activities/{activity_id}/steps/1/reopen", json={"version": step["version"]})
            self.assertEqual(response.status_code, 200)
        provider.on_call = supersede
        final = self._stream(activity_id, 3)[-1][1]
        self.assertEqual(final["errorCode"], "GENERATION_SUPERSEDED")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/steps/3").json()["status"], "needs_review")
        run = self.db.scalar(select(ModelRun).where(ModelRun.generation_id == UUID(final["generationId"])))
        self.assertEqual(run.prompt_tokens, 100)
        self.assertEqual(run.planning_progress["units"][0]["providerRequestId"], "planning-3-annual")

    def test_version_owner_auth_and_nonstream_boundaries_precede_provider(self):
        activity_id, provider = self._prepare()
        endpoint = f"/api/activities/{activity_id}/steps/3/generate"
        old = self.client.post(endpoint, json={"version": 2, "model": "selected-model"})
        self.assertEqual(old.json()["detail"]["code"], "USE_PLANNING_STREAM_ENDPOINT")
        bad = self.client.post(endpoint + "/stream", json={"version": 1, "model": "selected-model"})
        self.assertEqual(bad.json()["detail"]["code"], "VERSION_CONFLICT")
        self.current_user.user_id = uuid4()
        self.assertEqual(self.client.get(endpoint + "/progress").status_code, 404)
        self.assertEqual(self.client.post(endpoint + "/stream", json={"version": 2, "model": "selected-model"}).status_code, 404)
        self.client.app.dependency_overrides.pop(require_session)
        self.assertEqual(self.client.get(endpoint + "/progress").status_code, 401)
        self.assertEqual(provider.calls, [])

    def test_review_preserves_each_units_own_actual_metrics(self):
        activity_id, provider = self._prepare()
        self._complete_through(activity_id, 8)
        saved = self._stream(activity_id, 9)[-1][1]["step"]
        output = saved["outputJson"]
        units = [output["annualPlan"], *[item["output"] for item in output["eventPlans"]]]
        for index, unit in enumerate(units):
            unit["actualMetrics"] = [{"metric": "真实客流", "value": float(100 + index), "unit": "人", "sourceType": "actual", "basis": "运营方真实录入"}]
            unit["missingActualMetrics"] = []
        updated = self.client.patch(f"/api/activities/{activity_id}/steps/9", json={"version": saved["version"], "outputJson": output})
        self.assertEqual(updated.status_code, 200, updated.text)
        provider.calls.clear()
        events = self._stream(activity_id, 9, updated.json()["version"])
        self.assertEqual(events[-1][0], "planning_completed", events)
        result = events[-1][1]["step"]["outputJson"]
        for index, unit in enumerate([result["annualPlan"], *[item["output"] for item in result["eventPlans"]]]):
            self.assertEqual(unit["actualMetrics"], units[index]["actualMetrics"])
            context = json.loads(provider.calls[index][0][1].content.split("\n", 1)[1])
            self.assertEqual(context["actualMetrics"], units[index]["actualMetrics"])

    def test_changed_architecture_ids_keep_history_readable_but_require_fresh_outputs(self):
        activity_id, _provider = self._prepare()
        self._complete_through(activity_id, 9)
        original = self.client.get(f"/api/activities/{activity_id}").json()
        step3 = original["steps"][2]
        reopened = self.client.post(f"/api/activities/{activity_id}/steps/3/reopen", json={"version": step3["version"]})
        self.assertEqual(reopened.status_code, 200, reopened.text)
        architecture = deepcopy(step3["outputJson"])
        architecture["eventBriefs"][1]["id"] = "new-summer"
        architecture["eventBriefs"].append({**deepcopy(architecture["eventBriefs"][1]), "id": "new-autumn", "name": "秋季自然观察"})
        updated = self.client.patch(f"/api/activities/{activity_id}/steps/3", json={"version": reopened.json()["version"], "outputJson": architecture})
        self.assertEqual(updated.status_code, 200, updated.text)
        self._confirm(activity_id, 3, updated.json()["version"])
        history = self.client.get(f"/api/activities/{activity_id}")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()["steps"][3]["outputJson"], original["steps"][3]["outputJson"])
        stale_step = history.json()["steps"][3]
        rejected = self.client.post(f"/api/activities/{activity_id}/steps/4/confirm", json={"version": stale_step["version"]})
        self.assertEqual(rejected.json()["detail"]["code"], "PERSISTED_STEP_OUTPUT_INVALID")
        for step_no in range(4, 10):
            events = self._stream(activity_id, step_no)
            self.assertEqual(events[-1][0], "planning_completed", events)
            saved = events[-1][1]["step"]
            self.assertEqual([item["eventId"] for item in saved["outputJson"]["eventPlans"]], ["event-1", "new-summer", "new-autumn"])
            self._confirm(activity_id, step_no, saved["version"])

    def test_planning_mode_is_locked_after_outputs_exist(self):
        activity_id, _provider = self._prepare()
        brief = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
        reopened = self.client.post(f"/api/activities/{activity_id}/steps/1/reopen", json={"version": brief["version"]})
        self.assertEqual(reopened.status_code, 200, reopened.text)
        mode_change = self.client.patch(f"/api/activities/{activity_id}/steps/1", json={"version": reopened.json()["version"], "inputJson": {"idea": "尝试切换", "planningMode": "single"}})
        self.assertEqual(mode_change.json()["detail"]["code"], "PLANNING_MODE_LOCKED")


if __name__ == "__main__":
    unittest.main()
