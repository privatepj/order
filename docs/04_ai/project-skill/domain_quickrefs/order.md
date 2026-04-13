# 订单 — 速查

- **模型** `app/models/order.py`：`SalesOrder`、`OrderItem`
- **服务** `app/services/order_svc.py`：创建/预览、按送货回算状态、`EVENT_ORDER_CHANGED`
- **路由** `app/main/routes_order.py`；**模板** `app/templates/order/`（明细行品名搜索 + 规格只读：`textarea` + `autoResize`，见 [../SKILL.md](../SKILL.md)）
- **权限** 菜单 `order`；能力 `order.action.create|edit|delete`
- **全文** [../../02_domains/order.md](../../02_domains/order.md)
