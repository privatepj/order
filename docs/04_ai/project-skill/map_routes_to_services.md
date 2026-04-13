# 路由 → 服务 / 域映射

蓝图注册顺序见 [`app/main/__init__.py`](../../../app/main/__init__.py)。下表为 **主站 UI** `app/main/routes_*.py` 与常见服务/域文档对应关系（非穷尽导入，以文件内 `import` 为准）。

| 路由模块 | 主要服务 / 说明 | 域文档 |
|----------|-----------------|--------|
| `routes_customer.py` | `customer_svc` | （客户：可在 order 文档中交叉引用，或后续单开 domain） |
| `routes_order.py` | `order_svc` | [order.md](../../02_domains/order.md) |
| `routes_delivery.py` | `delivery_svc`、`order_svc` | [delivery.md](../../02_domains/delivery.md) |
| `routes_reconciliation.py` | 对账 Excel 等 | — |
| `routes_customer_product.py` | `customer_product_svc`（OpenClaw 等也会用） | — |
| `routes_product.py` | 产品主数据 | — |
| `routes_company.py` | 公司主体 | — |
| `routes_express.py` | 快递/单号池 | [delivery.md](../../02_domains/delivery.md) |
| `routes_user.py` | 用户、pending 审批 | [rbac_and_menus.md](rbac_and_menus.md) |
| `routes_role.py` | 角色授权、`invalidate_rbac_cache` | [rbac_and_menus.md](rbac_and_menus.md) |
| `routes_audit.py` | 审计 UI 上报 | [architecture.md](../../00_overview/architecture.md) |
| `routes_inventory.py` | `inventory_svc`；批次列表 `GET /inventory` 支持 `?category=finished` / `semi` / `material`（与三录入菜单一致，见 inventory 域文档） | [inventory.md](../../02_domains/inventory.md) |
| `routes_semi_material.py` | 半成品/物料页面 | [semi-material.md](../../02_domains/semi-material.md) |
| `routes_bom.py` | `bom_svc` | [bom.md](../../02_domains/bom.md) |
| `routes_production.py` | `production_svc`、`production_schedule_svc`、`production_cost_svc`、`production_preplan_schedule_manual_svc`（预计划人工排程/确认）等 | [production.md](../../02_domains/production.md) |
| `routes_rbac_admin.py` | 导航/能力表维护 | [rbac_and_menus.md](rbac_and_menus.md) |
| `routes_hr.py` | `hr_*_svc` | [hr.md](../../02_domains/hr.md) |
| `routes_employee_schedule.py` | `hr_employee_schedule_svc`、`hr_work_type_svc` | [hr.md](../../02_domains/hr.md) |
| `routes_employee_capability.py` | `hr_employee_capability_svc` 等 | [hr.md](../../02_domains/hr.md) |
| `routes_machine.py` | `machine_schedule_svc` | [machine.md](../../02_domains/machine.md) |
| `routes_procurement.py` | 采购逻辑（多在路由 + 模型） | [procurement.md](../../02_domains/procurement.md) |
| `routes_orchestrator.py` | `orchestrator_engine` | [../../03_orchestrator/index.md](../../03_orchestrator/index.md) |

## 其他入口

| 路径 | 说明 |
|------|------|
| `app/openclaw/routes.py` | 对外 API → 各 `*_svc` |
| `app/auth/routes.py` | 登录/注册/登出 |
| `app/cli_commands.py` | Flask CLI（OpenClaw token、编排任务等） |
