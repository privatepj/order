# 业务域：机台（Machine）

> 本文档为**骨架**。

## 核心概念

- 机台类型、机台台账、运行日志、排班模板与预约：`app/models/machine.py`。
- **归属行政部门** `machine.owning_hr_department_id`：车间/产线行政归属（`hr_department.id`，0=未分配），用于部门生产看板与预计划机台候选收窄；与 **能力工位/工种** `default_capability_*`（计件、排程资源键）语义不同，表单与培训需区分。
- 排程服务：`app/services/machine_schedule_svc.py`。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_machine.py` |
| 模板 | `app/templates/machine/*.html` |
| 生产协作 | 工序资源可映射到 `machine_type`（见 [production.md](production.md)） |
