# 活动策划 Agent 首期开发契约

## 1. 文档目的

本文档是活动策划 Agent 首期真实功能开发的共享契约。两位开发人员分别在 `yuxin` 和 `wenhao` 分支工作，必须以本文档约定的数据结构、状态和行为为共同边界。

本文档不是最终业务规则的替代品。业务人员仍可对九步内容、字段和验收案例提出修改；但任何修改必须先由双方讨论并更新本文档，再修改代码。代码不得先于契约自行发明新的状态、接口或字段。

## 2. 首期目标

首期只完成活动策划 Agent 的一个可保存、可恢复、可追踪的完整纵向流程：

`创建活动任务 -> 可选上传资料 -> 九步生成与确认 -> 前序修改影响提示 -> 活动后数据回填 -> 复盘 -> 下载三类成果`

首期不直接对外发送短信、发布公众号、投放广告、发送供应商询价或调用其他外部执行系统。所有外部动作先生成草稿，用户确认后仅锁定为“待执行”任务并记录确认；真实执行接口另行立项。

### 2.1 大模型调用必须经 Ccode 中转站

活动策划 Agent 在运行时使用的所有大模型能力，必须统一经由公司指定的 Ccode 中转站 `https://api.ccode.vip` 调用。禁止从应用服务端或浏览器直接请求 OpenAI、Anthropic、Google、DeepSeek 等模型厂商接口；禁止在中转站失败时静默切换到厂商直连或其他未批准服务。

开发约束：

