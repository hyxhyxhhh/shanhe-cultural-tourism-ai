"""Thin async adapter for the canonical ``backend.ccode_provider`` contract."""

import asyncio

from backend.ccode_provider import CcodeModelProvider, ModelMessage, ModelProvider

from .base import (
    ProviderJsonResult,
    ProviderRequest,
    ProviderResult,
    ProviderUsage,
    parse_json_object,
)


class AsyncModelProviderAdapter:
    """Run a synchronous ``ModelProvider`` without blocking the event loop."""

    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    @classmethod
    def from_env(cls) -> "AsyncModelProviderAdapter":
        return cls(CcodeModelProvider.from_env())

    async def generate(self, request: ProviderRequest) -> ProviderResult:
        messages = tuple(
            ModelMessage(role=message["role"], content=message["content"])
            for message in request.messages
        )
        result = await asyncio.to_thread(
            self._provider.generate,
            messages,
            model=request.model,
            metadata=request.metadata,
        )
        return ProviderResult(
            content=result.text,
            model=result.model,
            provider_request_id=result.provider_request_id,
            usage=ProviderUsage(
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            ),
            duration_ms=result.duration_ms,
        )

    async def generate_json(self, request: ProviderRequest) -> ProviderJsonResult:
        return parse_json_object(await self.generate(request), request.response_schema)
