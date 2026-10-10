from __future__ import annotations

import json
import unittest
import httpx
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.activity_api import (
    _provider_public_error,
    _provider_status,
    get_activity_db_session,
    get_model_provider,
    router,
)
from backend.activity_steps import (
    StepDomainError,
    build_generation_messages,
    complete_generation,
    find_step,
    get_owned_activity,
    patch_step,
    reopen_step,
    start_generation,
)
from backend.auth import require_session
from backend.auth import get_db_session
from backend.app.routers.research import router as research_router
from backend.app.routers.test_research_route import _LongEvidenceProvider
from backend.ccode_provider import (
    CcodeAuthenticationError,
    CcodeBalanceError,
    CcodeConfigurationError,
    CcodeInvalidResponseError,
    CcodeModelUnavailableError,
    CcodeNetworkError,
    CcodeProviderError,
    CcodeRateLimitError,
    CcodeRequestRejectedError,
    CcodeTimeoutError,
    CcodeUpstreamError,
    ModelResult,
)
from backend.db import SessionLocal, engine
from backend.models import (
    Activity,
    ActivityStep,
    ActivityStepConfirmation,
    ActivityStepVersion,
    ExecutionTask,
    ModelRun,
    SourceReference,
    STEP_KEYS,
)
from backend.model_catalog import require_allowed_models


STEP_ONE_OUTPUT = {
    "standardizedBrief": {
        "objective": "Build a measurable evening cultural market",
        "location": "Riverside park",
        "target": "Visitor growth and secondary spending",
        "budgetMin": 10000,
        "budgetMax": 50000,
        "targetAudience": "Local families and weekend visitors",
        "knownConstraints": "Outdoor venue",
    },
    "missingFields": ["计划开始时间", "计划结束时间"],
}

STEP_TWO_OUTPUT = {
    "summary": "Only supplied facts were assessed",
    "findings": ["The location is Riverside park"],
    "sources": [
        {"sourceType": "actual", "label": "User activity brief"},
        {"sourceType": "missing", "label": "Public trend data not retrieved"},
    ],
    "risks": ["Public trend evidence is unavailable"],
}

STEP_THREE_OUTPUT = {
    "candidates": [
        {
            "id": "family-night",
            "name": "Family Riverside Night",
            "storyline": "A family journey following the river lights",
            "visualDirection": "Warm lanterns and clear wayfinding",
            "highlights": ["Family missions", "Night market"],
        },
        {
            "id": "river-memory",
            "name": "River Memory",
            "storyline": "Local stories unfold along the waterfront",
            "visualDirection": "Historic textures with modern lighting",
            "highlights": ["Story stations", "Local performances"],
        },
    ]
}

STEP_FOUR_OUTPUT = {
    "schedule": [{"time": "17:30", "title": "Opening", "description": "Open visitor zones"}],
    "zones": [
        {
            "name": "Family zone",
            "purpose": "Host family missions",
            "activities": ["Stamp trail"],
            "requirements": ["Queue barriers"],
        }
    ],
    "personnel": [
        {"role": "Coordinator", "count": 2, "responsibilities": ["Visitor flow"]}
    ],
    "safetyRequirements": ["Maintain emergency access"],
}

STEP_FIVE_OUTPUT = {
    "items": [
        {
            "item": "Stage lighting",
            "category": "production",
            "quantity": 2.0,
            "unit": "set",
            "unitPrice": 5000.0,
            "subtotal": 10000.0,
            "sourceType": "calculated",
            "basis": "Two performance zones",
        }
    ],
    "totalAmount": 10000.0,
    "savings": [{"action": "Reuse fixtures", "estimatedSaving": 1000.0, "impact": "None"}],
    "resources": [{"name": "Lighting set", "quantity": 2.0, "unit": "set", "purpose": "Stage"}],
    "budgetNote": "Reference estimate pending supplier confirmation",
}

STEP_SIX_OUTPUT = {
    "strategy": "Reach local families with a staged campaign",
    "phases": [
        {"phase": "warmup", "objective": "Awareness", "channels": ["WeChat"], "contentDrafts": ["Preview draft"], "materials": ["Poster"]},
        {"phase": "peak", "objective": "Attendance", "channels": ["Short video"], "contentDrafts": ["Opening draft"], "materials": ["Video"]},
        {"phase": "followup", "objective": "Retention", "channels": ["Member channel"], "contentDrafts": ["Recap draft"], "materials": ["Photo set"]},
    ],
}

STEP_SEVEN_OUTPUT = {
    "tasks": [
        {
            "title": "Confirm lighting supplier",
            "description": "Review quotation and production schedule",
            "owner": "Production lead",
            "dueAt": "2026-10-01T18:00:00+08:00",
            "dependencies": ["Budget confirmation"],
            "approvalDraft": "Approval request draft",
            "supplierInquiryDraft": "Quotation request draft",
        }
    ],
    "approvalSummary": "All external actions await human confirmation",
    "externalActionsDraftOnly": True,
}

STEP_EIGHT_OUTPUT = {
    "channelActions": [
        {
            "channel": "Local hotel partners",
            "objective": "Package sales",
            "actions": ["Prepare joint package draft"],
            "revenueModel": "Revenue-share reference plan",
            "draftTerms": "Draft terms pending review",
        }
    ],
    "sponsorshipPackages": [
        {
            "name": "Family zone partner",
            "targetPartner": "Family brands",
            "benefits": ["Draft signage placement"],
            "referencePrice": 20000.0,
            "sourceType": "calculated",
            "basis": "Comparable placement estimate",
        }
    ],
    "ticketingPlan": "Draft bundled ticket plan",
    "secondarySalesPlan": "Draft food and merchandise plan",
    "externalActionsDraftOnly": True,
}

STEP_NINE_OUTPUT = {
    "forecastMetrics": [
        {"metric": "attendance", "value": 3000.0, "unit": "visitors", "sourceType": "calculated", "basis": "Venue capacity model"}
    ],
    "actualMetrics": [],
    "missingActualMetrics": ["attendance", "revenue", "cost", "exposure", "engagement", "conversion"],
    "conclusions": ["Actual performance cannot be concluded before data entry"],
    "improvements": ["Collect gate counts and transaction data"],
}


def valid_step_output(step_no: int) -> dict:
    return {
        1: STEP_ONE_OUTPUT,
        2: STEP_TWO_OUTPUT,
        3: STEP_THREE_OUTPUT,
        4: STEP_FOUR_OUTPUT,
        5: STEP_FIVE_OUTPUT,
        6: STEP_SIX_OUTPUT,
        7: STEP_SEVEN_OUTPUT,
        8: STEP_EIGHT_OUTPUT,
        9: STEP_NINE_OUTPUT,
    }[step_no]


class FakeProvider:
    def __init__(self, *, output: dict | None = None, error: Exception | None = None) -> None:
        self.output = output or STEP_ONE_OUTPUT
        self.error = error
        self.calls = []
        self.models = []
        self.on_generate = None

    def generate(self, messages, *, model, metadata=None) -> ModelResult:
        self.calls.append((messages, metadata))
        self.models.append(model)
        if self.on_generate is not None:
            self.on_generate(metadata)
        if self.error is not None:
            raise self.error
        output = deepcopy(self.output)
        if metadata and "research_scope" in metadata:
            scoped = json.loads(messages[1].content.split("\n", 1)[1])["publicSearchEvidence"]
            for source in output.get("sources", []):
                if source.get("sourceType") == "public" and source.get("scope") != metadata["research_scope"]:
                    source.clear()
                    source.update(sourceType="public", **scoped[0])
                    source["excerpt"] = scoped[0]["excerpt"][:200]
        return ModelResult(
            text=json.dumps(output),
            model="test-structured-model",
            provider_request_id="test-request-id",
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            duration_ms=15,
        )


def generate_research_test(client, activity_id, version):
    response = client.post(f"/api/activities/{activity_id}/research/generate/stream",
                           json={"version": version, "model": "selected-model"})
    if response.status_code != 200:
        return response
    frames = [frame for frame in response.text.split("\n\n") if frame]
    name, serialized = frames[-1].split("\n", 1)
    final = json.loads(serialized.removeprefix("data: "))
    if name == "event: research_completed":
        return httpx.Response(200, json=final["step"])
    if name != "event: research_failed":
        raise AssertionError("Research stream ended without a terminal event")
    return httpx.Response(504 if final["errorCode"] == "PROVIDER_TIMEOUT" else 502,
                          json={"detail": {"code": final["errorCode"]}})


