"""Strict request-contract checks for execution task updates."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.auth import get_db_session, require_session
from backend.db import engine
from backend.models import Activity, ExecutionTask

from .execution import ExecutionTaskUpdate, router


class ExecutionTaskUpdateContractTests(unittest.TestCase):
    def test_empty_unknown_and_null_status_are_rejected(self) -> None:
        for payload in ({}, {"unexpected": True}, {"status": None}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    ExecutionTaskUpdate.model_validate(payload)

    def test_owner_and_due_at_can_be_explicitly_cleared(self) -> None:
        payload = ExecutionTaskUpdate.model_validate({"owner": None, "dueAt": None})
        self.assertEqual(payload.model_fields_set, {"owner", "due_at"})
        self.assertIsNone(payload.owner)
        self.assertIsNone(payload.due_at)

    def test_due_at_requires_timezone(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionTaskUpdate.model_validate({"dueAt": "2026-10-01T18:00:00"})


class ExecutionTaskPatchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.current_user = SimpleNamespace(user_id=uuid4())
        self.activity = Activity(
            title="Execution PATCH contract",
            status="running",
            current_step=7,
            input={"idea": "Test strict patching"},
            search_enabled=False,
            created_by=str(self.current_user.user_id),
        )
        self.db.add(self.activity)
        self.db.flush()
        self.task = ExecutionTask(
            activity_id=self.activity.id,
            step_no=7,
            title="Existing task",
            owner="Owner",
            status="ready",
            attachment_file_ids=[],
        )
        self.db.add(self.task)
        self.db.commit()

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: self.current_user
        app.dependency_overrides[get_db_session] = lambda: self.db
        self.client = TestClient(app)
        self.url = f"/api/activities/{self.activity.id}/execution-tasks/{self.task.id}"

    def tearDown(self) -> None:
        self.client.close()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def test_fastapi_rejects_empty_unknown_and_null_status(self) -> None:
        for payload in ({}, {"unexpected": True}, {"status": None}):
            with self.subTest(payload=payload):
                response = self.client.patch(self.url, json=payload)
                self.assertEqual(response.status_code, 422, response.text)

    def test_fastapi_allows_explicit_owner_and_due_at_clear(self) -> None:
        response = self.client.patch(self.url, json={"owner": None, "dueAt": None})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["owner"])
        self.assertIsNone(response.json()["dueAt"])


if __name__ == "__main__":
    unittest.main()
