"""Integrated FastAPI route and runtime dependency assembly checks."""

import unittest

from backend.app.deliverables.service import DeliverableService
from backend.main import app


class RuntimeAssemblyTests(unittest.TestCase):
    def test_canonical_generation_route_is_registered_once(self) -> None:
        operation = app.openapi()["paths"][
            "/api/activities/{activity_id}/steps/{step_no}/generate"
        ]
        self.assertEqual(set(operation), {"post"})

    def test_integrated_routes_and_deliverable_service_are_registered(self) -> None:
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/activities/{activity_id}/research", paths)
        self.assertIn("/api/activities/{activity_id}/execution-tasks", paths)
        self.assertIn("/api/activities/{activity_id}/deliverables/generate", paths)
        self.assertIsInstance(app.state.deliverable_service, DeliverableService)


if __name__ == "__main__":
    unittest.main()
