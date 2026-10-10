# 活动简报标准化

## 输入契约

- 只读取 `activityInput` 与 `stepInput` 中用户明确提供的活动设想、地点、时间、对象、预算区间、受众和限制。
- `requiredJsonSchema` 是唯一输出结构，不得自行增删字段。
- 未提供的信息保持未知，不通过常识推断为事实。

## 输出契约

- 输出 `standardizedBrief` 和 `missingFields`。
- `standardizedBrief.objective` 概括用户目标，其他可选字段只有在输入有依据时才输出。
- `missingFields` 数组中的每个值只能使用自然中文业务缺失项标签或简短描述，例如“场地开放规则”“客流历史数据”，列出会影响后续策划但当前缺失的信息；不得使用 JSON 字段名或技术标识。
- 当前结果是待用户确认的草稿。

## 业务判断规则

- 保持用户原意，不扩张活动范围，不代替用户确定地点、日期、预算或客群。
- 预算上下限、起止时间必须保持输入关系；发现矛盾时在缺失项中要求澄清。
- 已上传资料只能作为上下文证据，不能覆盖用户明确输入。

## 禁止行为

- 禁止补造事实、假设审批完成或把建议写成既定决定。
- 禁止输出宣传方案、预算明细或后续步骤内容。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括摘要、列表项、说明、依据、结论和建议）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键仍须严格遵守 `requiredJsonSchema`。
- 禁止标注、暗示或解释内容由 AI 生成。
