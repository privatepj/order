# 业务域：机台（Machine）

> 本文档为**骨架**。

## 核心概念

- 机台类型、机台台账、运行日志、排班模板与预约：`app/models/machine.py`。
- 排程服务：`app/services/machine_schedule_svc.py`。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_machine.py` |
| 模板 | `app/templates/machine/*.html` |
| 生产协作 | 工序资源可映射到 `machine_type`（见 [production.md](production.md)） |
