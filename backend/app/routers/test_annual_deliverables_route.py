"""Download and parse real annual artifacts, including all event briefs."""

from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
import unittest
from uuid import uuid4
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.activities import create_activity
from backend.app.deliverables.repository import SqlAlchemyDeliverableRepository
from backend.app.deliverables.service import DeliverableService
from backend.auth import get_db_session, require_session
from backend.db import SessionLocal
from backend.models import Activity, ExecutionTask
from backend.test_annual_planning import ANNUAL_INPUT, ANNUAL_OUTPUT
from backend.test_activity_steps import valid_step_output
from .deliverables import router


def annual_outputs():
    outputs = {}
    labels = ["全年共享", "春季花事", "暑期研学"]
    for step_no in range(4, 10):
        blocks = []
        for index, label in enumerate(labels):
            block = deepcopy(valid_step_output(step_no))
            if step_no == 4:
                block["schedule"][0]["title"] = f"{label}内容安排"
            elif step_no == 5:
                amount = [0.1, 0.2, 0.3][index]
                block["items"][0].update(item=f"{label}预算项目", quantity=1.0, unitPrice=amount, subtotal=amount)
                block["totalAmount"] = amount
            elif step_no == 6:
                block["strategy"] = f"{label}传播策略"
            elif step_no == 7:
                block["tasks"][0]["title"] = f"{label}执行任务"
            elif step_no == 8:
                block["ticketingPlan"] = f"{label}渠道安排"
            else:
                block["conclusions"] = [f"{label}复盘安排"]
            blocks.append(block)
        outputs[step_no] = {"annualPlan": blocks[0], "eventPlans": [{"eventId": event["id"], "output": block} for event, block in zip(ANNUAL_OUTPUT["eventBriefs"], blocks[1:], strict=True)]}
        if step_no == 5:
            outputs[step_no]["annualTotalAmount"] = 0.6
    return outputs


def read_xlsx(content):
    with ZipFile(BytesIO(content)) as archive:
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [["".join(cell.itertext()) for cell in row.findall("s:c", ns)] for row in sheet.findall("s:sheetData/s:row", ns)]


class AnnualDeliverableRouteTests(unittest.TestCase):
    def setUp(self):
        self.owner = uuid4()
        self.db = SessionLocal()
        self.activity = create_activity(title="2027年度景区总策划", idea=ANNUAL_INPUT["idea"], created_by=str(self.owner), input_data=ANNUAL_INPUT, session=self.db)
        self.activity.status = "completed"
        self.activity.current_step = 9
        outputs = annual_outputs()
        for step in self.activity.steps:
            step.status = "confirmed"
            if step.step_no == 3:
                step.output_json = deepcopy(ANNUAL_OUTPUT)
            elif step.step_no >= 4:
                step.output_json = outputs[step.step_no]
        execution = outputs[7]
        blocks = [execution["annualPlan"], *[item["output"] for item in execution["eventPlans"]]]
        for index, block in enumerate(blocks):
            self.db.add(ExecutionTask(activity_id=self.activity.id, step_no=7, title=block["tasks"][0]["title"], status=["ready", "in_progress", "completed"][index], attachment_file_ids=[], source_step_version=1, source_task_index=index))
        self.db.add(ExecutionTask(activity_id=self.activity.id, title="旧版任务不应导出", status="ready", attachment_file_ids=[], source_step_version=99, source_task_index=0))
        self.db.add(ExecutionTask(activity_id=self.activity.id, title="补充人工任务", status="ready", attachment_file_ids=[]))
        self.db.commit()
        app = FastAPI()
        app.include_router(router)
        app.state.deliverable_service = DeliverableService(SqlAlchemyDeliverableRepository(SessionLocal))
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(user_id=self.owner)
        app.dependency_overrides[get_db_session] = lambda: self.db
        self.client = TestClient(app)
        self.base_url = f"/api/activities/{self.activity.id}/deliverables"

    def tearDown(self):
        self.client.close()
        self.db.rollback()
        self.db.execute(delete(Activity).where(Activity.id == self.activity.id))
        self.db.commit()
        self.db.close()

    def test_three_downloaded_files_preserve_annual_and_each_event_content(self):
        generated = self.client.post(f"{self.base_url}/generate")
        self.assertEqual(generated.status_code, 202, generated.text)
        downloads = {}
        for record in generated.json():
            response = self.client.get(f"{self.base_url}/{record['id']}/download")
            self.assertEqual(response.status_code, 200, response.text)
            downloads[record["filename"]] = response.content
        with ZipFile(BytesIO(downloads["event-plan.docx"])) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
        text = "\n".join(document.itertext())
        self.assertIn(ANNUAL_OUTPUT["annualNarrative"], text)
        for label in ("全年共享", "春季花事", "暑期研学"):
            for suffix in ("内容安排", "预算项目", "传播策略", "执行任务", "渠道安排", "复盘安排"):
                self.assertIn(label + suffix, text)
        for heading in ("年度规划周期", "年度目标", "时间窗口", "可共享资源", "预热期", "来源类型", "推算数据"):
            self.assertIn(heading, text)
        for technical in ("annualPlan", "eventPlans", "annualNarrative", "unitPrice", "sourceType", "warmup", "externalActionsDraftOnly"):
            self.assertNotIn(technical, text)
        self.assertIn("全年预算合计：0.6", text)

        budget = read_xlsx(downloads["budget.xlsx"])
        self.assertEqual(budget[0], ["项目", "数量", "单价", "小计", "来源"])
        details = [row for row in budget[1:] if row[1]]
        self.assertEqual(len(details), 3)
        self.assertEqual(sum(Decimal(row[3]) for row in details), Decimal("0.6"))
        self.assertEqual(budget[-1][3], "0.6")
        self.assertTrue(all("推算数据" in row[4] for row in budget[1:]))
        tasks = read_xlsx(downloads["execution-tasks.xlsx"])
        self.assertEqual(len(tasks), 5)  # Three confirmed generated tasks + one manual task.
        self.assertEqual([row[3] for row in tasks[1:]], ["待执行", "执行中", "已完成", "待执行"])
        self.assertIn("年度统筹｜全年共享执行任务", tasks[1][0])
        self.assertIn("春季花事｜春季花事执行任务", tasks[2][0])
        self.assertIn("暑期研学｜暑期研学执行任务", tasks[3][0])
        self.assertNotIn("旧版任务不应导出", str(tasks))

    def test_missing_current_execution_task_fails_without_publishing_files(self):
        self.db.execute(delete(ExecutionTask).where(ExecutionTask.activity_id == self.activity.id, ExecutionTask.source_step_version == 1, ExecutionTask.source_task_index == 2))
        self.db.commit()
        rejected = self.client.post(f"{self.base_url}/generate")
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(rejected.json()["detail"]["code"], "EXECUTION_TASK_SYNC_CONFLICT")
        self.assertEqual(self.client.get(self.base_url).json(), [])

    def test_changed_event_scope_fails_without_silently_dropping_an_event(self):
        step = self.activity.steps[3]
        output = deepcopy(step.output_json)
        output["eventPlans"][1]["eventId"] = "wrong-event"
        step.output_json = output
        self.db.commit()
        rejected = self.client.post(f"{self.base_url}/generate")
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(rejected.json()["detail"]["code"], "ANNUAL_EVENT_SCOPE_MISMATCH")
        self.assertEqual(self.client.get(self.base_url).json(), [])


if __name__ == "__main__":
    unittest.main()
