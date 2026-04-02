# Orchestrator 事件触发与后续自动动作（业务流程版）

这份文档面向不懂接口/不懂技术的人，目标是回答三个问题：

1. 业务上发生了什么动作，会触发 Orchestrator 的“事件”？
2. 触发后系统会自动做什么（哪些会立刻改数据，哪些只是生成建议/等待处理）？
3. 如果动作没有推进/卡住了，应该去哪里看、怎么继续？

---

## 一句话总览

当订单、库存、收货、生产、质检、机器事故等业务发生变化时，系统会先记录一条“事件”（`orchestrator_event`），再由 Orchestrator 引擎把它转换成“后续动作”（`orchestrator_action`）。

部分动作会直接推动订单状态、创建预生产计划、触发生产测算；也有一部分动作目前属于“建议/占位”，执行后主要是生成动作记录与建议结果，并不等同于已经创建出采购单/外协单等业务单据。

---

## 系统会不会自动把事件继续往下跑？

在这个仓库里，**没有发现后台 worker/定时任务会自动把 `OrchestratorEvent.status = "new"` 的事件继续推进到执行阶段**。

也就是说：

- 只有少数“入口”会在产生事件后立刻执行（例如某些 Orchestrator 的接口、部分生产/质检相关按钮、以及 `flask orchestrator-scan-overdue`）。
- 其它业务通常只是把事件写入库里，事件会停留在 `status="new"`，需要后续人工或外部任务去触发“运行事件”（`POST /orchestrator/events/<event_id>/run`）。

你可以把它理解为：**事件先落地，后续推进要看是否走了“立刻执行”的入口，或是否有人/外部任务去 run。**

---

## 能力边界（哪些“后续动作”会真的改主数据）

根据引擎当前的实现，动作大致分两类：

1. 会直接改业务主数据（更接近“自动执行”）
   - `CreatePreplan`：创建预生产计划草稿，并生成明细行
   - `RunProductionMeasure`：触发生产测算（调用生产测算服务）
   - `MoveOrderStatus`：推进订单状态

2. 当前实现偏“建议/占位”（执行后主要是生成动作记录/建议结果）
   - `CreateProcurementRequest`：当前只返回“建议行数”等结果（不等同于已经生成采购单）
   - `ApplyAlternativeMaterial` / `CreateOutsourceOrder` / `SwitchSecondarySupplier`：当前多为候选建议/策略模板结果
   - `EscalateDeviceAlert`：目前返回“告警升级”结果（不等同于完成整套告警工单闭环）
   - `TriggerQualityHold` / `TriggerQualityRework`：当前共用同一套执行逻辑，返回“返工创建/质检hold”相关结果（不保证已经落到完整的质检单据链路）

---

## 端到端业务场景（从业务动作开始 -> 系统自动做什么）

下面每个场景都按同一逻辑写：

`触发点` -> `触发的事件(event_type)` -> `系统自动生成/执行哪些动作` -> `你通常接下来要做什么/怎么看结果`

### 1. 新建/更新订单（缺料触发链路）

触发点：订单创建成功或订单重新计算/保存后

触发事件：`order.changed`

系统自动做什么（当事件被执行到引擎时）：

1) 引擎会做一次缺料对比（库存合计 vs 订单需求）

2) 如果发现缺料（缺口 > 0），系统会生成这些动作：

- `CreatePreplan`：创建预生产计划草稿（草稿状态）
- `CreateProcurementRequest`：生成采购建议
- 以及可能的补充建议（由规则开关/策略决定）：
  - `ApplyAlternativeMaterial`：替代物料建议
  - `CreateOutsourceOrder`：外协建议
  - `SwitchSecondarySupplier`：二供切换建议

3) 如果不缺料（缺口 = 0），系统会生成：

- `MoveOrderStatus(target_status="pending")`：推进订单状态到 `pending`

你通常接下来要做什么：

- 如果这次是通过“入库事件但未立刻执行”的入口发生的，你需要在事件列表里找到对应的 `event_id`，调用：`POST /orchestrator/events/<event_id>/run`
- 看结果优先看：
  - 订单时间线：`GET /orchestrator/orders/<order_id>/timeline`
  - 看该事件生成了哪些动作：`GET /orchestrator/events/<event_id>/actions`

注意：是否“立刻推进”，取决于你的业务入口是不是在产生事件后立刻执行引擎。

---

### 2. 送货出库 / 库存变化（库存更新后，缺料消失则触发生产测算）

触发点：送货出库生成库存流水；或手工补录库存流水等导致库存变化

触发事件：`inventory.changed`

系统自动做什么（当事件被执行到引擎时）：

1) 引擎会再次做缺料对比
2) 如果不再缺料（库存已覆盖需求）：
   - 生成 `RunProductionMeasure`：触发生产测算

你通常接下来要做什么：

- 同样取决于事件是否被立刻执行：
  - 如果未立刻跑，找到 `event_id` 后执行 `POST /orchestrator/events/<event_id>/run`
- 观察结果：
  - 订单时间线是否出现生产测算相关动作与状态推进

---

### 3. 采购收货（posted）后，若缺料消失则触发生产测算

