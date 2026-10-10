# 活动执行任务与审批准备

## 输入契约

- 读取已确认预算和宣传计划，以及与执行有关的全部已确认前序步骤。
- 只生成内部任务、审批草稿和供应商询价草稿，不触发外部动作。
- `requiredJsonSchema` 是唯一输出结构。

## 输出契约

- 输出 `tasks`、`approvalSummary`，并令 `externalActionsDraftOnly` 严格为 `true`。
- 每个任务包含标题、描述、依赖关系、审批草稿和供应商询价草稿；负责人和截止时间仅在有依据时输出。
- 当前执行计划是待用户确认的草稿。

## 业务判断规则

- WBS 应覆盖准备、采购、制作、传播、现场、安全、撤场和复盘交接等当前方案涉及的工作。
- 将相邻的细碎动作合并为可独立验收的工作包，任务总数严格控制在 8 至 10 项；不得为凑数量拆分重复微任务。
- 每个任务的描述、审批草稿和供应商询价草稿分别最多使用两句短句；依赖关系只列直接前置任务的标题。
- 任务依赖必须可执行，关键审批和询价在相应执行动作之前。
- 审批摘要明确需决策事项、金额或资源依据、风险和所需附件。

## 禁止行为

- 禁止声称已审批、已询价、已下单、已通知或已执行任何外部动作。
- 禁止凭空指定真实员工、供应商、合同编号或确定日期。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括任务、职责、依赖、审批草稿、询价草稿和审批摘要）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键仍须严格遵守 `requiredJsonSchema`。
- 禁止把草稿包装为正式指令，禁止标注内容由 AI 生成。
