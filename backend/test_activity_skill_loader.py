from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from backend.activity_prompt import RESEARCH_DRAFTING_PREFIX, build_activity_system_prompt
from backend.activity_skill_loader import (
    ActivitySkillError,
    SKILLS_ROOT,
    load_activity_step_skill,
)
from backend.activity_steps import StepDomainError, validate_generated_output
from backend.models import STEP_KEYS


class ActivitySkillLoaderTests(unittest.TestCase):
    def test_every_workflow_step_loads_its_exact_versioned_skill(self) -> None:
        for step_no, step_key in enumerate(STEP_KEYS, start=1):
            with self.subTest(step_no=step_no, step_key=step_key):
                skill = load_activity_step_skill(step_no, step_key)

                self.assertEqual(skill.step_no, step_no)
                self.assertEqual(skill.step_key, step_key)
                self.assertEqual(skill.skill_id, f"activity-step-{step_key}")
                self.assertEqual(skill.version, "1.0.0")
                self.assertIn("## 输入契约", skill.content)
                self.assertIn("## 输出契约", skill.content)
                self.assertIn("## 业务判断规则", skill.content)
                self.assertIn("## 禁止行为", skill.content)

    def test_prompt_contains_loaded_skill_identity_and_strict_json_rule(self) -> None:
        prompt = build_activity_system_prompt(5, "budget")

        self.assertIn("# 活动预算与资源配置", prompt)
        self.assertIn("activity-step-budget@1.0.0", prompt)
        self.assertIn("预算确认后才可生成宣传计划", prompt)
        self.assertIn("绝不输出 JSON null", prompt)
        self.assertIn("只能包含一个符合 requiredJsonSchema 的 JSON 对象", prompt)
        self.assertIn("首字符必须是 {，末字符必须是 }", prompt)
        self.assertIn("不得使用 Markdown 代码块", prompt)
        self.assertIn("不得输出 `subtotal`、`totalAmount`", prompt)
        self.assertIn("服务端会根据数量和单价确定性计算", prompt)

    def test_execution_plan_prompt_bounds_work_package_count_and_length(self) -> None:
        prompt = build_activity_system_prompt(7, "execution_plan")

        self.assertIn("任务总数严格控制在 8 至 10 项", prompt)
        self.assertIn("不得为凑数量拆分重复微任务", prompt)
        self.assertIn("分别最多使用两句短句", prompt)
        self.assertIn("依赖关系只列直接前置任务的标题", prompt)

    def test_research_prompt_precedes_skill_with_concise_pure_json_drafting_targets(self) -> None:
        prompt = build_activity_system_prompt(2, "research")
        self.assertTrue(prompt.startswith(RESEARCH_DRAFTING_PREFIX))
        self.assertIn("parsed directly by json.loads", prompt)
        self.assertIn("summary around 200 characters", prompt)
        self.assertIn("6-10 distinct findings around 30-60 characters each", prompt)
        self.assertIn("4-6 directly supporting citations", prompt)
        self.assertIn("booking/transport/venue constraints", prompt)
        self.assertIn("Deduplicate findings and never fabricate to reach a count", prompt)
        self.assertIn("资料不足明确标为待核实", prompt)
        self.assertIn("All valid public search sources and their complete excerpts are included", prompt)
        self.assertIn("不限制每个范围的来源条数", prompt)
        self.assertIn("excerpts around 30-80 characters", prompt)
        self.assertIn("These are drafting targets within the required schema", prompt)
        self.assertIn("copy label, url, capturedAt, rank, scope, providerRequestId", prompt)
        self.assertIn("one character-for-character continuous substring", prompt)
        self.assertIn("Never insert ellipses or join fragments", prompt)
        self.assertIn("do not normalize punctuation or whitespace", prompt)
        self.assertIn("may be shorter than the 30-character drafting target", prompt)
        self.assertIn("# 活动公开信息研判", prompt)
        self.assertIn("不超过 3000 个字符", prompt)
        self.assertIn("不得为凑数量编造", prompt)
        for step_no, step_key in enumerate(STEP_KEYS, start=1):
            if step_no != 2:
                self.assertNotIn(RESEARCH_DRAFTING_PREFIX, build_activity_system_prompt(step_no, step_key))

    def test_brief_missing_fields_use_chinese_business_descriptions(self) -> None:
        prompt = build_activity_system_prompt(1, "brief")

        self.assertIn("`missingFields` 数组中的每个值只能使用自然中文业务缺失项标签或简短描述", prompt)
        self.assertIn("不得使用 JSON 字段名或技术标识", prompt)
        self.assertNotIn("`missingFields` 使用输出契约中的字段名", prompt)

        output = {
            "standardizedBrief": {"objective": "策划文旅活动"},
            "missingFields": ["场地开放规则", "客流历史数据"],
        }
        self.assertEqual(
            validate_generated_output(1, json.dumps(output, ensure_ascii=False), search_enabled=False),
            output,
        )

        for identifier in ("targetAudience", "knownConstraints"):
            with self.subTest(identifier=identifier):
                technical_output = {**output, "missingFields": [identifier]}
                with self.assertRaises(StepDomainError) as raised:
                    validate_generated_output(
                        1,
                        json.dumps(technical_output, ensure_ascii=False),
                        search_enabled=False,
                    )
                self.assertEqual(raised.exception.code, "INVALID_MODEL_RESPONSE")
                self.assertEqual(
                    raised.exception.message,
                    "Model response contained an internal technical identifier in user-visible text",
                )

    def test_every_skill_forbids_internal_identifiers_in_user_visible_text(self) -> None:
        required_examples = (
            "confirmedResearchEvidence",
            "confirmedResearchEvidence.sources",
            "similar_events",
            "public_trend",
            "plannedStartAt",
            "plannedEndAt",
            "sourceType",
            "calculated",
            "missing",
            "actualMetrics",
            "forecastMetrics",
            "missingActualMetrics",
        )
        for step_no, step_key in enumerate(STEP_KEYS, start=1):
            with self.subTest(step_no=step_no, step_key=step_key):
                skill = load_activity_step_skill(step_no, step_key)
                self.assertIn("任何面向用户的字符串值", skill.content)
                self.assertIn("camelCase", skill.content)
                self.assertIn("snake_case", skill.content)
                self.assertIn("结构化 JSON 键", skill.content)
                for identifier in required_examples:
                    self.assertIn(f"`{identifier}`", skill.content)

    def test_step_key_mismatch_fails_without_fallback(self) -> None:
        with self.assertRaisesRegex(
            ActivitySkillError,
            "activity skill stepKey for step 2 must be research",
        ):
            load_activity_step_skill(2, "brief")

    def test_invalid_manifest_and_missing_skill_section_fail_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            shutil.copytree(SKILLS_ROOT, root)
            manifest_path = root / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skills"][0]["unexpected"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ActivitySkillError, "contains unknown field"):
                load_activity_step_skill(1, "brief", skills_root=root)

            shutil.rmtree(root)
            shutil.copytree(SKILLS_ROOT, root)
            skill_path = root / "v1" / "01-brief.md"
            skill_path.write_text("# 活动简报标准化\n", encoding="utf-8")

            with self.assertRaisesRegex(ActivitySkillError, "missing section"):
                load_activity_step_skill(1, "brief", skills_root=root)

    def test_duplicate_manifest_key_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            shutil.copytree(SKILLS_ROOT, root)
            (root / "manifest.json").write_text(
                '{"schemaVersion":1,"schemaVersion":1,"skills":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ActivitySkillError, "not valid JSON"):
                load_activity_step_skill(1, "brief", skills_root=root)


if __name__ == "__main__":
    unittest.main()
