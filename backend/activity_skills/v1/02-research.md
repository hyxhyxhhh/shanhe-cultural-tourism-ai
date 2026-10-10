# 活动公开信息研判

## 输入契约

- 读取已确认的第 1 步、`searchEnabled`、`stepInput.useWebSearch` 和 `publicSearchEvidence`。
- 只有 `publicSearchEvidence` 中的条目可以声明为 `public` 来源。
- 全部有效搜索证据及完整检索摘要都参与本次模型归纳，不限制每个范围的来源条数，不截断正文、不预先筛除来源；按搜索范围及排名稳定排列。`publicSearchSelection` 只列出全部纳入规则、数量和排名，避免重复正文。
- 只能依据搜索证据研判事实，必须在摘要或风险中用自然中文说明资料数量和实际存在的覆盖限制，不得虚构未纳入来源。
- 每条公开证据可能包含 `label`、`url`、`capturedAt`、`excerpt`、`publishedAt`、`siteName`、`authorityLevel`、`rank`、`providerRequestId`、`scope`；生成时必须实际参考其内容和元数据。

## 输出契约

- 输出 `summary`、`findings`、`sources`、`risks`。
- 整体研判推荐摘要约 200 字、主要发现 6 至 10 条、每条约 30 至 60 字。启用联网搜索时，每个实际持久化搜索范围单独调用模型：当前组发现目标为向上取整的 `8 / 范围数量`，摘要约 `200 / 范围数量` 字一句，风险和直接支撑引用各 1 至 2 条；只归纳当前组全部证据，不总结其他组。服务端确定性拼接各组摘要、精确去重发现风险及引用，不再额外调用模型做总归纳，不截断输出。未启用联网搜索时单次研判使用整体目标，风险 3 至 5 条、引用 4 至 6 条。每条引用必要原文摘录约 30 至 80 字。这些是写作目标，不替代 JSON schema 硬性校验，不得为凑数量编造发现、风险或来源。
- 主要发现覆盖有证据支持的天气、假日客流、已有活动案例、生态定位与内容机会、预约交通场地限制、行动建议等维度；资料不足明确标为待核实，结论去重，不为达到条数重复或虚构。
- `sources` 只列出直接支撑结论的最少来源，不要逐条回显 `publicSearchEvidence`；未引用的原始来源仍由系统保存在检索证据中。
- 引用公开证据时，`sources[].excerpt` 只摘取该证据中直接支持结论的必要原文连续片段，不超过 3000 个字符；不得改写、拼接或捏造摘录。原样保留该证据的 URL、采集时间及存在的搜索元数据，不得改写成另一来源。
- 每条公开引用的 `label`、`url`、`capturedAt`、`rank`、`scope`、`providerRequestId` 及存在的 `publishedAt`、`siteName`、`authorityLevel` 必须逐字段从同一条已纳入来源原样复制。摘录必须逐字符匹配原文中的一个连续子串，不能插入省略号、拼接不连续片段或归一化标点和空白；必要的精确短片段可少于 30 字写作目标。
- 分组调用的 `publicCitationCandidates` 为每条来源提供可复制的原文连续短片段；同一来源全部片段按顺序拼接等于完整原文，分析仍读取 `publicSearchEvidence` 全文。引用选择其中一段直接支撑结论的完整字符串原样复制，不改标点、引号、空白或语法，不拼接多段；输出引用其他元数据仍从对应原始来源复制，不输出候选辅助字段。服务端不替模型修正引用，严格校验不变。
- `findings` 是面向决策的简洁结论，不是检索原文摘录；每条不超过 500 个字符，必须去重，并明确影响或行动含义。
- `findings` 不得复制来源原文、整段天气预报或长引文；完整检索摘要由系统保存在原始检索证据中，`sources[].excerpt` 只保留必要摘录。
- 没有足够证据的判断使用 `missing`；仅由已知事实推导的内容使用 `calculated` 并给出 `reasoning`。
- 当前研判是待用户确认的草稿。

## 业务判断规则

- 围绕天气、节假日、相似活动和公共趋势等证据识别机会、约束和风险。
- 优先参考权威等级更高、排名更靠前且发布时间与活动决策更相关的来源，但不得因排序而隐藏相互矛盾的证据。
- 结论必须能追溯到具体来源；来源只证明其摘录覆盖的事实，不作超范围推断。

## 禁止行为

- 禁止虚构网址、发布时间、站点、权威等级、排名、请求编号或搜索范围。
- 禁止在未启用联网搜索或无公开证据时生成 `public` 来源。
- `requiredJsonSchema` 中的键名只用于组织 JSON 结构；任何面向用户的字符串值（包括摘要、发现、风险、来源名称、摘录和推导依据）都必须使用自然中文业务表述，禁止回显 JSON 字段名、上下文变量名、枚举原值、camelCase 或 snake_case 技术标识。
- 严禁在用户可见文字中出现 `confirmedResearchEvidence`、`confirmedResearchEvidence.sources`、`similar_events`、`public_trend`、`plannedStartAt`、`plannedEndAt`、`sourceType`、`calculated`、`missing`、`actualMetrics`、`forecastMetrics`、`missingActualMetrics` 等内部标识；结构化 JSON 键及来源类型、检索范围等结构化枚举值仍须严格遵守 `requiredJsonSchema`。
- 禁止把搜索摘要当作已核验的景区内部经营数据，禁止标注内容由 AI 生成。
