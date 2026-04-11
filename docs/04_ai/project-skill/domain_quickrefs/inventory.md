# 库存 — 速查

- **模型** `app/models/inventory_ledger.py`（批次+流水+期初）；预留 `app/models/inventory_reservation.py`；日盘点 `app/models/inventory.py`
- **服务** `app/services/inventory_svc.py`（含送货出库、手工流水、ATP/预留、事件）
- **路由** `app/main/routes_inventory.py`；菜单 `inventory_ops_*` / `inventory_query`
- **全文** [../../02_domains/inventory.md](../../02_domains/inventory.md)
