"""Tests for the async boundary around the canonical model provider."""

import asyncio
import unittest

from backend.ccode_provider import CcodeInvalidResponseError, ModelResult

from .base import ProviderRequest
from .ccode import AsyncModelProviderAdapter
from .fake import FakeProvider


class RecordingModelProvider:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[object, str, object]] = []

    def generate(self, messages, *, model, metadata=None) -> ModelResult:
        self.calls.append((messages, model, metadata))
        return ModelResult(
            text=self.text,
            model=model,
            provider_request_id="provider-request-42",
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
            duration_ms=23,
        )


class AsyncModelProviderAdapterTests(unittest.TestCase):
    def request(self, **overrides) -> ProviderRequest:
        values = {
            "task": "activity_step_5",
            "messages": ({"role": "user", "content": "Generate a budget"},),
            "model": "selected-model",
            "request_id": "job-1",
            "metadata": {"activityId": "activity-1", "stepNo": "5"},
        }
        values.update(overrides)
        return ProviderRequest(**values)

    def test_adapter_passes_explicit_model_and_preserves_metadata(self) -> None:
        provider = RecordingModelProvider('{"total":1200}')
        result = asyncio.run(AsyncModelProviderAdapter(provider).generate_json(self.request()))

        self.assertEqual(provider.calls[0][1], "selected-model")
        self.assertEqual(provider.calls[0][2], {"activityId": "activity-1", "stepNo": "5"})
        self.assertEqual(result.data, {"total": 1200})
        self.assertEqual(result.model, "selected-model")
        self.assertEqual(result.provider_request_id, "provider-request-42")
        self.assertEqual(
            (
                result.usage.prompt_tokens,
                result.usage.completion_tokens,
                result.usage.total_tokens,
                result.duration_ms,
            ),
            (11, 7, 18, 23),
        )

    def test_model_is_required_and_has_no_default(self) -> None:
        with self.assertRaises(TypeError):
            ProviderRequest(task="activity_step_5", messages=())  # type: ignore[call-arg]
        for model in (None, "", "   ", " selected-model", "selected-model "):
            with self.subTest(model=model):
                with self.assertRaises(ValueError):
                    self.request(model=model)

    def test_json_parser_rejects_non_strict_or_schema_invalid_objects(self) -> None:
        cases = (
            ("", None),
            ('{"total":1200} {"total":1300}', None),
            ('{"total":null}', None),
            ('{"total":1200,"total":1300}', None),
            ('{"total":NaN}', None),
            (
                '{"total":1200,"unapproved":true}',
                {
                    "type": "object",
                    "required": ["total"],
                    "properties": {"total": {"type": "number"}},
                },
            ),
        )
        for text, schema in cases:
            with self.subTest(text=text):
                adapter = AsyncModelProviderAdapter(RecordingModelProvider(text))
                with self.assertRaises(CcodeInvalidResponseError):
                    asyncio.run(adapter.generate_json(self.request(response_schema=schema)))


class FakeProviderTests(unittest.TestCase):
    def test_fake_requires_an_explicit_task_fixture(self) -> None:
        provider = FakeProvider({})
        request = ProviderRequest(task="activity_step_5", messages=(), model="test-model")
        with self.assertRaises(KeyError):
            asyncio.run(provider.generate(request))


if __name__ == "__main__":
    unittest.main()
