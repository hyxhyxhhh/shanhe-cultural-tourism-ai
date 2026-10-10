"""Prompt assembly for activity generation using runtime step skills."""

from __future__ import annotations

from backend.activity_skill_loader import load_activity_step_skill


OPTIONAL_FIELD_OUTPUT_RULE = (
    "所有层级（包括嵌套对象和数组元素）中的可选字段，在缺失或不适用时必须完全省略对应键，"
    "绝不输出 JSON null。"
)

RESEARCH_JSON_PREFIX = (
    "You are a backend JSON generator. Your entire response is parsed directly by json.loads; "
    "Markdown code fences make the request fail. Output starts with { and ends with }. "
    "Never output backticks or any text outside the JSON object. "
)

RESEARCH_GLOBAL_TARGETS = (
    "Draft a concise Chinese decision brief: summary around 200 characters; "
    "6-10 distinct findings around 30-60 characters each; 3-5 concise risks; "
    "4-6 directly supporting citations, with necessary verbatim excerpts around 30-80 characters. "
    "Preserve all original citation metadata. These are drafting targets within the required schema.\n"
)

RESEARCH_EVIDENCE_PREFIX = (
    "Cover evidence-supported weather, holiday visitor flows, existing event examples, ecological positioning "
    "and content opportunities, booking/transport/venue constraints, and recommended actions. "
    "Mark missing information as requiring verification. Deduplicate findings and never fabricate to reach a count.\n"
    "All valid public search sources and their complete excerpts are included for analysis, without a per-scope cap. "
    "Assess the full evidence set, while citing only sources that directly support the concise findings.\n"
    "For every public citation, copy label, url, capturedAt, rank, scope, providerRequestId, "
    "and every present publishedAt, siteName and authorityLevel field exactly from the same selected source. "
    "The excerpt must be one character-for-character continuous substring of that source's excerpt. "
    "Never insert ellipses or join fragments; do not normalize punctuation or whitespace. "
    "A necessary exact excerpt may be shorter than the 30-character drafting target.\n"
)

RESEARCH_DRAFTING_PREFIX = RESEARCH_JSON_PREFIX + RESEARCH_GLOBAL_TARGETS + RESEARCH_EVIDENCE_PREFIX


def build_activity_system_prompt(
    step_no: int, step_key: str, *, research_scope_targets: tuple[int, int] | None = None,
) -> str:
    skill = load_activity_step_skill(step_no, step_key)
    research_prefix = RESEARCH_DRAFTING_PREFIX
    if research_scope_targets is not None:
        if step_no != 2:
            raise ValueError("research scope targets are only valid for step two")
        findings_target, summary_target = research_scope_targets
        research_prefix = (
            RESEARCH_JSON_PREFIX
            + f"Draft only the current research scope: summary around {summary_target} Chinese characters in one concise sentence; "
            + f"around {findings_target} distinct findings of 30-60 characters each; 1-2 concise risks; "
            + "1-2 directly supporting citations, with necessary verbatim excerpts around 30-80 characters. "
            + "Preserve all original citation metadata. These are drafting targets within the required schema.\n"
            + RESEARCH_EVIDENCE_PREFIX
        )
    return (
        (research_prefix if step_no == 2 else "")
        + f"{skill.content}\n\n"
        "## 运行时输出要求\n"
        f"已加载 {skill.skill_id}@{skill.version}，仅执行 stepNo={step_no}、stepKey={step_key}。\n"
        f"{OPTIONAL_FIELD_OUTPUT_RULE}\n"
        "最终响应必须是纯 JSON 对象：首字符必须是 {，末字符必须是 }。"
        "只能包含一个符合 requiredJsonSchema 的 JSON 对象；不得使用 Markdown 代码块、"
        "解释文字、前后缀、多个 JSON 对象或其他任何字符。"
    )
