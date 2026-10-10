# 单场活动主题与年度活动架构设计

## 输入契约

- 读取已确认的活动简报和研究研判，不使用未确认步骤作为事实依据。
- `requiredJsonSchema` 是唯一输出结构。
- 主题必须受地点、客群、时间、预算约束和研究风险约束。
- `activityInput.planningMode` 明确选择单场活动或年度活动组合；只执行该模式，不混用两种输出。

## 输出契约

- 单场活动模式输出 2 至 3 个 `candidates`，每个候选包含稳定唯一的 `id`、`name`、`storyline`、`visualDirection` 和 `highlights`。候选之间必须有清晰差异，且都能够进入内容、空间和预算设计。所有候选均为待用户选择一个主主题并确认的草稿。
- 年度活动组合模式分次请求，每次只输出 `requiredJsonSchema` 指定的当前单元，不得输出 `candidates` 或擅自生成完整年度活动列表。
- 年度架构请求只输出 `annualNarrative` 和 `eventSeeds`。总叙事说明全年定位、核心客群、活动节奏与共享资产的统筹方式；活动种子包含稳定唯一的 `id`、`name`、`timeWindow`、`targetAudience`、`positioning`、`themeDirection` 和 `scale`，数量和 ID 顺序必须符合上下文明确指定的要求。
- 每场活动补充请求只输出 `sharedAssets` 和 `highlights`，依据该场活动种子和年度叙事生成，不输出、改写其他种子字段，也不包含其他活动。服务端将所有已完成单元组装为 `annualNarrative` 与 `eventBriefs` 供用户整体确认。
- 年度活动简案须覆盖具体时间窗口、活动分工和内容亮点，不一次展开所有活动的完整执行细节；用户确认整个年度架构，之后可单独深入某场活动。

## 业务判断规则

- 主题名称清晰可传播，叙事与目的地资源及目标受众一致。
- 卖点应能转化为现场内容，而不是只写抽象口号。
- 视觉方向描述色彩、材质、氛围和关键识别元素，不承诺尚未制作的素材。
- 年度活动组合需要体现季节与节庆差异，说明各活动如何共同支撑年度目标，避免客群、场地、人员与传播窗口的冲突。
- 共享资产只记录明确可复用的内容、场地、设备、供应商或传播资产；没有共享资产时使用空数组，不编造资源。

## 禁止行为

- 禁止脱离已确认简报和研究结论另起活动目标。
- 禁止生成无法区分的同义候选或把候选写成已最终选定。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括主题名称、叙事、视觉方向和亮点）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键仍须严格遵守 `requiredJsonSchema`。
- 禁止标注内容由 AI 生成。
