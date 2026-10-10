"""PostgreSQL persistence checks for versioned deliverables."""

import asyncio
import unittest
from uuid import uuid4

from sqlalchemy import delete

from backend.app.deliverables.generator import DeliverableFile
from backend.app.deliverables.repository import SqlAlchemyDeliverableRepository
from backend.db import SessionLocal
from backend.models import Activity


class SqlAlchemyDeliverableRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.activity_id = uuid4()
        with SessionLocal.begin() as session:
            session.add(
                Activity(
                    id=self.activity_id,
                    title="Deliverable repository test",
                    status="draft",
                    current_step=1,
                    input={"idea": "Verify generated files"},
                    search_enabled=False,
                    created_by="deliverable-test-user",
                )
            )
        self.repository = SqlAlchemyDeliverableRepository(SessionLocal)

    def tearDown(self) -> None:
        with SessionLocal.begin() as session:
            session.execute(delete(Activity).where(Activity.id == self.activity_id))

    def test_batch_save_is_persistent_and_versions_without_overwrite(self) -> None:
        first_files = (
            DeliverableFile("event-plan.docx", "application/test-doc", b"plan-v1"),
            DeliverableFile("budget.xlsx", "application/test-sheet", b"budget-v1"),
        )
        first = asyncio.run(self.repository.save_batch(str(self.activity_id), first_files))
        second = asyncio.run(
            self.repository.save_batch(
                str(self.activity_id),
                (DeliverableFile("event-plan.docx", "application/test-doc", b"plan-v2"),),
            )
        )

        self.assertEqual([record.version for record in first], [1, 1])
        self.assertEqual(second[0].version, 2)
        self.assertNotEqual(first[0].storage_key, second[0].storage_key)
        self.assertEqual(asyncio.run(self.repository.read(first[0])), b"plan-v1")
        self.assertEqual(asyncio.run(self.repository.read(second[0])), b"plan-v2")

        listed = asyncio.run(self.repository.list(str(self.activity_id)))
        self.assertEqual(len(listed), 3)
        plan_versions = [record.version for record in listed if record.filename == "event-plan.docx"]
        self.assertEqual(plan_versions, [2, 1])


if __name__ == "__main__":
    unittest.main()
