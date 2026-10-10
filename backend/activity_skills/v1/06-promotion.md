# 活动宣传与传播计划

## 输入契约

- 只在第 5 步预算已确认后生成，读取已确认主题、内容空间方案和预算。
- 渠道与素材规模必须受已确认预算和执行资源约束。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- 输出 `strategy` 和恰好三个阶段：`warmup`、`peak`、`followup`。
- 每个阶段包含目标、渠道、内容草稿和素材清单。
- 所有对外文案和传播安排都是待人工确认的草稿。

## 业务判断规则

- 预热阶段负责认知和预约，爆发阶段负责到场和互动，延续阶段负责复盘传播和长期转化。
- 渠道选择应匹配目标受众、地域和活动类型，并与预算中的宣传资源对应。
- 内容草稿表达具体活动价值，不虚构嘉宾、权益、奖品、名额或官方背书。

## 禁止行为

- 禁止在预算确认前生成宣传计划。
- 禁止声称内容已发布、广告已投放、媒体已确认或用户已触达。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括策略、目标、渠道、文案和素材名称）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键及阶段枚举值仍须严格遵守 `requiredJsonSchema`。
- 禁止输出超出预算依据的传播承诺，禁止标注内容由 AI 生成。
