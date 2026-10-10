from copy import deepcopy
from datetime import datetime, timezone
import asyncio
import json
import threading
from types import SimpleNamespace
import unittest
from uuid import UUID, uuid4

from pydantic import ValidationError
import anyio
from sqlalchemy import select

from backend.activity_api import stream_research_generation
from backend.auth import require_session
from backend.activity_steps import StepDomainError
from backend.ccode_provider import ModelResult, CcodeTimeoutError
from backend.models import ActivityStep, ModelRun, SourceReference
from backend.research_generation import ScopeProgress, SCOPE_NAMES, citation_candidates, progress_snapshot
import backend.test_activity_steps as activity_tests


class ScopedProvider:
    def __init__(self):
        self.calls = []
        self.fail_scope = None
        self.cross_scope = None
        self.on_call = None
        self.large_summary = False

    def generate(self, messages, *, model, metadata):
        self.calls.append((messages, metadata))
        context = json.loads(messages[1].content.split("\n", 1)[1])
        scope = metadata["research_scope"]
        if self.on_call:
            self.on_call(scope)
        if scope == self.fail_scope:
            raise CcodeTimeoutError()
        source = deepcopy(context["publicSearchEvidence"][-1])
        source["excerpt"] = context["publicCitationCandidates"][-1]["excerpts"][0]
        if self.cross_scope:
            source["scope"] = self.cross_scope
        output = {"summary": f"{SCOPE_NAMES[scope]}资料支持当前活动安排。", "findings": [f"{SCOPE_NAMES[scope]}形成可执行建议。", "共同事项需要运营方核实。"],
                  "risks": ["运营细节待核实。"], "sources": [{"sourceType": "public", **source}]}
        if self.large_summary:
            output["summary"] = SCOPE_NAMES[scope] + "长" * 3000
        return ModelResult(text=json.dumps(output), model=model, provider_request_id=f"provider-{scope}",
                           prompt_tokens=100, completion_tokens=20, total_tokens=120, duration_ms=25)


