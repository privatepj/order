# 业务域：生产（Production）

> 本文档为**骨架**：列出主要入口。测算管线、排程与成本细节见代码与 [production-measurement-benchmark.md](../production-measurement-benchmark.md)。

## 核心概念

- 预计划、工单、工序/路由、缺料、测算与成本等模型分布在 `app/models/production_*.py`。
- 核心测算：`app/services/production_svc.py`（如 `measure_production_for_preplan`），排程与成本见 `production_schedule_svc.py`、`production_cost_svc.py`。测算内库存分配使用 **`inventory_svc.atp_for_item_aggregate`**（台账结存 − 他单有效预留）；测算成功后按工单/子项 **`stock_covered_qty`** 汇总写入 `inventory_reservation`（`ref_type=preplan`），重算前删除本预计划旧预留。
- **排程 v3 跨工单（BOM）**：`production_schedule_svc.plan_operations_for_preplan` 根据 `production_component_need`（`shortage_qty>0` 且子项为 `finished`/`semi`）将同预计划、同 `root_preplan_line_id`、且与 BOM 子项匹配的子工单与父工单建立 **FS**：父工单任意无工序内向前置的工序，最早开工时间不早于相关子工单**全部工序**的最晚 EF；工单处理顺序为子先于父（Kahn 拓扑）。人工保存/确认排程时，`validate_preplan_schedule` 会调用 `list_bom_work_order_gate_errors` 校验同一规则。
- **预计划人工排程与确认**：详情页「排程规划」表格内在人工排程模式下可改 ES/EF 与指定机台/人员；`POST .../schedule-manual` 经 `production_preplan_schedule_manual_svc.apply_manual_plan_from_form` 校验后写回 `production_work_order_operation_plan` 与工序快照并重算成本；`POST .../schedule-confirm` 将计划写入机台 `machine_schedule_booking` 切分 + `machine_schedule_dispatch_log`（`scheduled`）及人员 `hr_employee_schedule_booking`。重新测算前由 `revoke_preplan_commits_for_measure` 撤销未报工提交；若存在已报工 `dispatch_log` 则禁止测算。库表见 `run_71_production_operation_plan_commit.sql` / `production_schedule_commit_row`。
- **部门生产看板**：菜单 `production_department`，路由 `/production/department-board`；`app/services/production_dept_board_svc.py` 按行政部门聚合工序——机台类工序依据 `machine.owning_hr_department_id`（及已选 `budget_machine_id` / 同机种本部门机台池）；人工类工序依据 `hr_department_id` 或 `hr_department_work_type_map`（部门-工种允许）。预计划详情页机台下拉与当日可用 `machine_schedule_booking` 列表对**已绑定 HR 档案部门**的用户收窄为「本部门 + 未分配归属」机台。库表：`run_89_machine_owning_hr_department.sql`、`run_90_production_department_nav.sql`。
- 工序路由支持统一目标对象：`finished`（成品）与 `semi`（半成品）。路由模型使用 `production_product_routing.target_kind + target_id` 绑定工序模板；测算阶段会为成品/半成品工单都生成工序快照（若存在有效路由）。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_production.py` |
| 服务 | `app/services/production_svc.py`、`production_schedule_svc.py`、`production_cost_svc.py`、`production_dept_board_svc.py` |
| 模板 | `app/templates/production/*.html` |
| 编排器 | 库存/订单等事件可触发测算类动作（见 [03_orchestrator](../03_orchestrator/index.md)） |

### 工序管理（统一路由）

- 列表与编辑入口：`/production/product-routings`
- 页面支持对象类型切换（成品/半成品），复用同一套“模板绑定 + 步骤覆写”编辑器。

## 权限

- 以 `routes_production.py` 装饰器为准；变更时同步 [map_routes_to_services.md](../04_ai/project-skill/map_routes_to_services.md)。
- **预生产计划菜单**（`production_preplan`）下常见细项能力：
  - `production.preplan.action.create` / `edit` / `delete`：预计划维护
  - `production.calc.action.run`：重新测算、人工排程、保存排程、确认计划等与测算/排程相关的 **操作**
  - `production.preplan.cost.view`：预生产详情页 **「预算总成本（元）」** 汇总（优化场景与按已选资源）；无此能力时仍可看排程与工时等，但不查询/不展示成本金额。管理员不受限。库表种子见 `scripts/sql/run_79_production_preplan_cost_view_cap.sql`。
  - **部门生产看板**（`production_department`）：`production.department.board.view` / `production.department.board.filter_dept`（切换部门；管理员或显式授权）。普通用户依赖 `HrEmployee.user_id` + `department_id` 解析默认部门。

## 相关文档

- [production-measurement-benchmark.md](../production-measurement-benchmark.md)
