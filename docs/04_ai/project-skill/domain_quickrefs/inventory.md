# 库存 — 速查

- **模型** `app/models/inventory_ledger.py`（批次+流水+期初）；预留 `app/models/inventory_reservation.py`；日盘点 `app/models/inventory.py`
- **服务** `app/services/inventory_svc.py`（含送货出库、手工流水、ATP/预留、事件）
- **路由** `app/main/routes_inventory.py`；菜单 `inventory_ops_*` / `inventory_query`
- **表单 UI**：进出库等待办行「品名搜索 + 规格只读」为 `textarea` + `name-search-textarea` + `autoResize`（见 [../SKILL.md](../SKILL.md)「长品名与规格」）
- **结存查询** `GET /inventory/query`：`query_stock_aggregate`；可选按**系列**筛选（`inventory_query.filter.series`，主数据 `product` / `semi_material(kind=semi)` 的 `series` 字段）
- **导出** `GET /inventory/movement/export`：支持 `preset=week|month|custom` + `start_date/end_date`，能力键 `inventory_ops_*.movement.export`
- **全文** [../../02_domains/inventory.md](../../02_domains/inventory.md)