class ResearchScopeGenerationTests(unittest.TestCase):
    tracked_models = activity_tests.ActivityStepApiIntegrationTests.tracked_models
    setUp = activity_tests.ActivityStepApiIntegrationTests.setUp
    tearDown = activity_tests.ActivityStepApiIntegrationTests.tearDown
    _create_activity = activity_tests.ActivityStepApiIntegrationTests._create_activity
    _save_output = activity_tests.ActivityStepApiIntegrationTests._save_output
    _confirm = activity_tests.ActivityStepApiIntegrationTests._confirm

    @classmethod
    def setUpClass(cls):
        activity_tests.ActivityStepApiIntegrationTests.setUpClass.__func__(cls)

    def _prepare(self, scopes):
        activity_id = self._create_activity()["id"]
        brief = self._save_output(activity_id, 1, 1)
        self._confirm(activity_id, 1, brief["version"])
        enabled = self.client.patch(f"/api/activities/{activity_id}/steps/2", json={"version": 2, "inputJson": {"useWebSearch": True}})
        self.assertEqual(enabled.status_code, 200)
        for scope in scopes:
            for rank in range(10):
                self.db.add(SourceReference(id=uuid4(), activity_id=UUID(activity_id), step_no=2, source_type="public",
                                           label=f"{SCOPE_NAMES[scope]}原始资料{rank}", url=f"https://example.com/{scope}/{rank}",
                                           captured_at=datetime(2026, 9, 24, tzinfo=timezone.utc), excerpt=f"{SCOPE_NAMES[scope]}完整原始检索摘要{rank}。" * 400,
                                           scope=scope, rank=rank, provider_request_id=f"search-{scope}", site_name="原始站点", authority_level="high"))
        self.db.commit()
        provider = ScopedProvider()
        from backend.activity_api import get_model_provider
        self.client.app.dependency_overrides[get_model_provider] = lambda: provider
        return activity_id, enabled.json()["version"], provider

    def _stream(self, activity_id, version):
        response = self.client.post(f"/api/activities/{activity_id}/research/generate/stream", json={"version": version, "model": "selected-model"})
        self.assertEqual(response.status_code, 200, response.text)
        events = []
        for frame in response.text.split("\n\n"):
            if frame:
                name, data = frame.split("\n", 1)
                events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
        return events

    def test_one_two_four_scopes_make_exactly_one_complete_model_call_per_scope(self):
        for scopes in (["weather"], ["weather", "holiday"], ["weather", "holiday", "similar_events", "public_trend"]):
            with self.subTest(scopes=scopes):
                activity_id, version, provider = self._prepare(scopes)
                provider.on_call = lambda _scope: self.assertFalse(self.db.in_transaction())
                events = self._stream(activity_id, version)
                self.assertEqual(len(provider.calls), len(scopes))
                for (messages, metadata), scope in zip(provider.calls, scopes):
                    context = json.loads(messages[1].content.split("\n", 1)[1])
                    self.assertEqual(metadata["research_scope"], scope)
                    self.assertEqual(len(context["publicSearchEvidence"]), 10)
                    self.assertEqual({item["scope"] for item in context["publicSearchEvidence"]}, {scope})
                    self.assertTrue(all(len(item["excerpt"]) > 3000 for item in context["publicSearchEvidence"]))
                    self.assertEqual(len(context["publicCitationCandidates"]), 10)
                    for source, candidate in zip(context["publicSearchEvidence"], context["publicCitationCandidates"]):
                        self.assertEqual("".join(candidate["excerpts"]), source["excerpt"])
                        self.assertTrue(all(0 < len(quote) <= 80 and quote in source["excerpt"] for quote in candidate["excerpts"]))
                        self.assertEqual({key: candidate[key] for key in ("rank", "scope", "url", "providerRequestId")},
                                         {key: source[key] for key in ("rank", "scope", "url", "providerRequestId")})
                    self.assertNotIn("6-10 distinct findings", messages[0].content)
                    self.assertNotIn("4-6 directly supporting citations", messages[0].content)
                self.assertEqual(events[-1][0], "research_completed")
                result = events[-1][1]
                self.assertEqual(result["completedScopes"], len(scopes))
                self.assertEqual(result["step"]["status"], "review")
                self.assertEqual(len(result["step"]["outputJson"]["findings"]), len(scopes) + 1)
                self.assertEqual(result["step"]["outputJson"]["risks"], ["运营细节待核实。"])
                self.assertEqual([item["rank"] for item in result["step"]["outputJson"]["sources"]], [9] * len(scopes))
                run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == UUID(activity_id), ModelRun.step_no == 2))
                self.assertIsNone(run.provider_request_id)
                self.assertEqual(run.prompt_tokens, 100 * len(scopes))
                self.assertEqual(run.duration_ms, 25 * len(scopes))
                self.assertEqual([item["providerRequestId"] for item in run.scope_progress["scopes"]], [f"provider-{scope}" for scope in scopes])
                read = self.client.get(f"/api/activities/{activity_id}/research/generate/progress")
                self.assertEqual(read.json()["progress"]["status"], "completed")
                self.assertNotIn("providerRequestId", read.text)
                self.assertNotIn("完整原始检索摘要", read.text)
                old = self.client.post(f"/api/activities/{activity_id}/steps/2/generate", json={"version": result["step"]["version"], "model": "selected-model"})
                self.assertEqual(old.json()["detail"]["code"], "USE_RESEARCH_STREAM_ENDPOINT")
                self.assertEqual(len(provider.calls), len(scopes))

    def test_citation_candidates_preserve_every_original_character(self):
        for original in ("短文", "无标点" * 100, "引号‘原样’  空格\r\n" * 50, "完整句子。" * 70, "x" * 80, "x" * 81):
            with self.subTest(original=original[:10]):
                quotes = citation_candidates(original)
                self.assertEqual("".join(quotes), original)
                self.assertTrue(all(0 < len(quote) <= 80 and quote in original for quote in quotes))

    def test_failure_stops_next_scopes_and_preserves_all_raw_evidence(self):
        activity_id, version, provider = self._prepare(["weather", "holiday", "similar_events", "public_trend"])
        previous = self._stream(activity_id, version)[-1][1]["step"]
        old_output = deepcopy(previous["outputJson"])
        raw_before = self.db.scalars(select(SourceReference).where(SourceReference.activity_id == UUID(activity_id)).order_by(SourceReference.id)).all()
        original_evidence = [(str(item.id), item.excerpt) for item in raw_before]
        self.db.rollback()
        provider.calls.clear()
        provider.fail_scope = "holiday"
        events = self._stream(activity_id, previous["version"])
        final = events[-1][1]
        self.assertEqual(events[-1][0], "research_failed")
        self.assertEqual(final["errorCode"], "PROVIDER_TIMEOUT")
        self.assertEqual([item["status"] for item in final["scopes"]], ["completed", "failed", "cancelled", "cancelled"])
        self.assertEqual(len(provider.calls), 2)
        step = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual((step["status"], step["outputJson"]), ("failed", old_output))
        raw = self.db.scalars(select(SourceReference).where(SourceReference.activity_id == UUID(activity_id)).order_by(SourceReference.id)).all()
        self.assertEqual(len(raw), 40)
        self.assertTrue(all(len(item.excerpt) > 3000 for item in raw))
        self.assertEqual([(str(item.id), item.excerpt) for item in raw], original_evidence)
        run = self.db.scalar(select(ModelRun).where(ModelRun.generation_id == UUID(final["generationId"])))
        self.assertEqual(run.prompt_tokens, 100)
        self.assertIsNone(run.provider_request_id)
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/research/generate/progress").json()["progress"], final)

    def test_cross_scope_citation_is_rejected_before_group_completion(self):
        activity_id, version, provider = self._prepare(["weather", "holiday"])
        provider.cross_scope = "holiday"
        events = self._stream(activity_id, version)
        self.assertEqual(events[-1][1]["errorCode"], "PUBLIC_CITATION_METADATA_MISMATCH")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(events[-1][1]["completedScopes"], 0)

    def test_version_owner_and_auth_boundaries_run_before_stream_or_provider(self):
        activity_id, version, provider = self._prepare(["weather"])
        bad = self.client.post(f"/api/activities/{activity_id}/research/generate/stream", json={"version": version - 1, "model": "selected-model"})
        self.assertEqual(bad.json()["detail"]["code"], "VERSION_CONFLICT")
        self.current_user.user_id = uuid4()
        denied = self.client.get(f"/api/activities/{activity_id}/research/generate/progress")
        self.assertEqual(denied.status_code, 404)
        denied_start = self.client.post(f"/api/activities/{activity_id}/research/generate/stream", json={"version": version, "model": "selected-model"})
        self.assertEqual(denied_start.status_code, 404)
        self.client.app.dependency_overrides.pop(require_session)
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/research/generate/progress").status_code, 401)
        self.assertEqual(provider.calls, [])

    def test_disconnect_after_one_scope_commits_failure_and_stops_next_scope(self):
        activity_id, version, provider = self._prepare(["weather", "holiday"])

        async def consume():
            request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
            response = stream_research_generation(UUID(activity_id), SimpleNamespace(version=version, model="selected-model"), request,
                                                 self.current_user, self.db, provider, ("selected-model",))
            iterator = response.body_iterator
            first = await anext(iterator)
            self.assertIn('"completedScopes": 0', first)
            await anext(iterator)  # Scope one running.
            completed = await anext(iterator)
            self.assertIn('"completedScopes": 1', completed)
            await iterator.aclose()

        asyncio.run(consume())
        self.assertEqual(len(provider.calls), 1)
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == UUID(activity_id), ModelRun.step_no == 2))
        self.assertEqual((run.status, run.error_code), ("failed", "GENERATION_INTERRUPTED"))
        self.assertEqual([item["status"] for item in run.scope_progress["scopes"]], ["completed", "cancelled"])
        self.assertEqual(run.prompt_tokens, 100)

    def test_cancel_during_provider_call_retains_real_usage_and_stops_next_scope(self):
        activity_id, version, provider = self._prepare(["weather", "holiday"])
        started, release = threading.Event(), threading.Event()
        def blocking(_scope):
            started.set()
            if not release.wait(3):
                raise AssertionError("test provider did not receive release")
        provider.on_call = blocking

        async def consume():
            request = SimpleNamespace(is_disconnected=lambda: asyncio.sleep(0, result=False))
            response = stream_research_generation(UUID(activity_id), SimpleNamespace(version=version, model="selected-model"), request,
                                                 self.current_user, self.db, provider, ("selected-model",))
            async def reader():
                async for _frame in response.body_iterator:
                    pass
            async with anyio.create_task_group() as group:
                group.start_soon(reader)
                self.assertTrue(await anyio.to_thread.run_sync(lambda: started.wait(3)))
                group.cancel_scope.cancel()
                release.set()

        asyncio.run(consume())
        self.assertEqual(len(provider.calls), 1)
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == UUID(activity_id), ModelRun.step_no == 2))
        self.assertEqual((run.status, run.error_code), ("failed", "GENERATION_INTERRUPTED"))
        self.assertEqual(run.prompt_tokens, 100)
        self.assertEqual(run.scope_progress["scopes"][0]["providerRequestId"], "provider-weather")
        self.assertEqual(run.scope_progress["scopes"][1]["status"], "cancelled")

    def test_legal_groups_with_oversized_merge_fail_explicitly_without_truncating(self):
        activity_id, version, provider = self._prepare(["weather", "holiday"])
        provider.large_summary = True
        events = self._stream(activity_id, version)
        self.assertEqual(events[-1][0], "research_failed")
        self.assertEqual(events[-1][1]["errorCode"], "INVALID_MODEL_RESPONSE")
        self.assertEqual(events[-1][1]["completedScopes"], 2)
        self.assertEqual(len(provider.calls), 2)
        step = self.client.get(f"/api/activities/{activity_id}/steps/2").json()
        self.assertEqual((step["status"], step["outputJson"]), ("failed", {}))

    def test_upstream_change_supersedes_group_without_overwriting_current_step(self):
        activity_id, version, provider = self._prepare(["weather", "holiday"])
        def supersede(_scope):
            first = self.client.get(f"/api/activities/{activity_id}/steps/1").json()
            changed = self.client.post(f"/api/activities/{activity_id}/steps/1/reopen", json={"version": first["version"]})
            self.assertEqual(changed.status_code, 200)
        provider.on_call = supersede
        events = self._stream(activity_id, version)
        self.assertEqual(events[-1][0], "research_failed")
        self.assertEqual(events[-1][1]["errorCode"], "GENERATION_SUPERSEDED")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(self.client.get(f"/api/activities/{activity_id}/steps/2").json()["status"], "needs_review")
        run = self.db.scalar(select(ModelRun).where(ModelRun.activity_id == UUID(activity_id), ModelRun.step_no == 2))
        self.assertEqual([item["status"] for item in run.scope_progress["scopes"]], ["failed", "cancelled"])
        self.assertEqual(run.scope_progress["scopes"][0]["providerRequestId"], "provider-weather")
        self.assertEqual(run.prompt_tokens, 100)
        self.assertEqual(run.duration_ms, 25)


