"""Volcengine Doubao Search Global web-search provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Mapping, Sequence

import httpx

from .service import PublicSearchProvider, ResearchScope, SearchItem


GLOBAL_SEARCH_ENDPOINT = "https://open.feedcoopapi.com/search_api/global_search"
_AUTHORITY_LEVELS = frozenset({"very_high", "high", "normal"})
_SCOPE_SUFFIXES: Mapping[ResearchScope, str] = {
    "weather": "天气 气候 户外活动影响",
    "holiday": "节假日安排 客流 出行",
    "similar_events": "类似文旅活动 案例 成效",
    "public_trend": "文旅消费趋势 舆情 热点",
}
_GLOBAL_REQUEST_LIMIT = asyncio.Semaphore(10)


class SearchProviderError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.provider_request_id = provider_request_id


class SearchConfigurationError(SearchProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("SEARCH_CONFIGURATION_ERROR", message, status_code=503)


class SearchRequestError(SearchProviderError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_SEARCH_REQUEST", message, status_code=422)


class SearchInvalidResponseError(SearchProviderError):
    def __init__(self, provider_request_id: str | None = None) -> None:
        super().__init__(
            "SEARCH_INVALID_RESPONSE",
            "联网搜索服务返回了无效响应",
            status_code=502,
            provider_request_id=provider_request_id,
        )


@dataclass(frozen=True, slots=True)
class VolcengineSearchSettings:
    api_key: str
    timeout_seconds: float = 15.0
    doc_count: int = 10
    max_snippet_length: int = 1000
    icp_host_only: bool = False

    @classmethod
    def from_env(cls) -> "VolcengineSearchSettings":
        api_key = os.environ.get("VOLCENGINE_SEARCH_API_KEY")
        if api_key is None or not api_key:
            raise SearchConfigurationError("VOLCENGINE_SEARCH_API_KEY 未配置")
        if api_key != api_key.strip():
            raise SearchConfigurationError("VOLCENGINE_SEARCH_API_KEY 不能包含首尾空白")

        timeout_seconds = _env_float("VOLCENGINE_SEARCH_TIMEOUT_SECONDS", 15.0, 1.0, 60.0)
        doc_count = _env_int("VOLCENGINE_SEARCH_DOC_COUNT", 10, 1, 20)
        max_snippet_length = _env_int(
            "VOLCENGINE_SEARCH_MAX_SNIPPET_LENGTH",
            1000,
            1,
            3000,
        )
        icp_host_only = _env_bool("VOLCENGINE_SEARCH_ICP_HOST_ONLY", False)
        return cls(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            doc_count=doc_count,
            max_snippet_length=max_snippet_length,
            icp_host_only=icp_host_only,
        )


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw != raw.strip() or not raw.isascii() or not raw.isdecimal():
        raise SearchConfigurationError(f"{name} 必须是 {minimum} 到 {maximum} 的整数")
    value = int(raw)
    if value < minimum or value > maximum:
        raise SearchConfigurationError(f"{name} 必须是 {minimum} 到 {maximum} 的整数")
    return value


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw != raw.strip():
        raise SearchConfigurationError(f"{name} 必须是 {minimum:g} 到 {maximum:g} 的数字")
    try:
        value = float(raw)
    except ValueError as exc:
        raise SearchConfigurationError(f"{name} 必须是 {minimum:g} 到 {maximum:g} 的数字") from exc
    if not minimum <= value <= maximum:
        raise SearchConfigurationError(f"{name} 必须是 {minimum:g} 到 {maximum:g} 的数字")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise SearchConfigurationError(f"{name} 必须是 true 或 false")


class VolcengineGlobalSearchProvider(PublicSearchProvider):
    """Calls the documented Global API once per requested research scope."""

    def __init__(
        self,
        settings: VolcengineSearchSettings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client

    @classmethod
    def from_env(cls) -> "VolcengineGlobalSearchProvider":
        return cls(VolcengineSearchSettings.from_env())

    async def search(
        self,
        query: str,
        scopes: Sequence[ResearchScope],
    ) -> Sequence[SearchItem]:
        scoped_queries = tuple((scope, build_scope_query(query, scope)) for scope in scopes)
        if self._client is not None:
            results = await asyncio.gather(
                *(self._search_scope(self._client, scope, scoped_query) for scope, scoped_query in scoped_queries)
            )
        else:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                results = await asyncio.gather(
                    *(self._search_scope(client, scope, scoped_query) for scope, scoped_query in scoped_queries)
                )
        return tuple(item for result in results for item in result)

    async def _search_scope(
        self,
        client: httpx.AsyncClient,
        scope: ResearchScope,
        query: str,
    ) -> tuple[SearchItem, ...]:
        payload = {
            "SearchType": "web",
            "Query": query,
            "DocCount": self.settings.doc_count,
            "MaxSnippetLength": self.settings.max_snippet_length,
            "Filter": {"IcpHostOnly": self.settings.icp_host_only},
        }
        try:
            async with _GLOBAL_REQUEST_LIMIT:
                response = await client.post(
                    GLOBAL_SEARCH_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.settings.timeout_seconds,
                )
        except httpx.TimeoutException as exc:
            raise SearchProviderError(
                "SEARCH_TIMEOUT",
                "联网搜索请求超时",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise SearchProviderError(
                "SEARCH_UNAVAILABLE",
                "无法连接联网搜索服务",
                status_code=502,
            ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise SearchInvalidResponseError() from exc
        if not isinstance(body, dict):
            raise SearchInvalidResponseError()
        if response.status_code >= 400:
            raise _provider_error(body, http_status=response.status_code)
        return _parse_success(body, scope=scope, captured_at=datetime.now(timezone.utc))


def build_scope_query(query: str, scope: ResearchScope) -> str:
    if not isinstance(query, str) or not query or query != query.strip():
        raise SearchRequestError("联网搜索 query 必须是非空且不含首尾空白的字符串")
    suffix = _SCOPE_SUFFIXES.get(scope)
    if suffix is None:
        raise SearchRequestError(f"不支持的联网搜索范围：{scope}")
    scoped_query = f"{query} {suffix}"
    if len(scoped_query) > 100:
        raise SearchRequestError("联网搜索 query 与范围组合后不能超过 100 个字符")
    return scoped_query


def _provider_error(body: Mapping[str, Any], *, http_status: int) -> SearchProviderError:
    request_id, code, _ = _parse_error_metadata(body)
    if http_status == 429 or code == "700429":
        return SearchProviderError(
            "SEARCH_RATE_LIMITED",
            "联网搜索请求超过频率限制",
            status_code=429,
            provider_request_id=request_id,
        )
    if code in {"10403", "700901"} or http_status in {401, 403}:
        return SearchProviderError(
            "SEARCH_AUTHENTICATION_FAILED",
            "联网搜索服务鉴权失败",
            status_code=502,
            provider_request_id=request_id,
        )
    return SearchProviderError(
        "SEARCH_UPSTREAM_ERROR",
        "联网搜索服务请求失败",
        status_code=502,
        provider_request_id=request_id,
    )


def _parse_success(
    body: Mapping[str, Any],
    *,
    scope: ResearchScope,
    captured_at: datetime,
) -> tuple[SearchItem, ...]:
    _exact_fields(body, {"ResponseMetadata", "Result"})
    metadata = _object(_required(body, "ResponseMetadata"))
    _exact_fields(metadata, {"RequestId", "Action", "Version", "Service", "Region", "Error"})
    request_id = _non_empty_string(_required(metadata, "RequestId"))
    for key in ("Action", "Version", "Service", "Region"):
        _string(_required(metadata, key))
    if "Error" in metadata:
        raise _provider_error(body, http_status=200)

    result = _object(_required(body, "Result"))
    _exact_fields(
        result,
        {"TotalDocCount", "Documents", "ErrorCode", "ErrorMsg", "Choices", "Usage"},
    )
    for nullable_field in ("Choices", "Usage"):
        if nullable_field in result and result[nullable_field] is not None:
            raise SearchInvalidResponseError(request_id)
    _non_negative_int(_required(result, "TotalDocCount"))
    error_code = _int(_required(result, "ErrorCode"))
    _string(_required(result, "ErrorMsg"))
    if error_code != 0:
        raise _provider_error(body, http_status=200)
    documents = _required(result, "Documents")
    if not isinstance(documents, list):
        raise SearchInvalidResponseError(request_id)

    items = tuple(
        _parse_document(document, scope=scope, request_id=request_id, captured_at=captured_at)
        for document in documents
    )
    if not items:
        raise SearchProviderError(
            "SEARCH_NO_RESULTS",
            "联网搜索没有返回结果",
            status_code=404,
            provider_request_id=request_id,
        )
    return items


def _parse_document(
    value: Any,
    *,
    scope: ResearchScope,
    request_id: str,
    captured_at: datetime,
) -> SearchItem:
    document = _object(value)
    _exact_fields(document, {"Rank", "Url", "Title", "Snippet", "DocumentInfo", "HostInfo"})
    rank = _non_negative_int(_required(document, "Rank"))
    url = _http_url(_required(document, "Url"))
    title = _non_empty_string(_required(document, "Title"))
    snippets = _required(document, "Snippet")
    if not isinstance(snippets, list):
        raise SearchInvalidResponseError(request_id)
    text_parts: list[str] = []
    for snippet_value in snippets:
        snippet = _object(snippet_value)
        _exact_fields(snippet, {"Type", "Text", "Image"})
        snippet_type = _string(_required(snippet, "Type"))
        if snippet_type == "text":
            text_parts.append(_non_empty_string(_required(snippet, "Text")))
        elif snippet_type == "image":
            _parse_image(_required(snippet, "Image"), request_id)
        else:
            raise SearchInvalidResponseError(request_id)
    if not text_parts:
        raise SearchInvalidResponseError(request_id)

    published_at: str | None = None
    if "DocumentInfo" in document:
        info = _object(document["DocumentInfo"])
        _exact_fields(info, {"ContentCharCount", "ContentTokenCount", "Filetype", "PublishTime"})
        for key in ("ContentCharCount", "ContentTokenCount"):
            if key in info:
                _non_negative_int(info[key])
        if "Filetype" in info:
            _string(info["Filetype"])
        if "PublishTime" in info:
            raw_published_at = _string(info["PublishTime"])
            published_at = raw_published_at or None

    site_name: str | None = None
    authority_level: str | None = None
    if "HostInfo" in document:
        host = _object(document["HostInfo"])
        _exact_fields(host, {"Hostname", "IconUrl", "AuthorityLevel"})
        if "Hostname" in host:
            raw_site_name = _string(host["Hostname"])
            site_name = raw_site_name or None
        if "IconUrl" in host:
            icon_url = _string(host["IconUrl"])
            if icon_url:
                _http_url(icon_url)
        if "AuthorityLevel" in host:
            raw_authority = _string(host["AuthorityLevel"])
            if raw_authority not in _AUTHORITY_LEVELS:
                raise SearchInvalidResponseError(request_id)
            authority_level = raw_authority

    return SearchItem(
        label=title,
        summary="\n".join(text_parts),
        url=url,
        captured_at=captured_at,
        published_at=published_at,
        site_name=site_name,
        authority_level=authority_level,
        rank=rank,
        provider_request_id=request_id,
        scope=scope,
    )


def _parse_image(value: Any, request_id: str) -> None:
    image = _object(value)
    _exact_fields(image, {"Width", "Height", "ImageUrl", "Alt", "ThumbnailUrl"})
    for key in ("Width", "Height"):
        if key in image:
            _non_negative_int(image[key])
    if "ImageUrl" in image:
        _http_url(image["ImageUrl"])
    if "Alt" in image:
        _string(image["Alt"])
    if "ThumbnailUrl" in image:
        thumbnails = _object(image["ThumbnailUrl"])
        _exact_fields(thumbnails, {"Tiny", "Small", "Medium", "Large"})
        for value in thumbnails.values():
            _http_url(value)


def _parse_error_metadata(body: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    metadata = body.get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return None, None, None
    request_id = metadata.get("RequestId") if isinstance(metadata.get("RequestId"), str) else None
    error = metadata.get("Error")
    if not isinstance(error, dict):
        result = body.get("Result")
        if isinstance(result, dict):
            code = result.get("ErrorCode")
            message = result.get("ErrorMsg")
            return request_id, str(code) if isinstance(code, int) else None, message if isinstance(message, str) else None
        return request_id, None, None
    code_value = error.get("Code")
    code = code_value if isinstance(code_value, str) else None
    message_value = error.get("Message")
    message = message_value if isinstance(message_value, str) else None
    return request_id, code, message


def _required(value: Mapping[str, Any], key: str) -> Any:
    if key not in value or value[key] is None:
        raise SearchInvalidResponseError()
    return value[key]


def _exact_fields(value: Mapping[str, Any], allowed: set[str]) -> None:
    if set(value) - allowed:
        raise SearchInvalidResponseError()


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SearchInvalidResponseError()
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise SearchInvalidResponseError()
    return value


def _non_empty_string(value: Any) -> str:
    result = _string(value)
    if not result.strip():
        raise SearchInvalidResponseError()
    return result


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SearchInvalidResponseError()
    return value


def _non_negative_int(value: Any) -> int:
    result = _int(value)
    if result < 0:
        raise SearchInvalidResponseError()
    return result


def _http_url(value: Any) -> str:
    result = _non_empty_string(value)
    try:
        url = httpx.URL(result)
    except ValueError as exc:
        raise SearchInvalidResponseError() from exc
    if url.scheme not in {"http", "https"} or not url.host:
        raise SearchInvalidResponseError()
    return result