- 模型目录和具体模型 ID 以 [Ccode 模型广场](https://api.ccode.vip/pricing) 当前可用列表为准。模型按任务需要选择，不在业务代码中写死一个不可替换的模型。
- 服务端通过统一 Provider Adapter 调用模型。业务步骤只声明所需能力和配置模型，不各自拼接厂商 URL、鉴权头或供应商专属请求。
- Adapter 需兼容中转站实际开放的协议与模型端点。中转站公开说明包含 OpenAI、Claude Code 等协议，模型目录也标注端点类型；实现前仍须按其[接入文档](https://ccode.apifox.cn)核验 API Base URL、认证方式、请求格式、流式响应和错误语义，不能根据域名或其他服务经验猜接口。
- API Base URL 和 API Key 从环境变量或部署密钥注入。密钥不得进入 Git、前端 bundle、日志、错误详情、数据库明文或交付物。仓库只提交不含真实值的 `.env.example`。
- `CCODE_ALLOWED_MODELS` 是服务端唯一模型目录配置，使用无空格的逗号分隔模型 ID。缺失、空项、重复、非法 ID 或超过 200 字符时服务必须明确报错，不得清洗、猜测或回退。
- 每次生成由用户在前端从服务端模型目录中显式选择模型，生成请求必须携带非空模型 ID；FastAPI 在创建 `ModelRun` 前再次校验白名单并逐次传给 Provider。不得配置或使用默认模型，不得在模型缺失、无效或不可用时自动回退到其他模型。
- 测试可注入 Fake Provider，不消耗真实额度；Fake Provider 只用于测试，不得在生产环境无提示地返回演示内容。
- 记录必要的调用元数据用于排错和费用控制，例如任务 ID、步骤、模型 ID、请求时间、耗时、token 用量和中转站请求 ID。不得记录 API Key、完整敏感文件内容或不必要的个人信息。
- 对超时、限流、余额不足、模型不可用和中转站故障返回可见错误并支持安全重试；重试须幂等，不能重复确认步骤或重复生成成果版本。

本条针对产品运行时 Agent 的大模型调用，不改变开发人员在 Codex 中选择编码助手模型的方式。

### 2.2 单一契约与显式失败

- 开发只实现双方已经确认的当前契约，不为未确认的旧字段、旧结构或推测中的调用方增加兼容分支。
- 请求、响应、配置或持久化数据出现未知字段、未知结构或不满足 schema 时必须明确失败，并返回可定位的错误；不得通过默认值、字段猜测、范围压缩或任意对象兜底掩盖契约错误。
- 不得吞掉异常、把不同业务错误统一改写成无关提示，或在失败后静默降级。Provider 故障时不得自动切换到其他模型供应商。
- Fake Provider 仅用于测试。生产环境不得生成或返回 Fake、演示或伪造业务结果，也不得在缺少来源时合成业务数据。
- 上述规则不取消必要的工程边界：服务端鉴权、所有权校验、输入和输出 schema 校验、数据库事务、乐观锁、幂等与可审计版本仍必须保留。

## 3. 九步定义

步骤必须保持九个独立状态。界面可以在同一屏展示相邻步骤，但数据库、API、确认记录和版本记录不能合并。

| 编号 | 稳定 ID | 名称 | 主要产出 | 是否需要用户确认 |
|---|---|---|---|---|
| 1 | `brief` | 活动简报 | 标准化活动目标、时间、地点、预算、客群、约束 | 是 |
| 2 | `research` | 数据收集与研判 | 数据摘要、来源、推理依据、参考测算、风险提示 | 是 |
| 3 | `theme` | 活动主题方案 | 2 至 3 个候选主题、故事线、视觉方向 | 是，先选定方案 |
| 4 | `content_space` | 活动内容与空间设计 | 动线、时段、场景、装置、互动、人员和安全要求 | 是 |
| 5 | `budget` | 预算控制与资源配置 | 成本明细、预算汇总、降本方案、资源清单 | 是 |
| 6 | `promotion` | 宣传内容与传播计划 | 预热/爆发/尾声节奏、渠道、内容和素材草稿 | 是 |
| 7 | `execution_plan` | 审批、任务分解与执行准备 | WBS、责任人、时间节点、审批草稿、供应商询价草稿 | 是 |
| 8 | `channel_business` | 渠道联动与商业化 | 异业合作、招商赞助、票务、二销和渠道联动方案 | 是 |
| 9 | `review` | 效果预测与活动复盘 | 活动前预测、实际数据回填、复盘结论和改进建议 | 是，复盘完成时确认 |

默认必须按 1 至 9 顺序确认。用户可以返回已完成步骤修改，但不能跳过未确认的步骤直接确认后续步骤。

## 4. 工作流状态

### 4.1 活动任务状态

```text
draft       草稿，尚未开始或仍在填写
running     已开始生成或处理
paused      用户主动暂停，可恢复
completed   九步全部确认且复盘完成
failed      当前任务存在未恢复的系统错误
archived    用户归档，不在默认列表显示
```

### 4.2 步骤状态

```text
locked       前置步骤未确认，当前步骤不可确认
draft        可编辑草稿
generating   正在生成或处理
review       结果已生成，等待用户查看
confirmed    用户已确认
needs_review 前置步骤修改后，本步骤结果可能失效，等待复核
failed       本步骤生成失败，可重试
```

步骤状态变化必须由服务端校验，不能只依赖前端按钮隐藏。服务端必须拒绝未满足前置条件的确认请求。

### 4.3 用户动作

每个步骤至少支持：

- `生成或重新生成`
- `编辑并保存草稿`
- `确认并进入下一步`
- `退回修改`
- `查看来源和版本`

确认时记录用户、时间、输入版本和输出版本。重新生成不能静默覆盖已经确认的版本。

## 5. 数据来源分类

所有指标、判断和预测必须带来源分类。页面不使用“AI 估算”作为展示标签，但不能把估算伪装成事实。

```text
actual       实际数据：用户上传或已接入业务系统的原始数据
public       公开数据：联网检索得到，必须保存来源 URL、抓取时间和摘要
calculated   参考测算：基于已知数据和明确规则计算，必须展示依据
missing      待补充：没有足够依据，不得编造数值
```

`calculated` 的展示示例：

> 参考客流 2.8 万人，依据去年同期客流 2.35 万人、周末系数 1.12 和活动提升系数 1.06 测算。

任何来源不明的数字都不能进入“实际数据”字段。联网搜索默认关闭，由用户在第 2 步单独选择是否启用；启用后仍允许补充搜索。

## 6. 核心实体

### 6.1 Activity

```ts
interface Activity {
  id: string;
  projectId?: string;
  title: string;
  status: "draft" | "running" | "paused" | "completed" | "failed" | "archived";
  currentStep: number;
  input: ActivityBriefInput;
  searchEnabled: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}
```

### 6.2 ActivityBriefInput

```ts
interface ActivityBriefInput {
  idea: string;
  location?: string;
  plannedStartAt?: string;
  plannedEndAt?: string;
  target?: string;
  budgetMin?: number;
  budgetMax?: number;
  targetAudience?: string;
  knownConstraints?: string;
}
```

除 `idea` 外的字段允许暂时为空。系统必须明确显示待补充项，不得为了通过流程自动填入业务事实。

### 6.3 ActivityStep

```ts
interface ActivityStep {
  id: string;
  activityId: string;
  stepNo: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
  stepKey: string;
  status: "locked" | "draft" | "generating" | "review" | "confirmed" | "needs_review" | "failed";
  inputJson: unknown;
  outputJson: unknown;
  version: number;
  confirmedBy?: string;
  confirmedAt?: string;
  updatedAt: string;
}
```

第 5 至第 9 步的 `outputJson` 使用以下固定结构。未提供的可选字段必须省略，不能写 `null`；所有未声明字段必须拒绝。

```ts
interface BudgetOutput {
  items: Array<{
    item: string;
    category: string;
    quantity: number;
    unit: string;
    unitPrice: number;
    subtotal: number;
    sourceType: "actual" | "public" | "calculated" | "missing";
    basis: string;
  }>;
  totalAmount: number;
  savings: Array<{ action: string; estimatedSaving: number; impact: string }>;
  resources: Array<{ name: string; quantity: number; unit: string; purpose: string }>;
  budgetNote: string;
}

interface PromotionOutput {
  strategy: string;
  phases: Array<{
    phase: "warmup" | "peak" | "followup";
    objective: string;
    channels: string[];
    contentDrafts: string[];
    materials: string[];
  }>;
}

interface ExecutionPlanOutput {
  tasks: Array<{
    title: string;
    description: string;
    owner?: string;
    dueAt?: string;
    dependencies: string[];
    approvalDraft: string;
    supplierInquiryDraft: string;
  }>;
  approvalSummary: string;
  externalActionsDraftOnly: true;
}

interface ChannelBusinessOutput {
  channelActions: Array<{
    channel: string;
    objective: string;
    actions: string[];
    revenueModel: string;
    draftTerms: string;
  }>;
  sponsorshipPackages: Array<{
    name: string;
    targetPartner: string;
    benefits: string[];
    referencePrice: number;
    sourceType: "calculated" | "missing";
    basis: string;
  }>;
  ticketingPlan: string;
  secondarySalesPlan: string;
  externalActionsDraftOnly: true;
}

interface ReviewOutput {
  forecastMetrics: Array<{
    metric: string;
    value: number;
    unit: string;
    sourceType: "calculated";
    basis: string;
  }>;
  actualMetrics: Array<{
    metric: string;
    value: number;
    unit: string;
    sourceType: "actual";
    basis: string;
  }>;
  missingActualMetrics: string[];
  conclusions: string[];
  improvements: string[];
}
```

第 5 步 `subtotal` 必须等于 `quantity * unitPrice`，`totalAmount` 必须等于全部 `subtotal` 之和。第 7 步首次确认某一版本时，服务端在同一事务内按任务顺序创建 `pending_confirmation` 执行任务；重复请求不得重复创建。第 7、8 步的 `externalActionsDraftOnly` 必须为 `true`。

### 6.4 SourceReference

```ts
interface SourceReference {
  id: string;
  activityId: string;
  stepNo: number;
  sourceType: "actual" | "public" | "calculated" | "missing";
  label: string;
  fileId?: string;
  url?: string;
  capturedAt?: string;
  excerpt?: string;
  reasoning?: string;
}
```

### 6.5 UploadedFile

```ts
interface UploadedFile {
  id: string;
  activityId: string;
  filename: string;
  mimeType: string;
  size: number;
  storageKey: string;
  parseStatus: "pending" | "processing" | "ready" | "failed";
  extractedText?: string;
  uploadedBy: string;
  createdAt: string;
}
```

上传资料是可选的。首期至少支持常见 Word、Excel、PDF 和 CSV；不支持的格式要明确提示，而不是静默忽略。

### 6.6 ExecutionTask

```ts
interface ExecutionTask {
  id: string;
  activityId: string;
  stepNo: number;
  title: string;
  description?: string;
  owner?: string;
  dueAt?: string;
  status: "draft" | "pending_confirmation" | "ready" | "in_progress" | "blocked" | "completed";
  attachmentFileIds: string[];
}
```

第 7 步生成的任务初始为 `pending_confirmation`。用户确认后变为 `ready`，首期不自动触发外部系统。

## 7. API 契约

浏览器统一请求 Next.js BFF；BFF 负责登录态、权限上下文和请求转发。FastAPI 负责长任务、文件解析、联网搜索、模型调用和成果生成。浏览器不得直接依赖 FastAPI 地址。

登录用户通过 `GET /api/models` 获取当前服务端允许选择的模型，响应结构固定为：

```json
{
  "models": ["model-a", "vendor/model-b"]
}
```

返回顺序与 `CCODE_ALLOWED_MODELS` 配置顺序一致。接口不得合并其他来源的模型、增加默认项或暴露 API Key。

### 7.1 活动任务

```text
GET    /api/activities
POST   /api/activities
GET    /api/activities/:activityId
PATCH  /api/activities/:activityId
POST   /api/activities/:activityId/pause
POST   /api/activities/:activityId/archive
```

`POST /api/activities` 最小请求：

```json
{
  "title": "2026 武汉樱花季文旅沉浸式市集",
  "input": {
    "idea": "围绕樱花季做一场沉浸式夜游市集",
    "location": "某文旅街区",
    "plannedStartAt": "2026-03-20T17:30:00+08:00",
    "plannedEndAt": "2026-03-22T22:30:00+08:00",
    "target": "引流与二销",
    "budgetMax": 500000
  }
}
```

### 7.2 步骤操作

```text
GET    /api/activities/:activityId/steps
GET    /api/activities/:activityId/steps/:stepNo
PATCH  /api/activities/:activityId/steps/:stepNo
POST   /api/activities/:activityId/steps/:stepNo/generate
POST   /api/activities/:activityId/steps/:stepNo/confirm
POST   /api/activities/:activityId/steps/:stepNo/reopen
```

生成请求必须同时包含当前版本号和用户选择的 Ccode 模型 ID：

```json
{
  "version": 3,
  "model": "用户在前端明确选择的模型 ID"
}
```

`model` 必须是 1 至 200 个字符的非空字符串，不能包含首尾空白。缺失或非法时请求直接失败；服务端不得使用环境变量、默认值或其他模型回退。所选模型必须传给 Ccode Provider，并记录到本次 `ModelRun`。

若模型不在 `CCODE_ALLOWED_MODELS` 中，FastAPI 返回 `422 MODEL_NOT_ALLOWED`，且不得改变步骤状态、版本或创建 `ModelRun`。

确认请求至少包含当前版本号，防止旧页面覆盖新结果：

```json
{
  "version": 3,
  "comment": "确认主题二，并要求保留亲子互动环节"
}
```

版本不匹配时返回 `409 VERSION_CONFLICT`，前端必须重新拉取当前版本。

### 7.3 文件

```text
POST   /api/activities/:activityId/files
GET    /api/activities/:activityId/files
DELETE /api/activities/:activityId/files/:fileId
POST   /api/activities/:activityId/files/:fileId/reparse
```

文件上传后先保存元数据，再异步解析。文件解析失败不能阻塞用户查看和编辑已有步骤，但必须显示失败原因。

### 7.4 研究与联网搜索

原始检索证据与模型研判分别存储：搜索成功后将完整来源和检索摘要保存在 `SourceReference` 中，清空第 2 步的旧研判并生成新版本，步骤保持 `draft`，此时不能确认。模型研判成功后才进入 `review`；研判只引用直接支撑结论的必要原文连续片段，每条 `sources[].excerpt` 不超过 3000 个字符，完整检索摘要仍保留在原始证据中。

全部有效搜索证据及完整检索摘要参与第 2 步模型归纳，不限制每个搜索范围的来源条数，不截断正文、不预先筛除或静默压缩来源。启用联网搜索时，按真实持久化搜索范围分组，选几种范围就顺序调用几次模型，每次只包含当前范围的全部原始正文；不再把所有范围一次性提交，也不追加总归纳模型调用。按搜索范围、排名升序排列，排名相同按持久化的采集时间及来源 ID 稳定排列；纳入前校验全部原始证据，非法排名、范围或结构必须显式失败。`publicSearchSelection` 仅传当前组全部纳入规则、数量和排名，避免重复正文。模型公开引用必须属于当前组、对应真实证据、保留全部搜索元数据，并使用原文连续片段；组完成前校验一次，最终保存事务内重新校验，失败不得保存。原始资料不删除。摘要或风险须说明当前组资料数量及实际存在的覆盖限制，不得虚构未纳入来源。

第 2 步整体推荐摘要约 200 字、主要发现 6 至 10 条、每条約 30 至 60 字。联网分组调用中，每组发现目标为向上取整的 `8 / 实际范围数`，摘要约 `200 / 实际范围数` 字一句，风险及直接支撑引用各 1 至 2 条；每条原文摘录约 30 至 80 字。服务端以中文范围标题拼接各组实际摘要，发现与风险按完全相同的文本去重，引用按规范字段完整相同去重，不截断、不补造、不二次模型合成；合并超出现有 schema 直接报 `INVALID_MODEL_RESPONSE`，不降级保存。发现覆盖有证据支持的天气、假日客流、已有活动案例、生态定位与内容机会、预约交通场地限制、行动建议等维度；资料不足明确待核实，不为条数虚构内容。未开启联网搜索时保留普通单次研判，风险 3 至 5 条、引用 4 至 6 条。写作目标不改变现有输出 schema、单次请求超时和 token 上限；纯 JSON、来源元数据和连续原文校验仍为硬性边界。

公开引用来源名称及全部存在的元数据逐字段原样复制；摘录是已纳入来源正文中的一个逐字符匹配的连续子串，不插入省略号、不拼接片段、不归一化标点和空白。必要摘录可少于 30 字写作目标。来源元数据不匹配报 `PUBLIC_CITATION_METADATA_MISMATCH`，摘录不连续报 `PUBLIC_CITATION_EXCERPT_MISMATCH`；前端按领域错误码显示明确中文原因，失败不保存研判、不修改原始证据，可重试归纳。

第 2 步顶层 `sources[]` 中 `sourceType == public` 的 `excerpt` 属于外部原文，不按内部技术标识词表扫描（例如真实英文 `warm-weather`）；仍须通过严格输出 schema，并在生成锁内通过全部来源元数据和逐字符连续原文校验后才允许保存。摘要、发现、风险、来源名称、站点、推理文本及非公开摘录仍执行原技术标识校验；任意其他嵌套对象不得使用此例外。

联网分组 prompt 另提供 `publicCitationCandidates`，每条原始来源均有候选，关联 `rank/scope/url/providerRequestId`；将完整原文按顺序确定性分成不超过 80 字的连续片段，优先在句末断开，全部片段拼接严格等于原文，不删改任何字符。模型分析仍读取 `publicSearchEvidence` 的全部完整原文，引用选择一个支持结论的候选字符串整体原样复制，不复述或修正文法、标点、引号及空白。辅助字段不进入输出或后续步骤，来源元数据与连续子串 validator 不变，服务端绝不自动修正模型返回引用。

`GET /api/activities/{id}/research/selection` 经过登录及活动所有权校验，返回 `activityId`、`totalCount`、`selectedCount`、`omittedCount`、`selected`、`omitted`；唯一支持全量纳入契约：`selectedCount == totalCount`、`omittedCount == 0`、`omitted == []`。每条 `selected` 含完整原始证据字段 `label`、`url`、`capturedAt`、`excerpt`、`rank`、`scope`、`providerRequestId`，以及存在的 `publishedAt`、`siteName`、`authorityLevel`；前端严格拒绝旧的部分纳入结构。此接口只读，从持久化原始证据确定性计算，刷新及重试后仍能查看全部来源的标题、链接、全量纳入标记及可展开的完整检索摘要；内部请求标识不在页面展示。页面区分“直接支撑研判的引用”与“全部检索来源”，原始证据面板位于研判结果下方并使用滚动列表。后续步骤仅接收已确认研判，不传递原始检索正文和纳入记录。

确认第 2 步和写入后续步骤时，必须在第 2 步最近一次清空输出之后存在 `generated` 版本；手工保存和失败版本不能替代模型归纳成功记录。所有研判输出（包含已保存、待确认和供后续使用的输出）统一通过 `ResearchGenerationOutput`，至少含一条发现，每条发现不超过 500 个字符。未完成归纳时不得手工保存非空研判；归纳成功后的人工编辑必须保留完整原始公开证据。归纳失败保留搜索资料，可单独重试模型归纳，无需重新搜索。

```text
POST   /api/activities/:activityId/research
GET    /api/activities/:activityId/research/selection
POST   /api/activities/:activityId/research/generate/stream
GET    /api/activities/:activityId/research/generate/progress
```

分组归纳请求只接受 `{version, model}`，范围从当前持久化资料确定，重试不重搜。请求返回 SSE 前校验登录、活动所有权、版本、模型及全部证据，启动一个 `ModelRun`；启用联网搜索的旧步骤生成接口显式返回 `USE_RESEARCH_STREAM_ENDPOINT`。`ModelRun.scope_progress` 是严格 JSONB 审计，逐组保存实际状态、真实模型请求标识、耗时、token 用量及安全错误码。父记录只聚合实际用量和耗时，`provider_request_id` 保持 `None`，不拼接或冒充单次调用标识；其他步骤该 JSONB 字段为 `None`。资料和单组业务结果不写进进度审计。

进度业务快照唯一结构为 `{activityId, generationId, status, totalScopes, completedScopes, scopes:[{scope,status,sourceCount}], errorCode?}`。整体状态为 `running/completed/failed`，范围状态为 `waiting/running/completed/failed/cancelled`；已完成范围必须连续位于列表前部，至多一个正在归纳且必须是下一范围。整体失败禁止等待或正在归纳范围，后续全部取消；`errorCode` 仅失败状态必需，使用现有公开错误码，不返回模型请求标识或正文。SSE 仅使用 `event`/`data`：`research_progress` 发送快照，`research_completed` 发送快照加最终 `step`，`research_failed` 发送失败快照。GET 返回 `{activityId,progress:快照或null}`；最新第 2 步调用不是分组归纳时进度为 `null`。前端按实际 `completedScopes / totalScopes` 显示进度，全部范围完成后仍须等待最终保存成功事件。

每组运行前后只持有短数据库事务，模型等待期间无步骤行锁。任何组失败，当前范围失败、后续取消、整体失败必须在同一事务记录；保留完整检索证据和上次草稿，不保存部分业务成功。全部组通过后在活动及生成记录锁内一次性保存最终研判和一个新版本；代际失效不能覆盖当前步骤。断开连接不继续下一组，已开始的同步模型调用等待返回后保留实际审计，将未完成整体标记 `GENERATION_INTERRUPTED`；即使响应正文尚未启动也有清理保障。禁止自动重试、切换供应商或以内存假任务代替真实持久化进度。

请求示例：

```json
{
  "useWebSearch": true,
  "queryScope": ["weather", "holiday", "similar_events", "public_trend"]
}
```

联网搜索不可用时，系统应返回可继续编辑的结果和 `missing` 来源，不得伪造联网结果。

### 7.5 活动后回填与复盘

```text
POST   /api/activities/:activityId/review/prepare
POST   /api/activities/:activityId/review/actual-data
POST   /api/activities/:activityId/review/generate
POST   /api/activities/:activityId/review/confirm
```

实际数据至少支持客流、收入、成本、曝光、互动、转化和异常说明。字段不齐时允许部分回填，并标记缺失项。

### 7.6 成果文件

```text
POST   /api/activities/:activityId/deliverables/generate
GET    /api/activities/:activityId/deliverables
GET    /api/activities/:activityId/deliverables/:deliverableId/download
```

首期必须生成三类成果：

```text
event-plan.docx       完整策划 Word
budget.xlsx           预算 Excel
execution-tasks.xlsx  执行任务表 Excel
```

文件生成应产生可追踪版本，不能覆盖用户已经下载或确认的旧版本。

## 8. SSE 事件

长任务使用 SSE。事件数据统一包含 `activityId`、可选 `stepNo`、`eventId` 和服务端时间。

```text
job_started
progress
step_output_updated
job_completed
job_failed
```

`progress` 至少包含 `percent` 和 `message`。断线重连必须能够通过任务查询接口恢复最终状态，不能只依赖 SSE 内存事件。

## 9. 前序修改规则

用户修改并保存已确认步骤时：

1. 当前步骤生成新版本，旧版本保留。
2. 所有受影响的后续步骤标记为 `needs_review`。
3. 系统列出受影响步骤和原因。
4. 不自动删除后续输出，不自动执行外部动作。
5. 用户确认受影响步骤后，才能再次进入下一步。

首期影响关系按顺序处理：前一步默认影响所有后续步骤；如果后续实现更精细的依赖图，必须补充到本文档后再使用。

## 10. 首期非目标

- 不实现真实短信、广告、公众号、OTA 或供应商平台执行。
- 不同时把运营招商和营销策划 Agent 接入真实后端。
- 不建设复杂多 Agent 编排平台。
- 不在没有数据来源时编造业务事实。
- 不以隐藏按钮代替服务端权限。
- 不先做大规模 UI 重构。
- 不为了“看起来智能”增加无法验收的自动化。

## 11. 端到端验收标准

使用一个真实活动案例完成以下流程：

1. 用户创建活动任务，只填写基础想法也可以保存。
2. 用户可选择不上传文件，也可上传至少一种支持格式。
3. 用户在第 2 步选择是否联网搜索，并能看到来源分类。
4. 九步按顺序生成、编辑、确认，刷新页面后状态不丢失。
5. 第 3 步可以选择 2 至 3 个主题中的一个。
6. 第 5 步预算能追溯到第 4 步内容和资源。
7. 第 7 步生成任务草稿，确认后任务进入平台内可管理状态。
8. 修改第 1 至 4 步任一步后，后续步骤显示 `needs_review`。
9. 活动结束后可以回填实际数据并完成第 9 步复盘。
10. 可以下载完整策划 Word、预算 Excel 和执行任务表 Excel。
11. 关键操作保留用户、时间、版本和失败原因。
12. 所有真实运行时大模型请求均通过 Ccode 中转站；密钥不出现在客户端、Git 或日志中，中转站故障不会导致静默直连其他模型供应商。

## 12. 契约变更流程

发现契约不足时，先在分支上提交文档修改草案并通知另一位开发人员。双方确认后再修改接口或数据模型。不得为了局部开发方便直接绕过契约；不得把 Mock 字段当作正式字段；不得在没有业务确认的情况下增加新的正式步骤。
