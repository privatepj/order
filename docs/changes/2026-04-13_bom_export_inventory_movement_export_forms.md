# 2026-04-13：BOM 多级导出、库存进出明细导出与表单长文本展示

## 摘要

- **BOM**：列表支持按父项导出**多级 BOM Excel**（新路由 `/boms/export-multilevel`），权限码 `bom.action.export`；实现位于 `app/services/bom_multilevel_excel.py`，与 `bom_svc` 配合。
- **库存**：成品/半成品/材料三类「库存进出」列表支持按条件导出明细 Excel（`/inventory/movement/export`），权限分别为 `inventory_ops_finished|semi|material.movement.export`；查询与组装在 `app/services/inventory_svc.py`。
- **UI**：多类业务表单将品名搜索、只读/可编辑规格等与长文本展示对齐（`textarea` + `name-search-textarea`、`autoResize` 等，见 `app/static/css/app.css` 与各 `app/templates/**/form.html`）。

## 影响范围

- **域**：BOM、库存（成品/半成品/材料录入）、订单/采购/送货/客户产品等表单（长文本展示）。
- **主要模块**：
  - `app/main/routes_bom.py`、`app/main/routes_inventory.py`
  - `app/services/bom_multilevel_excel.py`、`app/services/bom_svc.py`、`app/services/inventory_svc.py`
  - `app/auth/capability_data.py`（库表无能力数据时的兜底与 `run_*` 一致）
  - 模板：`app/templates/bom/*.html`、`inventory/movement_list.html`、若干 `*_form.html`
  - 静态：`app/static/css/app.css`

## 增量部署步骤（生产 / 预发）

1. **发布应用代码**  
   部署包含上述文件的版本（与当前分支一致）。

2. **执行数据库增量脚本（按序号顺序，勿跳过）**  
   在目标库执行（示例，库名以环境为准）：

   ```bash
   mysql -u ... -p sydixon_order < scripts/sql/run_77_bom_export_capability.sql
   mysql -u ... -p sydixon_order < scripts/sql/run_78_inventory_movement_export_capability.sql
   ```

   - `run_77`：写入 `sys_capability`中 `bom.action.export`，并为已有 `bom.action.import` 的角色**默认追加**导出权限。  
   - `run_78`：写入三条 `*.movement.export` 能力，并为已有对应 `*.movement.create` 的角色**默认追加**导出权限。

3. **重启应用进程**  
   确保加载新代码与 RBAC 缓存策略（若环境有菜单/能力缓存，按现有运维习惯刷新或等待失效）。

4. **权限复核（可选）**  
   若某角色不应导出：在「角色-能力」中去掉对应 `cap_code`，增量脚本只做「继承自导入/手工出入库」的默认授权。

## SQL / 全量库

- **新增增量**：`scripts/sql/run_77_bom_export_capability.sql`、`scripts/sql/run_78_inventory_movement_export_capability.sql`（**禁止**修改已上线的旧 `run_*.sql` 文件内容）。  
- **全量**：新建库请使用已对齐的 `scripts/sql/00_full_schema.sql`（内含上述能力种子数据时可不再单独跑 77/78，以实际全量文件为准；若全量已包含等价 `INSERT`，避免重复执行造成困惑，以 DBA 约定为准）。

## 文档 / Skill 同步

- [ ] `docs/02_domains/bom.md`、`docs/02_domains/inventory.md`（若需记录导出入口与权限）  
- [ ] `docs/04_ai/project-skill/domain_quickrefs/inventory.md` 等速查页（若对外说明导出能力）  
- 本文件：`docs/changes/2026-04-13_bom_export_inventory_movement_export_forms.md`

## 验证

- **自动化**：`.\.venv\Scripts\python.exe -m pytest tests/test_bom_multilevel_excel.py`
- **手工**：
  - BOM 列表：选对父项类型与父项后，具备 `bom.action.export` 的用户可下载多级 BOM Excel。  
  - 库存进出列表：具备对应 `*.movement.export` 的用户可从列表页导出，日期范围与行数上限以页面提示为准（代码侧约 92 天、最多 5 万行）。  
  - 抽样打开已改的表单页，确认长品名/规格可换行展示、搜索与高度自适应正常。
