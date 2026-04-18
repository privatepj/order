# 业务域：库存（Inventory）

## 核心概念

- **期初** `InventoryOpeningBalance`：按 `category`、成品 `product_id` 或物料 `material_id`、`storage_area` 等维度。
- **流水** `InventoryMovement`：方向、数量、业务日、`source_type` 及来源 ID（送货、采购单、收货单等）。
- **批次** `InventoryMovementBatch`：一次提交（手工、Excel、送货出库等）的批次头；与多条 `InventoryMovement` 关联。字段 **`source`**：`form` / `excel` / `delivery` 为系统写入；**手工录入页**（非 Excel）可提供「批次来源」：`source` 为空或仅空白时存 `form`（列表仍显示「手工录入」），否则存用户填写的说明（最多 64 字符，不可用保留字 `excel`、`delivery`）。Excel 导入与送货自动出库仍为 `excel` / `delivery`。
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

## 进出明细导出（周/月/自定义）

- **入口**：`GET /inventory/movement/export`（由在线查询页 `inventory/movement_query.html` 的“导出当前结果”触发）。
- **周期参数**：
  - `preset=week|month|custom`
  - `custom` 必填 `start_date` + `end_date`（`YYYY-MM-DD`）
  - `week/month` 未传日期时后端自动回填本周/本月区间
- **可选筛选**：`category`、`direction`、`storage_area`、`name_spec`。
- **权限**：按类别校验 `inventory_ops_*.movement.export`（并叠加菜单可见范围）。
- **保护阈值**：单次导出日期跨度最多 92 天，结果最多 50,000 行，超限需缩小范围。

## 库存录入明细在线查询

- **入口**：`GET /inventory/movement/query`，列表页 `inventory/movement_list.html` 新增「在线查询明细」按钮。
- **用途**：查看**跨批次**库存录入流水；与批次详情 `GET /inventory/batch/<id>` 的区别是，后者仅看单批，前者可跨时间/类别/方向检索。
- **与批次列表关系**：材料、半成品、成品库存批次列表页不再直接提供“导出进出明细”，统一先在线筛选，再按当前结果导出。
- **筛选参数**：
  - `category`
  - `direction`
  - `preset=week|month|custom`
  - `start_date` / `end_date`（`custom` 必填）
  - `storage_area`
  - `name_spec`
- **分页**：每页 30 条，按 `biz_date DESC, movement_id DESC` 排序。
- **权限**：复用各类别 `inventory_ops_*.movement.list`；菜单仍要求具备对应 `inventory_ops_*` 页面入口。
- **导出一致性**：查询页“导出当前结果”直接提交到既有 `/inventory/movement/export`，并携带当前筛选条件；服务层与导出共用同一套过滤逻辑，避免页面与 Excel 口径不一致。

## 数量展示与录入校验

- **页面数量字符串**：模板中对 `Decimal`/`Numeric` 数量优先使用 Jinja 过滤器 **`qty_plain`**（[`app/utils/qty_display.py`](../../app/utils/qty_display.py)），避免 `0E-8` 等科学计数与无意义尾随零；采购侧收货/确认列表与对比页中的数量列亦同。
- **手工/Excel 流水数量**：方向为 **入库** 时单行数量允许 **0**（须 ≥0）；**出库** 时单行数量须 **>0**（与 `routes_inventory` 解析及 `inventory_svc` 导入校验一致）。
- **库存录入品名搜索下拉**（[`app/templates/inventory/movement_form.html`](../../app/templates/inventory/movement_form.html)）：打开时挂到 **`document.body`** 并用 `getBoundingClientRect` 固定定位，避免表格/`.app-table-scroll` 内层叠与 flex 子项被压扁；关闭、切换类别或删行前移回对应 `td.inv-product-cell`；文档点击关闭时需排除 `.inv-product-dd` 自身以免点选项即被关掉。
- **录入列表辅助列（手工录入，非 Excel）**  
  - **当前结存**：选品后调用 `GET /api/inventory/movement-line-on-hand`（`category`、`item_id`、可选 `storage_area`）；数据由 [`inventory_svc.on_hand_for_movement_line`](../../app/services/inventory_svc.py) 计算——仓储区为空时与全仓台账 `ledger_qty_aggregate` 一致；有仓储区时与该品名在该区的期初+流水结存一致（与库存查询按区汇总同口径）。带出默认仓储区后会再请求一次，以便显示本区结存。  
  - **录入后结存（预览）**：仅前端根据当前表头「入库/出库」与本行数量演算（入为加、出为减），**不落库**；数量未填或非法时显示 `-` 或留空。  
  - **权限**：`inventory_ops_{finished|semi|material}.api.movement_line_on_hand`；增量脚本 [`run_83_inventory_movement_line_on_hand_cap.sql`](../../scripts/sql/run_83_inventory_movement_line_on_hand_cap.sql) 从对应 `*.movement.create` 自动授予。

## 典型流程

1. **手工/批量流水**：创建 `InventoryMovementBatch` + 明细；部分操作会 `emit_event(EVENT_INVENTORY_CHANGED)` 供编排器使用。
2. **送货出库**：发运后生成出库流水，强调幂等与唯一约束（见服务内注释）；送货批次通常**不可**在库存页随意作废（`void_movement_batch` 限制）。
3. **采购入库**：流水可带 `source_purchase_order_id` / `source_purchase_receipt_id`（与采购对账一致）。

## 权限（模式）

能力键按菜单前缀展开，例如：

- `inventory_ops_finished.movement.create`、`inventory_ops_semi.movement.create`、`inventory_ops_material.movement.create`（三者之一或组合，见 `INVENTORY_CAP_KEYS`）。
- `inventory_ops_finished.movement.export`、`inventory_ops_semi.movement.export`、`inventory_ops_material.movement.export`（库存进出明细导出）。
- `inventory_ops_finished.api.movement_line_on_hand` 等（录入页「当前结存」接口）。
- 同类还有 `movement.delete`、`movement_batch.void`、`opening.*`、`daily.*` 等。

**查询**：菜单 `inventory_query`（与 `inventory_stock_query_read_filters` 配合）。

## 库存结存查询（`/inventory/query`）

- **结存口径**：期初 + 累计入库 − 累计出库；按类别、仓储区、成品 `product_id` 或半成品/物料 `material_id` 等 bucket 聚合（`inventory_svc.query_stock_aggregate`）。
- **筛选**：`category`、`spec`、`name_spec`、`storage_area`；**系列**（`series`）为下拉，选项来自成品 `product.series` 与 `semi_material`（半成品 `kind=semi`、采购物料 `kind=material`）`semi_material.series` 的去重排序列表，与主数据 `TRIM` 后**精确**匹配；无权限时由 `inventory_stock_query_read_filters` 忽略该参数。能力键：`inventory_query.filter.series`（增量见 `scripts/sql/run_86_product_semi_series_and_stock_query_filter.sql`）。
- **列表**：结果表含「系列」列（成品取 `product.series`，半成品/物料行取 `semi_material.series`）。

## 关联域

- **送货**：`source_delivery_id` / `source_delivery_item_id`。  
- **采购**：采购单/收货单来源字段。  
- **生产**：测算按 **ATP** 分配库存（预留扣减后再算 `stock_covered`）；预留行在测算成功落库时写入，重算/改草稿/删预计划时删除（见 [production.md](production.md)）。

## 常见问题

- **结存不准**：从期初 + 流水方向核对；注意 `product_id`/`material_id` 为 0 的占位语义。  
- **撤销批次失败**：若为送货关联批次，需走送货/业务规则允许的路径。
