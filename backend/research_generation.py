"""Strict, persistent per-scope research generation; no partial business output."""

from copy import deepcopy
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.activity_prompt import build_activity_system_prompt
from backend.activity_steps import ResearchGenerationOutput, StepDomainError, complete_generation
from backend.app.research.selection import RESEARCH_SCOPES, RawPublicEvidence


SCOPE_NAMES = {
    "weather": "天气与气候", "holiday": "节假日与客流",
    "similar_events": "同类活动", "public_trend": "公共趋势",
}


class ScopeAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scope: Literal["weather", "holiday", "similar_events", "public_trend"]
    sourceCount: int = Field(ge=1)
    status: Literal["waiting", "running", "completed", "failed", "cancelled"]
    model: str | None = Field(default=None, min_length=1, max_length=200)
    providerRequestId: str | None = Field(default=None, min_length=1, max_length=300)
    durationMs: int | None = Field(default=None, ge=0)
    promptTokens: int | None = Field(default=None, ge=0)
    completionTokens: int | None = Field(default=None, ge=0)
    totalTokens: int | None = Field(default=None, ge=0)
    errorCode: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, value):
        if isinstance(value, dict) and any(item is None for item in value.values()):
            raise ValueError("audit optional fields must be omitted instead of null")
        return value

    @model_validator(mode="after")
    def check_status(self):
        metadata = (self.model, self.providerRequestId, self.durationMs, self.promptTokens, self.completionTokens, self.totalTokens)
        if any(value is not None and not value.strip() for value in (self.model, self.providerRequestId, self.errorCode)):
            raise ValueError("audit identifiers must not be blank")
        usage = (self.promptTokens, self.completionTokens, self.totalTokens)
        if any(value is not None for value in usage) and not all(value is not None for value in metadata):
            raise ValueError("provider response metadata must be complete")
        if self.status == "cancelled" and any(value is not None for value in metadata):
            raise ValueError("uncalled cancelled scopes cannot have provider metadata")
        if self.status == "completed" and any(value is None for value in metadata):
            raise ValueError("completed scope audit requires complete provider metadata")
        if self.status in {"failed", "cancelled"} and not self.errorCode:
            raise ValueError("failed or cancelled scope audit requires an error code")
        if self.status in {"waiting", "running"} and any(value is not None for value in (*metadata, self.errorCode)):
            raise ValueError("unfinished scope cannot have finished provider metadata")
        if self.status == "completed" and self.errorCode is not None:
            raise ValueError("completed scope cannot have an error code")
        return self


class ScopeProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scopes: list[ScopeAudit] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def check_scopes(self):
        scopes = [item.scope for item in self.scopes]
        if scopes != [scope for scope in RESEARCH_SCOPES if scope in scopes] or len(set(scopes)) != len(scopes):
            raise ValueError("scope audits must be unique and in research scope order")
        if sum(item.status == "running" for item in self.scopes) > 1:
            raise ValueError("only one scope may run at a time")
        states = [item.status for item in self.scopes]
        position = 0
        while position < len(states) and states[position] == "completed":
            position += 1
        tail = states[position:]
        if tail:
            if tail[0] == "running":
                valid = all(value == "waiting" for value in tail[1:])
            elif tail[0] == "waiting":
                valid = all(value == "waiting" for value in tail)
            elif tail[0] == "failed":
                valid = all(value == "cancelled" for value in tail[1:])
            else:
                valid = all(value == "cancelled" for value in tail)
            if not valid:
                raise ValueError("scope progress must contain a completed prefix and a valid sequential tail")
        return self


def initial_scope_progress(evidence):
    groups = {scope: [item for item in evidence if item["scope"] == scope] for scope in RESEARCH_SCOPES}
    progress = ScopeProgress(scopes=[ScopeAudit(scope=scope, sourceCount=len(items), status="waiting") for scope, items in groups.items() if items])
    return progress.model_dump(exclude_none=True)


def progress_snapshot(run, *, error_code: str | None = None):
    try:
        progress = ScopeProgress.model_validate(run.scope_progress)
    except ValueError as exc:
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Persisted research progress does not match its contract") from exc
    states = [item.status for item in progress.scopes]
    if (run.status == "running" and any(value in {"failed", "cancelled"} for value in states)
        or run.status == "completed" and any(value != "completed" for value in states)
        or run.status == "failed" and any(value in {"waiting", "running"} for value in states)
        or run.status not in {"running", "completed", "failed"}):
        raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Research parent status does not match scope states")
    snapshot = {
        "activityId": str(run.activity_id), "generationId": str(run.generation_id), "status": run.status,
        "totalScopes": len(progress.scopes), "completedScopes": sum(item.status == "completed" for item in progress.scopes),
        "scopes": [{"scope": item.scope, "status": item.status, "sourceCount": item.sourceCount} for item in progress.scopes],
    }
    if run.status == "failed":
        if not error_code:
            raise StepDomainError("PERSISTED_GENERATION_PROGRESS_INVALID", "Failed research progress requires a public error code")
        snapshot["errorCode"] = error_code
    return snapshot


def citation_candidates(excerpt):
    """Partition the entire original into short copyable continuous quotations."""
    candidates = []
    start = 0
    while start < len(excerpt):
        end = min(start + 80, len(excerpt))
        if end < len(excerpt):
            boundaries = [index + 1 for index in range(start + 29, end) if excerpt[index] in "。！？；\n"]
            if boundaries:
                end = boundaries[-1]
        candidates.append(excerpt[start:end])
        start = end
    return candidates


