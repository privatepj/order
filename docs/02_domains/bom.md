# 业务域：BOM

> 本文档为**骨架**。

## 关键入口

| 层级 | 路径 |
|------|------|
| 路由 | `app/main/routes_bom.py` |
| 服务 | `app/services/bom_svc.py` |
| 多级 Excel | `app/services/bom_multilevel_excel.py` |
| 模板 | `app/templates/` 下 BOM 相关页面 |

## 多级 Excel（导入/导出版式）

- 第 1 行：整行浅蓝底；`A1` 固定为 **品名**（加粗、字号略小）；`B1` 至 **工序** 列合并，内为根父项展示：**编码 - 名称（规格）**（成品为 `product`，半成品/物料根为 `semi_material`），加粗且字号比四号略小一号。
- 表头默认第 3 行；`B` 列至「产品名称」列前一列为层级编码列；导入时合并区左上角 `B1` 可填 **纯 `product_code`**，或与导出一致的 **全称**（系统会按 ` - ` 前段解析编码）。
- 已用区域内单元格细边框。导出与「多级导入模板」样式一致。

## 关联

- 生产测算会消费 BOM（见 [production.md](production.md)）。

## 从表格快速录入（主数据 + 多层 BOM + 工序 + 机台）

批量建种子数据或迁移自 Excel 时，按项目 Skill 步骤操作（表映射、防重 SQL、机台白名单与路由顺序）：

- [../04_ai/project-skill/bom_routing_seed_from_table.md](../04_ai/project-skill/bom_routing_seed_from_table.md)

示例增量脚本：`scripts/sql/run_73_b7_typec9p_bom_process_seed.sql`（`semi_material.name` / `spec` 与主数据表「产品名称」「规格」一致）；历史库可补跑 `run_74`、`run_75`（见各脚本头注释）。
