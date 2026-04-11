# 业务域：送货（Delivery）

## 核心概念

- **送货单** `Delivery`：单号、客户、快递/配送方式、运单号、状态等。
- **送货明细** `DeliveryItem`：关联 `order_item_id`、数量等。
- **送货方式**（`delivery_method`）：`express`（快递）、`self_delivery`（自配送）、`pickup`（自提）；解析与展示见 [`app/utils/delivery_method.py`](../../app/utils/delivery_method.py)。

**模型**：[`app/models/delivery.py`](../../app/models/delivery.py)  
**服务**：[`app/services/delivery_svc.py`](../../app/services/delivery_svc.py)（创建/预览、待发项、运单更新等）  
**路由**：[`app/main/routes_delivery.py`](../../app/main/routes_delivery.py)  
**模板**：`app/templates/delivery/list.html`、`form.html`、`detail.html`、`print.html`

## 送货状态（`Delivery.status`）

- 包含 `created`、`shipped` 等（以模型与路由业务为准）。
- **订单已发/待发占用**的计算依赖送货单状态与明细；与 `order_svc` 回算一致。
- 状态流转能力：如 `delivery.action.mark_shipped`、`mark_created`、`mark_expired` 等（见路由装饰器）。

## 典型流程

1. 新建送货单：选择订单行、数量；快递场景可占用单号池（逻辑在 `delivery_svc`）。
2. 打印/导出：独立能力 `delivery.action.print`。
3. **发运**后可触发库存出库（见 [inventory.md](inventory.md)）及编排事件（若有订阅）。

## 权限（摘录）

| 类型 | 代码示例 |
|------|-----------|
| 菜单 | `delivery` |
| 能力 | `delivery.action.create`、`detail`、`delete`、`mark_shipped`、`mark_created`、`mark_expired`、`edit_delivery_no`、`edit_waybill`、`clear_waybill`、`print` |
| 报表 | `report_notes`、`report_records` 及相关 `*.page.view` / `*.export.run` |

## 关联域

- **订单**：明细挂 `OrderItem`；影响订单 `pending/partial/delivered`。  
- **库存**：出库流水 `source_type` 与送货关联（`inventory_svc.create_delivery_outbound_movements`）。  
- **快递**：运单与快递公司主数据（见 `routes_express` 等）。

## 常见问题

- **剩余可发数量不对**：查 `delivery_svc.get_pending_order_items` 口径（已发 + 待发占用）。  
- **方式与运单展示**：用 `resolved_delivery_method` / `delivery_method_waybill_text` 等模型辅助属性。
