"""Async application boundary for the canonical synchronous model provider."""

from dataclasses import dataclass, field
from enum import StrEnum
import json
from typing import Any, Mapping, Protocol, Sequence

from backend.ccode_provider import CcodeInvalidResponseError


class ProviderCapability(StrEnum):
    """Describes a business use without selecting a model for it."""

    GENERAL_GENERATION = "general_generation"
    STRUCTURED_EXTRACTION = "structured_extraction"
    LONG_CONTEXT_REVIEW = "long_context_review"


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    """A model request with an explicit model selected by the caller."""

    task: str
    messages: Sequence[Mapping[str, str]]
    model: str
    response_schema: Mapping[str, Any] | None = None
    request_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task, str) or not self.task.strip():
            raise ValueError("task must be a non-empty string")
        if (
            not isinstance(self.model, str)
            or not self.model.strip()
            or self.model != self.model.strip()
            or len(self.model) > 200
        ):
            raise ValueError("model must be explicitly provided without surrounding whitespace")


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class ProviderResult:
    content: str
    model: str
    provider_request_id: str
    usage: ProviderUsage
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ProviderJsonResult:
    data: dict[str, Any]
    model: str
    provider_request_id: str
    usage: ProviderUsage
    duration_ms: int


class Provider(Protocol):
    async def generate(self, request: ProviderRequest) -> ProviderResult:
        """Generate text through the injected canonical model provider."""
        ...

    async def generate_json(self, request: ProviderRequest) -> ProviderJsonResult:
        """Generate one strictly validated JSON object and preserve metadata."""
        ...


def parse_json_object(
    result: ProviderResult,
    schema: Mapping[str, Any] | None,
) -> ProviderJsonResult:
    """Parse exactly one JSON object, rejecting nulls and schema drift."""

    try:
        value = json.loads(
            result.content,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise CcodeInvalidResponseError(request_id=result.provider_request_id) from exc
    if not isinstance(value, dict):
        raise CcodeInvalidResponseError(request_id=result.provider_request_id)
    error = _json_schema_error(value, schema, path="$", reject_null=True)
    if error is not None:
        raise CcodeInvalidResponseError(request_id=result.provider_request_id)
    return ProviderJsonResult(
        data=value,
        model=result.model,
        provider_request_id=result.provider_request_id,
        usage=result.usage,
        duration_ms=result.duration_ms,
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for name, child in pairs:
        if name in value:
            raise ValueError("duplicate JSON object key")
        value[name] = child
    return value


def _reject_json_constant(_: str) -> Any:
    raise ValueError("non-standard JSON numeric constant")


def _json_schema_error(
    value: Any,
    schema: Mapping[str, Any] | None,
    *,
    path: str,
    reject_null: bool,
) -> str | None:
    if value is None and reject_null:
        return f"{path} must not be null"

    if schema is None:
        if isinstance(value, dict):
            for name, child in value.items():
                error = _json_schema_error(child, None, path=f"{path}.{name}", reject_null=reject_null)
                if error:
                    return error
        elif isinstance(value, list):
            for index, child in enumerate(value):
                error = _json_schema_error(child, None, path=f"{path}[{index}]", reject_null=reject_null)
                if error:
                    return error
        return None

    expected_type = schema.get("type")
    if expected_type == "object" and not isinstance(value, dict):
        return f"{path} must be an object"
    if expected_type == "array" and not isinstance(value, list):
        return f"{path} must be an array"
    if expected_type == "string" and not isinstance(value, str):
        return f"{path} must be a string"
    if expected_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return f"{path} must be a number"
    if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return f"{path} must be an integer"
    if expected_type == "boolean" and not isinstance(value, bool):
        return f"{path} must be a boolean"

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            return f"{path} schema properties must be an object"
        unknown = sorted(set(value) - set(properties))
        if unknown:
            return f"{path} contains unknown fields: {','.join(unknown)}"
        required = schema.get("required", ())
        if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
            return f"{path} schema required must be an array"
        missing = [str(name) for name in required if name not in value]
        if missing:
            return f"{path} is missing required fields: {','.join(missing)}"
        for name, child in value.items():
            child_schema = properties[name]
            if not isinstance(child_schema, Mapping):
                return f"{path}.{name} schema must be an object"
            error = _json_schema_error(
                child,
                child_schema,
                path=f"{path}.{name}",
                reject_null=reject_null,
            )
            if error:
                return error
    elif isinstance(value, list):
        item_schema = schema.get("items")
        if not isinstance(item_schema, Mapping):
            return f"{path} schema items must be an object"
        for index, child in enumerate(value):
            error = _json_schema_error(
                child,
                item_schema,
                path=f"{path}[{index}]",
                reject_null=reject_null,
            )
            if error:
                return error
    return None
