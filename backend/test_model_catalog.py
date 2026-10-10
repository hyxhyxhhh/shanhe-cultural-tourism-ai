from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import require_session
from backend.model_catalog import (
    ModelCatalogConfigurationError,
    parse_allowed_models,
    router,
)


class ModelCatalogConfigurationTests(unittest.TestCase):
    def test_valid_models_preserve_configured_order(self) -> None:
        self.assertEqual(
            parse_allowed_models("model-a,vendor/model-b,model.c:latest"),
            ("model-a", "vendor/model-b", "model.c:latest"),
        )

    def test_invalid_configuration_fails_explicitly(self) -> None:
        invalid_values = (
            None,
            "",
            "   ",
            ",",
            "model-a,",
            ",model-a",
            "model-a,,model-b",
            "model-a, model-b",
            " model-a,model-b",
            "model-a,model-b ",
            "model-a,model-a",
            "invalid model",
            "invalid?model",
            "模型",
            "m" * 201,
        )
        for raw_value in invalid_values:
            with self.subTest(raw_value=raw_value):
                with self.assertRaises(ModelCatalogConfigurationError):
                    parse_allowed_models(raw_value)


class ModelCatalogApiTests(unittest.TestCase):
    def test_endpoint_requires_authentication(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with patch.dict(os.environ, {"CCODE_ALLOWED_MODELS": "model-a"}, clear=False):
            with TestClient(app) as client:
                response = client.get("/api/models")
        self.assertEqual(response.status_code, 401, response.text)

    def test_authenticated_endpoint_returns_exact_configured_list(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(
            user_id=uuid4(),
            account="planner@example.test",
            display_name="Planner",
            role_id="planner",
        )
        with patch.dict(
            os.environ,
            {"CCODE_ALLOWED_MODELS": "model-b,vendor/model-a"},
            clear=False,
        ):
            with TestClient(app) as client:
                response = client.get("/api/models")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"models": ["model-b", "vendor/model-a"]})

    def test_invalid_catalog_configuration_is_service_error(self) -> None:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_session] = lambda: SimpleNamespace(
            user_id=uuid4(),
            account="planner@example.test",
            display_name="Planner",
            role_id="planner",
        )
        with patch.dict(os.environ, {}, clear=True):
            with TestClient(app) as client:
                response = client.get("/api/models")
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()["detail"]["code"], "MODEL_CATALOG_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