class ProviderErrorMappingTests(unittest.TestCase):
    def test_browser_error_codes_do_not_expose_provider_implementation(self) -> None:
        cases = [
            (CcodeConfigurationError(), "PROVIDER_NOT_CONFIGURED"),
            (CcodeAuthenticationError(), "PROVIDER_AUTH_ERROR"),
            (CcodeBalanceError(), "PROVIDER_BALANCE_ERROR"),
            (CcodeRateLimitError(), "PROVIDER_RATE_LIMITED"),
            (CcodeModelUnavailableError(), "MODEL_UNAVAILABLE"),
            (CcodeTimeoutError(), "PROVIDER_TIMEOUT"),
            (CcodeNetworkError(), "PROVIDER_UNAVAILABLE"),
            (CcodeUpstreamError(), "PROVIDER_UNAVAILABLE"),
            (CcodeRequestRejectedError(), "PROVIDER_UNAVAILABLE"),
            (CcodeInvalidResponseError(), "INVALID_MODEL_RESPONSE"),
        ]
        for error, expected_code in cases:
            with self.subTest(error=type(error).__name__):
                code, message = _provider_public_error(error)
                self.assertEqual(code, expected_code)
                self.assertNotIn("CCODE", code)
                self.assertNotIn("Ccode", message)

    def test_unknown_provider_error_code_fails_explicitly(self) -> None:
        error = CcodeProviderError()
        with self.assertRaisesRegex(RuntimeError, "Unsupported provider error code"):
            _provider_public_error(error)
        with self.assertRaisesRegex(RuntimeError, "Unsupported provider error code"):
            _provider_status(error)


