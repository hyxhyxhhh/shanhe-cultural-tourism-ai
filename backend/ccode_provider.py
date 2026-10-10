from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence, TypeAlias
from urllib.parse import urlsplit, urlunsplit

import httpx


TaskMetadataValue: TypeAlias = str | int | float | bool | None
TaskMetadata: TypeAlias = Mapping[str, TaskMetadataValue]


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelResult:
    text: str
    model: str
    provider_request_id: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int


class ModelProvider(Protocol):
    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        model: str,
        metadata: TaskMetadata | None = None,
    ) -> ModelResult: ...


class CcodeProviderError(RuntimeError):
    """Base exception with a safe, user-visible message."""

    error_code = "CCODE_ERROR"
    public_message = "The text generation service could not complete the request."

    def __init__(
        self,
        *,
        request_id: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(self.public_message)
        self.request_id = request_id
        self.status_code = status_code


class CcodeConfigurationError(CcodeProviderError):
    error_code = "CCODE_NOT_CONFIGURED"
    public_message = "The text generation service is not configured."


class CcodeAuthenticationError(CcodeProviderError):
    error_code = "CCODE_AUTHENTICATION_FAILED"
    public_message = "The text generation service rejected its credentials or permissions."


class CcodeBalanceError(CcodeProviderError):
    error_code = "CCODE_BALANCE_INSUFFICIENT"
    public_message = "The text generation service has insufficient balance or quota."


class CcodeRateLimitError(CcodeProviderError):
    error_code = "CCODE_RATE_LIMITED"
    public_message = "The text generation service is temporarily rate limited."


class CcodeModelUnavailableError(CcodeProviderError):
    error_code = "CCODE_MODEL_UNAVAILABLE"
    public_message = "The configured text generation model is unavailable."


class CcodeTimeoutError(CcodeProviderError):
    error_code = "CCODE_TIMEOUT"
    public_message = "The text generation service timed out."


class CcodeNetworkError(CcodeProviderError):
    error_code = "CCODE_NETWORK_ERROR"
    public_message = "The text generation service could not be reached."


class CcodeUpstreamError(CcodeProviderError):
    error_code = "CCODE_UPSTREAM_ERROR"
    public_message = "The text generation service is temporarily unavailable."


class CcodeRequestRejectedError(CcodeProviderError):
    error_code = "CCODE_REQUEST_REJECTED"
    public_message = "The text generation service rejected the request."


class CcodeInvalidResponseError(CcodeProviderError):
    error_code = "CCODE_INVALID_RESPONSE"
    public_message = "The text generation service returned an invalid response."


_DEFAULT_BASE_URL = "https://api.ccode.vip"
_DEFAULT_TIMEOUT_SECONDS = 90.0
_MIN_TIMEOUT_SECONDS = 1.0
_MAX_TIMEOUT_SECONDS = 600.0
_DEFAULT_MAX_OUTPUT_TOKENS = 4096
_MIN_MAX_OUTPUT_TOKENS = 256
_MAX_MAX_OUTPUT_TOKENS = 16384
_MAX_MODEL_LENGTH = 200
_REQUEST_ID_HEADER = "x-oneapi-request-id"
_ALLOWED_MESSAGE_ROLES = frozenset({"system", "user", "assistant"})


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise CcodeConfigurationError()
    return value


def _timeout_from_environment() -> float:
    raw_value = os.environ.get("CCODE_REQUEST_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise CcodeConfigurationError() from exc
    if not _MIN_TIMEOUT_SECONDS <= timeout <= _MAX_TIMEOUT_SECONDS:
        raise CcodeConfigurationError()
    return timeout


def _max_output_tokens_from_environment() -> int:
    raw_value = os.environ.get("CCODE_MAX_OUTPUT_TOKENS", str(_DEFAULT_MAX_OUTPUT_TOKENS)).strip()
    try:
        max_output_tokens = int(raw_value)
    except ValueError as exc:
        raise CcodeConfigurationError() from exc
    if not _MIN_MAX_OUTPUT_TOKENS <= max_output_tokens <= _MAX_MAX_OUTPUT_TOKENS:
        raise CcodeConfigurationError()
    return max_output_tokens


def normalize_chat_completions_url(base_url: str) -> str:
    raw_url = base_url.strip().rstrip("/")
    if not raw_url:
        raise CcodeConfigurationError()
    parsed = urlsplit(raw_url)
    if parsed.scheme != "https" or parsed.netloc != "api.ccode.vip":
        raise CcodeConfigurationError()
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CcodeConfigurationError()

    path = parsed.path.rstrip("/")
    if path not in {"", "/v1"}:
        raise CcodeConfigurationError()
    path = "/v1/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _request_id(response: httpx.Response, *, required: bool) -> str | None:
    value = response.headers.get(_REQUEST_ID_HEADER)
    if value is None:
        if required:
            raise CcodeInvalidResponseError(status_code=response.status_code)
        return None

    request_id = value.strip()
    if not request_id or len(request_id) > 200 or not all(character.isprintable() for character in request_id):
        if required:
            raise CcodeInvalidResponseError(status_code=response.status_code)
        return None
    return request_id


def _raise_for_error_response(response: httpx.Response) -> None:
    status_code = response.status_code
    request_id = _request_id(response, required=False)
    details = {"request_id": request_id, "status_code": status_code}

    if status_code == 402:
        raise CcodeBalanceError(**details)
    if status_code in (401, 403):
        raise CcodeAuthenticationError(**details)
    if status_code == 404:
        raise CcodeModelUnavailableError(**details)
    if status_code == 429:
        raise CcodeRateLimitError(**details)
    if status_code >= 500:
        raise CcodeUpstreamError(**details)
    raise CcodeRequestRejectedError(**details)


def _required_token_count(usage: object, name: str) -> int:
    if not isinstance(usage, dict) or name not in usage:
        raise CcodeInvalidResponseError()
    value = usage[name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CcodeInvalidResponseError()
    return value


def _response_text(content: object) -> str:
    if not isinstance(content, str) or not content.strip():
        raise CcodeInvalidResponseError()
    return content


class CcodeModelProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = _DEFAULT_BASE_URL,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        clean_api_key = api_key.strip()
        if not clean_api_key:
            raise CcodeConfigurationError()
        if not _MIN_TIMEOUT_SECONDS <= timeout_seconds <= _MAX_TIMEOUT_SECONDS:
            raise CcodeConfigurationError()
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not _MIN_MAX_OUTPUT_TOKENS <= max_output_tokens <= _MAX_MAX_OUTPUT_TOKENS
        ):
            raise CcodeConfigurationError()

        self._api_key = clean_api_key
        self._max_output_tokens = max_output_tokens
        self._endpoint = normalize_chat_completions_url(base_url)
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
            trust_env=False,
        )

    @classmethod
    def from_env(cls, *, transport: httpx.BaseTransport | None = None) -> CcodeModelProvider:
        return cls(
            api_key=_required_environment("CCODE_API_KEY"),
            base_url=os.environ.get("CCODE_API_BASE_URL", _DEFAULT_BASE_URL),
            timeout_seconds=_timeout_from_environment(),
            max_output_tokens=_max_output_tokens_from_environment(),
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CcodeModelProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        model: str,
        metadata: TaskMetadata | None = None,
    ) -> ModelResult:
        del metadata  # Reserved for caller-side tracing; never sent as prompt content.
        if (
            not isinstance(model, str)
            or not model.strip()
            or model != model.strip()
            or len(model) > _MAX_MODEL_LENGTH
        ):
            raise ValueError("model must be a non-empty string of at most 200 characters without surrounding whitespace")
        if not messages:
            raise ValueError("messages must not be empty")
        request_messages: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message.role, str) or message.role not in _ALLOWED_MESSAGE_ROLES:
                raise ValueError("each message role must be system, user, or assistant")
            if not isinstance(message.content, str) or not message.content.strip():
                raise ValueError("each message content must be a non-empty string")
            request_messages.append({"role": message.role, "content": message.content})

        started_at = time.perf_counter()
        try:
            response = self._client.post(
                self._endpoint,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": request_messages,
                    "max_tokens": self._max_output_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
        except httpx.TimeoutException as exc:
            raise CcodeTimeoutError() from exc
        except httpx.RequestError as exc:
            raise CcodeNetworkError() from exc
        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))

        if not response.is_success:
            _raise_for_error_response(response)
        request_id = _request_id(response, required=True)
        try:
            payload = response.json()
        except ValueError as exc:
            raise CcodeInvalidResponseError(request_id=request_id, status_code=response.status_code) from exc
        try:
            if not isinstance(payload, dict):
                raise TypeError
            model = payload["model"]
            choices = payload["choices"]
            if not isinstance(model, str) or not model.strip() or not isinstance(choices, list) or not choices:
                raise TypeError
            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise TypeError
            message = first_choice["message"]
            if not isinstance(message, dict) or "content" not in message:
                raise TypeError
            text = _response_text(message["content"])
            usage = payload["usage"]
            prompt_tokens = _required_token_count(usage, "prompt_tokens")
            completion_tokens = _required_token_count(usage, "completion_tokens")
            total_tokens = _required_token_count(usage, "total_tokens")
        except (KeyError, TypeError, CcodeInvalidResponseError) as exc:
            raise CcodeInvalidResponseError(
                request_id=request_id,
                status_code=response.status_code,
            ) from exc

        return ModelResult(
            text=text,
            model=model,
            provider_request_id=request_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )
