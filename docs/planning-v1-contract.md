# V1 规划契约

任务简报支持 `planningMode: single | annual`，省略模式按既有单场契约处理。年度模式必须提供非空的 `annualPeriod`、`annualGoals` 和 2 至 12 的整数 `plannedEventCount`。已有任意生成结果后规划模式固定，另一种模式需新建任务。

年度第 3 步输出 `annualNarrative` 与 `eventBriefs`。每场简案包含 id、名称、时间窗口、客群、定位、主题方向、规模、共享资产与亮点。用户可将初次生成数量调整至 2 至 12 场，确认的是整个年度架构。年度后续步骤不按 `selectedPlanItemId` 缩小范围。

年度第 4 至 9 步采用 `{ annualPlan, eventPlans: [{ eventId, output }] }`。其中 `annualPlan` 及每场 `output` 使用对应步骤的单场输出契约。第 5 步另有 `annualTotalAmount`，等于年度共用预算与各场预算之和；客户端采用十进制乘加生成数字，避免二进制小数误差。页面允许切换年度统筹和各活动单元编辑。第 9 步各单元可回填实际指标，成果文件仍是年度整体报告。

第 3 步年度架构变更会使下游旧结果失效。年度第 4 至 9 步在 `needs_review`、`generating`、`failed` 状态可读取保留的历史输出，活动 ID 可以属于旧架构；历史输出不代表当前有效结果。读取仍严格验证输出模式、字段和单元结构。`draft`、`review`、`confirmed` 的活动 ID 和顺序必须与当前年度架构一致，保存、确认及成功生成也必须通过当前架构的严格校验。

联网研究保留按实际搜索范围归纳的独立 SSE 入口。其他步骤采用 `POST /api/activities/{id}/steps/{stepNo}/generate/stream`，请求 `{version, model}`。单场有一个 `single` 单元；年度简报有一个 `annual` 单元；年度第 3 步生成年度架构及每场简案；第 4 至 9 步生成年度统筹及每场方案。进度来自实际单元状态，不能用计时模拟。只有 `planning_completed` 且保存的步骤为待确认状态才判定成功；断流、单元失败或保存失败均明确失败。

`GET .../generate/progress` 返回 `{activityId, stepNo, progress}`；刷新只读取状态，不自动重复发起模型请求。进度快照包含 generationId、状态、单元列表与完成数量；失败带公共 errorCode，不暴露服务凭据或内部响应。

已确认的年度简案可通过 `POST /api/activities/{id}/plan-items/{eventId}/activity` 请求 `{version: 第3步版本}` 进入单独深入策划。返回普通单场 Activity。重复进入复用已有任务；年度来源版本变化明确返回 `PLAN_ITEM_SOURCE_CHANGED`，不覆盖子任务。