class GenerationPromptContractTests(unittest.TestCase):
    def test_all_implemented_steps_require_optional_fields_to_be_omitted(self) -> None:
        for step_no in range(1, 10):
            with self.subTest(step_no=step_no):
                step = SimpleNamespace(
                    step_no=step_no,
                    step_key=STEP_KEYS[step_no - 1],
                    status="draft",
                    input_json={},
                    output_json={},
                )
                activity = SimpleNamespace(
                    input={"idea": "Plan an event"},
                    search_enabled=False,
                    steps=(
                        [
                            SimpleNamespace(
                                step_no=2,
                                step_key="research",
                                status="confirmed",
                                input_json={"useWebSearch": False},
                                output_json=STEP_TWO_OUTPUT,
                            ),
                            step,
                        ]
                        if step_no >= 3
                        else [step]
                    ),
                )

                messages = build_generation_messages(activity, step)
                system_prompt = messages[0]["content"]
                generation_prompt = messages[1]["content"]

                self.assertIn("所有层级", system_prompt)
                self.assertIn("嵌套对象和数组元素", system_prompt)
                self.assertIn("完全省略对应键", system_prompt)
                self.assertIn("绝不输出 JSON null", system_prompt)
                self.assertIn("首字符必须是 {，末字符必须是 }", system_prompt)
                self.assertIn("不得使用 Markdown 代码块", system_prompt)
                self.assertIn("首字符必须是 {，末字符必须是 }", generation_prompt)
                self.assertIn("禁止 Markdown 代码围栏", generation_prompt)

        budget_step = SimpleNamespace(
            step_no=5,
            step_key="budget",
            status="draft",
            input_json={},
            output_json={},
        )
        budget_messages = build_generation_messages(
            SimpleNamespace(
                input={"idea": "Plan an event"},
                search_enabled=False,
                steps=[
                    SimpleNamespace(
                        step_no=2,
                        step_key="research",
                        status="confirmed",
                        input_json={"useWebSearch": False},
                        output_json=STEP_TWO_OUTPUT,
                    ),
                    budget_step,
                ],
            ),
            budget_step,
        )
        instruction, serialized_context = budget_messages[1]["content"].split("\n", 1)
        budget_schema = json.loads(serialized_context)["requiredJsonSchema"]
        item_schema = budget_schema["$defs"]["BudgetDraftItem"]
        self.assertFalse(budget_schema["additionalProperties"])
        self.assertFalse(item_schema["additionalProperties"])
        self.assertNotIn("subtotal", item_schema["properties"])
        self.assertNotIn("totalAmount", budget_schema["properties"])
        self.assertIn("不得输出 `subtotal`、`totalAmount`", budget_messages[0]["content"])
        self.assertIn("禁止输出 subtotal、totalAmount", instruction)
        self.assertIn("服务端", instruction)

        step_one = SimpleNamespace(
            step_no=1,
            step_key="brief",
            status="draft",
            input_json={},
            output_json={},
        )
        step_one_prompt = build_generation_messages(
            SimpleNamespace(
                input={"idea": "Plan an event"},
                search_enabled=False,
                steps=[step_one],
            ),
            step_one,
        )[0]["content"]
        self.assertIn("missingFields", step_one_prompt)

    def test_step_four_prompt_forbids_placeholder_and_corrected_second_object(self) -> None:
        step = SimpleNamespace(
            step_no=4,
            step_key="content_space",
            status="draft",
            input_json={},
            output_json={},
        )
        prompt = build_generation_messages(
            SimpleNamespace(
                input={"idea": "Plan an event"},
                search_enabled=False,
                steps=[
                    SimpleNamespace(
                        step_no=2,
                        step_key="research",
                        status="confirmed",
                        input_json={"useWebSearch": False},
                        output_json=STEP_TWO_OUTPUT,
                    ),
                    step,
                ],
            ),
            step,
        )[0]["content"]

        self.assertIn("zones", prompt)
        self.assertIn("必须全部直接输出为 JSON 数组", prompt)
        self.assertIn("严禁输出对象占位符", prompt)
        self.assertIn("$dummy", prompt)
        self.assertIn("禁止先输出草稿", prompt)
        self.assertIn("追加第二个 JSON 对象", prompt)
        self.assertIn("不得展示检查过程", prompt)

    def test_steps_three_to_nine_receive_complete_confirmed_research_evidence(self) -> None:
        research_output = {
            "summary": "检索到节假日客流与同类活动资料",
            "findings": ["国庆期间周边短途客流增长"],
            "sources": [
                {
                    "sourceType": "public",
                    "label": "文旅市场公开报告",
                    "url": "https://example.com/report",
                    "capturedAt": "2026-09-24T10:00:00+08:00",
                    "publishedAt": "2026-09-20",
                    "siteName": "示例文旅网",
                    "authorityLevel": "high",
                    "rank": 2,
                    "providerRequestId": "search-request-1",
                    "scope": "public_trend",
                    "excerpt": "报告显示国庆期间周边短途客流增长。",
                }
            ],
            "risks": ["公开趋势不能替代景区实际客流数据"],
        }
        research_step = SimpleNamespace(
            step_no=2,
            step_key="research",
            status="confirmed",
            input_json={"useWebSearch": True},
            output_json=research_output,
        )

        for step_no in range(3, 10):
            with self.subTest(step_no=step_no):
                target_step = SimpleNamespace(
                    step_no=step_no,
                    step_key=STEP_KEYS[step_no - 1],
                    status="draft",
                    input_json={},
                    output_json={},
                )
                messages = build_generation_messages(
                    SimpleNamespace(
                        input={"idea": "策划山水夜游活动"},
                        search_enabled=True,
                        steps=[research_step, target_step],
                    ),
                    target_step,
                )

                instruction, serialized_context = messages[1]["content"].split("\n", 1)
                context = json.loads(serialized_context)
                evidence = context["confirmedResearchEvidence"]

                self.assertIn("必须实质参考 confirmedResearchEvidence", instruction)
                self.assertIn("不得忽略、改写或伪造", instruction)
                self.assertEqual(evidence["summary"], research_output["summary"])
                self.assertEqual(evidence["findings"], research_output["findings"])
                self.assertEqual(evidence["risks"], research_output["risks"])
                self.assertEqual(evidence["sources"], research_output["sources"])
                self.assertNotIn(2, [item["stepNo"] for item in context["confirmedPreviousSteps"]])
                self.assertEqual(context["confirmedPreviousSteps"], [])
                self.assertEqual(serialized_context.count(research_output["sources"][0]["url"]), 1)
                self.assertEqual(
                    serialized_context.count(research_output["sources"][0]["providerRequestId"]),
                    1,
                )

    def test_later_step_prompt_rejects_invalid_persisted_research_evidence(self) -> None:
        research_step = SimpleNamespace(
            step_no=2,
            step_key="research",
            status="confirmed",
            input_json={"useWebSearch": True},
            output_json={
                "summary": "检索完成",
                "findings": ["发现"],
                "sources": [
                    {
                        "sourceType": "public",
                        "label": "来源",
                        "url": "https://example.com/report",
                        "capturedAt": "2026-09-24T10:00:00+08:00",
                        "excerpt": "摘要",
                        "unknownMetadata": "不受支持",
                    }
                ],
                "risks": [],
            },
        )
        target_step = SimpleNamespace(
            step_no=3,
            step_key="theme",
            status="draft",
            input_json={},
            output_json={},
        )

        with self.assertRaises(StepDomainError) as raised:
            build_generation_messages(
                SimpleNamespace(
                    input={"idea": "策划活动"},
                    search_enabled=True,
                    steps=[research_step, target_step],
                ),
                target_step,
            )

        self.assertEqual(raised.exception.code, "PERSISTED_STEP_OUTPUT_INVALID")

    def test_execution_plan_prompt_includes_only_execution_inputs_and_research_evidence(self) -> None:
        research_output = deepcopy(STEP_TWO_OUTPUT)
        prior_steps = [
            SimpleNamespace(
                step_no=step_no,
                step_key=STEP_KEYS[step_no - 1],
                status="confirmed",
                input_json={"inputFor": step_no},
                output_json=(research_output if step_no == 2 else {"outputFor": step_no}),
            )
            for step_no in range(1, 7)
        ]
        execution_step = SimpleNamespace(
            step_no=7,
            step_key="execution_plan",
            status="draft",
            input_json={},
            output_json={},
        )

        messages = build_generation_messages(
            SimpleNamespace(
                input={"idea": "Plan an event"},
                search_enabled=False,
                steps=[*prior_steps, execution_step],
            ),
            execution_step,
        )
        _, serialized_context = messages[1]["content"].split("\n", 1)
        context = json.loads(serialized_context)

        self.assertEqual(
            [item["stepNo"] for item in context["confirmedPreviousSteps"]],
            [4, 5, 6],
        )
        self.assertEqual(context["confirmedResearchEvidence"], research_output)

    def test_review_prompt_with_saved_actual_metrics_requests_only_analysis(self) -> None:
        saved_review = deepcopy(STEP_NINE_OUTPUT)
        saved_review["actualMetrics"] = [
            {
                "metric": "attendance",
                "value": 2764.0,
                "unit": "visitors",
                "sourceType": "actual",
                "basis": "Gate counter export",
            }
        ]
        saved_review["missingActualMetrics"] = ["revenue", "satisfaction"]
        review_step = SimpleNamespace(
            step_no=9,
            step_key="review",
            status="review",
            input_json={},
            output_json=saved_review,
        )
        messages = build_generation_messages(
            SimpleNamespace(
                input={"idea": "Plan an event"},
                search_enabled=False,
                steps=[
                    SimpleNamespace(
                        step_no=2,
                        step_key="research",
                        status="confirmed",
                        input_json={"useWebSearch": False},
                        output_json=STEP_TWO_OUTPUT,
                    ),
                    review_step,
                ],
            ),
            review_step,
        )

        instruction, serialized_context = messages[1]["content"].split("\n", 1)
        context = json.loads(serialized_context)
        schema = context["requiredJsonSchema"]

        self.assertEqual(set(schema["properties"]), {"conclusions", "improvements"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(context["forecastMetrics"], saved_review["forecastMetrics"])
        self.assertEqual(context["actualMetrics"], saved_review["actualMetrics"])
        self.assertEqual(context["missingActualMetrics"], saved_review["missingActualMetrics"])
        self.assertIn("只能基于上下文中的 forecastMetrics、actualMetrics", instruction)
        self.assertIn("不得改写、删除、补充或重新判断任何指标", instruction)


class ActivityStepApiIntegrationTests(unittest.TestCase):
    tracked_models = (
        Activity,
        ActivityStep,
        ActivityStepVersion,
        ActivityStepConfirmation,
        ModelRun,
        SourceReference,
        ExecutionTask,
    )

    @classmethod
    def setUpClass(cls) -> None:
        with SessionLocal() as session:
            cls.initial_counts = {
                model: session.scalar(select(func.count()).select_from(model))
                for model in cls.tracked_models
            }

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
            account="planner@example.test",
            display_name="Planner",
            role_id="creative-design",
        )
        self.provider = FakeProvider()
        app = FastAPI()
        app.include_router(router)
        app.include_router(research_router)
        self.search_provider = _LongEvidenceProvider()
        app.state.research_provider = self.search_provider
        app.dependency_overrides[require_session] = lambda: self.current_user
        app.dependency_overrides[get_activity_db_session] = lambda: self.db
        app.dependency_overrides[get_db_session] = lambda: self.db
        app.dependency_overrides[get_model_provider] = lambda: self.provider
        app.dependency_overrides[require_allowed_models] = lambda: ("selected-model",)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()
        with SessionLocal() as session:
            final_counts = {
                model: session.scalar(select(func.count()).select_from(model))
                for model in self.tracked_models
            }
        self.assertEqual(final_counts, self.initial_counts)

    def _create_activity(self) -> dict:
        response = self.client.post(
            "/api/activities",
            json={
                "title": "Riverside Festival",
                "input": {
                    "idea": "Build an evening cultural market",
                    "location": "Riverside park",
                    "budgetMin": 10000,
                    "budgetMax": 50000,
                },
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _save_output(self, activity_id: str, step_no: int, version: int, output: dict | None = None) -> dict:
        if step_no == 2:
            step = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
            if not step["outputJson"]:
                previous_output = self.provider.output
                self.provider.output = output or valid_step_output(step_no)
                try:
                    response = self.client.post(
                        f"/api/activities/{activity_id}/steps/2/generate",
                        json={"version": version, "model": "selected-model"},
                    )
                finally:
                    self.provider.output = previous_output
                self.assertEqual(response.status_code, 200, response.text)
                return response.json()
        payload = {"version": version, "outputJson": output or valid_step_output(step_no)}
        if step_no == 3:
            payload["inputJson"] = {"selectedThemeId": "family-night"}
        response = self.client.patch(
            f"/api/activities/{activity_id}/steps/{step_no}",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _confirm(self, activity_id: str, step_no: int, version: int, comment: str | None = None) -> dict:
        payload = {"version": version}
        if comment is not None:
            payload["comment"] = comment
        response = self.client.post(
            f"/api/activities/{activity_id}/steps/{step_no}/confirm",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_generate_confirm_history_version_conflict_and_owner_isolation(self) -> None:
        activity = self._create_activity()
        activity_id = activity["id"]
        observed_generation_state = {}

        def inspect_started_generation(metadata) -> None:
            step = self.db.scalar(
                select(ActivityStep).where(
                    ActivityStep.activity_id == activity_id,
                    ActivityStep.step_no == 1,
                )
            )
            run = self.db.scalar(
                select(ModelRun).where(ModelRun.generation_id == metadata["generation_id"])
            )
            observed_generation_state.update(step_status=step.status, run_status=run.status)

        self.provider.on_generate = inspect_started_generation

        locked = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": 1, "outputJson": {"draft": "not allowed"}},
        )
        self.assertEqual(locked.status_code, 409)
        self.assertEqual(locked.json()["detail"]["code"], "STEP_LOCKED")

        for invalid_payload in (
            {"version": 1},
            {"version": 1, "model": ""},
            {"version": 1, "model": " selected-model"},
            {"version": 1, "model": "selected-model "},
            {"version": 1, "model": "m" * 201},
        ):
            with self.subTest(invalid_payload=invalid_payload):
                invalid_model = self.client.post(
                    f"/api/activities/{activity_id}/steps/1/generate",
                    json=invalid_payload,
                )
                self.assertEqual(invalid_model.status_code, 422, invalid_model.text)

        rejected_model = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": 1, "model": "not-allowed-model"},
        )
        self.assertEqual(rejected_model.status_code, 422, rejected_model.text)
        self.assertEqual(rejected_model.json()["detail"]["code"], "MODEL_NOT_ALLOWED")
        unchanged_step = self.db.scalar(
            select(ActivityStep).where(
                ActivityStep.activity_id == activity_id,
                ActivityStep.step_no == 1,
            )
        )
        self.assertEqual((unchanged_step.status, unchanged_step.version), ("draft", 1))
        self.assertIsNone(
            self.db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id))
        )
        self.assertEqual(self.provider.calls, [])

        generated = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": 1, "model": "selected-model"},
        )
        self.assertEqual(generated.status_code, 200, generated.text)
        generated_step = generated.json()
        self.assertEqual(generated_step["status"], "review")
        self.assertEqual(generated_step["version"], 2)
        self.assertEqual(generated_step["outputJson"], STEP_ONE_OUTPUT)
        self.assertEqual(self.provider.calls[0][1]["step_no"], 1)
        self.assertEqual(self.provider.models, ["selected-model"])
        self.assertEqual(observed_generation_state, {"step_status": "generating", "run_status": "running"})
        self.assertNotIn("activityTitle", self.provider.calls[0][0][1].content)
        self.assertNotIn("Riverside Festival", self.provider.calls[0][0][1].content)

        stale = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={"version": 1, "inputJson": {"note": "stale"}},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["code"], "VERSION_CONFLICT")

        for invalid_comment in (None, "   "):
            invalid_confirmation = self.client.post(
                f"/api/activities/{activity_id}/steps/1/confirm",
                json={"version": 2, "comment": invalid_comment},
            )
            self.assertEqual(invalid_confirmation.status_code, 422, invalid_confirmation.text)

        confirmed = self._confirm(activity_id, 1, 2, "Brief accepted")
        self.assertEqual(confirmed["status"], "confirmed")
        self.assertEqual(confirmed["confirmedBy"], str(self.current_user.user_id))
        refreshed = self.client.get(f"/api/activities/{activity_id}/steps")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json()[1]["status"], "draft")
        self.assertEqual(refreshed.json()[1]["version"], 2)

        versions = self.db.scalars(
            select(ActivityStepVersion)
            .where(ActivityStepVersion.activity_id == activity_id, ActivityStepVersion.step_no == 1)
            .order_by(ActivityStepVersion.version)
        ).all()
        self.assertEqual([(item.version, item.change_type) for item in versions], [(1, "initial"), (2, "generated")])
        self.assertTrue(all(item.changed_by == str(self.current_user.user_id) for item in versions))
        confirmation = self.db.scalar(
            select(ActivityStepConfirmation).where(
                ActivityStepConfirmation.activity_id == activity_id,
                ActivityStepConfirmation.step_no == 1,
            )
        )
        self.assertEqual(confirmation.comment, "Brief accepted")
        self.assertEqual(confirmation.confirmed_by, str(self.current_user.user_id))
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id))
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.model, "selected-model")
        self.assertEqual(run.total_tokens, 200)
        self.assertEqual(run.provider_request_id, "test-request-id")

        self.current_user.user_id = uuid4()
        hidden = self.client.get(f"/api/activities/{activity_id}/steps/1")
        self.assertEqual(hidden.status_code, 404)

    def test_confirmed_edit_marks_downstream_and_reopen_comment_is_audited(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        step2 = self._save_output(activity_id, 2, 2)
        self._confirm(activity_id, 2, step2["version"])

        rejected_patch = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={
                "version": step1["version"],
                "inputJson": {
                    "idea": "Build an evening cultural market with a family zone",
                    "location": "Riverside park",
                    "budgetMin": 10000,
                    "budgetMax": 50000,
                    "knownConstraints": "Keep family zone",
                },
            },
        )
        self.assertEqual(rejected_patch.status_code, 409, rejected_patch.text)
        self.assertEqual(rejected_patch.json()["detail"]["code"], "STEP_REOPEN_REQUIRED")
        rejected_generate = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": step1["version"], "model": "selected-model"},
        )
        self.assertEqual(rejected_generate.status_code, 409, rejected_generate.text)
        self.assertEqual(rejected_generate.json()["detail"]["code"], "STEP_REOPEN_REQUIRED")

        for invalid_comment in (None, "   "):
            invalid_reopen = self.client.post(
                f"/api/activities/{activity_id}/steps/1/reopen",
                json={"version": step1["version"], "comment": invalid_comment},
            )
            self.assertEqual(invalid_reopen.status_code, 422, invalid_reopen.text)

        reopened = self.client.post(
            f"/api/activities/{activity_id}/steps/1/reopen",
            json={"version": step1["version"], "comment": "Business owner changed the objective"},
        )
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(reopened.json()["status"], "draft")
        steps = self.client.get(f"/api/activities/{activity_id}/steps").json()
        self.assertEqual(steps[1]["status"], "needs_review")
        self.assertEqual(steps[2]["status"], "needs_review")
        self.assertEqual(steps[1]["outputJson"], step2["outputJson"])

        changed = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={
                "version": reopened.json()["version"],
                "inputJson": {
                    "idea": "Build an evening cultural market with a family zone",
                    "location": "Riverside park",
                    "budgetMin": 10000,
                    "budgetMax": 50000,
                    "knownConstraints": "Keep family zone",
                },
            },
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()["status"], "needs_review")
        activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertEqual(activity["currentStep"], 1)
        self.assertEqual(
            activity["input"]["idea"],
            "Build an evening cultural market with a family zone",
        )
        self.assertEqual(activity["input"]["knownConstraints"], "Keep family zone")

        snapshot = self.db.scalar(
            select(ActivityStepVersion).where(
                ActivityStepVersion.activity_id == activity_id,
                ActivityStepVersion.step_no == 1,
                ActivityStepVersion.version == reopened.json()["version"],
            )
        )
        self.assertEqual(snapshot.change_type, "reopened")
        self.assertEqual(snapshot.change_reason, "Business owner changed the objective")

    def test_step_two_search_choice_is_validated_and_atomically_synced(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])

        self.provider.output = {
            "summary": "Only supplied facts were assessed",
            "findings": ["The location is Riverside park"],
            "sources": [{"sourceType": "actual", "label": "User activity brief"}],
            "risks": [],
        }
        baseline = self.client.post(
            f"/api/activities/{activity_id}/steps/2/generate",
            json={"version": 2, "model": "selected-model"},
        )
        self.assertEqual(baseline.status_code, 200, baseline.text)

        invalid = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": baseline.json()["version"], "inputJson": {"useWebSearch": "yes"}},
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(invalid.json()["detail"]["code"], "INVALID_STEP_INPUT")

        saved = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": baseline.json()["version"], "inputJson": {"useWebSearch": True}},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["inputJson"], {"useWebSearch": True})
        self.assertEqual(saved.json()["status"], "needs_review")
        self.assertEqual(saved.json()["outputJson"], baseline.json()["outputJson"])
        activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertTrue(activity["searchEnabled"])

        with_sources = self._save_output(activity_id, 2, saved.json()["version"])
        sources = self.db.scalars(
            select(SourceReference)
            .where(SourceReference.activity_id == activity_id, SourceReference.step_no == 2)
            .order_by(SourceReference.label)
        ).all()
        self.assertEqual(
            [(source.source_type, source.label) for source in sources],
            [
                ("missing", "Public trend data not retrieved"),
                ("actual", "User activity brief"),
            ],
        )

        replacement_output = {
            "summary": "A bounded reference estimate was prepared",
            "findings": ["Attendance remains an estimate"],
            "sources": [
                {
                    "sourceType": "calculated",
                    "label": "Reference attendance",
                    "reasoning": "Last comparable event attendance multiplied by the documented weekend factor",
                },
                {
                    "sourceType": "missing",
                    "label": "Public trend data not retrieved",
                    "reasoning": "Web search is not implemented in this workflow",
                },
            ],
            "risks": ["Actual attendance may differ"],
        }
        replaced = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": with_sources["version"], "outputJson": replacement_output},
        )
        self.assertEqual(replaced.status_code, 200, replaced.text)
        replaced_sources = self.db.scalars(
            select(SourceReference)
            .where(SourceReference.activity_id == activity_id, SourceReference.step_no == 2)
            .order_by(SourceReference.label)
        ).all()
        self.assertEqual(len(replaced_sources), 2)
        calculated = next(source for source in replaced_sources if source.source_type == "calculated")
        self.assertIn("weekend factor", calculated.reasoning)

    def test_step_one_input_uses_the_complete_activity_brief_contract(self) -> None:
        activity_id = self._create_activity()["id"]
        invalid = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={
                "version": 1,
                "inputJson": {
                    "idea": "Invalid budget",
                    "budgetMin": 50000,
                    "budgetMax": 10000,
                    "legacyField": "not accepted",
                },
            },
        )
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(invalid.json()["detail"]["code"], "INVALID_STEP_INPUT")
        activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertEqual(activity["input"]["idea"], "Build an evening cultural market")
        step1 = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
        self.assertEqual((step1["version"], step1["status"]), (1, "draft"))

        explicit_null = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={"version": 1, "inputJson": {"idea": "Idea", "location": None}},
        )
        self.assertEqual(explicit_null.status_code, 422, explicit_null.text)
        self.assertEqual(explicit_null.json()["detail"]["code"], "INVALID_STEP_INPUT")

    def test_step_save_touches_running_activity_updated_at(self) -> None:
        activity_id = self._create_activity()["id"]
        first_save = self._save_output(activity_id, 1, 1)
        first_activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertEqual(first_activity["status"], "running")

        second_save = self._save_output(activity_id, 1, first_save["version"])
        second_activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertEqual(second_save["version"], first_save["version"] + 1)
        self.assertGreater(
            datetime.fromisoformat(second_activity["updatedAt"]),
            datetime.fromisoformat(first_activity["updatedAt"]),
        )

    def test_step_three_confirmation_requires_a_current_candidate_selection(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        step2 = self._save_output(activity_id, 2, 2)
        self._confirm(activity_id, 2, step2["version"])

        step3 = self.client.patch(
            f"/api/activities/{activity_id}/steps/3",
            json={"version": 2, "outputJson": STEP_THREE_OUTPUT},
        )
        self.assertEqual(step3.status_code, 200, step3.text)
        missing = self.client.post(
            f"/api/activities/{activity_id}/steps/3/confirm",
            json={"version": step3.json()["version"]},
        )
        self.assertEqual(missing.status_code, 409)
        self.assertEqual(missing.json()["detail"]["code"], "THEME_SELECTION_REQUIRED")

        null_selection = self.client.patch(
            f"/api/activities/{activity_id}/steps/3",
            json={"version": step3.json()["version"], "inputJson": {"selectedThemeId": None}},
        )
        self.assertEqual(null_selection.status_code, 422, null_selection.text)
        self.assertEqual(null_selection.json()["detail"]["code"], "INVALID_STEP_INPUT")

        invalid_selection = self.client.patch(
            f"/api/activities/{activity_id}/steps/3",
            json={"version": step3.json()["version"], "inputJson": {"selectedThemeId": "not-current"}},
        )
        self.assertEqual(invalid_selection.status_code, 200, invalid_selection.text)
        invalid_confirm = self.client.post(
            f"/api/activities/{activity_id}/steps/3/confirm",
            json={"version": invalid_selection.json()["version"]},
        )
        self.assertEqual(invalid_confirm.status_code, 409)
        self.assertEqual(invalid_confirm.json()["detail"]["code"], "INVALID_THEME_SELECTION")

        valid_selection = self.client.patch(
            f"/api/activities/{activity_id}/steps/3",
            json={
                "version": invalid_selection.json()["version"],
                "inputJson": {"selectedThemeId": "family-night"},
            },
        )
        confirmed = self._confirm(activity_id, 3, valid_selection.json()["version"])
        self.assertEqual(confirmed["status"], "confirmed")

    def test_annual_create_generate_confirm_and_refresh_use_annual_architecture(self) -> None:
        from backend.test_annual_planning import ANNUAL_INPUT, ANNUAL_OUTPUT
        created = self.client.post("/api/activities", json={"title": "年度总策划", "input": ANNUAL_INPUT})
        self.assertEqual(created.status_code, 201, created.text)
        activity_id = created.json()["id"]
        self.provider.output = {
            "standardizedBrief": {"objective": "统筹景区全年活动", **{key: value for key, value in ANNUAL_INPUT.items() if key != "idea"}},
            "missingFields": ["景区全年客流数据"],
        }
        generated_brief = self.client.post(f"/api/activities/{activity_id}/steps/1/generate", json={"version": 1, "model": "selected-model"})
        self.assertEqual(generated_brief.status_code, 200, generated_brief.text)
        self._confirm(activity_id, 1, generated_brief.json()["version"])
        step2 = self._save_output(activity_id, 2, 2)
        self._confirm(activity_id, 2, step2["version"])
        from backend.test_planning_stream import PlanningProvider, parse_events, generated_architecture
        provider = PlanningProvider()
        self.client.app.dependency_overrides[get_model_provider] = lambda: provider
        old_endpoint = self.client.post(f"/api/activities/{activity_id}/steps/3/generate", json={"version": 2, "model": "selected-model"})
        self.assertEqual(old_endpoint.json()["detail"]["code"], "USE_PLANNING_STREAM_ENDPOINT")
        generated = self.client.post(f"/api/activities/{activity_id}/steps/3/generate/stream", json={"version": 2, "model": "selected-model"})
        self.assertEqual(generated.status_code, 200, generated.text)
        events = parse_events(generated.text)
        self.assertEqual(events[-1][0], "planning_completed", generated.text)
        output = generated_architecture()
        self.assertEqual(events[-1][1]["step"]["outputJson"], output)
        self.assertEqual(len(provider.calls), 3)
        self._confirm(activity_id, 3, events[-1][1]["step"]["version"])
        refreshed = self.client.get(f"/api/activities/{activity_id}")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["steps"][2]["outputJson"], output)
        refreshed_steps = self.client.get(f"/api/activities/{activity_id}/steps")
        self.assertEqual(refreshed_steps.status_code, 200, refreshed_steps.text)
        self.assertEqual(refreshed_steps.json()[2]["status"], "confirmed")

    def test_manual_step_outputs_cannot_bypass_structured_schemas(self) -> None:
        activity_id = self._create_activity()["id"]
        invalid_step1 = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={"version": 1, "outputJson": {"arbitrary": "text"}},
        )
        self.assertEqual(invalid_step1.status_code, 422, invalid_step1.text)
        self.assertEqual(invalid_step1.json()["detail"]["code"], "INVALID_STEP_OUTPUT")
        unchanged = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
        self.assertEqual((unchanged["version"], unchanged["status"]), (1, "draft"))

        explicit_null_brief = dict(STEP_ONE_OUTPUT)
        explicit_null_brief["standardizedBrief"] = dict(STEP_ONE_OUTPUT["standardizedBrief"])
        explicit_null_brief["standardizedBrief"]["plannedStartAt"] = None
        rejected_null_brief = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={"version": 1, "outputJson": explicit_null_brief},
        )
        self.assertEqual(rejected_null_brief.status_code, 422, rejected_null_brief.text)

        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        public_source = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={
                "version": 2,
                "outputJson": {
                    "summary": "Unverified",
                    "findings": ["Claim"],
                    "sources": [
                        {
                            "sourceType": "public",
                            "label": "Invented",
                            "url": "https://example.test/invented",
                        }
                    ],
                    "risks": [],
                },
            },
        )
        self.assertEqual(public_source.status_code, 422, public_source.text)
        self.assertEqual(public_source.json()["detail"]["code"], "INVALID_STEP_OUTPUT")

        explicit_null = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={
                "version": 2,
                "outputJson": {
                    "summary": "Invalid null",
                    "findings": [],
                    "sources": [
                        {"sourceType": "actual", "label": "Brief", "reasoning": None}
                    ],
                    "risks": [],
                },
            },
        )
        self.assertEqual(explicit_null.status_code, 422, explicit_null.text)

        missing_reasoning = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={
                "version": 2,
                "outputJson": {
                    "summary": "Invalid calculation",
                    "findings": [],
                    "sources": [{"sourceType": "calculated", "label": "Attendance"}],
                    "risks": [],
                },
            },
        )
        self.assertEqual(missing_reasoning.status_code, 422, missing_reasoning.text)

    def test_corrupted_persisted_output_fails_response_validation(self) -> None:
        activity_id = self._create_activity()["id"]
        step = self.db.scalar(
            select(ActivityStep).where(
                ActivityStep.activity_id == activity_id,
                ActivityStep.step_no == 1,
            )
        )
        step.output_json = {"unexpected": "persisted corruption"}
        self.db.commit()

        response = self.client.get(f"/api/activities/{activity_id}/steps/1")
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"]["code"], "PERSISTED_STEP_OUTPUT_INVALID")

    def test_corrupted_persisted_output_cannot_be_confirmed_or_committed(self) -> None:
        activity_id = self._create_activity()["id"]
        step = self.db.scalar(
            select(ActivityStep).where(
                ActivityStep.activity_id == activity_id,
                ActivityStep.step_no == 1,
            )
        )
        step.output_json = {"unexpected": "persisted corruption"}
        step.status = "review"
        self.db.commit()

        response = self.client.post(
            f"/api/activities/{activity_id}/steps/1/confirm",
            json={"version": step.version},
        )
        self.assertEqual(response.status_code, 500, response.text)
        self.assertEqual(response.json()["detail"]["code"], "PERSISTED_STEP_OUTPUT_INVALID")

        self.db.expire_all()
        persisted = self.db.scalar(select(ActivityStep).where(ActivityStep.id == step.id))
        self.assertEqual((persisted.status, persisted.confirmed_by), ("review", None))
        self.assertIsNone(
            self.db.scalar(
                select(ActivityStepConfirmation).where(
                    ActivityStepConfirmation.activity_id == activity_id,
                    ActivityStepConfirmation.step_no == 1,
                )
            )
        )

    def test_domain_patch_rejects_supplied_null_input_and_output(self) -> None:
        activity_id = self._create_activity()["id"]
        activity = get_owned_activity(
            activity_id=activity_id,
            owner_id=str(self.current_user.user_id),
            session=self.db,
            lock=True,
        )
        step = find_step(activity=activity, step_no=1)

        for kwargs, expected_code in (
            ({"input_json": None, "input_supplied": True}, "INVALID_STEP_INPUT"),
            ({"output_json": None, "output_supplied": True}, "INVALID_STEP_OUTPUT"),
        ):
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(StepDomainError) as raised:
                    patch_step(
                        activity=activity,
                        step=step,
                        expected_version=step.version,
                        actor=str(self.current_user.user_id),
                        session=self.db,
                        **kwargs,
                    )
                self.assertEqual(raised.exception.code, expected_code)
        self.db.rollback()

    def test_generation_completion_requires_complete_metadata(self) -> None:
        activity_id = self._create_activity()["id"]
        activity = get_owned_activity(
            activity_id=activity_id,
            owner_id=str(self.current_user.user_id),
            session=self.db,
            lock=True,
        )
        step = find_step(activity=activity, step_no=1)
        for invalid_model in ("", " model", "model ", "m" * 201):
            with self.subTest(invalid_model=invalid_model):
                with self.assertRaises(StepDomainError) as raised:
                    start_generation(
                        activity=activity,
                        step=step,
                        expected_version=step.version,
                        model=invalid_model,
                        actor=str(self.current_user.user_id),
                        session=self.db,
                    )
                self.assertEqual(raised.exception.code, "INVALID_GENERATION_MODEL")
        generation_id, _ = start_generation(
            activity=activity,
            step=step,
            expected_version=step.version,
            model="selected-model",
            actor=str(self.current_user.user_id),
            session=self.db,
        )

        invalid_cases = (
            {"model": " ", "request_id": "request", "duration_ms": 1, "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
            {"model": "model", "request_id": "request", "duration_ms": 1, "usage": {}},
        )
        for metadata in invalid_cases:
            with self.subTest(metadata=metadata):
                with self.assertRaises(StepDomainError) as raised:
                    complete_generation(
                        activity=activity,
                        step=step,
                        generation_id=generation_id,
                        actor=str(self.current_user.user_id),
                        output_json=STEP_ONE_OUTPUT,
                        session=self.db,
                        **metadata,
                    )
                self.assertEqual(raised.exception.code, "INVALID_GENERATION_METADATA")
        self.db.rollback()

    def test_steps_five_to_nine_use_the_canonical_generation_contract(self) -> None:
        activity_id = self._create_activity()["id"]
        for step_no in range(1, 5):
            current = self.client.get(f"/api/activities/{activity_id}/steps/{step_no}").json()
            saved = self._save_output(activity_id, step_no, current["version"])
            self._confirm(activity_id, step_no, saved["version"])

        for step_no in range(5, 10):
            current = self.client.get(f"/api/activities/{activity_id}/steps/{step_no}").json()
            invalid = self.client.patch(
                f"/api/activities/{activity_id}/steps/{step_no}",
                json={"version": current["version"], "outputJson": {"draft": "unsupported"}},
            )
            self.assertEqual(invalid.status_code, 422, invalid.text)
            self.assertEqual(invalid.json()["detail"]["code"], "INVALID_STEP_OUTPUT")

            self.provider.output = deepcopy(valid_step_output(step_no))
            if step_no == 5:
                self.provider.output.pop("totalAmount")
                for item in self.provider.output["items"]:
                    item.pop("subtotal")
            generated = self.client.post(
                f"/api/activities/{activity_id}/steps/{step_no}/generate",
                json={"version": current["version"], "model": "selected-model"},
            )
            self.assertEqual(generated.status_code, 200, generated.text)
            self.assertEqual(generated.json()["outputJson"], valid_step_output(step_no))
            confirmed = self._confirm(activity_id, step_no, generated.json()["version"])
            if step_no == 7:
                tasks = self.db.scalars(
                    select(ExecutionTask)
                    .where(ExecutionTask.activity_id == activity_id)
                    .order_by(ExecutionTask.source_task_index)
                ).all()
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0].title, STEP_SEVEN_OUTPUT["tasks"][0]["title"])
                self.assertEqual(tasks[0].status, "pending_confirmation")
                self.assertEqual(tasks[0].source_step_version, confirmed["version"])
                self.assertEqual(tasks[0].source_task_index, 0)

                duplicate = self.client.post(
                    f"/api/activities/{activity_id}/steps/7/confirm",
                    json={"version": confirmed["version"]},
                )
                self.assertEqual(duplicate.status_code, 409, duplicate.text)
                self.assertEqual(
                    self.db.scalar(
                        select(func.count())
                        .select_from(ExecutionTask)
                        .where(ExecutionTask.activity_id == activity_id)
                    ),
                    1,
                )

        activity = self.client.get(f"/api/activities/{activity_id}").json()
        self.assertEqual(activity["status"], "completed")
        self.assertEqual(activity["currentStep"], 9)

    def test_step_nine_analysis_generation_preserves_saved_metrics(self) -> None:
        activity_id = self._create_activity()["id"]
        for step_no in range(1, 9):
            current = self.client.get(f"/api/activities/{activity_id}/steps/{step_no}").json()
            saved = self._save_output(activity_id, step_no, current["version"])
            self._confirm(activity_id, step_no, saved["version"])

        current = self.client.get(f"/api/activities/{activity_id}/steps/9").json()
        saved_review = deepcopy(STEP_NINE_OUTPUT)
        saved_review["actualMetrics"] = [
            {
                "metric": "attendance",
                "value": 2764.0,
                "unit": "visitors",
                "sourceType": "actual",
                "basis": "Gate counter export",
            }
        ]
        saved_review["missingActualMetrics"] = ["revenue", "satisfaction"]
        saved = self._save_output(activity_id, 9, current["version"], saved_review)

        self.provider.output = {
            "conclusions": ["Attendance reached 92.1% of the forecast"],
            "improvements": ["Rebalance entry staffing for the next event"],
        }
        generated = self.client.post(
            f"/api/activities/{activity_id}/steps/9/generate",
            json={"version": saved["version"], "model": "selected-model"},
        )

        self.assertEqual(generated.status_code, 200, generated.text)
        generated_output = generated.json()["outputJson"]
        self.assertEqual(generated_output["forecastMetrics"], saved_review["forecastMetrics"])
        self.assertEqual(generated_output["actualMetrics"], saved_review["actualMetrics"])
        self.assertEqual(
            generated_output["missingActualMetrics"],
            saved_review["missingActualMetrics"],
        )
        self.assertEqual(generated_output["conclusions"], self.provider.output["conclusions"])
        self.assertEqual(generated_output["improvements"], self.provider.output["improvements"])

        self.provider.output = {
            "actualMetrics": saved_review["actualMetrics"],
            "conclusions": ["Attempted metric rewrite"],
            "improvements": ["Should be rejected"],
        }
        rejected = self.client.post(
            f"/api/activities/{activity_id}/steps/9/generate",
            json={"version": generated.json()["version"], "model": "selected-model"},
        )
        self.assertEqual(rejected.status_code, 502, rejected.text)
        self.assertEqual(rejected.json()["detail"]["code"], "INVALID_MODEL_RESPONSE")
        failed_step = self.client.get(f"/api/activities/{activity_id}/steps/9").json()
        self.assertEqual(failed_step["outputJson"], generated_output)

    def test_step_three_and_four_generation_use_public_output_contracts(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        step2 = self._save_output(activity_id, 2, 2)
        self._confirm(activity_id, 2, step2["version"])

        selected = self.client.patch(
            f"/api/activities/{activity_id}/steps/3",
            json={"version": 2, "inputJson": {"selectedThemeId": "family-night"}},
        )
        self.assertEqual(selected.status_code, 200, selected.text)
        self.provider.output = {
            "candidates": [
                {
                    "id": "family-night",
                    "name": "Family Riverside Night",
                    "storyline": "A family journey following the river lights",
                    "visualDirection": "Warm lanterns and clear wayfinding",
                    "highlights": ["Family missions", "Night market"],
                },
                {
                    "id": "river-memory",
                    "name": "River Memory",
                    "storyline": "Local stories unfold along the waterfront",
                    "visualDirection": "Historic textures with modern lighting",
                    "highlights": ["Story stations", "Local performances"],
                },
            ]
        }
        step3 = self.client.post(
            f"/api/activities/{activity_id}/steps/3/generate",
            json={"version": selected.json()["version"], "model": "selected-model"},
        )
        self.assertEqual(step3.status_code, 200, step3.text)
        self.assertEqual(len(step3.json()["outputJson"]["candidates"]), 2)
        self.assertIn("selectedThemeId", self.provider.calls[-1][0][1].content)
        self._confirm(activity_id, 3, step3.json()["version"])

        step4_input = self.client.patch(
            f"/api/activities/{activity_id}/steps/4",
            json={"version": 2, "inputJson": {"unsupported": True}},
        )
        self.assertEqual(step4_input.status_code, 422, step4_input.text)
        self.assertEqual(step4_input.json()["detail"]["code"], "INVALID_STEP_INPUT")

        self.provider.output = {
            "schedule": [
                {"time": "17:30", "title": "Opening", "description": "Open all visitor zones"}
            ],
            "zones": [
                {
                    "name": "Family interaction zone",
                    "purpose": "Host family missions",
                    "activities": ["Stamp trail"],
                    "requirements": ["Queue barriers"],
                }
            ],
            "personnel": [
                {
                    "role": "Zone coordinator",
                    "count": 2,
                    "responsibilities": ["Visitor flow", "Incident reporting"],
                }
            ],
            "safetyRequirements": ["Maintain emergency access at all times"],
        }
        step4 = self.client.post(
            f"/api/activities/{activity_id}/steps/4/generate",
            json={"version": 2, "model": "selected-model"},
        )
        self.assertEqual(step4.status_code, 200, step4.text)
        self.assertEqual(step4.json()["outputJson"]["zones"][0]["name"], "Family interaction zone")
        self.assertIn("safetyRequirements", step4.json()["outputJson"])
        self.assertIn('"selectedThemeId":"family-night"', self.provider.calls[-1][0][1].content)

    def test_paused_and_archived_activities_reject_step_writes(self) -> None:
        activity_id = self._create_activity()["id"]
        self.client.post(f"/api/activities/{activity_id}/pause")
        paused = self.client.patch(
            f"/api/activities/{activity_id}/steps/1",
            json={"version": 1, "outputJson": {"draft": "blocked"}},
        )
        self.assertEqual(paused.status_code, 409)
        self.assertEqual(paused.json()["detail"]["code"], "ACTIVITY_NOT_WRITABLE")

        self.client.patch(f"/api/activities/{activity_id}", json={"status": "running"})
        self.client.post(f"/api/activities/{activity_id}/archive")
        archived = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": 1, "model": "selected-model"},
        )
        self.assertEqual(archived.status_code, 409)
        self.assertEqual(archived.json()["detail"]["code"], "ACTIVITY_NOT_WRITABLE")

    def test_upstream_change_supersedes_an_in_flight_downstream_generation(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        owner_id = str(self.current_user.user_id)

        activity = get_owned_activity(
            activity_id=activity_id,
            owner_id=owner_id,
            session=self.db,
            lock=True,
        )
        step2 = find_step(activity=activity, step_no=2)
        generation_id, _ = start_generation(
            activity=activity,
            step=step2,
            expected_version=step2.version,
            model="selected-model",
            actor=owner_id,
            session=self.db,
        )
        self.db.commit()

        activity = get_owned_activity(
            activity_id=activity_id,
            owner_id=owner_id,
            session=self.db,
            lock=True,
        )
        step1_model = find_step(activity=activity, step_no=1)
        reopen_step(
            activity=activity,
            step=step1_model,
            expected_version=step1_model.version,
            actor=owner_id,
            comment="Update the brief",
            session=self.db,
        )
        self.db.commit()

        run = self.db.scalar(select(ModelRun).where(ModelRun.generation_id == generation_id))
        self.assertEqual((run.status, run.error_code), ("failed", "GENERATION_SUPERSEDED"))
        step2_model = self.db.scalar(
            select(ActivityStep).where(
                ActivityStep.activity_id == activity_id,
                ActivityStep.step_no == 2,
            )
        )
        self.assertEqual(step2_model.status, "needs_review")

        with self.assertRaises(StepDomainError) as stale:
            complete_generation(
                activity=activity,
                step=step2_model,
                generation_id=generation_id,
                actor=owner_id,
                output_json={"summary": "late"},
                model="test-model",
                request_id=None,
                duration_ms=1,
                usage={},
                session=self.db,
            )
        self.assertEqual(stale.exception.code, "GENERATION_STALE")
        self.db.rollback()

    def test_provider_configuration_failure_is_generic_persisted_and_retryable(self) -> None:
        activity_id = self._create_activity()["id"]
        self.provider.error = CcodeConfigurationError()
        failed = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": 1, "model": "selected-model"},
        )
        self.assertEqual(failed.status_code, 503, failed.text)
        self.assertEqual(failed.json()["detail"]["code"], "PROVIDER_NOT_CONFIGURED")
        self.assertNotIn("CCODE", json.dumps(failed.json()))

        step = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
        self.assertEqual(step["status"], "failed")
        self.assertEqual(step["version"], 2)
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id))
        self.assertEqual(run.error_code, "CCODE_NOT_CONFIGURED")
        self.assertEqual(run.model, "selected-model")
        self.assertIsNone(run.provider_request_id)

        self.provider.error = None
        retried = self.client.post(
            f"/api/activities/{activity_id}/steps/1/generate",
            json={"version": 2, "model": "selected-model"},
        )
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["status"], "review")
        self.assertEqual(retried.json()["version"], 3)

    def test_generation_route_rejects_internal_identifier_in_user_visible_text(self) -> None:
        activity_id = self._create_activity()["id"]
        self.provider.output = deepcopy(STEP_ONE_OUTPUT)
        self.provider.output["standardizedBrief"]["objective"] = (
            "根据 confirmedResearchEvidence.sources 形成活动目标"
        )

        with self.assertLogs("backend.activity_api", level="WARNING") as captured:
            response = self.client.post(
                f"/api/activities/{activity_id}/steps/1/generate",
                json={"version": 1, "model": "selected-model"},
            )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["detail"]["code"], "INVALID_MODEL_RESPONSE")
        logs = "\n".join(captured.output)
        self.assertIn('"stage": "user_visible_identifier"', logs)
        self.assertIn('"path": ["standardizedBrief", "objective"]', logs)
        self.assertNotIn(self.provider.output["standardizedBrief"]["objective"], logs)
        self.assertNotIn("confirmedResearchEvidence", logs)
        failed_step = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
        self.assertEqual(failed_step["status"], "failed")
        self.assertEqual(failed_step["outputJson"], {})

    def test_provider_failure_after_upstream_change_returns_generation_stale(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        owner_id = str(self.current_user.user_id)

        def supersede_generation(_metadata) -> None:
            activity = get_owned_activity(
                activity_id=activity_id,
                owner_id=owner_id,
                session=self.db,
                lock=True,
            )
            first_step = find_step(activity=activity, step_no=1)
            reopen_step(
                activity=activity,
                step=first_step,
                expected_version=first_step.version,
                actor=owner_id,
                comment="Change the brief while research is generating",
                session=self.db,
            )
            self.db.commit()

        self.provider.on_generate = supersede_generation
        self.provider.error = CcodeConfigurationError()
        response = self.client.post(
            f"/api/activities/{activity_id}/steps/2/generate",
            json={"version": 2, "model": "selected-model"},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["detail"]["code"], "GENERATION_STALE")
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id))
        self.assertEqual((run.status, run.error_code), ("failed", "GENERATION_SUPERSEDED"))

    def test_invalid_or_public_research_output_fails_without_overwriting_output(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        search_choice = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": 2, "inputJson": {"useWebSearch": False}},
        )
        self.assertEqual(search_choice.status_code, 200, search_choice.text)
        self.provider.output = {
            "summary": "Claimed web result",
            "findings": ["Unverified trend"],
            "sources": [
                {
                    "sourceType": "public",
                    "label": "Invented source",
                    "url": "https://example.test/invented",
                }
            ],
            "risks": [],
        }
        invalid = self.client.post(
            f"/api/activities/{activity_id}/steps/2/generate",
            json={"version": search_choice.json()["version"], "model": "selected-model"},
        )
        self.assertEqual(invalid.status_code, 502, invalid.text)
        self.assertEqual(invalid.json()["detail"]["code"], "INVALID_MODEL_RESPONSE")
        failed_step = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual(failed_step["status"], "failed")
        self.assertEqual(failed_step["outputJson"], {})

        self.provider.output = {
            "summary": "Only supplied facts were assessed",
            "findings": ["The location is Riverside park"],
            "sources": [
                {"sourceType": "actual", "label": "User activity brief"},
                {
                    "sourceType": "missing",
                    "label": "Public trend data not retrieved",
                    "reasoning": "Web search is not implemented in this workflow",
                },
            ],
            "risks": ["Public trend evidence is unavailable"],
        }
        retried = self.client.post(
            f"/api/activities/{activity_id}/steps/2/generate",
            json={"version": failed_step["version"], "model": "selected-model"},
        )
        self.assertEqual(retried.status_code, 200, retried.text)
        source_types = {source["sourceType"] for source in retried.json()["outputJson"]["sources"]}
        self.assertEqual(source_types, {"actual", "missing"})
        persisted_sources = self.db.scalars(
            select(SourceReference).where(
                SourceReference.activity_id == activity_id,
                SourceReference.step_no == 2,
            )
        ).all()
        self.assertEqual({source.source_type for source in persisted_sources}, {"actual", "missing"})

    def test_research_generation_preserves_all_persisted_public_evidence(self) -> None:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        search_choice = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": 2, "inputJson": {"useWebSearch": True}},
        )
        self.assertEqual(search_choice.status_code, 200, search_choice.text)

        captured_at = datetime(2026, 9, 24, 10, tzinfo=timezone.utc)
        self.db.add_all(
            [
                SourceReference(
                    activity_id=activity_id,
                    step_no=2,
                    source_type="public",
                    label="Search result A",
                    url="https://example.com/a",
                    captured_at=captured_at,
                    excerpt="Evidence A",
                    published_at="2026-09-20",
                    site_name="Example",
                    authority_level="high",
                    rank=0,
                    provider_request_id="request-a",
                    scope="holiday",
                ),
                SourceReference(
                    activity_id=activity_id,
                    step_no=2,
                    source_type="public",
                    label="Search result B",
                    url="https://example.com/b",
                    captured_at=captured_at,
                    excerpt="Evidence B",
                    published_at="2026-09-19",
                    site_name="Example",
                    authority_level="normal",
                    rank=1,
                    provider_request_id="request-b",
                    scope="public_trend",
                ),
            ]
        )
        self.db.commit()

        self.provider.output = {
            "summary": "Evidence A supports the decision",
            "findings": ["使用节假日证据进行判断"],
            "sources": [
                {
                    "sourceType": "public",
                    "label": "Search result A",
                    "url": "https://example.com/a",
                    "capturedAt": "2026-09-24T10:00:00+00:00",
                    "publishedAt": "2026-09-20",
                    "siteName": "Example",
                    "authorityLevel": "high",
                    "rank": 0,
                    "providerRequestId": "request-a",
                    "scope": "holiday",
                    "excerpt": "Evidence A",
                }
            ],
            "risks": [],
        }
        generated = generate_research_test(self.client, activity_id, search_choice.json()["version"])
        self.assertEqual(generated.status_code, 200, generated.text)

        persisted_sources = self.db.scalars(
            select(SourceReference)
            .where(SourceReference.activity_id == activity_id, SourceReference.step_no == 2)
            .order_by(SourceReference.rank)
        ).all()
        self.assertEqual([source.label for source in persisted_sources], ["Search result A", "Search result B"])
        self.assertEqual([source.provider_request_id for source in persisted_sources], ["request-a", "request-b"])

    def _search_research(self) -> tuple[str, dict]:
        activity_id = self._create_activity()["id"]
        step1 = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, step1["version"])
        enabled = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": 2, "inputJson": {"useWebSearch": True}},
        )
        response = self.client.post(
            f"/api/activities/{activity_id}/research",
            json={"version": enabled.json()["version"], "useWebSearch": True,
                  "query": "Riverside Festival", "queryScope": ["weather", "holiday"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return activity_id, self.client.get(f"/api/activities/{activity_id}/steps/2").json()

    def _summarized_search_output(self) -> dict:
        return {
            "summary": "依据公开资料形成的活动研判",
            "findings": ["活动应为户外区域准备天气应对方案"],
            "sources": [{"sourceType": "public", "label": "天气来源",
                         "url": "https://example.com/weather",
                         "capturedAt": "2026-09-24T00:00:00+00:00", "excerpt": "原" * 200,
                         "publishedAt": "2026-09-20", "siteName": "示例站点", "authorityLevel": "high",
                         "rank": 0, "providerRequestId": "request-weather", "scope": "weather"}],
            "risks": ["公开天气资料不能代替临近活动的预报"],
        }

    def test_search_and_failed_summary_cannot_be_confirmed_or_bypassed_by_save(self) -> None:
        activity_id, step = self._search_research()
        self.assertEqual((step["status"], step["outputJson"]), ("draft", {}))
        confirmed = self.client.post(
            f"/api/activities/{activity_id}/steps/2/confirm", json={"version": step["version"]},
        )
        self.assertEqual(confirmed.status_code, 409, confirmed.text)
        later = self.client.post(
            f"/api/activities/{activity_id}/steps/3/generate",
            json={"version": 1, "model": "selected-model"},
        )
        self.assertEqual(later.status_code, 409, later.text)
        self.provider.error = CcodeTimeoutError()
        failed = generate_research_test(self.client, activity_id, step["version"])
        self.assertEqual(failed.status_code, 504, failed.text)
        step = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual((step["status"], step["outputJson"]), ("failed", {}))
        saved = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": step["version"], "inputJson": {"useWebSearch": True}},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        bypass = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": saved.json()["version"], "outputJson": self._summarized_search_output()},
        )
        self.assertEqual(bypass.status_code, 409, bypass.text)
        self.assertEqual(bypass.json()["detail"]["code"], "RESEARCH_GENERATION_REQUIRED")
        self.provider.error = None
        self.provider.output = self._summarized_search_output()
        retried = generate_research_test(self.client, activity_id, saved.json()["version"])
        self.assertEqual(retried.status_code, 200, retried.text)

    def test_invalid_public_citation_fails_without_losing_raw_evidence_and_can_retry(self) -> None:
        for field, invalid_value, code in (
            ("label", "改写的来源名称", "PUBLIC_CITATION_METADATA_MISMATCH"),
            ("excerpt", "伪造的证据摘录", "PUBLIC_CITATION_EXCERPT_MISMATCH"),
            ("excerpt", "Invented warm-weather evidence", "PUBLIC_CITATION_EXCERPT_MISMATCH"),
        ):
            with self.subTest(code=code):
                self._assert_invalid_public_citation_can_retry(field, invalid_value, code)

    def _assert_invalid_public_citation_can_retry(self, field: str, invalid_value: str, code: str) -> None:
        activity_id, step = self._search_research()
        search_calls = self.search_provider.calls
        self.provider.output = self._summarized_search_output()
        self.provider.output["sources"][0][field] = invalid_value
        response = generate_research_test(self.client, activity_id, step["version"])
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(response.json()["detail"]["code"], code)
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == activity_id, ModelRun.step_no == 2))
        self.assertEqual((run.status, run.error_code), ("failed", code))
        failed = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual((failed["status"], failed["outputJson"]), ("failed", {}))
        sources = self.db.scalars(select(SourceReference).where(
            SourceReference.activity_id == activity_id, SourceReference.step_no == 2,
        ).order_by(SourceReference.rank)).all()
        self.assertEqual([len(source.excerpt) for source in sources], [3260, 3973])
        self.provider.output = self._summarized_search_output()
        retried = generate_research_test(self.client, activity_id, failed["version"])
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["status"], "review")
        self.assertEqual(self.search_provider.calls, search_calls)
        self._confirm(activity_id, 2, retried.json()["version"])

    def test_summary_edits_keep_raw_evidence_and_later_prompt_receives_only_summary(self) -> None:
        activity_id, step = self._search_research()
        self.provider.output = self._summarized_search_output()
        generated = generate_research_test(self.client, activity_id, step["version"])
        self.assertEqual(generated.status_code, 200, generated.text)
        model_context = json.loads(self.provider.calls[-1][0][1].content.split("\n", 1)[1])
        self.assertEqual([len(item["excerpt"]) for item in model_context["publicSearchEvidence"]], [3973])
        first_context = json.loads(self.provider.calls[-2][0][1].content.split("\n", 1)[1])
        self.assertEqual([len(item["excerpt"]) for item in first_context["publicSearchEvidence"]], [3260])
        edited = deepcopy(generated.json()["outputJson"])
        edited["findings"] = ["人工复核后保留天气应对方案"]
        saved = self.client.patch(
            f"/api/activities/{activity_id}/steps/2",
            json={"version": generated.json()["version"], "outputJson": edited},
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        sources = self.db.scalars(select(SourceReference).where(
            SourceReference.activity_id == activity_id, SourceReference.step_no == 2,
        ).order_by(SourceReference.rank)).all()
        self.assertEqual([len(source.excerpt) for source in sources], [3260, 3973])
        self._confirm(activity_id, 2, saved.json()["version"])
        self.provider.output = STEP_THREE_OUTPUT
        later = self.client.post(
            f"/api/activities/{activity_id}/steps/3/generate",
            json={"version": 2, "model": "selected-model"},
        )
        self.assertEqual(later.status_code, 200, later.text)
        context = json.loads(self.provider.calls[-1][0][1].content.split("\n", 1)[1])
        self.assertEqual(context["confirmedResearchEvidence"], edited)
        self.assertNotIn("publicSearchEvidence", context)
        self.assertNotIn("publicSearchSelection", context)
        self.assertNotIn("原" * 3260, self.provider.calls[-1][0][1].content)

    def test_search_reset_and_uncompleted_persisted_confirmation_block_later_steps(self) -> None:
        activity_id, step = self._search_research()
        self.provider.output = self._summarized_search_output()
        generated = generate_research_test(self.client, activity_id, step["version"])
        self.assertEqual(generated.status_code, 200, generated.text)
        reset = self.client.post(
            f"/api/activities/{activity_id}/research",
            json={"version": generated.json()["version"], "useWebSearch": True,
                  "query": "Fresh search", "queryScope": ["weather", "holiday"]},
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        research = self.db.scalar(select(ActivityStep).where(
            ActivityStep.activity_id == activity_id, ActivityStep.step_no == 2,
        ))
        research.output_json = self._summarized_search_output()
        research.status = "review"
        self.db.commit()
        confirm = self.client.post(
            f"/api/activities/{activity_id}/steps/2/confirm", json={"version": research.version},
        )
        self.assertEqual(confirm.status_code, 409, confirm.text)
        self.assertEqual(confirm.json()["detail"]["code"], "RESEARCH_GENERATION_REQUIRED")
        # Reproduce an already-confirmed search placeholder without relying on its wording.
        research.status = "confirmed"
        next_step = self.db.scalar(select(ActivityStep).where(
            ActivityStep.activity_id == activity_id, ActivityStep.step_no == 3,
        ))
        next_step.status = "draft"
        self.db.commit()
        calls_before = len(self.provider.calls)
        later = self.client.post(
            f"/api/activities/{activity_id}/steps/3/generate",
            json={"version": next_step.version, "model": "selected-model"},
        )
        self.assertEqual(later.status_code, 409, later.text)
        self.assertEqual(later.json()["detail"]["code"], "RESEARCH_GENERATION_REQUIRED")
        self.assertEqual(len(self.provider.calls), calls_before)


if __name__ == "__main__":
    unittest.main()
