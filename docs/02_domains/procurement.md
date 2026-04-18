# 业务域：采购（Procurement）

> 本文档为**骨架**：列出主要入口文件。详细流程、状态机与权限表建议随迭代补充。

## 核心概念

- 供应商、物料映射、请购单、采购单、收货、入库与对账等模型见 `app/models/procurement.py`。
- 大量业务流程在路由层实现：`app/main/routes_procurement.py`（可逐步下沉到 `procurement_svc` 若后续抽取）。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_procurement.py` |
| 工具/Excel | `app/utils/procurement_order_excel.py` 等 |
| 模板 | `app/templates/procurement/*.html` |
| 库存协作 | 收货/入库与 `InventoryMovement` 的 `source_purchase_*` 字段（见 [inventory.md](inventory.md)） |

## 权限

- 以路由上的 `@menu_required` / `@capability_required` 为准；变更时请同步本文件与 [map_routes_to_services.md](../04_ai/project-skill/map_routes_to_services.md)。
- 物料管理入口为 `采购管理 -> 物料管理`，菜单 code：`procurement_material`，endpoint：`main.procurement_material_list`，URL：`/procurement/materials`。
- 若 admin 看不到“物料管理”，优先排查：
  - `sys_nav_item` 中 `procurement_material` 是否 `is_active=1` 且挂在 `nav_procurement` 下；
  - 服务进程是否使用了旧 RBAC 快照（多实例需全部重载）。

## 供应商 Excel 导入

- 入口：`/procurement/suppliers/import`；模板下载：`/procurement/suppliers/export-import-template`。
- 供应商-物料映射列填写 **物料名称 + 规格**（与 `semi_material` 主数据一致），系统按 `app/services/inventory_svc.py` 中 `find_semi_material_id_by_name_spec` 与库存导入相同的规则匹配 `kind=material` 的物料；**不在 Excel 中填写物料编号**。

## 相关 SQL

- 以 `scripts/sql/run_*` 中与 procurement 相关的脚本为准（见 [05_releases](../05_releases/index.md) 发布说明）。
