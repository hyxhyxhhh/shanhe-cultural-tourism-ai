from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4

from pydantic import ValidationError

from backend.activity_prompt import build_activity_system_prompt
from backend.activity_steps import (
    ResearchGenerationOutput,
    StepDomainError,
    build_generation_messages,
    complete_generation,
    generation_failure_diagnostic,
    validate_generated_output,
)
from backend.models import Activity, ActivityStep, SourceReference
from backend.app.research.test_selection import evidence


class ResearchEvidenceContractTests(unittest.TestCase):
    def _activity(self):
        activity_id = uuid4()
        step = ActivityStep(
            id=uuid4(), activity_id=activity_id, step_no=2, step_key="research",
            status="draft", input_json={"useWebSearch": True}, output_json={}, version=2,
        )
        activity = Activity(
            id=activity_id, title="Activity", status="running", current_step=2,
            input={"idea": "Activity"}, search_enabled=True, created_by="user-1",
        )
        activity.steps = [
            ActivityStep(
                id=uuid4(), activity_id=activity_id, step_no=1, step_key="brief",
                status="confirmed", input_json={}, version=2,
                output_json={"standardizedBrief": {"objective": "Activity"}, "missingFields": []},
            ),
            step,
        ]
        source = SourceReference(
            id=uuid4(), activity_id=activity_id, step_no=2, source_type="public",
            label="Report", url="https://example.com/report", excerpt="A" * 4128,
            captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
            published_at="2026-09-20", site_name="Example", authority_level="high",
            rank=1, provider_request_id="request-1", scope="weather",
        )
        return activity, step, source

    def _output(self, excerpt):
        return {
            "summary": "Decision summary", "findings": ["Decision finding"], "risks": [],
            "sources": [{
                "sourceType": "public", "label": "Report", "url": "https://example.com/report",
                "capturedAt": "2026-09-24T00:00:00+00:00", "excerpt": excerpt,
                "publishedAt": "2026-09-20", "siteName": "Example", "authorityLevel": "high",
                "rank": 1, "providerRequestId": "request-1", "scope": "weather",
            }],
        }

    def test_prompt_keeps_complete_evidence_and_requires_bounded_verbatim_extract(self):
        activity, step, source = self._activity()
        session = Mock()
        session.scalars.return_value.all.return_value = [source]
        messages = build_generation_messages(activity, step, session=session)
        instruction, serialized_context = messages[1]["content"].split("\n", 1)
        evidence = json.loads(serialized_context)["publicSearchEvidence"][0]
        self.assertEqual(evidence["excerpt"], source.excerpt)
        self.assertEqual(evidence["providerRequestId"], "request-1")
        self.assertIn("必要原文连续片段", instruction)
        self.assertIn("不超过 3000 个字符", instruction)
        self.assertIn("不得改写、拼接或捏造摘录", instruction)
        self.assertIn("采集时间及存在的搜索元数据", instruction)
        self.assertIn("完整检索摘要仍保留", instruction)
        prompt = build_activity_system_prompt(2, "research")
        self.assertIn("必要原文连续片段", prompt)
        self.assertIn("不超过 3000 个字符", prompt)
        self.assertNotIn("完整原文只保留在对应", prompt)

    def test_model_excerpt_still_rejects_3001_characters(self):
        ResearchGenerationOutput.model_validate(self._output("A" * 3000))
        with self.assertRaises(ValidationError) as raised:
            ResearchGenerationOutput.model_validate(self._output("A" * 3001))
        error = raised.exception.errors(include_input=False, include_url=False)[0]
        self.assertEqual(error["loc"], ("sources", 0, "excerpt"))
        self.assertEqual(error["type"], "string_too_long")
        self.assertEqual(error["ctx"]["max_length"], 3000)

    def test_prompt_includes_all_forty_originals_and_only_compact_selection_metadata(self):
        activity, step, _source = self._activity()
        session = Mock()
        from backend.app.research.selection import RESEARCH_SCOPES
        raw = [evidence(scope=scope, rank=rank) for scope in RESEARCH_SCOPES for rank in reversed(range(10))]
        from unittest.mock import patch
        with patch("backend.activity_steps.load_public_evidence", return_value=raw):
            messages = build_generation_messages(activity, step, session=session)
        context = json.loads(messages[1]["content"].split("\n", 1)[1])
        self.assertEqual(len(context["publicSearchEvidence"]), 40)
        self.assertEqual(context["publicSearchSelection"]["selectedCount"], 40)
        self.assertEqual(context["publicSearchSelection"]["omittedCount"], 0)
        for scope in RESEARCH_SCOPES:
            self.assertEqual([item["rank"] for item in context["publicSearchEvidence"] if item["scope"] == scope], list(range(10)))
        for item in context["publicSearchEvidence"]:
            self.assertEqual(item, next(source for source in raw if source["label"] == item["label"]))
        self.assertNotIn("omitted", context["publicSearchSelection"])
        self.assertNotIn("selected", context["publicSearchSelection"])
        self.assertEqual(len(raw), 40)

    def test_generation_rejects_external_or_rewritten_public_citation_without_saving(self):
        from unittest.mock import patch
        for change in ("external", "metadata", "excerpt"):
            with self.subTest(change=change):
                activity, step, source = self._activity()
                step.status = "generating"
                session = Mock()
                session.scalar.return_value = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
                raw = [evidence(rank=rank) for rank in range(5)]
                chosen = evidence(rank=99) if change == "external" else raw[0]
                citation = {"sourceType": "public", **chosen}
                citation["excerpt"] = chosen["excerpt"][:40]
                if change == "metadata": citation["label"] = "Rewritten title"
                if change == "excerpt": citation["excerpt"] = "Invented excerpt"
                with patch("backend.activity_steps.load_public_evidence", return_value=raw):
                    with self.assertRaises(StepDomainError) as raised:
                        complete_generation(
                            activity=activity, step=step, generation_id=uuid4(), actor="user-1",
                            output_json={"summary": "Summary", "findings": ["Finding"], "risks": [], "sources": [citation]},
                            model="configured-model", request_id="request", duration_ms=10,
                            usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, session=session,
                        )
                expected_code = "PUBLIC_CITATION_EXCERPT_MISMATCH" if change == "excerpt" else "PUBLIC_CITATION_METADATA_MISMATCH"
                self.assertEqual(raised.exception.code, expected_code)
                self.assertEqual(step.output_json, {})
                session.execute.assert_not_called()

    def test_generation_preserves_complete_raw_evidence_and_enters_review(self):
        activity, step, source = self._activity()
        step.status = "generating"
        run = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
        session = Mock()
        session.scalar.return_value = run
        session.scalars.return_value.all.return_value = [source]
        output = self._output(source.excerpt[100:300])
        complete_generation(
            activity=activity, step=step, generation_id=uuid4(), actor="user-1",
            output_json=output, model="configured-model", request_id="model-request",
            duration_ms=10, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            session=session,
        )
        self.assertEqual(step.status, "review")
        self.assertEqual(step.version, 3)
        self.assertEqual(step.output_json, output)
        self.assertEqual(len(source.excerpt), 4128)
        self.assertEqual(run.status, "completed")
        deletion = session.execute.call_args.args[0]
        self.assertIn("source_references.source_type !=", str(deletion))
        self.assertIn("public", deletion.compile().params.values())
        self.assertEqual(list(session.add_all.call_args.args[0]), [])

    def test_generation_can_cite_rank_nine_without_any_hidden_top_three_filter(self):
        from unittest.mock import patch
        activity, step, source = self._activity()
        source.rank = 9
        step.status = "generating"
        session = Mock()
        session.scalar.return_value = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
        output = self._output(source.excerpt[:40])
        output["sources"][0]["rank"] = 9
        original = {key: value for key, value in output["sources"][0].items() if key != "sourceType"}
        original["excerpt"] = source.excerpt
        raw = [evidence(rank=rank) for rank in range(9)] + [original]
        with patch("backend.activity_steps.load_public_evidence", return_value=raw):
            complete_generation(
                activity=activity, step=step, generation_id=uuid4(), actor="user-1",
                output_json=output, model="configured-model", request_id="request",
                duration_ms=10, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, session=session,
            )
        self.assertEqual(step.status, "review")
        self.assertEqual(step.output_json["sources"][0]["rank"], 9)
        self.assertEqual(len(raw[-1]["excerpt"]), 4128)

    def test_public_verbatim_warm_weather_excerpt_passes_schema_and_provenance(self):
        original = "the best times of year to visit Chongqing for warm-weather activities are from mid April to late May and from late September to early November"
        activity, step, source = self._activity()
        source.excerpt = original
        step.status = "generating"
        session = Mock()
        session.scalar.return_value = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
        session.scalars.return_value.all.return_value = [source]
        output = validate_generated_output(2, json.dumps(self._output(original)), search_enabled=True)
        complete_generation(
            activity=activity, step=step, generation_id=uuid4(), actor="user-1",
            output_json=output, model="configured-model", request_id="request",
            duration_ms=10, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, session=session,
        )
        self.assertEqual(step.status, "review")
        self.assertEqual(step.output_json["sources"][0]["excerpt"], original)

    def test_public_excerpt_exception_does_not_apply_to_other_user_visible_fields(self):
        from copy import deepcopy
        valid = self._output("warm-weather")
        for location in ("summary", "findings", "risks", "label", "siteName", "reasoning", "non-public excerpt", "nested public excerpt"):
            with self.subTest(location=location):
                output = deepcopy(valid)
                if location in {"findings", "risks"}:
                    output[location] = ["warm-weather"]
                elif location == "summary":
                    output[location] = "warm-weather"
                elif location == "non-public excerpt":
                    output["sources"] = [{"sourceType": "actual", "label": "User brief", "excerpt": "warm-weather"}]
                elif location == "nested public excerpt":
                    output["unexpected"] = {"sources": [{"sourceType": "public", "excerpt": "warm-weather"}]}
                else:
                    output["sources"][0][location] = "warm-weather"
                with self.assertRaises(StepDomainError) as raised:
                    validate_generated_output(2, json.dumps(output), search_enabled=True)
                self.assertEqual(raised.exception.code, "INVALID_MODEL_RESPONSE")
                self.assertIn("internal technical identifier", raised.exception.message)

    def test_failed_generation_diagnostics_expose_only_safe_stage_and_field_shape(self):
        sensitive = "private business excerpt and secret-api-key"
        cases = []
        identifiers = self._output("Safe original")
        identifiers["findings"] = [f"warm-weather {sensitive}"]
        cases.append((json.dumps(identifiers), "user_visible_identifier", ["findings", 0]))
        nested = self._output("Safe original")
        nested[sensitive] = {"sources": [{"sourceType": "public", "excerpt": f"warm-weather {sensitive}"}]}
        cases.append((json.dumps(nested), "user_visible_identifier", ["unknown", "sources", 0, "excerpt"]))
        invalid_schema = self._output(sensitive)
        invalid_schema["sources"][0]["rank"] = sensitive
        invalid_schema[sensitive] = sensitive
        cases.append((json.dumps(invalid_schema), "schema_validation", None))
        cases.append((f"```json\n{sensitive}\n```", "json_parse", None))
        for body, stage, path in cases:
            with self.subTest(stage=stage, path=path):
                with self.assertRaises(StepDomainError) as raised:
                    validate_generated_output(2, body, search_enabled=True)
                detail = generation_failure_diagnostic(raised.exception, step_no=2, response_text=body)
                self.assertEqual(detail["stage"], stage)
                self.assertEqual(detail["code"], "INVALID_MODEL_RESPONSE")
                self.assertNotIn(sensitive, json.dumps(detail))
                self.assertNotIn(body, json.dumps(detail))
                if path is not None:
                    self.assertEqual(detail["path"], path)
                if stage == "schema_validation":
                    self.assertTrue(any(item["path"] == ["sources", 0, "rank"] for item in detail["errors"]))
                    self.assertTrue(any(item["path"] == ["unknown"] for item in detail["errors"]))
                    self.assertTrue(all(set(item) == {"path", "type"} for item in detail["errors"]))
                if stage == "json_parse":
                    self.assertEqual(detail["kind"], "markdown_fence")
                    self.assertEqual(detail["position"], 0)

    def test_verbatim_excerpt_rejects_joined_fragments_and_normalized_punctuation_or_whitespace(self):
        original = "门票：免费（需提前预约）。\n车辆出入岛时间：9:00至19:00。\n预约时间：在进岛前7天内进行网上预约。"
        for excerpt in (
            "门票：免费...预约时间：在进岛前7天内进行网上预约。",
            "门票：免费预约时间：在进岛前7天内进行网上预约。",
            "门票:免费（需提前预约）。",
            "门票：免费（需提前预约）。 车辆出入岛时间：9:00至19:00。",
        ):
            with self.subTest(excerpt=excerpt):
                activity, step, source = self._activity()
                source.excerpt = original
                step.status = "generating"
                session = Mock()
                session.scalar.return_value = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
                session.scalars.return_value.all.return_value = [source]
                with self.assertRaises(StepDomainError) as raised:
                    complete_generation(
                        activity=activity, step=step, generation_id=uuid4(), actor="user-1",
                        output_json=self._output(excerpt), model="configured-model", request_id="request",
                        duration_ms=10, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, session=session,
                    )
                self.assertEqual(raised.exception.code, "PUBLIC_CITATION_EXCERPT_MISMATCH")
                self.assertIn("一段连续原文", raised.exception.message)
                self.assertEqual(source.excerpt, original)
                self.assertEqual(step.output_json, {})
                session.execute.assert_not_called()

    def test_short_exact_excerpt_below_drafting_target_is_valid(self):
        activity, step, source = self._activity()
        source.excerpt = "门票：免费（需提前预约）。\n车辆出入岛时间：9:00至19:00。"
        step.status = "generating"
        session = Mock()
        session.scalar.return_value = SimpleNamespace(status="running", activity_id=activity.id, step_no=2)
        session.scalars.return_value.all.return_value = [source]
        complete_generation(
            activity=activity, step=step, generation_id=uuid4(), actor="user-1",
            output_json=self._output("门票：免费（需提前预约）。"), model="configured-model", request_id="request",
            duration_ms=10, usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}, session=session,
        )
        self.assertEqual(step.status, "review")


if __name__ == "__main__":
    unittest.main()
