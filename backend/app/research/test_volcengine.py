"""Contract tests for Volcengine Doubao Search Global integration."""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

import httpx

from .volcengine import (
    GLOBAL_SEARCH_ENDPOINT,
    SearchConfigurationError,
    SearchProviderError,
    SearchRequestError,
    VolcengineGlobalSearchProvider,
    VolcengineSearchSettings,
    build_scope_query,
)


def _success_body(request_id: str = "request-1") -> dict:
    return {
        "ResponseMetadata": {
            "RequestId": request_id,
            "Action": "",
            "Version": "",
            "Service": "",
            "Region": "",
        },
        "Result": {
            "TotalDocCount": 1,
            "Documents": [
                {
                    "Rank": 0,
                    "Url": "https://example.com/event",
                    "Title": "公开活动资料",
                    "Snippet": [{"Type": "text", "Text": "可核验的公开摘要"}],
                    "DocumentInfo": {
                        "ContentCharCount": 120,
                        "ContentTokenCount": 80,
                        "Filetype": "webpage",
                        "PublishTime": "2026-09-20",
                    },
                    "HostInfo": {
                        "Hostname": "示例站点",
                        "IconUrl": "",
                        "AuthorityLevel": "very_high",
                    },
                }
            ],
            "ErrorCode": 0,
            "ErrorMsg": "",
            "Choices": None,
            "Usage": None,
        },
    }


class VolcengineSearchSettingsTests(unittest.TestCase):
    def test_from_env_requires_server_only_key_and_rejects_invalid_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SearchConfigurationError, "VOLCENGINE_SEARCH_API_KEY"):
                VolcengineSearchSettings.from_env()

        with patch.dict(
            os.environ,
            {
                "VOLCENGINE_SEARCH_API_KEY": "secret",
                "VOLCENGINE_SEARCH_DOC_COUNT": "21",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(SearchConfigurationError, "DOC_COUNT"):
                VolcengineSearchSettings.from_env()

    def test_scope_query_is_explicit_and_never_silently_truncated(self) -> None:
        query = build_scope_query("北京文旅活动", "weather")
        self.assertEqual(query, "北京文旅活动 天气 气候 户外活动影响")
        self.assertLessEqual(len(query), 100)
        with self.assertRaises(SearchRequestError):
            build_scope_query("活动" * 50, "weather")


class VolcengineGlobalSearchProviderTests(unittest.TestCase):
    def test_posts_documented_web_payload_and_preserves_provenance(self) -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=_success_body(f"request-{len(requests)}"))

        async def scenario():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = VolcengineGlobalSearchProvider(
                    VolcengineSearchSettings(
                        api_key="server-secret",
                        timeout_seconds=5,
                        doc_count=5,
                        max_snippet_length=800,
                        icp_host_only=True,
                    ),
                    client=client,
                )
                return await provider.search("北京文旅活动", ("weather", "holiday"))

        items = asyncio.run(scenario())
        self.assertEqual(len(requests), 2)
        self.assertEqual({request.url for request in requests}, {httpx.URL(GLOBAL_SEARCH_ENDPOINT)})
        for request in requests:
            self.assertEqual(request.headers["authorization"], "Bearer server-secret")
            payload = __import__("json").loads(request.content)
            self.assertEqual(payload["SearchType"], "web")
            self.assertEqual(payload["DocCount"], 5)
            self.assertEqual(payload["MaxSnippetLength"], 800)
            self.assertEqual(payload["Filter"], {"IcpHostOnly": True})
            self.assertLessEqual(len(payload["Query"]), 100)

        self.assertEqual({item.scope for item in items}, {"weather", "holiday"})
        self.assertEqual(items[0].url, "https://example.com/event")
        self.assertEqual(items[0].site_name, "示例站点")
        self.assertEqual(items[0].authority_level, "very_high")
        self.assertEqual(items[0].published_at, "2026-09-20")
        self.assertEqual(items[0].rank, 0)
        self.assertTrue(items[0].provider_request_id.startswith("request-"))

    def test_rate_limit_is_returned_without_retry(self) -> None:
        calls = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                429,
                json={
                    "ResponseMetadata": {
                        "RequestId": "rate-request",
                        "Action": "",
                        "Version": "",
                        "Service": "",
                        "Region": "",
                        "Error": {"CodeN": 700429, "Code": "700429", "Message": "limited"},
                    },
                    "Result": None,
                },
            )

        async def scenario():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = VolcengineGlobalSearchProvider(
                    VolcengineSearchSettings(api_key="server-secret"),
                    client=client,
                )
                await provider.search("北京文旅活动", ("weather",))

        with self.assertRaises(SearchProviderError) as raised:
            asyncio.run(scenario())
        self.assertEqual(raised.exception.code, "SEARCH_RATE_LIMITED")
        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.provider_request_id, "rate-request")
        self.assertEqual(calls, 1)

    def test_unknown_response_field_is_rejected(self) -> None:
        body = _success_body()
        body["Result"]["Unexpected"] = True

        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        async def scenario():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = VolcengineGlobalSearchProvider(
                    VolcengineSearchSettings(api_key="server-secret"),
                    client=client,
                )
                await provider.search("北京文旅活动", ("public_trend",))

        with self.assertRaises(SearchProviderError) as raised:
            asyncio.run(scenario())
        self.assertEqual(raised.exception.code, "SEARCH_INVALID_RESPONSE")

    def test_documented_nullable_result_fields_reject_non_null_values(self) -> None:
        for field in ("Choices", "Usage"):
            with self.subTest(field=field):
                body = _success_body()
                body["Result"][field] = {}

                async def handler(_: httpx.Request) -> httpx.Response:
                    return httpx.Response(200, json=body)

                async def scenario():
                    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                        provider = VolcengineGlobalSearchProvider(
                            VolcengineSearchSettings(api_key="server-secret"),
                            client=client,
                        )
                        await provider.search("北京文旅活动", ("public_trend",))

                with self.assertRaises(SearchProviderError) as raised:
                    asyncio.run(scenario())
                self.assertEqual(raised.exception.code, "SEARCH_INVALID_RESPONSE")

    def test_non_empty_icon_url_must_be_http_url(self) -> None:
        body = _success_body()
        body["Result"]["Documents"][0]["HostInfo"]["IconUrl"] = "not-a-url"

        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        async def scenario():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                provider = VolcengineGlobalSearchProvider(
                    VolcengineSearchSettings(api_key="server-secret"),
                    client=client,
                )
                await provider.search("北京文旅活动", ("public_trend",))

        with self.assertRaises(SearchProviderError) as raised:
            asyncio.run(scenario())
        self.assertEqual(raised.exception.code, "SEARCH_INVALID_RESPONSE")


if __name__ == "__main__":
    unittest.main()
