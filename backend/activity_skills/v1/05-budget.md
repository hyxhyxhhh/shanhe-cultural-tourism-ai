# 活动预算与资源配置

## 输入契约

- 读取已确认的内容与空间方案以及全部已确认前序依据。
- 用户预算区间是硬约束；没有真实报价时只能给出有测算依据的参考值。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- 输出 `items`、`savings`、`resources`、`budgetNote`。
- 每项预算只包含项目、类别、数量、单位、单价、来源类型和测算依据。
- 不得输出 `subtotal`、`totalAmount` 或其他派生算术字段；服务端会根据数量和单价确定性计算每项小计与预算总额。
- 只能输出 `requiredJsonSchema` 声明的字段；禁止额外键、占位键或临时修正字段。
- 当前预算是待用户确认的草稿，预算确认后才可生成宣传计划。

## 业务判断规则

- 逐项覆盖场地、搭建、内容制作、人员、设备、安全、宣传准备和预备费用等当前方案实际需要的成本。
- 真实资料使用 `actual`，公开依据使用 `public`，估算使用 `calculated`，缺依据使用 `missing`。
- 节省建议必须说明预计节省金额和对效果、质量或风险的影响。

## 禁止行为

- 禁止把估算、网络价格或经验值写成实际报价。
- 禁止用总额反推无法解释的明细，禁止以宣传目标倒逼虚假预算。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括项目、类别、单位、测算依据、节省影响和预算说明）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键及来源类型等结构化枚举值仍须严格遵守 `requiredJsonSchema`。
- 禁止声称采购、询价或付款已经发生，禁止标注内容由 AI 生成。
