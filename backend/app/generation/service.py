"""Provider-backed generation for the activity agent's later steps."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from backend.activity_prompt import build_activity_system_prompt
from backend.models import STEP_KEYS

from ..providers.base import Provider, ProviderCapability, ProviderRequest
from .prerequisites import assert_can_generate


@dataclass(frozen=True)
class GenerationContext:
    activity_id: str
    step_no: int
    model: str
    prior_outputs: Mapping[int, Mapping[str, Any]]
    request_id: str
    prior_statuses: Mapping[int, str] = field(default_factory=dict)


class StepGenerationService:
    """Builds step-specific requests while leaving persistence to the caller."""

    _capabilities = {
        5: ProviderCapability.STRUCTURED_EXTRACTION,
        6: ProviderCapability.GENERAL_GENERATION,
        7: ProviderCapability.STRUCTURED_EXTRACTION,
        8: ProviderCapability.GENERAL_GENERATION,
        9: ProviderCapability.LONG_CONTEXT_REVIEW,
    }

    _names = {
        5: "预算控制与资源配置",
        6: "宣传内容与传播计划",
        7: "审批、任务分解与执行准备",
        8: "渠道联动与商业化",
        9: "效果预测与活动复盘",
    }

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    async def generate(self, context: GenerationContext) -> dict[str, Any]:
        if context.step_no not in self._capabilities:
            raise ValueError("only steps 5 through 9 are owned by this service")
        assert_can_generate(context.step_no, context.prior_statuses)
        request = self._request(context)
        result = await self.provider.generate_json(request)
        return {
            "stepNo": context.step_no,
            "stepKey": self._names[context.step_no],
            "capability": self._capabilities[context.step_no].value,
            "data": result.data,
            "sources": self._sources(context),
            "modelRun": {
                "model": result.model,
                "providerRequestId": result.provider_request_id,
                "promptTokens": result.usage.prompt_tokens,
                "completionTokens": result.usage.completion_tokens,
                "totalTokens": result.usage.total_tokens,
                "durationMs": result.duration_ms,
            },
        }

    def _request(self, context: GenerationContext) -> ProviderRequest:
        name = self._names[context.step_no]
        prerequisite_text = "\n".join(
            f"第 {number} 步已确认结果：{output}"
            for number, output in sorted(context.prior_outputs.items())
        )
        return ProviderRequest(
            task=f"activity_step_{context.step_no}",
            model=context.model,
            messages=(
                {
                    "role": "system",
                    "content": build_activity_system_prompt(
                        context.step_no,
                        STEP_KEYS[context.step_no - 1],
                    ),
                },
                {
                    "role": "user",
                    "content": f"请生成第 {context.step_no} 步{name}。\n{prerequisite_text}",
                },
            ),
            request_id=context.request_id,
            metadata={"activityId": context.activity_id, "stepNo": str(context.step_no)},
        )

    def _sources(self, context: GenerationContext) -> list[dict[str, str]]:
        if context.prior_outputs:
            return [{"sourceType": "calculated", "label": "基于已确认前序步骤生成"}]
        return [{"sourceType": "missing", "label": "前序依据待补充"}]
