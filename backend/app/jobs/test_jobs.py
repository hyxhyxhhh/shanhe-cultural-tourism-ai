"""Standard-library tests for recoverable job state."""

import asyncio
import unittest

from .models import JobStatus
from .repository import InMemoryJobRepository
from .service import JobService
from .sse import event_replay_response


class JobServiceTests(unittest.TestCase):
    def test_idempotency_and_event_replay(self) -> None:
        async def scenario():
            service = JobService(InMemoryJobRepository())
            first = await service.get_or_create(activity_id="a", kind="test", idempotency_key="same")
            second = await service.get_or_create(activity_id="a", kind="test", idempotency_key="same")
            self.assertEqual(first.id, second.id)

            other_activity = await service.get_or_create(
                activity_id="b", kind="test", idempotency_key="same"
            )
            other_kind = await service.get_or_create(
                activity_id="a", kind="other", idempotency_key="same"
            )
            other_step = await service.get_or_create(
                activity_id="a", kind="test", step_no=2, idempotency_key="same"
            )
            self.assertEqual(len({first.id, other_activity.id, other_kind.id, other_step.id}), 4)

            async def worker(progress):
                await progress(50, "half")
                return {"ok": True}

            await service.execute(first, worker)
            saved = await service.get(first.id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.status, JobStatus.COMPLETED)
            events = await service.events_since(first.id)
            self.assertGreaterEqual(len(events), 3)

        asyncio.run(scenario())

    def test_worker_exception_is_not_exposed(self) -> None:
        async def scenario():
            service = JobService(InMemoryJobRepository())
            job = await service.get_or_create(
                activity_id="a", kind="test", idempotency_key="failure"
            )

            async def worker(_progress):
                raise RuntimeError("secret provider response")

            failed = await service.execute(job, worker)
            self.assertEqual(failed.status, JobStatus.FAILED)
            self.assertEqual(failed.error_code, "job_failed")
            self.assertEqual(failed.error_message, "任务处理失败")
            self.assertNotIn("secret provider response", str(failed.as_dict()))

            async def successful_worker(_progress):
                return {"ok": True}

            completed = await service.execute(failed, successful_worker)
            self.assertEqual(completed.status, JobStatus.COMPLETED)
            self.assertIsNone(completed.error_code)
            self.assertIsNone(completed.error_message)

        asyncio.run(scenario())

    def test_event_response_is_explicitly_finite_replay(self) -> None:
        response = event_replay_response(InMemoryJobRepository(), "job-id")
        self.assertEqual(response.headers["x-event-stream-mode"], "replay")
        self.assertNotIn("connection", response.headers)


if __name__ == "__main__":
    unittest.main()
