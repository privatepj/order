# 项目 Skill：sydixon-order（仓库内版本）

本 Skill 供 **人类与 AI** 在本仓库内改代码前阅读。目标：先通过文档定位域与入口，再下钻实现；**任何业务逻辑、权限、库表或对外 API 的变更，须同步更新对应文档与本 Skill 子页**（见 [../../changes/README.md](../../changes/README.md)）。

## 必读硬约束

1. **禁止数据库级外键**：SQL 无 `FOREIGN KEY`；ORM 列上不用 `ForeignKey()`，关系用 `primaryjoin` + `foreign(子表.逻辑外键列)`。  
2. **增量 SQL 只增不改**：已存在的 `scripts/sql/run_*.sql` 不得改内容；新变更只新增 `run_NN_*.sql`；全量可维护 `00_full_schema.sql`。

## 改需求时的推荐顺序

1. 打开 [../../index.md](../../index.md)，定位业务域。  
2. 阅读 [../../02_domains/](../../02_domains/) 对应域文档。  
3. 查 [map_routes_to_services.md](map_routes_to_services.md) 锁定 `routes_*` / `services` / `models` / 模板。  
4. 若涉及菜单或按钮权限，读 [rbac_and_menus.md](rbac_and_menus.md)。  
5. 若涉及表结构/SQL，读 [db_rules_and_patterns.md](db_rules_and_patterns.md)。  
6. 改完后：更新域文档 + 本目录相关子页 + 必要时 `docs/changes/` 记录。

## Web UI：长品名与规格（textarea）

业务表单里**易被截断**的「品名关键字搜索」「只读规格」「主数据规格」统一为：

- **样式**：`textarea` + 全局类 `name-search-textarea`（`app/static/css/app.css`），`rows="1"` 起步；与 `.name-wrap` 配合可完整换行展示。
- **脚本**：与品名搜索一致时，查询串用 `normalizeQuery`（空白/换行压成单空格）；`input`/`回填`/`清空` 后对相关 `textarea` 调 **`autoResize`**（高度约 32–96px，超出纵向滚动），避免长文本只见一行。
- **已覆盖页面（维护新表单时请对齐）**  
  - 库存进出：`app/templates/inventory/movement_form.html`（品名搜索 + 规格只读 + 当前结存列 + 录入后结存预览列）  
  - 订单明细：`app/templates/order/form.html`（品名搜索 + 规格只读）  
  - 采购：`app/templates/procurement/order_form.html`、`requisition_form.html`（供应商/物料搜索 + 规格只读）  
  - 主数据规格可编辑：`app/templates/product/form.html`、`semi_material/form.html`、`procurement/material_form.html`（「系列」用于结存查询筛选；另有 **类型**（`nav_type`）用于内部分类/列表筛选，与主数据类别无关）  
  - **成品/半成品 Excel 导入**：模板第 7 列「类型」对应 `nav_type`（内部分类）；详见 [../../02_domains/semi-material.md](../../02_domains/semi-material.md)「Excel 导入与「类型」列」  
  - 其他已用品名 textarea 的库存页：`inventory/daily_form.html`、`inventory/opening_form.html` 等（与 movement 同套路）

## 子文档索引

| 文件 | 用途 |
|------|------|
| [map_routes_to_services.md](map_routes_to_services.md) | 路由文件与服务/域映射 |
| [rbac_and_menus.md](rbac_and_menus.md) | RBAC、缓存失效、混合模式要点 |
| [db_rules_and_patterns.md](db_rules_and_patterns.md) | 迁移与 ORM 无外键写法 |
| [domain_quickrefs/](domain_quickrefs/index.md) | 各域一行速查（链到 02_domains） |
| [bom_routing_seed_from_table.md](bom_routing_seed_from_table.md) | 从工艺/BOM 表批量录入主数据、BOM、工序、机台（种子 SQL 步骤） |

## 与 OpenClaw Skill 的关系

- **OpenClaw**（对外 JSON、确认制）：`docs/openclaw-skill/SKILL.md`  
- **本 Skill**：全仓库 Web、服务、模型、SQL、RBAC 的通用工作方式；二者同时适用时两处都要检查是否需更新。
