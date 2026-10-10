from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from pydantic import ValidationError

from backend.activities import ActivityBriefInputData, create_activity
from backend.activity_api import ActivityBriefInputDTO
from backend.activity_steps import (
    StepDomainError, build_generation_messages, confirm_step, patch_step,
    validate_generated_output, validate_step_output,
)
from backend.test_activity_steps import STEP_TWO_OUTPUT, STEP_THREE_OUTPUT
from backend.planning_generation import planning_unit_messages, validate_planning_unit_output


ANNUAL_INPUT = {
    "idea": "统筹景区全年活动",
    "planningMode": "annual",
    "annualPeriod": "2027年",
    "annualGoals": "四季引流和提升游客复游率",
    "plannedEventCount": 2,
}
ANNUAL_OUTPUT = {
    "annualNarrative": "以四季生态体验连接景区全年品牌叙事",
    "eventBriefs": [
        {"id": "spring", "name": "春季花事", "timeWindow": "三月至四月", "targetAudience": "家庭游客",
         "positioning": "春季客流增长", "themeDirection": "花海探索", "scale": "中型",
         "sharedAssets": ["基础导视"], "highlights": ["花径任务"]},
        {"id": "summer", "name": "暑期研学", "timeWindow": "七月至八月", "targetAudience": "亲子家庭",
         "positioning": "暑期复游与研学", "themeDirection": "生态课堂", "scale": "中型",
         "sharedAssets": ["基础导视"], "highlights": ["自然观察"]},
    ],
}


