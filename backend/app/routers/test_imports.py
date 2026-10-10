"""Import contract for the merged application modules."""

import importlib
import unittest


class RouterImportTests(unittest.TestCase):
    def test_merged_modules_import_without_optional_runtime_dependencies(self) -> None:
        module_names = (
            "backend.app.routers.research",
            "backend.app.routers.generation",
            "backend.app.routers.execution",
            "backend.app.routers.deliverables",
            "backend.app.routers.register",
        )
        for module_name in module_names:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main()
