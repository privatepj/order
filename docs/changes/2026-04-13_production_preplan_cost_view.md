# 2026-04-13：预生产详情测算成本单独 RBAC

## 行为

- 新增能力 `production.preplan.cost.view`；预生产计划详情页「预算总成本（元）」仅对有该能力的账号展示并查询 `production_cost_plan_detail` 汇总。
- 测算管线仍照常落库成本明细；仅 Web 展示与详情页成本聚合查询受能力控制。

## 代码与 SQL

- `app/auth/capability_data.py`：兜底注册新能力。
- `app/main/routes_production.py`：`production_preplan_detail` 按 `current_user_can_cap` 条件查询成本合计。
- `app/templates/production/preplan_detail.html`：成本卡片分支展示。
- `scripts/sql/run_79_production_preplan_cost_view_cap.sql`：向 `sys_capability` 登记能力（默认不向既有角色批量授权）。
- `scripts/sql/00_full_schema.sql`：全量种子同步。

## 测试

- `tests/test_production_preplan_cost_view_cap.py`

## 文档

- `docs/02_domains/production.md`、`docs/04_ai/project-skill/rbac_and_menus.md`
