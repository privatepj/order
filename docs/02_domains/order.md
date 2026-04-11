# 业务域：订单（Order）

## 核心概念

- **销售订单** `SalesOrder`：表头（订单号、客户、交期、付款方式 `payment_type`、状态 `status` 等）。
- **订单行** `OrderItem`：品名规格、数量单价金额；`is_sample`（样板）、`is_spare`（备品）；可选绑定 `customer_product_id`。
- 金额：`OrderItem.compute_amount()` 用数量 × 单价写入 `amount`。

**模型**：[`app/models/order.py`](../../app/models/order.py)  
**服务**：[`app/services/order_svc.py`](../../app/services/order_svc.py)（创建/预览、状态按送货回算等）  
**路由**：[`app/main/routes_order.py`](../../app/main/routes_order.py)  
**模板**：`app/templates/order/list.html`、`form.html`、`detail.html`

## 订单状态（`SalesOrder.status`）

- 典型取值：`pending`（未送完）、`partial`（部分发货）、`delivered`（按业务规则视为送完）。
- 回算逻辑在服务层（如 `recompute_orders_status_for_delivery` / 按订单 ID 批量），**已发货数量**通常只统计 `Delivery.status == "shipped"` 的送货明细（与送货域一致）。

## 典型流程

1. 列表/筛选 → 新建订单 → 保存（多行明细、客户产品可选）。
2. 保存成功后服务层可 **`emit_event(EVENT_ORDER_CHANGED)`**，供编排器触发预计划、采购建议等（见 `order_svc.create_order_from_data` 末尾与 `orchestrator_contracts`）。

## 权限（菜单 / 能力）

以 `routes_order.py` 为准（摘录）：

| 能力 | 说明 |
|------|------|
| 菜单 `order` | 列表、详情等入口 |
| `order.action.create` | 新建 |
| `order.action.edit` | 编辑 |
| `order.action.delete` | 删除 |
| 部分路由允许 `order` 与 `customer_product` 菜单二选一 | 见路由装饰器 |

变更权限时同步更新本文档与 [map_routes_to_services.md](../04_ai/project-skill/map_routes_to_services.md)。

## OpenClaw

- 预览/创建订单：`app/openclaw/routes.py` → `order_svc.preview_order_create` / `create_order_from_data`  
- 规范见 `docs/openclaw-skill/SKILL.md`

## 关联域

- **送货**：`DeliveryItem.order_item_id` 汇总已发/待发占用。  
- **库存 / 生产 / 编排器**：通过事件与状态回算间接关联。

## 常见问题

- **订单状态不对**：先查送货单是否已 `shipped`、明细是否挂到正确 `order_item`。  
- **备品行展示**：`display_product_name` 对备品加后缀（见模型）。
