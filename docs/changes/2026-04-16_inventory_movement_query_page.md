# 2026-04-16：库存录入明细在线查询页

## 摘要

- 库存录入新增在线查询页：`GET /inventory/movement/query`。
- 成品、半成品、物料三类库存录入均可按当前授权类别查看**跨批次**流水明细，不再必须先导出 Excel 才能核对。
- 查询页支持按类别、方向、周期、仓储区、品名/规格/编号筛选，并可直接“导出当前结果”。

## 影响范围

- 路由：`app/main/routes_inventory.py`
- 服务：`app/services/inventory_svc.py`
- 模板：`app/templates/inventory/movement_list.html`、`app/templates/inventory/movement_query.html`
- 测试：`tests/test_inventory_movement_query.py`
- 文档：`docs/02_domains/inventory.md`、`docs/04_ai/project-skill/rbac_and_menus.md`

## 权限与菜单

- 菜单：沿用库存录入域 `inventory_ops_finished` / `inventory_ops_semi` / `inventory_ops_material`。
- 能力：**不新增 capability**，查询页按 `category` 复用现有 `inventory_ops_*.movement.list`。
- 行为：
  - 具备菜单但缺少该类别 `movement.list` 时，访问对应类别查询返回 `403`。
  - “导出当前结果”仍使用既有 `inventory_ops_*.movement.export` 控制。

## 实现说明

- 服务层新增分页查询方法，并与既有导出查询共用同一套过滤逻辑，避免在线表格与 Excel 结果口径不一致。
- 列表页新增“在线查询明细”入口按钮，默认带上当前 `category`；原批次列表页“导出进出明细”入口移除。
- 查询页分页参数会保留现有筛选条件。

## 验证

- 自动化：`.\.venv\Scripts\python.exe -m pytest tests/test_inventory_movement_query.py`
- 手工：
  - 进入成品/半成品/材料录入列表，确认存在“在线查询明细”按钮，且不再显示“导出进出明细”。
  - 在查询页按品名/规格/编号筛选，确认表格结果与“导出当前结果”一致。
  - 用仅授权某一类别 `movement.list` 的角色验证其他类别返回 `403`。