class ScopeProgressContractTests(unittest.TestCase):
    def test_invalid_sequence_and_incomplete_audit_fail_explicitly(self):
        waiting = {"scope": "weather", "status": "waiting", "sourceCount": 10}
        completed = {**waiting, "status": "completed", "model": "chosen-model", "providerRequestId": "real-request", "durationMs": 5,
                     "promptTokens": 1, "completionTokens": 2, "totalTokens": 3}
        cases = [
            {"scopes": [waiting, {**completed, "scope": "holiday"}]},
            {"scopes": [{**waiting, "status": "failed", "errorCode": "ERROR"}, {**waiting, "scope": "holiday"}]},
            {"scopes": [{**completed, "model": " "}]},
            {"scopes": [{**completed, "providerRequestId": ""}]},
            {"scopes": [{**waiting, "status": "failed", "errorCode": "ERROR", "promptTokens": 1}]},
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ScopeProgress.model_validate(value)
        for state, progress in (("completed", {"scopes": [waiting]}), ("failed", {"scopes": [waiting]}),
                                ("running", {"scopes": [{**waiting, "status": "cancelled", "errorCode": "INTERRUPTED"}]})):
            run = SimpleNamespace(scope_progress=progress, status=state, activity_id=uuid4(), generation_id=uuid4())
            with self.assertRaises(StepDomainError):
                progress_snapshot(run, error_code="ERROR")


if __name__ == "__main__":
    unittest.main()
