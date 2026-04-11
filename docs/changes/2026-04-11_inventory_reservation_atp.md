# 2026-04-11 生产测算库存预留与 ATP

## 摘要

- 新增表 `inventory_reservation`（增量 `scripts/sql/run_72_inventory_reservation.sql`，全量见 `00_full_schema.sql`）。
- `measure_production_for_preplan` 内库存分配改为按 **ATP**（`ledger_qty_aggregate − reserved_active_qty_aggregate`），成功后按 `stock_covered_qty` 写入预留；重算/预计划改草稿/删除预计划时删除对应预留。
- 预计划编辑与删除路由补充调用 `inventory_svc.delete_reservations_for_preplan`。

## 测试

- `pytest tests/test_inventory_reservation.py`
