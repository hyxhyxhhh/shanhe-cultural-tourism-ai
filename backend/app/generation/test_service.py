"""Tests for steps five through nine generation rules."""

import asyncio
import unittest

from backend.app.providers.fake import FakeProvider

from .prerequisites import assert_can_generate
from .service import GenerationContext, StepGenerationService


class GenerationPrerequisiteTests(unittest.TestCase):
    def test_step_nine_requires_step_eight_confirmation(self) -> None:
        for status in (None, "locked", "draft", "review", "needs_review"):
            with self.subTest(status=status):
                statuses = {} if status is None else {8: status}
                with self.assertRaisesRegex(ValueError, "steps not confirmed: 8"):
                    assert_can_generate(9, statuses)
        assert_can_generate(9, {8: "confirmed"})

    def test_all_later_step_prerequisites_are_exact(self) -> None:
        allowed = {
            5: {4: "confirmed"},
            6: {5: "confirmed"},
            7: {5: "confirmed", 6: "confirmed"},
            8: {7: "confirmed"},
            9: {8: "confirmed"},
        }
        for step_no, statuses in allowed.items():
            with self.subTest(step_no=step_no):
                assert_can_generate(step_no, statuses)


class StepGenerationServiceTests(unittest.TestCase):
    def test_generation_keeps_model_run_metadata_for_audit(self) -> None:
        provider = FakeProvider({"activity_step_5": {"total": 1200}})
        result = asyncio.run(
            StepGenerationService(provider).generate(
                GenerationContext(
                    activity_id="activity-1",
                    step_no=5,
                    model="selected-model",
                    prior_outputs={4: {"schedule": []}},
                    request_id="job-1",
                    prior_statuses={4: "confirmed"},
                )
            )
        )

        self.assertEqual(provider.requests[0].model, "selected-model")
        self.assertIn("activity-step-budget@1.0.0", provider.requests[0].messages[0]["content"])
        self.assertEqual(result["data"], {"total": 1200})
        self.assertEqual(
            result["modelRun"],
            {
                "model": "selected-model",
                "providerRequestId": "job-1",
                "promptTokens": 0,
                "completionTokens": 0,
                "totalTokens": 0,
                "durationMs": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
