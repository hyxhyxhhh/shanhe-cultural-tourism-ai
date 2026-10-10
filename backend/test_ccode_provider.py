import json
import logging
import os
import unittest
from unittest.mock import patch

import httpx

from backend.ccode_provider import (
    CcodeAuthenticationError,
    CcodeBalanceError,
    CcodeConfigurationError,
    CcodeInvalidResponseError,
    CcodeModelProvider,
    CcodeModelUnavailableError,
    CcodeNetworkError,
    CcodeRateLimitError,
    CcodeRequestRejectedError,
    CcodeTimeoutError,
    CcodeUpstreamError,
    ModelMessage,
    normalize_chat_completions_url,
)


def response_payload(*, content: object = "Generated text") -> dict[str, object]:
    return {
        "model": "actual-model",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class CcodeProviderTests(unittest.TestCase):
    def provider(self, handler) -> CcodeModelProvider:
        return CcodeModelProvider(
            api_key="super-secret-api-key",
            transport=httpx.MockTransport(handler),
        )

    def test_url_normalization(self) -> None:
        self.assertEqual(
            normalize_chat_completions_url("https://api.ccode.vip"),
            "https://api.ccode.vip/v1/chat/completions",
        )
        self.assertEqual(
            normalize_chat_completions_url("https://api.ccode.vip/v1/"),
            "https://api.ccode.vip/v1/chat/completions",
        )
        invalid_urls = (
            "https://api.openai.com/v1",
            "https://api.ccode.vip:443",
            "https://api.ccode.vip/proxy",
            "https://api.ccode.vip/v1/chat/completions",
        )
        for invalid_url in invalid_urls:
            with self.subTest(invalid_url=invalid_url):
                with self.assertRaises(CcodeConfigurationError):
                    normalize_chat_completions_url(invalid_url)

    def test_request_headers_model_and_success_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), "https://api.ccode.vip/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer super-secret-api-key")
            self.assertEqual(request.headers["content-type"], "application/json")
            self.assertEqual(
                request.read(),
                b'{"model":"selected-model","messages":[{"role":"user","content":"Plan an event"}],"max_tokens":4096,"response_format":{"type":"json_object"}}',
            )
            return httpx.Response(
                200,
                json=response_payload(),
                headers={"x-oneapi-request-id": "req-safe-123"},
            )

        with self.provider(handler) as provider:
            result = provider.generate(
                [ModelMessage(role="user", content="Plan an event")],
                model="selected-model",
                metadata={"activity_id": "activity-1", "step_no": 1},
            )

        self.assertEqual(result.text, "Generated text")
        self.assertEqual(result.model, "actual-model")
        self.assertEqual(result.provider_request_id, "req-safe-123")
        self.assertEqual((result.prompt_tokens, result.completion_tokens, result.total_tokens), (10, 5, 15))
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_missing_environment_configuration_and_timeout_validation(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(CcodeConfigurationError):
                CcodeModelProvider.from_env()

    def test_environment_uses_default_output_limit_and_rejects_invalid_values(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertIn(b'"max_tokens":4096', request.read())
            return httpx.Response(
                200,
                json=response_payload(),
                headers={"x-oneapi-request-id": "request-42"},
            )

        configured = {"CCODE_API_KEY": "key"}
        with patch.dict(os.environ, configured, clear=True):
            with CcodeModelProvider.from_env(transport=httpx.MockTransport(handler)) as provider:
                provider.generate([ModelMessage("user", "hello")], model="selected-model")

        for invalid_value in ("not-an-integer", "255", "16385"):
            with self.subTest(invalid_value=invalid_value):
                with patch.dict(
                    os.environ,
                    {**configured, "CCODE_MAX_OUTPUT_TOKENS": invalid_value},
                    clear=True,
                ):
                    with self.assertRaises(CcodeConfigurationError):
                        CcodeModelProvider.from_env()
        with patch.dict(
            os.environ,
            {"CCODE_API_KEY": "key", "CCODE_REQUEST_TIMEOUT_SECONDS": "0"},
            clear=True,
        ):
            with self.assertRaises(CcodeConfigurationError):
                CcodeModelProvider.from_env()

    def test_error_statuses_are_classified(self) -> None:
        cases = (
            (401, {"error": {"message": "secret upstream text"}}, CcodeAuthenticationError),
            (402, {"error": {"code": "billing_error"}}, CcodeBalanceError),
            (429, {"error": {"code": "rate_limit"}}, CcodeRateLimitError),
            (404, {"error": {"code": "model_not_found"}}, CcodeModelUnavailableError),
            (503, {"error": {"message": "database details"}}, CcodeUpstreamError),
            (400, {"error": {"message": "invalid request details"}}, CcodeRequestRejectedError),
        )
        for status_code, payload, error_type in cases:
            with self.subTest(status_code=status_code, error_type=error_type.__name__):
                with self.provider(
                    lambda _, status_code=status_code, payload=payload: httpx.Response(
                        status_code,
                        json=payload,
                        headers={"x-oneapi-request-id": "request-42"},
                    )
                ) as provider:
                    with self.assertRaises(error_type) as raised:
                        provider.generate([ModelMessage("user", "private prompt")], model="selected-model")
                self.assertEqual(raised.exception.request_id, "request-42")
                self.assertNotIn("private prompt", str(raised.exception))
                self.assertNotIn("secret", str(raised.exception))

    def test_error_body_codes_do_not_override_http_status_classification(self) -> None:
        cases = (
            (429, {"error": {"code": "insufficient_quota"}}, CcodeRateLimitError),
            (400, {"error": {"code": "model_not_found"}}, CcodeRequestRejectedError),
            (400, {"code": "insufficient_balance"}, CcodeRequestRejectedError),
        )
        for status_code, payload, expected_error in cases:
            with self.subTest(status_code=status_code, payload=payload):
                with self.provider(
                    lambda _, payload=payload, status_code=status_code: httpx.Response(
                        status_code,
                        json=payload,
                        headers={"x-oneapi-request-id": "request-42"},
                    )
                ) as provider:
                    with self.assertRaises(expected_error):
                        provider.generate([ModelMessage("user", "hello")], model="selected-model")

    def test_timeout_and_network_errors_are_wrapped_without_secrets(self) -> None:
        failures = (
            (httpx.ReadTimeout("upstream timed out"), CcodeTimeoutError),
            (httpx.ConnectError("network failed"), CcodeNetworkError),
        )
        for failure, error_type in failures:
            with self.subTest(error_type=error_type.__name__):
                with self.provider(lambda _: (_ for _ in ()).throw(failure)) as provider:
                    with self.assertRaises(error_type) as raised:
                        provider.generate([ModelMessage("user", "private prompt")], model="selected-model")
                self.assertNotIn("private prompt", str(raised.exception))
                self.assertNotIn("super-secret-api-key", str(raised.exception))

    def test_non_json_and_missing_fields_are_invalid_responses(self) -> None:
        responses = (
            httpx.Response(200, text="not json", headers={"x-oneapi-request-id": "request-42"}),
            httpx.Response(
                200,
                json={"model": "model", "choices": []},
                headers={"x-oneapi-request-id": "request-42"},
            ),
            httpx.Response(
                200,
                json={"model": "model", "choices": [{"message": {}}]},
                headers={"x-oneapi-request-id": "request-42"},
            ),
        )
        for response in responses:
            with self.subTest(content=response.text):
                with self.provider(lambda _, response=response: response) as provider:
                    with self.assertRaises(CcodeInvalidResponseError):
                        provider.generate([ModelMessage("user", "private prompt")], model="selected-model")

    def test_success_requires_string_content(self) -> None:
        for content in ([{"type": "text", "text": "hello"}], "", "   ", None, 42):
            with self.subTest(content=content):
                with self.provider(
                    lambda _, content=content: httpx.Response(
                        200,
                        json=response_payload(content=content),
                        headers={"x-oneapi-request-id": "request-42"},
                    )
                ) as provider:
                    with self.assertRaises(CcodeInvalidResponseError):
                        provider.generate([ModelMessage("user", "hello")], model="selected-model")

    def test_success_requires_non_blank_model_name(self) -> None:
        payload = response_payload()
        payload["model"] = "   "
        with self.provider(
            lambda _: httpx.Response(
                200,
                json=payload,
                headers={"x-oneapi-request-id": "request-42"},
            )
        ) as provider:
            with self.assertRaises(CcodeInvalidResponseError):
                provider.generate([ModelMessage("user", "hello")], model="selected-model")

    def test_success_requires_oneapi_request_id(self) -> None:
        headers_cases = ({}, {"x-request-id": "fallback-id"}, {"x-oneapi-request-id": "   "})
        for headers in headers_cases:
            with self.subTest(headers=headers):
                with self.provider(
                    lambda _, headers=headers: httpx.Response(200, json=response_payload(), headers=headers)
                ) as provider:
                    with self.assertRaises(CcodeInvalidResponseError):
                        provider.generate([ModelMessage("user", "hello")], model="selected-model")

    def test_success_requires_complete_valid_usage(self) -> None:
        invalid_usage_values = (
            None,
            {},
            {"prompt_tokens": 1, "completion_tokens": 2},
            {"prompt_tokens": 1, "total_tokens": 3},
            {"completion_tokens": 2, "total_tokens": 3},
            {"prompt_tokens": -1, "completion_tokens": 2, "total_tokens": 3},
            {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3},
            {"prompt_tokens": "1", "completion_tokens": 2, "total_tokens": 3},
            {"prompt_tokens": 1.0, "completion_tokens": 2, "total_tokens": 3},
            {"prompt_tokens": 1, "completion_tokens": -2, "total_tokens": 3},
            {"prompt_tokens": 1, "completion_tokens": False, "total_tokens": 3},
            {"prompt_tokens": 1, "completion_tokens": "2", "total_tokens": 3},
            {"prompt_tokens": 1, "completion_tokens": 2.0, "total_tokens": 3},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": -3},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": True},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": "3"},
            {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3.0},
        )
        for usage in invalid_usage_values:
            with self.subTest(usage=usage):
                payload = response_payload()
                if usage is None:
                    payload.pop("usage")
                else:
                    payload["usage"] = usage
                with self.provider(
                    lambda _, payload=payload: httpx.Response(
                        200,
                        json=payload,
                        headers={"x-oneapi-request-id": "request-42"},
                    )
                ) as provider:
                    with self.assertRaises(CcodeInvalidResponseError):
                        provider.generate([ModelMessage("user", "hello")], model="selected-model")

    def test_message_role_and_content_are_strictly_validated(self) -> None:
        invalid_messages = (
            ModelMessage(role="tool", content="hello"),
            ModelMessage(role=" user ", content="hello"),
            ModelMessage(role=None, content="hello"),  # type: ignore[arg-type]
            ModelMessage(role="user", content=""),
            ModelMessage(role="user", content="   "),
            ModelMessage(role="user", content=None),  # type: ignore[arg-type]
        )
        with self.provider(lambda _: self.fail("invalid messages must not send a request")) as provider:
            for message in invalid_messages:
                with self.subTest(message=message):
                    with self.assertRaises(ValueError):
                        provider.generate([message], model="selected-model")

    def test_model_is_required_per_request_and_never_defaulted(self) -> None:
        invalid_models = (None, "", "   ", " selected-model", "selected-model ", "m" * 201)
        with self.provider(lambda _: self.fail("invalid model must not send a request")) as provider:
            with self.assertRaises(TypeError):
                provider.generate([ModelMessage("user", "hello")])  # type: ignore[call-arg]
            for model in invalid_models:
                with self.subTest(model=model):
                    with self.assertRaises(ValueError):
                        provider.generate(
                            [ModelMessage("user", "hello")],
                            model=model,  # type: ignore[arg-type]
                        )

    def test_model_is_selected_independently_for_each_request(self) -> None:
        requested_models: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_model = json.loads(request.read())["model"]
            requested_models.append(requested_model)
            return httpx.Response(
                200,
                json={**response_payload(), "model": requested_model},
                headers={"x-oneapi-request-id": f"request-{len(requested_models)}"},
            )

        with self.provider(handler) as provider:
            first = provider.generate([ModelMessage("user", "hello")], model="model-a")
            second = provider.generate([ModelMessage("user", "hello")], model="model-b")

        self.assertEqual(requested_models, ["model-a", "model-b"])
        self.assertEqual((first.model, second.model), ("model-a", "model-b"))

    def test_logs_and_exception_text_do_not_leak_request_data(self) -> None:
        logger = logging.getLogger("backend.ccode_provider")
        with self.assertNoLogs(logger, level="DEBUG"):
            with self.provider(
                lambda _: httpx.Response(500, text="upstream included super-secret-api-key and private prompt")
            ) as provider:
                with self.assertRaises(CcodeUpstreamError) as raised:
                    provider.generate([ModelMessage("user", "private prompt")], model="selected-model")
        self.assertNotIn("super-secret-api-key", str(raised.exception))
        self.assertNotIn("private prompt", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
