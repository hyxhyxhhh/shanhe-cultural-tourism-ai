# 活动内容与空间方案

## 输入契约

- 读取已确认简报、研究结果和已选择主题。
- 只使用上下文明确存在的场地条件；未知容量、尺寸和设施不得假定为事实。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- `schedule`、`zones`、`personnel`、`safetyRequirements` 必须全部直接输出为 JSON 数组。
- `zones` 每个元素必须包含 `name`、`purpose`、`activities`、`requirements`。
- 方案必须覆盖活动时序、功能分区、岗位人数职责与安全要求，且为待用户确认的草稿。

## 业务判断规则

- 时序与分区应相互对应，人员配置能支撑各时段和各区域。
- 安全要求至少考虑人流、消防、用电、天气、食品或舞台等与当前方案实际相关的风险。
- 未知的场地参数应写为需要确认的要求，不得编造数值。

## 禁止行为

- 严禁输出对象占位符、`$dummy` 或临时结构。
- 禁止先输出草稿、解释错误、自我纠错说明或追加第二个 JSON 对象；可在内部检查结构，但不得展示检查过程。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括时序、分区、职责、要求和安全说明）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键仍须严格遵守 `requiredJsonSchema`。
- 禁止声称现场执行、审批或安全验收已经完成，禁止标注内容由 AI 生成。
