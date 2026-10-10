from copy import deepcopy
import unittest

from pydantic import ValidationError

from backend.app.research.selection import RESEARCH_SCOPES, select_public_evidence


def evidence(scope="weather", rank=0, label=None):
    return {
        "label": label or f"{scope}-{rank}",
        "url": f"https://example.com/{scope}/{rank}",
        "capturedAt": "2026-09-24T00:00:00+00:00",
        "excerpt": f"完整原文-{scope}-{rank}" * 500,
        "rank": rank,
        "scope": scope,
        "providerRequestId": "request-1",
    }


class SelectionTests(unittest.TestCase):
    def test_four_scopes_include_all_forty_complete_sources_without_omissions(self):
        raw = [evidence(scope, rank) for scope in RESEARCH_SCOPES for rank in reversed(range(10))]
        before = deepcopy(raw)
        selected, record = select_public_evidence(raw)
        self.assertEqual(raw, before)
        self.assertEqual((record["totalCount"], record["selectedCount"], record["omittedCount"]), (40, 40, 0))
        for scope in RESEARCH_SCOPES:
            self.assertEqual([source["rank"] for source in selected if source["scope"] == scope], list(range(10)))
        self.assertTrue(all(source["excerpt"] == before[before.index(source)]["excerpt"] for source in selected))
        self.assertEqual(record["selected"], selected)
        for item in record["selected"]:
            original = next(source for source in before if source["label"] == item["label"])
            self.assertEqual(item, original)
            self.assertGreater(len(item["excerpt"]), 3000)
        self.assertEqual(record["omitted"], [])

    def test_selection_preserves_all_present_optional_metadata(self):
        raw = [evidence(rank=rank) for rank in range(4)]
        for source in raw:
            source.update(publishedAt="2026-09-20", siteName="原始站点", authorityLevel="high")
        selected, record = select_public_evidence(raw)
        self.assertEqual(record["selected"], raw)
        self.assertEqual(record["omitted"], [])

    def test_equal_ranks_keep_persisted_order_and_small_scopes_keep_all(self):
        raw = [evidence(rank=1, label=label) for label in ("first", "second", "third", "fourth")]
        raw.append(evidence("holiday", 9))
        selected, record = select_public_evidence(raw)
        self.assertEqual([item["label"] for item in selected], ["first", "second", "third", "fourth", "holiday-9"])
        self.assertEqual(record["omitted"], [])

    def test_invalid_evidence_fails_instead_of_disappearing(self):
        for field, value in (("rank", -1), ("rank", "9"), ("rank", True), ("scope", "unknown"), ("excerpt", None), ("url", "file:///invalid")):
            with self.subTest(field=field, value=value):
                raw = [evidence(rank=rank) for rank in range(10)]
                raw[-1][field] = value
                with self.assertRaises(ValidationError):
                    select_public_evidence(raw)

    def test_empty_evidence_returns_zero_actual_counts(self):
        selected, record = select_public_evidence([])
        self.assertEqual(selected, [])
        self.assertEqual(record, {"totalCount": 0, "selectedCount": 0, "omittedCount": 0, "selected": [], "omitted": []})


if __name__ == "__main__":
    unittest.main()
