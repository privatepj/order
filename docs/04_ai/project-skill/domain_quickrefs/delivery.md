# 送货 — 速查

- **模型** `app/models/delivery.py`；**方式常量** `app/utils/delivery_method.py`
- **服务** `app/services/delivery_svc.py`
- **路由** `app/main/routes_delivery.py`；**模板** `app/templates/delivery/`
- **权限** 菜单 `delivery`；发运/打印等见路由 `capability_required`
- **列表** 默认待发（`created`）；有 `delivery.filter.status` 时可用 `status=` / 具体状态查全部或其它；无该能力则固定待发
- **全文** [../../02_domains/delivery.md](../../02_domains/delivery.md)
