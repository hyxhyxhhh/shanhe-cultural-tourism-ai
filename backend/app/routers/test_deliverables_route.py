"""End-to-end route checks for persistent generated deliverables."""

import io
import unittest
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app.deliverables.repository import SqlAlchemyDeliverableRepository
from backend.app.deliverables.service import DeliverableService
from backend.auth import get_db_session, require_session
from backend.db import SessionLocal
from backend.models import Activity, ActivityStep, ExecutionTask, STEP_KEYS
from backend.test_activity_steps import valid_step_output

from .deliverables import router


class DeliverableRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()
        self.activity_id = uuid4()
        self.db = SessionLocal()
        activity = Activity(
            id=self.activity_id,
            title="Persistent deliverable route",
            status="completed",
            current_step=9,
            input={"idea": "Generate the three contracted files"},
            search_enabled=False,
            created_by=str(self.user_id),
        )
        self.db.add(activity)
        self.db.add_all(
            ActivityStep(
                activity_id=self.activity_id,
                step_no=step_no,
                step_key=STEP_KEYS[step_no - 1],
                status="confirmed",
                input_json={},
                output_json=valid_step_output(step_no),
                version=1,
                confirmed_by=str(self.user_id),
                confirmed_at=datetime.now(timezone.utc),
            )
            for step_no in range(1, 10)
        )
        self.db.add(
            ExecutionTask(
                activity_id=self.activity_id,
                step_no=7,
                title="Prepare venue",
                description="Complete setup",
                owner="Operations lead",
                due_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
                status="ready",
                attachment_file_ids=[],
            )
        )
        self.db.commit()

        app = FastAPI()
        app.state.deliverable_service = DeliverableService(
            SqlAlchemyDeliverableRepository(SessionLocal)
        )
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(user_id=self.user_id)
        app.dependency_overrides[get_db_session] = lambda: self.db
        self.client = TestClient(app)
        self.base_url = f"/api/activities/{self.activity_id}/deliverables"

    def tearDown(self) -> None:
        self.client.close()
        self.db.rollback()
        self.db.execute(delete(Activity).where(Activity.id == self.activity_id))
        self.db.commit()
        self.db.close()

    def test_generate_list_version_and_download_three_files(self) -> None:
        first = self.client.post(f"{self.base_url}/generate")
        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(
            {record["filename"] for record in first.json()},
            {"event-plan.docx", "budget.xlsx", "execution-tasks.xlsx"},
        )
        self.assertEqual({record["version"] for record in first.json()}, {1})

        second = self.client.post(f"{self.base_url}/generate")
        self.assertEqual(second.status_code, 202, second.text)
        self.assertEqual({record["version"] for record in second.json()}, {2})

        listed = self.client.get(self.base_url)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()), 6)

        record = next(item for item in first.json() if item["filename"] == "budget.xlsx")
        downloaded = self.client.get(f"{self.base_url}/{record['id']}/download")
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertEqual(downloaded.content[:2], b"PK")
        self.assertIn("budget.xlsx", downloaded.headers["content-disposition"])

    def test_generate_allows_execution_task_without_owner_or_due_at(self) -> None:
        task = self.db.scalar(
            select(ExecutionTask).where(ExecutionTask.activity_id == self.activity_id)
        )
        self.assertIsNotNone(task)
        task.owner = None
        task.due_at = None
        self.db.commit()

        generated = self.client.post(f"{self.base_url}/generate")

        self.assertEqual(generated.status_code, 202, generated.text)
        task_file = next(
            item for item in generated.json() if item["filename"] == "execution-tasks.xlsx"
        )
        downloaded = self.client.get(f"{self.base_url}/{task_file['id']}/download")
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            worksheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn('<c r="B2" t="inlineStr"><is><t></t></is></c>', worksheet)
        self.assertIn('<c r="C2" t="inlineStr"><is><t></t></is></c>', worksheet)


if __name__ == "__main__":
    unittest.main()
