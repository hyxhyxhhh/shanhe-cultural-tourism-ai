# 统一模型 Provider 契约

本文档定义活动策划业务使用大模型的唯一正式边界。实现以 `backend/ccode_provider.py` 中的 `ModelProvider`、`ModelMessage`、`ModelResult` 和 `CcodeModelProvider` 为准。`backend/app/providers/` 不拥有另一套 Ccode 协议实现，只提供异步业务代码所需的薄适配层。

## 1. 强制规则

1. 生产模型请求只能通过 `CcodeModelProvider` 发往 Ccode 中转站。
2. 每次生成必须由调用方显式提供非空 `model`。禁止默认模型、能力到模型的隐式映射、供应商切换、模型降级和自动重试。
3. 业务层不得拼接 Ccode URL、鉴权头或厂商请求体，也不得解释厂商响应。
4. `FakeProvider` 只能由测试显式注入。生产代码不得根据环境或异常自动选择 Fake。
5. Ccode 错误必须原样进入现有 `CcodeProviderError` 分类，由 API 层统一转换；不得吞掉异常或用伪造结果继续流程。
6. JSON 输出只接受一个完整对象。禁止 Markdown 包裹、多个 JSON、空响应和任意层级的 `null`。传入 Schema 时还必须拒绝未知字段、缺失必填字段和类型错误。
7. 生成结果必须保留模型 ID、上游请求 ID、输入/输出/总 token 数和耗时，供上层审计。
8. API Key 只能存在于服务端环境或密钥系统，不能进入 Git、前端、日志、数据库业务字段或交付文件。

## 2. 唯一环境契约

只允许以下 Ccode 环境变量：

```env
CCODE_API_BASE_URL=https://api.ccode.vip
CCODE_API_KEY=
CCODE_ALLOWED_MODELS=
CCODE_REQUEST_TIMEOUT_SECONDS=90
CCODE_MAX_OUTPUT_TOKENS=4096
```

- `CCODE_API_BASE_URL` 由 `CcodeModelProvider` 校验并规范化为正式 chat completions 地址。
- `CCODE_ALLOWED_MODELS` 由模型目录和 API 请求校验层使用，不产生默认模型。
- `CCODE_REQUEST_TIMEOUT_SECONDS` 只控制单次请求超时。
- `CCODE_MAX_OUTPUT_TOKENS` 是请求输出上限，不等同于模型选择。
- 不支持 `CCODE_BASE_URL`、`CCODE_GENERAL_MODEL`、`CCODE_STRUCTURED_MODEL`、`CCODE_LONG_CONTEXT_MODEL`、`CCODE_TIMEOUT_SECONDS`、`CCODE_MAX_RETRIES` 或 `CCODE_RETRY_BACKOFF_SECONDS`。

## 3. 同步正式接口

`backend.ccode_provider.ModelProvider` 是唯一 Provider 协议：

```python
class ModelProvider(Protocol):
    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        model: str,
        metadata: TaskMetadata | None = None,
    ) -> ModelResult: ...
```

`model` 是必填关键字参数。`ModelResult` 必须包含：

```text
text
model
provider_request_id
prompt_tokens
completion_tokens
total_tokens
duration_ms
```

业务能力标签可以用于界面或审计，但不能解析为模型 ID。模型必须来自当前请求中用户选择且已由 API 层校验的值。

## 4. 异步业务适配

异步服务注入 `backend.app.providers.AsyncModelProviderAdapter`。它只做三件事：

1. 将通用消息转成 `ModelMessage`；
2. 用 `asyncio.to_thread` 调用已注入的同步 `ModelProvider`；
3. 将 `ModelResult` 转成保留完整元数据的 `ProviderResult` 或 `ProviderJsonResult`。

适配器不得创建 HTTP 请求、读取另一套配置、选择模型、重试或修改模型输出。

调用示例：

```python
provider = AsyncModelProviderAdapter(CcodeModelProvider.from_env())
request = ProviderRequest(
    task="activity_step_5",
    messages=({"role": "user", "content": "生成预算草稿"},),
    model=validated_selected_model,
    request_id=job_id,
    metadata={"activityId": activity_id, "stepNo": "5"},
)
result = await provider.generate_json(request)
```

调用方必须显式保存或传递 `result.model`、`result.provider_request_id`、`result.usage` 和 `result.duration_ms`，不能只取 `result.data`。

## 5. 第 5 至 9 步前置条件

生成只接受状态为 `confirmed` 的指定前序步骤：

| 当前步骤 | 必须已确认 |
|---|---|
| 5 | 4 |
| 6 | 5 |
| 7 | 5、6 |
| 8 | 7 |
| 9 | 8 |

`locked`、`draft`、`review`、`needs_review` 或缺失记录都不满足前置条件。前置步骤发生变更后，必须先重新确认，不能绕过。

## 6. 测试边界

单元测试可以直接注入 `FakeProvider` 或把一个实现 `ModelProvider` 的同步夹具包装进 `AsyncModelProviderAdapter`。Fake 的每个任务响应必须显式配置，请求仍必须显式携带模型；不存在默认响应、默认模型或生产自动选择逻辑。

测试至少覆盖：

- 请求模型必填且逐次传递；
- 多个 JSON、`null`、未知字段和类型错误被拒绝；
- 模型运行元数据完整保留；
- 第 5 至 9 步的确认顺序，尤其第 9 步依赖第 8 步；
- 任何错误都不会触发默认模型、供应商切换、Fake 回退或自动重试。

## 7. 集成责任

- Router/API 层负责认证、活动归属、模型允许列表校验、幂等键和错误响应。
- Generation Service 负责步骤前置条件、Prompt 和将完整模型结果交给上层持久化。
- Provider 层不读写 Activity、ActivityStep、Job 或审计表。
- Job/SSE 层负责进度和最终状态；SSE 不是事实来源。
- 任何运行时装配必须显式创建 `AsyncModelProviderAdapter(CcodeModelProvider.from_env())`，不得出现第二个 Ccode adapter。