触发点：收货单状态变为 `posted`（且是从未 posted 到 posted）

触发事件：`procurement.received`

系统自动做什么（当事件被执行到引擎时）：

1) 再次做缺料对比
2) 如果不缺料：
   - 生成 `RunProductionMeasure`：触发生产测算

你通常接下来要做什么：

- 找到对应事件并 run（如未自动立刻执行）
- 然后跟踪订单时间线

---

### 4. 生产测算完成（推进关联订单为 partial）

触发点：生产测算动作完成后（形成测算结果）

触发事件：`production.measured`

系统自动做什么（当事件被执行到引擎时）：

- 生成 `MoveOrderStatus(target_status="partial")`，用于推进与该预生产计划关联的订单到 `partial`

你通常接下来要做什么：

- 确认这次 `production.measured` 事件是否被立刻执行
- 如果未立刻执行，就 run 该 event；然后看订单时间线是否出现 partial 推进

---

### 5. 生产报工（推进订单为 partial）

触发点：工作单报工成功

触发事件（当前会写入两类事件）：
- `production.operation.reported`
- `production.reported`

系统自动做什么（当对应事件被执行到引擎时）：

- `production.reported`：会推进订单为 `partial`
- `production.operation.reported`：同样会推进订单为 `partial`

你通常接下来要做什么：

- 看订单时间线：partial 是否被推进
- 如果你发现订单没有推进，可能是某个事件还停留在 `status="new"`，需要 run

---

### 6. 质检链路（开始/通过/失败/返工）

触发点：质检开始、质检通过、质检失败、以及返工完成

触发事件：
- `quality.inspection.started`
- `quality.passed`
- `quality.failed`
- `quality.reworked`

系统自动做什么（当事件被执行到引擎时）：

1) 质检开始：生成
- `MoveOrderStatus(target_status="pending")`

2) 质检通过：生成
- `MoveOrderStatus(target_status="partial")`

3) 质检失败：生成两类动作
- `TriggerQualityHold(target_status="pending")`：质检 hold（等待/冻结）
- `TriggerQualityRework`：触发返工

4) 返工完成：生成
- `MoveOrderStatus(target_status="partial")`

你通常接下来要做什么：

- 看订单时间线的状态推进（pending/partial）
- 若质检失败触发后你需要继续处理返工/hold 对应的业务单据，那么需要根据你们系统里对这两类动作的落地方式（当前实现偏“返回结果/占位”，不保证自动生成完整质检单据）

---

### 7. 机器事故（异常/恢复 -> 告警升级）

触发点：事故新增（异常）、事故状态更新为关闭（恢复）

触发事件：
- `production.machine.abnormal`
- `production.machine.recovered`

系统自动做什么（当事件被执行到引擎时）：

- 生成 `EscalateDeviceAlert`：告警升级动作（当前实现偏返回结果/占位）

你通常接下来要做什么：

- 查该事故相关事件的动作记录是否生成
- 如果没有动作，检查该事件是否仍在 `status="new"`，必要时 run

---

### 8. 逾期扫描（time-out 催办，给逾期订单生成采购建议）

触发点：
- 手动触发：`POST /orchestrator/scan/overdue`
- 或 CLI：`flask orchestrator-scan-overdue`

触发事件：`order.overdue_scan`

系统自动做什么（当事件被执行到引擎时）：

1) 引擎会找出逾期订单：
   - `required_date < 今天`
   - 订单状态在 `pending/partial`
   - 最多取 200 条

2) 对每个逾期订单生成：
   - `CreateProcurementRequest`（采购建议动作）

重要说明（避免误解）：

- 逾期扫描只负责“逾期识别 + 催办提醒”，本阶段不会像 `order.changed` 那样计算缺料明细
- 因此在当前执行实现里，`CreateProcurementRequest` 的结果更像“提醒/触发采购动作的建议记录”，并不等同于完整缺料明细驱动的采购单落地

你通常接下来要做什么：

- 看逾期事件对应的动作记录
- 需要进一步真正创建采购单时，通常还要结合你们采购侧的业务流程（或者触发缺料计算链路）

---

## 用户如何确认发生了什么、以及继续推进

1. 看系统概览
- `GET /orchestrator/dashboard`

2. 看某个订单发生了哪些事件/动作
- `GET /orchestrator/orders/<order_id>/timeline`

3. 看某个事件生成了哪些动作
- `GET /orchestrator/events/<event_id>/actions`

4. 如果发现事件停留在 `status="new"` 或未推进，继续执行
- `POST /orchestrator/events/<event_id>/run`

5. 如果发现动作失败，可重试/恢复
- `POST /orchestrator/actions/retry`
- `POST /orchestrator/actions/<action_id>/recover`

---

## 附录：你们业务最常用的“链路口诀”

- 订单变了（`order.changed`）且缺料：生成预生产计划草稿 + 采购建议（并可能补充替代/外协/二供切换）
- 库存/收货变了（`inventory.changed` / `procurement.received`）且不缺料：触发生产测算
- 生产推进（测算/报工/质检）：推进订单为 `partial` 或停在 `pending`
- 机器事故：触发告警升级动作
- 逾期扫描：识别逾期订单并生成采购建议催办

