"""Standard-library tests for fixed deliverable packages."""

import io
import unittest
import zipfile

from .generator import generate_budget_xlsx, generate_execution_tasks_xlsx, generate_plan_docx


class DeliverableGeneratorTests(unittest.TestCase):
    def test_fixed_filenames_and_zip_packages(self) -> None:
        files = [
            generate_plan_docx("Plan", {"Brief": "missing"}),
            generate_budget_xlsx(
                [{"项目": "场地", "数量": 1, "单价": 100, "小计": 100, "来源": "报价单"}]
            ),
            generate_execution_tasks_xlsx(
                [
                    {
                        "任务": "审批",
                        "负责人": "张三",
                        "截止时间": "2026-10-01T09:00:00+08:00",
                        "状态": "ready",
                        "附件": "",
                    }
                ]
            ),
        ]
        self.assertEqual([file.filename for file in files], ["event-plan.docx", "budget.xlsx", "execution-tasks.xlsx"])
        for file in files:
            with zipfile.ZipFile(io.BytesIO(file.content)) as archive:
                self.assertTrue(archive.namelist())

    def test_spreadsheet_generation_rejects_missing_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing required spreadsheet columns"):
            generate_budget_xlsx([{"项目": "场地", "来源": "报价单"}])

    def test_spreadsheet_generation_rejects_null_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "spreadsheet columns cannot be null"):
            generate_execution_tasks_xlsx(
                [
                    {
                        "任务": "审批",
                        "负责人": None,
                        "截止时间": "2026-10-01T09:00:00+08:00",
                        "状态": "ready",
                        "附件": "",
                    }
                ]
            )

    def test_generators_reject_empty_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "document title is required"):
            generate_plan_docx("", {"Brief": "content"})
        with self.assertRaisesRegex(ValueError, "document sections are required"):
            generate_plan_docx("Plan", {})
        with self.assertRaisesRegex(ValueError, "at least one spreadsheet data row is required"):
            generate_budget_xlsx([])


if __name__ == "__main__":
    unittest.main()