def scope_messages(raw_messages, scope, total_scopes):
    instruction, serialized = raw_messages[1]["content"].split("\n", 1)
    context = json.loads(serialized)
    evidence = [item for item in context["publicSearchEvidence"] if item["scope"] == scope]
    if not evidence:
        raise StepDomainError("RESEARCH_EVIDENCE_REQUIRED", "The selected research scope has no persisted evidence")
    context["publicSearchEvidence"] = evidence
    context["publicCitationCandidates"] = [
        {"rank": item["rank"], "scope": item["scope"], "url": item["url"],
         "providerRequestId": item["providerRequestId"], "excerpts": citation_candidates(item["excerpt"])}
        for item in evidence
    ]
    context["publicSearchSelection"] = {
        "totalCount": len(evidence), "selectedCount": len(evidence), "omittedCount": 0,
        "rule": "本次只归纳当前搜索范围的全部完整资料，不截断正文；其他范围另行归纳。",
        "selectedRanksByScope": {scope: [item["rank"] for item in evidence]},
    }
    context["researchScope"] = scope
    target = math.ceil(8 / total_scopes)
    system = build_activity_system_prompt(2, "research", research_scope_targets=(target, math.ceil(200 / total_scopes)))
    system += (
        f"\n本次仅归纳{SCOPE_NAMES[scope]}范围，输入包含该范围全部 {len(evidence)} 条完整检索资料。"
        f"当前共有 {total_scopes} 个范围，各自单独归纳；本次只输出当前范围内容，不能总结其他范围。"
        f"本组主要发现建议约 {target} 条、每条30至60字，摘要约{math.ceil(200 / total_scopes)}字一句，风险及引用各1至2条。"
        "资料不足必须明确待核实，不为目标数量编造；全部引用须来自当前范围并逐字段保留元数据和连续原文。"
        "publicSearchEvidence 仍是完整分析原文。publicCitationCandidates 将每条原文按原有顺序切成可直接复制的短片段，"
        "全部片段拼接等于该来源完整原文，不筛掉任何资料。引用时从对应来源的 excerpts 数组中选择一段直接支撑结论的完整字符串，"
        "逐字符原样复制到 sources[].excerpt；不要凭记忆复述、修正文法、转换引号、标点或空格，也不能拼接多段。"
        "JSON 中的引号、反斜杠及换行按 JSON 语法转义，解析后的字符串必须与候选字符完全相同。"
        "其他引用字段仍从同一 publicSearchEvidence 来源复制，不输出 publicCitationCandidates 或 excerpts 等辅助字段。"
        "这些是当前调用的写作目标，最终整体推荐6至10条短发现，服务端仅确定性合并各组而不再调用模型。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": instruction + "\n" + json.dumps(context, ensure_ascii=False)}], evidence


def validate_scope_citations(output, evidence, *, required_scope=None):
    parsed = ResearchGenerationOutput.model_validate(output)
    originals = [RawPublicEvidence.model_validate(item) for item in evidence]
    for citation in parsed.sources:
        if citation.source_type != "public":
            continue
        if required_scope is not None and citation.scope != required_scope:
            raise StepDomainError("PUBLIC_CITATION_METADATA_MISMATCH", "Public citation must belong to the current research scope")
        matches = [item for item in originals if all(getattr(citation, field) == getattr(item, field) for field in (
            "label", "url", "captured_at", "rank", "scope", "provider_request_id", "published_at", "site_name", "authority_level",
        ))]
        if not matches:
            raise StepDomainError("PUBLIC_CITATION_METADATA_MISMATCH", "Public citation metadata must exactly match a persisted source")
        if not any(citation.excerpt in item.excerpt for item in matches):
            raise StepDomainError("PUBLIC_CITATION_EXCERPT_MISMATCH", "Public citation excerpt must be a character-exact continuous original substring")


def merged_scope_output(outputs):
    summaries, findings, risks, sources = [], [], [], []
    seen_sources = set()
    for scope, output in outputs:
        summaries.append(f"{SCOPE_NAMES[scope]}：{output['summary']}")
        for key, target in (("findings", findings), ("risks", risks)):
            for value in output[key]:
                if value not in target:
                    target.append(value)
        for source in output["sources"]:
            canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if canonical not in seen_sources:
                sources.append(deepcopy(source))
                seen_sources.add(canonical)
    merged = {"summary": "\n".join(summaries), "findings": findings, "risks": risks, "sources": sources}
    try:
        return ResearchGenerationOutput.model_validate(merged).model_dump(by_alias=True, exclude_none=True, mode="json")
    except ValueError as exc:
        raise StepDomainError("INVALID_MODEL_RESPONSE", "Merged research output did not match the required schema") from exc


def aggregate_scope_audit(progress):
    parsed = ScopeProgress.model_validate(progress)
    return {
        "duration_ms": sum(item.durationMs or 0 for item in parsed.scopes),
        "usage": {
            "prompt_tokens": sum(item.promptTokens or 0 for item in parsed.scopes),
            "completion_tokens": sum(item.completionTokens or 0 for item in parsed.scopes),
            "total_tokens": sum(item.totalTokens or 0 for item in parsed.scopes),
        },
    }


def complete_research_group_generation(**kwargs):
    return complete_generation(**kwargs, request_id=None, research_group=True)
