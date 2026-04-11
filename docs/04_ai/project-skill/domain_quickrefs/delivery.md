# 送货 — 速查

- **模型** `app/models/delivery.py`；**方式常量** `app/utils/delivery_method.py`
- **服务** `app/services/delivery_svc.py`
- **路由** `app/main/routes_delivery.py`；**模板** `app/templates/delivery/`
- **权限** 菜单 `delivery`；发运/打印等见路由 `capability_required`
- **列表** 有 `delivery.filter.status` 时默认待发（`created`）；`status=` 可查全部
- **全文** [../../02_domains/delivery.md](../../02_domains/delivery.md)
