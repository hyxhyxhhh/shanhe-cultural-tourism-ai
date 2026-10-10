"""Structured output contracts for activity steps five through nine."""

from copy import deepcopy
import json
import unittest

from backend.activity_steps import StepDomainError, validate_generated_output, validate_step_output
from backend.test_activity_steps import valid_step_output


class LaterStepOutputContractTests(unittest.TestCase):
    def test_each_later_step_accepts_its_canonical_shape(self) -> None:
        for step_no in range(5, 10):
            with self.subTest(step_no=step_no):
                self.assertEqual(
                    validate_step_output(
                        step_no,
                        valid_step_output(step_no),
                        search_enabled=False,
                        error_code="INVALID_STEP_OUTPUT",
                    ),
                    valid_step_output(step_no),
                )

    def test_unknown_fields_and_nested_nulls_are_rejected(self) -> None:
        unknown = deepcopy(valid_step_output(6))
        unknown["unexpected"] = True
        nested_null = deepcopy(valid_step_output(7))
        nested_null["tasks"][0]["owner"] = None
        for step_no, output in ((6, unknown), (7, nested_null)):
            with self.subTest(step_no=step_no), self.assertRaises(StepDomainError):
                validate_step_output(
                    step_no,
                    output,
                    search_enabled=False,
                    error_code="INVALID_STEP_OUTPUT",
                )

    def test_budget_arithmetic_and_review_evidence_are_enforced(self) -> None:
        bad_budget = deepcopy(valid_step_output(5))
        bad_budget["totalAmount"] = 9999.0
        bad_review = deepcopy(valid_step_output(9))
        bad_review["missingActualMetrics"] = []
        for step_no, output in ((5, bad_budget), (9, bad_review)):
            with self.subTest(step_no=step_no), self.assertRaises(StepDomainError):
                validate_step_output(
                    step_no,
                    output,
                    search_enabled=False,
                    error_code="INVALID_STEP_OUTPUT",
                )

    def test_budget_arithmetic_rejects_sub_cent_drift(self) -> None:
        bad_subtotal = deepcopy(valid_step_output(5))
        bad_subtotal["items"][0]["subtotal"] += 0.009
        bad_total = deepcopy(valid_step_output(5))
        bad_total["totalAmount"] += 0.009

        for output in (bad_subtotal, bad_total):
            with self.assertRaises(StepDomainError) as raised:
                validate_step_output(
                    5,
                    output,
                    search_enabled=False,
                    error_code="INVALID_STEP_OUTPUT",
                )
            self.assertEqual(raised.exception.code, "INVALID_STEP_OUTPUT")

    def test_generated_budget_draft_adds_canonical_arithmetic(self) -> None:
        draft = deepcopy(valid_step_output(5))
        draft.pop("totalAmount")
        draft["items"][0].pop("subtotal")

        canonical = validate_generated_output(
            5,
            json.dumps(draft),
            search_enabled=False,
        )

        self.assertEqual(canonical["items"][0]["subtotal"], 10000.0)
        self.assertEqual(canonical["totalAmount"], 10000.0)

    def test_generated_budget_rejects_model_supplied_derived_fields(self) -> None:
        subtotal_only = deepcopy(valid_step_output(5))
        subtotal_only.pop("totalAmount")
        total_only = deepcopy(valid_step_output(5))
        total_only["items"][0].pop("subtotal")

        for output in (subtotal_only, total_only):
            with self.assertRaises(StepDomainError) as raised:
                validate_generated_output(
                    5,
                    json.dumps(output),
                    search_enabled=False,
                )
            self.assertEqual(raised.exception.code, "INVALID_MODEL_RESPONSE")

    def test_generated_json_rejects_duplicate_keys_and_non_standard_numbers(self) -> None:
        for text in (
            '{"items":[],"items":[]}',
            '{"totalAmount":NaN}',
            '```json\n{"totalAmount":0}\n```',
        ):
            with self.subTest(text=text), self.assertRaises(StepDomainError) as raised:
                validate_generated_output(5, text, search_enabled=False)
            self.assertEqual(raised.exception.code, "INVALID_MODEL_RESPONSE")

    def test_generated_user_visible_text_rejects_internal_identifiers(self) -> None:
        contaminated_values = (
            "请参考 confirmedResearchEvidence.sources 中的天气信息",
            "相似活动与 similar_events、public_trend 均为 missing",
            "活动日期来自 plannedStartAt 和 plannedEndAt",
            "该指标的 sourceType=calculated",
            "请在 actualMetrics 回填后对比 forecastMetrics",
            "仍需补齐 missing_actual_metrics 数据",
        )
        for text in contaminated_values:
            output = deepcopy(valid_step_output(9))
            output["conclusions"] = [text]
            with self.subTest(text=text), self.assertRaises(StepDomainError) as raised:
                validate_generated_output(
                    9,
                    json.dumps(output, ensure_ascii=False),
                    search_enabled=False,
                )
            self.assertEqual(raised.exception.code, "INVALID_MODEL_RESPONSE")

    def test_generated_user_visible_text_accepts_natural_chinese_business_language(self) -> None:
        output = deepcopy(valid_step_output(9))
        output["conclusions"] = ["实际到场人数尚未回填，当前只能保留预测判断。"]
        output["improvements"] = ["活动结束后补充闸机客流与现场销售记录，再完成复盘。"]

        canonical = validate_generated_output(
            9,
            json.dumps(output, ensure_ascii=False),
            search_enabled=False,
        )

        self.assertEqual(canonical["conclusions"], output["conclusions"])
        self.assertEqual(canonical["improvements"], output["improvements"])

    def test_persisted_output_with_legacy_internal_identifier_remains_readable(self) -> None:
        legacy = deepcopy(valid_step_output(9))
        legacy["conclusions"] = ["参考 confirmedResearchEvidence.sources 形成判断"]

        canonical = validate_step_output(
            9,
            legacy,
            search_enabled=False,
            error_code="PERSISTED_STEP_OUTPUT_INVALID",
        )

        self.assertEqual(canonical["conclusions"], legacy["conclusions"])

    def test_research_findings_are_short_for_new_and_persisted_outputs(self) -> None:
        short = valid_step_output(2)
        self.assertEqual(
            validate_step_output(
                2,
                short,
                search_enabled=False,
                error_code="INVALID_STEP_OUTPUT",
            ),
            short,
        )

        long_finding = dict(short)
        long_finding["findings"] = ["x" * 501]
        with self.assertRaises(StepDomainError) as raised:
            validate_step_output(
                2,
                long_finding,
                search_enabled=False,
                error_code="INVALID_STEP_OUTPUT",
            )
        self.assertEqual(raised.exception.code, "INVALID_STEP_OUTPUT")

        with self.assertRaises(StepDomainError) as raised:
            validate_step_output(
                2,
                long_finding,
                search_enabled=False,
                error_code="PERSISTED_STEP_OUTPUT_INVALID",
            )
        self.assertEqual(raised.exception.code, "PERSISTED_STEP_OUTPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
