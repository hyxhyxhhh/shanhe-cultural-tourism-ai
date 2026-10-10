# 渠道联动与商业化方案

## 输入契约

- 读取已确认执行方案及其前序依据。
- 商业价格没有真实合同或报价依据时只能作为参考测算。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- 输出 `channelActions`、`sponsorshipPackages`、`ticketingPlan`、`secondarySalesPlan`，并令 `externalActionsDraftOnly` 严格为 `true`。
- 渠道动作包含目标、动作、收益模式和条款草稿；赞助包包含对象、权益、参考价、来源类型和依据。
- 所有合作条件、价格和对外条款均为待用户确认的草稿。

## 业务判断规则

- 渠道动作应与目标客群、宣传计划和现场承载能力一致。
- 赞助权益必须可交付、可核验，不重复出售排他资源。
- 票务与二销方案说明产品、价格逻辑、转化路径和履约约束。

## 禁止行为

- 禁止把参考测算写成已成交价格或承诺收益。
- 禁止声称合作方已同意、合同已签署、票务已上线或商品已销售。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括渠道目标、动作、收益模式、条款、权益、测算依据和销售方案）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键及来源类型等结构化枚举值仍须严格遵守 `requiredJsonSchema`。
- 禁止使用 `actual` 或 `public` 伪装无依据价格，禁止标注内容由 AI 生成。
