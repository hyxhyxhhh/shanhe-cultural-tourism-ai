import unittest
from unittest.mock import MagicMock

from backend.activities import InvalidActivityTransition, create_activity, pause_activity, update_activity
from backend.models import STEP_KEYS


class ActivityCreationTests(unittest.TestCase):
    def test_activity_starts_with_first_step_open_and_remaining_steps_locked(self) -> None:
        activity = create_activity(
            title="  Lantern Festival  ",
            idea="  Create an evening event  ",
            created_by="developer@example.test",
            input_data={"location": "Riverside park"},
            session=MagicMock(),
        )

        self.assertEqual(activity.title, "Lantern Festival")
        self.assertEqual(activity.input["location"], "Riverside park")
        self.assertEqual(activity.input["idea"], "Create an evening event")
        self.assertEqual([step.step_key for step in activity.steps], list(STEP_KEYS))
        self.assertEqual([step.status for step in activity.steps], ["draft"] + ["locked"] * 8)
        self.assertEqual(activity.steps[0].input_json, activity.input)
        self.assertEqual(activity.steps[1].input_json, {"useWebSearch": False})

    def test_activity_requires_owner_and_idea(self) -> None:
        with self.assertRaisesRegex(ValueError, "created_by is required"):
            create_activity(title="Event", idea="Idea", created_by=" ")
        with self.assertRaisesRegex(ValueError, "idea is required"):
            create_activity(title="Event", idea=" ", created_by="developer@example.test")

    def test_paused_activity_can_resume_but_cannot_return_to_draft(self) -> None:
        session = MagicMock()
        activity = create_activity(
            title="Event",
            idea="Idea",
            created_by="developer@example.test",
            session=session,
        )

        pause_activity(activity=activity, session=session)
        self.assertEqual(activity.status, "paused")
        with self.assertRaisesRegex(InvalidActivityTransition, "paused to draft"):
            update_activity(activity=activity, status="draft", session=session)

        update_activity(activity=activity, status="running", session=session)
        self.assertEqual(activity.status, "running")


if __name__ == "__main__":
    unittest.main()