class AnnualPlanningContractTests(unittest.TestCase):
    def _annual_activity(self):
        session = MagicMock()
        activity = create_activity(title="年度总策划", idea=ANNUAL_INPUT["idea"], created_by="planner", input_data=ANNUAL_INPUT, session=session)
        activity.status = "running"
        activity.steps[0].status = "confirmed"
        activity.steps[0].output_json = {"standardizedBrief": {"objective": ANNUAL_INPUT["idea"], **{key: value for key, value in ANNUAL_INPUT.items() if key != "idea"}}, "missingFields": []}
        activity.steps[1].status = "confirmed"
        activity.steps[1].output_json = deepcopy(STEP_TWO_OUTPUT)
        activity.steps[2].status = "review"
        activity.steps[2].output_json = deepcopy(ANNUAL_OUTPUT)
        session.scalars.return_value.all.return_value = [SimpleNamespace(
            input_json={"useWebSearch": False}, output_json=STEP_TWO_OUTPUT, change_type="generated"
        )]
        return activity, session

    def test_brief_models_accept_only_complete_mode_specific_fields(self):
        invalid_inputs = [
            {**ANNUAL_INPUT, "planningMode": "unknown"},
            {key: value for key, value in ANNUAL_INPUT.items() if key != "annualGoals"},
            {**ANNUAL_INPUT, "annualPeriod": " "},
            {**ANNUAL_INPUT, "plannedEventCount": True},
            {**ANNUAL_INPUT, "plannedEventCount": 13},
            {**ANNUAL_INPUT, "planningMode": "single"},
            {**ANNUAL_INPUT, "extraAnnualField": "unsupported"},
        ]
        for model in (ActivityBriefInputData, ActivityBriefInputDTO):
            with self.subTest(model=model.__name__):
                parsed = model.model_validate(ANNUAL_INPUT).model_dump(by_alias=True, exclude_none=True, mode="json")
                self.assertEqual(parsed, ANNUAL_INPUT)
                self.assertEqual(model.model_validate({"idea": "单场策划"}).planning_mode, "single")
            for invalid in invalid_inputs:
                with self.subTest(model=model.__name__, invalid=invalid), self.assertRaises(ValidationError):
                    model.model_validate(invalid)

    def test_annual_and_single_outputs_are_distinct_strict_contracts(self):
        self.assertEqual(validate_generated_output(3, json.dumps(ANNUAL_OUTPUT, ensure_ascii=False), search_enabled=False, planning_mode="annual"), ANNUAL_OUTPUT)
        invalid_outputs = [STEP_THREE_OUTPUT, {**ANNUAL_OUTPUT, "candidates": []}, {**ANNUAL_OUTPUT, "eventBriefs": ANNUAL_OUTPUT["eventBriefs"][:1]}]
        duplicate = deepcopy(ANNUAL_OUTPUT)
        duplicate["eventBriefs"][1]["id"] = "spring"
        invalid_outputs.append(duplicate)
        nested_unknown = deepcopy(ANNUAL_OUTPUT)
        nested_unknown["eventBriefs"][0]["legacyTheme"] = "unsupported"
        invalid_outputs.append(nested_unknown)
        for invalid in invalid_outputs:
            with self.subTest(invalid=invalid), self.assertRaises(StepDomainError):
                validate_step_output(3, invalid, search_enabled=False, planning_mode="annual", error_code="INVALID_STEP_OUTPUT")
        with self.assertRaises(StepDomainError):
            validate_step_output(3, ANNUAL_OUTPUT, search_enabled=False, planning_mode="single", error_code="INVALID_STEP_OUTPUT")

    def test_annual_architecture_can_confirm_without_selecting_a_single_event(self):
        activity, session = self._annual_activity()
        step = activity.steps[2]
        confirmed = confirm_step(activity=activity, step=step, expected_version=step.version, actor="planner", comment=None, session=session)
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(activity.steps[3].status, "draft")

    def test_annual_selection_requires_a_current_event_and_rejects_single_theme_input(self):
        activity, session = self._annual_activity()
        step = activity.steps[2]
        for invalid in ({"selectedThemeId": "spring"}, {"selectedPlanItemId": None}, {"selectedPlanItemId": " "}):
            with self.subTest(invalid=invalid), self.assertRaises(StepDomainError):
                patch_step(activity=activity, step=step, expected_version=step.version, actor="planner", session=session, input_json=invalid, input_supplied=True)
        step.input_json = {"selectedPlanItemId": "not-current"}
        with self.assertRaises(StepDomainError) as error:
            confirm_step(activity=activity, step=step, expected_version=step.version, actor="planner", comment=None, session=session)
        self.assertEqual(error.exception.code, "INVALID_PLAN_ITEM_SELECTION")
        step.input_json = {"selectedPlanItemId": "spring"}
        self.assertEqual(confirm_step(activity=activity, step=step, expected_version=step.version, actor="planner", comment=None, session=session).status, "confirmed")

    def test_generation_uses_annual_schema_and_current_event_boundary(self):
        activity, _session = self._annual_activity()
        step = activity.steps[2]
        context = json.loads(build_generation_messages(activity, step)[1]["content"].split("\n", 1)[1])
        self.assertEqual(set(context["requiredJsonSchema"]["properties"]), {"annualNarrative", "eventSeeds"})
        self.assertIn("完整年度架构的最终展示文字", build_generation_messages(activity, step)[1]["content"])
        self.assertEqual(context["confirmedPreviousSteps"][0]["output"], activity.steps[0].output_json)
        architecture = {"annualNarrative": ANNUAL_OUTPUT["annualNarrative"], "eventSeeds": [{key: value for key, value in event.items() if key not in {"sharedAssets", "highlights"}} for event in ANNUAL_OUTPUT["eventBriefs"]]}
        context = json.loads(planning_unit_messages(activity, step, "spring", architecture_draft=architecture)[1]["content"].split("\n", 1)[1])
        self.assertEqual(set(context["requiredJsonSchema"]["properties"]), {"sharedAssets", "highlights"})
        self.assertEqual(context["currentEventSeed"], architecture["eventSeeds"][0])
        self.assertNotIn("eventSeeds", context)
        details = {key: ANNUAL_OUTPUT["eventBriefs"][0][key] for key in ("sharedAssets", "highlights")}
        self.assertEqual(validate_planning_unit_output(activity, step, "spring", json.dumps(details), architecture_draft=architecture), ANNUAL_OUTPUT["eventBriefs"][0])
        with self.assertRaises(StepDomainError):
            validate_planning_unit_output(activity, step, "spring", json.dumps({**details, "name": "模型重写名称"}), architecture_draft=architecture)
        step.status = "confirmed"
        step.input_json = {"selectedPlanItemId": "spring"}
        context = json.loads(planning_unit_messages(activity, activity.steps[3], "spring", current_annual_plan={"constraints": "年度统筹边界"})[1]["content"].split("\n", 1)[1])
        self.assertEqual(context["currentEventBrief"], ANNUAL_OUTPUT["eventBriefs"][0])
        self.assertNotIn("eventBriefs", context)


if __name__ == "__main__":
    unittest.main()
