# 活动效果预测与复盘

## 输入契约

- 读取全部已确认方案，以及上下文中明确提供的实际活动数据。
- 方案期只能形成预测；只有有明确来源的已发生数据才可进入实际指标。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- 输出 `forecastMetrics`、`actualMetrics`、`missingActualMetrics`、`conclusions`、`improvements`。
- 当上下文已经提供至少一条已保存的 `actualMetrics` 时，`requiredJsonSchema` 只允许输出 `conclusions` 与 `improvements`；`forecastMetrics`、`actualMetrics` 和 `missingActualMetrics` 由服务端原样保留并合并。
- 预测指标的 `sourceType` 必须为 `calculated`；实际指标必须为 `actual`。
- 没有实际数据时保持 `actualMetrics` 为空，并在 `missingActualMetrics` 明确列出缺口。
- 当前结果是待用户确认的预测或复盘草稿。

## 业务判断规则

- 预测指标应覆盖客流、传播、转化、收入、成本或满意度中与本活动目标相关的可测指标。
- 每个指标说明计算或数据依据，结论区分预测与事实。
- 改进项必须能对应已识别的风险、指标差距或执行问题。

## 禁止行为

- 禁止伪造客流、收入、曝光、转化、满意度或其他实际数据。
- 禁止把目标值、预算值或模型估算写入 `actualMetrics`。
- 已有实际指标时，禁止输出、改写、删除、补充或重新判断 `forecastMetrics`、`actualMetrics`、`missingActualMetrics` 中的任何内容。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括指标名称、单位、依据、实际数据缺口、复盘结论和改进建议）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键及来源类型等结构化枚举值仍须严格遵守 `requiredJsonSchema`。
- 禁止声称复盘已经完成或改进措施已经实施，禁止标注内容由 AI 生成。
