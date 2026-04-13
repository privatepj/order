# 业务域：库存（Inventory）

## 核心概念

- **期初** `InventoryOpeningBalance`：按 `category`、成品 `product_id` 或物料 `material_id`、`storage_area` 等维度。
- **流水** `InventoryMovement`：方向、数量、业务日、`source_type` 及来源 ID（送货、采购单、收货单等）。
- **批次** `InventoryMovementBatch`：一次提交（手工、Excel、送货出库等）的批次头；与多条 `InventoryMovement` 关联。
- **日盘点**：`InventoryDailyRecord` / `InventoryDailyLine`（`app/models/inventory.py`），路由在 `routes_inventory.py`。
- **预留** `InventoryReservation`（[`app/models/inventory_reservation.py`](../../app/models/inventory_reservation.py)）：计划占用，**不**写入 `InventoryMovement`。`ref_type`/`ref_id` 当前用于 `preplan` + `production_preplan.id`。测算用 **ATP** = 台账结存（期初+流水汇总，与生产测算相同口径、忽略仓储区）− `status=active` 的预留合计；见 `inventory_svc.ledger_qty_aggregate`、`reserved_active_qty_aggregate`、`atp_for_item_aggregate`。

**台账模型**：[`app/models/inventory_ledger.py`](../../app/models/inventory_ledger.py)  
**服务**：[`app/services/inventory_svc.py`](../../app/services/inventory_svc.py)  
**路由**：[`app/main/routes_inventory.py`](../../app/main/routes_inventory.py)

## 品类菜单（`category`）

与操作菜单码对应（见 `routes_inventory`）：

- 成品：`inventory_ops_finished`（`inventory_svc` 中 finished 品类常量）
- 半成品：`inventory_ops_semi`
- 物料：`inventory_ops_material`

查询结存等能力可能受 `inventory_stock_query_read_filters` 等约束（见 `app/auth/capabilities.py`）。

## 批次列表与 `?category=`

- **入口**：侧栏「成品/半成品/材料录入」对应 `GET /inventory/finished|semi|material`，内部 **302** 到 `GET /inventory?category=finished|semi|material`，先进入**仅含该类的** `InventoryMovementBatch` 列表。
- **无 query**：`GET /inventory` 按当前用户拥有的上述菜单，**仅展示其有权菜单对应品类的批次**（多菜单则合并为一张表并保留「类别」列）；仅一个菜单时等价于带 `category=`。
- **越权**：`category` 与本人菜单不一致时返回 **403**；非法取值 **404**。
- **批次详情 / 撤销 / 删单条流水**：按批次或流水上的 `category` 校验对应 `movement.list`、`movement_batch.void`、`movement.delete`（不再仅凭「任一品类能力」覆盖他类数据）。


## 数量展示与录入校验

- **页面数量字符串**：模板中对 `Decimal`/`Numeric` 数量优先使用 Jinja 过滤器 **`qty_plain`**（[`app/utils/qty_display.py`](../../app/utils/qty_display.py)），避免 `0E-8` 等科学计数与无意义尾随零；采购侧收货/确认列表与对比页中的数量列亦同。
- **手工/Excel 流水数量**：方向为 **入库** 时单行数量允许 **0**（须 ≥0）；**出库** 时单行数量须 **>0**（与 `routes_inventory` 解析及 `inventory_svc` 导入校验一致）。
- **库存录入品名搜索下拉**（[`app/templates/inventory/movement_form.html`](../../app/templates/inventory/movement_form.html)）：打开时挂到 **`document.body`** 并用 `getBoundingClientRect` 固定定位，避免表格/`.app-table-scroll` 内层叠与 flex 子项被压扁；关闭、切换类别或删行前移回对应 `td.inv-product-cell`；文档点击关闭时需排除 `.inv-product-dd` 自身以免点选项即被关掉。

## 典型流程

1. **手工/批量流水**：创建 `InventoryMovementBatch` + 明细；部分操作会 `emit_event(EVENT_INVENTORY_CHANGED)` 供编排器使用。
2. **送货出库**：发运后生成出库流水，强调幂等与唯一约束（见服务内注释）；送货批次通常**不可**在库存页随意作废（`void_movement_batch` 限制）。
3. **采购入库**：流水可带 `source_purchase_order_id` / `source_purchase_receipt_id`（与采购对账一致）。

## 权限（模式）

能力键按菜单前缀展开，例如：

- `inventory_ops_finished.movement.create`、`inventory_ops_semi.movement.create`、`inventory_ops_material.movement.create`（三者之一或组合，见 `INVENTORY_CAP_KEYS`）。
- 同类还有 `movement.delete`、`movement_batch.void`、`opening.*`、`daily.*` 等。

**查询**：菜单 `inventory_query`（与 `inventory_stock_query_read_filters` 配合）。

## 关联域

- **送货**：`source_delivery_id` / `source_delivery_item_id`。  
- **采购**：采购单/收货单来源字段。  
- **生产**：测算按 **ATP** 分配库存（预留扣减后再算 `stock_covered`）；预留行在测算成功落库时写入，重算/改草稿/删预计划时删除（见 [production.md](production.md)）。

## 常见问题

- **结存不准**：从期初 + 流水方向核对；注意 `product_id`/`material_id` 为 0 的占位语义。  
- **撤销批次失败**：若为送货关联批次，需走送货/业务规则允许的路径。
