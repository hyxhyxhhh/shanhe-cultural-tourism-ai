"""Deterministic Provider for explicitly injected tests."""

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .base import ProviderJsonResult, ProviderRequest, ProviderResult, ProviderUsage, parse_json_object


class FakeProvider:
    """A deterministic provider that never performs network calls."""

    def __init__(
        self,
        responses: Mapping[str, Any],
    ) -> None:
        self.responses = dict(responses)
        self.requests: list[ProviderRequest] = []

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        self.requests.append(request)
        value = self._value_for(request)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict):
            content = json.dumps(value, ensure_ascii=False)
        else:
            content = str(value)
        return ProviderResult(
            content=content,
            model=request.model,
            provider_request_id=request.request_id or f"fake-{request.task}",
            usage=ProviderUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            duration_ms=0,
        )

    async def generate_json(self, request: ProviderRequest) -> ProviderJsonResult:
        return parse_json_object(await self.generate(request), request.response_schema)

    def _value_for(self, request: ProviderRequest) -> Any:
        if request.task not in self.responses:
            raise KeyError(f"No fake response configured for task {request.task}")
        value = self.responses[request.task]
        return deepcopy(value)
